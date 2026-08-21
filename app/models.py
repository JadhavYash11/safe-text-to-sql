"""API contracts. Keeping them explicit makes LLM output and API output testable."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)
    verify_with_alternative: bool = False


class GeneratedQuery(BaseModel):
    sql: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    tables_accessed: list[str] = []
    columns_accessed: list[str] = []


class ClarificationOption(BaseModel):
    label: str
    description: str
    example_question: str


class ClarificationNeeded(BaseModel):
    needs_clarification: bool = True
    message: str
    options: list[ClarificationOption]


class GuardrailWarning(BaseModel):
    rule: str
    message: str


class CheckResult(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    message: str


class QueryResponse(BaseModel):
    status: str = "ok"
    question: str
    generated: GeneratedQuery
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: float
    explain_plan: str
    confidence: float = Field(ge=0, le=1)
    confidence_breakdown: list[CheckResult]
    warnings: list[GuardrailWarning] = []
    alternative_agreement: bool | None = None


class TableColumn(BaseModel):
    name: str
    type: str
    primary_key: bool = False
    nullable: bool = True
    sample_values: list[str] = []


class ForeignKey(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableSchema(BaseModel):
    name: str
    columns: list[TableColumn]
    foreign_keys: list[ForeignKey] = []


class SchemaResponse(BaseModel):
    tables: list[TableSchema]


class FeedbackRequest(BaseModel):
    question: str
    sql: str
    correct: bool
    note: str = ""


class HistoryEntry(BaseModel):
    id: str
    timestamp: datetime
    question: str
    sql: str
    confidence: float
    row_count: int
    status: str

