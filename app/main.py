"""FastAPI entrypoint for guarded natural-language database queries."""

from contextlib import asynccontextmanager
from collections import Counter
import json
from pathlib import Path
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine, seed_demo_database
from app.guardrails import SQLSafetyError, reject_large_estimate, validate_and_limit
from app.history import QueryHistory, persist_feedback
from app.llm import GenerationError, get_generator
from app.models import (
    CheckResult,
    ClarificationNeeded,
    ClarificationOption,
    FeedbackRequest,
    QueryRequest,
    QueryResponse,
    SchemaResponse,
)
from app.schema import extract_schema, relevant_schema
from app.validation import sanity_checks, weighted_confidence


history = QueryHistory()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().should_seed_demo_data:
        seed_demo_database()
    yield


app = FastAPI(
    title="Safe Text-to-SQL",
    version="0.1.0",
    description="Schema-aware SQL generation with deterministic safety checks and validation.",
    lifespan=lifespan,
)

WEB_APP = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


def get_schema() -> SchemaResponse:
    return extract_schema(get_engine())


def _ambiguity(question: str) -> ClarificationNeeded | None:
    normalized = question.lower()
    if "revenue" in normalized and not any(
        marker in normalized for marker in ("gross", "net", "total", "after discount")
    ):
        return ClarificationNeeded(
            message="Revenue is ambiguous in this schema: should discounts be included?",
            options=[
                ClarificationOption(
                    label="Gross revenue",
                    description="Sum orders.total_amount before discounts.",
                    example_question="Show gross revenue by month",
                ),
                ClarificationOption(
                    label="Net revenue",
                    description="Sum orders.net_amount after discounts.",
                    example_question="Show net revenue by month",
                ),
            ],
        )
    return None


def _plan_text(connection, sql: str) -> str:
    plan_rows = connection.execute(text(f"EXPLAIN {sql}")).fetchall()
    return "\n".join(str(row[-1]) for row in plan_rows)


def _execute_read_only(sql: str) -> tuple[list[dict[str, Any]], str, float]:
    """Use a transaction rolled back in all cases, even though guards allow only SELECT."""
    engine = get_engine()
    started = time.perf_counter()
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            explain_plan = _plan_text(connection, sql)
            reject_large_estimate(explain_plan, get_settings())
            result = connection.execute(text(sql))
            rows = [dict(row._mapping) for row in result]
        finally:
            transaction.rollback()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return rows, explain_plan, elapsed_ms


def _same_result(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
    serialize = lambda row: json.dumps(row, sort_keys=True, default=str)
    return Counter(map(serialize, left)) == Counter(map(serialize, right))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def website() -> FileResponse:
    """Serve the UI from the API origin so Safari makes no cross-server request."""
    return FileResponse(WEB_APP)


@app.get("/v1/schema", response_model=SchemaResponse)
def schema() -> SchemaResponse:
    return get_schema()


@app.get("/v1/history")
def query_history():
    return history.list()


@app.post("/v1/feedback", status_code=201)
def feedback(request: FeedbackRequest) -> dict[str, str]:
    persist_feedback(request)
    return {"status": "stored", "message": "Feedback was saved for the next evaluation dataset update."}


@app.post("/v1/query", response_model=QueryResponse | ClarificationNeeded)
def query(request: QueryRequest):
    clarification = _ambiguity(request.question)
    if clarification:
        return clarification

    settings = get_settings()
    full_schema = get_schema()
    context_schema = relevant_schema(request.question, full_schema)
    try:
        generator = get_generator(
            settings.llm_provider,
            settings.openai_api_key,
            settings.openai_model,
            settings.ollama_base_url,
            settings.ollama_model,
        )
        generated = generator.generate(request.question, context_schema)
        safe_sql, warnings = validate_and_limit(generated.sql, settings)
        rows, explain_plan, execution_ms = _execute_read_only(safe_sql)
    except GenerationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLSafetyError as error:
        history.add(request.question, generated.sql if "generated" in locals() else "", 0, 0, "blocked")
        raise HTTPException(status_code=400, detail={"rule": error.rule, "message": error.message}) from error
    except Exception as error:
        # Syntax errors, unavailable local model, and driver errors must not return a partial success.
        raise HTTPException(status_code=422, detail=f"Query could not be safely executed: {error}") from error

    checks: list[CheckResult] = [
        CheckResult(
            name="generation_confidence",
            score=generated.confidence,
            message="Self-reported generation confidence; never used as the only safety signal.",
        ),
        CheckResult(
            name="schema_coverage",
            score=1.0,
            message="Generated query was based on live SQLAlchemy schema context.",
        ),
    ]
    checks.append(generator.judge(request.question, safe_sql))
    checks.extend(sanity_checks(rows, settings.max_rows))

    alternative_agreement: bool | None = None
    if request.verify_with_alternative:
        alternative = generator.generate_alternative(request.question, context_schema, safe_sql)
        if alternative is None:
            warnings.append(
                {
                    "rule": "multi_query_validation",
                    "message": "No independent alternative is available in offline mode.",
                }
            )
        else:
            try:
                alternative_sql, _ = validate_and_limit(alternative.sql, settings)
                alternative_rows, _, _ = _execute_read_only(alternative_sql)
                alternative_agreement = _same_result(rows, alternative_rows)
                checks.append(
                    CheckResult(
                        name="multi_query_agreement",
                        score=1.0 if alternative_agreement else 0.25,
                        message=(
                            "Independent SQL approach returned the same result."
                            if alternative_agreement
                            else "Independent SQL approach diverged; inspect both queries."
                        ),
                    )
                )
            except (SQLSafetyError, Exception) as error:
                warnings.append(
                    {
                        "rule": "multi_query_validation",
                        "message": f"Alternative query was not used: {error}",
                    }
                )

    confidence = weighted_confidence(checks, generated.confidence)
    history.add(request.question, safe_sql, confidence, len(rows), "ok")
    generated.sql = safe_sql
    return QueryResponse(
        question=request.question,
        generated=generated,
        rows=rows,
        row_count=len(rows),
        execution_ms=execution_ms,
        explain_plan=explain_plan,
        confidence=confidence,
        confidence_breakdown=checks,
        warnings=warnings,
        alternative_agreement=alternative_agreement,
    )
