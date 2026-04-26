import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkAccessibilityPage")

class AccessibilityPage(Page):

    def on_init(self):
        self.info.accessibility = ""

        ttk.Label(self, text=_("Accessibility profile"),
                  font=("Segoe UI", 13, "bold"),
                  bootstyle="primary").pack(pady=(16, 0))
        ttk.Label(self, text=_("Please select the appropriate accessibility profile")).pack()

        self._access_var = ttk.StringVar(value="none")

        vis = ttk.Labelframe(self.body, text=_("Visibility Aids"), padding=8)
        vis.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        for val, label in [
            ("access=visibility1", _("Visibility1")),
            ("access=visibility2", _("Visibility2")),
            ("access=visibility3", _("Visibility3")),
            ("braille=ask",        _("Braille")),
        ]:
            ttk.Radiobutton(vis, text=label, variable=self._access_var,
                            value=val).pack(anchor=W, pady=2)

        mob = ttk.Labelframe(self.body, text=_("Mobility Aids"), padding=8)
        mob.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        for val, label in [
            ("access=mobility1", _("Mobility1")),
            ("access=mobility2", _("Mobility2")),
        ]:
            ttk.Radiobutton(mob, text=label, variable=self._access_var,
                            value=val).pack(anchor=W, pady=2)

        ttk.Radiobutton(self.body, text=_("None"), variable=self._access_var,
                        value="none").grid(row=1, column=0, sticky=W, padx=8)

        ttk.Separator(self).pack(fill=X, side=BOTTOM, pady=(4, 0))
        ttk.Button(self.nav, text=_("Cancel"), command=self.on_cancel,
                   bootstyle="secondary-outline").pack(side=RIGHT, padx=8)
        ttk.Button(self.nav, text=_("Next >>"), command=self.on_next,
                   bootstyle="primary").pack(side=RIGHT, padx=4)

    def on_cancel(self):
        self.frontend.cancel()

    def on_next(self):
        val = self._access_var.get()
        self.info.accessibility = "" if val == "none" else val
        self.frontend.show_page(self.frontend.installation_page)