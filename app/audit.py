"""
Decision audit log — the record a model risk reviewer asks for on day one.

Every consequential event is appended here with the inputs that produced it, the
engine and model versions that were live at the time, the reason codes shown to
the RM, and who saw it. Append-only: a decision is evidence, so nothing is
rewritten. Reproducibility is what makes it useful — the same record re-scored
against the same engine version must produce the same tier, which is why the
scoring path is deterministic and seeded.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import APP_VERSION

DATA_DIR = Path(__file__).resolve().parent / "data"
AUDIT_LOG = DATA_DIR / "audit_log.jsonl"

MAX_RETURNED = 500

_lock = threading.Lock()
_cache: list[dict] | None = None

EVENT_TYPES = {
    "scoring_run": "Batch scoring of the lead book",
    "lead_decision": "A tier and action shown to an RM",
    "aa_consent": "Account Aggregator consent requested",
    "aa_fetch": "Other-bank data pulled under consent",
    "outcome_recorded": "RM logged a call disposition",
    "underwriter_packet": "Underwriter PDF generated",
    "queue_export": "RM queue exported to CSV",
    "whatif_simulation": "RM ran a what-if simulation",
}


def _display_path(path: Path) -> str:
    """Repo-relative when it sits inside the project, absolute otherwise."""
    try:
        return str(path.relative_to(Path(__file__).resolve().parent.parent))
    except ValueError:
        return str(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


_model_version_cache: str | None = None


def _model_version() -> str:
    """Memoised: the loaded model cannot change without a restart, and resolving
    it per entry cost ~3 ms each when the ML extras are absent."""
    global _model_version_cache
    if _model_version_cache is not None:
        return _model_version_cache
    _model_version_cache = _resolve_model_version()
    return _model_version_cache


def _resolve_model_version() -> str:
    try:
        from app.ml_model import get_model

        model = get_model()
        if model.is_ready:
            return f"xgb-{model.meta.get('version', '1.0')}"
        return "rules-only"
    except Exception:
        return "rules-only"


def _read_all() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    records: list[dict] = []
    if AUDIT_LOG.exists():
        for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    _cache = records
    return _cache


def record(
    event_type: str,
    actor: str = "demo-rm",
    customer_id: str | None = None,
    summary: str = "",
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    reason_codes: list[str] | None = None,
    sync: bool = True,
) -> dict:
    entry = {
        "audit_id": uuid.uuid4().hex[:12],
        "at": _now(),
        "event_type": event_type,
        "event_label": EVENT_TYPES.get(event_type, event_type),
        "actor": actor,
        "customer_id": customer_id,
        "summary": summary[:300],
        "inputs": inputs or {},
        "outputs": outputs or {},
        "reason_codes": (reason_codes or [])[:6],
        "engine_version": APP_VERSION,
        "model_version": _model_version(),
    }
    with _lock:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with AUDIT_LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
                fh.flush()
                if sync:
                    os.fsync(fh.fileno())
        except OSError as exc:
            entry["persisted"] = False
            entry["persist_error"] = type(exc).__name__
        else:
            entry["persisted"] = True
        if _cache is not None:
            _cache.append(entry)
    return entry


def record_lead_decisions(ranked_profiles: list[dict], limit: int = 200) -> int:
    """One entry per lead for a scoring run — the decisions an RM will act on."""
    existing = {
        (r.get("customer_id"), r.get("event_type"))
        for r in _read_all()
        if r.get("event_type") == "lead_decision"
    }
    written = 0
    for profile in ranked_profiles[:limit]:
        if (profile["customer_id"], "lead_decision") in existing:
            continue
        reasons = []
        for key in ("repayment_capacity", "purchase_intent", "behavioral_discipline"):
            dim = profile.get(key) or {}
            if dim.get("reasons"):
                reasons.append(dim["reasons"][0])
        record(
            "lead_decision",
            actor="scoring-engine",
            customer_id=profile["customer_id"],
            summary=f"{profile['lead_tier']} — {profile.get('recommended_action', '')}",
            inputs={
                "monthly_income": profile.get("monthly_income"),
                "inferred_income": profile.get("inferred_monthly_income"),
                "scoring_mode": profile.get("scoring_mode", "rules"),
            },
            outputs={
                "lead_tier": profile["lead_tier"],
                "composite_lead_score": profile["composite_lead_score"],
                "rm_call_eligible": profile.get("rm_call_eligible", False),
                "top_product": profile.get("top_product_label"),
            },
            reason_codes=reasons,
            sync=False,  # batch: one fsync after the run, not 200
        )
        written += 1

    if written:
        try:
            with AUDIT_LOG.open("a", encoding="utf-8") as fh:
                os.fsync(fh.fileno())
        except OSError:
            pass
    return written


def query(
    event_type: str | None = None,
    customer_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    rows = _read_all()
    if event_type:
        rows = [r for r in rows if r.get("event_type") == event_type]
    if customer_id:
        rows = [r for r in rows if r.get("customer_id") == customer_id]
    return list(reversed(rows))[: min(limit, MAX_RETURNED)]


def build_audit_report(limit: int = 40) -> dict[str, Any]:
    rows = _read_all()
    by_type: dict[str, int] = {}
    actors: dict[str, int] = {}
    for r in rows:
        by_type[r.get("event_type", "?")] = by_type.get(r.get("event_type", "?"), 0) + 1
        actors[r.get("actor", "?")] = actors.get(r.get("actor", "?"), 0) + 1

    covered = {r.get("customer_id") for r in rows if r.get("event_type") == "lead_decision"}
    return {
        "total_entries": len(rows),
        "entries_by_type": [
            {"event_type": k, "label": EVENT_TYPES.get(k, k), "count": v}
            for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])
        ],
        "actors": [{"actor": k, "count": v} for k, v in sorted(actors.items(), key=lambda kv: -kv[1])],
        "leads_with_decision_record": len(covered),
        "first_entry_at": rows[0]["at"] if rows else None,
        "last_entry_at": rows[-1]["at"] if rows else None,
        "recent": list(reversed(rows))[:limit],
        "engine_version": APP_VERSION,
        "model_version": _model_version(),
        "properties": [
            ("Append-only", "No entry is ever updated or deleted; a correction is a new entry."),
            ("Versioned", "Every entry carries the engine and model version that produced it."),
            ("Reason-coded", "The reasons shown to the RM are stored with the decision, not regenerated later."),
            ("Reproducible", "Deterministic, seeded scoring means a replay of the same record returns the same tier."),
            ("Exportable", "Full log available as CSV for the bank's own retention and review."),
        ],
    }


def clear_cache_for_tests() -> None:
    global _cache
    _cache = None
