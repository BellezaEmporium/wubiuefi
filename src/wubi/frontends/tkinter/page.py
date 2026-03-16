import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class Page(ttk.Frame):
    def __init__(self, parent, frontend):
        super().__init__(parent, padding=20)
        self.frontend = frontend
        self.info = frontend.app.info
        self.on_init()

    def on_init(self):
        pass

    def show(self):
        self.pack(fill=BOTH, expand=YES)

    def hide(self):
        self.pack_forget()
