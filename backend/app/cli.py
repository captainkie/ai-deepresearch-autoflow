"""``autoflow`` CLI — run a research job end-to-end and print a Markdown report.

Milestone 1 wires the deterministic mock providers so the whole pipeline runs
offline. Real providers + registries arrive in a later task.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.__about__ import ACKNOWLEDGEMENTS, APP_NAME, AUTHORS, LICENSE, VERSION
from app.config import load_run_config
from app.core.engine import ResearchEngine
from app.models.schemas import Event, EventType, Plan, PlanSection, RunConfig
from app.providers.crawl.mock import MockCrawlProvider
from app.providers.llm.mock import MockLLMProvider
from app.providers.search.mock import MockSearchProvider

_CREDIT = f"{APP_NAME} v{VERSION} · {LICENSE} · by Narenrit (captainkie) & Claude"


def _build_providers(config: RunConfig):
    if config.llm_provider != "mock":
        raise SystemExit(f"llm provider '{config.llm_provider}' not available yet; use --llm mock")
    if config.search_provider != "mock":
        raise SystemExit(
            f"search provider '{config.search_provider}' not available yet; use --search mock"
        )
    if config.crawl_provider != "mock":
        raise SystemExit(
            f"crawl provider '{config.crawl_provider}' not available yet; use --crawl mock"
        )
    return (
        MockLLMProvider(model=config.llm_model),
        MockSearchProvider(),
        MockCrawlProvider(),
    )


def _format_event(event: Event) -> str | None:
    data = event.data
    match event.type:
        case EventType.status:
            return f"[status] {data.get('stage')} — {data.get('message')}"
        case EventType.plan:
            titles = ", ".join(s["title"] for s in data.get("sections", []))
            return f"[plan] {len(data.get('sections', []))} sections: {titles}"
        case EventType.awaiting_plan:
            return "[plan] awaiting approval…"
        case EventType.section_start:
            return f"→ section {data.get('section_id')}: {data.get('title')}"
        case EventType.search:
            return f"  search: {data.get('query')}"
        case EventType.source:
            source = data.get("source", {})
            return f"  + [{source.get('id')}] {source.get('title')}"
        case EventType.section_done:
            return f"✓ section {data.get('section_id')} ({data.get('source_count')} sources)"
        case EventType.done:
            return f"[done] {data.get('title')} ({data.get('source_count')} sources)"
        case EventType.error:
            return f"[error] {data.get('message')}"
        case _:
            return None


def _make_sink(json_events: bool):
    async def sink(event: Event) -> None:
        if json_events:
            sys.stdout.write(
                json.dumps(
                    {
                        "seq": event.seq,
                        "run_id": event.run_id,
                        "ts": event.ts,
                        "type": event.type.value,
                        "data": event.data,
                    }
                )
                + "\n"
            )
            return
        line = _format_event(event)
        if line:
            print(line, file=sys.stderr)

    return sink


async def _auto_approval(plan: Plan) -> list[PlanSection]:
    return plan.sections


async def _run_research(args: argparse.Namespace) -> int:
    config = load_run_config(
        llm_provider=args.llm,
        search_provider=args.search,
        crawl_provider=args.crawl,
        template=args.template,
        language=args.lang,
        require_plan_approval=args.approve,
    )
    llm, search, crawl = _build_providers(config)
    engine = ResearchEngine(llm=llm, search=search, crawl=crawl)
    sink = _make_sink(args.json_events)
    approval = _auto_approval if config.require_plan_approval else None

    markdown = await engine.run("cli-run", args.query, config, sink, approval)

    if not args.json_events:
        print(markdown)
        print()
        print(_CREDIT)
    return 0


def _print_about() -> None:
    print(f"{APP_NAME} v{VERSION}")
    print(f"License: {LICENSE}")
    print("Authors:")
    for author in AUTHORS:
        print(f"  - {author['name']} ({author['handle']}) — {author['role']}")
    print("Acknowledgements:")
    for ack in ACKNOWLEDGEMENTS:
        print(f"  - {ack['name']} ({ack['license']}) {ack['url']}")
    print()
    print(_CREDIT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autoflow", description=f"{APP_NAME} — deep research CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    research = sub.add_parser("research", help="Run a research job and print a report")
    research.add_argument("query", help="The research goal / question")
    research.add_argument("--template", default=None, help="Template id (default: deep_research)")
    research.add_argument("--lang", default=None, choices=["en", "th"], help="Report language")
    research.add_argument("--llm", default=None, help="LLM provider (mock)")
    research.add_argument("--search", default=None, help="Search provider (mock)")
    research.add_argument("--crawl", default=None, help="Crawl provider (mock)")
    approve = research.add_mutually_exclusive_group()
    approve.add_argument("--approve", dest="approve", action="store_true", default=None)
    approve.add_argument("--no-approve", dest="approve", action="store_false")
    research.add_argument("--json-events", action="store_true", help="Emit raw JSON event lines")

    sub.add_parser("about", help="Show authors, license, and acknowledgements")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "about":
        _print_about()
        return 0
    if args.command == "research":
        return asyncio.run(_run_research(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
