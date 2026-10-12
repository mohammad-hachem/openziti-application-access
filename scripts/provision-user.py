#!/usr/bin/env python3
"""Reconstructed onboarding helper. Never sends email or logs enrollment tokens."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from email.message import EmailMessage
from email.policy import SMTP

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('identity')
    parser.add_argument('roles', help='Comma-separated approved application roles')
    parser.add_argument('--recipient')
    parser.add_argument('--sender')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', args.identity):
        parser.error('Identity must be 1–64 letters, digits, dots, underscores or hyphens.')
    catalog = json.loads((ROOT / 'config/applications.json').read_text())
    roles = list(dict.fromkeys(args.roles.split(',')))
    if not roles or any(role not in catalog for role in roles):
        parser.error('Use only catalog roles: ' + ', '.join(catalog))
    if bool(args.recipient) != bool(args.sender):
        parser.error('--recipient and --sender must be supplied together.')
    for address in (args.recipient, args.sender):
        if address and not re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', address):
            parser.error('Use a plain email address without display names or line breaks.')
    apps = [catalog[role] for role in roles]
    print('Identity:', args.identity)
    print('Roles:', ', '.join(roles))
    for app in apps:
        print(app['label'] + ': ' + app['url'])
    if not args.apply:
        print('Preview only. No files or controller requests. Verify your CLI context before --apply.')
        return 0
    if any(shutil.which(binary) is None for binary in ('ziti', 'qrencode')):
        parser.error('Install ziti and qrencode before creating an identity.')
    print('Using the current authenticated ziti CLI context.')
    try:
        found = subprocess.run(['ziti', 'edge', 'list', 'identities',
            'name = "' + args.identity + '"', '-j'], check=True, capture_output=True, text=True)
        data = json.loads(found.stdout)['data']
        if not isinstance(data, list):
            raise ValueError('Invalid identity response')
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError):
        print('Identity lookup failed; nothing created. Check CLI authentication and response format.', file=sys.stderr)
        return 1
    if data:
        print('Identity already exists; inspect it instead of creating another enrollment.', file=sys.stderr)
        return 1
    # Exact-name lookup is a guard, not a lock against concurrent administrators.
    os.umask(0o077)
    bundle = Path(tempfile.mkdtemp(prefix='enrollment-bundle-', dir='.')).resolve()
    jwt = bundle / 'identity.jwt'
    png = bundle / 'enrollment.png'
    try:
        subprocess.run(['ziti', 'edge', 'create', 'identity', args.identity,
            '--role-attributes', ','.join(roles), '--jwt-output-file', str(jwt)],
            check=True, capture_output=True)
        if not jwt.is_file() or not jwt.stat().st_size:
            raise ValueError('No enrollment token')
        jwt.chmod(0o600)
    except (subprocess.CalledProcessError, ValueError, OSError):
        print('Creation did not complete cleanly. Inspect the controller before retrying; an identity may exist.', file=sys.stderr)
        print('Private bundle:', bundle)
        return 1
    try:
        subprocess.run(['qrencode', '-r', str(jwt), '-o', str(png)], check=True, capture_output=True)
        if not png.is_file() or not png.stat().st_size:
            raise ValueError('No QR image')
        png.chmod(0o600)
    except (subprocess.CalledProcessError, ValueError, OSError):
        print('QR generation failed. Identity and JWT retained; do not recreate the identity.', file=sys.stderr)
        print('Private bundle:', bundle)
        return 1
    body = ('Your device identity is ' + args.identity + '.\n\n'
        'Import the JWT using your OpenZiti client, or use its supported QR import.\n'
        'These attachments represent the same one-time enrollment, not two identities.\n'
        'Use this identity on one device only. Do not forward the attachments.\n\n'
        'Assigned application links (access still depends on controller policies):\n' +
        ''.join('- ' + app['label'] + ': ' + app['url'] + '\n' for app in apps) +
        '\nAfter enrollment, connect the client and test each assigned application.\n'
        'Keep the application\'s own login. Report enrollment or connection errors to your administrator.\n'
        'Do not include the token or identity file in screenshots or support messages.\n')
    (bundle / 'instructions.txt').write_text(body)
    if args.recipient:
        message = EmailMessage(policy=SMTP)
        message['From'] = args.sender
        message['To'] = args.recipient
        message['Subject'] = 'Application access enrollment: ' + args.identity
        message.set_content(body)
        message.add_attachment(jwt.read_bytes(), maintype='application', subtype='octet-stream', filename='identity.jwt')
        message.add_attachment(png.read_bytes(), maintype='image', subtype='png', filename='enrollment.png')
        (bundle / 'enrollment.eml').write_bytes(message.as_bytes())
    print('Private bundle:', bundle)
    print('No email sent. Review the recipient and deliver through your approved channel.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
