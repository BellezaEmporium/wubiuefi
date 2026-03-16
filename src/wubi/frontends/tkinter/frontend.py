import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import gettext
import logging
import gettext
_ = gettext.gettext
import threading

log = logging.getLogger("WindowsFrontend")

class WindowsFrontend:
    def __init__(self, application):
        info = application.info
        t = gettext.translation(
            info.application_name,
            localedir=info.locale_dir,
            languages=[info.language],
            fallback=True
        )
        t.install()

        self.app = application
        self.current_page = None
        self.root = ttk.Window(
            title=info.application_name,
            themename="simplex",
            size=(540, 520),
            resizable=(False, False)
        )
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self._page_done = threading.Event()

    def run(self):
        self.root.mainloop()

    def stop(self):
        self._page_done.set()
    
    def quit(self):
        """Closes the frontend and exits the event loop."""
        self.root.quit()
        self.root.destroy()

    def cancel(self, confirm=False):
        if confirm:
            from ttkbootstrap.dialogs import Messagebox
            if not Messagebox.yesno(_("Are you sure you want to quit?"), _("Confirm")):
                return
        log.info("Operation cancelled")
        self.app.info.quitting = True
        self.stop()
        self.root.quit() 

    def show_page(self, page):
        if self.current_page is page:
            self.current_page.show()
            return
        if self.current_page:
            self.current_page.hide()
        self.current_page = page
        page.show()

    def _wait_for_page(self):
        self._page_done.clear()
        while not self._page_done.is_set():
            self.root.update()
            self.root.after(50, lambda: None)
            self._page_done.wait(0.05)

    def show_installer_page(self):
        from .installation_page import InstallationPage
        from .accessibility_page import AccessibilityPage
        self.accessibility_page = AccessibilityPage(self.root, self)
        self.installation_page = InstallationPage(self.root, self)
        self.show_page(self.installation_page)
        self.root.update()
        self._wait_for_page()

    def show_installation_finish_page(self):
        from .installation_finish_page import InstallationFinishPage
        self.installation_finish_page = InstallationFinishPage(self.root, self)
        self.show_page(self.installation_finish_page)
        self._wait_for_page()

    def show_uninstallation_finish_page(self):
        from .uninstallation_finish_page import UninstallationFinishPage
        self.uninstallation_finish_page = UninstallationFinishPage(self.root, self)
        self.show_page(self.uninstallation_finish_page)
        self._wait_for_page()

    def show_uninstallation_settings(self):
        from .uninstallation_page import UninstallationPage
        self.uninstallation_page = UninstallationPage(self.root, self)
        self.show_page(self.uninstallation_page)
        self._wait_for_page()

    def show_cd_menu_page(self):
        from .cd_menu_page import CDMenuPage
        from .cd_finish_page import CDFinishPage
        self.cd_menu_page = CDMenuPage(self.root, self)
        self.cd_finish_page = CDFinishPage(self.root, self)
        self.show_page(self.cd_menu_page)
        self._wait_for_page()

    def show_cdboot_menu_page(self):
        # Compatibility alias expected by application.py.
        self.show_cd_menu_page()

    def show_error_message(self, message, title=None):
        from ttkbootstrap.dialogs import Messagebox
        if not title:
            title = self.root.title()
        Messagebox.show_error(str(message), str(title), parent=self.root)

    def show_info_message(self, message, title=None):
        from ttkbootstrap.dialogs import Messagebox
        if not title:
            title = self.root.title()
        return Messagebox.show_info(str(message), str(title), parent=self.root)

    def ask_confirmation(self, message, title=None):
        from ttkbootstrap.dialogs import Messagebox
        if not title:
            title = self.root.title()
        return bool(Messagebox.yesno(str(message), str(title), parent=self.root))

    def ask_to_retry(self, message, title=None):
        from tkinter import messagebox
        if not title:
            title = self.root.title()
        return messagebox.askretrycancel(str(title), str(message), parent=self.root)

    def run_tasks(self, tasklist):
        from .progress_page import ProgressPage
        self.progress_page = ProgressPage(self.root, self)
        tasklist.callback = self.progress_page.on_progress
        self.tasklist = tasklist
        tasklist.start()
        self.show_page(self.progress_page)
        self.root.update()
        self._wait_for_page()
        if tasklist.error:
            exc_type, exc_value, exc_tb = tasklist.error
            raise exc_value.with_traceback(exc_tb)
