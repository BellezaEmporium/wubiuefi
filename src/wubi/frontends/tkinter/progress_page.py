import tkinter as tk
from tkinter import ttk
from gettext import gettext as _
from .page import Page
import logging

log = logging.getLogger("TkProgressPage")


class ProgressPage(Page):

    def on_init(self):
        self._title_var = tk.StringVar(value=_("Installing..."))
        tk.Label(self, textvariable=self._title_var, font=("Tahoma", 12, "bold"), bg="#ffffff").pack(pady=(16, 4))
        tk.Label(self, text=_("Please wait"), bg="#ffffff").pack()

        body = tk.Frame(self, bg="#ffffff")
        body.pack(fill="both", expand=True, padx=24, pady=12)

        self._task_var = tk.StringVar()
        tk.Label(body, textvariable=self._task_var, bg="#ffffff", anchor="w").pack(fill="x")
        self.progressbar = ttk.Progressbar(body, maximum=100)
        self.progressbar.pack(fill="x", pady=4)

        self._subtask_var = tk.StringVar()
        self._subtask_label = tk.Label(body, textvariable=self._subtask_var, bg="#ffffff", anchor="w")
        self._subtask_label.pack(fill="x")
        self.subprogressbar = ttk.Progressbar(body, maximum=100)
        self.subprogressbar.pack(fill="x", pady=4)
        self._subtask_label.pack_forget()
        self.subprogressbar.pack_forget()

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"), command=self.on_cancel).pack(side="right", padx=8, pady=8)

    def on_progress(self, task, message=None):
        """Callback appelé depuis le thread des tâches — doit passer par after()."""
        self.frontend.root.after(0, self._update, task)

    def _update(self, task):
        tasklist = task.get_root()
        self._title_var.set(tasklist.description)
        self.progressbar["value"] = int(100 * tasklist.get_percent_of_tasks_completed())
        self._task_var.set(task.description)

        pct = task.get_percent_completed()
        if pct > 0:
            self.subprogressbar["value"] = int(100 * pct)
            remaining = task.estimate_remaining_time()[0]
            self._subtask_var.set(_("Remaining time approximately %s") % remaining)
            self._subtask_label.pack(fill="x")
            self.subprogressbar.pack(fill="x", pady=4)
        else:
            self._subtask_label.pack_forget()
            self.subprogressbar.pack_forget()

        if tasklist.status is not tasklist.ACTIVE:
            self.progressbar["value"] = 100
            self.frontend.stop()

    def on_cancel(self):
        self.frontend.cancel(confirm=True)
