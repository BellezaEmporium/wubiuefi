import os
import sys
import tempfile
import logging
from optparse import OptionParser
from gettext import gettext as _

from wubi import errors
from version import application_name, version, revision

log = logging.getLogger("application")


class Info(object):
    _ALIASES = {
        "root_dir": "rootdir",
        "force_exit": "forceexit",
        "application_name": "applicationname",
        "version_revision": "versionrevision",
        "full_application_name": "fullapplicationname",
        "full_version": "fullversion",
        "log_file": "logfile",
        "original_exe": "originalexe",
        "use_frontend": "usefrontend",
        "run_task": "runtask",
        "cd_path": "cdpath",
        "previous_target_dir": "previoustargetdir",
        "uninstall_before_install": "uninstallbeforeinstall",
        "cd_distro": "cddistro",
        "iso_distro": "isodistro",
        "target_drive": "targetdrive",
        "installation_size_mb": "installationsizemb",
        "skip_md5_check": "skipmd5check",
        "skip_size_check": "skipsizecheck",
        "skip_memory_check": "skipmemorycheck",
        "force_i386": "forcei386",
        "force_wubi": "forcewubi",
        "image_dir": "imagedir",
        "translations_dir": "translationsdir",
        "application_icon": "applicationicon",
        "iso_md5_hashes": "isomd5hashes",
        "distros_dict": "distrosdict",
        "drives_dict": "drivesdict",
        "previous_uninstaller_path": "previousuninstallerpath",
        "previous_distro_name": "previousdistroname",
        "windows_language": "windowslanguage",
        "host_username": "hostusername",
        "user_full_name": "userfullname",
        "user_directory": "userdirectory",
        "keyboard_layout": "keyboardlayout",
        "keyboard_variant": "keyboardvariant",
        "total_memory_mb": "totalmemorymb",
        "environment_variables": "environmentvariables",
        "os_name": "osname",
        "check_arch": "checkarch",
        "web_proxy": "webproxy",
        "iso_path": "isopath",
        "disk_image_path": "dimagepath",
        "install_dir": "installdir",
        "install_boot_dir": "installbootdir",
        "disks_dir": "disksdir",
        "disks_boot_dir": "disksbootdir",
        "custom_install": "custominstall",
        "no_bittorrent": "nobittorrent",
    }
    _alias_reverse = {}

    def __init__(self):
        object.__setattr__(self, "_alias_reverse", dict((v, k) for k, v in self._ALIASES.items()))

        self.root_dir = None
        self.temp_dir = None
        self.data_dir = None
        self.bin_dir = None
        self.image_dir = None
        self.translations_dir = None
        self.trusted_keys = None
        self.application_icon = None
        self.icon = None

        self.force_exit = False
        self.quitting = False

        self.version = None
        self.revision = None
        self.application_name = None
        self.version_revision: str | None = None
        self.full_application_name: str | None = None
        self.full_version: str | None = None

        self.log_file: str | None = None
        self.original_exe = None
        self.use_frontend = None
        self.verbosity: str | None = None

        self.run_task: str | None = None
        self.cd_path = None
        self.iso_path = None
        self.disk_image_path = None

        self.previous_target_dir = None
        self.previous_uninstaller_path = None
        self.previous_distro_name = None
        self.uninstall_before_install = False

        self.non_interactive = False
        self.cd_distro = None
        self.iso_distro = None
        self.distro = None
        self.distro_name = None
        self.distros = []
        self.distros_dict = {}

        self.platform = None
        self.os_name = None
        self.arch = None
        self.check_arch = False
        self.encoding = None
        self.environment_variables = {}
        self.iso_md5_hashes = {}

        self.drives = []
        self.drives_dict = {}
        self.system_drive = None
        self.target_drive = None
        self.installation_size_mb = None

        self.language = None
        self.windows_language = None
        self.locale = None
        self.country = None
        self.timezone = None

        self.username = None
        self.password = None
        self.host_username = None
        self.user_full_name = None
        self.user_directory = None

        self.keyboard_layout = None
        self.keyboard_variant = None
        self.accessibility = ""

        self.total_memory_mb = 0

        self.skip_md5_check = False
        self.skip_size_check = False
        self.skip_memory_check = False
        self.no_bittorrent = False
        self.force_i386 = False
        self.force_wubi = False
        self.test = False
        self.debug = False

        self.web_proxy = None

        self.target_dir = None
        self.install_dir = None
        self.install_boot_dir = None
        self.disks_dir = None
        self.disks_boot_dir = None
        self.custom_install = None

        self.root_size_mb = None
        self.swap_size_mb = None
        self.home_size_mb = None
        self.usr_size_mb = None

        self.kernel = None
        self.initrd = None

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)

        alias = self._ALIASES.get(name)
        if alias and getattr(self, alias, None) != value:
            object.__setattr__(self, alias, value)

        alias_reverse = getattr(self, "_alias_reverse", {})
        canonical = alias_reverse.get(name)
        if canonical and getattr(self, canonical, None) != value:
            object.__setattr__(self, canonical, value)

    def update(self, mapping):
        for key, value in mapping.items():
            setattr(self, key, value)

    def __str__(self):
        return "Info(%s)" % self.__dict__


