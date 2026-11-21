"""Evidence recorded during one scenario execution."""

from pydantic import BaseModel


class OrderItemSnapshot(BaseModel):
    quantity: int
    unit_price_cents: int


class OrderSnapshot(BaseModel):
    """Order data with items keyed by product ID. Older snapshots omit items."""

    customer_id: int
    delivery_address: str
    items: dict[int, OrderItemSnapshot] | None = None


class StoreSnapshot(BaseModel):
    orders: dict[int, OrderSnapshot]
    product_prices: dict[int, int]


class ScenarioOutput(BaseModel):
    responses: list[str]
    tool_events: list[dict[str, object]]
    store_before: StoreSnapshot | None = None
    store_after: StoreSnapshot | None = None
