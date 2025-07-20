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
                
                user_update_result = await self.db["users"].update_one(
                    {"_id": user_object_id},
                    {"$inc": {"credits": float(topup_request.amount)}},
                    session=session
                )
                
                if user_update_result.matched_count == 0:
                    raise ValueError("User not found")
                
                updated_user = await self.db["users"].find_one(
                    {"_id": user_object_id}, session=session
                )
                
                new_balance = Decimal(str(updated_user["credits"]))
                
                return CreditTopupResponse(
                    transaction_id=str(transaction_result.inserted_id),
                    amount=topup_request.amount,
                    new_balance=new_balance,
                    message=f"Successfully added {topup_request.amount} credits"
                )

    async def get_user_balance(self, user_id: str) -> Decimal:
        user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found")
        return Decimal(str(user.get("credits", 0)))

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