from __future__ import annotations

import asyncio
import logging

from gateway import artifact_store, research_runs
from gateway import db as kitty_db
from gateway.paths import DATA_DIR
from gateway.researcher import DeepResearcher

RESEARCH_OUTPUT_DIR = DATA_DIR / "research"
logger = logging.getLogger("kitty.research_execution")


def _markdown(topic: str, summary: str, sources: list[str], findings: str) -> str:
    source_lines = "\n".join(f"- {url}" for url in sources) or "- No external sources recorded"
    return (
        f"# Research: {topic}\n\n"
        f"## Summary\n{summary.strip()}\n\n"
        f"## Sources\n{source_lines}\n\n"
        f"## Evidence\n{findings.strip() or 'No extracted evidence was available.'}\n"
    )


async def run_persisted_research(run_id: str) -> None:
    run = research_runs.get_run(run_id)
    if run is None:
        raise research_runs.ResearchRunNotFound(run_id)

    def progress(stage: str, sources: list[str] | None = None) -> None:
        research_runs.update_stage(run_id, stage=stage, sources=sources)

    try:
        researcher = DeepResearcher()
        report = await researcher.technical_deep_dive_report(run["topic"], progress=progress)
        sources = [str(url) for url in report.get("sources", []) if str(url).strip()]
        research_runs.update_stage(run_id, stage="saving", sources=sources)
        RESEARCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESEARCH_OUTPUT_DIR / f"{run_id}.md"
        output_path.write_text(
            _markdown(run["topic"], str(report.get("summary") or ""), sources, str(report.get("findings") or "")),
            encoding="utf-8",
        )
        if artifact_store.ARTIFACTS_DB_FILE != research_runs.DB_FILE:
            raise research_runs.ResearchRunError("research artifact and run stores must share one database")
        with kitty_db.connect(research_runs.DB_FILE) as conn:
            artifact = artifact_store.register_file(
                output_path,
                kind="research_report",
                media_type="text/markdown",
                project_id=run.get("project_id"),
                created_by="research",
                source_ref=f"research_run:{run_id}",
                metadata={"research_run_id": run_id, "sources": sources},
                connection=conn,
            )
            research_runs.complete_run(
                run_id,
                summary=str(report.get("summary") or ""),
                artifact_id=artifact["id"],
                sources=sources,
                connection=conn,
            )
    except Exception as exc:
        current = research_runs.get_run(run_id)
        if current is not None and current.get("status") == "running":
            research_runs.fail_run(run_id, error=f"{type(exc).__name__}: {exc}")
        logger.exception("Research run %s failed", run_id)
        raise


def run_persisted_research_background(run_id: str) -> None:
    """Run research in FastAPI's sync background thread, off the event loop."""
    asyncio.run(run_persisted_research(run_id))
