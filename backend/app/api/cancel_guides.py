from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.schemas.cancel_guide import CancelGuideResponse
from app.services import cancel_guides

router = APIRouter(prefix="/cancel-guides", tags=["cancel-guides"])


@router.get("/{merchant}", response_model=CancelGuideResponse)
def get_cancel_guide(
    merchant: str, user: User = Depends(get_current_user)
) -> CancelGuideResponse:
    guide = cancel_guides.lookup(merchant)
    return CancelGuideResponse(
        merchant_key=guide.merchant_key,
        name=guide.name,
        url=guide.url,
        difficulty=guide.difficulty,
        steps=guide.steps,
        known=guide.known,
    )
