from app.core.security import verify_token
from fastapi import APIRouter, Depends, HTTPException, status
from sse_starlette.sse import EventSourceResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.scan import ScanCollectionCreate
from app.models.common import ApiResponse
from app.services.scan_service import (
    create_scans_for_collection,
    compute_collection_status,
)

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict])
async def start_scan_collection(
    body: ScanCollectionCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.scanners:
        raise HTTPException(status_code=400, detail="scanners list cannot be empty")

    # Create child scans and start them
    scan_ids = await create_scans_for_collection(
        db=db,
        user_id=current_user.id,
        repository_name=body.repository_name,
        scanners=body.scanners,
        configurations=body.configurations or {},
    )

    # Create the collection document
    doc = {
        "user_id": current_user.id,
        "repository_name": body.repository_name,
        "scanners": body.scanners,
        "scan_ids": scan_ids,
        "status": "scanning",
        "progress_percent": 0,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db["scan_collections"].insert_one(doc)

    return ApiResponse(data={"collection_id": str(result.inserted_id), "scan_ids": scan_ids}, message="Scan collection started")


@router.get("/{collection_id}/status", response_model=ApiResponse[dict])
async def get_collection_status(
    collection_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await db["scan_collections"].find_one({"_id": ObjectId(collection_id), "user_id": current_user.id})
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    scan_ids: List[str] = collection.get("scan_ids", [])
    agg_status, agg_progress = await compute_collection_status(db, scan_ids)

    # Fetch per-scan mini status
    cursor = db["scans"].find({"_id": {"$in": [ObjectId(sid) for sid in scan_ids]}})
    scans = []
    async for s in cursor:
        scans.append({
            "scan_id": str(s["_id"]),
            "status": s.get("status", "pending"),
            "progress_percent": int(s.get("progress_percent", 0) or 0),
            "progress_text": s.get("progress_text", ""),
            "scanner_name": s.get("scanner_name", ""),
        })

    # Update collection aggregate fields
    update = {"status": agg_status, "progress_percent": agg_progress}
    if agg_status in ["completed", "failed"] and not collection.get("finished_at"):
        update["finished_at"] = datetime.now(timezone.utc)
    await db["scan_collections"].update_one({"_id": ObjectId(collection_id)}, {"$set": update})

    return ApiResponse(data={
        "collection": {"status": agg_status, "progress_percent": agg_progress},
        "scans": scans,
    })


@router.get("/", response_model=ApiResponse[List[dict]])
async def list_collections(
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cursor = db["scan_collections"].find({"user_id": current_user.id}).sort("created_at", -1).limit(limit)
    items: List[Dict[str, Any]] = []
    async for c in cursor:
        items.append({
            "id": str(c["_id"]),
            "repository_name": c.get("repository_name"),
            "scanners": c.get("scanners", []),
            "scan_ids": c.get("scan_ids", []),
            "status": c.get("status", "pending"),
            "progress_percent": int(c.get("progress_percent", 0) or 0),
            "created_at": c.get("created_at"),
            "finished_at": c.get("finished_at"),
        })
    return ApiResponse(data=items, message="Collections retrieved successfully")


@router.get("/{collection_id}/results", response_model=ApiResponse[dict])
async def get_collection_results(
    collection_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.scan_service import list_vulnerabilities_for_scan_ids

    collection = await db["scan_collections"].find_one({"_id": ObjectId(collection_id), "user_id": current_user.id})
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    scan_ids: List[str] = collection.get("scan_ids", [])
    vulns = await list_vulnerabilities_for_scan_ids(db, scan_ids)
    return ApiResponse(data={"vulnerabilities": vulns})


@router.get("/{collection_id}/stream")
async def stream_collection(
    collection_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    token: str = "",
):
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
        
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    user["id"] = str(user["_id"])
    user = User(**user)

    if not user:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    async def event_generator():
        last_update = None
        while True:
            collection = await db["scan_collections"].find_one({"_id": ObjectId(collection_id), "user_id": user.id})
            if not collection:
                yield json.dumps({"error": "Collection not found"})
                return

            scan_ids: List[str] = collection.get("scan_ids", [])
            agg_status, agg_progress = await compute_collection_status(db, scan_ids)

            # Fetch all vulnerabilities so far for the collection's scans
            vulnerabilities: List[Dict[str, Any]] = []
            if scan_ids:
                cursor = db["vulnerabilities"].find({"scan_id": {"$in": scan_ids}})
                async for v in cursor:
                    v = dict(v)
                    v["id"] = str(v.get("_id"))
                    v.pop("_id", None)
                    vulnerabilities.append(v)

            state = {
                "event": "progress",
                "collection": {"status": agg_status, "progress_percent": agg_progress},
                "vulnerabilities": vulnerabilities,
            }

            payload = json.dumps(state)
            if payload != last_update:
                last_update = payload
                yield payload

            if agg_status in ["completed", "failed"]:
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


