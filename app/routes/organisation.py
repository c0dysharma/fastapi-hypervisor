import random
import string

from typing import Annotated
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


@router.post("/organisations")
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

    result = {
        "id": organisation.id,
        "name": organisation.name,
        "invite_code": organisation.invite_code
    }

    return result


@router.get("/organisations/{org_id}")
async def get_organisation(org_id: str, session: SessionDep):
    organisation = session.exec(select(Organisation).where(
        Organisation.id == org_id)).first()
    if not organisation:
        raise HTTPException(
            status_code=404, detail="organisation not found")

    return organisation
