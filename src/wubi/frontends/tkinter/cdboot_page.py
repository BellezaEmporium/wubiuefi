import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDBootPage")

class CDBootPage(Page):

    def on_init(self):
        ttk.Label(self, text=_("CD Boot"),
                  font=("Segoe UI", 13, "bold"),
                  bootstyle="primary").pack(pady=(16, 0))
        ttk.Label(self, text=_("Setting up CD boot helper. Please wait."),
                  wraplength=440).pack(pady=8)

        ttk.Separator(self).pack(fill=X, side=BOTTOM, pady=(4, 0))
        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Cancel"), command=self.on_cancel,
                   bootstyle="secondary-outline").pack(side=RIGHT, padx=8)
        ttk.Button(nav, text=_("Next >>"), command=self.on_next,
                   bootstyle="primary").pack(side=RIGHT, padx=4)

    def on_cancel(self): self.frontend.cancel()
    def on_next(self): self.frontend.stop()