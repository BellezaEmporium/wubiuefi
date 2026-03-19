import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _

from wubi.backends.tasklist import Task
from .page import Page
import logging

log = logging.getLogger("TkProgressPage")

class ProgressPage(Page):

    def on_init(self):
        self._title_var = ttk.StringVar(value=_("Installing..."))
        ttk.Label(self, textvariable=self._title_var,
                  font=("Segoe UI", 12, "bold"),
                  bootstyle="primary").pack(pady=(16, 4))
        ttk.Label(self, text=_("Please wait")).pack()

        body = ttk.Frame(self)
        body.pack(fill=BOTH, expand=YES, padx=24, pady=12)

        self._task_var = ttk.StringVar()
        ttk.Label(body, textvariable=self._task_var, anchor="w").pack(fill=X)
        self.progressbar = ttk.Progressbar(body, maximum=100,
                                           bootstyle="success-striped")
        self.progressbar.pack(fill=X, pady=4)

        self._subtask_var = ttk.StringVar()
        self._subtask_label = ttk.Label(body, textvariable=self._subtask_var,
                                        anchor="w", bootstyle="secondary")
        self._subtask_label.pack(fill=X)
        self.subprogressbar = ttk.Progressbar(body, maximum=100,
                                              bootstyle="info-striped")
        self.subprogressbar.pack(fill=X, pady=4)
        self._subtask_label.pack_forget()
        self.subprogressbar.pack_forget()

        ttk.Separator(self).pack(fill=X, side=BOTTOM, pady=(4, 0))
        nav = ttk.Frame(self, padding=(8, 6))
        nav.pack(side=BOTTOM, fill=X)
        ttk.Button(nav, text=_("Cancel"), command=self.on_cancel,
                   bootstyle="danger-outline").pack(side=RIGHT, padx=8)

    def on_progress(self, task, message=None):
        """Callback appelé depuis le thread des tâches — doit passer par after()."""
        self.frontend._ui_queue.put(task)
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

        if tasklist.status == Task.COMPLETED:
            self.progressbar["value"] = 100
            self.frontend.stop()
        elif tasklist.status in (Task.FAILED, Task.CANCELLED):
            self.frontend.stop()

    def on_cancel(self):
        self.frontend.cancel(confirm=True)
