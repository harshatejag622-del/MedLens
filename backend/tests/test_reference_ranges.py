"""
Phase 6 — Deterministic Reference-Range Classification Engine Tests
====================================================================

Coverage areas:
  A.  Standard interval formats (12.0 - 16.0, en-dash, em-dash, "to", slash)
  B.  Boundary values (exactly equal to lower / upper bound → NORMAL)
  C.  Upper-bound only ("< 200", "<= 200", "≤ 200", "up to 200")
  D.  Lower-bound only ("> 50", ">= 50", "≥ 50", "at least 50")
  E.  LOW / NORMAL / HIGH classification correctness
  F.  Missing / null / empty reference range → UNKNOWN
  G.  Non-assessable phrases → UNKNOWN
  H.  Qualitative (non-numeric) ranges → UNKNOWN
  I.  Unparseable / ambiguous ranges → UNKNOWN
  J.  Missing value (None) → UNKNOWN
  K.  Unit-suffixed ranges (unit stripped, number parsed correctly)
  L.  Locale comma-decimal ranges ("12,0 - 16,0")
  M.  Parenthesised / bracket-enclosed ranges
  N.  Negative numeric values (e.g. temperature scales)
  O.  Large and very small values (precision edge cases)
  P.  Inverted range (low > high) → UNKNOWN (not parseable as interval)
  Q.  AI-hallucination guard integration (range asserted, not in source → stripped)
  R.  ReferenceRangeService backward-compatible API
  S.  ClassificationResult datatype guarantees
  T.  Raw range preserved verbatim
  U.  Description content checks (reason field)
"""

import pytest
from app.services.reference_range import (
    classify,
    LabStatus,
    ClassificationResult,
    ReferenceRangeService,
    _parse_numeric_range,
    _is_qualitative,
    _is_non_assessable,
)


# ===========================================================================
# A — Standard interval formats
# ===========================================================================

class TestStandardIntervalFormats:

    def test_hyphen_integer_range(self):
        r = classify(14.0, "12 - 16")
        assert r.status == LabStatus.NORMAL

    def test_hyphen_decimal_range(self):
        r = classify(14.0, "12.0 - 16.0")
        assert r.status == LabStatus.NORMAL
        assert r.parsed_low == 12.0
        assert r.parsed_high == 16.0

    def test_en_dash_range(self):
        r = classify(11.0, "12.0–16.0")
        assert r.status == LabStatus.LOW

    def test_em_dash_range(self):
        r = classify(17.0, "12.0—16.0")
        assert r.status == LabStatus.HIGH

    def test_to_separator(self):
        r = classify(14.0, "12.0 to 16.0")
        assert r.status == LabStatus.NORMAL

    def test_slash_separator(self):
        r = classify(14.0, "12 / 16")
        assert r.status == LabStatus.NORMAL

    def test_multiple_hyphens_separator(self):
        # "12.0 -- 16.0" (double-hyphen used in some labs)
        r = classify(14.0, "12.0 -- 16.0")
        assert r.status == LabStatus.NORMAL

    def test_no_spaces_around_separator(self):
        r = classify(14.0, "12.0-16.0")
        assert r.status == LabStatus.NORMAL

    def test_extra_whitespace(self):
        r = classify(14.0, "  12.0   -   16.0  ")
        assert r.status == LabStatus.NORMAL


# ===========================================================================
# B — Boundary value tests (exactly at lower / upper bound → NORMAL)
# ===========================================================================

