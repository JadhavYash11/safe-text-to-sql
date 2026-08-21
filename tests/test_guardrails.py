import pytest

from app.config import Settings
from app.guardrails import SQLSafetyError, validate_and_limit


def test_adds_a_limit_when_missing():
    sql, warnings = validate_and_limit("SELECT customer_id FROM customers", Settings(max_rows=50))
    assert sql.endswith("LIMIT 50")
    assert warnings[0].rule == "row_limit"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT * FROM orders; DROP TABLE orders",
        "UPDATE orders SET status = 'paid'",
        "CREATE TABLE unsafe (id INTEGER)",
    ],
)
def test_blocks_write_and_multiple_statements(sql):
    with pytest.raises(SQLSafetyError):
        validate_and_limit(sql, Settings())


def test_caps_an_existing_limit():
    sql, warnings = validate_and_limit("SELECT * FROM orders LIMIT 5000", Settings(max_rows=100))
    assert sql.endswith("LIMIT 100")
    assert "capped" in warnings[0].message

