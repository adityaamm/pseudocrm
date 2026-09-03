"""Scenario injectors — pseudocrm.

Injected, never generated, for the reason `pseudohcm`'s de-growth is: a base corpus
that already contained the scenario would change the shape of every fixture written
against it, and no test could then say *this appears when the scenario is applied and
not otherwise*.
"""
from __future__ import annotations

from datetime import date

from contract.markers import RESERVED_ID_NAMESPACE

from pseudocrm.generator import Corpus


def _namespaced(code: str) -> str:
    return code if code.startswith(RESERVED_ID_NAMESPACE) else (
        RESERVED_ID_NAMESPACE + code)


def inject_offering_retirement(corpus: Corpus, *, on: date, count: int = 3) -> dict:
    """Retire the offerings furthest through their lifecycle, on a date.

    WHY THIS MATTERS TO A PILLAR THAT NEVER MENTIONS PRODUCTS.

    D77's value-chain component asks whether a role delivers an offering. A role
    attached to a retired offering is the clearest case the component has to get right,
    and the wrong answer is available in two directions:

      count it        the role scores as core to delivering something nobody sells
      drop it         the role scores as supporting nothing, and a team winding down a
                      product becomes invisible at exactly the moment somebody is
                      deciding what to do with it

    The corpus makes both reachable. It does not decide between them — that belongs to
    the pillar, and the point of the scenario is that it can be tested rather than
    assumed.

    `valid_to` is set as well as the stage, because a retired offering is a version of
    the record ending, not merely a label change. Both are true and a consumer that
    read only one of them would be right about the other by luck.
    """
    ordered = sorted(
        (o for o in corpus.offerings if o["lifecycle_stage"] != "RETIRED"),
        key=lambda o: (-_stage_rank(o["lifecycle_stage"]), o["offering_id"]),
    )
    retired = []
    for offering in ordered[:count]:
        offering["lifecycle_stage"] = "RETIRED"
        offering["valid_to"] = on.isoformat()
        retired.append(offering["offering_id"])
    return {"offerings_retired": len(retired), "identifiers": retired,
            "on": on.isoformat()}


def inject_churn_quarter(corpus: Corpus, *, year: int, quarter: int,
                         retention_floor: float = 0.72) -> dict:
    """One quarter where retention collapses across every territory.

    The commercial mirror of `pseudofin`'s bad year, and it exists to catch a different
    thing: **a single bad period surrounded by ordinary ones.** Pillar E computes the
    relationship at three lags, and a one-quarter shock is what distinguishes a genuine
    lag effect from a coincidence — a correlation that only appears at lag two, driven
    by one quarter, is not the finding it looks like.
    """
    affected = [
        m for m in corpus.business_unit_metrics
        if m["metric_key"] == "gross_retention_pct"
        and _quarter_of(m["period_start"]) == (year, quarter)
    ]
    for metric in affected:
        metric["actual"] = round(metric["plan"] * retention_floor, 2)
    return {"metrics_adjusted": len(affected), "year": year, "quarter": quarter,
            "retention_floor": retention_floor}


def offerings_for_unit(corpus: Corpus, unit_code: str) -> list[dict]:
    """Offerings a named unit owns. Normalises the caller's plain code, since the
    corpus holds identifiers stamped into the reserved namespace."""
    stamped = _namespaced(unit_code)
    return [o for o in corpus.offerings if o["owning_source_unit_id"] == stamped]


def _stage_rank(stage: str) -> int:
    order = ("INTRODUCTION", "GROWTH", "MATURITY", "DECLINE", "RETIRED")
    return order.index(stage) if stage in order else -1


def _quarter_of(iso: str) -> tuple[int, int]:
    when = date.fromisoformat(iso)
    return when.year, (when.month - 1) // 3 + 1