class TestBoundaryValues:

    def test_value_exactly_at_lower_bound_is_normal(self):
        """Value == lower bound → NORMAL (inclusive)."""
        r = classify(12.0, "12.0 - 16.0")
        assert r.status == LabStatus.NORMAL, (
            f"Value at exact lower bound must be NORMAL, got {r.status}"
        )

    def test_value_exactly_at_upper_bound_is_normal(self):
        """Value == upper bound → NORMAL (inclusive)."""
        r = classify(16.0, "12.0 - 16.0")
        assert r.status == LabStatus.NORMAL, (
            f"Value at exact upper bound must be NORMAL, got {r.status}"
        )

    def test_value_just_below_lower_bound_is_low(self):
        """Value one floating-point step below lower bound → LOW."""
        r = classify(11.99, "12.0 - 16.0")
        assert r.status == LabStatus.LOW

    def test_value_just_above_upper_bound_is_high(self):
        """Value one floating-point step above upper bound → HIGH."""
        r = classify(16.01, "12.0 - 16.0")
        assert r.status == LabStatus.HIGH

    def test_value_exactly_at_upper_bound_of_upper_only_range(self):
        """'< 200': value == 200 → NORMAL (up to and including 200)."""
        r = classify(200.0, "< 200")
        assert r.status == LabStatus.NORMAL

    def test_value_exactly_at_lower_bound_of_lower_only_range(self):
        """'>= 50': value == 50 → NORMAL."""
        r = classify(50.0, ">= 50")
        assert r.status == LabStatus.NORMAL

    def test_integer_lower_bound_with_float_value(self):
        r = classify(135.0, "135 - 145")
        assert r.status == LabStatus.NORMAL

    def test_float_boundary_precision(self):
        """0.500 exactly at lower boundary of 0.5 - 5.0."""
        r = classify(0.5, "0.5 - 5.0")
        assert r.status == LabStatus.NORMAL

    def test_float_boundary_upper_precision(self):
        r = classify(5.0, "0.5 - 5.0")
        assert r.status == LabStatus.NORMAL


# ===========================================================================
# C — Upper-bound only ranges
# ===========================================================================

class TestUpperBoundOnly:

    def test_strict_less_than(self):
        r = classify(150.0, "< 200")
        assert r.status == LabStatus.NORMAL

    def test_strict_less_than_above(self):
        r = classify(250.0, "< 200")
        assert r.status == LabStatus.HIGH

    def test_less_than_equals(self):
        r = classify(200.0, "<= 200")
        assert r.status == LabStatus.NORMAL

    def test_unicode_leq(self):
        r = classify(200.0, "≤ 200")
        assert r.status == LabStatus.NORMAL

    def test_up_to_phrase(self):
        r = classify(150.0, "up to 200")
        assert r.status == LabStatus.NORMAL

    def test_up_to_phrase_exceeds(self):
        r = classify(201.0, "up to 200")
        assert r.status == LabStatus.HIGH

    def test_less_than_no_space(self):
        r = classify(99.0, "<100")
        assert r.status == LabStatus.NORMAL

    def test_less_than_equals_no_space(self):
        r = classify(100.0, "<=100")
        assert r.status == LabStatus.NORMAL


# ===========================================================================
# D — Lower-bound only ranges
# ===========================================================================

class TestLowerBoundOnly:

    def test_strict_greater_than(self):
        r = classify(60.0, "> 50")
        assert r.status == LabStatus.NORMAL

    def test_strict_greater_than_below(self):
        r = classify(40.0, "> 50")
        assert r.status == LabStatus.LOW

    def test_greater_than_equals(self):
        r = classify(50.0, ">= 50")
        assert r.status == LabStatus.NORMAL

    def test_unicode_geq(self):
        r = classify(50.0, "≥ 50")
        assert r.status == LabStatus.NORMAL

    def test_at_least_phrase(self):
        r = classify(60.0, "at least 50")
        assert r.status == LabStatus.NORMAL

    def test_at_least_phrase_below(self):
        r = classify(40.0, "at least 50")
        assert r.status == LabStatus.LOW

    def test_greater_than_no_space(self):
        r = classify(60.0, ">50")
        assert r.status == LabStatus.NORMAL


# ===========================================================================
# E — Correct LOW / NORMAL / HIGH assignment
# ===========================================================================

class TestLowNormalHigh:

    @pytest.mark.parametrize("value,expected", [
        (11.9, "LOW"),
        (12.0, "NORMAL"),   # boundary
        (14.0, "NORMAL"),
        (16.0, "NORMAL"),   # boundary
        (16.1, "HIGH"),
        (0.0,  "LOW"),
        (100.0, "HIGH"),
    ])
    def test_hemoglobin_classification(self, value, expected):
        r = classify(value, "12.0 - 16.0")
        assert r.status.value == expected, (
            f"classify({value}, '12.0 - 16.0') → {r.status.value}, expected {expected}"
        )

    @pytest.mark.parametrize("value,expected", [
        (69.0,  "LOW"),
        (70.0,  "NORMAL"),  # boundary
        (100.0, "NORMAL"),
        (100.1, "HIGH"),
    ])
    def test_glucose_classification(self, value, expected):
        r = classify(value, "70 - 100 mg/dL")
        assert r.status.value == expected

    @pytest.mark.parametrize("value,expected", [
        (0.0,  "NORMAL"),   # 0 is within < 200
        (199.0, "NORMAL"),
        (200.0, "NORMAL"),  # boundary
        (201.0, "HIGH"),
    ])
    def test_total_cholesterol_upper_only(self, value, expected):
        r = classify(value, "< 200 mg/dL")
        assert r.status.value == expected


