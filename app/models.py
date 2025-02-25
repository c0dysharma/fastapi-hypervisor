from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str

class Cluster(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cpu: int
    ram: int
    gpu: int
