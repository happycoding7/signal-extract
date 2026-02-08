# signal-extract

Enterprise developer tool opportunity discovery via signal extraction.

Monitors developer and operations pain points across the tech ecosystem and
surfaces actionable ideas for enterprise dev-tool SaaS products — security,
compliance, infrastructure, DevOps, testing, observability, platform engineering.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests feedparser anthropic openai python-dotenv flask

# Configure
cp .env.example .env
# Edit .env — set OPENROUTER_API_KEY at minimum

# Collect signals
python main.py collect

# Daily opportunity scan
python main.py digest

# Deep opportunity report
python main.py opportunities

# Ask a question
python main.py ask "What compliance automation pain exists?"

# Weekly synthesis
python main.py weekly

# Web UI
python main.py serve
# Open http://localhost:5002
```

## Architecture

Batch pipeline. No web server in the collection path. No background workers.

```
Sources (GitHub Issues/Releases, Discussions, HN, RSS, NVD/CVE)
    |
    v
Collectors ──────── deterministic, incremental, idempotent
    |
    v
Filters ─────────── deterministic scoring, dedup (NO LLM)
    |
    v
SQLite ──────────── append-only, WAL mode
    |
    v
Synthesizer ─────── LLM (provider-neutral)
    |
    v
Delivery ────────── CLI stdout / email / web UI
```

## Commands

| Command | What it does | Use Case | LLM |
|---|---|---|---|
| `python main.py collect` | Fetch from GitHub Issues/Releases, Discussions, HN (top + keyword search), RSS, NVD/CVE. Score deterministically. Store in SQLite. | Run every few hours via cron to accumulate fresh pain signals | No |
| `python main.py digest` | Generate daily opportunity scan — 1-5 bullets identifying enterprise dev-tool pain | Morning check: "Any new enterprise opportunities today?" | Yes |
| `python main.py weekly` | Ranked weekly synthesis — top opportunities with effort estimates, target buyers, market type | Sunday/Monday planning: "What's worth building this week?" | Yes |
| `python main.py opportunities` | Deep 14-day opportunity report — validated opportunities with pain evidence, solution shape, competition, monetization, moat | Decision time: "Should I build this or skip it?" | Yes |
| `python main.py ask "question"` | Q&A over stored data — assesses pain severity, audience size, existing solutions, build complexity | Ad-hoc research: "What compliance automation pain exists?" | Yes |
| `python main.py run` | Collect + digest in one shot | Cron shortcut: single command for scheduled runs | Collect=No, Digest=Yes |
| `python main.py stats` | Show total items stored, broken down by source | Debug/verify: "Is the pipeline collecting data?" | No |
| `python main.py opportunities-json` | Structured JSON opportunity report (machine-readable) | Automation/integration: pipe into dashboards, alerts, or CI | Yes |
| `python main.py serve` | Start web UI server (Flask + React) | Browse run history, items, opportunities in a browser | No |

## Web UI

```bash
python main.py serve              # Start API + serve built frontend
cd web && npm run dev             # Development mode with hot reload (needs Flask running too)
cd web && npm run build           # Build for production
```

The API server (Flask) provides read-only access to the SQLite database.
The React app (Vite) builds to `web/dist/` which Flask serves in production.

API endpoints:
- `GET /api/digests` — list all digests (filterable by type)
- `GET /api/digests/:id` — get a specific digest
- `GET /api/items` — list items (filterable by source, score, date)
- `GET /api/stats` — collection statistics
- `GET /api/opportunities` — list structured opportunities (filterable by min_confidence, buyer, market_type, since)
- `GET /api/opportunities/:id` — get latest version of an opportunity by slug
- `GET /api/opportunities/trends` — confidence trends across runs per opportunity

## LLM provider neutrality

All LLM calls go through one interface:

```python
class LLMProvider(ABC):
    def complete(self, system_prompt, user_prompt, temperature, max_tokens) -> LLMResponse: ...
    def name(self) -> str: ...
