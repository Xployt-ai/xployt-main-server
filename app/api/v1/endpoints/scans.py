from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.scan import ScanRequest, Scan, ScanStatus, ScanCreate, Vulnerability
from app.models.common import ApiResponse
from app.services.scan_service import run_scan, stream_scan_progress, run_scan_with_sse

router = APIRouter()

@router.post("/", response_model=ApiResponse[dict])
async def start_scan(
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks,
    use_sse: bool = False,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start a new scan for the specified repository and scanner.
    
    Args:
        scan_request: Scan configuration including repository and scanner details
        use_sse: If True, uses SSE-enabled scanning with real scanner services
        
    Returns:
        ApiResponse containing the scan_id of the started scan
    """
    scan_create = ScanCreate(
        repository_name=scan_request.repository_name,
        scanner_name=scan_request.scanner_name,
        configurations=scan_request.configurations,
        user_id=current_user.id
    )
    
    result = await db["scans"].insert_one(scan_create.model_dump())
    scan_id = str(result.inserted_id)
    
    # Choose between SSE-enabled or mock scanning
    if use_sse:
        background_tasks.add_task(
            run_scan_with_sse,
            db,
            scan_id,
            scan_request.repository_name,
            scan_request.scanner_name,
            scan_request.configurations
        )
    else:
        background_tasks.add_task(
            run_scan,
            db,
            scan_id,
            scan_request.repository_name,
            scan_request.scanner_name,
            scan_request.configurations
        )
    
    return ApiResponse(
        data={"scan_id": scan_id, "sse_enabled": use_sse},
        message="Scan started successfully"
    )

@router.get("/{scan_id}", response_model=ApiResponse[ScanStatus])
async def get_scan_status(
    scan_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current status and progress of a scan.
    """
    try:
        scan = await db["scans"].find_one({
            "_id": ObjectId(scan_id),
            "user_id": current_user.id
        })
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan_status = ScanStatus(
            scan_id=scan_id,
            status=scan["status"],
            progress_percent=scan["progress_percent"],
            progress_text=scan["progress_text"]
        )
        
        return ApiResponse(data=scan_status, message="Scan status retrieved successfully")
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to get scan status: {str(e)}")

@router.get("/{scan_id}/stream")
async def stream_scan_status(
    scan_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream real-time scan progress updates via Server-Sent Events (SSE).
    
    This endpoint provides real-time updates for scan progress including:
    - Connection establishment
    - Progress updates (only when status changes)
    - Completion/failure notifications
    - Error handling
    
    The stream automatically closes when the scan completes or fails.
    Maximum connection time is 1 hour to prevent resource leaks.
    """
    try:
        # Verify scan exists and belongs to user
        scan = await db["scans"].find_one({
            "_id": ObjectId(scan_id),
            "user_id": current_user.id
        })
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Return SSE response with proper headers
        return EventSourceResponse(
            stream_scan_progress(db, scan_id),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start SSE stream: {str(e)}")

@router.get("/{scan_id}/results", response_model=ApiResponse[List[Vulnerability]])
async def get_scan_results(
    scan_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all vulnerability results for a completed scan.
    """
    try:
        scan = await db["scans"].find_one({
            "_id": ObjectId(scan_id),
            "user_id": current_user.id
        })
        
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        if scan["status"] != "completed":
            raise HTTPException(status_code=400, detail="Scan is not yet completed")
        
        vulnerabilities_cursor = db["vulnerabilities"].find({"scan_id": scan_id})
        vulnerabilities_list = await vulnerabilities_cursor.to_list(length=None)
        
        vulnerabilities = []
        for vuln in vulnerabilities_list:
            vuln["id"] = str(vuln["_id"])
            vulnerabilities.append(Vulnerability(**vuln))
        
        return ApiResponse(
            data=vulnerabilities,
            message=f"Found {len(vulnerabilities)} vulnerabilities"
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to get scan results: {str(e)}")

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