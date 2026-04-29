from __future__ import annotations

import os
import sys
import logging
import tempfile
import threading
import traceback
from gettext import gettext as _

from wubi import errors
from wubi.backends.utils.utils import run_command
from wubi.errors import QuitException
from wubi.info import Info
from wubi.cli import parse_args
from wubi.logger import setup_logger
from version import application_name, version, revision

log = logging.getLogger("application")


class Wubi:

    def __init__(
        self,
        application_name: str,
        version: str,
        revision: str,
        root_dir: str,
    ) -> None:
        self.frontend = None
        self.backend  = None
        self.info = Info(                                    # ← keyword args now valid
            root_dir              = root_dir,
            application_name      = application_name,
            version               = version,
            revision              = revision,
            version_revision      = f"{version}-rev{revision}",
            full_application_name = f"{application_name}-{version}-rev{revision}",
            full_version          = f"{application_name} {version} rev{revision}",
        )

    # ── Entry point ───────────────────────────────────────────────

    def run(self) -> None:
        self.info.quitting = False
        try:
            parse_args(self.info)
            setup_logger(self.info)
            log.info(self.info.full_version)
            log.debug("sys.argv=%s", sys.argv)
            log.debug("Logfile: %s", self.info.log_file)

            self.backend = self._get_backend()
            self.backend.remove_existing_binary()
            self.backend.fetch_basic_info()
            self._select_task()

        except QuitException:
            log.info("Quitting application (QuitException)")

        except Exception:
            tb = traceback.format_exc()
            log.error("Unhandled exception:\n%s", tb)
            self._write_crash_file(tb)
            self._show_fatal_error()

        finally:
            self.on_quit()

    # ── Task routing ──────────────────────────────────────────────

    def _select_task(self) -> None:
        task = self.info.run_task
        dispatch = {
            "install":   self._run_installer,
            "cd_boot":   self._run_cdboot,
            "cdboot":    self._run_cdboot,
            "uninstall": self._run_uninstaller,
            "show_info": self._show_info,
            "showinfo":  self._show_info,
            "reboot":    self._reboot,
            "cd_menu":   self._run_cd_menu,
            "cdmenu":    self._run_cd_menu,
        }
        if task in dispatch:
            dispatch[task]()
        elif self.info.cd_path:
            self._run_cd_menu()
        else:
            self._run_installer()
        self.quit()

    # ── Flows ─────────────────────────────────────────────────────

    def _run_installer(self) -> None:
        if self.info.previous_target_dir and os.path.isdir(self.info.previous_target_dir):
            log.info("Already installed — running uninstaller first")
            self.info.uninstall_before_install = True
            self._run_uninstaller()
            if self.backend:
                self.backend.fetch_basic_info()
            if self.info.previous_target_dir and os.path.isdir(self.info.previous_target_dir):
                msg = _(
                    "A previous installation was detected in %s. "
                    "Uninstall that before continuing."
                ) % self.info.previous_target_dir
                log.error(msg)
                self._get_frontend().show_error_message(msg)
                self.quit()
                return

        log.info("Running the installer…")
        fe = self._get_frontend()
        fe.show_installer_page()
        if self.info.quitting:
            raise QuitException()

        if self.backend:
            tasklist = self.backend.get_installation_tasklist()
            fe.run_tasks(tasklist)

        if not self.info.non_interactive:
            fe.show_installation_finish_page()

        if self.info.run_task == "reboot":
            self.quit()
            self._reboot()

    def _run_uninstaller(self) -> None:
        log.info("Running the uninstaller…")
        if not self.info.previous_target_dir or \
                not os.path.isdir(self.info.previous_target_dir):
            log.error("No previous target dir found — aborting")
            return
        if self.backend and self.backend.run_previous_uninstaller():
            return

        fe = self._get_frontend()
        fe.show_uninstallation_settings()
        try:
            if self.backend:
                fe.run_tasks(self.backend.get_uninstallation_tasklist())
        except errors.WubiCorruptionError:
            msg = _(
                "Files on your computer are corrupted. "
                "A disk check has been scheduled for the next boot. "
                "Please reboot now."
            )
            fe.show_error_message(msg)
            self.quit()
            return

        if not self.info.uninstall_before_install and not self.info.non_interactive:
            fe.show_uninstallation_finish_page()

    def _run_cd_menu(self) -> None:
        log.info("Running the CD menu…")
        if not self.info.cd_distro:
            self._get_frontend().show_error_message(_("No CD detected, cannot run CD menu"))
            self.quit()
            return
        self._get_frontend().show_cd_menu_page()
        self._select_task()

    def _run_cdboot(self) -> None:
        if not self.info.cd_distro:
            msg = _("Could not find any valid CD. CD boot helper can only be used with a Live CD.")
            log.error(msg)
            self._get_frontend().show_error_message(msg)
            self.quit()
            return
        if self.info.previous_target_dir:
            log.info("Already installed — running uninstaller first")
            self.info.uninstall_before_install = True
            self._run_uninstaller()
            if self.backend:
                self.backend.fetch_basic_info()
            if self.info.previous_target_dir:
                msg = _(
                    "A previous installation was detected in %s. "
                    "Uninstall that before continuing."
                ) % self.info.previous_target_dir
                log.error(msg)
                self._get_frontend().show_error_message(msg)
                self.quit()
                return

        fe = self._get_frontend()
        fe.show_cdboot_menu_page()
        if self.backend:
            fe.run_tasks(self.backend.get_cdboot_tasklist())
        fe.show_installation_finish_page()
        if self.info.run_task == "reboot":
            self._reboot()

    def _reboot(self) -> None:
        log.info("Scheduling async reboot")
        def _do_reboot() -> None:
            import time
            time.sleep(2)
            run_command(["shutdown", "-r", "-t", "00"])
        threading.Thread(target=_do_reboot, daemon=True).start()

    def _show_info(self) -> None:
        if self.backend:
            self.backend.show_info()

    # ── Lifecycle ─────────────────────────────────────────────────

    def quit(self) -> None:
        log.debug("application.quit")
        self.info.quitting = True
        if self.frontend:
            try:
                self.frontend.quit()
            except Exception:
                pass
            self.frontend = None

    def on_quit(self) -> None:
        log.debug("application.on_quit")
        if self.frontend:
            try:
                self.frontend.quit()
            except Exception:
                pass
        sys.exit(0)

    # ── Factories ─────────────────────────────────────────────────

    def _get_backend(self):
        from wubi.backends import Backend
        return Backend(self)

    def _get_frontend(self):
        if self.frontend:
            return self.frontend
        from wubi.frontends.tkinter.frontend import WindowsFrontend
        self.frontend = WindowsFrontend(self)
        return self.frontend

    # ── Error helpers ─────────────────────────────────────────────

    def _write_crash_file(self, tb: str) -> None:
        try:
            crash_path = os.path.join(tempfile.gettempdir(), "wubi_crash.txt")
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass

    def _show_fatal_error(self) -> None:
        msg = _(
            "A fatal error occurred.\n\nPlease check the log file for details:\n%s"
        ) % self.info.log_file
        if self.frontend:
            try:
                self.frontend.show_error_message(msg)
                return
            except Exception:
                pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(self.info.application_name or "Wubi", msg)
            root.destroy()
        except Exception:
            print(msg, file=sys.stderr)


if __name__ == "__main__":
    app = Wubi(
        application_name,
        version,
        str(revision),
        os.path.abspath(os.path.dirname(__file__)),
    )
    app.run()