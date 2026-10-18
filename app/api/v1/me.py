from fastapi import APIRouter

from app.core.deps import CurrentOrgDep
from app.schemas.org import OrgOut

router = APIRouter(tags=["me"])


# بيرجّع الشركة صاحبة المفتاح، مفيد تتأكد بيه إن المفتاح شغال
@router.get("/me", response_model=OrgOut)
def read_me(org: CurrentOrgDep) -> OrgOut:
    return OrgOut(id=org.id, name=org.name)
