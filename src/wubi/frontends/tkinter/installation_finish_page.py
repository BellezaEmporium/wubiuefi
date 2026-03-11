import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkInstallationFinishPage")


class InstallationFinishPage(Page):

    def on_init(self):
        tk.Label(self,
                 text=_("Completing the %s Setup Wizard") % self.info.distro.name,
                 font=("Arial", 16, "bold"), bg="#ffffff", wraplength=440,
                 justify="left").pack(anchor="w", padx=40, pady=(30, 0))

        tk.Label(self,
                 text=_("You need to reboot to complete the installation"),
                 bg="#ffffff", wraplength=440, justify="left").pack(anchor="w", padx=40, pady=(16, 8))

        self._reboot_var = tk.StringVar(value="later")
        tk.Radiobutton(self, text=_("Reboot now"),
                       variable=self._reboot_var, value="now",
                       bg="#ffffff").pack(anchor="w", padx=60)
        tk.Radiobutton(self, text=_("I want to manually reboot later"),
                       variable=self._reboot_var, value="later",
                       bg="#ffffff").pack(anchor="w", padx=60)

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Finish"), command=self.on_finish).pack(side="right", padx=8, pady=8)

    def on_finish(self):
        if self._reboot_var.get() == "now":
            self.info.run_task = "reboot"
        self.frontend.stop()
