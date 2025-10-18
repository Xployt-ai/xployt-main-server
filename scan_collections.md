### Overview
Scan collections let the frontend start multiple scanners (by SCANNER_HOSTS keys) against one repository, track aggregate progress, stream collection progress, list history, and fetch combined results.

### Auth
- Requires Bearer token (same as other v1 endpoints).
- All responses are wrapped in ApiResponse unless noted (SSE).

### Data types
- ScanCollectionCreate
  - repository_name: string
  - scanners: string[] (keys from SCANNER_HOSTS, e.g., "static_scanner", "llm_scanner", "dast_scanner")
  - configurations: object (optional, shared across scanners)
- CollectionSummary
  - id: string
  - repository_name: string
  - scanners: string[]
  - scan_ids: string[]
  - status: "pending" | "scanning" | "completed" | "failed"
  - progress_percent: number
  - created_at: ISO datetime
  - finished_at: ISO datetime | null
- ScanMiniStatus
  - scan_id: string
  - status: "pending" | "scanning" | "completed" | "failed"
  - progress_percent: number
  - progress_text: string
  - scanner_name: string
- Vulnerability
  - id: string
  - scan_id: string
  - file_path: string
  - line: number
  - description: string
  - vulnerability: string
  - severity: string
  - confidence_level: string

### 1) Start a collection
- Method/Path: POST /api/v1/scan-collections/
- Description: Creates a collection, starts all child scans concurrently, returns collection_id and scan_ids.

Request body (ScanCollectionCreate):
```json
{
  "repository_name": "org/repo",
  "scanners": ["static_scanner", "llm_scanner"],
  "configurations": { "mock": false }
}
```

Response 200 (ApiResponse<{collection_id, scan_ids}>):
```json
{
  "success": true,
  "data": {
    "collection_id": "664e8c4f7f0a8b0012abcd89",
    "scan_ids": ["664e8c4f7f0a8b0012000001", "664e8c4f7f0a8b0012000002"]
  },
  "message": "Scan collection started",
  "timestamp": "2025-10-18T10:00:00Z"
}
```

### 2) Get collection status
- Method/Path: GET /api/v1/scan-collections/{collection_id}/status
- Description: Returns aggregate collection status/progress and per-scan mini statuses.

Response 200 (ApiResponse<{collection, scans[]}>):
```json
{
  "success": true,
  "data": {
    "collection": { "status": "scanning", "progress_percent": 42 },
    "scans": [
      {
        "scan_id": "664e8c4f7f0a8b0012000001",
        "status": "scanning",
        "progress_percent": 60,
        "progress_text": "Analyzing",
        "scanner_name": "static_scanner"
      },
      {
        "scan_id": "664e8c4f7f0a8b0012000002",
        "status": "scanning",
        "progress_percent": 24,
        "progress_text": "Indexing files",
        "scanner_name": "llm_scanner"
      }
    ]
  },
  "timestamp": "2025-10-18T10:00:05Z"
}
```

Notes:
- Aggregate status: failed if any failed; completed if all completed; else scanning. Progress is the average of child `progress_percent`.

### 3) Stream collection progress (SSE)
- Method/Path: GET /api/v1/scan-collections/{collection_id}/stream
- Description: Server-Sent Events stream emitting collection aggregate progress updates; ends on completed/failed.
- Headers: Accept: text/event-stream

Event data (each line is a JSON string):
```json
{"event":"progress","collection":{"status":"scanning","progress_percent":42}}
```

Notes:
- Emits only on change; polls ~1s.
- Stream ends when status is "completed" or "failed".

### 4) List collections (history)
- Method/Path: GET /api/v1/scan-collections/
- Description: Lists current user’s collections, newest first. Optional query: limit (default 50).

Response 200 (ApiResponse<CollectionSummary[]>):
```json
{
  "success": true,
  "data": [
    {
      "id": "664e8c4f7f0a8b0012abcd89",
      "repository_name": "org/repo",
      "scanners": ["static_scanner", "llm_scanner"],
      "scan_ids": ["664e8c4f7f0a8b0012000001", "664e8c4f7f0a8b0012000002"],
      "status": "completed",
      "progress_percent": 100,
      "created_at": "2025-10-18T09:59:30Z",
      "finished_at": "2025-10-18T10:01:12Z"
    }
  ],
  "message": "Collections retrieved successfully",
  "timestamp": "2025-10-18T10:02:00Z"
}
```

### 5) Get collection results
- Method/Path: GET /api/v1/scan-collections/{collection_id}/results
- Description: Combined vulnerabilities for all child scan_ids.

Response 200 (ApiResponse<{vulnerabilities: Vulnerability[]}>):
```json
{
  "success": true,
  "data": {
    "vulnerabilities": [
      {
        "id": "665000000000000000000001",
        "scan_id": "664e8c4f7f0a8b0012000001",
        "file_path": "config.py",
        "line": 15,
        "description": "API key found in source code",
        "vulnerability": "secret",
        "severity": "high",
        "confidence_level": "high"
      }
    ]
  },
  "timestamp": "2025-10-18T10:03:00Z"
}
```

### Errors
- 400: invalid input (e.g., empty scanners list).
- 404: collection not found or not owned by user.
- Error envelope (ApiError):
```json
{"success": false, "error": "Collection not found", "detail": null, "timestamp": "2025-10-18T10:00:00Z"}
```