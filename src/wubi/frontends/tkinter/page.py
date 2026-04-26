import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class Page(ttk.Frame):
    page_title: str = ""
    page_subtitle: str = ""

    def __init__(self, parent, frontend) -> None:
        super().__init__(parent)
        self.frontend = frontend
        self.info = frontend.app.info
        self._build_shell()
        self.on_init()

    def _build_shell(self) -> None:
        # ── Top banner ────────────────────────────────────────────
        banner = ttk.Frame(self, bootstyle="primary", padding=(24, 16))
        banner.pack(fill=X)

        self._title_label = ttk.Label(
            banner,
            text=self.page_title,
            font=("Segoe UI", 14, "bold"),
            bootstyle="inverse-primary",
            anchor="w",
        )
        self._title_label.pack(fill=X)

        self._subtitle_label = ttk.Label(
            banner,
            text=self.page_subtitle,
            font=("Segoe UI", 9),
            bootstyle="inverse-primary",
            anchor="w",
        )
        self._subtitle_label.pack(fill=X)

        ttk.Separator(self).pack(fill=X)

        # ── Content area ──────────────
        self.body = ttk.Frame(self, padding=(28, 16))
        self.body.pack(fill=BOTH, expand=YES)

        ttk.Separator(self).pack(fill=X, side=BOTTOM)

        # ── Nav bar ───────────────────────────────────────────────
        self.nav = ttk.Frame(self, padding=(12, 8))
        self.nav.pack(side=BOTTOM, fill=X)

    def set_title(self, title: str, subtitle: str = "") -> None:
        self._title_label.configure(text=title)
        self._subtitle_label.configure(text=subtitle)

    def on_init(self) -> None:
        pass

    def show(self) -> None:
        self.pack(fill=BOTH, expand=YES)

    def hide(self) -> None:
        self.pack_forget()