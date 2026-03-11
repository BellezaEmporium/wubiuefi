import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDFinishPage")


class CDFinishPage(Page):

    def on_init(self):
        tk.Label(self, text=_("CD boot configured"),
                 font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))
        tk.Label(self,
                 text=_("Reboot to try Ubuntu from the CD without installing"),
                 bg="#ffffff", wraplength=440).pack(pady=8)

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
