import ttkbootstrap as ttk
import gettext
import logging
import threading
import queue

_ = gettext.gettext

log = logging.getLogger("WindowsFrontend")


class WindowsFrontend:
    def __init__(self, application) -> None:
        info = application.info
        t = gettext.translation(
            info.application_name,
            localedir=info.translations_dir,
            languages=[info.language],
            fallback=True,
        )
        t.install()

        self.app = application
        self.current_page = None
        self.root = ttk.Window(
            title=info.application_name,
            themename="litera",
            size=(560, 540),
            resizable=(False, False),
        )
        # Set window icon if available
        if info.application_icon:
            try:
                self.root.iconbitmap(info.application_icon)
            except Exception:
                pass

        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self._page_done = threading.Event()
        self._ui_queue = queue.Queue()

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        self._page_done.set()

    def quit(self) -> None:
        self.root.quit()
        self.root.destroy()

    def cancel(self, confirm: bool = False) -> None:
        if confirm:
            from ttkbootstrap.dialogs import Messagebox
            if not Messagebox.yesno(_("Are you sure you want to quit?"), _("Confirm")):
                return
        log.info("Operation cancelled")
        self.app.info.quitting = True
        self.stop()
        self.root.quit()

    def show_page(self, page) -> None:
        if self.current_page and self.current_page is page:
            self.current_page.show()
            return
        if self.current_page:
            self.current_page.hide()
        self.current_page = page
        page.show()

    def _drain_ui_queue(self) -> None:
        """Process all pending UI update tasks from the worker thread."""
        while True:
            try:
                task = self._ui_queue.get_nowait()
                if self.current_page and hasattr(self.current_page, "_update"):
                    self.current_page._update(task)
            except queue.Empty:
                break

    def _wait_for_page(self) -> None:
        from wubi.backends.tasklist import Task

        self._page_done.clear()

        def _poll() -> None:
            if self._page_done.is_set():
                self.root.quit()
                return
            self._drain_ui_queue()
            if hasattr(self, "tasklist") and self.tasklist is not None:
                if self.tasklist.status in (Task.COMPLETED, Task.FAILED, Task.CANCELLED):
                    self.tasklist = None
                    self.stop()
                    self.root.quit()
                    return
            self.root.after(50, _poll)

        self.tasklist = None
        self.root.after(50, _poll)
        self.root.mainloop()

    # ── Page show methods ─────────────────────────────────────────────

    def show_installer_page(self) -> None:
        from .installation_page import InstallationPage
        from .accessibility_page import AccessibilityPage
        self.accessibility_page = AccessibilityPage(self.root, self)
        self.installation_page = InstallationPage(self.root, self)
        self.show_page(self.installation_page)
        self.root.update()
        self._wait_for_page()

    def show_installation_finish_page(self) -> None:
        from .installation_finish_page import InstallationFinishPage
        self.installation_finish_page = InstallationFinishPage(self.root, self)
        self.show_page(self.installation_finish_page)
        self._wait_for_page()

    def show_uninstallation_finish_page(self) -> None:
        from .uninstallation_finish_page import UninstallationFinishPage
        self.uninstallation_finish_page = UninstallationFinishPage(self.root, self)
        self.show_page(self.uninstallation_finish_page)
        self._wait_for_page()

    def show_uninstallation_settings(self) -> None:
        from .uninstallation_page import UninstallationPage
        self.uninstallation_page = UninstallationPage(self.root, self)
        self.show_page(self.uninstallation_page)
        self._wait_for_page()

    def show_cd_menu_page(self) -> None:
        from .cd_menu_page import CDMenuPage
        from .cd_finish_page import CDFinishPage
        self.cd_menu_page = CDMenuPage(self.root, self)
        self.cd_finish_page = CDFinishPage(self.root, self)
        self.show_page(self.cd_menu_page)
        self._wait_for_page()

    def show_cdboot_menu_page(self) -> None:
        from .cdboot_page import CDBootPage
        self.cdboot_page = CDBootPage(self.root, self)
        self.show_page(self.cdboot_page)
        self._wait_for_page()

    # ── Dialogs ───────────────────────────────────────────────────────

    def show_error_message(self, message: str, title: str | None = None) -> None:
        from ttkbootstrap.dialogs import Messagebox
        Messagebox.show_error(str(message), str(title or self.root.title()), parent=self.root)

    def show_info_message(self, message: str, title: str | None = None):
        from ttkbootstrap.dialogs import Messagebox
        return Messagebox.show_info(str(message), str(title or self.root.title()), parent=self.root)

    def ask_confirmation(self, message: str, title: str | None = None) -> bool:
        from ttkbootstrap.dialogs import Messagebox
        return bool(Messagebox.yesno(str(message), str(title or self.root.title()), parent=self.root))

    def ask_to_retry(self, message: str, title: str | None = None) -> bool:
        from ttkbootstrap.dialogs import Messagebox
        result = Messagebox.retrycancel(str(message), str(title or self.root.title()), parent=self.root)
        return result == "Retry"

    # ── Task runner ───────────────────────────────────────────────────

    def run_tasks(self, tasklist) -> None:
        log.debug(f"run_tasks id={id(tasklist)} subtasks={len(tasklist.subtasks)}")
        from .progress_page import ProgressPage

        self.progress_page = ProgressPage(self.root, self)

        def debug_callback(task, message=None) -> None:
            if task.status != getattr(debug_callback, "_last_status", None) or task.error:
                log.debug(
                    f"TASK status={task.status} name={task.name} "
                    f"error={task.error} root_error={task.get_root().error}"
                )
                debug_callback._last_status = task.status
            self.progress_page.on_progress(task, message)

        tasklist.callback = debug_callback
        self.tasklist = tasklist
        tasklist.start()
        log.debug(f"after start id={id(tasklist)} subtasks={len(tasklist.subtasks)}")
        self.show_page(self.progress_page)
        self.root.update()
        self._wait_for_page()
        if tasklist.error:
            exc_type, exc_value, exc_tb = tasklist.error
            raise exc_value.with_traceback(exc_tb)