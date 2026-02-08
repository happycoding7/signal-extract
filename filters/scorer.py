"""
Deterministic signal scoring for enterprise developer tool opportunity discovery.
No LLM. No ML. Just pattern matching and heuristics.

Three pattern lists:
- HIGH_SIGNAL_PATTERNS: generic technical signals (breaking changes, failures, etc.)
- ENTERPRISE_SIGNAL_PATTERNS: developer/ops pain that could be an enterprise tool opportunity
- LOW_SIGNAL_PATTERNS: noise to penalize (marketing, hype, self-promotion)

Score range: 0-100. Items below the configured threshold are discarded.
"""

import re
from models import Item, Source


# --- Generic high-signal patterns ---
# Breaking changes, outages, etc. indicate ecosystem churn — useful
# context for enterprise tool decisions.

HIGH_SIGNAL_PATTERNS: list[tuple[str, int]] = [
    # Breaking changes and migrations
    (r"\bbreaking\s+change", 25),
    (r"\bdeprecate[ds]?\b", 20),
    (r"\bmigrat(e|ion|ing)\b", 15),
    (r"\bremov(e[ds]?|ing)\b.{0,30}\b(api|support|feature)", 15),
    (r"\bend[- ]?of[- ]?life\b", 20),

    # Failures and rollbacks
    (r"\broll(ed)?\s*back\b", 25),
    (r"\breverted?\b", 20),
    (r"\bpost[- ]?mortem\b", 30),
    (r"\bincident\s+(report|review)\b", 25),
    (r"\boutage\b", 20),
    (r"\bfail(ed|ure|ing)\b", 10),
    (r"\bregression\b", 15),

    # Rewrites and major changes
    (r"\brewrit(e|ten|ing)\b", 15),
    (r"\brearchitect", 15),
    (r"\bfrom\s+scratch\b", 10),
    (r"\bmajor\s+(version|release|update)\b", 10),
    (r"\bv\d+\.0\.0\b", 10),

    # Pain signals
    (r"\bfrustrat(ed|ing|ion)\b", 10),
    (r"\bworkaround\b", 10),
    (r"\bbug\b.*\b(critical|severe|major)\b", 15),
    (r"\bsecurity\s+(vulnerabilit|advis|patch|fix)", 20),
    (r"\bCVE-\d{4}", 20),

    # Performance and scaling
    (r"\bperformance\s+(regression|degradation|issue)", 15),
    (r"\bmemory\s+leak\b", 15),
    (r"\b\d+x\s+(faster|slower)\b", 10),

    # Technical depth signals
    (r"\bbenchmark", 8),
    (r"\barchitecture\s+decision\b", 10),
    (r"\blessons?\s+learned\b", 15),
    (r"\bwhy\s+we\s+(chose|switched|moved|left|abandoned)\b", 15),
]


# --- Enterprise developer tool opportunity patterns ---
# Pain points that represent enterprise SaaS / dev-tool product opportunities.

