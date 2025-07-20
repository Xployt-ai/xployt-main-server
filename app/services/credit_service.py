from typing import Optional
from decimal import Decimal
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.credit import (
    CreditTransaction,
    CreditTransactionCreate,
    CreditTopupRequest,
    CreditTopupResponse,
    UserCreditBalance
)

class CreditService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def topup_credits(self, user_id: str, topup_request: CreditTopupRequest) -> CreditTopupResponse:
        user_object_id = ObjectId(user_id)
        
        user_exists = await self.db["users"].find_one({"_id": user_object_id})
        if not user_exists:
            raise ValueError("User not found")
        
        transaction_create = CreditTransactionCreate(
            user_id=user_id,
            amount=topup_request.amount,
            description=topup_request.description or "Credit topup"
        )
        
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                transaction_result = await self.db["credit_transactions"].insert_one(
                    transaction_create.model_dump(), session=session
                )
                
                credit_update_result = await self.db["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance": float(topup_request.amount)},
                        "$set": {"last_updated": datetime.utcnow()}
                    },
                    upsert=True,
                    session=session
                )
                
                updated_credits = await self.db["user_credits"].find_one(
                    {"user_id": user_id}, session=session
                )
                
                new_balance = Decimal(str(updated_credits["balance"]))
                
                return CreditTopupResponse(
                    transaction_id=str(transaction_result.inserted_id),
                    amount=topup_request.amount,
                    new_balance=new_balance,
                    message=f"Successfully added {topup_request.amount} credits"
                )

    async def get_user_balance(self, user_id: str) -> Decimal:
        user_exists = await self.db["users"].find_one({"_id": ObjectId(user_id)})
        if not user_exists:
            raise ValueError("User not found")
            
        user_credits = await self.db["user_credits"].find_one({"user_id": user_id})
        if not user_credits:
            await self._initialize_user_credits(user_id)
            return Decimal('0')
        
        return Decimal(str(user_credits.get("balance", 0)))

    async def get_transaction_history(self, user_id: str, limit: int = 50) -> list[CreditTransaction]:
        cursor = self.db["credit_transactions"].find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)
        
        transactions = []
        async for transaction_doc in cursor:
            transaction_doc["id"] = str(transaction_doc["_id"])
            transactions.append(CreditTransaction(**transaction_doc))
        
        return transactions

    async def get_transaction_by_id(self, transaction_id: str, user_id: str) -> Optional[CreditTransaction]:
        transaction_doc = await self.db["credit_transactions"].find_one({
            "_id": ObjectId(transaction_id),
            "user_id": user_id
        })
        
        if not transaction_doc:
            return None
            
        transaction_doc["id"] = str(transaction_doc["_id"])
        return CreditTransaction(**transaction_doc)

    async def _initialize_user_credits(self, user_id: str) -> None:
        """Initialize credit balance for a user if it doesn't exist"""
        credit_balance = UserCreditBalance(user_id=user_id)
        await self.db["user_credits"].insert_one(credit_balance.model_dump()) 