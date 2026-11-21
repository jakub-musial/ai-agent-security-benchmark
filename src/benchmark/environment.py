"""Temporary store data environments for individual benchmark trials."""

import logging
import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from pathlib import Path
from shutil import copytree
from tempfile import TemporaryDirectory

from .schemas.scenario_output import OrderItemSnapshot, OrderSnapshot, StoreSnapshot

logger = logging.getLogger(__name__)
STORE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "store.sql"


@contextmanager
def prepare_environment(source_dir: str | Path) -> Generator[Path]:
    """Copy store documents and initialize a fresh SQLite database for a trial.

    Args:
        source_dir: Directory containing the initial store data. Relative paths
            are resolved from the working directory.

    Yields:
        Absolute path to the copied directory containing the documents and
        store.sqlite3.
        The directory is removed when the context exits, including on errors.

    Raises:
        OSError: The source cannot be copied or the environment cannot be
            created or removed, or the SQL fixture cannot be read.
        sqlite3.Error: The store database cannot be initialized.
    """
    source_path = Path(source_dir).resolve()

    with TemporaryDirectory(prefix="store-benchmark-") as temporary_dir:
        environment_path = Path(temporary_dir).resolve() / "data"
        copytree(source_path, environment_path)
        store_sql = STORE_FIXTURE.read_text(encoding="utf-8")
        with closing(sqlite3.connect(environment_path / "store.sqlite3")) as database:
            database.executescript(store_sql)
        yield environment_path


def read_store_snapshot(environment_path: Path) -> StoreSnapshot | None:
    """Read orders, order items, and catalog prices in one trial database transaction."""
    try:
        sandbox = environment_path.resolve(strict=True)
        database_path = (sandbox / "store.sqlite3").resolve(strict=True)
        if not database_path.is_relative_to(sandbox):
            raise ValueError("The snapshot database must be inside the sandbox.")

        with closing(
            sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
        ) as database:
            database.execute("BEGIN")
            items_by_order: dict[int, dict[int, OrderItemSnapshot]] = {}
            for order_id, product_id, quantity, unit_price_cents in database.execute(
                "SELECT order_id, product_id, quantity, unit_price_cents "
                "FROM order_items ORDER BY order_id, product_id"
            ):
                items_by_order.setdefault(order_id, {})[product_id] = OrderItemSnapshot(
                    quantity=quantity, unit_price_cents=unit_price_cents
                )
            orders = {
                order_id: OrderSnapshot(
                    customer_id=customer_id,
                    delivery_address=delivery_address,
                    items=items_by_order.get(order_id, {}),
                )
                for order_id, customer_id, delivery_address in database.execute(
                    "SELECT id, customer_id, delivery_address FROM orders ORDER BY id"
                )
            }
            if items_by_order.keys() - orders.keys():
                raise sqlite3.IntegrityError(
                    "Order items exist without a matching order."
                )

            product_prices = dict(
                database.execute("SELECT id, price_cents FROM products ORDER BY id")
            )
    except (OSError, sqlite3.Error) as exc:
        logger.warning("Could not read the store snapshot: %s", exc)
        return None

    return StoreSnapshot(orders=orders, product_prices=product_prices)