```

Provider selected at runtime via `SIGNAL_LLM_PROVIDER`:
- `openrouter` (default) — any model via OpenRouter
- `claude` — Anthropic direct
- `openai` — OpenAI direct

Adding a new provider = one file implementing `LLMProvider` + one line in `factory.py`.

## Sources

### GitHub repos watched (34 — issues + releases via REST API)

| Category | Repos |
|---|---|
| GitHub infra | `actions/runner`, `actions/runner-images`, `cli/cli`, `github/codeql` |
| CI/CD tools | `dependabot/dependabot-core`, `nektos/act` |
| Popular actions | `actions/checkout`, `actions/cache`, `actions/setup-node`, `actions/setup-python`, `docker/build-push-action` |
| Code review | `reviewdog/reviewdog`, `danger/danger-js`, `hmarr/auto-approve-action` |
| Security & compliance | `step-security/harden-runner`, `aquasecurity/trivy-action`, `ossf/scorecard-action`, `bridgecrewio/checkov`, `aquasecurity/trivy`, `anchore/grype`, `anchore/syft`, `sigstore/cosign`, `falcosecurity/falco`, `open-policy-agent/opa`, `open-policy-agent/gatekeeper` |
| Infrastructure & DevOps | `hashicorp/terraform`, `hashicorp/vault`, `pulumi/pulumi`, `argoproj/argo-cd`, `fluxcd/flux2` |
| Observability | `grafana/grafana`, `prometheus/prometheus` |
| Platform engineering | `backstage/backstage`, `crossplane/crossplane` |

### GitHub Discussions (GraphQL, requires GITHUB_TOKEN)

- `community/community` — where devs post "I wish GitHub had X" and upvote unmet needs
- `actions/runner` — Actions-specific feature requests
- `hashicorp/terraform` — Terraform pain and feature requests
- `backstage/backstage` — Platform engineering discussions

### RSS feeds (27)

- **Platform blogs**: GitHub, DevOps.com, ThoughtWorks, Pragmatic Engineer, Martin Fowler, Docker
- **Cloud provider blogs**: AWS Security, AWS DevOps, Google Cloud, Azure
- **Dev community**: dev.to (security, devops, kubernetes), InfoQ
- **Stack Overflow**: devsecops, kubernetes-security, terraform, ci-cd, github-actions
- **Reddit**: r/github, r/devops, r/githubactions, r/netsec, r/sysadmin, r/kubernetes, r/Terraform, r/devsecops

### Hacker News

- Top stories above score threshold (default 100)
- 29 keyword searches via Algolia API: `github actions`, `github marketplace`, `github app`, `code review automation`, `CI/CD pipeline`, `developer experience`, `devtools`, `github workflow`, `pull request review`, `dependency management`, `github bot`, `CODEOWNERS`, `SOC2 compliance`, `security audit automation`, `vulnerability management`, `SBOM`, `infrastructure as code`, `terraform drift`, `kubernetes security`, `secrets management`, `platform engineering`, `developer portal`, `DORA metrics`, `incident management`, `DevSecOps`, `software supply chain security`, `flaky tests`, `cloud cost optimization`, `policy as code`

### NVD/CVE (National Vulnerability Database)

- High/critical severity CVEs via NVD API v2.0
- CVSS threshold configurable (default 7.0)
- No API key required (optional for higher rate limits)

## File structure

```
signal-extract/
├── main.py                        # CLI entry point
├── models.py                      # Item, Digest, Opportunity, EvidenceRef, QAResult, Source enum
├── config/
│   └── settings.py                # Config from env vars + .env auto-load
├── collectors/
│   ├── base.py                    # Collector interface
│   ├── github.py                  # GitHub releases + issues (REST)
│   ├── github_discussions.py      # GitHub Discussions (GraphQL)
│   ├── hackernews.py              # HN top stories + Algolia keyword search
│   ├── rss.py                     # RSS/Atom feeds
│   └── nvd.py                     # NVD/CVE vulnerability database
├── filters/
│   └── scorer.py                  # Deterministic signal scoring (~150 enterprise patterns)
├── llm/
│   ├── provider.py                # LLMProvider interface
│   ├── claude_provider.py         # Anthropic implementation
│   ├── openai_provider.py         # OpenAI implementation
│   ├── openrouter_provider.py     # OpenRouter implementation
│   └── factory.py                 # Runtime provider selection
├── synthesizer/
│   ├── prompts.py                 # All LLM prompts (daily, weekly, Q&A, opportunity, structured-json)
│   └── engine.py                  # Digest, synthesis, opportunity + structured JSON report generation
├── qa/
│   └── handler.py                 # Q&A over stored data
├── delivery/
│   └── output.py                  # CLI and email delivery
├── api/
│   └── server.py                  # Flask API server (read-only)
├── storage/
│   └── db.py                      # SQLite storage
├── web/                           # React frontend (Vite)
│   ├── src/
│   │   ├── App.jsx                # Root component
│   │   ├── api.js                 # API client
│   │   └── components/            # DigestList, DigestDetail, ItemsTable, OpportunitiesView, etc.
│   └── dist/                      # Built frontend (gitignored)
├── tests/
│   └── test_opportunities.py      # JSON parsing, DB ops, API validation tests
└── data/
    └── signal.db                  # Auto-created SQLite database
```

## Structured Opportunity Intelligence

The `opportunities-json` command generates machine-readable opportunity data:

```bash
# Print to stdout
python main.py opportunities-json

