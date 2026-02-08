# HLD (High-Level Design)

## 1. Architecture Overview

### System Purpose

The system discovers enterprise developer-tool opportunities by collecting ecosystem pain signals, scoring them deterministically, and synthesizing findings into analyst-ready outputs.

### Scope

Included:
- Multi-source signal ingestion
- Deterministic scoring and filtering
- Historical persistence and run tracking
- Digest/opportunity synthesis and read-only serving

Excluded:
- Transactional product workflows
- Autonomous remediation/execution
- Real-time distributed event processing

### High-Level Data Flow

```text
Sources -> Ingest -> Normalize -> Score -> Persist -> Serve
```

### Container View

```mermaid
flowchart LR
    subgraph SOURCES["Sources"]
        S1["GitHub"]
        S2["Hacker News"]
        S3["RSS"]
        S4["NVD"]
    end

    subgraph CORE["Core Pipeline"]
        C1["Collectors"]
        C2["Normalization"]
        C3["Deterministic Scoring"]
        C4["Persistence"]
    end

    subgraph SYNTH["Interpretation Layer"]
        L1["LLM Provider Interface"]
        L2["Digest and Opportunity Synthesis"]
    end

    subgraph ACCESS["Access Layer"]
        A1["CLI"]
        A2["Flask API"]
        A3["React UI"]
    end

    DB[("SQLite")]

    S1 --> C1
    S2 --> C1
    S3 --> C1
    S4 --> C1
    C1 --> C2 --> C3 --> C4 --> DB
    DB --> L2
    L2 --> DB
    L1 --> L2
    DB --> A1
    DB --> A2 --> A3
```

### Sync vs Async Boundaries

- Sync: collection, scoring, persistence, synthesis requests
- Async: none in core architecture

### Stateless vs Stateful

- Stateless: scoring logic, prompt templates, rendering adapters
- Stateful: SQLite, collector state, digest history, opportunity runs

### Deployment Boundaries

- Batch execution boundary (`main.py` commands)
- Serving boundary (Flask API + static frontend)
- Storage boundary (single local DB)

### Workflow Boundary View

```mermaid
flowchart TD
    B1["Batch Commands"] --> P1["collect run digest weekly opportunities"]
    B2["Serve Command"] --> P2["read only API and UI"]

    P1 --> W1["State writes enabled"]
    P2 --> W2["State writes disabled"]
```

## 2. Domain Model and Core Concepts

### Signal Taxonomy

- High-signal: technical instability and substantive engineering changes (breakage, outages, security incidents)
- Enterprise-signal: repeatable, budget-backed pain (compliance friction, DevOps toil, platform engineering gaps)
- Low-signal: hype, self-promotion, generic opinion with low operational consequence

### Taxonomy Diagram

```mermaid
mindmap
  root((Signal))
    High signal
      Breaking changes
      Outages and incidents
      CVEs and security regressions
    Enterprise signal
      Compliance toil
      CI CD friction
      Platform engineering pain
      Observability gaps
    Low signal
      Marketing hype
      Generic opinion
      Hiring and self promotion
```

### Definitions and Invariants

- `Item`: normalized collected artifact with source identity, content, metadata, and score
- `Digest`: human-readable summary of a time window
- `Opportunity`: structured inferred opportunity with confidence and supporting evidence
- `EvidenceRef`: linkable supporting artifact for an opportunity claim

Invariants:
- Item identity must be stable across reruns (source + source_id hash)
- Scoring output range is bounded and deterministic
- Structured opportunities must retain traceability to evidence records

### Scoring Philosophy

What is measured:
- Concrete pain language
- Severity and recurrence indicators
- Engagement proxies (comments, reactions, upvotes, CVSS)

What is intentionally ignored:
- Marketing narratives without technical consequence
- Surface-level popularity absent operational pain
- LLM-generated reinterpretation of upstream raw data at filtering stage

Stability guarantees:
- Same input item text and metadata produce the same score under same scoring rules
- Deterministic filtering thresholding yields repeatable inclusion/exclusion behavior
- Any scoring drift is explicit and version-controlled via rules changes

### Scoring Decision Diagram

```mermaid
flowchart TD
    I["Normalized Item"] --> P["Pattern and Engagement Rules"]
    P --> R["Raw Score"]
    R --> C["Clamp to 0 to 100"]
    C --> T{"Above threshold"}
    T -- "yes" --> K["Persist and expose"]
    T -- "no" --> D["Discard as noise"]
```
