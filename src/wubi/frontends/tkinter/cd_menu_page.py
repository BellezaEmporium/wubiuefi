import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDMenuPage")


class CDMenuPage(Page):

    def on_init(self):
        tk.Label(self, text=_("CD detected"),
                 font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))

        distro = getattr(self.info.cd_distro, "name", "") if self.info.cd_distro else ""
        tk.Label(self,
                 text=_("A Ubuntu CD has been detected. What do you want to do?"),
                 bg="#ffffff", wraplength=440).pack(pady=8)

        self._choice_var = tk.StringVar(value="install")
        tk.Radiobutton(self, text=_("Install inside Windows"),
                       variable=self._choice_var, value="install",
                       bg="#ffffff").pack(anchor="w", padx=60)
        tk.Radiobutton(self, text=_("Boot from CD"),
                       variable=self._choice_var, value="cdboot",
                       bg="#ffffff").pack(anchor="w", padx=60)
        tk.Radiobutton(self, text=_("Demo Ubuntu without any change to your computer"),
                       variable=self._choice_var, value="demo",
                       bg="#ffffff").pack(anchor="w", padx=60)

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"), command=self.on_cancel).pack(side="right", padx=8, pady=8)
        tk.Button(nav, text=_("Next >>"), command=self.on_next).pack(side="right", padx=4, pady=8)

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
