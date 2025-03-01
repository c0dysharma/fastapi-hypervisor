from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Organisation, OrganisationMember, User

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class JoinOrganisationInput(BaseModel):
    invite_code: str
    user_id: str
    role: str


@router.post("/organisation_members")
async def join_organisation(args: JoinOrganisationInput, session: SessionDep):
    organisation = session.exec(select(Organisation).where(
        Organisation.invite_code == args.invite_code)).first()
    if not organisation:
        raise HTTPException(
            status_code=404, detail="Organisation not found")

    user = session.exec(select(User).where(
        User.id == args.user_id)).first()
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
        organisation_id=organisation.id, user_id=user.id, role=args.role)
    session.add(member)
    session.commit()
    session.refresh(member)

    return member
