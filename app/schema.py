"""Schema introspection and lightweight relevance filtering for LLM context."""

import re

from sqlalchemy import inspect, text

from app.models import ForeignKey, SchemaResponse, TableColumn, TableSchema


def _words(value: str) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", value.lower()) if len(part) > 1}


def extract_schema(engine) -> SchemaResponse:
    """Use SQLAlchemy inspection instead of maintaining a second schema by hand."""
    inspector = inspect(engine)
    identifier = engine.dialect.identifier_preparer
    tables: list[TableSchema] = []
    for table_name in inspector.get_table_names():
        if table_name.startswith("sqlite_"):
            continue
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
        columns: list[TableColumn] = []
        for column in inspector.get_columns(table_name):
            sample_values: list[str] = []
            # Values are context for categorical filters, not user-query output.
            if any(word in str(column["type"]).upper() for word in ("CHAR", "TEXT", "STRING")):
                with engine.connect() as connection:
                    quoted_column = identifier.quote(column["name"])
                    quoted_table = identifier.quote(table_name)
                    values = connection.execute(
                        text(
                            f"SELECT DISTINCT {quoted_column} FROM {quoted_table} "
                            f"WHERE {quoted_column} IS NOT NULL LIMIT 5"
                        )
                    ).scalars()
                    sample_values = [str(value) for value in values]
            columns.append(
                TableColumn(
                    name=column["name"],
                    type=str(column["type"]),
                    primary_key=column["name"] in pk_columns,
                    nullable=bool(column.get("nullable", True)),
                    sample_values=sample_values,
                )
            )
        foreign_keys = [
            ForeignKey(
                constrained_columns=fk["constrained_columns"],
                referred_table=fk["referred_table"],
                referred_columns=fk["referred_columns"],
            )
            for fk in inspector.get_foreign_keys(table_name)
        ]
        tables.append(TableSchema(name=table_name, columns=columns, foreign_keys=foreign_keys))
    return SchemaResponse(tables=tables)


def relevant_schema(question: str, schema: SchemaResponse, max_tables: int = 4) -> SchemaResponse:
    """A transparent token-overlap baseline; replace with embeddings at larger scale."""
    question_words = _words(question)
    scored: list[tuple[int, TableSchema]] = []
    for table in schema.tables:
        description_words = _words(table.name)
        for column in table.columns:
            description_words |= _words(column.name)
            for value in column.sample_values:
                description_words |= _words(value)
        scored.append((len(question_words & description_words), table))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    # Include a few tables even at zero overlap: the model still sees valid join paths.
    selected = [table for _, table in scored[:max_tables]]
    return SchemaResponse(tables=selected)


def schema_to_prompt(schema: SchemaResponse) -> str:
    lines: list[str] = []
    for table in schema.tables:
        columns = []
        for column in table.columns:
            suffix = " PRIMARY KEY" if column.primary_key else ""
            samples = f" examples={column.sample_values}" if column.sample_values else ""
            columns.append(f"{column.name} {column.type}{suffix}{samples}")
        lines.append(f"TABLE {table.name} ({'; '.join(columns)})")
        for fk in table.foreign_keys:
            lines.append(
                f"  FK ({', '.join(fk.constrained_columns)}) -> "
                f"{fk.referred_table}({', '.join(fk.referred_columns)})"
            )
    return "\n".join(lines)
