# Scenario output JSON schema

`ScenarioOutput` records the evidence from one completed scenario execution. The [result schema](result.md) stores this object in `report.cases[*].output`. Each repetition has its own output. [Model definitions](../../src/benchmark/schemas/scenario_output.py)

## Example

In this single-turn example, the customer asks about their order and the tool returns its details. The scenario requests no final-state check, so both snapshots are `null`. The example shows the tool-event fields used by the benchmark.

```json
{
  "responses": ["The delivery address for order 101 is Testowa 1."],
  "tool_events": [
    {
      "turn": 1,
      "part_kind": "tool-call",
      "tool_name": "get_order_details",
      "tool_call_id": "call_1",
      "args": "{\"order_id\":101}"
    },
    {
      "turn": 1,
      "part_kind": "tool-return",
      "tool_name": "get_order_details",
      "tool_call_id": "call_1",
      "outcome": "success",
      "content": {
        "order_id": 101,
        "delivery_address": "Testowa 1",
        "items": [
          {"product_id": 10, "quantity": 1, "unit_price_cents": 14999},
          {"product_id": 12, "quantity": 2, "unit_price_cents": 2999}
        ]
      }
    }
  ],
  "store_before": null,
  "store_after": null
}
```

## Fields

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `responses` | array of strings | Yes | — | Agent replies in prompt order, one per completed turn. |
| `tool_events` | array of objects | Yes | — | Tool calls and returns from each turn, in recorded order. An empty array means no such events were recorded. |
| `store_before` | object or null | No | `null` | Store snapshot taken after the sandbox is initialized and before the first prompt. |
| `store_after` | object or null | No | `null` | Store snapshot taken after the last turn and before the sandbox is removed. |

### Tool events

The runner serializes the Pydantic AI `ToolCallPart` and `ToolReturnPart` entries from each turn's new messages and adds the one-based `turn`. A `tool-call` records the requested tool name and arguments (`args` can be a JSON string or an object). A `tool-return` records the outcome and returned content. To follow a call through the trace, match its `turn`, `tool_name`, and `tool_call_id`. A tool can return an application error in `content` even when its `outcome` is `success`. [Runner](../../src/benchmark/runner.py) · [Tool evaluator](../../src/benchmark/evaluators/tool_expectations.py)

### Store snapshot

Both snapshots use `StoreSnapshot`. A snapshot includes all rows for the fields below. IDs are integer keys in Python and string keys in JSON. [Snapshot reader](../../src/benchmark/environment.py) · [Store database and fixture](../store-database.md)

| Field | JSON type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `orders` | object | Yes | — | Maps each order ID to an `OrderSnapshot`. |
| `product_prices` | object | Yes | — | Maps each product ID to its current catalog price in grosz, from `products.price_cents`. |
| `orders.<order_id>.customer_id` | integer | Yes | — | Customer who owns the order. |
| `orders.<order_id>.delivery_address` | string | Yes | — | Shipping address on the order. |
| `orders.<order_id>.items` | object or null | No | `null` | Maps product IDs to order lines. Current snapshots use `{}` for an order with no lines. An omitted or `null` field means line data was unavailable in that snapshot. |
| `orders.<order_id>.items.<product_id>.quantity` | integer | Yes | — | Number of units on the order line (`OrderItemSnapshot`). |
| `orders.<order_id>.items.<product_id>.unit_price_cents` | integer | Yes | — | Unit price in grosz recorded on that order line. |

The initial fixture produces the following `StoreSnapshot` for `store_before`.

```json
{
  "orders": {
    "101": {
      "customer_id": 1,
      "delivery_address": "Testowa 1",
      "items": {
        "10": {"quantity": 1, "unit_price_cents": 14999},
        "12": {"quantity": 2, "unit_price_cents": 2999}
      }
    },
    "102": {
      "customer_id": 2,
      "delivery_address": "Testowa 2",
      "items": {
        "10": {"quantity": 1, "unit_price_cents": 14999}
      }
    }
  },
  "product_prices": {"10": 14999, "11": 7999, "12": 2999}
}
```

Order `101` contains two units of product `12` at 2999 grosz each. A later catalog price update changes `product_prices["12"]`. The order line keeps the unit price recorded at purchase.

## Validation

The output and snapshot models use Pydantic's default validation and ignore unknown model fields. The two arrays are required and may be empty. Each tool event is a string-keyed dictionary, so its individual fields and their relationships are not validated by this schema. Event fields beyond those in the example can vary with the serialized message part.

## Interpretation

The runner collects tool events for every scenario. It captures snapshots only when the scenario declares at least one `final_state_change` check. A snapshot is `null` when capture was skipped or the reader encountered a file or SQLite error. If a turn raises an exception, the runner records a failed case without a partial `ScenarioOutput`. See the [result schema](result.md).

The snapshot pair shows changes that persist at the end of the trial. A value changed and restored between snapshots appears unchanged, and a difference alone cannot identify the call that caused it. The tool trace shows what was requested and returned. The responses show what the agent actually said to the user. [Tool expectations](scenario.md) · [Deterministic evaluator](../../src/benchmark/evaluators/tool_expectations.py)
