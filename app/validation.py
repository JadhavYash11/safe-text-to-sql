"""Post-execution checks and confidence-score calculation."""

from collections.abc import Sequence
from typing import Any

from app.models import CheckResult


def sanity_checks(rows: Sequence[dict[str, Any]], row_limit: int) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if not rows:
        checks.append(
            CheckResult(
                name="result_sanity", score=0.65, message="Query returned no rows; verify filters."
            )
        )
        return checks

    if len(rows) == row_limit:
        checks.append(
            CheckResult(
                name="result_truncation",
                score=0.8,
                message=f"Result reached the {row_limit}-row cap; output may be truncated.",
            )
        )
    else:
        checks.append(
            CheckResult(
                name="result_size", score=1.0, message=f"Returned {len(rows)} rows within the safety cap."
            )
        )

    values = [value for row in rows for value in row.values()]
    null_fraction = sum(value is None for value in values) / max(len(values), 1)
    null_score = 1.0 if null_fraction <= 0.35 else 0.55
    checks.append(
        CheckResult(
            name="null_density",
            score=null_score,
            message=(
                f"{null_fraction:.0%} of returned values are NULL."
                if null_fraction > 0.35
                else "No concerning NULL density detected."
            ),
        )
    )
    return checks


def weighted_confidence(checks: list[CheckResult], generation_confidence: float) -> float:
    """Keep the formula visible and easy to tune as eval data accumulates."""
    score_by_name = {check.name: check.score for check in checks}
    alignment = score_by_name.get("back_translation", 0.6)
    sanity = sum(check.score for check in checks if check.name != "back_translation") / max(
        len([check for check in checks if check.name != "back_translation"]), 1
    )
    agreement = score_by_name.get("multi_query_agreement", 0.75)
    return round(
        min(1.0, max(0.0, 0.30 * generation_confidence + 0.35 * alignment + 0.20 * sanity + 0.15 * agreement)),
        2,
    )

