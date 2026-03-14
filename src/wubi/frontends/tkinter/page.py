import tkinter as tk

class Page(tk.Frame):
    def __init__(self, frontend):
        super().__init__(frontend.root, bg="#ffffff")
        self.frontend = frontend
        self.application = frontend.application
        self.info = frontend.application.info
        self.on_init()

    def on_init(self):
        pass

    def show(self):
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.lift()

    def hide(self):
        self.place_forget()
