import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationFinishPage")


class UninstallationFinishPage(Page):

    def on_init(self):
        distro = self.info.previous_distro_name or ""
        tk.Label(self,
                 text=_("Completing the %s Uninstall Wizard") % distro,
                 font=("Arial", 16, "bold"), bg="#ffffff", wraplength=440,
                 justify="left").pack(anchor="w", padx=40, pady=(30, 0))

        tk.Label(self,
                 text=_("You need to reboot to complete the uninstallation"),
                 bg="#ffffff", wraplength=440).pack(anchor="w", padx=40, pady=(16, 8))

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
