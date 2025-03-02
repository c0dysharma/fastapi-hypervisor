from datetime import datetime
import random
import string

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Organisation, OrganisationMember, User


router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class CreateOrganisationInput(BaseModel):
    name: str
    user_id: str


class OrganisationResponse(BaseModel):
    id: str
    name: str
    invite_code: str


@router.post("/organisations",
             response_model=OrganisationResponse,
             summary="Create a new organization",
             description="Create a new organization and add the user as an admin")
def create_organisation(args: CreateOrganisationInput, session: SessionDep):
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

    result = OrganisationResponse(
        id=organisation.id,
        name=organisation.name,
        invite_code=organisation.invite_code
    )

    return result


class DetailedOrganisationResponse(BaseModel):
    id: str
    name: str
    invite_code: str
    created_at: datetime
    updated_at: Optional[datetime] = None


@router.get("/organisations/{org_id}",
            response_model=DetailedOrganisationResponse,
            summary="Get organization details",
            description="Get details of a specific organization by ID")
async def get_organisation(org_id: str, session: SessionDep):
    organisation = session.exec(select(Organisation).where(
        Organisation.id == org_id)).first()
    if not organisation:
        raise HTTPException(
            status_code=404, detail="organisation not found")

    return organisation
