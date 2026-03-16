import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDMenuPage")

class CDMenuPage(Page):

    def on_init(self):
        ttk.Label(self, text=_("CD detected"),
                  font=("Segoe UI", 13, "bold"),
                  bootstyle="primary").pack(pady=(16, 0))
        ttk.Label(self,
                  text=_("A Ubuntu CD has been detected. What do you want to do?"),
                  wraplength=440).pack(pady=8)

        self._choice_var = ttk.StringVar(value="install")
        ttk.Radiobutton(self, text=_("Install inside Windows"),
                        variable=self._choice_var, value="install").pack(anchor=W, padx=60)
        ttk.Radiobutton(self, text=_("Boot from CD"),
                        variable=self._choice_var, value="cdboot").pack(anchor=W, padx=60)
        ttk.Radiobutton(self, text=_("Demo Ubuntu without any change to your computer"),
                        variable=self._choice_var, value="demo").pack(anchor=W, padx=60)

        ttk.Separator(self).pack(fill=X, side=BOTTOM, pady=(4, 0))
        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Cancel"), command=self.on_cancel,
                   bootstyle="secondary-outline").pack(side=RIGHT, padx=8)
        ttk.Button(nav, text=_("Next >>"), command=self.on_next,
                   bootstyle="primary").pack(side=RIGHT, padx=4)

    def on_cancel(self):
        self.frontend.cancel()

    def on_next(self):
        choice = self._choice_var.get()
        if choice == "install":
            self.frontend.show_installation_settings()
        elif choice == "cdboot":
            self.frontend.show_cdboot_page()
        else:
            self.info.show_info()
            self.frontend.stop()