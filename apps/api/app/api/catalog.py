from fastapi import APIRouter, Depends

from app.api.deps import get_current_membership
from app.modules.auth.models import Membership
from app.modules.catalog.orders import list_test_orders

router = APIRouter(prefix="/catalog")


@router.get("/test-orders")
def test_orders(_membership: Membership = Depends(get_current_membership)) -> dict[str, list[dict[str, object]]]:
    return {
        "test_orders": [
            {
                "code": item.code,
                "description": item.description,
                "amount_minor": item.amount_minor,
                "display_amount": item.display_amount,
                "currency": item.currency,
            }
            for item in list_test_orders()
        ]
    }
