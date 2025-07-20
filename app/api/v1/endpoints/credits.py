from fastapi import APIRouter, Depends, HTTPException
from typing import List
from decimal import Decimal
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.credit import (
    CreditTopupRequest,
    CreditTopupResponse,
    CreditTransaction
)
from app.services.credit_service import CreditService

router = APIRouter()

@router.post("/topup", response_model=CreditTopupResponse)
async def topup_credits(
    topup_request: CreditTopupRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Top up user's credit balance.
    
    Args:
        topup_request: Contains the amount and optional description
        db: Database dependency
        current_user: Current authenticated user
        
    Returns:
        CreditTopupResponse with transaction details and new balance
    """
    credit_service = CreditService(db)
    
    try:
        result = await credit_service.topup_credits(current_user.id, topup_request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process credit topup: {str(e)}")

@router.get("/balance")
async def get_credit_balance(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's credit balance.
    
    Returns:
        dict: Contains the user's current credit balance
    """
    credit_service = CreditService(db)
    
    try:
        balance = await credit_service.get_user_balance(current_user.id)
        return {"balance": balance, "user_id": current_user.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get credit balance: {str(e)}")

@router.get("/transactions", response_model=List[CreditTransaction])
async def get_transaction_history(
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the user's credit transaction history.
    
    Args:
        limit: Maximum number of transactions to return (default: 50, max: 100)
        
    Returns:
        List of CreditTransaction objects
    """
    if limit > 100:
        limit = 100
        
    credit_service = CreditService(db)
    
    try:
        transactions = await credit_service.get_transaction_history(current_user.id, limit)
        return transactions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction history: {str(e)}")

@router.get("/transactions/{transaction_id}", response_model=CreditTransaction)
async def get_transaction_by_id(
    transaction_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific transaction by ID.
    
    Args:
        transaction_id: The ID of the transaction to retrieve
        
    Returns:
        CreditTransaction object
    """
    credit_service = CreditService(db)
    
    try:
        transaction = await credit_service.get_transaction_by_id(transaction_id, current_user.id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return transaction
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction: {str(e)}") 