# ===========================================================================
# F — Missing / null / empty range → UNKNOWN
# ===========================================================================

class TestMissingRange:

    def test_none_range_is_unknown(self):
        r = classify(14.0, None)
        assert r.status == LabStatus.UNKNOWN

    def test_empty_string_range_is_unknown(self):
        r = classify(14.0, "")
        assert r.status == LabStatus.UNKNOWN

    def test_whitespace_only_range_is_unknown(self):
        r = classify(14.0, "   ")
        assert r.status == LabStatus.UNKNOWN

    def test_missing_range_is_not_assessable(self):
        r = classify(14.0, None)
        assert r.range_assessable is False

    def test_missing_range_preserves_none(self):
        r = classify(14.0, None)
        assert r.raw_range_preserved is None


# ===========================================================================
# G — Non-assessable phrases → UNKNOWN
# ===========================================================================

class TestNonAssessablePhrases:

    @pytest.mark.parametrize("raw_range", [
        "Not established",
        "Reference range not established",
        "Not provided",
        "Not available",
        "Unavailable",
        "Pending",
        "See note",
        "See report",
        "Variable",
        "Varies",
        "See laboratory-specific",
        "See lab-specific",
        "Contact laboratory",
        "Method dependent",
        "None",
        # Case variations
        "NOT ESTABLISHED",
        "not established",
        "Not Established",
        # With surrounding text
        "Reference range not available at this time",
    ])
    def test_non_assessable_phrase_yields_unknown(self, raw_range):
        r = classify(14.0, raw_range)
        assert r.status == LabStatus.UNKNOWN, (
            f"Expected UNKNOWN for '{raw_range}', got {r.status}"
        )

    def test_non_assessable_is_not_range_assessable(self):
        r = classify(14.0, "Not established")
        assert r.range_assessable is False

    def test_normal_range_not_established_legacy(self):
        """Existing test case from previous suite must still pass."""
        status, desc = ReferenceRangeService.evaluate_status(
            value=42.0,
            raw_range="Normal range not established"
        )
        assert status == "UNKNOWN"


# ===========================================================================
# H — Qualitative ranges → UNKNOWN
# ===========================================================================

class TestQualitativeRanges:

    @pytest.mark.parametrize("raw_range", [
        "Negative",
        "Positive",
        "Reactive",
        "Non-reactive",
        "Detected",
        "Not detected",
        "Absent",
        "Present",
        "Trace",
        "Equivocal",
        "Indeterminate",
        "Borderline",
    ])
    def test_qualitative_range_is_unknown(self, raw_range):
        r = classify(1.0, raw_range)
        assert r.status == LabStatus.UNKNOWN, (
            f"Expected UNKNOWN for qualitative '{raw_range}', got {r.status}"
        )

    def test_qualitative_range_marks_not_assessable(self):
        r = classify(1.0, "Negative")
        assert r.range_assessable is False


# ===========================================================================
# I — Unparseable / ambiguous ranges → UNKNOWN
# ===========================================================================

