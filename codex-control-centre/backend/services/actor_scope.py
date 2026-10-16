"""Native FastAPI Bookings authority projection for supervisor v2."""

from dataclasses import dataclass

from fastapi import Depends

from app.api.deps import require_platform_owner
from app.models.user import User


@dataclass(frozen=True, slots=True)
class ActorScope:
    tenant_id: int
    user_id: int
    is_platform_owner: bool = True

    def __post_init__(self) -> None:
        if self.tenant_id <= 0 or self.user_id <= 0 or self.is_platform_owner is not True:
            raise ValueError("invalid_actor_scope")


async def get_actor_scope(user: User = Depends(require_platform_owner)) -> ActorScope:
    """Create immutable scalar scope only after native authority succeeds."""
    return ActorScope(tenant_id=int(user.tenant_id), user_id=int(user.id))
