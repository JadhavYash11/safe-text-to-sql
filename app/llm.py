"""Schema-aware SQL generation with an OpenAI path and an offline demo fallback."""

import json
import re
from typing import Protocol

from app.models import CheckResult, GeneratedQuery, SchemaResponse
from app.schema import schema_to_prompt


class GenerationError(ValueError):
    pass


class SQLGenerator(Protocol):
    def generate(self, question: str, schema: SchemaResponse) -> GeneratedQuery: ...

    def judge(self, question: str, sql: str) -> CheckResult: ...

    def generate_alternative(
        self, question: str, schema: SchemaResponse, original_sql: str
    ) -> GeneratedQuery | None: ...


_FEW_SHOTS = """
Question: How many paid orders were placed in June 2024?
SQL: SELECT COUNT(*) AS paid_orders FROM orders
WHERE status = 'paid' AND order_date >= DATE '2024-06-01' AND order_date < DATE '2024-07-01'

Question: Show the top customers by net revenue.
SQL: SELECT c.customer_name, ROUND(SUM(o.net_amount), 2) AS net_revenue
FROM customers c JOIN orders o ON o.customer_id = c.customer_id
GROUP BY c.customer_name ORDER BY net_revenue DESC LIMIT 10

Question: Which product categories generated the most sales?
SQL: SELECT p.category, ROUND(SUM(oi.line_total), 2) AS sales
FROM order_items oi JOIN products p ON p.product_id = oi.product_id
GROUP BY p.category ORDER BY sales DESC
""".strip()


def build_generation_prompt(question: str, schema: SchemaResponse) -> str:
    return f"""
You generate one read-only DuckDB SQL query. Use only the provided schema.
Never use CREATE, ALTER, DROP, INSERT, UPDATE, DELETE, multiple statements, or SELECT *.
Return strict JSON with keys sql, explanation, confidence, tables_accessed, columns_accessed.
confidence must be a number from 0 to 1. If the schema cannot answer, use an empty SQL string
and explain why; do not invent tables or columns.

Relevant schema:
{schema_to_prompt(schema)}

Examples:
{_FEW_SHOTS}

User question: {question}
""".strip()


class OpenAICompatibleSQLGenerator:
    """Uses JSON mode so malformed prose never enters the SQL execution layer."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def _completion(self, prompt: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise analytics engineer. Output JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def generate(self, question: str, schema: SchemaResponse) -> GeneratedQuery:
        output = self._completion(build_generation_prompt(question, schema))
        generated = GeneratedQuery.model_validate(output)
        if not generated.sql.strip():
            raise GenerationError(generated.explanation)
        return generated

    def judge(self, question: str, sql: str) -> CheckResult:
        prompt = f"""
