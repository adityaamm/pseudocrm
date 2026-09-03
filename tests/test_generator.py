"""The CRM / CX emulator produces the catalogue and the commercial measures — D97.

The organising question: **does a corpus exist in which D77's value-chain component can
be wrong in either direction, and be caught?**

That needs offerings with owners and without, at every lifecycle stage including
retired, some described and some not. A tidy catalogue where every offering is owned,
current and richly written would let the component pass while handling none of the
cases a real customer has.
"""
from __future__ import annotations

import json
from datetime import date

from contract.markers import SYNTHETIC_MARKER_FIELD, SYNTHETIC_MARKER_VALUE

from pseudocrm.emit import ENTITY_FILES, emit
from pseudocrm.generator import (
    KINDS, MEASURES, STAGES, Corpus, Parameters, generate, periods,
)
from pseudocrm.scenarios import (
    inject_churn_quarter, inject_offering_retirement, offerings_for_unit,
)


def small() -> Parameters:
    return Parameters(units=4, offerings=10, history_end=date(2025, 12, 31))


class TestReproducibility:
    def test_the_same_seed_produces_byte_identical_output(self):
        first = json.dumps(generate(small()).counts(), sort_keys=True)
        rows_a = json.dumps(generate(small()).offerings, sort_keys=True)
        rows_b = json.dumps(generate(small()).offerings, sort_keys=True)
        assert rows_a == rows_b
        assert first == json.dumps(generate(small()).counts(), sort_keys=True)

    def test_a_different_seed_produces_different_output(self):
        a = json.dumps(generate(Parameters(seed=1, units=4)).offerings, sort_keys=True)
        b = json.dumps(generate(Parameters(seed=2, units=4)).offerings, sort_keys=True)
        assert a != b

    def test_it_does_not_touch_the_global_random_generator(self):
        import random

        random.seed(1)
        before = random.random()
        random.seed(1)
        generate(small())
        assert random.random() == before


class TestTheCatalogue:
    def test_some_offerings_have_no_owning_unit(self):
        """Null is ordinary. Many offerings are delivered across several units and
        owned by none, and inventing an owner would place a role in a value chain it
        is not in."""
        offerings = generate(Parameters(units=4, offerings=24)).offerings
        owners = [o["owning_source_unit_id"] for o in offerings]
        assert None in owners and any(o is not None for o in owners)

    def test_every_lifecycle_stage_appears_including_retired(self):
        """A role delivering a declining offering and one delivering a growing offering
        are differently placed. RETIRED is the stage an analysis forgets to exclude."""
        stages = {o["lifecycle_stage"] for o in generate(small()).offerings}
        assert stages == set(STAGES)

    def test_every_kind_appears(self):
        assert {o["kind"] for o in generate(small()).offerings} == set(KINDS)

    def test_some_offerings_have_no_description(self):
        """The value-chain linkage is derived from content, so the thin path has to be
        reachable or nothing exercises the low-confidence branch."""
        offerings = generate(Parameters(units=4, offerings=24)).offerings
        assert any(o["description"] is None for o in offerings)
        assert any(o["description"] for o in offerings)

    def test_a_missing_description_is_null_and_never_an_empty_string(self):
        for offering in generate(Parameters(units=4, offerings=24)).offerings:
            assert offering["description"] != ""


class TestDirection:
    def test_a_lower_is_better_commercial_measure_is_present(self):
        """`avg_days_to_close`. A corpus where every measure runs the same way lets a
        product assume a direction and stay green."""
        assert {d for _, _, d, _ in MEASURES} == {"HIGHER_IS_BETTER",
                                                  "LOWER_IS_BETTER"}
        assert any(m["direction"] == "LOWER_IS_BETTER"
                   for m in generate(small()).business_unit_metrics)

    def test_no_plan_is_zero(self):
        assert all(m["plan"] != 0 for m in generate(small()).business_unit_metrics)


class TestTheCatalogueIsNotDuplicatedFromScm:
    def test_this_emulator_owns_offerings_and_scm_does_not(self):
        """Two systems owning the catalogue would mean deciding whether an SCM item and
        a CRM product are the same thing — cross-system identity resolution, which D56
        put out of scope for inference. Asserted here because the temptation to add
        offerings to the SCM emulator will be strongest in a hurry.
        """
        assert "Offering" in ENTITY_FILES
        from pathlib import Path

        scm = (Path(__file__).resolve().parents[2] / "pseudoscm"
               / "src" / "pseudoscm" / "emit.py")
        if scm.exists():
            assert "Offering" not in scm.read_text(encoding="utf-8"), (
                "the SCM emulator has started emitting offerings — two catalogues is "
                "the identity question D56 refuses to answer by inference"
            )


