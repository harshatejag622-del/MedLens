"""
Deterministic Laboratory Reference-Range Classification Engine
==============================================================
Phase 6 — MedLens

DESIGN PRINCIPLES
-----------------
1. The APPLICATION determines the lab status (LOW / NORMAL / HIGH / UNKNOWN).
   The AI only extracts the raw reference range string from the source document.

2. NEVER invent a reference range.
   NEVER use a hardcoded medical reference range.
   NEVER use external medical knowledge to fill a missing range.

3. Preserve the raw reference range text exactly as extracted from the source.

4. Classification is purely deterministic and independently testable:
   same (value, raw_range) → same (status, reason) every time, with zero
   dependence on AI, database, or network state.

STATUS RULES
------------
Given a numeric value V and parsed bounds [L, H]:

  V is None                          → UNKNOWN
  raw_range is None or empty         → UNKNOWN
  raw_range is qualitative / opaque  → UNKNOWN
  raw_range is not safely parseable  → UNKNOWN

  L present, H present:
    V < L          → LOW
    L <= V <= H    → NORMAL   (inclusive both ends — boundary values are NORMAL)
    V > H          → HIGH

  H present only (e.g. "< 200"):
    V <= H         → NORMAL
    V > H          → HIGH

  L present only (e.g. "> 50"):
    V >= L         → NORMAL
    V < L          → LOW

SUPPORTED RANGE FORMATS
-----------------------
  "12.0 - 16.0"           standard interval with hyphen
  "12.0–16.0"             en-dash interval
  "12.0—16.0"             em-dash interval
  "12.0 to 16.0"          word separator
  "(12.0 - 16.0)"         parenthesised
  "[12.0 - 16.0]"         bracket-enclosed
  "12.0 / 16.0"           slash-separated
  "< 200"                 strict upper bound
  "<= 200"                inclusive upper bound
  "≤ 200"                 unicode inclusive upper bound
  "up to 200"             upper bound phrase
  "> 50"                  strict lower bound
  ">= 50"                 inclusive lower bound
  "≥ 50"                  unicode inclusive lower bound
  "Negative"              qualitative → UNKNOWN
  "Reactive"              qualitative → UNKNOWN
  "See note"              non-assessable → UNKNOWN
  "Not established"       non-assessable → UNKNOWN
  "12.0 - 16.0 g/dL"     with trailing unit (unit stripped before parse)
  "12,0 - 16,0"           locale comma-decimal (normalised)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Status type
# ---------------------------------------------------------------------------

class LabStatus(str, Enum):
    LOW     = "LOW"
    NORMAL  = "NORMAL"
    HIGH    = "HIGH"
    UNKNOWN = "UNKNOWN"


StatusType = LabStatus   # backward-compatible alias


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassificationResult:
    """
    Fully typed, immutable result of reference-range classification.
    Carries every piece of information needed for clinical display and audit.
    """
    status: LabStatus
    reason: str

    # Parsed bounds (None if not derivable)
    parsed_low: Optional[float]
    parsed_high: Optional[float]

    # The raw string preserved verbatim from the source document
    raw_range_preserved: Optional[str]

    # Whether the range was parseable at all
    range_assessable: bool

    def __str__(self) -> str:
        return f"[{self.status.value}] {self.reason}"


# ---------------------------------------------------------------------------
# Non-assessable phrase table
# ---------------------------------------------------------------------------

# Phrases that indicate the range is explicitly acknowledged as unavailable.
# These are matched as substrings (case-insensitive) against the raw range text.
NON_ASSESSABLE_PHRASES: Tuple[str, ...] = (
    "not established",
    "not provided",
    "not applicable",
    "not available",
    "see laboratory-specific",
    "see lab-specific",
    "see laboratory specific",
    "see lab specific",
    "see note",
    "see report",
    "see attachment",
    "reference range not established",
    "reference range not available",
    "no reference range",
    "unavailable",
    "pending",
    "variable",
    "varies",
    "contact laboratory",
    "consult laboratory",
    "method dependent",
    "assay dependent",
    "none",
)

# Purely qualitative result words — result is interpretive, not numeric.
QUALITATIVE_WORDS: Tuple[str, ...] = (
    "negative",
    "positive",
    "reactive",
    "non-reactive",
    "nonreactive",
    "detected",
    "not detected",
    "absent",
    "present",
    "trace",
    "equivocal",
    "indeterminate",
    "borderline",
    "weakly reactive",
    "strongly reactive",
    "normal",         # standalone "Normal" range is ambiguous — require numbers
    "abnormal",
)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Pre-compiled patterns (in decreasing specificity order)
_INTERVAL_PATTERN = re.compile(
    r"""
    (?:^|[\s([\[,;])          # preceded by start, whitespace, or bracket
    (?P<low>                  # lower bound
        [+-]?                 # optional sign
        [0-9]{1,6}            # integer part
        (?:[.,][0-9]{1,4})?   # optional decimal (dot or comma)
    )
    \s*
    (?:-{1,3}|–|—|to|/)      # separator: hyphen(s), en-dash, em-dash, "to", slash
    \s*
    (?P<high>                 # upper bound
        [+-]?
        [0-9]{1,6}
        (?:[.,][0-9]{1,4})?
    )
    (?=[\s)[\],;]|$|\s*[a-zA-Z%µ])   # followed by space, bracket, unit, or end
    """,
    re.VERBOSE | re.IGNORECASE,
)

_UPPER_BOUND_PATTERN = re.compile(
    r"(?:<|<=|≤|up\s+to|less\s+than(?:\s+or\s+equal\s+to)?)\s*"
    r"(?P<high>[0-9]{1,6}(?:[.,][0-9]{1,4})?)",
    re.IGNORECASE,
)

_LOWER_BOUND_PATTERN = re.compile(
    r"(?:>|>=|≥|greater\s+than(?:\s+or\s+equal\s+to)?|at\s+least)\s*"
    r"(?P<low>[0-9]{1,6}(?:[.,][0-9]{1,4})?)",
    re.IGNORECASE,
)


def _normalise_decimal(s: str) -> float:
    """Parse a numeric string that may use comma as decimal separator."""
    # Replace locale comma-decimal (e.g. "12,5" → "12.5") only when it's
    # clearly a decimal separator (single comma between digits, not thousands).
    # Heuristic: if exactly one comma and digits both sides with ≤ 4 after:
    comma_decimal = re.match(r'^[+-]?[0-9]{1,6},[0-9]{1,4}$', s.strip())
    if comma_decimal:
        s = s.replace(',', '.')
    return float(s.replace(',', ''))   # strip remaining commas (thousands)


def _is_qualitative(cleaned: str) -> bool:
    """Return True if the raw range text is a qualitative word/phrase."""
    # Must be substantially composed of qualitative words
    for word in QUALITATIVE_WORDS:
        # Match whole-word or full string
        if re.fullmatch(r'\s*' + re.escape(word) + r'(\s+\w+)?\s*', cleaned, re.IGNORECASE):
            return True
    return False


def _is_non_assessable(cleaned: str) -> bool:
    """Return True if the raw range contains an explicit non-assessable phrase."""
    for phrase in NON_ASSESSABLE_PHRASES:
        if phrase in cleaned:
            return True
    return False


def _parse_numeric_range(raw_range: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse raw_range text into (low, high) float bounds.

    Returns:
        (low, high)  — both or either may be None if that bound is absent.
        (None, None) — if the range is not parseable as numeric bounds.

    Never raises. Never infers. Never uses medical knowledge.
    """
    cleaned = raw_range.strip().lower()

    if not cleaned:
        return None, None

    if _is_non_assessable(cleaned):
        return None, None

    if _is_qualitative(cleaned):
        return None, None

    # Strip common unit suffixes to simplify parsing
    # (units are informational only; we keep them in raw_range_preserved)
    stripped = re.sub(
        r'\s*(?:g/dL|g/L|mg/dL|mg/L|mmol/L|µmol/L|umol/L|nmol/L|pmol/L'
        r'|mEq/L|mIU/L|µIU/mL|uIU/mL|IU/L|U/L|%|cells/µL|cells/uL'
        r'|x10\^?[39]/[µu]L|/µL|/uL|K/µL|K/uL|fL|pg|g|mg|µg|ug'
        r'|mmHg|bpm|sec|s|min|h|days?|weeks?|months?)$',
        '',
        raw_range.strip(),
        flags=re.IGNORECASE,
    ).strip()

    # Pattern 1: Interval (low – high)
    m = _INTERVAL_PATTERN.search(stripped)
    if m:
        try:
            low = _normalise_decimal(m.group('low'))
            high = _normalise_decimal(m.group('high'))
            if low <= high:
                return low, high
            # Inverted: could be a single-bound written oddly — fall through
        except (ValueError, TypeError):
            pass

    # Pattern 2: Upper-bound only (< 200, <= 200, ≤ 200, up to 200)
    m = _UPPER_BOUND_PATTERN.search(stripped)
    if m:
        try:
            high = _normalise_decimal(m.group('high'))
            return 0.0, high   # Implied lower bound of 0 for one-sided upward ranges
        except (ValueError, TypeError):
            pass

    # Pattern 3: Lower-bound only (> 50, >= 50, ≥ 50, at least 50)
    m = _LOWER_BOUND_PATTERN.search(stripped)
    if m:
        try:
            low = _normalise_decimal(m.group('low'))
            return low, None
        except (ValueError, TypeError):
            pass

    # Could not parse — range is present but not numerically interpretable
    return None, None


# ---------------------------------------------------------------------------
# Public classification API
# ---------------------------------------------------------------------------

def classify(
    value: Optional[float],
    raw_range: Optional[str],
) -> ClassificationResult:
    """
    Classify a lab result value against its source-document reference range.

    This is the single authoritative entry-point for lab status determination.
    The AI extracts `raw_range` from the document; this function decides status.

    Args:
        value:     Numeric lab value (float) or None if non-numeric / missing.
        raw_range: Raw reference range string exactly as extracted from the
                   source document. None or empty string if absent.

    Returns:
        ClassificationResult with status, reason, parsed bounds, and metadata.

    Rules (see module docstring for the full specification):
        value is None          → UNKNOWN
        raw_range is absent    → UNKNOWN
        range is qualitative   → UNKNOWN
        range not parseable    → UNKNOWN
        value < low            → LOW
        low <= value <= high   → NORMAL  (boundary values are NORMAL)
        value > high           → HIGH
    """
    preserved = raw_range  # always preserve verbatim

    # ── Rule 1: value is None ─────────────────────────────────────────────
    if value is None:
        return ClassificationResult(
            status=LabStatus.UNKNOWN,
            reason="Test value is absent or non-numeric; classification not possible.",
            parsed_low=None,
            parsed_high=None,
            raw_range_preserved=preserved,
            range_assessable=False,
        )

    # ── Rule 2: range is absent ───────────────────────────────────────────
    if raw_range is None or not str(raw_range).strip():
        return ClassificationResult(
            status=LabStatus.UNKNOWN,
            reason="Reference range not provided in source report; status cannot be determined.",
            parsed_low=None,
            parsed_high=None,
            raw_range_preserved=preserved,
            range_assessable=False,
        )

    cleaned_range = raw_range.strip().lower()

    # ── Rule 3: explicitly non-assessable phrase ──────────────────────────
    if _is_non_assessable(cleaned_range):
        return ClassificationResult(
            status=LabStatus.UNKNOWN,
            reason=f"Source document states reference range is not assessable: '{raw_range}'.",
            parsed_low=None,
            parsed_high=None,
            raw_range_preserved=preserved,
            range_assessable=False,
        )

    # ── Rule 4: qualitative range ─────────────────────────────────────────
    if _is_qualitative(cleaned_range):
        return ClassificationResult(
            status=LabStatus.UNKNOWN,
            reason=f"Reference range '{raw_range}' is qualitative; numeric classification not possible.",
            parsed_low=None,
            parsed_high=None,
            raw_range_preserved=preserved,
            range_assessable=False,
        )

    # ── Rule 5: attempt numeric parse ────────────────────────────────────
    low, high = _parse_numeric_range(raw_range)

    if low is None and high is None:
        return ClassificationResult(
            status=LabStatus.UNKNOWN,
            reason=f"Reference range '{raw_range}' could not be parsed into numeric bounds.",
            parsed_low=None,
            parsed_high=None,
            raw_range_preserved=preserved,
            range_assessable=False,
        )

    # ── Rule 6: both bounds ───────────────────────────────────────────────
    if low is not None and high is not None:
        if value < low:
            return ClassificationResult(
                status=LabStatus.LOW,
                reason=f"Value {value} is below the source reference range ({low}–{high}).",
                parsed_low=low,
                parsed_high=high,
                raw_range_preserved=preserved,
                range_assessable=True,
            )
        elif value > high:
            return ClassificationResult(
                status=LabStatus.HIGH,
                reason=f"Value {value} is above the source reference range ({low}–{high}).",
                parsed_low=low,
                parsed_high=high,
                raw_range_preserved=preserved,
                range_assessable=True,
            )
        else:  # low <= value <= high  — boundary values are NORMAL
            return ClassificationResult(
                status=LabStatus.NORMAL,
                reason=f"Value {value} is within the source reference range ({low}–{high}).",
                parsed_low=low,
                parsed_high=high,
                raw_range_preserved=preserved,
                range_assessable=True,
            )

    # ── Rule 7: upper-bound only ──────────────────────────────────────────
    if low is not None and high is None:
        if value < low:
            return ClassificationResult(
                status=LabStatus.LOW,
                reason=f"Value {value} is below the source minimum threshold (≥ {low}).",
                parsed_low=low,
                parsed_high=None,
                raw_range_preserved=preserved,
                range_assessable=True,
            )
        else:
            return ClassificationResult(
                status=LabStatus.NORMAL,
                reason=f"Value {value} meets or exceeds the source minimum threshold (≥ {low}).",
                parsed_low=low,
                parsed_high=None,
                raw_range_preserved=preserved,
                range_assessable=True,
            )

    # ── Rule 8: lower-bound only (high is not None, low is 0.0 from parser)
    # _parse_numeric_range returns (0.0, H) for "< H" patterns
    if low == 0.0 and high is not None:
        if value > high:
            return ClassificationResult(
                status=LabStatus.HIGH,
                reason=f"Value {value} exceeds the source upper threshold (≤ {high}).",
                parsed_low=None,
                parsed_high=high,
                raw_range_preserved=preserved,
                range_assessable=True,
            )
        else:
            return ClassificationResult(
                status=LabStatus.NORMAL,
                reason=f"Value {value} is within the source upper threshold (≤ {high}).",
                parsed_low=None,
                parsed_high=high,
                raw_range_preserved=preserved,
                range_assessable=True,
            )

    # Fallback — should not be reached
    return ClassificationResult(
        status=LabStatus.UNKNOWN,
        reason="Status could not be determined from the available range information.",
        parsed_low=low,
        parsed_high=high,
        raw_range_preserved=preserved,
        range_assessable=False,
    )


# ---------------------------------------------------------------------------
# Backward-compatible class-based API (used by existing code)
# ---------------------------------------------------------------------------

class ReferenceRangeService:
    """
    Backward-compatible class-based wrapper around the functional API.
    Existing callers use ReferenceRangeService.evaluate_status() and
    ReferenceRangeService.parse_numeric_range().

    New code should prefer the top-level classify() function.
    """

    @staticmethod
    def parse_numeric_range(raw_range: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        """
        Parse raw reference range text strictly into (low, high) bounds.
        Returns (None, None) if the range is missing, qualitative, or ambiguous.
        Never infers or substitutes missing values.
        """
        if not raw_range or not isinstance(raw_range, str):
            return None, None
        return _parse_numeric_range(raw_range)

    @classmethod
    def evaluate_status(
        cls,
        value: Optional[float],
        raw_range: Optional[str],
        parsed_low: Optional[float] = None,
        parsed_high: Optional[float] = None,
    ) -> Tuple[str, str]:
        """
        Evaluate lab result status against the source reference range.

        Returns (status_string, reason_string) for backward compatibility.
        Delegates to the top-level classify() function.
        """
        # If caller pre-parsed bounds, build a synthetic range string to
        # route through the unified classifier
        if (parsed_low is not None or parsed_high is not None) and not raw_range:
            if parsed_low is not None and parsed_high is not None:
                raw_range = f"{parsed_low} - {parsed_high}"
            elif parsed_high is not None:
                raw_range = f"< {parsed_high}"
            elif parsed_low is not None:
                raw_range = f">= {parsed_low}"

        result = classify(value=value, raw_range=raw_range)
        return result.status.value, result.reason
