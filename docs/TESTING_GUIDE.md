# TESQIVO — Handover & Testing Guide

How to stand up TESQIVO on a machine and hand it to someone for testing.
Everything runs in Docker; no Python or Node needed on the host to *run* it.

---

## 1. What the tester receives

Pick one:

| Option | Give them | Good for |
|---|---|---|
| **A. A running URL** | You host it, they get a link + a login | Non-technical testers; fastest |
| **B. The repo** | A zip or Git access; they run `docker compose up` | Testers comfortable with a terminal |

Both paths below produce the same app.

---

## 2. Prerequisites (host that runs the stack)

- **Docker Desktop** (macOS/Windows) or **Docker Engine 24+ + Compose v2** (Linux)
- ~2 GB free RAM, ~2 GB disk
- Ports: one free host port for the web UI (default **8080**)
- `openssl` (for generating secrets) — preinstalled on macOS/Linux

Verify:

```bash
docker version        # Client + Server both present
docker compose version
```

---

## 3. Get the code

**From Git:**
```bash
git clone <your-repo-url> tesqivo
cd tesqivo
```

**From a zip:** unzip it, then `cd` into the folder. It must contain
`docker-compose.yml`, `backend/`, `frontend/`, `deploy/`.

---

## 4. Configure (`.env`)

```bash
cp .env.example .env
```

Edit `.env` and set these **four** values:

```dotenv
# 1. Session/CSRF secret — must be >= 32 bytes. Generate one:
#    openssl rand -base64 48
TESQIVO_SECRET_KEY=<paste generated value>

# 2. One-time gate for creating the first admin. Generate one:
#    openssl rand -hex 24
TESQIVO_BOOTSTRAP_TOKEN=<paste generated value>

# 3. The URL testers will open. Use the host's LAN IP if testing from other
#    machines, e.g. http://192.168.1.50:8080
TESQIVO_PUBLIC_URL=http://localhost:8080

# 4. Database password (any strong string)
POSTGRES_PASSWORD=<strong password>
```

Leave `TESQIVO_HTTP_PORT=8080` unless 8080 is taken.

Email is **optional** and off by default — the "Forgot password?" screen will
tell testers to contact an administrator, which is fine for a test instance. To
enable it, fill the `TESQIVO_SMTP_*` block in `.env`.

> Keep `.env` private — it holds secrets. It is git-ignored.

---

## 5. Start the stack

```bash
docker compose up -d --build
```

First run builds images (~2–4 min). It starts six services:
`db`, `redis`, `migrate` (runs once and exits), `api`, `worker`, `proxy`.

Wait for health, then check:

```bash
docker compose ps
curl -fsS http://localhost:8080/api/v1/healthz     # {"status":"ok"}
curl -fsS http://localhost:8080/api/v1/readyz      # database: ok
```

`migrate` showing **Exited (0)** is correct — it applies the schema and stops.

Open **http://localhost:8080** (or your `TESQIVO_PUBLIC_URL`).

---

## 6. First-admin setup (once)

The first screen is **"Create the first administrator"**.

1. Paste the `TESQIVO_BOOTSTRAP_TOKEN` from your `.env`.
2. Choose an admin **username**, **email**, and **password**
   (min 12 chars, upper + lower + a digit).
3. Submit. You land in the **Admin console**.

After this succeeds, the setup screen is permanently disabled. For safety you can
now blank `TESQIVO_BOOTSTRAP_TOKEN` in `.env` and `docker compose up -d` again.

---

## 7. Create a project and tester accounts

TESQIVO separates **admin** work from **test-management** work.

### 7a. Create a project (as the system admin)

Admin console → **Projects** → **+ New project**
- **Key**: 2–16 uppercase letters/digits, e.g. `PAY`
- **Name**: e.g. `Payments`

### 7b. Give testers access

Open the project (**Projects → Open**), then the **Settings** tab → **+ Add member**.

For each tester, choose **Create new user** and set a username, email, and a
temporary password, then pick a **role**:

| Role | Can do |
|---|---|
| **Test manager** | Everything in the test tool: scenarios, test cases, plans, cycles, releases, executions, links |
| **Tester** | Execute assigned cycle tests; create requirements/defects |
| **Viewer** | Read-only |
| **Project admin** | Test-manager rights **plus** manage this project's members |

For a general "please test the app" hand-off, give them **Test manager**.

