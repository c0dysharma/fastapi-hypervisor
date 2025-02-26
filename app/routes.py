from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select
from app.database import engine
from app.models import Organisation, OrganisationMember, User
from loguru import logger
import random
import string

router = APIRouter()


class UserInput(BaseModel):
    username: str
    password: str


# User routes
@router.get("/user/{username}")
async def get_user(username: str):
    with Session(engine) as session:
        user = session.exec(select(User).where(
            User.username == username)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # remove password key from user
        user.password = None
        return user


@router.post("/user")
async def create_user(user: UserInput):
    with Session(engine) as session:
        found_user = session.exec(select(User).where(
            User.username == user.username)).first()
        if found_user:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(username=user.username, password=user.password)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

# Organisation routes

# route to create organisation


class CreateOrganisationInput(BaseModel):
    name: str
    user_id: str


@router.post("/organisation")
def create_organisation(args: CreateOrganisationInput):
    with Session(engine) as session:
        user = session.exec(select(User).where(
            User.id == args.user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        invite_code = ''.join(random.choices(string.digits, k=6))
        organisation = Organisation(name=args.name, invite_code=invite_code)
        session.add(organisation)
        session.commit()
        session.refresh(organisation)

        member = OrganisationMember(
            organisation_id=organisation.id, user_id=user.id, role="admin")
        session.add(member)
        session.commit()
        session.refresh(member)

        result = {
            "id": organisation.id,
            "name": organisation.name,
            "invite_code": organisation.invite_code
        }

        return result

# route to get organisation details


@router.get("/organisation/{org_id}")
async def get_organisation(org_id: str):
    with Session(engine) as session:
        organisation = session.exec(select(Organisation).where(
            Organisation.id == org_id)).first()
        if not organisation:
            raise HTTPException(
                status_code=404, detail="organisation not found")

        return organisation

# organisation member routes

# route to join organisation


class JoinOrganisationInput(BaseModel):
    invite_code: str
    user_id: str
    role: str


@router.post("/organisation_member")
async def join_organisation(input: JoinOrganisationInput):
    with Session(engine) as session:
        organisation = session.exec(select(Organisation).where(
            Organisation.invite_code == input.invite_code)).first()
        if not organisation:
            raise HTTPException(
                status_code=404, detail="Organisation not found")

        user = session.exec(select(User).where(
            User.id == input.user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # if already a member of the organisation
        member = session.exec(
            select(OrganisationMember).where(
                (OrganisationMember.organisation_id == organisation.id) &
                (OrganisationMember.user_id == user.id)
            )
        ).first()
        if member:
            raise HTTPException(
                status_code=400, detail="User already a member of the organisation")

        member = OrganisationMember(
            organisation_id=organisation.id, user_id=user.id, role=input.role)
        session.add(member)
        session.commit()
        session.refresh(member)

        return member
