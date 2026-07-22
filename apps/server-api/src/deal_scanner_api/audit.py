from __future__ import annotations

from uuid import UUID

from .context import RequestContext
from .db_models import AuditEventRow


def record_audit_event(
    context: RequestContext,
    event_type: str,
    aggregate_type: str,
    aggregate_id: UUID | None,
    payload: dict[str, object] | None = None,
) -> None:
    context.session.add(
        AuditEventRow(
            workspace_id=context.workspace_id,
            actor_user_id=context.identity.user_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload or {},
        )
    )
