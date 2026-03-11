import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationPage")


class UninstallationPage(Page):

    def on_init(self):
        tk.Label(self, text=_("Uninstall"),
                 font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))

        distro = self.info.previous_distro_name or ""
        tk.Label(self,
                 text=_("You are about to uninstall %s") % distro,
                 bg="#ffffff", wraplength=440).pack(pady=8)

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"),    command=self.on_cancel).pack(side="right", padx=8,  pady=8)
        tk.Button(nav, text=_("Uninstall"), command=self.on_uninstall).pack(side="right", padx=4, pady=8)

    def on_cancel(self):
        self.frontend.cancel()

    def on_uninstall(self):
        self.frontend.stop()
