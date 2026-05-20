from __future__ import annotations
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agent.domain import Signal, SignalSourceType, SignalPriorityWeight


def collect_from_files(signal_dir: Path) -> list[Signal]:
    """
    Load all signal files from a directory (.txt or .json).
    Used in `agent evaluate` mode only.
    """
    signals = []
    for path in sorted(signal_dir.glob("*")):
        if path.suffix not in (".txt", ".json"):
            continue
        if path.suffix == ".json":
            data = json.loads(path.read_text())
            content = data["content"]
            source_name = data.get("source_name", "file")
            source_url = data.get("source_url")
            collected_at = data.get("collected_at", _utcnow())
            signal_id = data.get("id", str(uuid4()))
        else:
            content = path.read_text()
            source_name = "file"
            source_url = None
            collected_at = _utcnow()
            signal_id = path.stem
        signals.append(Signal(
            id=signal_id,
            source_type=SignalSourceType.FILE,
            source_name=source_name,
            source_url=source_url,
            collected_at=collected_at,
            raw_content=content,
            raw_content_hash=hashlib.sha256(content.encode()).hexdigest(),
        ))
    return signals


def collect_from_web(
    weights: list[SignalPriorityWeight],
    client: "LLMClient",
    max_signals_per_source: int = 5,
    top_n_parameters: int = 5,
    timeout_sec: int = 120,
) -> list[Signal]:
    """
    Live signal collection using Claude with web search.
    Runs searches concurrently (max 3 parallel). Times out per source.
    """
    top_weights = sorted(
        weights,
        key=lambda w: abs(w.sensitivity_cost_per_unit),
        reverse=True,
    )[:top_n_parameters]
    queries = _build_search_queries(top_weights)
    signals: list[Signal] = []

    def _search_one(query_spec: dict) -> list[Signal]:
        return _collect_one_query(query_spec, client, max_signals_per_source)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_search_one, q): q for q in queries}
        for future in as_completed(futures, timeout=timeout_sec):
            try:
                signals.extend(future.result())
            except Exception:
                pass

    return _deduplicate(signals)


def _build_search_queries(weights: list[SignalPriorityWeight]) -> list[dict]:
    queries = []
    for w in weights:
        if w.cdmo_node_name:
            queries.append({
                "query": f'"{w.cdmo_node_name}" FDA warning letter OR import alert OR inspection',
                "source_type": "fda_enforcement",
                "parameter": w.parameter_name,
            })
            queries.append({
                "query": f'"{w.cdmo_node_name}" BioSecure Act OR 1260H OR supply chain 2026',
                "source_type": "biosecure_legislative",
                "parameter": w.parameter_name,
            })
        if w.country_of_origin in ("CN", "IN") and w.parameter_type == "material_price":
            queries.append({
                "query": (
                    f"pharmaceutical API tariff {w.country_of_origin} 2026 "
                    f"site:federalregister.gov OR site:ustr.gov"
                ),
                "source_type": "federal_register",
                "parameter": w.parameter_name,
            })
        if abs(w.sensitivity_cost_per_unit) > 1.0:
            queries.append({
                "query": f'"{w.parameter_name}" supply shortage OR price increase OR lead time 2026',
                "source_type": "trade_press",
                "parameter": w.parameter_name,
            })
    return queries


def _collect_one_query(
    query_spec: dict,
    client: "LLMClient",
    max_results: int,
) -> list[Signal]:
    results = client.search(query_spec["query"])
    signals = []
    for r in results[:max_results]:
        if not isinstance(r, dict) or "content" not in r:
            continue
        content = r["content"]
        signals.append(Signal(
            id=str(uuid4()),
            source_type=SignalSourceType.WEB_SEARCH,
            source_name=r.get("source_name", query_spec["source_type"]),
            source_url=r.get("source_url"),
            collected_at=_utcnow(),
            raw_content=f"{r.get('title', '')}\n{r.get('published_date', '')}\n\n{content}",
            raw_content_hash=hashlib.sha256(content.encode()).hexdigest(),
        ))
    return signals


def _deduplicate(signals: list[Signal]) -> list[Signal]:
    seen: set[str] = set()
    result = []
    for s in signals:
        if s.raw_content_hash not in seen:
            seen.add(s.raw_content_hash)
            result.append(s)
    return result


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