class TestUnparseableRanges:

    def test_text_only_range_is_unknown(self):
        r = classify(14.0, "Within acceptable limits")
        assert r.status == LabStatus.UNKNOWN

    def test_inverted_range_is_unknown(self):
        """Range where low > high cannot be parsed as a valid interval."""
        r = classify(14.0, "16.0 - 12.0")
        assert r.status == LabStatus.UNKNOWN

    def test_single_number_without_operator_is_unknown(self):
        """A bare number is ambiguous — is it a threshold or a value?"""
        r = classify(14.0, "14.0")
        assert r.status == LabStatus.UNKNOWN

    def test_words_with_partial_number_is_unknown(self):
        r = classify(14.0, "approximately 12 to 16")
        # "approximately" makes this ambiguous for strict parsing
        # System may or may not parse "12 to 16" — either NORMAL or UNKNOWN is acceptable
        # What we MUST NOT have is a wrong status
        assert r.status in {LabStatus.NORMAL, LabStatus.UNKNOWN}

    def test_range_with_percent_sign_only(self):
        r = classify(14.0, "%")
        assert r.status == LabStatus.UNKNOWN

    def test_empty_parens_is_unknown(self):
        r = classify(14.0, "()")
        assert r.status == LabStatus.UNKNOWN


# ===========================================================================
# J — Missing value (None) → UNKNOWN
# ===========================================================================

class TestMissingValue:

    def test_none_value_with_valid_range_is_unknown(self):
        r = classify(None, "12.0 - 16.0")
        assert r.status == LabStatus.UNKNOWN

    def test_none_value_with_none_range_is_unknown(self):
        r = classify(None, None)
        assert r.status == LabStatus.UNKNOWN

    def test_none_value_with_non_assessable_range_is_unknown(self):
        r = classify(None, "Not established")
        assert r.status == LabStatus.UNKNOWN

    def test_none_value_reason_mentions_absent(self):
        r = classify(None, "12.0 - 16.0")
        assert "absent" in r.reason.lower() or "non-numeric" in r.reason.lower()


# ===========================================================================
# K — Unit-suffixed ranges (unit stripped, numeric value extracted correctly)
# ===========================================================================

class TestUnitSuffixedRanges:

    def test_gdl_unit_suffix(self):
        r = classify(14.0, "12.0 - 16.0 g/dL")
        assert r.status == LabStatus.NORMAL
        assert r.parsed_low == 12.0
        assert r.parsed_high == 16.0

    def test_mgdl_unit_suffix(self):
        r = classify(90.0, "70 - 100 mg/dL")
        assert r.status == LabStatus.NORMAL

    def test_mmol_unit_suffix(self):
        r = classify(6.0, "3.5 - 5.5 mmol/L")
        assert r.status == LabStatus.HIGH

    def test_percent_unit(self):
        r = classify(40.0, "35 - 45 %")
        assert r.status == LabStatus.NORMAL

    def test_cells_unit(self):
        r = classify(8.0, "4.0 - 11.0 x10^9/L")
        assert r.status == LabStatus.NORMAL

    def test_meql_unit(self):
        r = classify(140.0, "136 - 145 mEq/L")
        assert r.status == LabStatus.NORMAL

    def test_unit_only_range(self):
        """A string that is just a unit with no numbers is UNKNOWN."""
        r = classify(14.0, "g/dL")
        assert r.status == LabStatus.UNKNOWN

    def test_raw_range_preserved_with_unit(self):
        """Unit-stripping must NOT modify raw_range_preserved."""
        raw = "12.0 - 16.0 g/dL"
        r = classify(14.0, raw)
        assert r.raw_range_preserved == raw


# ===========================================================================
# L — Locale comma-decimal ranges
# ===========================================================================

class TestLocaleCommaDecimal:

    def test_comma_decimal_interval(self):
        """Some European lab reports use "12,0 - 16,0" notation."""
        r = classify(14.0, "12,0 - 16,0")
        assert r.status == LabStatus.NORMAL

    def test_comma_decimal_low_result(self):
        r = classify(11.0, "12,0 - 16,0")
        assert r.status == LabStatus.LOW

    def test_comma_decimal_high_result(self):
        r = classify(17.0, "12,5 - 16,5")
        assert r.status == LabStatus.HIGH


# ===========================================================================
# M — Parenthesised and bracket-enclosed ranges
# ===========================================================================

class TestEnclosedRanges:

    def test_parenthesised_range(self):
        r = classify(14.0, "(12.0 - 16.0)")
        assert r.status == LabStatus.NORMAL

    def test_bracket_range(self):
        r = classify(14.0, "[12.0 - 16.0]")
        assert r.status == LabStatus.NORMAL

    def test_parenthesised_with_unit(self):
        r = classify(14.0, "(12.0 - 16.0 g/dL)")
        assert r.status == LabStatus.NORMAL

    def test_parenthesised_upper_bound(self):
        r = classify(150.0, "(< 200)")
        assert r.status == LabStatus.NORMAL


