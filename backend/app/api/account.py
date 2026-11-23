from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import User

router = APIRouter(prefix="/account", tags=["account"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    """Hard-delete the account and all associated data. Foreign keys cascade
    through connections, transactions, subscriptions, and alerts."""
    db.delete(user)
    db.commit()
