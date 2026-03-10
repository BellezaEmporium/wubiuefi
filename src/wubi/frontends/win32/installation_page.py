# Copyright (c) 2008 Agostino Russo
#
# Written by Agostino Russo
#
# This file is part of Wubi the Win32 Ubuntu Installer.
#
# Wubi is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of
# the License, or (at your option) any later version.
#
# Wubi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see .

from winui import ui
from .page import Page
from wubi.backends.common.mappings import (
    reserved_usernames,
    lang_country2linux_locale,
    language2lang_country,
    lang_country2language,
)
import os
import logging
import re
import gettext
from gettext import gettext as _

log = logging.getLogger("WinuiInstallationPage")

reserved_usernames = [str(n) for n in reserved_usernames]
re_username_first = re.compile(r"^[a-z]")
re_username = re.compile(r"[a-z][-a-z0-9_]*$")


class InstallationPage(Page):

    def _image_path(self, *parts):
        return os.path.join(str(self.info.image_dir), "mbcs", *(str(part) for part in parts))

    def add_controls_block(self, parent, left, top, bmp, label, is_listbox):
        picture = ui.Bitmap(parent, left, top + 6, 32, 32)
        picture.set_image(self._image_path(bmp))

        label_widget = ui.Label(
            parent,
            left + 32 + 10,
            top,
            150,
            12,
            label,
        )

        if is_listbox:
            combo = ui.ComboBox(
                parent,
                left + 32 + 10,
                top + 20,
                150,
                200,
                "",
            )
        else:
            combo = None

        return picture, label_widget, combo

    def check_disk_free_space(self):
        if self.info.skip_size_check:
            return

        min_space_mb = (
            self.info.distro.min_disk_space_mb
            + self.info.distro.max_iso_size / (1024 ** 2)
            + 100
        )
        max_space_mb = 0
        max_space_mb2 = 0

        for drive in self.info.drives:
            if drive.type not in ["removable", "hd"]:
                continue
            max_space_mb = max(max_space_mb, drive.free_space_mb)
            if int(drive.free_space_mb / 1024) * 1000 > min_space_mb:
                max_space_mb2 = max(max_space_mb2, drive.free_space_mb)

        if max_space_mb < 1024:
            message = _(
                "Only %sMB of disk space are available.\n"
                "At least 1024MB are required as a bare minimum. Quitting"
            )
            self.frontend.show_error_message(message % int(max_space_mb))
            self.application.quit()
            return

        if max_space_mb2 < min_space_mb:
            message = _(
                "%(min_space)sMB of disk size are required for installation.\n"
                "Only %(max_space)sMB are available.\n"
                "The installation may fail in such circumstances.\n"
                "Do you wish to continue anyway?"
            )
            min_space_mb = round(min_space_mb / 1000 + 0.5) * 1024
            message = message % dict(
                min_space=int(min_space_mb),
                max_space=int(max_space_mb),
            )
            if not self.frontend.ask_confirmation(message):
                self.application.quit()
            else:
                self.info.skip_size_check = True

    def populate_drive_list(self):
        self.check_disk_free_space()

        min_space_mb = (
            self.info.distro.min_disk_space_mb
            + self.info.distro.max_iso_size / (1024 ** 2)
            + 100
        )

        self.drives_gb = []
        self.target_drive_list.clear()

        for drive in self.info.drives:
            if drive.type not in ["removable", "hd"]:
                continue

            drive_space_mb = int(drive.free_space_mb / 1024) * 1000
            if self.info.skip_size_check or drive_space_mb > min_space_mb:
                text = drive.path + " "
                text += _("(%sGB free)") % (drive_space_mb / 1000)
                self.drives_gb.append(text)
                self.target_drive_list.add_item(text)

        if self.drives_gb:
            self.select_default_drive()

    def select_default_drive(self):
        if not self.drives_gb:
            return

        drive = self.info.target_drive
        drive_text = self.drives_gb[0]

        if drive and self.info.drives:
            Drive = self.info.drives[0].__class__
            if not isinstance(drive, Drive):
                drive = self.info.drives_dict.get(str(drive)[:2].lower())

            if drive:
                for d in self.drives_gb:
                    if d.startswith(drive.path):
                        drive_text = d
                        break

        self.target_drive_list.set_value(drive_text)
        self.on_drive_change()

    def populate_size_list(self):
        target_drive = self.get_drive()
        self.size_list_gb = []
        self.size_list.clear()

        if target_drive is None:
            return

        i_size_list = list(range(1, 33)) + [64, 128, 256, 512]
        if self.info.installation_size_mb:
            i = int(self.info.installation_size_mb / 1000)
            if i not in i_size_list:
                i_size_list.append(i)
        i_size_list.sort()

        for i in i_size_list:
            if self.info.skip_size_check or i * 1000 >= self.info.distro.min_disk_space_mb:
                if i * 1000 + self.info.distro.max_iso_size / 1024 ** 2 + 100 <= target_drive.free_space_mb:
                    self.size_list_gb.append(i)
                    self.size_list.add_item(_("%sGB") % i)

        if self.size_list_gb:
            self.select_default_size()

    def select_default_size(self):
        if not self.size_list_gb:
            return

        if self.info.installation_size_mb:
            installation_size_gb = int(self.info.installation_size_mb / 1000)
            for i in self.size_list_gb:
                if i >= installation_size_gb:
                    self.size_list.set_value(_("%sGB") % i)
                    return

        i = int(len(self.size_list_gb) / 2)
        installation_size_gb = self.size_list_gb[i]
        self.size_list.set_value(_("%sGB") % installation_size_gb)
        self.on_size_change()

    def populate_distro_list(self):
        if self.info.cd_distro:
            distros = [self.info.cd_distro.name]
        elif self.info.iso_distro:
            distros = [self.info.iso_distro.name]
        else:
            distros = []

        for distro in self.info.distros:
            if distro.name not in distros:
                distros.append(distro.name)

        if not distros:
            self.frontend.show_error_message(_("No distributions are available."))
            self.application.quit()
            return

        for distro in distros:
            self.distro_list.add_item(distro)

        self.distro_list.set_value(distros[0])
        self.on_distro_change()

    def populate_language_list(self):
        languages = list(language2lang_country.keys())
        languages.sort()

        for language in languages:
            self.language_list.add_item(language)

        language = lang_country2language.get(self.info.language, None)
        if not language and self.info.windows_language in list(language2lang_country.keys()):
            language = self.info.windows_language
        if not language:
            language = lang_country2language.get("en_US")

        if language:
            self.language_list.set_value(language)

    def on_init(self):
        Page.on_init(self)

        self.insert_header(
            _("Installing"),
            _("Please select username and password for the new account"),
            "header.bmp",
        )

        self.insert_navigation(_("Accessibility"), _("Install"), _("Cancel"), default=2)
        self.navigation.button3.on_click = self.on_cancel
        self.navigation.button2.on_click = self.on_install
        self.navigation.button1.on_click = self.on_accessibility

        self.insert_main()
        h = 24
        w = 150

        picture, label, self.target_drive_list = self.add_controls_block(
            self.main, h, h,
            "install.bmp", _("Installation drive:"), True
        )
        self.target_drive_list.on_change = self.on_drive_change

        picture, label, self.size_list = self.add_controls_block(
            self.main, h, h * 4,
            "disksize.bmp", _("Installation size:"), True
        )
        self.size_list.on_change = self.on_size_change

        picture, label, self.distro_list = self.add_controls_block(
            self.main, h, h * 7,
            "desktop.bmp", _("Desktop environment:"), True
        )
        self.distro_list.on_change = self.on_distro_change

        picture, label, self.language_list = self.add_controls_block(
            self.main, h * 4 + w, h,
            "language.bmp", _("Language:"), True
        )
        self.populate_language_list()
        self.language_list.on_change = self.on_language_change

        if self.info.username:
            username = self.info.username
        else:
            username = self.info.host_username or ""
        username = re.sub(r"[^-a-z0-9_]", "", username.strip().lower())

        picture, label, combo = self.add_controls_block(
            self.main, h * 4 + w, h * 4,
            "user.bmp", _("Username:"), None
        )
        self.username = ui.Edit(
            self.main,
            h * 4 + w + 42, h * 4 + 20, 150, 20,
            username, False
        )

        picture, label, combo = self.add_controls_block(
            self.main, h * 4 + w, h * 7,
            "lock.bmp", _("Password:"), None
        )
        label.move(h * 4 + w + 42, h * 7 - 24)

        password = ""
        if self.info.password:
            password = self.info.password
        elif self.info.test:
            password = "test"

        self.password1 = ui.PasswordEdit(
            self.main,
            h * 4 + w + 42, h * 7 - 4, 150, 20,
            password, False
        )
        self.password2 = ui.PasswordEdit(
            self.main,
            h * 4 + w + 42, h * 7 + 20, 150, 20,
            password, False
        )

        self.error_label = ui.Label(
            self.main,
            40, self.main.height - 20, self.main.width - 80, 12,
            ""
        )
        self.error_label.set_text_color(255, 0, 0)

        self.populate_distro_list()

        if self.info.non_interactive:
            self.on_install()

    def get_drive(self):
        target_text = self.target_drive_list.get_text()
        if not target_text:
            return None
        target_drive = target_text[:2].lower()
        return self.info.drives_dict.get(target_drive)

    def get_installation_size_mb(self):
        installation_size = self.size_list.get_text()
        if not installation_size:
            return 0
        return int(installation_size[:-2]) * 1000

    def on_distro_change(self):
        distro_name = str(self.distro_list.get_text())
        self.info.distro = self.info.distros_dict.get((distro_name.lower(), self.info.arch))
        if not self.info.distro and self.info.arch == "amd64":
            self.info.distro = self.info.distros_dict.get((distro_name.lower(), "i386"))

        if not self.info.distro:
            self.frontend.show_error_message(_("Could not determine the selected distribution."))
            self.application.quit()
            return

        self.frontend.set_title(_("%s Installer") % self.info.distro.name)

        bmp_file = "%s-header.bmp" % self.info.distro.name
        self.header.image.set_image(self._image_path(bmp_file))

        title_text = _("You are about to install %(distro)s-%(version)s") % {
            "distro": self.info.distro.name,
            "version": self.info.version,
        }
        title_widget = getattr(self.header, "title", None)
        if title_widget is not None and hasattr(title_widget, "set_text"):
            title_widget.set_text(title_text)

        icon_file = "%s.ico" % self.info.distro.name
        self.frontend.set_icon(self._image_path(icon_file))

        if not self.info.skip_memory_check:
            if self.info.total_memory_mb < self.info.distro.min_memory_mb:
                message = _(
                    "%(min_memory)sMB of memory are required for installation.\n"
                    "Only %(total_memory)sMB are available.\n"
                    "The installation may fail in such circumstances.\n"
                    "Do you wish to continue anyway?"
                )
                message = message % dict(
                    min_memory=int(self.info.distro.min_memory_mb),
                    total_memory=int(self.info.total_memory_mb),
                )
                if not self.frontend.ask_confirmation(message):
                    self.application.quit()
                    return
                self.info.skip_memory_check = True

        self.populate_drive_list()

    def on_language_change(self):
        language = self.language_list.get_text()
        language1 = language2lang_country.get(language, None)
        language2 = language1 and language1.split("_")[0]
        language3 = lang_country2linux_locale.get(self.info.language, None)
        language4 = language3 and language3.split(".")[0]
        language5 = language4 and language4.split("_")[0]
        languages = [lang for lang in [language1, language2, language3, language4, language5] if lang]

        translation = gettext.translation(
            self.info.application_name,
            localedir=self.info.translations_dir,
            languages=languages,
            fallback=True,
        )
        translation.install(names=["ngettext"])

    def on_drive_change(self):
        self.info.target_drive = self.get_drive()
        self.populate_size_list()

    def on_size_change(self):
        self.info.installation_size_mb = self.get_installation_size_mb()

    def on_cancel(self):
        self.frontend.cancel()

    def on_accessibility(self):
        self.frontend.show_page(self.frontend.accessibility_page)

    def on_install(self):
        drive = self.get_drive()
        if drive is None:
            self.error_label.set_text(_("Please select a valid installation drive."))
            return

        installation_size_mb = self.get_installation_size_mb()
        language = self.language_list.get_text()
        language = language2lang_country.get(language, None)
        locale = lang_country2linux_locale.get(language, self.info.locale)
        username = self.username.get_text()
        password1 = self.password1.get_text()
        password2 = self.password2.get_text()

        error_message = ""
        if not username:
            error_message = _("Please enter a valid username.")
        elif username != username.lower():
            error_message = _("Please use all lower cases in the username.")
        elif " " in username:
            error_message = _("Please do not use spaces in the username.")
        elif not re_username_first.match(username):
            error_message = _("Your username must start with a lower-case letter.")
        elif not re_username.match(username):
            error_message = _("Your username must contain only lower-case letters, numbers, hyphens, and underscores.")
        elif username in reserved_usernames:
            error_message = _("The selected username is reserved, please select a different one.")
        elif not password1:
            error_message = _("Please enter a valid password.")
        elif " " in password1:
            error_message = _("Please do not use spaces in the password.")
        elif password1 != password2:
            error_message = _("Passwords do not match.")

        self.error_label.set_text(error_message)
        if error_message:
            if self.info.non_interactive:
                log.error("ERROR: %s Exiting." % error_message)
                self.frontend.quit()
            return

        log.debug(
            "target_drive=%s, installation_size=%sMB, distro_name=%s, language=%s, locale=%s, username=%s"
            % (drive.path, installation_size_mb, self.info.distro.name, language, locale, username)
        )

        self.info.target_drive = drive
        self.info.installation_size_mb = installation_size_mb
        self.info.language = language
        self.info.locale = locale
        self.info.username = username
        self.info.password = password1
        self.frontend.stop()
