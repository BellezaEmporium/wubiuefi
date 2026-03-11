import tkinter as tk
from tkinter import messagebox
from gettext import gettext as _
from wubi.errors import QuitException
from .installation_page import InstallationPage
from .progress_page import ProgressPage
from .accessibility_page import AccessibilityPage
import logging

log = logging.getLogger("TkFrontend")


class TkFrontend:

    def __init__(self, application):
        self.application = application
        self.current_page = None
        self.tasklist = None

        self.root = tk.Tk()
        self.root.title(application.info.application_name)
        self.root.geometry("504x385")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)

        try:
            self.root.iconbitmap(str(application.info.application_icon))
        except Exception:
            pass

    def run(self):
        if self.application.info.quitting:
            raise QuitException()
        self.root.mainloop()
        if self.application.info.quitting:
            raise QuitException()

    def stop(self):
        """Quitte la boucle mainloop courante sans fermer la fenêtre."""
        self.root.quit()

    def quit(self):
        log.debug("frontend.quit")
        self.application.info.quitting = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def cancel(self, confirm=False):
        if confirm:
            if not self.ask_confirmation(_("Are you sure you want to quit?")):
                return
        self.quit()

    def on_quit(self):
        if self.tasklist and self.tasklist.is_alive():
            log.debug("Stopping background tasks: %s" % self.tasklist.name)
            self.tasklist.cancel()
            self.tasklist.join(3)
            if self.tasklist.is_alive():
                self.application.info.force_exit = True
        self.application.on_quit()

    def show_page(self, page):
        if self.current_page is page:
            page.show()
            return
        if self.current_page:
            self.current_page.hide()
        self.current_page = page
        page.show()
        self.root.deiconify()
        self.run()

    def show_installation_settings(self):
        self.accessibility_page = AccessibilityPage(self)
        self.installation_page = InstallationPage(self)
        if not self.application.info.non_interactive:
            self.show_page(self.installation_page)

    def show_uninstallation_settings(self):
        from .uninstallation_page import UninstallationPage
        self.uninstallation_page = UninstallationPage(self)
        self.show_page(self.uninstallation_page)

    def show_installation_finish_page(self):
        from .installation_finish_page import InstallationFinishPage
        self.installation_finish_page = InstallationFinishPage(self)
        self.show_page(self.installation_finish_page)

    def show_uninstallation_finish_page(self):
        from .uninstallation_finish_page import UninstallationFinishPage
        self.uninstallation_finish_page = UninstallationFinishPage(self)
        self.show_page(self.uninstallation_finish_page)

    def run_tasks(self, tasklist):
        self.progress_page = ProgressPage(self)
        tasklist.callback = self.progress_page.on_progress
        self.tasklist = tasklist
        tasklist.start()
        self.show_page(self.progress_page)
        if isinstance(tasklist.error, Exception):
            raise tasklist.error
        elif isinstance(tasklist.error, tuple):
            raise tasklist.error[0](tasklist.error[1]).with_traceback(tasklist.error[2])

    def show_error_message(self, message, title=None):
        messagebox.showerror(title or self.root.title(), str(message))

    def show_info_message(self, message, title=None):
        messagebox.showinfo(title or self.root.title(), str(message))

    def ask_confirmation(self, message, title=None):
        return messagebox.askyesno(title or self.root.title(), str(message))

    def set_title(self, title):
        self.root.title(title)

    def set_icon(self, path):
        try:
            self.root.iconbitmap(str(path))
        except Exception:
            pass
