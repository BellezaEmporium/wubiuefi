import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationFinishPage")


class UninstallationFinishPage(Page):

    def on_init(self):
        distro = self.info.previous_distro_name or ""
        ttk.Label(self,
                  text=_("Completing the %s Uninstall Wizard") % distro,
                  font=("Segoe UI", 16, "bold"),
                  bootstyle="primary").pack(anchor="w", padx=40, pady=(30, 0))

        ttk.Label(self,
                  text=_("You need to reboot to complete the uninstallation"),
                  wraplength=440).pack(anchor="w", padx=40, pady=(16, 8))

        self._reboot_var = ttk.StringVar(value="later")
        ttk.Radiobutton(self, text=_("Reboot now"),
                        variable=self._reboot_var, value="now").pack(anchor="w", padx=60)
        ttk.Radiobutton(self, text=_("I want to manually reboot later"),
                        variable=self._reboot_var, value="later").pack(anchor="w", padx=60)

        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Finish"), command=self.on_finish,
                   bootstyle="primary").pack(side=RIGHT, padx=8, pady=8)

    def on_finish(self):
        if self._reboot_var.get() == "now":
            self.info.run_task = "reboot"
        self.frontend.stop()
