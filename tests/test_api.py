from fastapi.testclient import TestClient

from app.main import app


def test_schema_is_available():
    with TestClient(app) as client:
        response = client.get("/v1/schema")
    assert response.status_code == 200
    assert {table["name"] for table in response.json()["tables"]} >= {"customers", "orders"}


def test_website_is_served_from_the_api():
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Safe Text-to-SQL" in response.text


def test_offline_query_runs_safely():
    with TestClient(app) as client:
        response = client.post("/v1/query", json={"question": "How many paid orders are there?"})
    assert response.status_code == 200
    body = response.json()
    assert body["rows"][0]["order_count"] == 5
    assert body["generated"]["sql"].endswith("LIMIT 1000")
