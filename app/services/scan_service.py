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
    "secret_scanner": "http://secret-scanner-service:8000/scan",
    "sast_scanner": "http://sast-scanner-service:8000/scan",
    "llm_scanner": "http://llm-scanner-service:8000/scan",
    "dast_scanner": "http://dast-scanner-service:8000/scan",
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

async def create_mock_vulnerabilities(db: AsyncIOMotorDatabase, scan_id: str, scanner_name: str) -> List[Dict[str, Any]]:
    """Creates mock vulnerability data based on the scanner type."""
    mock_vulnerabilities = []
    
    if scanner_name == "secret_scanner":
        mock_vulnerabilities = [
            {
                "type": "secret",
                "severity": "high",
                "description": "API key found in environment file",
                "location": {"file": ".env", "line": 5},
                "metadata": {"pattern": "API_KEY=", "value_masked": "sk-***"}
            },
            {
                "type": "secret", 
                "severity": "medium",
                "description": "Database password in configuration",
                "location": {"file": "config/database.js", "line": 12},
                "metadata": {"pattern": "password:", "value_masked": "***"}
            }
        ]
    elif scanner_name == "sast_scanner":
        mock_vulnerabilities = [
            {
                "type": "sast",
                "severity": "critical",
                "description": "SQL injection vulnerability detected",
                "location": {"file": "src/controllers/user.js", "line": 45},
                "metadata": {"cwe": "CWE-89", "confidence": "high"}
            }
        ]
    elif scanner_name == "llm_scanner":
        mock_vulnerabilities = [
            {
                "type": "llm",
                "severity": "medium",
                "description": "Potential authentication bypass in login logic",
                "location": {"file": "src/auth/login.js", "line": 23},
                "metadata": {"reasoning": "LLM detected weak authentication flow", "confidence": "medium"}
            }
        ]
    elif scanner_name == "dast_scanner":
        mock_vulnerabilities = [
            {
                "type": "dast",
                "severity": "high", 
                "description": "XSS vulnerability in user input field",
                "location": {"endpoint": "/api/users", "method": "POST"},
                "metadata": {"payload": "<script>alert(1)</script>", "response_code": 200}
            }
        ]
    
    vulnerability_docs = []
    for vuln_data in mock_vulnerabilities:
        vuln_create = VulnerabilityCreate(scan_id=scan_id, **vuln_data)
        result = await db["vulnerabilities"].insert_one(vuln_create.model_dump())
        vuln_data["id"] = str(result.inserted_id)
        vuln_data["scan_id"] = scan_id
        vulnerability_docs.append(vuln_data)
    
    return vulnerability_docs

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
                # Check connection timeout
                if (datetime.now(timezone.utc) - connection_start).total_seconds() > max_connection_time:
                    yield json.dumps({'error': 'Connection timeout', 'scan_id': scan_id})
                    break
                
                # Get current scan status from database
                scan = await db["scans"].find_one({"_id": ObjectId(scan_id)})
                
                if not scan:
                    yield json.dumps({'error': 'Scan not found', 'scan_id': scan_id})
                    break
                
                current_update_time = scan.get("updated_at", scan.get("created_at"))
                
                # Only send update if status has changed
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
                
                # If scan is completed or failed, send final update and close stream
                if scan["status"] in ["completed", "failed"]:
                    yield json.dumps({'event': 'finished', 'scan_id': scan_id, 'final_status': scan['status']})
                    break
                    
                # Wait before checking again
                await asyncio.sleep(1)
                
            except Exception as e:
                yield json.dumps({'error': f'Stream error: {str(e)}', 'scan_id': scan_id})
                break
    
    except asyncio.CancelledError:
        # Client disconnected
        yield json.dumps({'event': 'disconnected', 'scan_id': scan_id})
    except Exception as e:
        yield json.dumps({'error': f'Connection error: {str(e)}', 'scan_id': scan_id})

