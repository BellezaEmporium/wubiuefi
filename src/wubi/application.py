import os
import sys
import tempfile
import logging
import traceback
import threading
from argparse import ArgumentParser
from gettext import gettext as _

from wubi import errors
from wubi.backends.utils import run_command
from wubi.errors import QuitException
from version import application_name, version, revision

log = logging.getLogger("application")


# ──────────────────────────────────────────────
# Info
# ──────────────────────────────────────────────
class Info(object):
    _ALIASES = {
        "root_dir": "rootdir",
        "force_exit": "forceexit",
        "application_name": "applicationname",
        "version_revision": "versionrevision",
        "full_application_name": "fullapplicationname",
        "full_version": "fullversion",
        "log_file": "logfile",
        "original_exe": "originalexe",
        "use_frontend": "usefrontend",
        "run_task": "runtask",
        "cd_path": "cdpath",
        "previous_target_dir": "previoustargetdir",
        "uninstall_before_install": "uninstallbeforeinstall",
        "cd_distro": "cddistro",
        "iso_distro": "isodistro",
        "target_drive": "targetdrive",
        "installation_size_mb": "installationsizemb",
        "skip_md5_check": "skipmd5check",
        "skip_size_check": "skipsizecheck",
        "skip_memory_check": "skipmemorycheck",
        "force_i386": "forcei386",
        "force_wubi": "forcewubi",
        "image_dir": "imagedir",
        "translations_dir": "translationsdir",
        "application_icon": "applicationicon",
        "iso_md5_hashes": "isomd5hashes",
        "distros_dict": "distrosdict",
        "drives_dict": "drivesdict",
        "previous_uninstaller_path": "previousuninstallerpath",
        "previous_distro_name": "previousdistroname",
        "windows_language": "windowslanguage",
        "host_username": "hostusername",
        "user_full_name": "userfullname",
        "user_directory": "userdirectory",
        "keyboard_layout": "keyboardlayout",
        "keyboard_variant": "keyboardvariant",
        "total_memory_mb": "totalmemorymb",
        "environment_variables": "environmentvariables",
        "os_name": "osname",
        "check_arch": "checkarch",
        "web_proxy": "webproxy",
        "iso_path": "isopath",
        "disk_image_path": "dimagepath",
        "install_dir": "installdir",
        "install_boot_dir": "installbootdir",
        "disks_dir": "disksdir",
        "disks_boot_dir": "disksbootdir",
        "custom_install": "custominstall",
        "no_bittorrent": "nobittorrent",
    }
    _alias_reverse = {}

    def __getattr__(self, name):
        canonical = self._ALIASES.get(name)
        if canonical:
            return object.__getattribute__(self, canonical)
        raise AttributeError(name)

    def __init__(self):
        object.__setattr__(self, "_alias_reverse",
                           {v: k for k, v in self._ALIASES.items()})

        self.root_dir = None
        self.temp_dir = None
        self.data_dir = None
        self.bin_dir = None
        self.image_dir = None
        self.translations_dir = None
        self.trusted_keys = None
        self.application_icon = None
        self.icon = None

        self.force_exit = False
        self.quitting = False

        self.version = None
        self.revision = None
        self.application_name = None
        self.version_revision = None
        self.full_application_name = None
        self.full_version = None

        self.log_file = None
        self.original_exe = None
        self.use_frontend = None
        self.verbosity = None

        self.run_task = None
        self.cd_path = None
        self.iso_path = None
        self.disk_image_path = None

        self.previous_target_dir = None
        self.previous_uninstaller_path = None
        self.previous_distro_name = None
        self.uninstall_before_install = False

        self.non_interactive = False
        self.cd_distro = None
        self.iso_distro = None
        self.distro = None
        self.distro_name = None
        self.distros = []
        self.distros_dict = {}

        self.platform = None
        self.os_name = None
        self.arch = None
        self.check_arch = False
        self.encoding = None
        self.efi = False
        self.environment_variables = {}
        self.iso_md5_hashes = {}

        self.drives = []
        self.drives_dict = {}
        self.system_drive = None
        self.target_drive = None
        self.installation_size_mb = None

        self.language = None
        self.windows_language = None
        self.locale = None
        self.country = None
        self.timezone = None

        self.username = None
        self.password = None
        self.host_username = None
        self.user_full_name = None
        self.user_directory = None

        self.keyboard_layout = None
        self.keyboard_variant = None
        self.accessibility = ""

        self.total_memory_mb = 0

        self.skip_md5_check = False
        self.skip_size_check = False
        self.skip_memory_check = False
        self.no_bittorrent = False
        self.force_i386 = False
        self.force_wubi = False
        self.test = False
        self.debug = False

        self.web_proxy = None

        self.target_dir = None
        self.install_dir = None
        self.install_boot_dir = None
        self.disks_dir = None
        self.disks_boot_dir = None
        self.custom_install = None

        self.root_size_mb = None
        self.swap_size_mb = None
        self.home_size_mb = None
        self.usr_size_mb = None

        self.kernel = None
        self.initrd = None

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)
        alias = self._ALIASES.get(name)
        if alias and getattr(self, alias, None) != value:
            object.__setattr__(self, alias, value)
        canonical = getattr(self, "_alias_reverse", {}).get(name)
        if canonical and getattr(self, canonical, None) != value:
            object.__setattr__(self, canonical, value)

    def update(self, mapping):
        for key, value in mapping.items():
            setattr(self, key, value)

    def __str__(self):
        return "Info(%s)" % self.__dict__


