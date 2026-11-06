# frontend/src/ee — Enterprise UI (proprietary)

Enterprise-only React code (AI Test Design today). It is compiled **only** into
the `tesqivo-enterprise` image: `Dockerfile.enterprise` builds the SPA with
`TESQIVO_EDITION=enterprise`, which points the `@edition` import alias at
`./index.tsx` (see `vite.config.ts`). Every other build resolves `@edition` to
`src/edition/community.tsx`, so none of this code is bundled. `tsc` still
type-checks it against `src/edition/types.ts`.

Try it locally: `TESQIVO_EDITION=enterprise npm run dev`.

Licence: proprietary — see `./LICENSE` and `/LICENSING.md`.
