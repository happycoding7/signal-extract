# Signal Extract Documentation

This site documents the system in Architecture, HLD, and LLD format for maintainers.

## Read First

- [Architecture](./architecture.md)
- [HLD](./hld.md)
- [LLD](./lld.md)

## Suggested `docs/` Structure

```text
docs/
  index.md            # Entry point and navigation
  architecture.md     # Cross-cutting architecture decisions and operational reality
  hld.md              # System intent, boundaries, domain model, high-level flow
  lld.md              # Component contracts, data architecture, repository map
  _config.yml         # GitHub Pages / Jekyll config
```

## Scope of This Documentation

This documentation intentionally excludes setup, CI/CD, and deployment playbooks.
It focuses on architecture intent, design boundaries, and maintainability constraints.
