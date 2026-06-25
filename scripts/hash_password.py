from __future__ import annotations

import getpass
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.security import hash_password, verify_password


def main() -> None:
    password = getpass.getpass("ACCESS_PASSWORD: ")
    confirm = getpass.getpass("Confirm ACCESS_PASSWORD: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    if not password:
        raise SystemExit("Password must not be empty.")

    encoded = hash_password(password)
    if not verify_password(password, encoded):
        raise SystemExit("Generated hash failed verification.")
    print(encoded)


if __name__ == "__main__":
    main()
