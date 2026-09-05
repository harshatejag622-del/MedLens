from typing import List, Dict, Optional
from app.models.clinical import LabResult
from app.schemas.clinical import LabComparisonItem

class ComparisonEngine:
    @staticmethod
    def compare_results(current: LabResult, previous: LabResult) -> LabComparisonItem:
        """
        Compares two lab results for the same test across time.
        Enforces Section 13 & Critical Case 7:
        - If units differ, comparison is blocked unless safe conversion is explicitly implemented.
        - Uses strictly neutral language without implying clinical improvement or worsening.
        """
        curr_unit = (current.unit or "").strip().lower()
        prev_unit = (previous.unit or "").strip().lower()

        # Check for unit compatibility
        units_match = (curr_unit == prev_unit) and (curr_unit != "")

        if not units_match and (curr_unit != "" or prev_unit != ""):
            return LabComparisonItem(
                test_name=current.test_name,
                current_value=current.value,
                current_value_text=current.value_text,
                current_unit=current.unit,
                current_date=current.report_date,
                current_status=current.status,
                current_range=current.raw_reference_range,
                previous_value=previous.value,
                previous_value_text=previous.value_text,
                previous_unit=previous.unit,
                previous_date=previous.report_date,
                previous_status=previous.status,
                previous_range=previous.raw_reference_range,
                change_absolute=None,
                change_percentage=None,
                comparison_note="Comparison unavailable because units differ.",
                safe_to_compare=False
            )

        # Both have matching units or both lack units
        if current.value is not None and previous.value is not None:
            abs_change = round(current.value - previous.value, 4)
            if previous.value != 0:
                pct_change = round(((current.value - previous.value) / abs(previous.value)) * 100, 2)
            else:
                pct_change = None

            unit_str = f" {current.unit}" if current.unit else ""
            change_sign = "+" if abs_change > 0 else ""
            pct_str = f" ({change_sign}{pct_change}%)" if pct_change is not None else ""
            note = f"Value changed from {previous.value_text} to {current.value_text}{unit_str}{pct_str}."

            return LabComparisonItem(
                test_name=current.test_name,
                current_value=current.value,
                current_value_text=current.value_text,
                current_unit=current.unit,
                current_date=current.report_date,
                current_status=current.status,
                current_range=current.raw_reference_range,
                previous_value=previous.value,
                previous_value_text=previous.value_text,
                previous_unit=previous.unit,
                previous_date=previous.report_date,
                previous_status=previous.status,
                previous_range=previous.raw_reference_range,
                change_absolute=abs_change,
                change_percentage=pct_change,
                comparison_note=note,
                safe_to_compare=True
            )

        return LabComparisonItem(
            test_name=current.test_name,
            current_value=current.value,
            current_value_text=current.value_text,
            current_unit=current.unit,
            current_date=current.report_date,
            current_status=current.status,
            current_range=current.raw_reference_range,
            previous_value=previous.value,
            previous_value_text=previous.value_text,
            previous_unit=previous.unit,
            previous_date=previous.report_date,
            previous_status=previous.status,
            previous_range=previous.raw_reference_range,
            change_absolute=None,
            change_percentage=None,
            comparison_note=f"Qualitative values: previous was '{previous.value_text}', current is '{current.value_text}'.",
            safe_to_compare=True
        )

    @classmethod
    def compare_patient_reports(cls, results: List[LabResult]) -> List[LabComparisonItem]:
        """
        Groups results by test_name and pairs the latest result with the immediate prior result.
        """
        grouped: Dict[str, List[LabResult]] = {}
        for res in sorted(results, key=lambda x: x.report_date or "", reverse=True):
            grouped.setdefault(res.test_name.lower(), []).append(res)

        comparisons: List[LabComparisonItem] = []
        for test_key, test_results in grouped.items():
            if len(test_results) >= 2:
                # Latest vs Previous
                curr = test_results[0]
                prev = test_results[1]
                comparisons.append(cls.compare_results(curr, prev))

        return comparisons