ENTERPRISE_SIGNAL_PATTERNS: list[tuple[str, int]] = [
    # ── Explicit wish / feature request signals ──
    (r"\bi\s+wish\s+(there\s+was|there\s+were|we\s+had|we\s+could)\b", 15),
    (r"\bi\s+wish\s+\w+\s+had\b", 20),
    (r"\bwhy\s+(doesn't|can't|won't|isn't)\b", 10),
    (r"\bfeature\s+request\b", 15),
    (r"\bwould\s+be\s+(great|nice|helpful|awesome)\s+(if|to)\b", 10),
    (r"\bmissing\s+feature\b", 20),
    (r"\bno\s+(way|option|ability)\s+to\b", 15),
    (r"\bneeds?\s+(a|an|better)\s+(way|option|tool|solution)\b", 15),
    (r"\bcan't\s+believe\s+there's\s+no\b", 25),

    # ── GitHub Actions / CI/CD friction ──
    (r"\b(github\s+)?actions?\s+(is|are)\s+(slow|broken|flaky|unreliable|painful)", 25),
    (r"\bworkflow\s+(is|keeps?)\s+(fail|break|timeout|slow|flaky)", 20),
    (r"\bCI\s+(is|keeps?)\s+(slow|flaky|broken|failing|unreliable)", 20),
    (r"\bpipeline\s+(is|keeps?)\s+(slow|break|fail|flaky)", 15),
    (r"\bactions?\s+(timeout|timed?\s+out)\b", 15),
    (r"\brunner\s+(is|are)\s+(slow|unavailable|down)\b", 15),
    (r"\bself[- ]hosted\s+runner", 10),
    (r"\bworkflow\s+(yaml|yml|syntax|config)\b.*\b(confus|complex|hard|painful)", 15),
    (r"\bcache\s+(miss|invalid|not\s+work|broken|slow)\b", 15),
    (r"\bartifact\s+(upload|download)\s+(slow|fail|broken|limit)\b", 15),

    # ── Repetitive work / automation wishes ──
    (r"\bmanual(ly)?\s+(approv|review|deploy|merge|tag|release|update|bump)", 15),
    (r"\brepetitive\s+(task|step|process|workflow|work)\b", 15),
    (r"\btoil\b", 10),
    (r"\bautomat(e|ion|ically)\b.*\b(wish|should|want|need|could)\b", 15),
    (r"\bbot\s+(that|to|for|which)\s+\w+", 10),

    # ── Code review pain ──
    (r"\bcode\s+review\s+(is|takes?|slow|painful|bottleneck|broken|tedious)", 25),
    (r"\bPR\s+(review|approval)\s+(is|takes?|slow|blocked|bottleneck|waiting)", 25),
    (r"\breview\s+fatigue\b", 20),
    (r"\bstale\s+PR[s]?\b", 15),
    (r"\bmerge\s+(conflict[s]?|queue|hell|nightmare)\b", 15),
    (r"\bcheck[s]?\s+(are|is)\s+(slow|redundant|flaky|failing)\b", 15),
    (r"\bCODEOWNERS\b.*\b(broken|doesn't|wrong|confus|limit|problem|issue|pain)", 20),
    (r"\bCODEOWNERS\b", 10),
    (r"\bauto[- ]?merge\b", 10),
    (r"\bmerge\s+queue\b", 10),

    # ── Security & Vulnerability Management ──
    (r"\bzero[- ]day\b", 25),
    (r"\bcritical\s+vulnerabilit", 25),
    (r"\bransomware\b", 15),
    (r"\bpatch\s+management\b", 20),
    (r"\bsecurity\s+(posture|baseline|hardening)\b", 15),
    (r"\bthreat\s+(model|detection|intelligence)\b", 15),
    (r"\bpenetration\s+test", 10),
    (r"\bsecurity\s+audit\b", 20),
    (r"\bincident\s+response\b", 15),
    (r"\bvulnerability\s+(manage|scan|remediat|priorit)", 15),

    # ── Compliance & Audit ──
    (r"\bSOC\s*2\b", 20),
    (r"\bSOC\s*[12]\s+type\s+[12]\b", 25),
    (r"\bISO\s*27001\b", 20),
    (r"\bHIPAA\b", 20),
    (r"\bGDPR\b", 15),
    (r"\bFedRAMP\b", 20),
    (r"\bPCI[- ]DSS\b", 20),
    (r"\bcompliance\s+(automation|drift|monitoring|report|check|audit|gap|requirement|polic)", 20),
    (r"\baudit\s+(trail|log|evidence|report)\b", 15),
    (r"\bpolicy[- ]as[- ]code\b", 20),
    (r"\bregulatory\s+(compliance|requirement)\b", 15),
    (r"\bcompliance\s+(violation|finding)\b", 20),

    # ── Infrastructure as Code & DevOps ──
    (r"\bterraform\b.*\b(drift|state|pain|broken|slow|issue|problem)\b", 15),
    (r"\bterraform\b", 8),
    (r"\binfrastructure[- ]as[- ]code\b", 10),
    (r"\bIaC\b", 10),
    (r"\bkubernetes\b.*\b(pain|complex|hard|config|security|cost)\b", 15),
    (r"\bk8s\b.*\b(pain|complex|hard|config|security|cost)\b", 15),
    (r"\bhelm\b.*\b(chart|pain|complex|broken)\b", 10),
    (r"\bansible\b.*\b(pain|slow|complex|broken)\b", 10),
    (r"\bconfiguration\s+(drift|management|sprawl)\b", 15),
    (r"\bcloud\s+(cost|spend|waste|optimization|governance)\b", 15),
    (r"\bFinOps\b", 15),
    (r"\bcloud\s+native\b.*\b(security|compliance|governance)\b", 10),

    # ── Observability & Incident Management ──
    (r"\bobservability\b", 10),
    (r"\bmonitoring\s+(gap|blind\s+spot|alert\s+fatigue)\b", 15),
    (r"\balert\s+fatigue\b", 20),
    (r"\bon[- ]call\s+(rotation|burden|fatigue|pain)\b", 15),
    (r"\bincident\s+(management|coordination|retrospective)\b", 15),
    (r"\bSLO\b.*\b(track|monitor|breach|burn)\b", 15),
    (r"\bSLI\b.*\b(defin|measur|track)\b", 10),
    (r"\bmean\s+time\s+to\s+(recover|detect|resolve)\b", 15),
    (r"\bMTTR\b", 10),

    # ── Secrets Management ──
    (r"\bsecret[s]?\s+(leak|expos|rotat|scan|detect|manage)", 20),
    (r"\bsecrets?\s+management\b", 15),
    (r"\bvault\b.*\b(pain|complex|config|issue)\b", 10),
    (r"\bsecret\s+rotation\b", 15),
    (r"\bcredential\s+(leak|rotat|manag|sprawl)\b", 15),
    (r"\bAPI\s+key\s+(rotat|manag|leak|expos)\b", 15),

    # ── Software Supply Chain ──
    (r"\bSBOM\b", 15),
    (r"\bsupply\s+chain\s+(security|attack|risk|integrity)", 20),
    (r"\bdependency\s+(confusion|hijack)\b", 20),
    (r"\bpackage\s+(integrity|provenance|signing)\b", 15),
    (r"\bSLSA\b", 15),
    (r"\bsoftware\s+composition\s+analysis\b", 15),
    (r"\bSCA\b.*\b(tool|scan|result)\b", 10),
    (r"\bdependency\s+(vulnerabilit|audit|scan|update|hell|management)", 20),
    (r"\blicense\s+(compliance|check|scan|violation|audit)", 15),
    (r"\bsecret\s+scanning\b.*\b(miss|false|limit|doesn't|not\s+enough)", 20),
    (r"\bdependabot\b.*\b(slow|noisy|miss|doesn't|broken|limit|annoying)", 20),

    # ── Access Control & Identity ──
    (r"\baccess\s+(control|management|review|governance)\b", 15),
    (r"\bprivilege\s+(escalation|management|creep)\b", 20),
    (r"\bleast\s+privilege\b", 15),
    (r"\bIAM\b.*\b(complex|pain|audit|review)\b", 15),
    (r"\bSSO\b.*\b(integration|pain|issue|broken)\b", 10),
    (r"\bRBAC\b", 10),

    # ── Testing & Code Quality ──
    (r"\bflaky\s+test", 20),
    (r"\btest\s+(coverage|gap|flak|automation|infrastructure)\b", 15),
    (r"\btesting\s+(pain|bottleneck|slow|manual|burden)\b", 15),
    (r"\bcode\s+quality\b.*\b(enforce|automat|gate|check)\b", 15),
    (r"\bstatic\s+analysis\b", 10),
    (r"\bSAST\b", 10),
    (r"\bDAST\b", 10),
    (r"\btechnical\s+debt\b", 10),
    (r"\bcode\s+coverage\b.*\b(enforce|requir|gate|low)\b", 15),

    # ── Developer Productivity & Platform Engineering ──
    (r"\bdeveloper\s+productivity\b", 10),
    (r"\bengineering\s+velocity\b", 10),
    (r"\bdeveloper\s+(platform|portal|self[- ]service)\b", 15),
    (r"\bplatform\s+engineering\b", 15),
    (r"\binternal\s+developer\s+platform\b", 15),
    (r"\bgolden\s+path\b", 10),
    (r"\bdeploy\s+(frequency|lead\s+time|time)\b", 10),
    (r"\bDORA\s+metrics\b", 20),
    (r"\bdeveloper\s+experience\b", 10),
    (r"\bDX\b\s+(is|sucks|poor|bad|terrible|awful|needs)", 20),
    (r"\bonboarding\s+(is|takes?|slow|painful|difficult|hard|complex)", 15),
    (r"\bdev\s+(environment|setup|config)\s+(is|takes?|painful|slow|broken|complex)", 15),

    # ── Integration / tooling gaps ──
    (r"\b(doesn't|don't|can't|no)\s+(integrat|connect|sync|work\s+with)\b", 20),
    (r"\bmissing\s+integration\b", 20),
    (r"\b(jira|linear|notion|slack|teams|discord)\s+(integration|sync|connect|bridge)", 15),
    (r"\bno\s+(native|built[- ]?in)\s+(support|integration|feature)\b", 20),
    (r"\bAPI\s+(limitation|missing|gap|doesn't|insufficient|rate\s+limit)", 15),
    (r"\bwebhook[s]?\s+(missing|unreliable|limitation|delay|broken)", 15),

    # ── Monorepo / scale-related pain ──
    (r"\bmonorepo\b.*\b(pain|slow|problem|issue|hard|scale|limit|doesn't)", 15),
    (r"\bmonorepo\b", 8),
    (r"\bcode\s+own(er|ership)\b.*\b(confus|broken|limit|doesn't|wrong|pain)", 15),
    (r"\blarge\s+(repo|repository|codebase)\b.*\b(slow|pain|problem|scale)", 15),

    # ── Notifications / noise management ──
    (r"\bnotification[s]?\s+(noise|overload|flood|too\s+many|useless|overwhelm)", 20),

    # ── Release / deployment pain ──
    (r"\brelease\s+(process|management|automation)\b.*\b(pain|manual|tedious|complex)", 15),
    (r"\bchangelog\s+(generat|automat|maintain)\b", 10),
    (r"\brelease\s+notes?\b.*\b(manual|automat|generat|tedious)", 10),
]


