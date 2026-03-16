import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDFinishPage")


class CDFinishPage(Page):

    def on_init(self):
        ttk.Label(self, text=_("CD boot configured"),
                 font=("Tahoma", 13, "bold"), bootstyle="primary").pack(pady=(16, 0))
        ttk.Label(self,
                 text=_("Reboot to try Ubuntu from the CD without installing"),
                 wraplength=440).pack(pady=8)

        self._reboot_var = ttk.StringVar(value="later")
        ttk.Radiobutton(self, text=_("Reboot now"),

                       variable=self._reboot_var, value="now").pack(anchor="w", padx=60)
        ttk.Radiobutton(self, text=_("I want to manually reboot later"),
                       variable=self._reboot_var, value="later").pack(anchor="w", padx=60)

        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Finish"), command=self.on_finish, bootstyle="primary").pack(side=RIGHT, padx=8, pady=8)

    def on_finish(self):
        if self._reboot_var.get() == "now":
            self.info.run_task = "reboot"
        self.frontend.stop()
