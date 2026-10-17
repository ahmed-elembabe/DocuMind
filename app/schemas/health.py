from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
