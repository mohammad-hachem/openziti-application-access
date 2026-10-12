import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from email import policy
from email.parser import BytesParser

ROOT = Path(__file__).resolve().parents[1]
FAKE = '''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps([pathlib.Path(sys.argv[0]).name] + args) + '\\n')
mode = os.environ.get('FAKE_MODE', '')
if pathlib.Path(sys.argv[0]).name == 'qrencode':
    if mode == 'qr-fail': sys.exit(1)
    pathlib.Path(args[args.index('-o')+1]).write_bytes(b'synthetic-png')
elif args[:3] == ['edge', 'list', 'identities']:
    if mode == 'lookup-fail': sys.exit(1)
    print(json.dumps({'data': [{'name':'existing'}] if mode == 'exists' else []}))
else:
    if mode == 'create-fail': sys.exit(1)
    pathlib.Path(args[args.index('--jwt-output-file')+1]).write_text('SYNTHETIC-NONCREDENTIAL')
'''


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        bindir = self.work / 'bin'
        bindir.mkdir()
        for name in ('ziti', 'qrencode'):
            path = bindir / name
            path.write_text(FAKE)
            path.chmod(0o700)
        self.env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
                        CALL_LOG=str(self.work / 'calls'))

    def run_helper(self, *args, mode=''):
        return subprocess.run([sys.executable, str(ROOT/'scripts/provision-user.py'), *args],
            cwd=self.work, env=dict(self.env, FAKE_MODE=mode), capture_output=True, text=True)

    def calls(self):
        path = self.work / 'calls'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_preview_has_no_side_effects(self):
        result = self.run_helper('alex-phone', 'portal-users')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls())
        self.assertFalse(list(self.work.glob('enrollment-bundle-*')))

    def test_invalid_input_does_not_call_controller(self):
        for args in [('bad/name', 'portal-users'), ('alex', 'all'),
                     ('alex', 'portal-users', '--sender', 'a@example.com'),
                     ('alex', 'portal-users', '--sender', 'a@example.com', '--recipient', 'a@example.com\nBcc:x@example.com')]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_helper(*args, '--apply').returncode, 0)
                self.assertFalse(self.calls())

    def test_roles_bundle_permissions_and_email(self):
        result = self.run_helper('sam-laptop', 'portal-users,reports-users,portal-users',
            '--sender', 'access@example.com', '--recipient', 'sam@example.com', '--apply')
        self.assertEqual(result.returncode, 0, result.stderr)
        creates = [c for c in self.calls() if c[1:4] == ['edge', 'create', 'identity']]
        self.assertEqual(len(creates), 1)
        self.assertIn('portal-users,reports-users', creates[0])
        bundle, = self.work.glob('enrollment-bundle-*')
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o700)
        for path in bundle.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        message = BytesParser(policy=policy.default).parsebytes((bundle/'enrollment.eml').read_bytes())
        self.assertEqual(message['To'], 'sam@example.com')
        self.assertEqual([p.get_filename() for p in message.iter_attachments()], ['identity.jwt','enrollment.png'])
        self.assertIn('Reporting portal', message.get_body().get_content())
        self.assertNotIn('SYNTHETIC-NONCREDENTIAL', result.stdout + result.stderr)

    def test_lookup_and_duplicate_stop_creation(self):
        for mode in ('exists', 'lookup-fail'):
            result = self.run_helper('alex', 'portal-users', '--apply', mode=mode)
            self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(c[1:4] == ['edge', 'list', 'identities'] for c in self.calls()))
        self.assertFalse(list(self.work.glob('enrollment-bundle-*')))

    def test_create_failure_does_not_generate_qr(self):
        result = self.run_helper('alex', 'portal-users', '--apply', mode='create-fail')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(c[0] == 'qrencode' for c in self.calls()))
        self.assertIn('may exist', result.stderr)

    def test_qr_failure_preserves_enrollment(self):
        result = self.run_helper('alex', 'portal-users', '--apply', mode='qr-fail')
        self.assertNotEqual(result.returncode, 0)
        bundle, = self.work.glob('enrollment-bundle-*')
        self.assertTrue((bundle/'identity.jwt').is_file())
        self.assertIn('do not recreate', result.stderr)


if __name__ == '__main__':
    unittest.main()