LOW_SIGNAL_PATTERNS: list[tuple[str, int]] = [
    # Marketing / hype
    (r"\bexcited\s+to\s+announce\b", -15),
    (r"\bgame[- ]?changer\b", -20),
    (r"\brevolution(ary|ize)\b", -15),
    (r"\bunlock\s+(the\s+)?power\b", -15),
    (r"\b10x\s+(developer|engineer|productivity)\b", -20),
    (r"\bsynerg", -20),
    (r"\bdelighted\b", -10),

    # Engagement bait
    (r"\bthis\s+is\s+huge\b", -10),
    (r"\byou\s+won't\s+believe\b", -20),
    (r"\bmind[- ]?blow(n|ing)\b", -15),
    (r"\bhot\s+take\b", -10),

    # Generic opinion
    (r"\bmy\s+thoughts\s+on\b", -5),
    (r"\bunpopular\s+opinion\b", -10),
    (r"\bthread\s*[🧵⬇️↓]\s*$", -10),

    # Hiring/job posts
    (r"\bwe're\s+hiring\b", -15),
    (r"\bjoin\s+our\s+team\b", -15),

    # Self-promotion (someone advertising their own app, not complaining)
    (r"\bcheck\s+out\s+my\s+(app|action|tool|project|extension)\b", -20),
    (r"\bjust\s+(published|released|launched|shipped)\s+(my|our|a)\s+(app|action|tool)\b", -15),
    (r"\bintroducing\s+(my|our)\s+(new\s+)?(app|action|tool)\b", -15),
    (r"\bshow\s+HN\b", -5),

    # Testimonials (people praising existing tools, not pain signals)
    (r"\b(love|loving)\s+(this|the)\s+(tool|app|action)\b", -10),
    (r"\bbest\s+(tool|app|action)\s+(I've|i've|ever)\b", -10),

    # Tutorial content (not pain signals)
    (r"\bstep[- ]by[- ]step\s+(guide|tutorial)\b", -10),
    (r"\bbeginner'?s?\s+guide\b", -10),
]


