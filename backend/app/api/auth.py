from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import login_limit, register_limit
from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest, TokenResponse, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(register_limit)]
)
async def register(body: RegisterRequest, session: SessionDep) -> UserRead:
    try:
        user = await auth_service.register_user(
            session, email=body.email, password=body.password, name=body.name
        )
    except auth_service.RegistrationClosed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Registration is closed"
        ) from None
    except auth_service.EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from None
    return UserRead.model_validate(user)


@router.post("/login", dependencies=[Depends(login_limit)])
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> TokenResponse:
    # OAuth2 form fields are fixed by the spec: the email travels in `username`.
    try:
        user = await auth_service.authenticate(session, email=form.username, password=form.password)
    except auth_service.InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me")
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
