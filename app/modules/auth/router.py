from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.pagination import Order
from app.core.responses import error_responses
from app.core.schemas import Cursor, PageResponse, SearchTerm
from app.modules.auth.dependencies import (
    AuthGuardDep,
    AuthServiceDep,
    get_current_user,
    require_permission,
)
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.models import User
from app.modules.auth.permissions import USERS_WRITE
from app.modules.auth.schemas import (
    AuthSession,
    AuthUser,
    LoginRequest,
    SignupRequest,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])

can_manage_users = Depends(require_permission(USERS_WRITE))


def client_ip(request: Request) -> str:
    # Detrás del proxy de Railway uvicorn deja aquí la IP real (--proxy-headers).
    return request.client.host if request.client else "unknown"


@router.post(
    "/signup",
    response_model=AuthSession,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(409, 429),
)
async def signup(
    body: SignupRequest, request: Request, service: AuthServiceDep, guard: AuthGuardDep
):
    guard.before_signup(ip=client_ip(request), email=body.email)
    # Los permisos no vienen del body: el servicio siempre asigna solo lectura.
    return await service.signup(
        full_name=body.full_name,
        email=body.email,
        password=body.password.get_secret_value(),
    )


@router.post(
    "/login",
    response_model=AuthSession,
    responses=error_responses(403, 429),
)
async def login(body: LoginRequest, request: Request, service: AuthServiceDep, guard: AuthGuardDep):
    guard.before_login(ip=client_ip(request), email=body.email)
    try:
        session = await service.login(email=body.email, password=body.password.get_secret_value())
    except InvalidCredentialsError:
        guard.login_failed(body.email)
        raise
    guard.login_succeeded(body.email)
    return session


@router.get("/me", response_model=AuthUser, responses=error_responses())
async def me(user: Annotated[User, Depends(get_current_user)]):
    # get_current_user ya cargó el usuario de la base: los permisos son los actuales.
    return user


@users_router.get(
    "",
    response_model=PageResponse[AuthUser],
    dependencies=[can_manage_users],
    responses=error_responses(),
)
async def list_users(
    service: AuthServiceDep,
    is_active: bool | None = None,  # omitido: activos e inactivos
    q: SearchTerm | None = None,  # coincidencia parcial en email y nombre
    sort: Literal["email", "created_at"] = "email",
    order: Order = "asc",
    after: Cursor | None = None,
):
    return await service.list_page(q=q, is_active=is_active, sort=sort, order=order, after=after)


@users_router.patch(
    "/{user_id}",
    response_model=AuthUser,
    dependencies=[can_manage_users],
    responses=error_responses(404, 409),
)
async def update_user(user_id: UUID, body: UserUpdate, service: AuthServiceDep):
    return await service.update_user(user_id, body.model_dump(exclude_unset=True))
