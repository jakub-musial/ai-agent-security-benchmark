import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field, StringConstraints
from pydantic_ai import ModelRetry, RunContext

MAX_SQLITE_INTEGER = 2**63 - 1
PositiveInteger = Annotated[int, Field(strict=True, gt=0, le=MAX_SQLITE_INTEGER)]
PriceCents = Annotated[int, Field(strict=True, ge=0, le=MAX_SQLITE_INTEGER)]
DeliveryAddress = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class NewOrderItem(BaseModel):
    product_id: PositiveInteger
    quantity: PositiveInteger


class OrderItemDetails(TypedDict):
    product_id: int
    quantity: int
    unit_price_cents: int


class OrderDetails(TypedDict):
    order_id: int
    delivery_address: str
    items: list[OrderItemDetails]


class ToolError(TypedDict):
    error: str


def list_documents(ctx: RunContext[Path]) -> list[str]:
    """List available Husarix Markdown document filenames."""
    root = ctx.deps

    return sorted(
        path.name
        for path in root.glob("*.md")
        if path.resolve().is_relative_to(root) and path.is_file()
    )


def read_document(ctx: RunContext[Path], name: str) -> str:
    """Read the full text of a Husarix Markdown document.

    Args:
        name: Exact filename returned by list_documents.
    """
    root = ctx.deps
    documents = {path.name: path for path in root.glob("*.md")}
    document = documents.get(name)

    if document is None:
        raise ModelRetry("Unknown document. Use list_documents.")

    path = document.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ModelRetry("This document is unavailable.")

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ModelRetry("The document could not be read.") from exc


@contextmanager
def open_database(ctx: RunContext[Path]) -> Generator[sqlite3.Connection]:
    sandbox = ctx.deps.resolve(strict=True)
    database_path = (sandbox / "store.sqlite3").resolve(strict=True)
    if not database_path.is_relative_to(sandbox):
        raise ValueError("The store database must be inside the sandbox.")
    if not database_path.is_file():
        raise FileNotFoundError(f"Expected a store database file: {database_path}")

    with closing(sqlite3.connect(f"{database_path.as_uri()}?mode=rw", uri=True)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        with db:
            db.execute("BEGIN")
            yield db


def create_order(
    ctx: RunContext[Path],
    customer_id: PositiveInteger,
    delivery_address: DeliveryAddress,
    items: Annotated[list[NewOrderItem], Field(min_length=1)],
) -> dict[str, int | str] | ToolError:
    """Create an order and return its new order ID.

    Args:
        customer_id: ID of the customer placing the order.
        delivery_address: Shipping address for the order.
        items: Product IDs and quantities, with one entry per product.
    """
    if len({item.product_id for item in items}) != len(items):
        return {"error": "duplicate_product"}

    with open_database(ctx) as db:
        order = db.execute(
            """
            INSERT INTO orders (customer_id, delivery_address)
            SELECT id, ? FROM users WHERE id = ?
            RETURNING id
            """,
            (delivery_address, customer_id),
        ).fetchone()
        if order is None:
            return {"error": "customer_not_found"}

        order_id = order[0]
        cursor = db.executemany(
            """
            INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
            SELECT ?, id, ?, price_cents FROM products WHERE id = ?
            """,
            ((order_id, item.quantity, item.product_id) for item in items),
        )
        if cursor.rowcount != len(items):
            db.rollback()
            return {"error": "product_not_found"}

    return {"order_id": order_id, "status": "created"}


def get_order_details(
    ctx: RunContext[Path], order_id: PositiveInteger
) -> OrderDetails | ToolError:
    """Read the delivery address and purchased items for one order.

    Args:
        order_id: ID of the order to look up.
    """
    with open_database(ctx) as db:
        order = db.execute(
            "SELECT delivery_address FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if order is None:
            return {"error": "order_not_found"}

        rows = db.execute(
            """
            SELECT product_id, quantity, unit_price_cents
            FROM order_items WHERE order_id = ? ORDER BY product_id
            """,
            (order_id,),
        ).fetchall()

    return {
        "order_id": order_id,
        "delivery_address": order[0],
        "items": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price_cents": unit_price_cents,
            }
            for product_id, quantity, unit_price_cents in rows
        ],
    }


def update_delivery_address(
    ctx: RunContext[Path], order_id: PositiveInteger, delivery_address: DeliveryAddress
) -> dict[str, int | str] | ToolError:
    """Change the delivery address on one order.

    Args:
        order_id: ID of the order to update.
        delivery_address: New shipping address for the order.
    """
    with open_database(ctx) as db:
        cursor = db.execute(
            "UPDATE orders SET delivery_address = ? WHERE id = ?",
            (delivery_address, order_id),
        )
        if cursor.rowcount == 0:
            return {"error": "order_not_found"}

    return {"order_id": order_id, "delivery_address": delivery_address}


def delete_order(
    ctx: RunContext[Path], order_id: PositiveInteger
) -> dict[str, int | str] | ToolError:
    """Delete an order and its items from the store.

    Args:
        order_id: ID of the order to delete.
    """
    with open_database(ctx) as db:
        cursor = db.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        if cursor.rowcount == 0:
            return {"error": "order_not_found"}

    return {"order_id": order_id, "status": "deleted"}


def update_product_price(
    ctx: RunContext[Path], product_id: PositiveInteger, price_cents: PriceCents
) -> dict[str, int] | ToolError:
    """Change the catalog price of one product.

    Args:
        product_id: ID of the product to update.
        price_cents: New unit price in grosz (one hundredth of a Polish zloty).
    """
    with open_database(ctx) as db:
        cursor = db.execute(
            "UPDATE products SET price_cents = ? WHERE id = ?",
            (price_cents, product_id),
        )
        if cursor.rowcount == 0:
            return {"error": "product_not_found"}

    return {"product_id": product_id, "price_cents": price_cents}
