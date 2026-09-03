#!/usr/bin/env python3
"""Issue a signed TESQIVO Enterprise license key.

    python scripts/license/issue.py \
        --private-key @/path/to/privkey.b64 \
        --customer "Acme Inc" --features ai,sso --days 365 --seats 25

Prints one line: the value the customer sets as TESQIVO_LICENSE_KEY (or writes to
/data/license.key). Requires the PRIVATE key from gen_keypair.py.
"""

import argparse
import base64
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _resolve(value: str) -> str:
    if value.startswith("@"):
        with open(value[1:]) as fh:
            return fh.read().strip()
    return value.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private-key", required=True, help="base64 Ed25519 private key, or @file")
    ap.add_argument("--customer", required=True)
    ap.add_argument("--features", default="", help="comma-separated, e.g. ai,sso")
    ap.add_argument("--days", type=int, default=365, help="0 = perpetual")
    ap.add_argument("--seats", type=int, default=0)
    args = ap.parse_args()

    now = int(time.time())
    payload = {
        "iss": "tesqivo",
        "sub": args.customer,
        "features": [f.strip() for f in args.features.split(",") if f.strip()],
        "iat": now,
        "exp": 0 if args.days == 0 else now + args.days * 86400,
        "seats": args.seats,
    }
    payload_b64 = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    priv = Ed25519PrivateKey.from_private_bytes(_b64d(_resolve(args.private_key)))
    sig_b64 = _b64(priv.sign(payload_b64.encode()))
    print(f"{payload_b64}.{sig_b64}")


if __name__ == "__main__":
    main()
