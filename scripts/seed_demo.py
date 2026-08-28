#!/usr/bin/env python3
"""Populate a TESQIVO instance with realistic demo data.

Usage:
    backend/.venv/bin/python scripts/seed_demo.py \
        --base http://localhost:8080 --user admin --password '<admin password>'

Idempotent-ish: if the demo project key already exists it exits without changes.
Drives the public REST API exactly like the GUI would.
"""

from __future__ import annotations

import argparse
import random
import sys

import httpx

random.seed(42)

PROJECT_KEY = "DEMO"
PROJECT_NAME = "Payments Platform (demo)"


class Api:
    def __init__(self, base: str):
        self.c = httpx.Client(base_url=base.rstrip("/") + "/api/v1", timeout=30)
        self.csrf: str | None = None

    def login(self, user: str, password: str) -> None:
        r = self.c.post("/auth/session", json={"username": user, "password": password})
        r.raise_for_status()
        self.csrf = self.c.cookies.get("tesqivo_csrf")

    def _h(self) -> dict:
        h = {"X-Tesqivo-Client": "web"}
        if self.csrf:
            h["X-CSRF-Token"] = self.csrf
        return h

    def get(self, path: str):
        r = self.c.get(path, headers=self._h())
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None):
        r = self.c.post(path, json=body or {}, headers=self._h())
        if r.status_code >= 400:
            raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content else {}

    def patch(self, path: str, body: dict):
        r = self.c.patch(path, json=body, headers=self._h())
        if r.status_code >= 400:
            raise RuntimeError(f"PATCH {path} -> {r.status_code}: {r.text}")
        return r.json()


REQUIREMENTS = [
    ("Customer can add a payment card", "functional", "high", "Wallet"),
    ("Card details are validated before save", "functional", "high", "Wallet"),
    ("Customer can pay with a saved card", "functional", "critical", "Checkout"),
    ("Failed payment shows a clear reason", "functional", "medium", "Checkout"),
    ("Refunds are processed within 5 seconds", "performance", "medium", "Refunds"),
    ("Partial refunds are supported", "functional", "medium", "Refunds"),
    ("All payment events are written to the ledger", "functional", "critical", "Ledger"),
    ("3-D Secure challenge is triggered when required", "functional", "high", "Checkout"),
    ("Statement export is available as CSV", "functional", "low", "Reporting"),
    ("PCI scope is limited to the vault service", "security", "critical", "Platform"),
    ("Idempotency keys prevent double charges", "functional", "critical", "Checkout"),
    ("Currency rounding follows ISO-4217 minor units", "functional", "medium", "Ledger"),
]

TEST_CASES = [
    ("Add a valid Visa card", "Wallet", ["active"], "automated"),
    ("Add card with expired date is rejected", "Wallet", ["active"], "automated"),
    ("Add card with bad Luhn is rejected", "Wallet", ["active"], "candidate"),
    ("Pay with saved card - happy path", "Checkout", ["active"], "automated"),
    ("Pay with insufficient funds shows decline reason", "Checkout", ["active"], "candidate"),
    ("Pay triggers 3-D Secure for flagged BIN", "Checkout", ["active"], "candidate"),
    ("Duplicate pay request with same idempotency key charges once", "Checkout", ["active"], "automated"),
    ("Full refund returns funds and ledger entry", "Refunds", ["active"], "candidate"),
    ("Partial refund of 50% is accepted", "Refunds", ["draft"], "candidate"),
    ("Refund latency under load stays < 5s", "Refunds", ["in_review"], "not_applicable"),
    ("Ledger contains one entry per settled payment", "Ledger", ["active"], "automated"),
    ("Statement CSV export opens in a spreadsheet", "Reporting", ["deprecated"], "not_applicable"),
]


