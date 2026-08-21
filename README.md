# Safe Text-to-SQL

A secure Natural Language to SQL application built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, and **Ollama/OpenAI**. The application converts natural language questions into SQL queries while applying deterministic guardrails to prevent unsafe database operations.

---

## Features

- Convert natural language questions into SQL
- Live schema discovery using SQLAlchemy
- Read-only SQL execution
- SQL safety validation
- Query history and feedback
- Confidence scoring
- PostgreSQL support
- Local LLM support with Ollama
- OpenAI API support
- REST API with FastAPI
- Interactive web interface

---

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- DuckDB (Demo)
- Ollama
- OpenAI
- Docker

---

# Project Structure

```
.
├── app/
│   ├── config.py
│   ├── db.py
│   ├── guardrails.py
│   ├── history.py
│   ├── llm.py
│   ├── main.py
│   ├── models.py
│   ├── schema.py
│   └── validation.py
│
├── frontend/
│   ├── app.py
│   └── index.html
│
├── sql/
│   └── postgres_demo.sql
│
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

# Installation

## 1. Clone Repository

```bash
git clone https://github.com/JadhavYash11/safe-text-to-sql.git

cd safe-text-to-sql
```

---

## 2. Create Virtual Environment

```bash
python3 -m venv .venv

source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -e ".[dev]"
```

---

## 4. Configure Environment

Copy

```bash
cp .env.example .env
```

Example:

```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/postgres
SEED_DEMO_DATA=false

LLM_PROVIDER=ollama

OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:3b

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

MAX_ROWS=1000
MAX_ESTIMATED_ROWS=100000
MAX_SUBQUERY_DEPTH=3
```

---

# PostgreSQL Setup

Create your database and import the demo schema.

```sql
CREATE DATABASE postgres;
```

Execute

```
sql/postgres_demo.sql
```

using pgAdmin or psql.

---

# Ollama Setup

Install Ollama

```bash
brew install ollama
```

Start the server

```bash
ollama serve
```

Download the model

```bash
ollama pull llama3.2:3b
```

---

# Run the Application

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8501
```

Open

```
http://127.0.0.1:8501
```

Swagger API

```
http://127.0.0.1:8501/docs
```

Schema Endpoint

```
http://127.0.0.1:8501/v1/schema
```

---

# Example Questions

- Show all paid orders
- Show gross revenue by month
- Show net revenue by month
- Which customers generated the highest revenue?
- Show total revenue by country
- List refunded orders
- Which products generated the most revenue?
- Show sales by product category
- Average order value by customer
- Monthly order count

---

# API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Health Check |
| GET | `/v1/schema` | Database Schema |
| POST | `/v1/query` | Generate SQL |
| GET | `/v1/history` | Query History |
| POST | `/v1/feedback` | Store Feedback |

---

# Running Tests

```bash
pytest
```

---

# Docker

Build and run

```bash
docker compose up --build
```

---

# Security

The application prevents:

- DELETE
- UPDATE
- INSERT
- DROP
- ALTER
- CREATE
- Multiple SQL statements
- Deep nested subqueries
- Large result sets

Only read-only SQL queries are executed.

---

# Future Improvements

- Vector-based schema retrieval
- Role-based authentication
- Query caching
- Audit logging
- Better SQL evaluation
- Support for multiple databases
- Streaming responses
- More LLM providers

---

# Author

**Yash Jadhav**

GitHub: https://github.com/JadhavYash11

---

# License

MIT License
