from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import User


router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class UserInput(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    # password intentionally omitted for security


@router.get("/users/{username}",
            response_model=UserResponse,
            summary="Get user by username",
            description="Retrieve a user's information by their username")
async def get_user(username: str, session: SessionDep):
    user = session.exec(select(User).where(
        User.username == username)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # remove password key from user
    user.password = None
    return user


@router.post("/users",
             response_model=UserResponse,
             summary="Create new user",
             description="Create a new user with the given username and password")
async def create_user(user: UserInput, session: SessionDep):
    found_user = session.exec(select(User).where(
        User.username == user.username)).first()
    if found_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(username=user.username, password=user.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
