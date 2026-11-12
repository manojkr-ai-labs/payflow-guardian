from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership
from app.core.db import get_db
from app.modules.activity.service import activity_payload, list_activity
from app.modules.auth.models import Membership

router = APIRouter(prefix="/activity")


@router.get("")
def read_activity(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    events = list_activity(db, membership.merchant_id)
    return {"events": [activity_payload(event) for event in events]}