# ===========================================================================
# N — Negative numeric values (temperature, special assays)
# ===========================================================================

class TestNegativeValues:

    def test_negative_value_below_negative_range(self):
        """Temperature-scale lab assay: range -0.5 to 0.5, value -1.0 → LOW."""
        r = classify(-1.0, "-0.5 - 0.5")
        # Parser handles negatives in the raw range text if pattern matches
        # This is an edge case — if not parsed, UNKNOWN is acceptable
        assert r.status in {LabStatus.LOW, LabStatus.UNKNOWN}

    def test_negative_value_in_normal_range(self):
        r = classify(-0.3, "-0.5 - 0.5")
        assert r.status in {LabStatus.NORMAL, LabStatus.UNKNOWN}


# ===========================================================================
# O — Large and very small floating-point values
# ===========================================================================

class TestPrecisionEdgeCases:

    def test_very_small_value(self):
        r = classify(0.001, "0.0 - 0.01")
        assert r.status == LabStatus.NORMAL

    def test_very_large_value(self):
        r = classify(999999.0, "100000 - 200000")
        assert r.status == LabStatus.HIGH

    def test_very_small_range(self):
        r = classify(0.005, "0.001 - 0.010")
        assert r.status == LabStatus.NORMAL

    def test_zero_value_within_range(self):
        r = classify(0.0, "0.0 - 5.0")
        assert r.status == LabStatus.NORMAL

    def test_zero_value_below_range(self):
        r = classify(0.0, "1.0 - 5.0")
        assert r.status == LabStatus.LOW


# ===========================================================================
# P — Inverted range (low > high)
# ===========================================================================

class TestInvertedRange:

    def test_inverted_range_is_unparseable(self):
        """An inverted range like '16 - 12' is logically invalid → UNKNOWN."""
        r = classify(14.0, "16.0 - 12.0")
        # Parser must not accept inverted ranges as valid
        assert r.status == LabStatus.UNKNOWN, (
            "Inverted range must yield UNKNOWN, not a spurious status"
        )

    def test_inverted_range_marks_not_assessable(self):
        r = classify(14.0, "16.0 - 12.0")
        assert r.range_assessable is False


# ===========================================================================
# Q — Anti-hallucination: AI asserted range not in source → grounding strips it
# ===========================================================================

class TestAntiHallucinationIntegration:

    def test_validator_strips_hallucinated_range(self):
        """
        When the BusinessValidator strips a hallucinated range, the downstream
        classify() call receives raw_range=None → UNKNOWN.
        This test verifies that the final status is correct after stripping.
        """
        # Simulate post-strip state: range set to None
        r = classify(10.2, None)
        assert r.status == LabStatus.UNKNOWN
        assert r.raw_range_preserved is None

    def test_status_after_grounding_failure(self):
        """After anti-hallucination, document processor calls classify(v, None)."""
        for value in [10.2, 14.0, 16.5, 0.0]:
            r = classify(value, None)
            assert r.status == LabStatus.UNKNOWN, (
                f"After range stripping, classify({value}, None) must be UNKNOWN"
            )


# ===========================================================================
# R — ReferenceRangeService backward-compatible API
# ===========================================================================

