# HR Assistant: RAG + Agent on local Ollama

Employees ask HR questions in natural language. Policy questions are answered from company
documents (RAG, with citations). Personal questions ("my leave balance") are answered through
tools that call the HRMS as the **authenticated user**. Everything runs locally.

## Run it

```bash
cp .env.example .env            # already done if you unzipped the provided .env
make up                         # builds + starts everything (first run downloads models, ~5 GB)
docker compose logs -f ollama-pull   # wait until both models are pulled
make seed                       # indexes sample policies
open http://localhost:3000
```

| URL | What |
|---|---|
| http://localhost:3000 | App (nginx: UI + `/api` proxy) |
| http://localhost:8000/docs | API docs (dev only) |
| http://localhost:8000/metrics | Prometheus metrics |
| http://localhost:8080 | Keycloak admin (admin / admin) |
| http://localhost:6333/dashboard | Qdrant (add `ports` to compose to expose) |

Test users (password = username): `alice` (employee), `bob` (manager), `hradmin` (hr).
Try the same question as alice and bob: *"What is the merit increase budget?"* Alice must get
"not found"; Bob gets the answer. That is the retrieval ACL working.

## Architecture

```
Browser (React) --OIDC PKCE--> Keycloak  (issues signed JWT, 15 min)
   |  Authorization: Bearer <JWT>
   v
nginx (TLS in prod, proxy_buffering off for streaming)
   v
FastAPI x N (stateless)
   1. verify JWT via JWKS (sig, exp, iss, aud) -> User(id, roles)
   2. rate limit (Redis)         3. input guardrails
   4. load last N messages (Postgres)
   5. LangGraph ReAct agent (Ollama) picks a tool:
        search_policy        -> Qdrant, filtered by the user's roles
        get_my_leave_balance -> HRMS (user id from the JWT, never from the LLM)
        get_my_next_payday   -> HRMS
        create_hr_ticket     -> HRMS
   6. stream tokens/tool status/sources to the browser over SSE
   7. persist answer + audit row

Celery worker (separate process): upload -> load -> chunk -> embed -> Qdrant -> mark "active"
```

### Why each choice
- **JWT + JWKS**: any API replica verifies tokens locally; no session store, so it scales horizontally.
- **ACL inside the vector query** (`metadata.allowed_roles`): restricted chunks never reach the LLM. The LLM is not a security boundary.
- **Identity injected via `RunnableConfig`**: tools take no `user_id` argument, so prompt injection cannot target another employee.
- **Ingestion in Celery**: uploads return `202` instantly; failures are visible in the admin UI. New version is indexed first, old versions are deleted after (zero downtime). Chunk ids are deterministic, so re-ingest is an upsert.
- **Retrieval cache in Redis** keyed by (query, roles, corpus_version). Uploading/deleting a doc bumps `corpus_version`, which invalidates it. Only retrieval is cached, never personal answers.
- **Ollama `num_ctx=4096`**: Ollama's default is 2048 and it silently truncates the prompt, dropping your retrieved context.
- **SSE over `fetch`**: `EventSource` cannot send an `Authorization` header.
- **Tokens in memory only** (keycloak-js): not in localStorage.

## Layout

```
backend/app/
  auth.py            JWT verify, role hierarchy, require_role
  api/chat.py        SSE chat endpoint (the core request path)
  api/conversations.py  history + feedback (ownership-checked)
  api/admin.py       policy upload/list/delete (hr only)
  agent/             prompt, LangGraph agent, tools
  rag/               vectorstore, ingest, retriever (ACL filter + cache)
  services/          guardrails/PII redaction, rate limit, HRMS client, audit, redis
  worker.py          Celery ingestion task
backend/migrations/  Alembic
backend/eval/        golden set + retrieval metrics + ACL leak test
backend/tests/       unit tests (auth, roles, guardrails)
frontend/src/        Chat, Admin, auth, SSE client
infra/keycloak/      realm with roles + test users
```

## Evaluate (this backs your "60% fewer tickets" claim)

```bash
make eval      # hit@k, MRR, and ACL leaks (must be 0)
make test
```
Grow `backend/eval/golden.jsonl` to 100+ real questions. Re-run after any change to chunk size,
embedding model, `k`, or `retrieval_min_score`. For the business metric, compute
deflection = conversations with no ticket / total conversations from `audit_logs` + tickets,
against the pre-launch ticket baseline.

## What you MUST change before real production

| Area | Dev default | Production |
|---|---|---|
| Secrets | `.env` in git-ignored file | Vault / cloud secret manager / K8s Secrets |
| Keycloak | `start-dev`, H2 DB, admin/admin, HTTP | Prod mode + Postgres, TLS, or your corporate IdP (Azure AD / Okta); set `ENV=prod`, real `OIDC_*` |
| TLS | none | Terminate at ingress/load balancer; HSTS |
| Postgres / Redis / Qdrant | single containers | Managed or HA (replicas, backups, PITR); Qdrant cluster/sharding |
| LLM serving | Ollama, one box | vLLM/TGI on GPU nodes with batching; keep Ollama for dev. LangChain makes this a config change |
| Migrations | run at container start | Run `alembic upgrade head` as a one-off K8s Job, then autogenerate new revisions |
| HRMS | `MockHRMS` | `HRMS_BASE_URL` + service credentials; keep the HRMS enforcing "own record only" too |
| Employee id | JWT `preferred_username` | Map a real `employee_id` claim in the IdP |
| Dependencies | version ranges | Lockfile (`pip-compile` / `npm ci`), image scanning, SBOM |
| Observability | JSON logs + `/metrics` | Prometheus + Grafana alerts, OpenTelemetry traces, Langfuse for LLM traces; ship logs centrally |
| Deployment | Docker Compose | Kubernetes: Deployments (`api`, `worker`, `vllm`), HPA on CPU/latency, readiness = `/readyz`, liveness = `/healthz`, PodDisruptionBudgets, NetworkPolicies (only `api` may reach HRMS/DBs) |
| Retrieval quality | vector only | Add hybrid search (BM25 + vectors) and a reranker (e.g. bge-reranker) once the golden set shows misses |
| Data governance | audit table | Retention policy for chats/audit, right-to-erasure flow, DPIA if required in your jurisdiction |
| Prompt injection | regex guardrail + tool design | Red-team test set, output checks, keep tools least-privilege |

## Known limitations
- Agent routing on 7-8B local models is imperfect. If it misroutes, try `qwen2.5:14b`, or add a classify-then-route node before the agent.
- Retrieval cache hit rate is modest, because the LLM rewrites the query. Add a semantic cache if you see heavy repetition.
- Fixed-window rate limiting allows bursts at window edges; swap for a token bucket if that matters.
- Scanned PDFs need OCR before ingestion (the worker reports "no extractable text").
- Not load-tested. Measure LLM concurrency first; it is the bottleneck.
