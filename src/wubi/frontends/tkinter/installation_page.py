import re
import tkinter as tk
from tkinter import ttk, messagebox
from gettext import gettext as _
from .page import Page
from wubi.backends.common.mappings import (
    reserved_usernames,
    lang_country2linux_locale,
    language2lang_country,
    lang_country2language,
)
import logging, gettext

log = logging.getLogger("TkInstallationPage")
reserved_usernames = [str(n) for n in reserved_usernames]
re_username_first = re.compile(r"^[a-z]")
re_username = re.compile(r"[a-z][-a-z0-9_]*$")


class InstallationPage(Page):

    def on_init(self):
        tk.Label(self, text=_("Installing"), font=("Tahoma", 13, "bold"), bg="#ffffff").pack(pady=(16, 0))
        tk.Label(self, text=_("Please select username and password for the new account"),
                 bg="#ffffff").pack()

        form = tk.Frame(self, bg="#ffffff")
        form.pack(fill="both", expand=True, padx=24, pady=12)

        # --- Colonne gauche ---
        tk.Label(form, text=_("Installation drive:"), bg="#ffffff", anchor="w").grid(row=0, column=0, sticky="w")
        self._drive_var = tk.StringVar()
        self.target_drive_list = ttk.Combobox(form, textvariable=self._drive_var, state="readonly", width=22)
        self.target_drive_list.grid(row=1, column=0, sticky="w", pady=(0, 10))
        self.target_drive_list.bind("<<ComboboxSelected>>", lambda e: self.on_drive_change())

        tk.Label(form, text=_("Installation size:"), bg="#ffffff", anchor="w").grid(row=2, column=0, sticky="w")
        self._size_var = tk.StringVar()
        self.size_list = ttk.Combobox(form, textvariable=self._size_var, state="readonly", width=22)
        self.size_list.grid(row=3, column=0, sticky="w", pady=(0, 10))
        self.size_list.bind("<<ComboboxSelected>>", lambda e: self.on_size_change())

        tk.Label(form, text=_("Desktop environment:"), bg="#ffffff", anchor="w").grid(row=4, column=0, sticky="w")
        self._distro_var = tk.StringVar()
        self.distro_list = ttk.Combobox(form, textvariable=self._distro_var, state="readonly", width=22)
        self.distro_list.grid(row=5, column=0, sticky="w", pady=(0, 10))
        self.distro_list.bind("<<ComboboxSelected>>", lambda e: self.on_distro_change())

        # --- Colonne droite ---
        tk.Label(form, text=_("Language:"), bg="#ffffff", anchor="w").grid(row=0, column=1, sticky="w", padx=(20, 0))
        self._lang_var = tk.StringVar()
        self.language_list = ttk.Combobox(form, textvariable=self._lang_var, state="readonly", width=22)
        self.language_list.grid(row=1, column=1, sticky="w", padx=(20, 0), pady=(0, 10))
        self.language_list.bind("<<ComboboxSelected>>", lambda e: self.on_language_change())

        tk.Label(form, text=_("Username:"), bg="#ffffff", anchor="w").grid(row=2, column=1, sticky="w", padx=(20, 0))
        username = self.info.host_username or ""
        username = re.sub(r"[^-a-z0-9_]", "", username.strip().lower())
        self._username_var = tk.StringVar(value=username)
        tk.Entry(form, textvariable=self._username_var, width=24).grid(row=3, column=1, sticky="w", padx=(20, 0), pady=(0, 10))

        tk.Label(form, text=_("Password:"), bg="#ffffff", anchor="w").grid(row=4, column=1, sticky="w", padx=(20, 0))
        self._pw1_var = tk.StringVar(value=self.info.password or "")
        self._pw2_var = tk.StringVar(value=self.info.password or "")
        tk.Entry(form, textvariable=self._pw1_var, show="*", width=24).grid(row=5, column=1, sticky="w", padx=(20, 0))
        tk.Entry(form, textvariable=self._pw2_var, show="*", width=24).grid(row=6, column=1, sticky="w", padx=(20, 0), pady=(0, 10))

        # --- Erreur + boutons ---
        self._error_var = tk.StringVar()
        tk.Label(self, textvariable=self._error_var, fg="red", bg="#ffffff").pack()

        nav = tk.Frame(self, bg="#eeeeee")
        nav.pack(side="bottom", fill="x")
        tk.Button(nav, text=_("Cancel"), command=self.on_cancel).pack(side="right", padx=8, pady=8)
        tk.Button(nav, text=_("Install"), command=self.on_install).pack(side="right", padx=4, pady=8)

        self.populate_language_list()
        self.populate_distro_list()

    # --- Populate helpers (logique identique à l'original) ---

    def populate_language_list(self):
        languages = sorted(language2lang_country.keys())
        self.language_list["values"] = languages
        language = lang_country2language.get(self.info.language) or self.info.windows_language
        if language not in languages:
            language = lang_country2language.get("en_US", "")
        self._lang_var.set(language)

    def populate_distro_list(self):
        distros = []
        for src in [self.info.cd_distro, self.info.iso_distro]:
            if src and src.name not in distros:
                distros.append(src.name)
        for d in self.info.distros:
            if d.name not in distros:
                distros.append(d.name)
        if not distros:
            messagebox.showerror(_("Error"), _("No distributions are available."))
            self.application.quit()
            return
        self.distro_list["values"] = distros
        self._distro_var.set(distros[0])
        self.on_distro_change()

    def populate_drive_list(self):
        min_mb = self.info.distro.min_disk_space_mb + self.info.distro.max_iso_size / 1024**2 + 100
        entries, self._drive_objs = [], []
        for drive in self.info.drives:
            if drive.type not in ("removable", "hd"):
                continue
            mb = int(drive.free_space_mb / 1024) * 1000
            if self.info.skip_size_check or mb > min_mb:
                label = "%s (%sGB free)" % (drive.path, mb // 1000)
                entries.append(label)
                self._drive_objs.append(drive)
        self.target_drive_list["values"] = entries
        if entries:
            self._drive_var.set(entries[0])
            self.on_drive_change()

    def populate_size_list(self):
        drive = self._get_selected_drive()
        self._sizes = []
        if drive is None:
            return
        for i in list(range(1, 33)) + [64, 128, 256, 512]:
            if self.info.skip_size_check or i * 1000 >= self.info.distro.min_disk_space_mb:
                if i * 1000 + self.info.distro.max_iso_size / 1024**2 + 100 <= drive.free_space_mb:
                    self._sizes.append(i)
        labels = [_("%sGB") % i for i in self._sizes]
        self.size_list["values"] = labels
        if labels:
            mid = labels[len(labels) // 2]
            self._size_var.set(mid)
            self.on_size_change()

    # --- Événements ---

    def _get_selected_drive(self):
        val = self._drive_var.get()
        for i, label in enumerate(self.target_drive_list["values"]):
            if label == val:
                return self._drive_objs[i] if hasattr(self, "_drive_objs") else None
        return None

    def on_distro_change(self):
        name = self._distro_var.get()
        self.info.distro = (
            self.info.distros_dict.get((name.lower(), self.info.arch))
            or self.info.distros_dict.get((name.lower(), "i386"))
        )
        if not self.info.distro:
            messagebox.showerror(_("Error"), _("Could not determine the selected distribution."))
            self.application.quit()
            return
        self.frontend.root.title(_("%s Installer") % self.info.distro.name)
        self.populate_drive_list()

    def on_language_change(self):
        language = self._lang_var.get()
        lc = language2lang_country.get(language)
        if lc:
            t = gettext.translation(self.info.application_name,
                                    localedir=self.info.translations_dir,
                                    languages=[lc], fallback=True)
            t.install(names=["ngettext"])

    def on_drive_change(self):
        self.info.target_drive = self._get_selected_drive()
        self.populate_size_list()

    def on_size_change(self):
        val = self._size_var.get()
        if val:
            self.info.installation_size_mb = int(val.rstrip("GB")) * 1000

    def on_cancel(self):
        self.frontend.cancel()

    def on_install(self):
        drive = self._get_selected_drive()
        username = self._username_var.get().strip()
        pw1 = self._pw1_var.get()
        pw2 = self._pw2_var.get()
        language = language2lang_country.get(self._lang_var.get())
        locale = lang_country2linux_locale.get(language, self.info.locale)

        error = ""
        if not drive:
            error = _("Please select a valid installation drive.")
        elif not username:
            error = _("Please enter a valid username.")
        elif username != username.lower() or " " in username:
            error = _("Please use all lower cases, no spaces in the username.")
        elif not re_username_first.match(username):
            error = _("Your username must start with a lower-case letter.")
        elif not re_username.match(username):
            error = _("Your username must contain only lower-case letters, numbers, hyphens, and underscores.")
        elif username in reserved_usernames:
            error = _("The selected username is reserved, please select a different one.")
        elif not pw1 or " " in pw1:
            error = _("Please enter a valid password (no spaces).")
        elif pw1 != pw2:
            error = _("Passwords do not match.")

        self._error_var.set(error)
        if error:
            return

        self.info.target_drive = drive
        self.info.language = language
        self.info.locale = locale
        self.info.username = username
        self.info.password = pw1
        self.frontend.stop()
