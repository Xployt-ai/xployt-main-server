# SSE (Server-Sent Events) Integration

## Overview

The Xployt main server now supports real-time scan progress streaming via Server-Sent Events (SSE). This allows frontend applications to receive live updates during scan execution instead of polling for status updates.

## New Endpoints

### SSE Streaming Endpoint

```
GET /api/v1/scans/{scan_id}/stream
```

**Description**: Stream real-time scan progress updates via SSE.

**Authentication**: Required (Bearer token)

**Response Format**: Server-Sent Events stream with JSON data

**Example SSE Message**:
```
data: {"scan_id": "123", "status": "scanning", "progress_percent": 45, "progress_text": "Analyzing code...", "timestamp": "2025-08-19T01:43:09.866666+00:00"}

data: {"scan_id": "123", "status": "completed", "progress_percent": 100, "progress_text": "Scan complete.", "timestamp": "2025-08-19T01:45:12.123456+00:00"}
```

### Enhanced Start Scan Endpoint

```
POST /api/v1/scans/?use_sse=true
```

**New Parameter**: `use_sse` (boolean, optional) - Enable SSE-based scanner service integration

## Frontend Integration

### JavaScript Example

```javascript
// Start a scan with SSE enabled
const response = await fetch('/api/v1/scans/?use_sse=true', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN',
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        repository_name: 'example-repo',
        scanner_name: 'secret_scanner',
        configurations: {}
    })
});

const result = await response.json();
const scanId = result.data.scan_id;

// Create SSE connection for real-time updates
const eventSource = new EventSource(`/api/v1/scans/${scanId}/stream`, {
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
    }
});

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Scan progress:', data);
    
    // Update UI with progress
    updateProgressBar(data.progress_percent);
    updateStatusText(data.progress_text);
    
    // Close connection when scan is complete
    if (data.status === 'completed' || data.status === 'failed') {
        eventSource.close();
    }
};

eventSource.onerror = function(event) {
    console.error('SSE error:', event);
    eventSource.close();
};
```

### React Hook Example

```jsx
import { useState, useEffect } from 'react';

function useScanProgress(scanId, token) {
    const [progress, setProgress] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!scanId || !token) return;

        const eventSource = new EventSource(
            `/api/v1/scans/${scanId}/stream`,
            {
                headers: { 'Authorization': `Bearer ${token}` }
            }
        );

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setProgress(data);
            
            if (data.status === 'completed' || data.status === 'failed') {
                eventSource.close();
            }
        };

        eventSource.onerror = (event) => {
            setError('Connection error');
            eventSource.close();
        };

        return () => {
            eventSource.close();
        };
    }, [scanId, token]);

    return { progress, error };
}
```

## Backend Architecture

### Scanner Service Integration

The system supports two modes:

1. **Mock Mode** (`use_sse=false`): Original mock scanning for development
2. **SSE Mode** (`use_sse=true`): Connects to real scanner services via SSE

### Scanner Service Protocol

Scanner services should expose SSE endpoints that stream progress updates:

```
POST /scan
Content-Type: application/json

{
    "scan_id": "string",
    "repository_name": "string", 
    "configurations": {}
}
```

**Response**: SSE stream with progress updates

**Expected SSE Format**:
```
data: {"status": "scanning", "progress_percent": 30, "message": "Analyzing files..."}

data: {"status": "completed", "progress_percent": 100, "vulnerabilities": [...]}
```

### Configuration

Scanner service URLs are configured in `SCANNER_HOSTS`:

```python
SCANNER_HOSTS = {
    "secret_scanner": "http://secret-scanner-service:8000/scan",
    "sast_scanner": "http://sast-scanner-service:8000/scan", 
    "llm_scanner": "http://llm-scanner-service:8000/scan",
    "dast_scanner": "http://dast-scanner-service:8000/scan",
}
```

## Error Handling

- SSE connections automatically close on scan completion/failure
- Network errors are propagated to the frontend via error events
- Fallback to polling-based status endpoint if SSE fails

## Backward Compatibility

The existing polling-based endpoints remain fully functional:
- `GET /api/v1/scans/{scan_id}` - Get current scan status
- `GET /api/v1/scans/{scan_id}/results` - Get scan results after completion