async def connect_to_scanner_service(scanner_url: str, scan_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Connect to external scanner service via SSE and yield progress updates.
    This would connect to the actual xployt-L2 or other scanner services.
    """
    async with httpx.AsyncClient() as client:
        try:
            # For now, simulate connection to scanner service
            # In real implementation, this would connect to actual scanner SSE endpoint
            async with client.stream("POST", scanner_url, json=scan_data) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])  # Remove "data: " prefix
                                yield data
                            except json.JSONDecodeError:
                                continue
                else:
                    yield {"error": f"Scanner service returned status {response.status_code}"}
        except Exception as e:
            yield {"error": f"Failed to connect to scanner service: {str(e)}"}

async def run_scan_with_sse(
    db: AsyncIOMotorDatabase,
    scan_id: str,
    repository_name: str,
    scanner_name: str,
    configurations: Dict[str, Any]
):
    """
    Enhanced scan function that connects to actual scanner services via SSE.
    This replaces the mock implementation with real service connections.
    """
    print(f"Starting SSE-enabled scan {scan_id} for repo '{repository_name}' with scanner '{scanner_name}'.")

    try:
        # 1. Initial setup
        await update_scan_status(db, scan_id, "connecting", 5, "Connecting to scanner service...")
        
        scanner_url = SCANNER_HOSTS.get(scanner_name, "http://default-scanner:8000/scan")
        scan_data = {
            "scan_id": scan_id,
            "repository_name": repository_name,
            "configurations": configurations
        }
        
        # 2. Connect to scanner service and process SSE updates
        async for update in connect_to_scanner_service(scanner_url, scan_data):
            if "error" in update:
                await update_scan_status(db, scan_id, "failed", 100, update["error"])
                return
            
            # Process scanner service updates
            status = update.get("status", "scanning")
            progress = update.get("progress_percent", 0)
            message = update.get("message", "Processing...")
            
            await update_scan_status(db, scan_id, status, progress, message)
            
            # Handle vulnerabilities if provided by scanner
            if "vulnerabilities" in update:
                await store_vulnerabilities(db, scan_id, update["vulnerabilities"])
            
            # Break if scan is complete
            if status in ["completed", "failed"]:
                break
                
    except Exception as e:
        error_message = f"SSE Scan failed: {str(e)}"
        print(error_message)
        await update_scan_status(db, scan_id, "failed", 100, error_message)

async def store_vulnerabilities(db: AsyncIOMotorDatabase, scan_id: str, vulnerabilities: List[Dict[str, Any]]):
    """Store vulnerabilities from scanner service in database."""
    for vuln_data in vulnerabilities:
        vuln_create = VulnerabilityCreate(scan_id=scan_id, **vuln_data)
        await db["vulnerabilities"].insert_one(vuln_create.model_dump())

async def run_scan(
    db: AsyncIOMotorDatabase,
    scan_id: str,
    repository_name: str,
    scanner_name: str,
    configurations: Dict[str, Any]
):
    """
    Simulates a full scanning process, providing mock progress updates.
    This function runs as a background task.
    """
    print(f"Starting scan {scan_id} for repo '{repository_name}' with scanner '{scanner_name}'.")

    try:
        # 1. Simulate cloning the repository
        await update_scan_status(db, scan_id, "cloning", 10, "Cloning repository...")
        await asyncio.sleep(3)

        # 2. Simulate the main scanning process
        await update_scan_status(db, scan_id, "scanning", 20, f"Running {scanner_name}...")

        scanner_url = SCANNER_HOSTS.get(scanner_name, "http://default-scanner:8000/scan")
        print(f"[{time.time():.2f}] SCAN INFO (ID: {scan_id}): Would call scanner at {scanner_url}")

        # Simulate scanning with multiple progress updates
        total_scan_duration = 24
        steps = 4
        for i in range(steps):
            await asyncio.sleep(total_scan_duration / steps)
            progress = 20 + int(70 * ((i + 1) / steps))
            await update_scan_status(db, scan_id, "scanning", progress, f"Analyzing part {i+1} of {steps}...")

        # 3. Create mock vulnerabilities
        await update_scan_status(db, scan_id, "saving", 95, "Finalizing and saving results...")
        vulnerabilities = await create_mock_vulnerabilities(db, scan_id, scanner_name)
        await asyncio.sleep(3)

        # 4. Finalize
        await update_scan_status(db, scan_id, "completed", 100, "Scan complete.")
        print(f"Scan {scan_id} finished successfully with {len(vulnerabilities)} vulnerabilities found.")

    except Exception as e:
        error_message = f"Scan failed due to an unexpected error: {e}"
        print(error_message)
        await update_scan_status(db, scan_id, "failed", 100, error_message) 