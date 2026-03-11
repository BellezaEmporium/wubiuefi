import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkCDBootPage")


class CDBootPage(Page):

    def on_init(self):
        tk.Label(self, text=_("CD Boot"),
                 font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))
        tk.Label(self,
                 text=_("Setting up CD boot helper. Please wait."),
                 bg="#ffffff", wraplength=440).pack(pady=8)

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"), command=self.on_cancel).pack(side="right", padx=8, pady=8)
        tk.Button(nav, text=_("Next >>"), command=self.on_next).pack(side="right", padx=4, pady=8)

    def on_cancel(self):
        self.frontend.cancel()

    def on_next(self):
        self.frontend.stop()
