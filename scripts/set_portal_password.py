#!/usr/bin/env python3
"""
Generate a GOKU_PORTAL_PASSWORD_HASH value.

There's no admin UI to set the portal password from, so this hashes it
for you. The plaintext is never written anywhere — only the hash is
printed, for you to paste into the systemd unit's environment (or an
.env file) as GOKU_PORTAL_PASSWORD_HASH.
"""
import getpass
import os
import sys

from werkzeug.security import generate_password_hash, check_password_hash


def main():
    password = getpass.getpass("New portal password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords didn't match.", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("Use at least 8 characters.", file=sys.stderr)
        return 1

    pw_hash = generate_password_hash(password)
    assert check_password_hash(pw_hash, password)

    print("\nAdd this to your environment (e.g. the systemd unit or .env):\n")
    print(f'GOKU_PORTAL_PASSWORD_HASH="{pw_hash}"')
    print(f'GOKU_PORTAL_USERNAME="{os.getenv("GOKU_PORTAL_USERNAME", "goku")}"  # change if desired')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
