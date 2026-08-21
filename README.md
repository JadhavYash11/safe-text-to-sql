# Safe Text-to-SQL

A first runnable natural-language database interface. It generates SQL from a question, blocks unsafe SQL, runs it in a transaction that always rolls back, performs hallucination checks, and returns a confidence score.

It starts with a local DuckDB database. You can run it in VS Code without PostgreSQL or a paid API. For broader, free model-backed questions, it supports local [Ollama](https://ollama.com/).

## What is built

| Layer | Purpose |
| --- | --- |
| Schema awareness | Reads tables, columns, primary/foreign keys, and sample categorical values through SQLAlchemy. |
| Generation | Uses structured JSON from OpenAI or free local Ollama; offline mode covers demo questions. |
| Guardrails | Allows one `SELECT`/`WITH`; blocks DDL/DML; limits rows; restricts depth and estimated scans. |
| Execution | Runs a read-only query transaction and returns results, time, and `EXPLAIN`. |
| Validation | Alignment, NULL/result sanity checks, optional alternative query, and a transparent confidence formula. |
| Interface | Streamlit UI, query history, and feedback stored for future evaluations. |

## 1. Open the project folder

1. In VS Code, select **File → Open Folder…**.
2. Select `/Users/yasshh/Documents/Codex/2026-08-05/sta`.
3. Open **Terminal → New Terminal**. Every command below runs from this folder.

Opening this exact directory matters: it lets VS Code find the source, tests, and Python environment as one project.

## 2. Create the Python environment

The computer currently has Python 3.10. This MVP supports it, although Python 3.11 is preferred for a new setup.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
```

- `venv` creates a project-only Python environment.
- `activate` makes the terminal use it; `(.venv)` appears in the prompt.
- `pip install -e '.[dev]'` installs the app and testing packages described in `pyproject.toml`.
- `.env` is your local configuration and is never committed to Git.

Then choose **Python: Select Interpreter** from the `Cmd+Shift+P` command palette and pick `.venv`.

## 3. Run the website and API together

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8501
```

This one process serves both the website and the query API. The first start creates `data/text2sql.duckdb` and seeds `customers`, `products`, `orders`, and `order_items`. This is trusted application setup—not model-generated SQL.

Open [interactive API documentation](http://127.0.0.1:8501/docs), find `POST /v1/query`, and submit:

```json
{
  "question": "Show gross revenue by month",
  "verify_with_alternative": false
}
```

`--reload` restarts the server when you save a Python file. Stop it with `Ctrl+C`.

## 4. Use the visual interface

With the command above running, open [http://127.0.0.1:8501](http://127.0.0.1:8501) in Safari. The website is served from the same server as the API, so it does not need a second terminal or a separate localhost connection. Good starter questions are:

- `Show gross revenue by month`
- `Which customers have the highest net revenue?`
- `How many paid orders are there?`
- `Show sales by product category`

Ask “Show revenue by month” to see ambiguity handling. The app asks if you mean gross or net revenue instead of silently guessing.

## 5. Use a free local LLM API (recommended next)

Offline mode works only for the demo questions. To ask arbitrary questions without paying per API call, install [Ollama](https://ollama.com/) and start its local server:

```bash
brew install ollama
ollama serve
```

In a new terminal, download a small model once:

```bash
ollama pull llama3.2:3b
```

Edit `.env` to this:

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b
```

Restart Uvicorn. The API now gives the local model a filtered version of the live schema, its relationships and few-shot examples. It forces JSON output, then applies independent deterministic SQL checks before anything runs. A stronger alternative for a capable machine is `qwen2.5-coder:7b`.

## 6. Connect PostgreSQL

Use a dedicated database user with **only `SELECT` permission**. Do not use your database owner, admin, or superuser account. Have the database owner run this once, replacing the database name and password:

```sql
CREATE ROLE text2sql_reader LOGIN PASSWORD 'use-a-strong-password-here';
GRANT CONNECT ON DATABASE your_database TO text2sql_reader;
GRANT USAGE ON SCHEMA public TO text2sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO text2sql_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO text2sql_reader;
```

Then open `.env` in VS Code and set:

```dotenv
DATABASE_URL=postgresql+psycopg://text2sql_reader:YOUR_URL_ENCODED_PASSWORD@localhost:5432/your_database
SEED_DEMO_DATA=false
```

For a cloud database, replace `localhost:5432` with the provider host and port. URL-encode password characters such as `@`, `:`, `/`, `?`, and `#`. Keep `.env` private and never paste its password into chat.

Install the driver and restart the local website:

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8501
```

Open [http://127.0.0.1:8501/v1/schema](http://127.0.0.1:8501/v1/schema). Seeing your own tables and columns confirms the connection. PostgreSQL URLs now skip demo-table creation automatically.

## 7. Run the tests

```bash
pytest -q
```

The test suite proves that `DELETE`, `UPDATE`, `CREATE`, and a `SELECT; DROP` payload are rejected. It also runs a safe query end-to-end against the seeded database.

## Project map

```text
app/
  config.py       Environment-driven limits and model settings
  db.py           SQLAlchemy engine and demo data
  schema.py       Live schema extraction and relevance filtering
  llm.py          Prompts, OpenAI/Ollama client, offline fallback
  guardrails.py   SQL allow-list, row/depth/EXPLAIN checks
  validation.py   Sanity checks and confidence calculation
  history.py      Query history and feedback persistence
  main.py         FastAPI routes, pipeline orchestration, and website delivery
frontend/index.html Single-origin browser interface
tests/            Automated safety and API tests
```

## Request lifecycle

```mermaid
flowchart LR
    Q["User question"] --> A{"Ambiguous?"}
    A -- Yes --> C["Clarification choices"]
    A -- No --> S["Filter live schema"]
    S --> G["LLM or offline generator"]
    G --> R["Structured SQL JSON"]
    R --> GR["Guardrails"]
    GR -- Block --> B["Reason and audit history"]
    GR -- Pass --> E["EXPLAIN and rollback transaction"]
    E --> V["Alignment and sanity checks"]
    V --> O["Rows, SQL, plan, warnings, confidence"]
```

## API reference

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Fast health check. |
| `GET /v1/schema` | Live schema used by the generator. |
| `POST /v1/query` | Accepts `question` and optional `verify_with_alternative`. |
| `GET /v1/history` | Last 100 in-process query metadata entries. |
| `POST /v1/feedback` | Stores correct/incorrect feedback in `data/feedback.jsonl`. |

Try the API from a terminal:

```bash
curl -X POST http://127.0.0.1:8501/v1/query \
  -H 'content-type: application/json' \
  -d '{"question":"How many paid orders are there?"}'
```

## Docker option

```bash
docker compose up --build
```

This runs the API on port 8000 and UI on port 8501. It persists the DuckDB file under `./data`. Docker defaults to offline mode; use the non-Docker setup for your first Ollama run.

## Safety and next build steps

This is a strong MVP, but deterministic middleware is not the only production defense. With PostgreSQL, create a separate `SELECT`-only database role and set database-level statement/connection timeouts.

Next, we should:

1. Replace token-overlap schema filtering with embeddings and a business glossary.
2. Add PostgreSQL, a dedicated read-only role, and JSON `EXPLAIN` cost parsing.
3. Add 50+ golden questions and execution-match evaluations under `tests/evals/`.
4. Persist audit history/feedback in a database with authentication.
5. Always run an independent second query for multi-query validation.
# safe-text-to-sql
