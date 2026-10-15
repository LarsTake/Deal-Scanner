from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentIdentity, Identity, IdentityProvider, get_identity_provider
from .database import get_session, set_request_subject
from .db_models import ExtensionPairingRow, WorkspaceMemberRow, WorkspaceRow
from .settings import get_settings


@dataclass
class RequestContext:
    identity: Identity
    workspace_id: UUID
    session: AsyncSession


async def get_request_context(
    identity: CurrentIdentity,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RequestContext:
    settings = get_settings()
    if settings.database_url.startswith("postgresql"):
        await set_request_subject(session, identity.user_id)
    result = await session.execute(select(WorkspaceMemberRow).where(WorkspaceMemberRow.user_id == identity.user_id))
    membership = result.scalars().first()
    if membership is None:
        if settings.environment == "production" and settings.auth_mode == "supabase":
            raise HTTPException(status_code=403, detail="user has no Deal Scanner workspace")
        workspace = WorkspaceRow(name="Persönlicher Workspace")
        session.add(workspace)
        await session.flush()
        membership = WorkspaceMemberRow(workspace_id=workspace.id, user_id=identity.user_id, role="owner")
        session.add(membership)
    return RequestContext(
        identity=identity,
        workspace_id=membership.workspace_id,
        session=session,
    )


async def get_browser_request_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_development_user: Annotated[str | None, Header()] = None,
    x_extension_pairing: Annotated[str | None, Header()] = None,
    provider: IdentityProvider = Depends(get_identity_provider),
) -> RequestContext:
    if not x_extension_pairing:
        identity = await provider.authenticate(authorization, x_development_user)
        return await get_request_context(identity, session)

    candidate_hash = hashlib.sha256(x_extension_pairing.encode()).hexdigest()
    settings = get_settings()
    if settings.database_url.startswith("postgresql"):
        resolved = (
            await session.execute(
                text("select workspace_id, user_id from deal_scanner.resolve_extension_pairing(:candidate_hash)"),
                {"candidate_hash": candidate_hash},
            )
        ).one_or_none()
        if resolved is None:
            raise HTTPException(status_code=401, detail="invalid or expired pairing token")
        workspace_id, user_id = resolved
    else:
        pairing = (
            await session.execute(
                select(ExtensionPairingRow).where(
                    ExtensionPairingRow.token_hash == candidate_hash,
                    ExtensionPairingRow.revoked_at.is_(None),
                    or_(
                        ExtensionPairingRow.expires_at.is_(None),
                        ExtensionPairingRow.expires_at > datetime.now(UTC),
                    ),
                )
            )
        ).scalar_one_or_none()
        if pairing is None:
            raise HTTPException(status_code=401, detail="invalid or expired pairing token")
        workspace_id, user_id = pairing.workspace_id, pairing.created_by_user_id

    if settings.database_url.startswith("postgresql"):
        await set_request_subject(session, user_id)
    return RequestContext(
        identity=Identity(user_id=user_id, roles=["extension"]),
        workspace_id=workspace_id,
        session=session,
    )


Context = Annotated[RequestContext, Depends(get_request_context)]
BrowserContext = Annotated[RequestContext, Depends(get_browser_request_context)]


def require_workspace(context: RequestContext, workspace_id: UUID | None) -> UUID:
    if workspace_id is not None and workspace_id != context.workspace_id:
        raise HTTPException(status_code=403, detail="workspace access denied")
    return context.workspace_id
