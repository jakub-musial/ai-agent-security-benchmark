"""Store session shared by the agent and the benchmark scenario schema."""

from dataclasses import dataclass
from enum import StrEnum

_MAX_CUSTOMER_ID = 2**63 - 1


class StoreRole(StrEnum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class StoreSession:
    role: StoreRole
    customer_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, StoreRole):
            raise ValueError("A store session requires a valid role.")

        if self.role is StoreRole.CUSTOMER:
            customer_id = self.customer_id
            if type(customer_id) is not int or not 0 < customer_id <= _MAX_CUSTOMER_ID:
                raise ValueError("A customer session requires a valid customer ID.")
        elif self.customer_id is not None:
            raise ValueError("An administrator session does not have a customer ID.")


DEFAULT_STORE_SESSION = StoreSession(StoreRole.CUSTOMER, customer_id=1)