# ──────────────────────────────────────────────
# Wubi
# ──────────────────────────────────────────────
class Wubi(object):

    def __init__(self, application_name, version, revision, root_dir):
        self.frontend = None
        self.backend  = None
        self.info     = Info()

        self.info.root_dir          = root_dir
        self.info.force_exit        = False
        self.info.version           = version
        self.info.revision          = revision
        self.info.application_name  = application_name
        self.info.version_revision  = "%s-rev%s" % (version, revision)
        self.info.full_application_name = "%s-%s-rev%s" % (application_name, version, revision)
        self.info.full_version      = "%s %s rev%s" % (application_name, version, revision)

    # ── Entry point ──────────────────────────

    def run(self):
        self.info.quitting = False
        try:
            self.parse_commandline_arguments()
            self.set_logger()
            log.info(self.info.full_version)
            log.debug("sys.argv=%s", sys.argv)
            log.debug("Logfile: %s", self.info.log_file)

            self.backend = self.get_backend()
            self.backend.remove_existing_binary()
            self.backend.fetch_basic_info()
            self.select_task()

        except errors.QuitException:
            log.info("Quitting application (QuitException)")

        except Exception:
            tb = traceback.format_exc()
            log.error("Unhandled exception:\n%s", tb)
            try:
                crash_path = os.path.join(tempfile.gettempdir(), "wubi_crash.txt")
                with open(crash_path, "w") as f:
                    f.write(tb)
            except Exception:
                pass
            self._show_fatal_error()

        finally:
            self.on_quit()

    def _show_fatal_error(self):
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
            _root = tk.Tk()
            _root.withdraw()
            messagebox.showerror(self.info.application_name or "Wubi", msg)
            _root.destroy()
        except Exception:
            print(msg, file=sys.stderr)

    # ── Lifecycle ────────────────────────────

    def quit(self):
        log.debug("application.quit")
        self.info.quitting = True
        if self.frontend:
            try:
                self.frontend.quit()
            except Exception:
                pass
        self.frontend = None

    def on_quit(self):
        log.debug("application.on_quit")
        if self.frontend:
            try:
                self.frontend.quit()
            except Exception:
                pass
        if self.info.force_exit:
            log.info("Forceful exit via sys.exit")
            sys.exit(0)

    # ── Factory backend / frontend ───────────────

    def get_backend(self):
        from wubi.backends import Backend
        return Backend(self)

    def get_frontend(self):
        if self.frontend:
            return self.frontend
        from wubi.frontends.tkinter.frontend import WindowsFrontend
        self.frontend = WindowsFrontend(self)
        return self.frontend

    # ── Task routing ───────────────────────

    def select_task(self):
        task = self.info.run_task
        dispatch = {
            "install":   self.run_installer,
            "cd_boot":   self.run_cdboot,
            "cdboot":    self.run_cdboot,
            "uninstall": self.run_uninstaller,
            "show_info": self.show_info,
            "showinfo":  self.show_info,
            "reboot":    self.reboot,
            "cd_menu":   self.run_cd_menu,
            "cdmenu":    self.run_cd_menu,
        }
        if task in dispatch:
            dispatch[task]()
        elif self.info.cd_path:
            self.run_cd_menu()
        else:
            self.run_installer()
        self.quit()

    # ── Main flux ──────────────────────────────

    def run_installer(self):
        if self.info.previous_target_dir and os.path.isdir(self.info.previous_target_dir):
            log.info("Already installed — running uninstaller first")
            self.info.uninstall_before_install = True
            self.run_uninstaller()
            if self.backend:
                self.backend.fetch_basic_info()
            if self.info.previous_target_dir and os.path.isdir(self.info.previous_target_dir):
                msg = _("A previous installation was detected in %s. "
                        "Uninstall that before continuing.") % self.info.previous_target_dir
                log.error(msg)
                self.get_frontend().show_error_message(msg)
                self.quit()
                return

        log.info("Running the installer...")
        fe = self.get_frontend()
        fe.show_installer_page()
        if self.info.quitting:
            raise errors.QuitException()
        log.info("Settings received")
        if self.backend:
            log.debug("target_drive=%s" % self.info.target_drive)
            log.debug("distro=%s" % self.info.distro)
            log.debug("installation_size_mb=%s" % self.info.installation_size_mb)
            tasklist = self.backend.get_installation_tasklist()
            log.debug("TASKLIST subtasks count=%d" % len(tasklist.subtasks))
            for t in tasklist.subtasks:
                log.debug("  - %s" % t.name)
            fe.run_tasks(tasklist)
        log.info("Almost finished installing")
        if not self.info.non_interactive:
            fe.show_installation_finish_page()
        log.info("Installation finished")
        if self.info.run_task == "reboot":
            self.quit()
            self.reboot()

    def run_uninstaller(self):
        log.info("Running the uninstaller...")
        if not self.info.previous_target_dir or \
           not os.path.isdir(self.info.previous_target_dir):
            log.error("No previous target dir found — aborting")
            return
        if self.backend and self.backend.run_previous_uninstaller():
            return

        fe = self.get_frontend()
        fe.show_uninstallation_settings()
        log.info("Settings received")
        try:
            if self.backend:
                fe.run_tasks(self.backend.get_uninstallation_tasklist())
        except errors.WubiCorruptionError:
            msg = _("Files on your computer are corrupted. "
                    "A disk check has been scheduled for the next boot. "
                    "Please reboot now.")
            fe.show_error_message(msg)
            self.quit()
            return

        log.info("Almost finished uninstalling")
        if not self.info.uninstall_before_install and not self.info.non_interactive:
            fe.show_uninstallation_finish_page()
        log.info("Uninstallation finished")

    def run_cd_menu(self):
        log.info("Running the CD menu...")
        if not self.info.cd_distro:
            self.get_frontend().show_error_message(_("No CD detected, cannot run CD menu"))
            self.quit()
            return
        self.get_frontend().show_cd_menu_page()
        log.info("CD menu finished")
        self.select_task()

    def run_cdboot(self):
        if not self.info.cd_distro:
            msg = _("Could not find any valid CD. "
                    "CD boot helper can only be used with a Live CD.")
            log.error(msg)
            self.get_frontend().show_error_message(msg)
            self.quit()
            return
        if self.info.previous_target_dir:
            log.info("Already installed — running uninstaller first")
            self.info.uninstall_before_install = True
            self.run_uninstaller()
            if self.backend:
                self.backend.fetch_basic_info()
            if self.info.previous_target_dir:
                msg = _("A previous installation was detected in %s. "
                        "Uninstall that before continuing.") % self.info.previous_target_dir
                log.error(msg)
                self.get_frontend().show_error_message(msg)
                self.quit()
                return

        log.info("Running the CD boot helper...")
        fe = self.get_frontend()
        fe.show_cdboot_menu_page()
        log.info("CD boot confirmed")
        if self.backend:
            fe.run_tasks(self.backend.get_cdboot_tasklist())
        log.info("Almost finished")
        fe.show_installation_finish_page()
        log.info("Finished")
        if self.info.run_task == "reboot":
            self.reboot()

    def reboot(self):
        log.info("Scheduling async reboot")
        def _do_reboot():
            import time
            time.sleep(2)
            run_command(['shutdown', '-r', '-t', '00'])
        t = threading.Thread(target=_do_reboot, daemon=True)
        t.start()

    def show_info(self):
        if self.backend:
            self.backend.show_info()

    # ── Parsing CLI ──────────────────────────────

    def parse_commandline_arguments(self):
        parser = ArgumentParser(prog=self.info.application_name)
        parser.add_argument("--quiet",          action="store_const", const="quiet",     dest="verbosity")
        parser.add_argument("--verbose",        action="store_const", const="verbose",   dest="verbosity")
        parser.add_argument("--install",        action="store_const", const="install",   dest="run_task")
        parser.add_argument("--uninstall",      action="store_const", const="uninstall", dest="run_task")
        parser.add_argument("--cdmenu",         action="store_const", const="cd_menu",   dest="run_task")
        parser.add_argument("--cdboot",         action="store_const", const="cd_boot",   dest="run_task")
        parser.add_argument("--showinfo",       action="store_const", const="show_info", dest="run_task")
        parser.add_argument("--nobittorrent",   action="store_true",  dest="no_bittorrent")
        parser.add_argument("--32bit",          action="store_true",  dest="force_i386")
        parser.add_argument("--skipmd5check",   action="store_true",  dest="skip_md5_check")
        parser.add_argument("--skipsizecheck",  action="store_true",  dest="skip_size_check")
        parser.add_argument("--skipmemorycheck",action="store_true",  dest="skip_memory_check")
        parser.add_argument("--noninteractive", action="store_true",  dest="non_interactive")
        parser.add_argument("--test",           action="store_true",  dest="test")
        parser.add_argument("--debug",          action="store_true",  dest="debug")
        parser.add_argument("--drive",          dest="target_drive")
        parser.add_argument("--size",           type=int,             dest="installation_size_mb")
        parser.add_argument("--locale",         dest="locale")
        parser.add_argument("--force-wubi",     action="store_true",  dest="force_wubi")
        parser.add_argument("--language",       dest="language")
        parser.add_argument("--username",       dest="username")
        parser.add_argument("--password",       dest="password")
        parser.add_argument("--distro",         dest="distro_name")
        parser.add_argument("--accessibility",  dest="accessibility")
        parser.add_argument("--webproxy",       dest="web_proxy")
        parser.add_argument("--isopath",        dest="iso_path")
        parser.add_argument("--dimagepath",     dest="disk_image_path")
        parser.add_argument("--exefile",        dest="original_exe",  default=None)
        parser.add_argument("--log-file",       dest="log_file",      default=None)
        parser.add_argument("--interface",      dest="use_frontend",  default=None)

        args = parser.parse_args()
        self.info.update(vars(args))

        if self.info.test or self.info.debug:
            self.info.verbosity = "verbose"

        if self.info.original_exe:
            exe = self.info.original_exe.strip().strip("'\"")
            self.info.original_exe = exe
            if os.path.basename(exe).lower().startswith("uninstall-"):
                self.info.run_task = "uninstall"

    # ── Logger ───────────────────────────────────

    def set_logger(self, log_to_console=True):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        for h in list(root.handlers):
            root.removeHandler(h)

        if not self.info.log_file or self.info.log_file.lower() != "none":
            if not self.info.log_file:
                filename = (self.info.full_application_name or "wubi") + ".log"
                self.info.log_file = os.path.join(tempfile.gettempdir(), filename)
            fh = logging.FileHandler(self.info.log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)-6s %(name)s: %(message)s",
                datefmt="%m-%d %H:%M"))
            fh.setLevel(logging.DEBUG)
            root.addHandler(fh)

        if log_to_console and not self.info.original_exe:
            ch = logging.StreamHandler(sys.stderr)
            ch.setFormatter(logging.Formatter("%(levelname)-6s %(message)s"))
            ch.setLevel(
                logging.DEBUG if self.info.verbosity == "verbose"
                else logging.ERROR if self.info.verbosity == "quiet"
                else logging.INFO
            )
            root.addHandler(ch)


if __name__ == "__main__":
    app = Wubi(application_name, version, revision,
               os.path.abspath(os.path.dirname(__file__)))
    app.run()
