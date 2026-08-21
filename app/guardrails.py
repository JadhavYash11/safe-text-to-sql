"""Deterministic SQL safety checks. The database's read-only role is defense in depth."""

import re

import sqlparse

from app.config import Settings
from app.models import GuardrailWarning


class SQLSafetyError(ValueError):
    def __init__(self, rule: str, message: str):
        super().__init__(message)
        self.rule = rule
        self.message = message


_BLOCKED_KEYWORDS = (
    "ALTER",
    "ANALYZE",
    "ATTACH",
    "CALL",
    "COPY",
    "CREATE",
    "DELETE",
    "DETACH",
    "DROP",
    "GRANT",
    "INSERT",
    "INSTALL",
    "LOAD",
    "MERGE",
    "PRAGMA",
    "REPLACE",
    "REVOKE",
    "SET",
    "TRUNCATE",
    "UPDATE",
    "VACUUM",
)


def _subquery_depth(sql: str) -> int:
    """Count SELECT/WITH expressions inside parentheses (a conservative approximation)."""
    return len(re.findall(r"\(\s*(?:SELECT|WITH)\b", sql, flags=re.IGNORECASE))


def validate_and_limit(sql: str, settings: Settings) -> tuple[str, list[GuardrailWarning]]:
    """Reject unsafe statements and ensure an explicit, bounded output size."""
    statements = [statement for statement in sqlparse.split(sql) if statement.strip()]
    if len(statements) != 1:
        raise SQLSafetyError("single_statement", "Only one SQL statement may be executed.")

    normalized = sqlparse.format(statements[0], strip_comments=True).strip().rstrip(";")
    if not re.match(r"^(SELECT|WITH)\b", normalized, re.IGNORECASE):
        raise SQLSafetyError("read_only", "Only SELECT queries and SELECT CTEs are allowed.")
    for keyword in _BLOCKED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", normalized, re.IGNORECASE):
            raise SQLSafetyError("blocked_keyword", f"The {keyword} operation is not allowed.")

    depth = _subquery_depth(normalized)
    if depth > settings.max_subquery_depth:
        raise SQLSafetyError(
            "subquery_depth",
            f"Query has {depth} nested subqueries; maximum is {settings.max_subquery_depth}.",
        )

    warnings: list[GuardrailWarning] = []
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", normalized, re.IGNORECASE)
    if limit_match:
        requested_limit = int(limit_match.group(1))
        if requested_limit > settings.max_rows:
            normalized = (
                normalized[: limit_match.start(1)]
                + str(settings.max_rows)
                + normalized[limit_match.end(1) :]
            )
            warnings.append(
                GuardrailWarning(
                    rule="row_limit",
                    message=f"LIMIT was capped from {requested_limit} to {settings.max_rows} rows.",
                )
            )
    else:
        normalized = f"{normalized} LIMIT {settings.max_rows}"
        warnings.append(
            GuardrailWarning(
                rule="row_limit", message=f"Added mandatory LIMIT {settings.max_rows}."
            )
        )
    return normalized, warnings


def reject_large_estimate(explain_plan: str, settings: Settings) -> None:
    """Reject a plan whose displayed DuckDB estimate breaches the configured budget."""
    estimates = re.findall(r"~\s*([\d,]+)\s+rows", explain_plan, flags=re.IGNORECASE)
    if not estimates:
        return
    largest_estimate = max(int(value.replace(",", "")) for value in estimates)
    if largest_estimate > settings.max_estimated_rows:
        raise SQLSafetyError(
            "estimated_scan",
            f"Estimated scan of {largest_estimate:,} rows exceeds "
            f"the {settings.max_estimated_rows:,}-row budget.",
        )

