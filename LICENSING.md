# Licensing

TESQIVO is **open-core**.

## Community edition — GNU AGPL-3.0

Everything in this repository **except** the paths listed below is free software
under the [GNU Affero General Public License v3.0](LICENSE). You may run, study,
modify, and self-host it, including in production, at no cost. If you run a
modified version as a network service, the AGPL requires you to offer that
service's users the corresponding source.

The Community edition is published as the container image
`ghcr.io/abhid001/tesqivo` (public) and installed with `docker-compose.yml`.

## Enterprise edition — proprietary

These paths are **not** covered by the AGPL and are proprietary
(© 2026 Abhishek Dixit — see [`backend/app/ee/LICENSE`](backend/app/ee/LICENSE)):

- `backend/app/ee/**`
- `frontend/src/ee/**`
- `Dockerfile.enterprise`

They add paid capabilities (LLM-assisted test authoring first, more later),
build the private image `ghcr.io/abhid001/tesqivo-enterprise`, and only activate
with a signed `TESQIVO_LICENSE_KEY`. See [`docs/enterprise.md`](docs/enterprise.md).

## Contributing

Contributions to the Community edition are accepted under the
[Developer Certificate of Origin](https://developercertificate.org/) — sign your
commits with `git commit -s`. Contributions to `ee/` require a separate agreement;
open an issue first.

## History

The licence has changed during early development: proposed Apache-2.0 →
all-rights-reserved proprietary → **open-core (AGPL-3.0 + proprietary `ee/`)**.
See decision **D-012** / **D-021** in `docs/architecture/16_decisions.md`.
