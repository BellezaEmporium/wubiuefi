import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from gettext import gettext as _

from wubi.backends.tasklist import Task
from .page import Page
import logging

log = logging.getLogger("TkProgressPage")

class ProgressPage(Page):
    page_title = _("Installing…")
    page_subtitle = _("Please wait while files are copied")

    def on_init(self):
        self._title_var = ttk.StringVar(value=_("Installing..."))
        ttk.Label(self, textvariable=self._title_var,
                  font=("Segoe UI", 12, "bold"),
                  bootstyle="primary").pack(pady=(16, 4))
        ttk.Label(self, text=_("Please wait")).pack()

        self._task_var = ttk.StringVar()
        ttk.Label(self.body, textvariable=self._task_var, anchor="w").pack(fill=X)
        self.progressbar = ttk.Progressbar(self.body, maximum=100,
                                           bootstyle="success-striped")
        self.progressbar.pack(fill=X, pady=6)

        self._subtask_var = ttk.StringVar()
        self._subtask_label = ttk.Label(self.body, textvariable=self._subtask_var,
                                        anchor="w", bootstyle="secondary")
        self._subtask_label.pack(fill=X)
        self.subprogressbar = ttk.Progressbar(self.body, maximum=100,
                                              bootstyle="info-striped")
        self.subprogressbar.pack(fill=X, pady=4)
        self._subtask_label.pack_forget()
        self.subprogressbar.pack_forget()

        ttk.Separator(self).pack(fill=X, side=BOTTOM, pady=(4, 0))
        ttk.Button(self.nav, text=_("Cancel"), command=self.on_cancel,
                   bootstyle="danger-outline").pack(side=RIGHT, padx=8)

    def on_progress(self, task, message=None):
        self.frontend._ui_queue.put(task)

    def _update(self, task) -> None:
        tasklist = task.get_root()
        self._title_var.set(tasklist.description)
        self.progressbar["value"] = int(100 * tasklist.get_percent_of_tasks_completed())
        self._task_var.set(task.description)

        pct = task.get_percent_completed()
        if pct > 0:
            self.subprogressbar["value"] = int(100 * pct)
            self.set_title(_("Installing…"), tasklist.description)
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
