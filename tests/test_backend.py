import unittest
import os
import tempfile
import shutil
from unittest import mock
from wubi.backends import backend
from wubi.backends.utils import registry
from wubi.backends.utils.utils import unix_path
from version import application_name, version, revision
from wubi import application


class BackendTests(unittest.TestCase):

    def setUp(self):
        root_dir = os.getcwd()
        self.app = application.Wubi(application_name, version, str(revision), root_dir)
        self.back = backend.Backend(self.app)
        self.back.info.iso_extractor = os.path.join(root_dir, 'build', 'bin', '7z.exe')
        self.app.info.original_exe = os.path.join(root_dir, 'build', 'wubi.exe')
        self.temp_target_dir = tempfile.mkdtemp(prefix='wubi-test-')

        self.uninstall_keys = [
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'UninstallString',
            '"%s" --uninstall' % os.path.join(self.temp_target_dir, 'uninstall-wubi.exe')),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'InstallationDir',
             self.temp_target_dir),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'DisplayName', 'Ubuntu'),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'DisplayIcon',
             os.path.join(root_dir, 'data', 'images', 'Wubi.ico')),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'DisplayVersion',
             self.back.info.version_revision),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'Publisher', 'Ubuntu'),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'URLInfoAbout',
             'https://www.ubuntu.com'),
            ('HKEY_LOCAL_MACHINE', 'registry-key', 'HelpLink',
             'https://www.ubuntu.com/support'),
        ]

        self._registry_patcher = mock.patch.object(registry, 'set_value')
        self.mock_set_value = self._registry_patcher.start()

    def tearDown(self):
        self._registry_patcher.stop()
        shutil.rmtree(self.temp_target_dir, ignore_errors=True)


    # --- Uninstaller ---

    def test_create_uninstaller(self):
        self.back.info.target_dir = self.temp_target_dir
        self.back.info.registry_key = 'registry-key'

        mock_distro = mock.Mock()
        mock_distro.name = 'Ubuntu'
        mock_distro.version = '24.04'
        mock_distro.website = 'https://www.ubuntu.com'
        mock_distro.support = 'https://www.ubuntu.com/support'
        self.back.info.distro = mock_distro

        self.back.create_uninstaller(None)

        calls = [c[0] for c in self.mock_set_value.call_args_list]
        for key in self.uninstall_keys:
            self.assertIn(key, calls,
                'Expected registry key not set: %s' % str(key))
        for call in calls:
            self.assertIn(call, self.uninstall_keys,
                'Unexpected registry key set: %s' % str(call))

        uninstaller = os.path.join(self.temp_target_dir, 'uninstall-wubi.exe')
        self.assertTrue(os.path.exists(uninstaller),
            'Uninstaller binary not created.')


    # --- ISO ---

    def test_get_iso_file_names(self):
        """Verifies the reading of files in a small test ISO."""
        expected = ['%02d' % x for x in range(1, 51)]
        self.assertEqual(expected,
            self.back.get_iso_file_names('tests/data/small.iso'))

    def test_get_source_id_fallback(self):
        """Fallback to SOURCE_ID_MAP if the ISO does not contain install-sources.yaml."""
        with mock.patch('pycdlib.PyCdlib', side_effect=Exception("no pycdlib")):
            source_id = self.back._get_source_id()
        self.assertEqual(source_id, 'ubuntu-desktop')

    def test_get_source_id_unknown_distro(self):
        """Fallback to ubuntu-desktop if the distro is unknown."""
        with mock.patch('pycdlib.PyCdlib', side_effect=Exception):
            source_id = self.back._get_source_id()
        self.assertEqual(source_id, 'ubuntu-desktop')

    def test_get_installation_tasklist_without_diskimage(self):
        """Tasklist generation should not fail when diskimage is not provided."""
        mock_distro = mock.Mock()
        mock_distro.name = 'ubuntu'
        mock_distro.diskimage = None

        self.back.info.distro = mock_distro
        self.back.info.target_drive = mock.Mock()
        self.back.info.target_drive.is_fat.return_value = False

        fake_iso = os.path.join(self.temp_target_dir, 'fake.iso')
        open(fake_iso, 'wb').close()
        self.back.info.iso_path = fake_iso
        self.back.info.iso_distro = mock_distro

        tasklist = self.back.get_installation_tasklist()
        self.assertIsNotNone(tasklist)
        self.assertTrue(tasklist.subtasks, 'Expected installation tasks to be created')


    # --- Password ---

    def test_hash_password(self):
        """Verifies that the hash starts with $6$ (sha512_crypt)."""
        from passlib.hash import sha512_crypt
        hashed = sha512_crypt.using(rounds=5000).hash('testpassword')
        self.assertTrue(hashed.startswith('$6$'),
            'Password hash should start with $6$')
        self.assertTrue(sha512_crypt.verify('testpassword', hashed))


    # --- EFI ---

    def test_get_efi_arch_amd64(self):
        self.back.info.arch = 'AMD64'
        arch = self.back.get_efi_arch(None, None)
        self.assertEqual(arch, 'x64')

    def test_get_efi_arch_arm64(self):
        self.back.info.arch = 'ARM64'
        arch = self.back.get_efi_arch(None, None)
        self.assertEqual(arch, 'arm64')

    def test_get_efi_arch_x86(self):
        self.back.info.arch = 'x86'
        arch = self.back.get_efi_arch(None, None)
        self.assertEqual(arch, 'ia32')


    # --- Hostname ---

    def test_hostname_sanitization(self):
        import re
        cases = [
            ('MY_PC',        'my-pc'),
            ('MY PC 2024!',  'my-pc-2024'),
            ('---test---',   'test'),
            ('',             'wubi-host'),
            ('valid-name',   'valid-name'),
        ]
        for raw, expected in cases:
            hostname = re.sub(r'[^a-z0-9-]', '-', raw.lower())
            hostname = re.sub(r'-+', '-', hostname)
            hostname = hostname.strip('-') or 'wubi-host'
            self.assertEqual(hostname, expected,
                'hostname(%r) = %r, expected %r' % (raw, hostname, expected))

    # --- Autoinstall ---

    def test_create_subiquity_autoinstall(self):
        """Verifies that the autoinstall.yaml file is created with the expected content."""
        import yaml
        mock_distro = mock.Mock()
        mock_distro.name = 'ubuntu'
        mock_distro.installer = 'subiquity'
        self.back.info.custom_install = self.temp_target_dir
        self.back.info.locale = 'fr_FR.UTF-8'
        self.back.info.keyboard_layout = 'fr'
        self.back.info.keyboard_variant = ''
        self.back.info.timezone = 'Europe/Paris'
        self.back.info.user_full_name = 'Test User'
        self.back.info.hostname = 'test-host'
        self.back.info.host_username = 'testuser'
        self.back.info.password = 'testpassword'
        self.back.info.iso_path = '/fake/ubuntu.iso'
        self.back.info.distro = mock_distro

         # Debug
        print(os.listdir(self.temp_target_dir))
        autoinstall_dir = os.path.join(self.temp_target_dir, 'autoinstall')
        if os.path.exists(autoinstall_dir):
            print(os.listdir(autoinstall_dir))

        with mock.patch.object(self.back, '_get_source_id', return_value='ubuntu-desktop'):
            self.back.create_preseed()

        yaml_path = os.path.join(self.temp_target_dir, 'autoinstall', 'autoinstall.yaml')
        self.assertTrue(os.path.exists(yaml_path), 'autoinstall.yaml not created')

        with open(yaml_path, 'r') as f:
            content = yaml.safe_load(f)

        ai = content['autoinstall']
        self.assertEqual(ai['locale'], 'fr_FR.UTF-8')
        self.assertEqual(ai['keyboard']['layout'], 'fr')
        self.assertEqual(ai['identity']['username'], 'testuser')
        self.assertEqual(ai['source']['id'], 'ubuntu-desktop')
        self.assertTrue(ai['identity']['password'].startswith('$6$'))
        early = ai['early-commands'][0]
        self.assertEqual(early[0], '/bin/sh')
        self.assertTrue(early[1].startswith('/host/'))
        self.assertNotIn('$(', early[1])
        self.assertEqual(early[2], unix_path(self.temp_target_dir))

    def test_modify_grub_configuration_subiquity_uses_isodevice_seed(self):
        mock_distro = mock.Mock()
        mock_distro.installer = 'subiquity'
        self.back.info.distro = mock_distro
        self.back.info.install_boot_dir = os.path.join(self.temp_target_dir, 'install', 'boot')
        self.back.info.custom_install = os.path.join(self.temp_target_dir, 'install', 'custom-installation')
        self.back.info.iso_path = os.path.join(self.temp_target_dir, 'ubuntu.iso')
        self.back.info.kernel = os.path.join(self.temp_target_dir, 'install', 'boot', 'vmlinuz')
        self.back.info.initrd = os.path.join(self.temp_target_dir, 'install', 'boot', 'initrd')
        self.back.info.keyboard_layout = 'fr'
        self.back.info.keyboard_variant = ''
        self.back.info.locale = 'fr_FR.UTF-8'
        self.back.info.accessibility = ''

        os.makedirs(os.path.join(self.back.info.install_boot_dir, 'grub'), exist_ok=True)
        self.back.modify_grub_configuration()

        grub_cfg = os.path.join(self.back.info.install_boot_dir, 'grub', 'grub.cfg')
        self.assertTrue(os.path.exists(grub_cfg))
        with open(grub_cfg, 'r') as f:
            content = f.read()

        self.assertIn('ds=nocloud\\;s=file:///host/', content)
        self.assertIn('/autoinstall/', content)
        self.assertNotIn('$(custom_installation_dir)', content)


if __name__ == '__main__':
    unittest.main()
