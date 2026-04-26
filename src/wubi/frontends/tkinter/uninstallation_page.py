import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationPage")


class UninstallationPage(Page):
    page_title = _("Uninstall Linux")
    page_subtitle = _("This will remove the Linux installation from your computer")

    def on_init(self) -> None:
        distro = self.info.previous_distro_name or "Linux"

        ttk.Label(
            self.body,
            text=f"⚠  {_('You are about to permanently remove %s.') % distro}",
            bootstyle="danger",
            font=("Segoe UI", 10, "bold"),
            wraplength=460,
        ).pack(anchor="w", pady=(8, 4))

        ttk.Label(
            self.body,
            text=_("All data stored inside the Linux installation will be lost. "
                   "Data on your Windows partition will not be affected."),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        ttk.Button(self.nav, text=_("Cancel"),
                   command=self.on_cancel, bootstyle="secondary-outline").pack(side=RIGHT, padx=8)
        ttk.Button(self.nav, text=_("Uninstall"),
                   command=self.on_uninstall, bootstyle="danger").pack(side=RIGHT, padx=4)

    def on_cancel(self):
        self.frontend.cancel()

    def on_uninstall(self):
        self.frontend.stop()