class TestBackwardCompatibleAPI:

    def test_evaluate_status_returns_string_tuple(self):
        status, desc = ReferenceRangeService.evaluate_status(
            value=11.2,
            raw_range="12.0–15.5 g/dL"
        )
        assert status == "LOW"
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_evaluate_status_normal(self):
        status, _ = ReferenceRangeService.evaluate_status(14.0, "12.0–15.5 g/dL")
        assert status == "NORMAL"

    def test_evaluate_status_high(self):
        status, _ = ReferenceRangeService.evaluate_status(16.2, "12.0–15.5 g/dL")
        assert status == "HIGH"

    def test_evaluate_status_none_range(self):
        status, desc = ReferenceRangeService.evaluate_status(11.2, None)
        assert status == "UNKNOWN"
        assert "not provided" in desc.lower()

    def test_evaluate_status_see_laboratory_specific(self):
        """Regression: legacy test from Phase 2."""
        status, _ = ReferenceRangeService.evaluate_status(85.0, "See laboratory-specific range")
        assert status == "UNKNOWN"

    def test_parse_numeric_range_standard_interval(self):
        low, high = ReferenceRangeService.parse_numeric_range("12.0 - 16.0")
        assert low == 12.0
        assert high == 16.0

    def test_parse_numeric_range_en_dash(self):
        low, high = ReferenceRangeService.parse_numeric_range("12.0–16.0")
        assert low == 12.0
        assert high == 16.0

    def test_parse_numeric_range_none(self):
        low, high = ReferenceRangeService.parse_numeric_range(None)
        assert low is None
        assert high is None

    def test_parse_numeric_range_qualitative(self):
        low, high = ReferenceRangeService.parse_numeric_range("Negative")
        assert low is None
        assert high is None

    def test_parse_numeric_range_non_assessable(self):
        low, high = ReferenceRangeService.parse_numeric_range("Not established")
        assert low is None
        assert high is None


# ===========================================================================
# S — ClassificationResult datatype guarantees
# ===========================================================================

class TestClassificationResultType:

    def test_result_is_immutable(self):
        r = classify(14.0, "12.0 - 16.0")
        with pytest.raises((AttributeError, TypeError)):
            r.status = LabStatus.LOW  # type: ignore[misc]

    def test_result_has_all_fields(self):
        r = classify(14.0, "12.0 - 16.0")
        assert hasattr(r, 'status')
        assert hasattr(r, 'reason')
        assert hasattr(r, 'parsed_low')
        assert hasattr(r, 'parsed_high')
        assert hasattr(r, 'raw_range_preserved')
        assert hasattr(r, 'range_assessable')

    def test_assessable_flag_true_for_valid_range(self):
        r = classify(14.0, "12.0 - 16.0")
        assert r.range_assessable is True

    def test_assessable_flag_false_for_missing_range(self):
        r = classify(14.0, None)
        assert r.range_assessable is False

    def test_assessable_flag_false_for_qualitative(self):
        r = classify(1.0, "Negative")
        assert r.range_assessable is False

    def test_str_representation(self):
        r = classify(14.0, "12.0 - 16.0")
        s = str(r)
        assert "NORMAL" in s

    def test_reason_is_non_empty_string(self):
        for args in [
            (14.0, "12.0 - 16.0"),
            (11.0, "12.0 - 16.0"),
            (17.0, "12.0 - 16.0"),
            (14.0, None),
            (14.0, "Negative"),
            (None, "12.0 - 16.0"),
        ]:
            r = classify(*args)
            assert isinstance(r.reason, str) and len(r.reason) > 0


# ===========================================================================
# T — Raw range preserved verbatim
# ===========================================================================

class TestRawRangePreservation:

    def test_raw_range_preserved_exact(self):
        raw = "12.0 - 16.0 g/dL"
        r = classify(14.0, raw)
        assert r.raw_range_preserved == raw

    def test_raw_range_preserved_with_units_unchanged(self):
        """Unit stripping during parsing must NOT modify raw_range_preserved."""
        raw = "70 - 100 mg/dL"
        r = classify(90.0, raw)
        assert r.raw_range_preserved == raw

    def test_raw_range_preserved_when_unparseable(self):
        raw = "Within acceptable limits"
        r = classify(14.0, raw)
        assert r.raw_range_preserved == raw

    def test_raw_range_preserved_when_non_assessable(self):
        raw = "Not established"
        r = classify(14.0, raw)
        assert r.raw_range_preserved == raw

    def test_raw_range_preserved_is_none_when_none_given(self):
        r = classify(14.0, None)
        assert r.raw_range_preserved is None

    def test_raw_range_preserved_does_not_trim_whitespace(self):
        """Verbatim preservation includes leading/trailing whitespace."""
        raw = "  12.0 - 16.0  "
        r = classify(14.0, raw)
        # Parser may still classify correctly even with whitespace
        assert r.raw_range_preserved == raw


# ===========================================================================
# U — Reason field content checks
# ===========================================================================

