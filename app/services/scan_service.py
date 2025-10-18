import asyncio
import time
import json
from typing import Dict, Any, List, AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
import httpx

from app.models.scan import ScanCreate, VulnerabilityCreate

SCANNER_HOSTS = {
    "static_scanner": "http://localhost:8001",
    "llm_scanner": "http://llm-scanner-service:8000",
    "dast_scanner": "http://dast-scanner-service:8000",
}

async def update_scan_status(db: AsyncIOMotorDatabase, scan_id: str, status: str, progress_percent: int, progress_text: str):
    """Updates the scan status in the database."""
    update_data = {
        "status": status,
        "progress_percent": progress_percent,
        "progress_text": progress_text,
        "updated_at": datetime.now(timezone.utc)
    }
    
    if status == "completed":
        update_data["finished_at"] = datetime.now(timezone.utc)
    
    await db["scans"].update_one(
        {"_id": ObjectId(scan_id)},
        {"$set": update_data}
    )
    
    print(
        f"[{time.time():.2f}] SCAN UPDATE (ID: {scan_id}): "
        f"Status='{status}', Progress={progress_percent}%, Text='{progress_text}'"
    )

async def stream_scan_progress(db: AsyncIOMotorDatabase, scan_id: str) -> AsyncGenerator[str, None]:
    """
    Stream scan progress updates via SSE.
    This function yields formatted SSE data for real-time updates.
    """
    last_update_time = None
    connection_start = datetime.now(timezone.utc)
    max_connection_time = 3600  # 1 hour max connection time
    
    try:
        yield json.dumps({'event': 'connected', 'scan_id': scan_id, 'timestamp': connection_start.isoformat()})
        
        while True:
            try:
                if (datetime.now(timezone.utc) - connection_start).total_seconds() > max_connection_time:
                    yield json.dumps({'error': 'Connection timeout', 'scan_id': scan_id})
                    break
                
                scan = await db["scans"].find_one({"_id": ObjectId(scan_id)})
                
                if not scan:
                    yield json.dumps({'error': 'Scan not found', 'scan_id': scan_id})
                    break
                
                current_update_time = scan.get("updated_at", scan.get("created_at"))
                
                if last_update_time != current_update_time:
                    scan_status = {
                        "event": "progress",
                        "scan_id": scan_id,
                        "status": scan["status"],
                        "progress_percent": scan["progress_percent"],
                        "progress_text": scan["progress_text"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    yield json.dumps(scan_status)
                    last_update_time = current_update_time
                
                if scan["status"] in ["completed", "failed"]:
                    yield json.dumps({'event': 'finished', 'scan_id': scan_id, 'final_status': scan['status']})
                    break
                    
                await asyncio.sleep(1)
                
            except Exception as e:
                yield json.dumps({'error': f'Stream error: {str(e)}', 'scan_id': scan_id})
                break
    
    except asyncio.CancelledError:
        # Client disconnected
        yield json.dumps({'event': 'disconnected', 'scan_id': scan_id})
    except Exception as e:
        yield json.dumps({'error': f'Connection error: {str(e)}', 'scan_id': scan_id})

async def stream_scanner_progress(response: httpx.Response) -> AsyncGenerator[Dict[str, Any], None]:
    """Stream and parse SSE responses from scanner services"""
    try:
        async for line in response.aiter_lines():
            if not line:
                continue
            print("Scanner response line:", line)
            try:
                data = json.loads(line)
                # Validate expected format with progress and vulnerabilities
                if "progress" not in data:
                    print(f"Warning: Progress field missing in scanner response: {data}")
                    continue
                yield data
            except json.JSONDecodeError:
                print(f"Failed to parse scanner response line: {line}")
                continue
    except Exception as e:
        yield {"error": f"Failed to stream progress: {str(e)}"}

async def run_scan_with_sse(
    db: AsyncIOMotorDatabase,
    scan_id: str,
    repository_name: str,
    scanner_name: str,
    configurations: Dict[str, Any]
):
    print(f"Starting SSE-enabled scan {scan_id} for repo '{repository_name}' with scanner '{scanner_name}'.")

    try:
        await update_scan_status(db, scan_id, "connecting", 5, "Connecting to scanner service...")

        if configurations.get("mock"):
            await update_scan_status(db, scan_id, "scanning", 1, "Scan started")
            mock_updates = [
                {
                    "progress": 5,
                    "message": "Preparing...",
                },
                {
                    "progress": 15,
                    "message": "Indexing files",
                },
                {
                    "progress": 35,
                    "message": "Analyzing",
                    "vulnerabilities": [
                        {
                            "type": "secret_leak",
                            "severity": "high",
                            "description": "API key found in source code",
                            "file_path": "config.py",
                            "line": 15,
                            "metadata": {"key_type": "api_key"}
                        }
                    ]
                },
                {
                    "progress": 60,
                    "message": "Aggregating results",
                    "vulnerabilities": [
                        {
                            "type": "sql_injection",
                            "severity": "critical",
                            "description": "Possible SQL injection in query parameter",
                            "file_path": "app/api/v1/endpoints/users.py",
                            "line": 45,
                            "metadata": {"query_param": "user_id"}
                        }
                    ]
                },
                {
                    "progress": 85,
                    "message": "Finalizing",
                },
                {
                    "progress": 100,
                    "message": "Scan completed",
                }
            ]
            
            for update in mock_updates:
                await asyncio.sleep(0.3)
                progress = update["progress"]
                message = update.get("message", "Processing...")
                status = "completed" if progress >= 100 else "scanning"
                
                await update_scan_status(db, scan_id, status, progress, message)
                
                if "vulnerabilities" in update:
                    await store_vulnerabilities(db, scan_id, update["vulnerabilities"])
            
            return

        base_url = SCANNER_HOSTS.get(scanner_name)
        if not base_url:
            raise ValueError(f"Scanner service not found: {scanner_name}")

        scan_url = f"{base_url.rstrip('/')}/scan"

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                print("scanning url: ", scan_url)
                async with client.stream("POST", scan_url, json={"path": repository_name}) as response:
                    if response.status_code != 200:
                        error_msg = f"Scanner service returned status {response.status_code}"
                        await update_scan_status(db, scan_id, "failed", 100, error_msg)
                        return

                    await update_scan_status(db, scan_id, "scanning", 1, "Scan started")

                    async for update in stream_scanner_progress(response):
                        print("update from scanner: ", update)

                        if "error" in update:
                            await update_scan_status(db, scan_id, "failed", 100, update["error"])
                            return

                        # Get progress from the standardized response format
                        progress = update.get("progress", 0)
                        # Default to scanning status while in progress
                        status = "completed" if progress >= 100 else "scanning"
                        message = update.get("message", "Processing...")
                        
                        await update_scan_status(db, scan_id, status, progress, message)
                        
                        if "vulnerabilities" in update:
                            await store_vulnerabilities(db, scan_id, update["vulnerabilities"])
                        
                        if progress >= 100:
                            break

            except Exception as e:
                error_msg = f"Failed to connect to scanner: {str(e)}"
                await update_scan_status(db, scan_id, "failed", 100, error_msg)
                return
                
    except Exception as e:
        error_message = f"SSE Scan failed: {str(e)}"
        print(error_message)
        await update_scan_status(db, scan_id, "failed", 100, error_message)

async def store_vulnerabilities(db: AsyncIOMotorDatabase, scan_id: str, vulnerabilities: List[Dict[str, Any]]):
    """Store vulnerabilities from scanner service in database."""
    for vuln_data in vulnerabilities:
        # Ensure the vulnerability data matches our model
        vuln_create = VulnerabilityCreate(
            scan_id=scan_id,
            type=vuln_data.get("type", "unknown"),
            severity=str(vuln_data.get("severity", "unknown")),
            description=vuln_data.get("description", ""),
            location={
                "file_path": vuln_data.get("file_path", ""),
                "line": vuln_data.get("line", 0),
            },
            metadata=vuln_data.get("metadata", {})
        )
        await db["vulnerabilities"].insert_one(vuln_create.model_dump())
