import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkUninstallationFinishPage")


class UninstallationFinishPage(Page):

    page_title = _("Uninstallation Complete")
    page_subtitle = _("Your Linux uninstallation is complete")

    def on_init(self) -> None:
        ttk.Label(
            self.body,
            text=_("You need to reboot your computer to complete the uninstallation."),
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        group = ttk.Labelframe(self.body, text=_("Restart options"), padding=12)
        group.pack(fill=X, pady=4)

        self._reboot_var = ttk.StringVar(value="later")
        ttk.Radiobutton(group, text=_("Reboot now"),
                        variable=self._reboot_var, value="now").pack(anchor="w", pady=2)
        ttk.Radiobutton(group, text=_("I want to manually reboot later"),
                        variable=self._reboot_var, value="later").pack(anchor="w", pady=2)

        ttk.Button(self.nav, text=_("Finish"), command=self.on_finish,
                   bootstyle="primary").pack(side=RIGHT, padx=8, pady=4)

    def on_finish(self):
        if self._reboot_var.get() == "now":
            self.info.run_task = "reboot"
        self.frontend.stop()
