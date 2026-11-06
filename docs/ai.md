# AI features

TESQIVO has two optional AI features. Both are **off until an administrator adds an
API key**, and neither can change project data without a person approving it.

| | Ask TESQIVO (help assistant) | AI Test Design (test-case generator) |
|---|---|---|
| Edition | Community and Enterprise | Enterprise, licence feature `ai` |
| What it does | Answers "how do I…?" questions about TESQIVO in a chat panel | Turns requirements, scenarios or user stories into suggested test cases |
| Who can use it | Every signed-in user | Generate: testers and test managers. Accept: test managers |
| What is sent to the AI provider | The question, the chat so far, the user's role and the page path. **No project records.** | The selected requirements (title, description, acceptance criteria), scenario, pasted story, and titles of existing test cases (to avoid duplicates) |
| Can it change data? | No. It has no tools. | Only through a human: accepted suggestions become **Draft** test cases |

The provider is Anthropic's Claude (default model `claude-opus-5-5`), called from
the TESQIVO server. Browsers never talk to the provider and never see the key.

## Turning it on

Add to the `.env` next to `docker-compose.yml`, then `docker compose up -d`:

```dotenv
TESQIVO_AI_API_KEY=sk-ant-...           # an Anthropic API key (console.anthropic.com)
```

That's all for the help assistant. For AI Test Design you also need the Enterprise
image and a licence key that includes `ai` (see [enterprise.md](enterprise.md)).

| Setting | Default | Meaning |
|---|---|---|
| `TESQIVO_AI_API_KEY` | *(unset)* | Anthropic API key. Unset = every AI feature is off. |
| `TESQIVO_AI_ENABLED` | `true` | Kill switch: `false` turns every AI feature off even with a key set. |
| `TESQIVO_AI_MODEL` | `claude-opus-5-5` | Model used by both features. |
| `TESQIVO_AI_ASSISTANT_EFFORT` | `low` | Reasoning effort for chat answers (`low`…`max`). Low keeps answers fast and cheap. |
| `TESQIVO_AI_GENERATION_EFFORT` | `high` | Reasoning effort for test-case generation. |
| `TESQIVO_AI_REQUESTS_PER_USER_HOUR` | `60` | Per-user limit across both features. Over it returns 429. |
| `TESQIVO_AI_MAX_CASES_PER_GENERATION` | `25` | Upper bound a user can ask for in one generation. |

Check it's live: `GET /api/v1/assistant/status` returns
`{"assistant": true, "generator": true|false}` for a signed-in user.

**Privacy.** Turning AI on means the content in the table above leaves your server
for Anthropic's API. Check that this fits your data policy before setting the key.
Nothing is sent while the key is unset or `TESQIVO_AI_ENABLED=false`.

**Cost.** Usage is billed to the API key's Anthropic account. A help-assistant answer
is small. The guide part of the prompt is identical for everyone, so the provider
caches it. A generation is larger and scales with the number and length of
requirements and the number of test cases requested. Token counts for each
generation are stored and shown on its review page.

## Ask TESQIVO

The **Ask TESQIVO** button (bottom-right, above Feedback) opens a chat panel with
starter questions for the page you're on. Answers come from a built-in user guide
(`backend/app/domain/ai/knowledge/user_guide.md`), plus your role and what that role
is allowed to do. That list comes from the live permission rules, so it can't drift.
The chat lives in your browser tab only and is not stored on the server.

To change what the assistant knows, edit `user_guide.md`. Keep it to things the UI
really does: the assistant is told never to invent screens or buttons.

## AI Test Design (Enterprise)

1. **Start.** On **Requirements**, select up to 10 requirements and click
   **Generate tests**. Or open **AI Test Design** in the sidebar and pick
   requirements, a scenario, and/or paste a user story. Choose what to cover
   (happy path, negative, boundary, permissions, security, accessibility, usability,
   integration), how many test cases at most, and any extra instructions.
2. **Wait.** The request runs as a background job on the `worker` service, which
   must be running. It usually takes under a minute. The page updates itself.
3. **Review.** Each suggestion shows its steps, type, priority, the requirements it
   covers and why it matters. You also get the **assumptions** the AI made and
   **questions** about ambiguous requirements, which are worth taking to the
   requirement owner. Suggestions that look like an existing test case are flagged.
4. **Decide.** Anyone who can generate can **Edit** or **Reject** (with a reason).
   A test manager clicks **Accept as Draft** (or **Accept all**).

An accepted suggestion becomes an ordinary **Draft** test case, linked to its
requirements, with the version marked *AI-generated*. It goes through the normal
**Submit for review → Approve version → Activate** flow. Until then it does not count
as coverage.

### Safeguards

- **Authorization.** Sources are checked against the requester's project access when
  the request is made, and the exact content sent is stored with the generation.
- **Untrusted input.** Requirement and story text is passed to the model as data,
  fenced off and explicitly not to be followed as instructions.
- **Validated output.** The model must return a fixed JSON schema. Each suggestion is
  validated again on the server. Incomplete ones are dropped, links to requirements
  that weren't in the sources are removed, and the count is capped.
- **No silent writes.** The provider never writes. Suggestions don't touch the test
  repository until a test manager accepts them. Existing tests are never modified.
- **Audit.** Requests, rejections and acceptances appear in **Logs**. Each generation
  keeps provider, model, prompt version, sources, token usage and who decided what.
- **Licence.** The worker re-checks the licence before sending anything, so a lapsed
  licence stops queued jobs too.

## For developers

- Provider port: `backend/app/domain/ai/provider.py` (`AiProvider`, `AnthropicProvider`).
  Tests swap in a fake with `set_provider_for_tests`. `tests/test_ai_provider.py`
  checks the exact HTTP request against a mocked transport.
- Assistant: `backend/app/domain/ai/assistant.py`, `POST /api/v1/assistant/chat`
  (Server-Sent Events: `delta` / `done` / `error`).
- Generator (proprietary): `backend/app/ee/ai/generator.py`, `/api/v1/ee/ai/*`,
  job type `ai_generate`. Tables `ai_generation`, `ai_suggestion` (migration 0008).
- Enterprise UI: `frontend/src/ee/`, compiled in only when the SPA is built with
  `TESQIVO_EDITION=enterprise` (the `@edition` alias in `vite.config.ts`).