def _pattern_score(text: str) -> int:
    """Apply all regex pattern lists to text and sum score deltas."""
    total = 0
    text_lower = text.lower()

    for pattern, delta in HIGH_SIGNAL_PATTERNS:
        if re.search(pattern, text_lower):
            total += delta

    for pattern, delta in ENTERPRISE_SIGNAL_PATTERNS:
        if re.search(pattern, text_lower):
            total += delta

    for pattern, delta in LOW_SIGNAL_PATTERNS:
        if re.search(pattern, text_lower):
            total += delta

    return total


def _engagement_score(item: Item) -> int:
    """Score based on engagement metrics. Source-specific."""
    meta = item.metadata
    score = 0

    if item.source == Source.GITHUB_ISSUE:
        reactions = meta.get("reactions", 0)
        comments = meta.get("comments", 0)
        score += min(reactions // 5, 15)
        score += min(comments // 3, 10)

        labels = meta.get("labels", [])
        high_signal_labels = {"bug", "breaking", "regression", "security", "critical"}
        if any(l.lower() in high_signal_labels for l in labels):
            score += 15
        # Enterprise-relevant labels
        opportunity_labels = {
            "enhancement", "feature-request", "feature", "feature request",
            "help-wanted", "help wanted", "proposal", "rfc",
        }
        if any(l.lower() in opportunity_labels for l in labels):
            score += 10

    elif item.source == Source.GITHUB_RELEASE:
        if meta.get("prerelease"):
            score -= 5

    elif item.source == Source.GITHUB_DISCUSSION:
        upvotes = meta.get("upvotes", 0)
        comments = meta.get("comments", 0)
        score += min(upvotes // 3, 20)
        score += min(comments // 5, 10)

        # Unanswered + high engagement = strong unmet need
        if not meta.get("has_answer", True) and upvotes >= 10:
            score += 15

        # Feature request / ideas categories are highest signal
        category = meta.get("category", "").lower()
        high_signal_categories = {
            "ideas", "feature request", "feature requests",
            "feedback", "feature", "enhancements",
        }
        if category in high_signal_categories:
            score += 10

        labels = meta.get("labels", [])
        opportunity_labels = {
            "enhancement", "feature-request", "feature", "feature request",
            "help-wanted", "help wanted", "proposal", "rfc",
        }
        if any(l.lower() in opportunity_labels for l in labels):
            score += 10

    elif item.source == Source.HACKER_NEWS:
        hn_score = meta.get("score", 0)
        comments = meta.get("comments", 0)
        score += min(hn_score // 50, 15)
        score += min(comments // 30, 10)

        # Keyword-targeted search hits get a small relevance boost
        if meta.get("search_keyword"):
            score += 5

    elif item.source == Source.NVD_CVE:
        # CVE severity is the primary engagement signal
        cvss = meta.get("cvss_score", 0)
        if cvss >= 9.0:
            score += 20    # critical
        elif cvss >= 7.0:
            score += 15    # high
        elif cvss >= 4.0:
            score += 5     # medium

    return score


def _body_quality_score(item: Item) -> int:
    """Reward substantive content, penalize empty or very short items."""
    body_len = len(item.body.strip())

    if body_len < 50:
        return -10
    elif body_len < 200:
        return 0
    elif body_len < 1000:
        return 5
    else:
        return 10


def score_item(item: Item) -> Item:
    """
    Score an item deterministically. Returns the item with score set.
    Score is clamped to 0-100.
    """
    base = 20

    text = f"{item.title}\n{item.body}"
    pattern = _pattern_score(text)
    engagement = _engagement_score(item)
    quality = _body_quality_score(item)

    total = base + pattern + engagement + quality
    item.score = max(0, min(100, total))

    return item


def filter_items(items: list[Item], threshold: int = 40) -> list[Item]:
    """Score and filter items. Returns only items above threshold, sorted by score."""
    scored = [score_item(item) for item in items]
    filtered = [item for item in scored if item.score >= threshold]
    filtered.sort(key=lambda x: x.score, reverse=True)
    return filtered
