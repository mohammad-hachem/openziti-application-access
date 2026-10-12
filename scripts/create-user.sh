#!/usr/bin/env bash
# Reconstructed example. Run from an already authenticated, reviewed CLI context.
# Creates one identity; never updates an existing identity or emails credentials.
set -euo pipefail
umask 077

usage() {
  printf 'Usage: %s IDENTITY_NAME portal-users [--apply]\n' "$0" >&2
  printf 'Default: print the plan only. --apply creates an identity and private JWT/QR bundle.\n' >&2
}
[[ $# -eq 2 || $# -eq 3 ]] || { usage; exit 2; }
identity_name=$1
role_name=$2
action_mode=dry-run
if [[ $# -eq 3 ]]; then
  [[ $3 == --apply ]] || { usage; exit 2; }
  action_mode=apply
fi
[[ $identity_name =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$ ]] || {
  printf 'Invalid identity name: use 1-64 letters, digits, dots, underscores or hyphens.\n' >&2
  exit 2
}
# Explicit access allowlist: extend only alongside reviewed service policies.
# No arbitrary role strings, Bind roles, wildcard selectors, or admin grants.
case "$role_name" in
  portal-users)
    application_url=https://portal.internal.example.com
    ;;
  *)
    printf 'Unsupported role. Allowed: portal-users\n' >&2
    exit 2
    ;;
esac

printf 'Identity: %s\nRole: %s\nApplication: %s\n' \
  "$identity_name" "$role_name" "$application_url"
printf 'Target: the current authenticated ziti CLI management context; verify it before --apply.\n'
if [[ $action_mode == dry-run ]]; then
  printf 'Dry run: would create identity, export JWT, and encode it as a PNG QR image.\n'
  printf 'No OpenZiti command was invoked and no files were created.\n'
  exit 0
fi
for executable in ziti qrencode mktemp; do
  command -v "$executable" >/dev/null || {
    printf 'Required executable missing: %s\n' "$executable" >&2
    exit 1
  }
done

# Unique, private output directory; no overwrite of an earlier enrollment bundle.
bundle_dir=$(mktemp -d "./enrollment-bundle-$identity_name.XXXXXXXX")
jwt_file="$bundle_dir/identity.jwt"
qr_file="$bundle_dir/enrollment.png"
printf 'Private output directory: %s\n' "$bundle_dir"

# If the CLI fails or its response is uncertain, stop and inspect the controller
# before retrying. Do not automatically delete identities or assume rollback.
if ! ziti edge create identity "$identity_name" \
  --role-attributes "$role_name" \
  --jwt-output-file "$jwt_file"; then
  printf 'Creation failed or result is uncertain. Inspect controller state before retrying.\n' >&2
  exit 1
fi
[[ -s $jwt_file ]] || {
  printf 'No JWT exported. Identity may exist: inspect before retrying.\n' >&2
  exit 1
}
chmod 600 "$jwt_file"
if ! qrencode -r "$jwt_file" -o "$qr_file"; then
  printf 'QR generation failed; identity and JWT remain. Regenerate QR from this JWT.\n' >&2
  exit 1
fi
chmod 600 "$qr_file"
printf 'Identity: %s\nRole: %s\nApplication: %s\n' \
  "$identity_name" "$role_name" "$application_url" > "$bundle_dir/instructions.txt"
printf 'Enroll using the approved mobile/desktop client before token expiry.\n' \
  >> "$bundle_dir/instructions.txt"
printf 'JWT and QR contain the same enrollment credential. Deliver securely to this device only.\n' \
  >> "$bundle_dir/instructions.txt"
printf 'Created private bundle. No email was sent and no client was enrolled locally.\n'
