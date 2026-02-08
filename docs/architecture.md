# Architecture

## System Purpose and Scope

Signal Extract is a local-first pipeline that converts external engineering signals into actionable enterprise dev-tool opportunities.

It is optimized for:
- Deterministic collection and scoring of raw signals
- Persistent historical evidence in SQLite
- LLM-assisted synthesis at the boundary where interpretation is required
- Read-only consumption through CLI, API, and web UI

## Explicit Non-Goals

- Real-time stream processing
- Multi-tenant SaaS runtime
- Autonomous decisioning or auto-execution from LLM output
- End-to-end workflow orchestration beyond scheduled batch runs

## High-Level Flow

```text
Sources -> Ingest -> Normalize -> Score -> Persist -> Serve
```

Where:
- `Sources`: GitHub (issues/releases/discussions), Hacker News (top + keyword search), RSS, NVD/CVE
- `Ingest`: Pull-based collectors with external API interaction
- `Normalize`: Canonical `Item` shape with source metadata
- `Score`: Deterministic regex/heuristics, no LLM
- `Persist`: SQLite with append-oriented history and run tracking
- `Serve`: CLI outputs, read-only Flask API, React UI

## Sync vs Async Boundaries

- Collection and scoring are synchronous per run.
- Collectors are executed sequentially by design.
- API serving is request/response synchronous with read-only DB access.
- There is no asynchronous queue or worker subsystem.

Implication: latency is bounded by external API calls; operational model stays simple.

## Stateless vs Stateful Components

Stateless:
- Scoring engine logic (pure function on item content)
- Prompt templates
- API response shaping

Stateful:
- SQLite tables (`items`, `collector_state`, `digests`, opportunity tables)
- Collector checkpoints (incremental collection cursors/seen sets)
- Historical run records for trend analysis

## Deployment Boundaries (Logical)

- Batch boundary: `main.py` commands (`collect`, `digest`, `weekly`, `opportunities`, `opportunities-json`)
- Serving boundary: `main.py serve` starts read-only API and optional static UI
- Data boundary: local SQLite file is the system of record

No runtime coupling requires collectors to be online while serving historical data.

## Trust, Security, and Compliance Boundaries

### Trust Zones

- External zone: third-party APIs (GitHub, HN, RSS endpoints, NVD)
- Processing zone: local runtime, scoring, synthesis
- Storage zone: local SQLite DB containing collected text and derived opportunities
- Presentation zone: local web UI + API consumers

### Data Ownership

- Raw and derived data are owned by the local deployment context.
- No mandatory external telemetry sink exists in core architecture.

### Secrets Handling Assumptions

- API and SMTP credentials are injected via environment variables.
- Secrets are not persisted in SQLite by intended design.
- Token exposure risk is concentrated in local environment and process execution context.

### Compliance Touchpoints

The system is not a compliance product itself but processes compliance-related signals. Future SOC2/ISO alignment depends on operational controls around:
- Secret management
- Access control to host and DB
- Auditability of scheduled runs and output artifacts

## Failure Modes and Operational Reality

### What Fails First Under Load

- Upstream APIs (rate limiting, transient failures)
- Collection latency (long-tail network/API response time)
- LLM reliability and response-shape validity for structured reports

### Silent Failure Risks

- Low-signal filtering can suppress meaningful but weakly worded signals
- Source drift can reduce quality without obvious runtime errors
- Prompt regressions can reduce output quality while still returning syntactically valid text

### Backpressure Points

- Sequential collector loop
- LLM token budget at synthesis stage
- UI/API queries over large historical datasets without aggressive indexing/caching

### Human-in-the-Loop Requirements

- Periodic review of scoring patterns and thresholds
- Curating source lists and search keywords
- Reviewing structured opportunities before downstream action

## Cost and Scaling Model

### Primary Cost Drivers

- LLM inference for digest/synthesis/opportunity generation
- External API rate limits requiring authenticated usage for scale
- Storage growth from retained historical text and evidence

### Linear Scaling Surfaces

- Number of source endpoints/repositories
- Number of items collected per run
- Number of opportunities/evidence rows per structured report

### Non-Linear Scaling Surfaces

- Prompt token growth with broad item windows
- Query complexity for trend/evidence joins over long time windows
- Noise growth when source breadth outpaces scoring precision

### Known Cost Cliffs

- Moving to larger LLM models without tighter prompt windows
- Expanding source catalog without per-source quality controls
- Serving heavy analytical queries directly from a single SQLite file at high concurrency

## Rebuild Test

### Must Be Rebuilt the Same Way

- Deterministic boundary: ingestion/normalization/scoring must remain non-LLM
- Source checkpointing and idempotent persistence behavior
- Opportunity evidence traceability back to raw collected items
- Provider abstraction boundary for LLM calls

### Safe to Redesign

- Web UI layout and interaction model
- API response envelopes (if backward compatibility is managed)
- Prompt wording, as long as output contracts remain explicit

### Compatibility Breakers

- Changing `Source` semantics without migration mapping
- Removing run/evidence linkage for opportunities
- Altering collector state keys without fallback migration

## Notes for Future Maintainers

- Sequential execution is intentional, not accidental complexity avoidance.
- Regex scoring is an explicit product decision to preserve inspectability and determinism.
- LLM output is downstream interpretation, never upstream filtering authority.
- SQLite is a deliberate portability tradeoff; do not optimize away simplicity without operational evidence.
- Structured opportunity JSON reliability should always be treated as partial-trust and validated.
