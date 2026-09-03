#!/usr/bin/env python3
"""Generate the Ed25519 keypair used to sign TESQIVO Enterprise license keys.

Run ONCE. Keep the PRIVATE key secret (password manager / CI secret). The PUBLIC
key is baked into the enterprise image via the TESQIVO_LICENSE_PUBKEY build arg
and stored as a GitHub Actions *variable* (not a secret).

    python scripts/license/gen_keypair.py
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def main() -> None:
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    pub_raw = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    print(f"TESQIVO_LICENSE_PRIVKEY={_b64(priv_raw)}")
    print(f"TESQIVO_LICENSE_PUBKEY={_b64(pub_raw)}")


if __name__ == "__main__":
    main()
