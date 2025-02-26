import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str
    organisations: List["OrganisationMember"] = Relationship(
        back_populates="user")


class Cluster(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    name: str
    cpu: int
    ram: int
    gpu: int


class Organisation(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    name: str
    invite_code: str
    members: List["OrganisationMember"] = Relationship(
        back_populates="organisation")


class OrganisationMember(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    organisation_id: str = Field(foreign_key="organisation.id")
    user_id: str = Field(foreign_key="user.id")
    role: str = Field(default="dev")
    organisation: Optional[Organisation] = Relationship(
        back_populates="members")
    user: Optional[User] = Relationship(back_populates="organisations")
