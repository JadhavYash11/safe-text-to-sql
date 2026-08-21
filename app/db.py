"""Database setup and the intentionally small demo business dataset."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create one SQLAlchemy engine for the process.

    DuckDB keeps the demo self-contained. Swap DATABASE_URL for a PostgreSQL URL
    in production; the rest of the application uses SQLAlchemy's common API.
    """
    settings = get_settings()
    # DuckDB is embedded, so its connections must close promptly. PostgreSQL uses SQLAlchemy's
    # normal pool and checks a pooled connection before reusing it.
    if settings.database_url.startswith("duckdb"):
        return create_engine(settings.database_url, poolclass=NullPool)
    return create_engine(settings.database_url, pool_pre_ping=True)


def seed_demo_database() -> None:
    """Create a realistic, repeatable schema only when the database is empty."""
    engine = get_engine()
    with engine.begin() as connection:
        exists = connection.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'main' AND table_name = 'customers'"
            )
        ).scalar_one()
        if exists:
            return

        connection.execute(
            text(
                """
                CREATE TABLE customers (
                    customer_id INTEGER PRIMARY KEY,
                    customer_name VARCHAR NOT NULL,
                    country VARCHAR NOT NULL,
                    segment VARCHAR NOT NULL,
                    created_at DATE NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE products (
                    product_id INTEGER PRIMARY KEY,
                    product_name VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    unit_price DECIMAL(10, 2) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE orders (
                    order_id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
                    order_date DATE NOT NULL,
                    status VARCHAR NOT NULL,
                    total_amount DECIMAL(10, 2) NOT NULL,
                    discount_amount DECIMAL(10, 2) NOT NULL,
                    net_amount DECIMAL(10, 2) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE order_items (
                    order_item_id INTEGER PRIMARY KEY,
                    order_id INTEGER NOT NULL REFERENCES orders(order_id),
                    product_id INTEGER NOT NULL REFERENCES products(product_id),
                    quantity INTEGER NOT NULL,
                    line_total DECIMAL(10, 2) NOT NULL
                )
                """
            )
        )

        connection.execute(
            text(
                """
                INSERT INTO customers VALUES
                (1, 'Aster Labs', 'India', 'Enterprise', '2024-01-15'),
                (2, 'Northwind Stores', 'United States', 'Mid-market', '2024-02-02'),
                (3, 'Cedar & Co', 'United Kingdom', 'SMB', '2024-02-28'),
                (4, 'Mosaic Health', 'India', 'Enterprise', '2024-03-10'),
                (5, 'Orbit Supply', 'Australia', 'Mid-market', '2024-03-19')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO products VALUES
                (1, 'Analytics Pro', 'Software', 1200.00),
                (2, 'Data Connector', 'Software', 650.00),
                (3, 'Implementation', 'Services', 2500.00),
                (4, 'Priority Support', 'Services', 800.00)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO orders VALUES
                (1001, 1, '2024-04-03', 'paid', 3700.00, 200.00, 3500.00),
                (1002, 2, '2024-04-18', 'paid', 1850.00, 0.00, 1850.00),
                (1003, 1, '2024-05-05', 'paid', 1200.00, 0.00, 1200.00),
                (1004, 3, '2024-05-21', 'refunded', 2500.00, 250.00, 2250.00),
                (1005, 4, '2024-06-02', 'paid', 3300.00, 300.00, 3000.00),
                (1006, 5, '2024-06-11', 'pending', 650.00, 0.00, 650.00),
                (1007, 2, '2024-06-28', 'paid', 2000.00, 0.00, 2000.00)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO order_items VALUES
                (1, 1001, 1, 1, 1200.00), (2, 1001, 3, 1, 2500.00),
                (3, 1002, 1, 1, 1200.00), (4, 1002, 2, 1, 650.00),
                (5, 1003, 1, 1, 1200.00), (6, 1004, 3, 1, 2500.00),
                (7, 1005, 3, 1, 2500.00), (8, 1005, 4, 1, 800.00),
                (9, 1006, 2, 1, 650.00), (10, 1007, 1, 1, 1200.00),
                (11, 1007, 4, 1, 800.00)
                """
            )
        )