class TestScenarios:
    def test_retirement_sets_both_the_stage_and_the_record_end(self):
        """A retired offering is a version of the record ending, not merely a label
        change. Both are true, and a consumer reading only one would be right about the
        other by luck."""
        corpus = generate(small())
        result = inject_offering_retirement(corpus, on=date(2025, 6, 30), count=2)
        assert result["offerings_retired"] == 2
        retired = [o for o in corpus.offerings
                   if o["offering_id"] in result["identifiers"]]
        assert all(o["lifecycle_stage"] == "RETIRED" for o in retired)
        assert all(o["valid_to"] == "2025-06-30" for o in retired)

    def test_retirement_does_not_touch_anything_else(self):
        corpus = generate(small())
        before = sum(1 for o in corpus.offerings
                     if o["lifecycle_stage"] == "RETIRED")
        inject_offering_retirement(corpus, on=date(2025, 6, 30), count=2)
        after = sum(1 for o in corpus.offerings if o["lifecycle_stage"] == "RETIRED")
        assert after == before + 2

    def test_a_churn_quarter_hits_retention_and_nothing_else(self):
        """One bad period surrounded by ordinary ones — what distinguishes a genuine
        lag effect from a coincidence at lag two."""
        corpus = generate(small())
        result = inject_churn_quarter(corpus, year=2025, quarter=2)
        assert result["metrics_adjusted"] > 0
        for metric in corpus.business_unit_metrics:
            when = date.fromisoformat(metric["period_start"])
            in_window = (when.year, (when.month - 1) // 3 + 1) == (2025, 2)
            if in_window and metric["metric_key"] == "gross_retention_pct":
                assert metric["actual"] < metric["plan"] * 0.8

    def test_the_base_corpus_has_no_churn_quarter(self):
        corpus = generate(small())
        retention = [m for m in corpus.business_unit_metrics
                     if m["metric_key"] == "gross_retention_pct"]
        assert any(m["actual"] >= m["plan"] * 0.9 for m in retention)

    def test_a_unit_lookup_normalises_the_plain_code(self):
        """The corpus holds stamped identifiers; a caller names a unit plainly."""
        corpus = generate(small())
        owned = offerings_for_unit(corpus, "TERR-001")
        assert all(o["owning_source_unit_id"] == "PSEUDO::TERR-001" for o in owned)


class TestTheMarker:
    def test_every_emitted_record_carries_it(self):
        corpus = generate(small())
        inject_offering_retirement(corpus, on=date(2025, 6, 30), count=2)
        for attribute in ENTITY_FILES.values():
            rows = getattr(corpus, attribute)
            assert rows, f"{attribute} is empty — this check would pass by vacancy"
            for row in rows:
                assert row[SYNTHETIC_MARKER_FIELD] == SYNTHETIC_MARKER_VALUE

    def test_identifiers_are_moved_into_the_reserved_namespace(self):
        corpus = generate(small())
        assert all(o["offering_id"].startswith("PSEUDO::") for o in corpus.offerings)
        assert all(m["metric_id"].startswith("PSEUDO::")
                   for m in corpus.business_unit_metrics)


class TestEmission:
    def test_every_entity_gets_a_file_even_when_empty(self, tmp_path):
        written = emit(Corpus(), tmp_path)
        assert set(written) == set(ENTITY_FILES)
        for entity in ENTITY_FILES:
            assert (tmp_path / f"{entity}.jsonl").exists()

    def test_the_files_round_trip(self, tmp_path):
        corpus = generate(small())
        written = emit(corpus, tmp_path)
        lines = (tmp_path / "Offering.jsonl").read_text(
            encoding="utf-8").splitlines()
        assert len(lines) == written["Offering"]
        assert json.loads(lines[0])["kind"] in KINDS


class TestPeriods:
    def test_periods_abut_exactly(self):
        found = periods(small())
        assert found
        for earlier, later in zip(found, found[1:]):
            assert later[0].toordinal() == earlier[1].toordinal() + 1
