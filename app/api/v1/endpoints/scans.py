from fastapi import APIRouter, Depends, HTTPException
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.scan import ScanRequest, Scan, ScanStatus, ScanCreate, Vulnerability
from app.models.common import ApiResponse
from app.services.scan_service import stream_vulnerabilities_for_scan, run_scan_single_response

router = APIRouter()

@router.post("/", response_model=ApiResponse[dict])
async def start_scan(
    scan_request: ScanRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a scan record, execute the single-response scanner, store results, and return only scan_id.
    Clients should connect to the stream endpoint to receive vulnerabilities.
    """
    try:
        payload = await run_scan_single_response(
            db=db,
            repository_name=scan_request.repository_name,
            scanner_name=scan_request.scanner_name,
            configurations=scan_request.configurations,
            user_id=current_user.id,
        )
        return ApiResponse(data={"scan_id": payload.get("scan_id")}, message="Scan created")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {str(e)}")

@router.get("/{scan_id}/stream")
async def stream_scan_vulnerabilities(
    scan_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream vulnerabilities for a scan. Each SSE event has id = progress and data = Vulnerability JSON.
    """
    # verify the scan belongs to the user
    scan = await db["scans"].find_one({"_id": ObjectId(scan_id), "user_id": current_user.id})
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return EventSourceResponse(stream_vulnerabilities_for_scan(db, scan_id))

    # old status/results endpoints removed

@router.get("/", response_model=ApiResponse[List[Scan]])
async def list_user_scans(
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all scans for the current user.
    """
    try:
        scans_cursor = db["scans"].find({"user_id": current_user.id}).sort("created_at", -1).limit(limit)
        scans_list = await scans_cursor.to_list(length=None)
        
        scans = []
        for scan in scans_list:
            scan["id"] = str(scan["_id"])
            scans.append(Scan(**scan))
        
        return ApiResponse(data=scans, message="Scans retrieved successfully")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list scans: {str(e)}") 