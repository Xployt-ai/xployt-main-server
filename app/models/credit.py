from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal

class CreditTransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount of credits to add")
    transaction_type: str = Field(default="topup", description="Type of transaction")
    description: Optional[str] = None

class CreditTransactionCreate(CreditTransactionBase):
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CreditTransactionInDB(CreditTransactionBase):
    id: str
    user_id: str
    created_at: datetime
    status: str = Field(default="completed")

class CreditTransaction(CreditTransactionBase):
    id: str
    user_id: str
    created_at: datetime
    status: str

    class Config:
        from_attributes = True

class CreditTopupRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, le=10000, description="Amount of credits to add (max 10,000)")
    description: Optional[str] = Field(None, max_length=255)

class CreditTopupResponse(BaseModel):
    transaction_id: str
    amount: Decimal
    new_balance: Decimal
    message: str

class UserCreditBalance(BaseModel):
    user_id: str
    balance: Decimal = Field(default=Decimal('0'))
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    last_monthly_topup_at: Optional[datetime] = Field(default=None, description="Last time user received monthly pro credits") 