class Wubi(object):
    def __init__(self, application_name, version, revision, root_dir):
        self.frontend = None
        self.backend = None
        self.info = Info()

        self.info.root_dir = root_dir
        self.info.force_exit = False
        self.info.version = version
        self.info.revision = revision
        self.info.application_name = application_name
        self.info.version_revision = "%s-rev%s" % (self.info.version, self.info.revision)
        self.info.full_application_name = "%s-%s-rev%s" % (
            self.info.application_name,
            self.info.version,
            self.info.revision,
        )
        self.info.full_version = "%s %s rev%s" % (
            self.info.application_name,
            self.info.version,
            self.info.revision,
        )

    def run(self):
        self.info.quitting = False
        try:
            self.parse_commandline_arguments()
            self.set_logger()
            log.info(self.info.full_version)
            log.debug("Logfile is %s", self.info.log_file)
            log.debug("sys.argv=%s", sys.argv)

            self.backend = self.get_backend()
            self._backend_call(("remove_existing_binary", "removeexistingbinary"))
            self._backend_call(("fetch_basic_info", "fetchbasicinfo"))
            self.select_task()

        except Exception as err:
            if self.info.quitting:
                log.info("Quitting application")
                return

            log.exception(err)

            if self.frontend:
                error_messages = " ".join(str(e) for e in err.args if e is not None).strip()
                if not error_messages:
                    error_messages = str(err)

                message = _(
                    "An error occurred:\n\n%(error)s\n\nFor more information, please see the log file:\n%(log)s"
                ) % {
                    "error": error_messages,
                    "log": self.info.log_file,
                }
                self._frontend_call(("show_error_message", "showerrormessage"), message)
            return

    def quit(self):
        log.debug("application.quit")
        if self.frontend and callable(getattr(self.frontend, "quit", None)):
            self.frontend.quit()
        else:
            self.on_quit()

    def on_quit(self):
        log.debug("application.on_quit")
        self.info.quitting = True
        if self.info.force_exit:
            log.debug("Forceful exit")
            log.info("sys.exit")
            sys.exit(0)

    def get_backend(self):
        from wubi.backends.win32 import WindowsBackend
        return WindowsBackend(self)

    def get_frontend(self):
        if self.frontend:
            return self.frontend

        if self.info.use_frontend and self.info.use_frontend != "win32":
            raise NotImplementedError()

        from wubi.frontends.win32 import WindowsFrontend
        self.frontend = WindowsFrontend(self)
        return self.frontend

    def _frontend_call(self, method_names, *args):
        for name in method_names:
            func = getattr(self.frontend, name, None)
            if callable(func):
                return func(*args)
        raise AttributeError("Frontend method not found: %s" % ", ".join(method_names))

    def _backend_call(self, method_names, *args):
        for name in method_names:
            func = getattr(self.backend, name, None)
            if callable(func):
                return func(*args)
        raise AttributeError("Backend method not found: %s" % ", ".join(method_names))

    def select_task(self):
        run_task = self.info.run_task

        if run_task == "install":
            self.run_installer()
        elif run_task in ("cd_boot", "cdboot"):
            self.run_cdboot()
        elif run_task == "uninstall":
            self.run_uninstaller()
        elif run_task in ("show_info", "showinfo"):
            self.show_info()
        elif run_task == "reboot":
            self.reboot()
        elif self.info.cd_path or run_task in ("cd_menu", "cdmenu"):
            self.run_cd_menu()
        else:
            self.run_installer()

        self.quit()

    def run_installer(self):
        previous_target_dir = self.info.previous_target_dir
        if previous_target_dir and os.path.isdir(previous_target_dir):
            log.info("Already installed, running the uninstaller...")
            self.info.uninstall_before_install = True
            self.run_uninstaller()
            self._backend_call(("fetch_basic_info", "fetchbasicinfo"))

            previous_target_dir = self.info.previous_target_dir
            if previous_target_dir and os.path.isdir(previous_target_dir):
                message = _(
                    "A previous installation was detected in %s. Uninstall that before continuing."
                ) % previous_target_dir
                log.error(message)
                self.get_frontend()
                self._frontend_call(("show_error_message", "showerrormessage"), message)
                self.quit()
                return

        log.info("Running the installer...")
        self.frontend = self.get_frontend()
        self._frontend_call(("show_installation_settings", "showinstallationsettings"))
        log.info("Received settings")
        self._frontend_call(
            ("run_tasks", "runtasks"),
            self._backend_call(("get_installation_tasklist", "getinstallationtasklist")),
        )
        log.info("Almost finished installing")

        if not self.info.non_interactive:
            self._frontend_call(("show_installation_finish_page", "showinstallationfinishpage"))

        log.info("Finished installation")
        if self.info.run_task == "reboot":
            self.reboot()

    def run_uninstaller(self):
        log.info("Running the uninstaller...")

        previous_target_dir = self.info.previous_target_dir
        if not previous_target_dir or not os.path.isdir(previous_target_dir):
            log.error("No previous target dir found, exiting")
            return

        if self._backend_call(("run_previous_uninstaller", "runpreviousuninstaller")):
            return

        self.frontend = self.get_frontend()
        self._frontend_call(("show_uninstallation_settings", "showuninstallationsettings"))
        log.info("Received settings")

        try:
            self._frontend_call(
                ("run_tasks", "runtasks"),
                self._backend_call(("get_uninstallation_tasklist", "getuninstallationtasklist")),
            )
        except errors.WubiCorruptionError:
            err = _(
                "Files on your computer are corrupted. A disk check has been scheduled and will be performed at the next boot. Please reboot your computer now."
            )
            self._frontend_call(("show_error_message", "showerrormessage"), err)
            self.quit()
            return

        log.info("Almost finished uninstalling")
        if not self.info.uninstall_before_install and not self.info.non_interactive:
            self._frontend_call(("show_uninstallation_finish_page", "showuninstallationfinishpage"))
        log.info("Finished uninstallation")

    def run_cd_menu(self):
        log.info("Running the CD menu...")
        self.frontend = self.get_frontend()

        if not self.info.cd_distro:
            self._frontend_call(
                ("show_error_message", "showerrormessage"),
                _("No CD detected, cannot run CD menu"),
            )
            self.quit()
            return

        self._frontend_call(("show_cd_menu_page", "showcdmenupage"))
        log.info("CD menu finished")
        self.select_task()

    def run_cdboot(self):
        if not self.info.cd_distro:
            message = _(
                "Could not find any valid CD. CD boot helper can only be used with a Live CD."
            )
            log.error(message)
            self.get_frontend()
            self._frontend_call(("show_error_message", "showerrormessage"), message)
            self.quit()
            return

        if self.info.previous_target_dir:
            log.info("Already installed, running the uninstaller...")
            self.info.uninstall_before_install = True
            self.run_uninstaller()
            self._backend_call(("fetch_basic_info", "fetchbasicinfo"))

            if self.info.previous_target_dir:
                message = _(
                    "A previous installation was detected in %s. Uninstall that before continuing."
                ) % self.info.previous_target_dir
                log.error(message)
                self.get_frontend()
                self._frontend_call(("show_error_message", "showerrormessage"), message)
                self.quit()
                return

        log.info("Running the CD boot helper...")
        self.frontend = self.get_frontend()
        self._frontend_call(("show_cdboot_page", "showcdbootpage"))
        log.info("CD boot helper confirmed")
        self._frontend_call(
            ("run_tasks", "runtasks"),
            self._backend_call(("get_cdboot_tasklist", "getcdboottasklist")),
        )
        log.info("Almost finished installing")
        self._frontend_call(("show_installation_finish_page", "showinstallationfinishpage"))
        log.info("Finished installation")

        if self.info.run_task == "reboot":
            self.reboot()

    def reboot(self):
        log.info("Rebooting")
        tasklist = self._backend_call(("get_reboot_tasklist", "getreboottasklist"))
        run_tasklist = getattr(tasklist, "run", None)
        if not callable(run_tasklist):
            raise AttributeError("Tasklist object has no callable 'run' method")
        run_tasklist()

    def show_info(self):
        self._backend_call(("show_info", "showinfo"))

    def parse_commandline_arguments(self):
        usage = "%s [options]" % self.info.application_name
        parser = OptionParser(usage=usage, version=self.info.full_version)

        parser.add_option("--quiet", action="store_const", const="quiet", dest="verbosity")
        parser.add_option("--verbose", action="store_const", const="verbose", dest="verbosity")
        parser.add_option("--install", action="store_const", const="install", dest="run_task")
        parser.add_option("--uninstall", action="store_const", const="uninstall", dest="run_task")
        parser.add_option("--cdmenu", action="store_const", const="cd_menu", dest="run_task")
        parser.add_option("--cdboot", action="store_const", const="cd_boot", dest="run_task")
        parser.add_option("--showinfo", action="store_const", const="show_info", dest="run_task")
        parser.add_option("--nobittorrent", action="store_true", dest="no_bittorrent")
        parser.add_option("--32bit", action="store_true", dest="force_i386")
        parser.add_option("--skipmd5check", action="store_true", dest="skip_md5_check")
        parser.add_option("--skipsizecheck", action="store_true", dest="skip_size_check")
        parser.add_option("--skipmemorycheck", action="store_true", dest="skip_memory_check")
        parser.add_option("--noninteractive", action="store_true", dest="non_interactive")
        parser.add_option("--test", action="store_true", dest="test")
        parser.add_option("--debug", action="store_true", dest="debug")
        parser.add_option("--drive", dest="target_drive")
        parser.add_option("--size", type="int", dest="installation_size_mb")
        parser.add_option("--locale", dest="locale")
        parser.add_option("--force-wubi", action="store_true", dest="force_wubi")
        parser.add_option("--language", dest="language")
        parser.add_option("--username", dest="username")
        parser.add_option("--password", dest="password")
        parser.add_option("--distro", dest="distro_name")
        parser.add_option("--accessibility", dest="accessibility")
        parser.add_option("--webproxy", dest="web_proxy")
        parser.add_option("--isopath", dest="iso_path")
        parser.add_option("--dimagepath", dest="disk_image_path")
        parser.add_option("--exefile", dest="original_exe", default=None)
        parser.add_option("--log-file", dest="log_file", default=None)
        parser.add_option("--interface", dest="use_frontend", default=None)

        options, self.args = parser.parse_args()
        self.info.update(vars(options))

        if self.info.test:
            self.info.debug = True
        if self.info.debug:
            self.info.verbosity = "verbose"

        if self.info.original_exe:
            original_exe = self.info.original_exe.strip()
            if original_exe[:1] in ("'", '"') and original_exe[-1:] in ("'", '"'):
                original_exe = original_exe[1:-1].strip()
            self.info.original_exe = original_exe

            if os.path.basename(self.info.original_exe).lower().startswith("uninstall-"):
                self.info.run_task = "uninstall"

    def set_logger(self, log_to_console=True):
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        if not self.info.log_file or self.info.log_file.lower() != "none":
            if not self.info.log_file:
                filename = (self.info.full_application_name or "wubi") + ".log"
                directory = tempfile.gettempdir()
                self.info.log_file = os.path.join(directory, filename)

            if not self.info.log_file:
                return
            file_handler = logging.FileHandler(self.info.log_file)
            file_formatter = logging.Formatter(
                "%(asctime)s %(levelname)-6s %(name)s: %(message)s",
                datefmt="%m-%d %H:%M",
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)
            root_logger.addHandler(file_handler)

        if log_to_console and not bool(self.info.original_exe):
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter("%(message)s", datefmt="%m-%d %H:%M")
            console_handler.setFormatter(console_formatter)

            if self.info.verbosity == "verbose":
                console_handler.setLevel(logging.DEBUG)
            elif self.info.verbosity == "quiet":
                console_handler.setLevel(logging.ERROR)
            else:
                console_handler.setLevel(logging.INFO)

            root_logger.addHandler(console_handler)


if __name__ == "__main__":
    app = Wubi(application_name, version, revision, os.path.abspath(os.path.dirname(__file__)))
    app.run()
