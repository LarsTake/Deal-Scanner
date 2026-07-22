from fastapi import APIRouter
from sqlalchemy import select

from ..context import Context
from ..db_models import WorkspaceMemberRow, WorkspaceRow
from ..schemas import AuthMeResponse, WorkspaceResponse

router = APIRouter(tags=["auth"])


@router.get("/auth/me", response_model=AuthMeResponse)
async def me(context: Context) -> AuthMeResponse:
    result = await context.session.execute(
        select(WorkspaceRow, WorkspaceMemberRow.role)
        .join(WorkspaceMemberRow, WorkspaceMemberRow.workspace_id == WorkspaceRow.id)
        .where(WorkspaceMemberRow.user_id == context.identity.user_id)
    )
    workspaces = [
        WorkspaceResponse(id=workspace.id, name=workspace.name, role=role) for workspace, role in result.all()
    ]
    return AuthMeResponse(
        user_id=context.identity.user_id,
        email=context.identity.email,
        workspaces=workspaces,
    )


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def workspaces(context: Context) -> list[WorkspaceResponse]:
    response = await me(context)
    return response.workspaces
