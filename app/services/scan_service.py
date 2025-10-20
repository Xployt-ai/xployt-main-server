import asyncio
import time
import json
from typing import Dict, Any, List, AsyncGenerator, Optional
from app.models.user import UserInDB
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
import httpx
from decimal import Decimal, ROUND_HALF_UP

from app.services.credit_service import CreditService
from app.services.git_service import git_service

from app.models.scan import ScanCreate, VulnerabilityCreate

SCANNER_HOSTS = {
    "static_scanner": "http://localhost:8001",
    "llm_scanner": "http://llm-scanner-service:8000",
    "dast_scanner": "http://dast-scanner-service:8000",
}

# Per-LOC credit rates per scanner
CREDIT_RATES_PER_LOC: Dict[str, float] = {
    "static_scanner": 0.001,
    "llm_scanner": 0.005,
    "dast_scanner": 0.002,
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
    configurations: Dict[str, Any],
    user_id: Optional[str] = None,
    charged_credits: Optional[float] = None,
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
            # Refund if billing was applied
            if user_id and charged_credits is not None:
                try:
                    await CreditService(db).refund_credits(
                        user_id, Decimal(str(charged_credits)), "Scan failed refund"
                    )
                except Exception:
                    pass
            raise ValueError(f"Scanner service not found: {scanner_name}")

        scan_url = f"{base_url.rstrip('/')}/scan"

        async with httpx.AsyncClient(timeout=None) as client:
            try:
                print("scanning url: ", scan_url)
                async with client.stream("POST", scan_url, json={"path": repository_name.replace("/", "_")}) as response:
                    if response.status_code != 200:
                        error_msg = f"Scanner service returned status {response.status_code}"
                        await update_scan_status(db, scan_id, "failed", 100, error_msg)
                        if user_id and charged_credits is not None:
                            try:
                                await CreditService(db).refund_credits(
                                    user_id, Decimal(str(charged_credits)), "Scan failed refund"
                                )
                            except Exception:
                                pass
                        return

                    await update_scan_status(db, scan_id, "scanning", 1, "Scan started")

                    async for update in stream_scanner_progress(response):
                        print("update from scanner: ", update)

                        if "error" in update:
                            await update_scan_status(db, scan_id, "failed", 100, update["error"])
                            if user_id and charged_credits is not None:
                                try:
                                    await CreditService(db).refund_credits(
                                        user_id, Decimal(str(charged_credits)), "Scan failed refund"
                                    )
                                except Exception:
                                    pass
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
                if user_id and charged_credits is not None:
                    try:
                        await CreditService(db).refund_credits(
                            user_id, Decimal(str(charged_credits)), "Scan failed refund"
                        )
                    except Exception:
                        pass
                return
                
    except Exception as e:
        error_message = f"SSE Scan failed: {str(e)}"
        print(error_message)
        await update_scan_status(db, scan_id, "failed", 100, error_message)
        if user_id and charged_credits is not None:
            try:
                await CreditService(db).refund_credits(
                    user_id, Decimal(str(charged_credits)), "Scan failed refund"
                )
            except Exception:
                pass

async def store_vulnerabilities(db: AsyncIOMotorDatabase, scan_id: str, vulnerabilities: List[Dict[str, Any]]):
    """Store vulnerabilities from scanner service in database using the new schema."""
    for vuln_data in vulnerabilities:
        vuln_create = VulnerabilityCreate(
            scan_id=scan_id,
            file_path=vuln_data.get("file_path", ""),
            line=int(vuln_data.get("line", 0) or 0),
            description=vuln_data.get("description", ""),
            vulnerability=vuln_data.get("vulnerability", "unknown"),
            severity=str(vuln_data.get("severity", "unknown")),
            confidence_level=str(vuln_data.get("confidence_level", "unknown")),
        )
        await db["vulnerabilities"].insert_one(vuln_create.model_dump())

async def stream_vulnerabilities_for_scan(
    db: AsyncIOMotorDatabase,
    scan_id: str,
) -> AsyncGenerator[str, None]:
    """
    Fetch single-response from external scanner for given scan, store vulnerabilities,
    and stream each vulnerability as SSE with id = progress.
    """
    scan = await db["scans"].find_one({"_id": ObjectId(scan_id)})
    if not scan:
        yield f"id: 0\ndata: {json.dumps({'error': 'Scan not found'})}\n\n"
        return

    repository_name = scan.get("repository_name")
    scanner_name = scan.get("scanner_name")
    configurations = scan.get("configurations") or {}

    # Get payload from external scanner (mock or real)
    if configurations.get("mock"):
        payload = {
            "progress": 100,
            "status": "complete",
            "vulnerabilities": [
                {
                    "file_path": "config.py",
                    "line": 15,
                    "description": "API key found in source code",
                    "vulnerability": "secret",
                    "severity": "high",
                    "confidence_level": "high",
                }
            ],
        }
    else:
        base_url = SCANNER_HOSTS.get(scanner_name)
        if not base_url:
            yield f"id: 0\ndata: {json.dumps({'error': f'Scanner not found: {scanner_name}'})}\n\n"
            return
        scan_url = f"{base_url.rstrip('/')}/scan"
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(scan_url, json={"path": repository_name})
                if response.status_code != 200:
                    yield f"id: 0\ndata: {json.dumps({'error': f'status {response.status_code}'})}\n\n"
                    return
                payload = response.json()
        except Exception as e:
            yield f"id: 0\ndata: {json.dumps({'error': str(e)})}\n\n"
            return

    progress = int(payload.get("progress", 0) or 0)
    status = payload.get("status", "")
    vulnerabilities = payload.get("vulnerabilities", []) or []

    # Save scan summary and vulnerabilities with minimal transformation
    await db["scans"].update_one(
        {"_id": ObjectId(scan_id)},
        {"$set": {"status": status, "progress_percent": progress}}
    )
    if vulnerabilities:
        await store_vulnerabilities(db, scan_id, vulnerabilities)

    # Stream each vulnerability as SSE with id = progress
    for vuln in vulnerabilities:
        yield f"id: {progress}\ndata: {json.dumps(vuln)}\n\n"

    # Emit a final id-only event to indicate completion
    yield f"id: {progress}\n\n"

async def run_scan_single_response(
    db: AsyncIOMotorDatabase,
    repository_name: str,
    scanner_name: str,
    configurations: Dict[str, Any],
    user_id: str,
) -> Dict[str, Any]:
    """
    Run a scan where the scanner returns a single JSON response containing
    progress, status, and vulnerabilities. Persist scan and vulnerabilities
    to the database and return the payload.
    """
    # Ensure repository exists locally
    repo_path = git_service.get_repo_path(repository_name)
    if not repo_path.exists():
        current_user = await db["users"].find_one({"_id": ObjectId(user_id)})
        if not current_user:
            raise ValueError("User not found")
        current_user = UserInDB(**current_user)
        await git_service.clone_github_repository(repository_name, current_user)

    # Calculate cost based on LOC and per-scanner rate
    try:
        loc = git_service.count_repo_loc(repository_name)
    except Exception as e:
        raise ValueError(f"Failed to count repository LOC: {e}")

    rate = float(CREDIT_RATES_PER_LOC.get(scanner_name, 0.001))
    raw_cost = Decimal(loc) * Decimal(str(rate))
    cost = raw_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Attempt to debit credits prior to starting the scan
    credit_service = CreditService(db)
    try:
        await credit_service.debit_credits(
            user_id=user_id,
            amount=cost,
            description=f"Scan {scanner_name} on {repository_name}",
            transaction_type="scan_debit",
        )
    except ValueError as e:
        # Propagate to endpoint to map as 402
        raise e

    scan_create = ScanCreate(
        repository_name=repository_name,
        scanner_name=scanner_name,
        configurations={**configurations, "charged_credits": float(cost)},
        user_id=user_id,
    )

    result = await db["scans"].insert_one(scan_create.model_dump())
    scan_id = str(result.inserted_id)

    # Initial status
    await update_scan_status(db, scan_id, "connecting", 5, "Connecting to scanner service...")

    # Mock flow for testing
    if configurations.get("mock"):
        payload = {
            "progress": 100,
            "status": "complete",
            "vulnerabilities": [
                {
                    "file_path": "config.py",
                    "line": 15,
                    "description": "API key found in source code",
                    "vulnerability": "secret",
                    "severity": "high",
                    "confidence_level": "high",
                }
            ],
        }
        await update_scan_status(db, scan_id, "completed", 100, "Scan completed")
        await store_vulnerabilities(db, scan_id, payload["vulnerabilities"])
        return {"scan_id": scan_id, **payload}

    base_url = SCANNER_HOSTS.get(scanner_name)
    if not base_url:
        await update_scan_status(db, scan_id, "failed", 100, f"Scanner service not found: {scanner_name}")
        # Refund if previously charged
        try:
            await credit_service.refund_credits(
                user_id=user_id,
                amount=cost,
                description="Scan failed refund",
                transaction_type="scan_refund",
            )
        except Exception:
            pass
        return {"scan_id": scan_id, "progress": 0, "status": "failed", "vulnerabilities": []}


# --- Scan Collections helpers ---

async def create_scans_for_collection(
    db: AsyncIOMotorDatabase,
    user_id: str,
    repository_name: str,
    scanners: List[str],
    configurations: Dict[str, Any],
) -> List[str]:
    """Create individual scans for each scanner and start them concurrently."""
    scan_ids: List[str] = []

    # Calculate LOC once
    repo_path = git_service.get_repo_path(repository_name)
    if not repo_path.exists():
        raise ValueError("Repository not found locally. Please clone first.")
    loc = git_service.count_repo_loc(repository_name)

    credit_service = CreditService(db)

    for scanner_name in scanners:
        scan_create = ScanCreate(
            repository_name=repository_name,
            scanner_name=scanner_name,
            configurations=configurations or {},
            user_id=user_id,
        )
        # Compute cost per scanner
        rate = float(CREDIT_RATES_PER_LOC.get(scanner_name, 0.001))
        cost = (Decimal(loc) * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Try to debit credits for this child scan
        charged = False
        try:
            await credit_service.debit_credits(
                user_id=user_id,
                amount=cost,
                description=f"Scan {scanner_name} on {repository_name}",
                transaction_type="scan_debit",
            )
            charged = True
        except ValueError:
            # Insufficient credits; create failed scan record
            doc = {
                **scan_create.model_dump(),
                "status": "failed",
                "progress_percent": 0,
                "progress_text": "Insufficient credits",
                "created_at": datetime.utcnow(),
            }
            result = await db["scans"].insert_one(doc)
            scan_id = str(result.inserted_id)
            scan_ids.append(scan_id)
            continue

        # Create scan with charged_credits marker
        doc = {
            **scan_create.model_dump(),
            "configurations": {**(configurations or {}), "charged_credits": float(cost)},
            "created_at": datetime.utcnow(),
        }
        result = await db["scans"].insert_one(doc)
        scan_id = str(result.inserted_id)
        scan_ids.append(scan_id)

        # Kick off background task without awaiting
        asyncio.create_task(
            run_scan_with_sse(
                db=db,
                scan_id=scan_id,
                repository_name=repository_name,
                scanner_name=scanner_name,
                configurations=configurations or {},
                user_id=user_id,
                charged_credits=float(cost) if charged else None,
            )
        )

    return scan_ids


async def compute_collection_status(
    db: AsyncIOMotorDatabase,
    scan_ids: List[str],
) -> tuple[str, int]:
    """Compute aggregate collection status and average progress."""
    if not scan_ids:
        return ("pending", 0)

    cursor = db["scans"].find({"_id": {"$in": [ObjectId(sid) for sid in scan_ids]}})
    statuses: List[str] = []
    progresses: List[int] = []
    async for scan in cursor:
        statuses.append(str(scan.get("status", "pending")))
        try:
            progresses.append(int(scan.get("progress_percent", 0) or 0))
        except Exception:
            progresses.append(0)

    if not statuses:
        return ("pending", 0)

    if any(s == "failed" for s in statuses):
        agg_status = "failed"
    elif all(s == "completed" for s in statuses):
        agg_status = "completed"
    else:
        agg_status = "scanning"

    avg_progress = int(sum(progresses) / max(len(progresses), 1)) if progresses else 0
    return (agg_status, avg_progress)


async def list_vulnerabilities_for_scan_ids(
    db: AsyncIOMotorDatabase,
    scan_ids: List[str],
) -> List[Dict[str, Any]]:
    """Return all vulnerabilities for given scan ids."""
    if not scan_ids:
        return []
    cursor = db["vulnerabilities"].find({"scan_id": {"$in": scan_ids}})
    vulns: List[Dict[str, Any]] = []
    async for v in cursor:
        v = dict(v)
        v["id"] = str(v.get("_id"))
        # scan_id is already stored as string
        vulns.append(v)
    return vulns

    scan_url = f"{base_url.rstrip('/')}/scan"
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(scan_url, json={"path": repository_name})
            if response.status_code != 200:
                error_msg = f"Scanner service returned status {response.status_code}"
                await update_scan_status(db, scan_id, "failed", 100, error_msg)
                try:
                    await credit_service.refund_credits(
                        user_id=user_id,
                        amount=cost,
                        description="Scan failed refund",
                        transaction_type="scan_refund",
                    )
                except Exception:
                    pass
                return {"scan_id": scan_id, "progress": 0, "status": "failed", "vulnerabilities": []}

            data = response.json()
            progress = int(data.get("progress", 0) or 0)
            status = str(data.get("status", "scanning"))
            vulns = data.get("vulnerabilities", []) or []

            # Map external status to our internal status values
            internal_status = "completed" if status == "complete" or progress >= 100 else "scanning"
            message = "Scan completed" if internal_status == "completed" else "Processing..."
            await update_scan_status(db, scan_id, internal_status, progress, message)

            if vulns:
                await store_vulnerabilities(db, scan_id, vulns)

            payload = {
                "progress": progress,
                "status": status,
                "vulnerabilities": vulns,
            }
            return {"scan_id": scan_id, **payload}
    except Exception as e:
        error_msg = f"Failed to connect to scanner: {str(e)}"
        await update_scan_status(db, scan_id, "failed", 100, error_msg)
        try:
            await credit_service.refund_credits(
                user_id=user_id,
                amount=cost,
                description="Scan failed refund",
                transaction_type="scan_refund",
            )
        except Exception:
            pass
        return {"scan_id": scan_id, "progress": 0, "status": "failed", "vulnerabilities": []}
