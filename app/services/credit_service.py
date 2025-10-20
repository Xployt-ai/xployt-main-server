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

    def _decimal_to_float(self, value: Decimal) -> float:
        """Convert Decimal to float for MongoDB storage"""
        return float(value)

    def _float_to_decimal(self, value: float) -> Decimal:
        """Convert float from MongoDB to Decimal"""
        return Decimal(str(value))

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
        
        # Convert Decimal to dict with float for MongoDB storage
        transaction_data = transaction_create.model_dump()
        transaction_data["amount"] = self._decimal_to_float(transaction_create.amount)
        transaction_data["status"] = "completed"  # Add status field

        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                transaction_result = await self.db["credit_transactions"].insert_one(
                    transaction_data, session=session
                )
                
                credit_update_result = await self.db["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance": self._decimal_to_float(topup_request.amount)},
                        "$set": {"last_updated": datetime.utcnow()}
                    },
                    upsert=True,
                    session=session
                )
                
                updated_credits = await self.db["user_credits"].find_one(
                    {"user_id": user_id}, session=session
                )
                
                new_balance = self._float_to_decimal(updated_credits["balance"])

                return CreditTopupResponse(
                    transaction_id=str(transaction_result.inserted_id),
                    amount=topup_request.amount,
                    new_balance=new_balance,
                    message=f"Successfully added {topup_request.amount} credits"
                )

    async def debit_credits(
        self,
        user_id: str,
        amount: Decimal,
        description: str = "",
        transaction_type: str = "scan_debit",
    ) -> str:
        """Debit credits from a user's balance for usage (e.g., scans).

        Creates a transaction with positive amount and decreases the user's balance atomically.
        Raises ValueError("Insufficient credits") if balance is not enough.
        """
        user_object_id = ObjectId(user_id)

        user_exists = await self.db["users"].find_one({"_id": user_object_id})
        if not user_exists:
            raise ValueError("User not found")

        amount_float = self._decimal_to_float(amount)

        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                credits_doc = await self.db["user_credits"].find_one({"user_id": user_id}, session=session)
                current_balance = float(credits_doc.get("balance", 0.0)) if credits_doc else 0.0

                if current_balance < amount_float:
                    pass
                    # raise ValueError("Insufficient credits")

                transaction_data = {
                    "user_id": user_id,
                    "amount": amount_float,
                    "transaction_type": transaction_type,
                    "description": description or "Usage debit",
                    "created_at": datetime.utcnow(),
                    "status": "completed",
                }

                result = await self.db["credit_transactions"].insert_one(transaction_data, session=session)

                await self.db["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance": -amount_float},
                        "$set": {"last_updated": datetime.utcnow()},
                    },
                    upsert=True,
                    session=session,
                )

                return str(result.inserted_id)

    async def refund_credits(
        self,
        user_id: str,
        amount: Decimal,
        description: str = "",
        transaction_type: str = "scan_refund",
    ) -> str:
        """Refund credits back to a user's balance (e.g., when a scan fails)."""
        user_object_id = ObjectId(user_id)

        user_exists = await self.db["users"].find_one({"_id": user_object_id})
        if not user_exists:
            raise ValueError("User not found")

        amount_float = self._decimal_to_float(amount)

        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                transaction_data = {
                    "user_id": user_id,
                    "amount": amount_float,
                    "transaction_type": transaction_type,
                    "description": description or "Usage refund",
                    "created_at": datetime.utcnow(),
                    "status": "completed",
                }

                result = await self.db["credit_transactions"].insert_one(transaction_data, session=session)

                await self.db["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance": amount_float},
                        "$set": {"last_updated": datetime.utcnow()},
                    },
                    upsert=True,
                    session=session,
                )

                return str(result.inserted_id)

    async def get_user_balance(self, user_id: str) -> Decimal:
        user_exists = await self.db["users"].find_one({"_id": ObjectId(user_id)})
        if not user_exists:
            raise ValueError("User not found")
            
        user_credits = await self.db["user_credits"].find_one({"user_id": user_id})
        if not user_credits:
            await self._initialize_user_credits(user_id)
            user_credits = {"balance": 0.0, "last_monthly_topup_at": None}

        # Check if user is pro and needs monthly topup
        if user_exists.get("is_pro", False):
            await self._check_and_apply_monthly_topup(user_id, user_credits)
            # Refetch credits after potential topup
            user_credits = await self.db["user_credits"].find_one({"user_id": user_id})
        
        return self._float_to_decimal(user_credits.get("balance", 0.0))

    async def get_transaction_history(self, user_id: str, limit: int = 50) -> list[CreditTransaction]:
        cursor = self.db["credit_transactions"].find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit)
        
        transactions = []
        async for transaction_doc in cursor:
            # Convert MongoDB document to dict and add missing fields
            transaction_dict = dict(transaction_doc)
            transaction_dict["id"] = str(transaction_dict["_id"])
            # Convert float back to Decimal for the model
            transaction_dict["amount"] = self._float_to_decimal(transaction_dict["amount"])
            # Add default status if missing
            if "status" not in transaction_dict:
                transaction_dict["status"] = "completed"
            transactions.append(CreditTransaction(**transaction_dict))

        return transactions

    async def get_transaction_by_id(self, transaction_id: str, user_id: str) -> Optional[CreditTransaction]:
        transaction_doc = await self.db["credit_transactions"].find_one({
            "_id": ObjectId(transaction_id),
            "user_id": user_id
        })
        
        if not transaction_doc:
            return None
            
        # Convert MongoDB document to dict and add missing fields
        transaction_dict = dict(transaction_doc)
        transaction_dict["id"] = str(transaction_dict["_id"])
        # Convert float back to Decimal for the model
        transaction_dict["amount"] = self._float_to_decimal(transaction_dict["amount"])
        # Add default status if missing
        if "status" not in transaction_dict:
            transaction_dict["status"] = "completed"
        return CreditTransaction(**transaction_dict)

    async def _initialize_user_credits(self, user_id: str) -> None:
        """Initialize credit balance for a user if it doesn't exist"""
        credit_balance_data = {
            "user_id": user_id,
            "balance": 0.0,  # Store as float in MongoDB
            "last_updated": datetime.utcnow(),
            "last_monthly_topup_at": None
        }
        await self.db["user_credits"].insert_one(credit_balance_data)

    async def subscribe_to_pro(self, user_id: str) -> dict:
        """Subscribe user to pro plan and give initial monthly credits"""
        user_object_id = ObjectId(user_id)
        
        user = await self.db["users"].find_one({"_id": user_object_id})
        if not user:
            raise ValueError("User not found")
        
        if user.get("is_pro", False):
            raise ValueError("User is already a pro user")
        
        async with await self.db.client.start_session() as session:
            async with session.start_transaction():
                # Update user to pro status
                await self.db["users"].update_one(
                    {"_id": user_object_id},
                    {"$set": {"is_pro": True}},
                    session=session
                )
                
                # Create transaction for initial pro credits
                transaction_data = {
                    "user_id": user_id,
                    "amount": 500.0,  # Store as float
                    "transaction_type": "pro_monthly",
                    "description": "Pro user monthly credit pack",
                    "created_at": datetime.utcnow(),
                    "status": "completed"  # Add status field
                }

                await self.db["credit_transactions"].insert_one(
                    transaction_data, session=session
                )
                
                # Update credit balance and set monthly topup timestamp
                current_time = datetime.utcnow()
                await self.db["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {"balance": 500.0},
                        "$set": {
                            "last_updated": current_time,
                            "last_monthly_topup_at": current_time
                        }
                    },
                    upsert=True,
                    session=session
                )
                
                return {"message": "Successfully subscribed to pro plan", "credits_added": 500}

    async def unsubscribe_from_pro(self, user_id: str) -> dict:
        """Unsubscribe user from pro plan"""
        user_object_id = ObjectId(user_id)
        
        user = await self.db["users"].find_one({"_id": user_object_id})
        if not user:
            raise ValueError("User not found")
        
        if not user.get("is_pro", False):
            raise ValueError("User is not a pro user")
        
        await self.db["users"].update_one(
            {"_id": user_object_id},
            {"$set": {"is_pro": False}}
        )
        
        return {"message": "Successfully unsubscribed from pro plan"}

    async def _check_and_apply_monthly_topup(self, user_id: str, user_credits: dict) -> None:
        """Check if pro user needs monthly topup and apply it"""
        last_topup = user_credits.get("last_monthly_topup_at")
        current_time = datetime.utcnow()
        
        # If never topped up or more than 30 days since last topup
        should_topup = (
            last_topup is None or 
            (current_time - last_topup).days >= 30
        )
        
        if should_topup:
            async with await self.db.client.start_session() as session:
                async with session.start_transaction():
                    # Create transaction for monthly pro credits
                    transaction_data = {
                        "user_id": user_id,
                        "amount": 500.0,  # Store as float
                        "transaction_type": "pro_monthly",
                        "description": "Pro user monthly credit pack",
                        "created_at": current_time,
                        "status": "completed"  # Add status field
                    }

                    await self.db["credit_transactions"].insert_one(
                        transaction_data, session=session
                    )
                    
                    # Update credit balance and monthly topup timestamp
                    await self.db["user_credits"].update_one(
                        {"user_id": user_id},
                        {
                            "$inc": {"balance": 500.0},
                            "$set": {
                                "last_updated": current_time,
                                "last_monthly_topup_at": current_time
                            }
                        },
                        session=session
                    )
