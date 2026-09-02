"""Deterministic generation — pseudocrm, the CRM / CX emulator.

Same rule as `pseudohcm` and `pseudofin`: the output is not a claim about the world. It
is the reproducible result of a published rule set with stated parameters. Same seed,
same parameters, byte-identical output.

**THE DOMAIN, NEVER A VENDOR'S SCHEMA — D91.** Nothing here is modelled on any
particular CRM's objects, field names or documentation. What is modelled is what every
CRM holds in some form: things the organisation sells, and commercial measures against
a plan. Field mappings for a real product are authored from that product's own
published documentation, under that product's terms, when an engagement requires them.

WHY THE CATALOGUE LIVES HERE AND NOWHERE ELSE

`Offering` is emitted by this emulator only. The SCM emulator measures how well things
are fulfilled and does **not** define what they are, because two systems owning the
catalogue is the cross-system identity problem D56 put out of scope — and a harness
that quietly produced the same offering codes from two sources would hide it rather
than exercise it.

WHAT THIS EMULATOR EXISTS TO EXERCISE

  VALUE CHAIN     D77's value-chain component asks whether a role delivers an offering
                  or supports those who do. That needs offerings with owners — and
                  some WITHOUT, because plenty of offerings are delivered across
                  several units and owned by none. Inventing an owner would place a
                  role in a value chain it is not in.

  LIFECYCLE       A role delivering a declining offering and a role delivering a
                  growing one are differently placed. Every stage appears, including
                  RETIRED, which is the one an analysis is most likely to forget to
                  exclude.

  A LOWER-IS-BETTER COMMERCIAL MEASURE. `avg_days_to_close` joins the two
                  higher-is-better ones for the reason `pseudofin` emits a cost metric:
                  a corpus where every measure runs the same way lets a product assume
                  a direction and stay green.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from pseudocrm.calendar import periods as calendar_periods
from pseudocrm.marking import mark

HISTORY_START = date(2024, 1, 1)
HISTORY_END = date(2026, 12, 31)

MEASURES: tuple[tuple[str, str, str, str], ...] = (
    ("new_bookings", "New bookings", "HIGHER_IS_BETTER", "GBP"),
    ("gross_retention_pct", "Gross revenue retention", "HIGHER_IS_BETTER", "percent"),
    # The one that runs the other way. See the module docstring.
    ("avg_days_to_close", "Average days to close", "LOWER_IS_BETTER", "days"),
)

KINDS: tuple[str, ...] = ("PRODUCT", "SERVICE", "PLATFORM", "INTERNAL_SERVICE")

# Ordinary product-lifecycle vocabulary. RETIRED is included deliberately: an offering
# nobody sells any more still explains a role that exists to wind it down.
STAGES: tuple[str, ...] = ("INTRODUCTION", "GROWTH", "MATURITY", "DECLINE", "RETIRED")


@dataclass
class Parameters:
    """Every parameter documented and adjustable. Nothing hidden."""

    seed: int = 20260902
    units: int = 12
    offerings: int = 18
    history_start: date = HISTORY_START
    history_end: date = HISTORY_END
    months_per_period: int = 3

    # This system's own account/territory codes unless the customer's HCM unit codes
    # are supplied deliberately. See `pseudofin` — the same reasoning, the same D56.
    org_unit_codes: tuple[str, ...] = ()

    performance_spread: float = 0.15
    unstated_comparability: float = 0.15
    late_plans: float = 0.10

    # Share of offerings with NO owning unit. Null is ordinary and must stay ordinary:
    # many offerings are delivered across several units and owned by none.
    unowned_offerings: float = 0.25
    # Share with no description. The value-chain linkage is derived from content, so a
    # corpus where every offering is richly described never exercises the thin path.
    offerings_without_description: float = 0.2


@dataclass
class Corpus:
    offerings: list[dict] = field(default_factory=list)
    business_unit_metrics: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "Offering": len(self.offerings),
            "BusinessUnitMetric": len(self.business_unit_metrics),
        }


def periods(params: Parameters) -> list[tuple[date, date]]:
    """Measurement periods for these parameters. Arithmetic in `calendar.py` — D98."""
    return calendar_periods(params.history_start, params.history_end,
                            params.months_per_period)


def unit_codes(params: Parameters) -> list[str]:
    if params.org_unit_codes:
        return list(params.org_unit_codes)
    return [f"TERR-{n:03d}" for n in range(1, params.units + 1)]


def generate(params: Parameters | None = None) -> Corpus:
    """The full corpus. Seeded locally — never the module-level RNG."""
    params = params or Parameters()
    rng = random.Random(params.seed)
    corpus = Corpus()
    codes = unit_codes(params)

    for n in range(params.offerings):
        kind = KINDS[n % len(KINDS)]
        stage = STAGES[n % len(STAGES)]
        owned = rng.random() >= params.unowned_offerings
        described = rng.random() >= params.offerings_without_description
        corpus.offerings.append(mark({
            "offering_id": f"OFF-{n:03d}",
            "offering_code": f"OFF-{n:03d}",
            "name": f"{kind.title().replace('_', ' ')} line {n:03d}",
            "kind": kind,
            "lifecycle_stage": stage,
            "owning_org_unit_id": codes[n % len(codes)] if owned else None,
            "description": (
                f"A {kind.lower().replace('_', ' ')} in the {stage.lower()} stage, "
                "sold through the direct channel." if described else None),
            "valid_from": params.history_start.isoformat(),
            "valid_to": None,
        }))

    for start, end in periods(params):
        for code in codes:
            for key, label, direction, measure in MEASURES:
                plan = float(rng.randrange(20, 900))
                actual = round(plan * (1 + rng.uniform(-params.performance_spread,
                                                       params.performance_spread)), 2)
                corpus.business_unit_metrics.append(mark({
                    "metric_id": f"BUM-{code}-{start.isoformat()}-{key}",
                    "source_unit_id": code,
                    "metric_key": key,
                    "label": label,
                    "unit_of_measure": measure,
                    "direction": direction,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "actual": actual,
                    "plan": plan,
                    "plan_set_on": (
                        date.fromordinal(start.toordinal() + 20).isoformat()
                        if rng.random() < params.late_plans
                        else date.fromordinal(start.toordinal() - 30).isoformat()),
                    "comparable_across_units": (
                        None if rng.random() < params.unstated_comparability else True),
                    "valid_from": start.isoformat(),
                    "valid_to": None,
                }))
    return corpus
