#!/usr/bin/env python3
"""
signal-extract: Enterprise developer tool opportunity discovery.

Usage:
    python main.py collect              # Fetch new items from all sources
    python main.py digest               # Generate daily enterprise opportunity scan
    python main.py weekly               # Generate weekly enterprise dev-tool synthesis
    python main.py opportunities        # Generate deep enterprise opportunity report (14-day window)
    python main.py opportunities-json   # Generate structured JSON opportunity report
    python main.py ask "question"       # Ask about recent enterprise signals
    python main.py run                  # collect + digest (for cron)
    python main.py stats                # Show collection stats
    python main.py serve                # Start web UI server
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from config import load_config
from collectors import GitHubCollector, GitHubDiscussionsCollector, HackerNewsCollector, RSSCollector
from collectors.nvd import NVDCollector
from filters import filter_items
from llm import create_provider
from storage import Storage
from synthesizer.engine import Synthesizer
from qa import QAHandler
from delivery import deliver_cli, deliver_email


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_collect(config, storage) -> int:
    """Run all collectors, filter, and store."""
    collectors = [
        GitHubCollector(storage, config),
        GitHubDiscussionsCollector(storage, config),
        HackerNewsCollector(storage, config),
        RSSCollector(storage, config),
        NVDCollector(storage, config),
    ]

    total_raw = 0
    total_stored = 0

    for collector in collectors:
        log = logging.getLogger(collector.name())
        try:
            raw_items = collector.collect()
            log.info(f"Collected {len(raw_items)} raw items")
            total_raw += len(raw_items)

            if raw_items:
                filtered = filter_items(raw_items, threshold=config.score_threshold)
                log.info(f"After filtering: {len(filtered)} items (threshold={config.score_threshold})")

                new_count = storage.insert_items(filtered)
                log.info(f"Stored {new_count} new items")
                total_stored += new_count
        except Exception as e:
            log.error(f"Collector {collector.name()} failed: {e}")

    print(f"Collected: {total_raw} raw -> {total_stored} stored")
    return total_stored


def cmd_digest(config, storage):
    """Generate and deliver daily enterprise opportunity scan."""
    llm = create_provider(config)
    synth = Synthesizer(llm, storage)

    digest = synth.daily_digest()
    if digest:
        deliver_cli(digest)
        if config.smtp_host:
            deliver_email(digest, config)


def cmd_weekly(config, storage):
    """Generate and deliver weekly enterprise dev-tool synthesis."""
    llm = create_provider(config)
    synth = Synthesizer(llm, storage)

    digest = synth.weekly_synthesis()
    if digest:
        deliver_cli(digest)
        if config.smtp_host:
            deliver_email(digest, config)


def cmd_opportunities(config, storage):
    """Generate deep enterprise opportunity report (14-day analysis window)."""
    llm = create_provider(config)
    synth = Synthesizer(llm, storage)

    digest = synth.opportunity_report()
    if digest:
        deliver_cli(digest)
        if config.smtp_host:
            deliver_email(digest, config)


def cmd_opportunities_json(config, storage, out_path: str | None = None):
    """Generate structured JSON opportunity report."""
    llm = create_provider(config)
    synth = Synthesizer(llm, storage)

    opportunities = synth.structured_opportunity_report()

    if opportunities is None:
        print("Error: Failed to generate structured opportunity report.", file=sys.stderr)
        sys.exit(1)

    if not opportunities:
        print("No qualifying opportunities found in the last 14 days.")
        return

    data = [opp.to_dict() for opp in opportunities]
    json_str = json.dumps(data, indent=2)

    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json_str, encoding="utf-8")
        print(f"Wrote {len(opportunities)} opportunities to {path}")
    else:
        print(json_str)


def cmd_ask(config, storage, question: str):
    """Answer a question about enterprise dev-tool signals."""
    llm = create_provider(config)
    handler = QAHandler(llm, storage)

    result = handler.ask(question)
    if result:
        deliver_cli(result)


def cmd_run(config, storage):
    """Full pipeline: collect then digest. Meant for cron."""
    stored = cmd_collect(config, storage)
    if stored > 0:
        cmd_digest(config, storage)
    else:
        print("Nothing new to digest.")


def cmd_stats(config, storage):
    """Print collection stats."""
    stats = storage.get_stats()
    print(f"Total items: {stats['total_items']}")
    for source, count in stats["by_source"].items():
        print(f"  {source}: {count}")


def cmd_serve(config, args):
    """Start the API + web UI server."""
    from api.server import create_app

    static_folder = Path(__file__).parent / "web" / "dist"
    if not static_folder.exists():
        static_folder = None
        print("No built frontend found. API-only mode.")
        print("Run 'cd web && npm install && npm run build' for the full UI.")

    app = create_app(db_path=config.db_path, static_folder=static_folder)
    print(f"Starting server at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.verbose)


def cli():
    parser = argparse.ArgumentParser(
        prog="signal",
        description="Enterprise developer tool opportunity discovery via signal extraction",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="command", help="Command to run")

    sub.add_parser("collect", parents=[common], help="Fetch new items from all sources")
    sub.add_parser("digest", parents=[common], help="Generate daily enterprise opportunity scan")
    sub.add_parser("weekly", parents=[common], help="Generate weekly enterprise dev-tool synthesis")
    sub.add_parser(
        "opportunities", parents=[common],
        help="Generate deep enterprise opportunity report (14-day window)",
    )

    opp_json_parser = sub.add_parser(
        "opportunities-json", parents=[common],
        help="Generate structured JSON opportunity report",
    )
    opp_json_parser.add_argument(
        "--out", type=str, default=None,
        help="Output file path. If omitted, prints to stdout.",
    )

    sub.add_parser("run", parents=[common], help="Collect + digest (for cron)")
    sub.add_parser("stats", parents=[common], help="Show collection stats")

    ask_parser = sub.add_parser("ask", parents=[common], help="Ask about enterprise dev-tool signals")
    ask_parser.add_argument("question", help="Your question")

    serve_parser = sub.add_parser("serve", parents=[common], help="Start web UI server")
    serve_parser.add_argument("--port", type=int, default=5002, help="Port (default 5002)")
    serve_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default 127.0.0.1)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)
    config = load_config()

    # serve command doesn't need storage — it opens its own read-only connections
    if args.command == "serve":
        cmd_serve(config, args)
        return

    storage = Storage(config.db_path)

    try:
        match args.command:
            case "collect":
                cmd_collect(config, storage)
            case "digest":
                cmd_digest(config, storage)
            case "weekly":
                cmd_weekly(config, storage)
            case "opportunities":
                cmd_opportunities(config, storage)
            case "opportunities-json":
                cmd_opportunities_json(config, storage, args.out)
            case "ask":
                cmd_ask(config, storage, args.question)
            case "run":
                cmd_run(config, storage)
            case "stats":
                cmd_stats(config, storage)
            case _:
                parser.print_help()
    finally:
        storage.close()


if __name__ == "__main__":
    cli()
