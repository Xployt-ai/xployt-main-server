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
from app.models.common import CreditBalanceResponse, ApiResponse
from app.services.credit_service import CreditService

router = APIRouter()

@router.post("/topup", response_model=ApiResponse[CreditTopupResponse])
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
        ApiResponse[CreditTopupResponse] with transaction details and new balance
    """
    credit_service = CreditService(db)
    
    try:
        result = await credit_service.topup_credits(current_user.id, topup_request)
        return ApiResponse(data=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process credit topup: {str(e)}")

@router.get("/balance", response_model=ApiResponse[CreditBalanceResponse])
async def get_credit_balance(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's credit balance.
    
    Returns:
        ApiResponse[CreditBalanceResponse]: Contains the user's current credit balance
    """
    credit_service = CreditService(db)
    
    try:
        balance = await credit_service.get_user_balance(current_user.id)
        balance_response = CreditBalanceResponse(balance=balance, user_id=current_user.id)
        return ApiResponse(data=balance_response, message="Credit balance retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get credit balance: {str(e)}")

@router.get("/transactions", response_model=ApiResponse[List[CreditTransaction]])
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
        ApiResponse[List[CreditTransaction]]: List of CreditTransaction objects
    """
    if limit > 100:
        limit = 100
        
    credit_service = CreditService(db)
    
    try:
        transactions = await credit_service.get_transaction_history(current_user.id, limit)
        return ApiResponse(data=transactions, message="Transaction history retrieved successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction history: {str(e)}")

@router.get("/transactions/{transaction_id}", response_model=ApiResponse[CreditTransaction])
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
        ApiResponse[CreditTransaction]: CreditTransaction object
    """
    credit_service = CreditService(db)
    
    try:
        transaction = await credit_service.get_transaction_by_id(transaction_id, current_user.id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return ApiResponse(data=transaction, message="Transaction retrieved successfully")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction: {str(e)}") 