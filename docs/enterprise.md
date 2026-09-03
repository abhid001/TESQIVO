# TESQIVO Enterprise

The Community edition (AGPL-3.0, `docker-compose.yml`) is complete test
management and free to self-host forever. **Enterprise** adds paid capabilities
on top of it and requires a subscription.

| | Community | Enterprise |
|---|---|---|
| Licence | AGPL-3.0 (free) | Proprietary (subscription) |
| Image | `ghcr.io/abhid001/tesqivo` (public) | `ghcr.io/abhid001/tesqivo-enterprise` (private) |
| Everything in Community | ✅ | ✅ |
| AI-assisted test authoring (`/api/v1/ee/ai/*`) | — | ✅ (roadmap: LLM generation) |
| More Enterprise features | — | as released |

Enterprise is the **same** application plus the proprietary `app/ee/` code; the
image is built `FROM` the exact Community image of the same version, so upgrades,
data, backups and configuration work identically.

## Getting a subscription

Contact the maintainer. You receive:

1. **Pull access** to `ghcr.io/abhid001/tesqivo-enterprise`.
2. A signed **license key** — a single string that encodes which features you're
   entitled to, an expiry, and a seat count.

## Install

```bash
# authenticate to the private registry (one-time)
echo <YOUR_GH_TOKEN> | docker login ghcr.io -u <YOUR_GH_USER> --password-stdin

curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.enterprise.yml

export TESQIVO_LICENSE_KEY='<the key you were sent>'
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d
docker compose exec web python -m app.cli create-admin
```

The key can also be placed in `/data/license.key` (inside the `appdata` volume)
instead of the environment variable.

Everything else — first admin, HTTPS, upgrades, backup/restore — is identical to
[`../INSTALL.md`](../INSTALL.md); just keep the `-f docker-compose.enterprise.yml`
overlay on every `docker compose` command.

## Checking entitlements

```bash
curl -s http://localhost:8080/api/v1/version
# {"version":"v0.3.0","edition":"enterprise","features":["ai"], ...}
```

`GET /api/v1/ee/license` (as a system admin) shows the customer, feature list,
expiry and seat count. When a key is missing, expired, or lacks a feature, that
feature's endpoints return **402 `LICENSE_REQUIRED`** with a clear message; the
rest of the app is unaffected.

## Expiry & renewal

Features stop working when the key's `exp` passes. Renew by setting the new key
and `docker compose … up -d` (no downtime for the rest of the app). Seat count is
currently advisory (surfaced, not enforced).

## Upgrading

```bash
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml pull
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d
```

Pin `TESQIVO_VERSION` for reviewed upgrades. The Enterprise image for a version
is only published after the Community image for that version.
