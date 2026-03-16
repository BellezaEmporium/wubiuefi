import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationPage")


class UninstallationPage(Page):

    def on_init(self):
        ttk.Label(self, text=_("Uninstall"),
                 font=("Tahoma", 13, "bold"), bootstyle="primary").pack(pady=(16, 0))

        distro = self.info.previous_distro_name or ""
        ttk.Label(self,
                 text=_("You are about to uninstall %s") % distro,
                 wraplength=440).pack(pady=8)

        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Cancel"),    command=self.on_cancel, bootstyle="secondary-outline").pack(side=RIGHT, padx=8,  pady=8)
        ttk.Button(nav, text=_("Uninstall"), command=self.on_uninstall, bootstyle="primary").pack(side=RIGHT, padx=4, pady=8)

    def on_cancel(self):
        self.frontend.cancel()

    def on_uninstall(self):
        self.frontend.stop()
