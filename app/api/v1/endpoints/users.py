from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.services.credit_service import CreditService

router = APIRouter()

@router.post("/subscribe")
async def subscribe_to_pro(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Subscribe user to pro plan.
    
    Grants immediate access to pro features and provides initial 500 credit pack.
    Future monthly credit packs will be automatically granted when accessing balance.
    
    Returns:
        dict: Success message and credits added
    """
    credit_service = CreditService(db)
    
    try:
        result = await credit_service.subscribe_to_pro(current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to subscribe to pro plan: {str(e)}")

@router.post("/unsubscribe")
async def unsubscribe_from_pro(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unsubscribe user from pro plan.
    
    Removes pro status and stops future monthly credit pack grants.
    User keeps existing credits in their balance.
    
    Returns:
        dict: Success message
    """
    credit_service = CreditService(db)
    
    try:
        result = await credit_service.unsubscribe_from_pro(current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe from pro plan: {str(e)}")

@router.get("/pro-status")
async def get_pro_status(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get current user's pro subscription status.
    
    Returns:
        dict: Contains is_pro status and user info
    """
    try:
        return {
            "user_id": current_user.id,
            "is_pro": current_user.is_pro,
            "username": current_user.username
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pro status: {str(e)}") 