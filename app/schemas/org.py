from pydantic import BaseModel


class OrgOut(BaseModel):
    id: str
    name: str