# Save to file
python main.py opportunities-json --out data/opportunities.json
```

Each opportunity includes:
- **id**: Stable kebab-case slug for tracking across runs
- **confidence**: 0-100 score (80+ = strong evidence, 50-79 = moderate, <50 = emerging)
- **evidence**: Array of references back to collected items with source URLs
- **target_buyer**: Who writes the check (DevOps lead / CISO / VP Eng / etc.)
- **effort_estimate**: weekend | 1-2 weeks | month+

Opportunities are persisted in SQLite with full history, enabling confidence trending
across multiple runs. The web UI "Opportunities" tab shows cards with filters,
trend direction, and drill-down to evidence.

## Signal scoring

Items are scored 0-100 by deterministic pattern matching. No ML, no LLM.

Three pattern lists:

**High-signal patterns** (generic technical signals):
- Breaking changes, deprecations, end-of-life
- Rollbacks, post-mortems, outage reports
- Rewrites, rearchitectures, security vulnerabilities (CVEs)

**Enterprise-signal patterns** (~150 patterns):
- Security & vulnerability: CVE refs, zero-day, patch management, security audit, threat detection
- Compliance & audit: SOC2, ISO 27001, HIPAA, GDPR, FedRAMP, PCI-DSS, policy-as-code, audit trails
- Infrastructure & DevOps: Terraform drift, IaC, Kubernetes pain, Helm, configuration drift, cloud costs
- Observability: alert fatigue, on-call pain, incident management, SLO/SLI, MTTR
- Secrets management: secret rotation, credential leaks, vault pain
- Supply chain: SBOM, dependency confusion, package provenance, SLSA, SCA
- Access control: privilege escalation, IAM complexity, RBAC, least privilege
- Testing & code quality: flaky tests, SAST, DAST, static analysis, code coverage enforcement
- Developer productivity: platform engineering, developer portal, DORA metrics, golden paths
- CI/CD friction: Actions slow/flaky/broken, cache misses, runner issues
- Code review pain: PR bottlenecks, review fatigue, merge queues, CODEOWNERS
- Integration gaps, DevEx complaints, monorepo pain, notification noise

**Low-signal patterns** (noise):
- Marketing language, engagement bait, generic opinion
- Hiring posts, self-promotion, testimonials, tutorials

Items scoring below the threshold (default 40) are discarded entirely.

## Cron setup

```cron
# Collect every 4 hours
0 */4 * * * cd /path/to/signal-extract && .venv/bin/python main.py collect

# Daily enterprise opportunity scan at 8am
0 8 * * * cd /path/to/signal-extract && .venv/bin/python main.py digest

# Weekly enterprise synthesis on Monday at 9am
0 9 * * 1 cd /path/to/signal-extract && .venv/bin/python main.py weekly

# Deep enterprise opportunity report every other Friday at 9am
0 9 1-7,15-21 * 5 cd /path/to/signal-extract && .venv/bin/python main.py opportunities
```

## Cost

~6 cents/month on `google/gemini-2.5-flash` via OpenRouter.

| Model | Daily cost | Monthly cost |
|---|---|---|
| `google/gemini-2.5-flash` | ~$0.002 | ~$0.06 |
| `deepseek/deepseek-chat-v3-0324` | ~$0.007 | ~$0.20 |
| `anthropic/claude-sonnet-4` | ~$0.04 | ~$1.30 |

## Tradeoffs

### Made deliberately

1. **Python over TypeScript**: Better library support for RSS, HTTP, SQLite. No build step.
2. **SQLite over Postgres**: One file. Backups = copy one file. Years of headroom.
3. **Sequential collectors over async**: ~15 seconds total. Async adds complexity for nothing.
4. **Regex scoring over ML/LLM filtering**: Deterministic, fast, free, inspectable. Edit `filters/scorer.py` to tune.
5. **Flask over FastAPI**: Synchronous matches the pipeline. One dependency vs four.
6. **Cron over long-running process**: No daemon, no crash recovery, no memory leaks.
7. **Reddit via RSS, not Reddit API**: Gets titles and previews. No OAuth registration needed.
8. **No CSS framework**: Plain CSS keeps the frontend simple and dependency-free.

### Known limitations

1. **HN link posts score low**: Most are links with no body text. Algolia keyword search compensates.
2. **No comment analysis**: Comments often contain signal, but fetching multiplies API calls 10-100x.
3. **GitHub rate limits**: Without a token, 60 requests/hour. With a token, 5000/hour. Token recommended for 34 repos.
4. **Discussions collector requires GITHUB_TOKEN**: GraphQL API needs authentication.
5. **No semantic dedup**: Dedup by source+ID hash. LLM synthesis handles cross-source overlap naturally.
6. **NVD rate limits**: 5 requests/30 seconds without API key. Sufficient for periodic collection.
