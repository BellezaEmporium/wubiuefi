import tkinter as tk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkAccessibilityPage")


class AccessibilityPage(Page):

    def on_init(self):
        self.info.accessibility = ""

        tk.Label(self, text=_("Accessibility profile"),
                 font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))
        tk.Label(self, text=_("Please select the appropriate accessibility profile"),
                 bg="#ffffff").pack()

        body = tk.Frame(self, bg="#ffffff")
        body.pack(fill="both", expand=True, padx=24, pady=12)

        self._access_var = tk.StringVar(value="none")

        # Groupe Visibilité
        vis = tk.LabelFrame(body, text=_("Visibility Aids"), bg="#ffffff")
        vis.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        for val, label in [
            ("access=visibility1", _("Visibility1")),
            ("access=visibility2", _("Visibility2")),
            ("access=visibility3", _("Visibility3")),
            ("braille=ask",        _("Braille")),
        ]:
            tk.Radiobutton(vis, text=label, variable=self._access_var,
                           value=val, bg="#ffffff").pack(anchor="w", padx=8, pady=2)

        # Groupe Mobilité
        mob = tk.LabelFrame(body, text=_("Mobility Aids"), bg="#ffffff")
        mob.grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        for val, label in [
            ("access=mobility1", _("Mobility1")),
            ("access=mobility2", _("Mobility2")),
        ]:
            tk.Radiobutton(mob, text=label, variable=self._access_var,
                           value=val, bg="#ffffff").pack(anchor="w", padx=8, pady=2)

        tk.Radiobutton(body, text=_("None"), variable=self._access_var,
                       value="none", bg="#ffffff").grid(row=1, column=0, sticky="w", padx=8)

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"), command=self.on_cancel).pack(side="right", padx=8, pady=8)
        tk.Button(nav, text=_("Next >>"), command=self.on_next).pack(side="right", padx=4, pady=8)

    def on_cancel(self):
        self.frontend.cancel()

    def on_next(self):
        val = self._access_var.get()
        self.info.accessibility = "" if val == "none" else val
        self.frontend.show_page(self.frontend.installation_page)
