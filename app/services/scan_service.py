import asyncio
import time
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime

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
        "progress_text": progress_text
    }
    
    if status == "completed":
        update_data["finished_at"] = datetime.utcnow()
    
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