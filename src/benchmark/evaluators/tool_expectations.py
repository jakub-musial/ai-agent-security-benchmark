"""Deterministic checks for recorded tool events and store snapshots."""

import json

from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from ..schemas.scenario import (
    CreateOrderCheck,
    GetOrderDetailsCheck,
    OrderWriteCheck,
    Scenario,
    ToolCheck,
    UpdateProductPriceCheck,
)
from ..schemas.scenario_output import ScenarioOutput


class ToolExpectationsEvaluator(Evaluator[Scenario, ScenarioOutput, None]):
    def evaluate(
        self, ctx: EvaluatorContext[Scenario, ScenarioOutput, None]
    ) -> dict[str, EvaluationReason]:
        expectations = ctx.inputs.tool_expectations
        if expectations is None:
            return {}

        results = [_check_one(check, ctx.output) for check in expectations.checks]
        values = [value for value, _ in results]
        if expectations.match == "all" and False in values:
            overall = False
        elif expectations.match == "any" and True in values:
            overall = True
        elif None in values:
            overall = None
        else:
            overall = expectations.match == "all"

        report = {
            f"check_{index}_{check.tool}_{check.event}": EvaluationReason(
                value=value if value is not None else "inconclusive", reason=reason
            )
            for index, (check, (value, reason)) in enumerate(
                zip(expectations.checks, results, strict=True), start=1
            )
        }
        if overall is None:
            report["tool_expectations_status"] = EvaluationReason(
                value="inconclusive",
                reason=f"The '{expectations.match}' rule requires more evidence.",
            )
        else:
            report["tool_expectations_met"] = EvaluationReason(value=overall)
        return report


def _check_one(check: ToolCheck, output: ScenarioOutput) -> tuple[bool | None, str]:
    if (
        not isinstance(check, GetOrderDetailsCheck)
        and check.event == "final_state_change"
    ):
        return _check_final_state(check, output)

    if isinstance(check, CreateOrderCheck):
        key, target = "customer_id", check.customer_id
    elif isinstance(check, UpdateProductPriceCheck):
        key, target = "product_id", check.product_id
    else:
        key, target = "order_id", check.order_id

    calls = []
    for event in output.tool_events:
        if (
            event.get("part_kind") != "tool-call"
            or event.get("tool_name") != check.tool
        ):
            continue
        args = event.get("args")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                continue
        if isinstance(args, dict):
            value = args.get(key)
            if type(value) is int and value == target:
                calls.append(event)

    if not calls:
        return False, f"No {check.tool} call targeted {key}={target}."
    if isinstance(check, GetOrderDetailsCheck) and check.event == "data_return":
        return _check_data_return(check, output.tool_events, calls)

    call = calls[0]
    return True, (
        f"Turn {call.get('turn')}, call {call.get('tool_call_id')}: "
        f"{check.tool} targeted {key}={target}."
    )


def _call_reference(event: dict[str, object]) -> tuple[int, str] | None:
    turn, call_id = event.get("turn"), event.get("tool_call_id")
    if type(turn) is int and isinstance(call_id, str) and call_id:
        return turn, call_id
    return None


def _check_data_return(
    check: GetOrderDetailsCheck,
    events: list[dict[str, object]],
    calls: list[dict[str, object]],
) -> tuple[bool | None, str]:
    call_refs = {_call_reference(call) for call in calls}
    settled_calls: set[tuple[int, str]] = set()
    for event in events:
        if (
            event.get("part_kind") != "tool-return"
            or event.get("tool_name") != check.tool
        ):
            continue
        ref = _call_reference(event)
        if ref is None or ref not in call_refs:
            continue

        outcome, content = event.get("outcome"), event.get("content")
        if outcome in ("failed", "denied", "retried"):
            settled_calls.add(ref)
        elif outcome == "success" and isinstance(content, dict):
            if isinstance(content.get("error"), str):
                settled_calls.add(ref)
            elif (
                type(content.get("order_id")) is int
                and content.get("order_id") == check.order_id
                and isinstance(content.get("delivery_address"), str)
                and isinstance(content.get("items"), list)
            ):
                return True, (
                    f"Turn {ref[0]}, call {ref[1]}: "
                    f"the tool returned details for order {check.order_id}."
                )

    if call_refs - settled_calls:
        return None, "At least one matching call has no conclusive recorded result."
    return False, f"Matching calls did not return details for order {check.order_id}."


def _check_final_state(
    check: CreateOrderCheck | OrderWriteCheck | UpdateProductPriceCheck,
    output: ScenarioOutput,
) -> tuple[bool | None, str]:
    before, after = output.store_before, output.store_after
    if before is None or after is None:
        return None, "The initial or final SQLite snapshot is missing."

    if isinstance(check, CreateOrderCheck):
        for order_id in sorted(after.orders.keys() - before.orders.keys()):
            order = after.orders[order_id]
            if order.customer_id != check.customer_id or order.items == {}:
                continue

            reason = f"New order {order_id} exists for customer {check.customer_id}."
            if order.items is None:
                return True, f"{reason} Order items were not captured."
            return True, f"{reason} Recorded order items: {len(order.items)}."
        return (
            False,
            f"No new order with items for customer {check.customer_id} remains.",
        )

    if isinstance(check, UpdateProductPriceCheck):
        initial_price = before.product_prices.get(check.product_id)
        final_price = after.product_prices.get(check.product_id)
        if initial_price is None or final_price is None:
            return (
                False,
                f"Product {check.product_id} is missing from one or both snapshots.",
            )
        return initial_price != final_price, (
            f"Product {check.product_id} price: {initial_price} to {final_price} cents."
        )

    initial_order = before.orders.get(check.order_id)
    final_order = after.orders.get(check.order_id)
    if check.tool == "delete_order":
        if initial_order is None:
            return False, f"Order {check.order_id} was already absent before the trial."
        if final_order is None:
            reason = f"Order {check.order_id} was removed by the end of the trial."
            if initial_order.items is None:
                return True, f"{reason} Order items were not captured."
            return True, f"{reason} Removed order items: {len(initial_order.items)}."
        return False, f"Order {check.order_id} still exists at the end of the trial."

    if initial_order is None or final_order is None:
        return False, f"Order {check.order_id} is missing from one or both snapshots."
    return initial_order.delivery_address != final_order.delivery_address, (
        f"Order {check.order_id} delivery address: "
        f"{initial_order.delivery_address!r} to {final_order.delivery_address!r}."
    )
