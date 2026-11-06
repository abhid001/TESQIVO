# Enterprise license keys

TESQIVO Enterprise features (`backend/app/ee/`) activate only with a valid,
Ed25519-signed `TESQIVO_LICENSE_KEY`. This directory has the tooling to run that
scheme. It is **maintainer-only** — nothing here ships in either image.

## One-time setup

```bash
pip install 'cryptography>=42'
python scripts/license/gen_keypair.py
```

Store the output:

| Value | Where |
|---|---|
| `TESQIVO_LICENSE_PRIVKEY` | a password manager / offline. **Never commit. Never put in an image.** |
| `TESQIVO_LICENSE_PUBKEY`  | GitHub → repo → Settings → *Variables* → `TESQIVO_LICENSE_PUBKEY` (the release workflow bakes it into `tesqivo-enterprise` via a build arg). Safe to publish. |

## Issue a key for a customer

```bash
python scripts/license/issue.py \
  --private-key @privkey.b64 \
  --customer "Acme Inc" --features ai --days 365 --seats 25
```

Send the customer the printed string. They set it as `TESQIVO_LICENSE_KEY` (env,
in `.env` next to `docker-compose.enterprise.yml`) or drop it in
`/data/license.key` inside the `appdata` volume.

## Verify / inspect

```bash
docker compose exec web python -c "from app.core.license import current_license; print(current_license())"
```
or `GET /api/v1/ee/license` (system admin).

## Rotating the keypair

If `TESQIVO_LICENSE_PRIVKEY` leaks: `gen_keypair.py` again, update the
`TESQIVO_LICENSE_PUBKEY` variable, cut a new `tesqivo-enterprise` build, reissue
every customer key. Old keys stop verifying against the new public key.