Send each tester: the **URL**, their **username**, and their **temporary
password**. Tell them to change it after first sign-in (topbar → *Settings* is
project-scoped; self-service password change is under the account — if they were
issued a temporary password they'll be forced to set a new one on login).

> The tester does **not** get the bootstrap token and cannot reach the Admin
> console — that is admin-only by design.

### 7c. Self-service access (alternative)

You can also just hand a tester a login with **no project** and let them request
access themselves: **Projects → Browse all projects → Request access**. The
request lands in **Admin console → Access requests** (or the project's
**Settings → Pending access requests** for a project admin), where you approve it
at a chosen role. Every signed-in user also has an account menu (top-right:
profile, email, change password, sign out) and a **Feedback** button that sends
straight to **Admin console → Feedback** (exportable to CSV / text).

---

## 8. (Optional) Load demo data

Gives testers a realistic project to explore immediately (12 requirements,
scenarios, ~12 test cases, an active cycle with executions, defects, releases).

Requires Python on the host once, to run the seed script:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -q -e ".[dev]" && cd ..
make seed PASSWORD='<your admin password>'
# or:
backend/.venv/bin/python scripts/seed_demo.py --base http://localhost:8080 \
  --user admin --password '<your admin password>'
```

It creates a project **`DEMO — Payments Platform (demo)`**. It is idempotent — it
skips if `DEMO` already exists.

---

## 9. What to ask the tester to try

A suggested happy-path walkthrough (project scoped, as a Test manager):

1. **Sign in**, switch to the project (top-left project menu).
2. **Requirements** → create 2–3 requirements → **Activate** them (defects live on the same tab).
3. **Scenarios** → create a scenario, link it to a requirement.
4. **Tests** → create a test case with steps; assign it to the scenario;
   move it through **submit for review → approve → activate** (test-case detail page).
5. **Plans** → create a plan, add the active test case to scope, **Activate**.
6. **Cycles** → create a cycle (environment + build), **Manage tests** to add the
   test, **Activate** (this snapshots the approved version).
7. **Cycles → Run** → start an attempt, set each step result, **Complete**.
8. **Dashboard** → confirm coverage and pass-rate update; **click a chart bar or
   any figure** to drill into the exact records; try the **Release** and **Cycle**
   scope filters and **Export CSV**.
9. **Traceability** → open the matrix; toggle design vs cycle view.
10. Exercise edge cases: edit an approved test case (should fork a new draft
    version while the cycle keeps its snapshot), archive/restore, wrong password
    lockout, "Forgot password?", sorting/pagination on the Tests table.

Ask them to note the **correlation_id** shown in any error message when filing a bug.

---

## 10. Operating the instance

```bash
docker compose logs -f --tail=100        # live logs (all services)
docker compose logs api                  # one service
docker compose restart api               # restart a service
docker compose down                      # stop, keep data
docker compose up -d                     # start again
```

### Reset to a clean slate (wipes all data)

```bash
docker compose down -v && docker compose up -d --build
```

Then repeat step 6 (first-admin setup).

### Back up / restore test data

```bash
make backup                                             # -> ./backups/
make restore BACKUP=backups/db-XXXX.dump ATTACH=backups/attachments-XXXX.tgz
```

### Reset a forgotten admin/user password

Admin console → **Users** → **Reset password** on the row → hand the token to the
user, who completes it at the "Forgot password?" screen. (For the *only* system
admin, if you're locked out entirely, see `docs/OPERATIONS.md`.)

### Upgrade to a newer build

```bash
git pull            # or drop in a new zip
docker compose up -d --build     # 'migrate' re-runs automatically
```

---

## 11. Testing from other machines / sharing externally

- **Same LAN:** set `TESQIVO_PUBLIC_URL=http://<host-LAN-IP>:8080`, re-run
  `docker compose up -d`, and open the firewall for that port. Testers use that URL.
- **Over the internet:** put a TLS reverse proxy / tunnel in front (e.g. a
  Cloudflare Tunnel or an nginx with a real certificate), set `TESQIVO_PUBLIC_URL`
  to the **https** URL (this makes session cookies `Secure`), and restart.
  Do **not** expose the raw `:8080` port publicly without TLS.

---

## 12. Health & support checklist for the tester

Give the tester this short note:

> **URL:** `<your URL>`  ·  **Username:** `<their username>`  ·  **Password:** `<temp password>` (change on first login)
>
> - API docs (for reference): `<URL>/api/v1/docs`
> - If something breaks: screenshot it **including the error's `correlation_id`**,
>   note what you did, and send it to `<you>`.
> - Known Phase-1 limits: no automation result ingestion, no external Jira/GitLab
>   sync, no AI features, email may be disabled (use "contact admin" for resets).

---

## 13. Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose up` fails: *"required variable TESQIVO_SECRET_KEY is missing"* | `.env` not filled — set all four values in step 4 |
| API container restarts / `readyz` shows `database: unavailable` | `docker compose logs api db`; usually `db` still starting — wait 20 s |
| `migrate` exited non-zero | `docker compose logs migrate`; on a schema conflict after an upgrade, reset with `down -v` (test data only) |
| Port 8080 in use | set `TESQIVO_HTTP_PORT` to a free port in `.env`, `up -d` again |
| Login works but every action says *"Missing or invalid CSRF token"* | hard-refresh the browser (Cmd/Ctrl+Shift+R); stale cached bundle |
| Tester on another machine can't sign in | `TESQIVO_PUBLIC_URL` must match the URL they actually open |
| `worker` shows unhealthy briefly at startup | normal for ~20 s while it connects to Redis |