class TestReasonFieldContent:

    def test_low_reason_mentions_below(self):
        r = classify(11.0, "12.0 - 16.0")
        assert "below" in r.reason.lower()

    def test_high_reason_mentions_above(self):
        r = classify(17.0, "12.0 - 16.0")
        assert "above" in r.reason.lower()

    def test_normal_reason_mentions_within(self):
        r = classify(14.0, "12.0 - 16.0")
        assert "within" in r.reason.lower()

    def test_missing_range_reason_mentions_not_provided(self):
        r = classify(14.0, None)
        assert "not provided" in r.reason.lower()

    def test_non_assessable_reason_is_informative(self):
        r = classify(14.0, "Not established")
        assert len(r.reason) > 10

    def test_qualitative_reason_mentions_qualitative(self):
        r = classify(1.0, "Negative")
        assert "qualitative" in r.reason.lower()


# ===========================================================================
# V — Helper function unit tests (_parse_numeric_range, etc.)
# ===========================================================================

class TestParserHelpers:

    def test_parse_en_dash(self):
        low, high = _parse_numeric_range("12.0–16.0")
        assert (low, high) == (12.0, 16.0)

    def test_parse_to_separator(self):
        low, high = _parse_numeric_range("12.0 to 16.0")
        assert (low, high) == (12.0, 16.0)

    def test_parse_slash_separator(self):
        low, high = _parse_numeric_range("12 / 16")
        assert (low, high) == (12.0, 16.0)

    def test_parse_less_than(self):
        low, high = _parse_numeric_range("< 200")
        assert low == 0.0
        assert high == 200.0

    def test_parse_less_than_equals(self):
        low, high = _parse_numeric_range("<= 200")
        assert high == 200.0

    def test_parse_greater_than(self):
        low, high = _parse_numeric_range("> 50")
        assert low == 50.0
        assert high is None

    def test_parse_greater_than_equals(self):
        low, high = _parse_numeric_range(">= 50")
        assert low == 50.0

    def test_parse_comma_decimal(self):
        low, high = _parse_numeric_range("12,0 - 16,0")
        assert (low, high) == (12.0, 16.0)

    def test_parse_inverted_is_none(self):
        low, high = _parse_numeric_range("16 - 12")
        assert low is None and high is None

    def test_parse_qualitative_is_none(self):
        low, high = _parse_numeric_range("Negative")
        assert low is None and high is None

    def test_parse_non_assessable_is_none(self):
        low, high = _parse_numeric_range("Not established")
        assert low is None and high is None

    def test_parse_empty_is_none(self):
        low, high = _parse_numeric_range("")
        assert low is None and high is None

    def test_is_qualitative_negative(self):
        assert _is_qualitative("negative") is True

    def test_is_qualitative_positive(self):
        assert _is_qualitative("positive") is True

    def test_is_qualitative_numeric_is_false(self):
        assert _is_qualitative("12.0 - 16.0") is False

    def test_is_non_assessable_not_established(self):
        assert _is_non_assessable("not established") is True

    def test_is_non_assessable_numeric_is_false(self):
        assert _is_non_assessable("12.0 - 16.0") is False


# ===========================================================================
# W — Regression tests (existing Phase 2 tests must still pass exactly)
# ===========================================================================

class TestPhase2Regression:

    def test_hemoglobin_low_regression(self):
        status, _ = ReferenceRangeService.evaluate_status(11.2, "12.0–15.5 g/dL")
        assert status == "LOW"

    def test_hemoglobin_normal_regression(self):
        status, _ = ReferenceRangeService.evaluate_status(14.0, "12.0–15.5 g/dL")
        assert status == "NORMAL"

    def test_hemoglobin_high_regression(self):
        status, _ = ReferenceRangeService.evaluate_status(16.2, "12.0–15.5 g/dL")
        assert status == "HIGH"

    def test_none_range_regression(self):
        status, desc = ReferenceRangeService.evaluate_status(11.2, None)
        assert status == "UNKNOWN"
        assert "not provided" in desc.lower()

    def test_not_established_regression(self):
        status, _ = ReferenceRangeService.evaluate_status(42.0, "Normal range not established")
        assert status == "UNKNOWN"

    def test_see_laboratory_specific_regression(self):
        status, _ = ReferenceRangeService.evaluate_status(85.0, "See laboratory-specific range")
        assert status == "UNKNOWN"