Original question: {question}
SQL query: {sql}
Back-translate what the SQL answers, then decide whether it answers the original question.
Return JSON only: {{"score": 0..1, "message": "short explanation"}}.
""".strip()
        output = self._completion(prompt)
        return CheckResult(name="back_translation", score=float(output["score"]), message=output["message"])

    def generate_alternative(
        self, question: str, schema: SchemaResponse, original_sql: str
    ) -> GeneratedQuery | None:
        prompt = build_generation_prompt(question, schema) + (
            "\nGenerate a semantically equivalent but independently structured SQL query. "
            f"Do not repeat this exact query:\n{original_sql}"
        )
        output = self._completion(prompt)
        candidate = GeneratedQuery.model_validate(output)
        return candidate if candidate.sql.strip() and candidate.sql != original_sql else None


class OfflineDemoGenerator:
    """Allows a full local demo without credentials; it deliberately supports only sample intents."""

    def generate(self, question: str, schema: SchemaResponse) -> GeneratedQuery:
        normalized = re.sub(r"\s+", " ", question.lower()).strip()
        if ("monthly" in normalized or "by month" in normalized) and "revenue" in normalized:
            amount = "net_amount" if "net" in normalized else "total_amount"
            label = "net_revenue" if amount == "net_amount" else "gross_revenue"
            return GeneratedQuery(
                sql=(
                    f"SELECT DATE_TRUNC('month', order_date) AS month, "
                    f"ROUND(SUM({amount}), 2) AS {label} FROM orders "
                    "GROUP BY month ORDER BY month"
                ),
                explanation=f"Groups orders by month and sums {amount}.",
                confidence=0.84,
                tables_accessed=["orders"],
                columns_accessed=["orders.order_date", f"orders.{amount}"],
            )
        if "top" in normalized and "customer" in normalized:
            amount = "net_amount" if "net" in normalized else "total_amount"
            return GeneratedQuery(
                sql=(
                    "SELECT c.customer_name, ROUND(SUM(o."
                    f"{amount}), 2) AS revenue FROM customers c "
                    "JOIN orders o ON o.customer_id = c.customer_id "
                    "GROUP BY c.customer_name ORDER BY revenue DESC"
                ),
                explanation=f"Ranks customers by summed {amount}.",
                confidence=0.86,
                tables_accessed=["customers", "orders"],
                columns_accessed=["customers.customer_name", f"orders.{amount}"],
            )
        if "status" in normalized and "order" in normalized:
            return GeneratedQuery(
                sql="SELECT status, COUNT(*) AS order_count FROM orders GROUP BY status ORDER BY order_count DESC",
                explanation="Counts orders grouped by their status.",
                confidence=0.91,
                tables_accessed=["orders"],
                columns_accessed=["orders.status", "orders.order_id"],
            )
        if ("category" in normalized or "product" in normalized) and (
            "sales" in normalized or "revenue" in normalized
        ):
            return GeneratedQuery(
                sql=(
                    "SELECT p.category, ROUND(SUM(oi.line_total), 2) AS sales "
                    "FROM order_items oi JOIN products p ON p.product_id = oi.product_id "
                    "GROUP BY p.category ORDER BY sales DESC"
                ),
                explanation="Sums order-item sales by product category.",
                confidence=0.87,
                tables_accessed=["order_items", "products"],
                columns_accessed=["products.category", "order_items.line_total"],
            )
        if ("how many" in normalized or "count" in normalized or "number of" in normalized) and "order" in normalized:
            where = " WHERE status = 'paid'" if "paid" in normalized else ""
            return GeneratedQuery(
                sql=f"SELECT COUNT(*) AS order_count FROM orders{where}",
                explanation="Counts matching orders.",
                confidence=0.90,
                tables_accessed=["orders"],
                columns_accessed=["orders.order_id"],
            )
        if "customer" in normalized and "country" in normalized:
            return GeneratedQuery(
                sql=(
                    "SELECT country, COUNT(*) AS customer_count FROM customers "
                    "GROUP BY country ORDER BY customer_count DESC"
                ),
                explanation="Counts customers by country.",
                confidence=0.88,
                tables_accessed=["customers"],
                columns_accessed=["customers.country", "customers.customer_id"],
            )
        raise GenerationError(
            "The offline demo understands sample questions about orders, revenue, customers, and "
            "product-category sales. Set OPENAI_API_KEY for arbitrary natural-language questions."
        )

    def judge(self, question: str, sql: str) -> CheckResult:
        # This deliberately modest score tells the caller that a real LLM judge was not used.
        question_terms = {
            word for word in re.findall(r"[a-z]+", question.lower()) if word not in {"the", "a", "by"}
        }
        sql_terms = set(re.findall(r"[a-z_]+", sql.lower()))
        matched_concepts = sum(
            any(term in sql_term or sql_term in term for sql_term in sql_terms) for term in question_terms
        )
        score = min(0.82, 0.5 + matched_concepts / max(len(question_terms), 1) * 0.32)
        return CheckResult(
            name="back_translation",
            score=score,
            message="Offline lexical alignment check used; configure OpenAI for LLM back-translation.",
        )

    def generate_alternative(
        self, question: str, schema: SchemaResponse, original_sql: str
    ) -> GeneratedQuery | None:
        return None


def get_generator(
    provider: str, api_key: str | None, model: str, ollama_base_url: str, ollama_model: str
) -> SQLGenerator:
    if provider == "ollama":
        # Ollama exposes an OpenAI-compatible local endpoint. The placeholder key is ignored locally.
        return OpenAICompatibleSQLGenerator("ollama", ollama_model, ollama_base_url)
    if provider == "openai":
        if not api_key:
            raise GenerationError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
        return OpenAICompatibleSQLGenerator(api_key, model)
    if provider != "offline":
        raise GenerationError("LLM_PROVIDER must be one of: offline, ollama, openai.")
    return OfflineDemoGenerator()