def steps_for(title: str) -> list[dict]:
    return [
        {"action": f"Open the screen for: {title}", "expected_result": "The screen loads without errors"},
        {"action": "Perform the primary action described by the test title", "expected_result": "The system responds as specified"},
        {"action": "Verify the resulting state / record", "expected_result": "Data matches the expectation and is persisted"},
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://localhost:8080")
    p.add_argument("--user", default="admin")
    p.add_argument("--password", required=True)
    args = p.parse_args()

    api = Api(args.base)
    api.login(args.user, args.password)

    for proj in api.get("/projects"):
        if proj["key"] == PROJECT_KEY:
            print(f"Project {PROJECT_KEY} already exists ({proj['id']}); nothing to do.")
            return 0

    project = api.post("/projects", {"key": PROJECT_KEY, "name": PROJECT_NAME})
    pid = project["id"]
    print("created project", pid)

    for comp in ["Wallet", "Checkout", "Refunds", "Ledger", "Reporting", "Platform"]:
        api.post(f"/projects/{pid}/reference-values", {"kind": "component", "value": comp})

    rel_q4 = api.post(f"/projects/{pid}/releases", {"name": "2025.12 - Q4", "version_label": "v2025.12"})
    rel_q1 = api.post(f"/projects/{pid}/releases", {"name": "2026.03 - Q1", "version_label": "v2026.03"})
    api.post(f"/releases/{rel_q4['id']}/transitions", {"to": "active", "expected_version": rel_q4["version"]})
    api.post(f"/releases/{rel_q1['id']}/transitions", {"to": "active", "expected_version": rel_q1["version"]})

    # requirements
    reqs = []
    for i, (title, rtype, prio, comp) in enumerate(REQUIREMENTS):
        r = api.post(
            f"/projects/{pid}/requirements",
            {"title": title, "req_type": rtype, "priority": prio, "component": comp,
             "release_id": rel_q4["id"] if i % 2 == 0 else rel_q1["id"]},
        )
        # activate most, leave a couple as draft, mark one fulfilled
        if i < 9:
            r = api.post(f"/requirements/{r['id']}/transitions", {"to": "active", "expected_version": r["version"]})
        if i == 8:
            r = api.post(f"/requirements/{r['id']}/transitions", {"to": "fulfilled", "expected_version": r["version"]})
        reqs.append(r)
    print(f"created {len(reqs)} requirements")

    # folders
    folders = {}
    for name in ["Wallet", "Checkout", "Refunds", "Ledger", "Reporting"]:
        folders[name] = api.post(f"/projects/{pid}/folders", {"name": name})["id"]

    # test cases
    tcs = []
    for title, folder, lifecycle, automation in TEST_CASES:
        tc = api.post(
            f"/projects/{pid}/test-cases",
            {"title": title, "folder_id": folders[folder], "steps": steps_for(title),
             "automation_status": automation},
        )
        target = lifecycle[0]
        chain = {
            "draft": [],
            "in_review": [("v", "in_review")],
            "approved": [("v", "in_review"), ("v", "approved")],
            "active": [("v", "in_review"), ("v", "approved"), ("l", "active")],
            "deprecated": [("v", "in_review"), ("v", "approved"), ("l", "active"), ("l", "deprecated")],
        }[target]
        for kind, to in chain:
            ep = "version-transitions" if kind == "v" else "lifecycle-transitions"
            body = {"to": to, "expected_version": tc["version"]}
            tc = api.post(f"/test-cases/{tc['id']}/{ep}", body)
        tcs.append(tc)
    print(f"created {len(tcs)} test cases")

    # trace links: requirement -> test case (roughly aligned by component)
    links = 0
    comp_of_req = {reqs[i]["id"]: REQUIREMENTS[i][3] for i in range(len(REQUIREMENTS))}
    comp_of_tc = {tcs[i]["id"]: TEST_CASES[i][1] for i in range(len(TEST_CASES))}
    for r in reqs:
        for t in tcs:
            if comp_of_req[r["id"]] == comp_of_tc[t["id"]]:
                try:
                    api.post(
                        f"/projects/{pid}/trace-links",
                        {"source_type": "requirement", "source_id": r["id"],
                         "target_type": "test_case", "target_id": t["id"]},
                    )
                    links += 1
                except RuntimeError:
                    pass
    print(f"created {links} requirement->test links")

    # plan + cycles
    plan = api.post(f"/projects/{pid}/plans", {"name": "Q1 regression", "objective": "Regression before the 2026.03 release", "release_id": rel_q1["id"]})
    active_tc_ids = [t["id"] for t, spec in zip(tcs, TEST_CASES) if spec[2][0] == "active"]
    api.post(f"/plans/{plan['id']}/scope", {"test_case_ids": active_tc_ids})
    api.post(f"/plans/{plan['id']}/transitions", {"to": "active", "expected_version": plan["version"]})

    cyc = api.post(
        f"/plans/{plan['id']}/cycles",
        {"name": "Staging - build 481", "environment": "staging", "build": "481", "release_id": rel_q1["id"]},
    )
    added = api.post(f"/cycles/{cyc['id']}/tests", {"test_case_ids": active_tc_ids})
    api.post(f"/cycles/{cyc['id']}/transitions", {"to": "active", "expected_version": cyc["version"]})
    print(f"activated cycle with {added['added']} tests")

    # a second, not-yet-started cycle for variety
    api.post(
        f"/plans/{plan['id']}/cycles",
        {"name": "Production smoke - build 481", "environment": "production", "build": "481", "release_id": rel_q1["id"]},
    )

    # executions - a realistic spread
    ct_rows = api.get(f"/cycles/{cyc['id']}/tests")["items"]
    outcomes = ["passed", "passed", "passed", "passed", "failed", "blocked", "passed", "skipped"]
    fail_attempt_ids = []
    for i, ct in enumerate(ct_rows):
        if i >= len(ct_rows) - 2:
            break  # leave the last two "not run"
        attempt = api.post(f"/cycle-tests/{ct['id']}/attempts")
        verdict = outcomes[i % len(outcomes)]
        n_steps = len(attempt["steps"])
        for s in range(1, n_steps + 1):
            res = "passed"
            if verdict != "passed" and s == n_steps:
                res = verdict
            api.patch(f"/attempts/{attempt['id']}/steps/{s}", {"result": res})
        done = api.post(f"/attempts/{attempt['id']}/complete", {})
        if done["overall_result"] == "FAILED":
            fail_attempt_ids.append((done["id"], ct))
    print(f"ran {len(ct_rows) - 2} executions")

    # defects
    defects = []
    d1 = api.post(f"/projects/{pid}/defects", {
        "summary": "Saved-card payment declines with generic error when 3-DS times out",
        "severity": "critical", "priority": "high", "environment": "staging",
        "release_id": rel_q1["id"], "detected_build": "481",
    })
    api.post(f"/defects/{d1['id']}/transitions", {"to": "open", "expected_version": d1["version"]})
    defects.append(d1)

    d2 = api.post(f"/projects/{pid}/defects", {
        "summary": "Partial refund rounds up 0.5 minor units",
        "severity": "high", "priority": "medium", "environment": "staging",
    })
    d2 = api.post(f"/defects/{d2['id']}/transitions", {"to": "open", "expected_version": d2["version"]})
    d2 = api.post(f"/defects/{d2['id']}/transitions", {"to": "in_progress", "expected_version": d2["version"]})
    defects.append(d2)

    d3 = api.post(f"/projects/{pid}/defects", {
        "summary": "Statement CSV header row missing on empty export",
        "severity": "minor", "priority": "low",
    })
    d3 = api.post(f"/defects/{d3['id']}/transitions", {"to": "open", "expected_version": d3["version"]})
    d3 = api.post(f"/defects/{d3['id']}/transitions", {"to": "in_progress", "expected_version": d3["version"]})
    d3 = api.post(f"/defects/{d3['id']}/transitions", {"to": "resolved", "expected_version": d3["version"], "resolution": "fixed", "resolved_build": "482"})
    d3 = api.post(f"/defects/{d3['id']}/transitions", {"to": "closed", "expected_version": d3["version"]})
    defects.append(d3)

    # link the critical defect to a failed attempt + to the checkout requirement
    if fail_attempt_ids:
        att_id, _ = fail_attempt_ids[0]
        api.post(f"/attempts/{att_id}/defects", {"defect_id": d1["id"]})
    checkout_req = next(r for r, spec in zip(reqs, REQUIREMENTS) if spec[3] == "Checkout" and r["status"] == "active")
    api.post(f"/projects/{pid}/trace-links", {
        "source_type": "defect", "source_id": d1["id"],
        "target_type": "requirement", "target_id": checkout_req["id"],
    })
    api.post(f"/projects/{pid}/trace-links", {
        "source_type": "defect", "source_id": d1["id"],
        "target_type": "release", "target_id": rel_q1["id"],
    })
    print(f"created {len(defects)} defects")

    print(f"\nDemo data ready. Open {args.base} and switch to project '{PROJECT_KEY}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
