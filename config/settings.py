"""
Configuration. All settings from env vars or a single config file.
No YAML. No TOML parsing. Just a Python dict you edit.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Auto-load .env file so you don't need `export $(grep ...)` every time
from dotenv import load_dotenv
load_dotenv()


@dataclass
class Config:
    # LLM provider: "claude" | "openai" | "openrouter"
    llm_provider: str = os.environ.get("SIGNAL_LLM_PROVIDER", "openrouter")

    # API keys — read from env only, never stored
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")

    # Models
    anthropic_model: str = os.environ.get("SIGNAL_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    openai_model: str = os.environ.get("SIGNAL_OPENAI_MODEL", "gpt-4o")
    openrouter_model: str = os.environ.get("SIGNAL_OPENROUTER_MODEL", "anthropic/claude-sonnet-4")

    # Storage
    db_path: Path = Path(os.environ.get("SIGNAL_DB_PATH", "data/signal.db"))

    # Email delivery (optional)
    smtp_host: str = os.environ.get("SIGNAL_SMTP_HOST", "")
    smtp_port: int = int(os.environ.get("SIGNAL_SMTP_PORT", "587"))
    smtp_user: str = os.environ.get("SIGNAL_SMTP_USER", "")
    smtp_pass: str = os.environ.get("SIGNAL_SMTP_PASS", "")
    email_to: str = os.environ.get("SIGNAL_EMAIL_TO", "")
    email_from: str = os.environ.get("SIGNAL_EMAIL_FROM", "signal-extract@localhost")

    # Filter threshold (0-100). Items below this score are discarded.
    score_threshold: int = int(os.environ.get("SIGNAL_SCORE_THRESHOLD", "40"))

    # ── GitHub repos to watch (issues + releases) ──
    # Enterprise dev-tool ecosystem: CI/CD, security, infrastructure, observability
    github_repos: list[str] = field(default_factory=lambda: [
        # GitHub's own infra — where workflow pain is filed directly
        "actions/runner",
        "actions/runner-images",
        "cli/cli",
        "github/codeql",
        # CI/CD tools with heavy GitHub integration
        "dependabot/dependabot-core",
        "nektos/act",
        # Popular actions where friction surfaces as issues
        "actions/checkout",
        "actions/cache",
        "actions/setup-node",
        "actions/setup-python",
        "docker/build-push-action",
        # Code review and PR automation tooling
        "reviewdog/reviewdog",
        "danger/danger-js",
        "hmarr/auto-approve-action",
        # Security and compliance tools
        "step-security/harden-runner",
        "aquasecurity/trivy-action",
        "ossf/scorecard-action",
        # ── Enterprise security & compliance ──
        "bridgecrewio/checkov",
        "aquasecurity/trivy",
        "anchore/grype",
        "anchore/syft",
        "sigstore/cosign",
        "falcosecurity/falco",
        "open-policy-agent/opa",
        "open-policy-agent/gatekeeper",
        # ── Infrastructure & DevOps ──
        "hashicorp/terraform",
        "hashicorp/vault",
        "pulumi/pulumi",
        "argoproj/argo-cd",
        "fluxcd/flux2",
        # ── Observability ──
        "grafana/grafana",
        "prometheus/prometheus",
        # ── Platform engineering ──
        "backstage/backstage",
        "crossplane/crossplane",
    ])

    # GitHub token — required for Discussions collector, recommended for rate limits
    github_token: str = os.environ.get("GITHUB_TOKEN", "")

    # ── GitHub Discussions repos (GraphQL, requires GITHUB_TOKEN) ──
    github_discussions_repos: list[str] = field(default_factory=lambda: [
        "community/community",
        "actions/runner",
        "hashicorp/terraform",
        "backstage/backstage",
    ])

    # ── RSS feeds — enterprise dev-tool, security, infrastructure, cloud blogs ──
    rss_feeds: list[str] = field(default_factory=lambda: [
        # Developer platform blogs
        "https://github.blog/feed/",
        "https://devops.com/feed/",
        "https://www.thoughtworks.com/rss/insights.xml",
        "https://blog.pragmaticengineer.com/rss/",
        "https://martinfowler.com/feed.atom",
        "https://www.docker.com/blog/feed/",
        # Reddit subreddits via RSS (no auth needed)
        "https://www.reddit.com/r/github/.rss",
        "https://www.reddit.com/r/devops/.rss",
        "https://www.reddit.com/r/githubactions/.rss",
        # ── Enterprise-focused subreddits ──
        "https://www.reddit.com/r/netsec/.rss",
        "https://www.reddit.com/r/sysadmin/.rss",
        "https://www.reddit.com/r/kubernetes/.rss",
        "https://www.reddit.com/r/Terraform/.rss",
        "https://www.reddit.com/r/devsecops/.rss",
        # ── Cloud provider blogs ──
        "https://aws.amazon.com/blogs/security/feed/",
        "https://aws.amazon.com/blogs/devops/feed/",
        "https://cloud.google.com/feeds/blog.xml",
        "https://azure.microsoft.com/en-us/blog/feed/",
        # ── Dev community ──
        "https://dev.to/feed/tag/security",
        "https://dev.to/feed/tag/devops",
        "https://dev.to/feed/tag/kubernetes",
        "https://www.infoq.com/feed/",
        # ── Stack Overflow via RSS (tag-based) ──
        "https://stackoverflow.com/feeds/tag/devsecops",
        "https://stackoverflow.com/feeds/tag/kubernetes-security",
        "https://stackoverflow.com/feeds/tag/terraform",
        "https://stackoverflow.com/feeds/tag/ci-cd",
        "https://stackoverflow.com/feeds/tag/github-actions",
    ])

    # ── HN settings ──
    hn_min_score: int = int(os.environ.get("SIGNAL_HN_MIN_SCORE", "100"))
    hn_max_items: int = int(os.environ.get("SIGNAL_HN_MAX_ITEMS", "30"))

    # HN keyword search — targeted queries via Algolia API
    hn_search_keywords: list[str] = field(default_factory=lambda: [
        # Existing — still relevant
        "github actions",
        "github marketplace",
        "github app",
        "code review automation",
        "CI/CD pipeline",
        "developer experience",
        "devtools",
        "github workflow",
        "pull request review",
        "dependency management",
        "github bot",
        "CODEOWNERS",
        # ── Enterprise / boring opportunity keywords ──
        "SOC2 compliance",
        "security audit automation",
        "vulnerability management",
        "SBOM software bill of materials",
        "infrastructure as code",
        "terraform drift",
        "kubernetes security",
        "secrets management",
        "platform engineering",
        "developer portal",
        "DORA metrics",
        "incident management",
        "DevSecOps",
        "software supply chain security",
        "flaky tests",
        "cloud cost optimization",
        "policy as code",
    ])
    hn_search_min_score: int = int(os.environ.get("SIGNAL_HN_SEARCH_MIN_SCORE", "50"))

    # ── NVD / CVE settings ──
    nvd_api_key: str = os.environ.get("NVD_API_KEY", "")
    nvd_min_cvss: float = float(os.environ.get("SIGNAL_NVD_MIN_CVSS", "7.0"))
    nvd_max_results: int = int(os.environ.get("SIGNAL_NVD_MAX_RESULTS", "20"))


def load_config() -> Config:
    return Config()
