# Scanner Service Protocol Specification

## Overview

This document defines the interface that external scanner services (e.g., xployt-L2, secret scanners, SAST scanners) must implement to integrate with the Xployt main server's SSE streaming functionality.

The main server connects to scanner services via Server-Sent Events (SSE) to receive real-time progress updates, which are then streamed to frontend clients.

## Architecture

```
Frontend Client    Main Server    Scanner Service
      |                |                |
      |---SSE stream--->|                |
      |                |---HTTP POST---->|
      |                |<--SSE stream----|
      |<--SSE events----|                |
```

## Scanner Service Interface Requirements

### 1. Scan Endpoint

Scanner services **MUST** expose a POST endpoint that accepts scan requests and responds with SSE streams:

```
POST /scan
Content-Type: application/json
Accept: text/event-stream
```

### 2. Request Format

The main server will send scan requests with the following JSON structure:

```json
{
  "scan_id": "507f1f77bcf86cd799439011",
  "repository_name": "example-org/example-repo", 
  "configurations": {
    "depth": "full",
    "file_types": ["js", "ts", "py"],
    "exclude_paths": ["node_modules", ".git"],
    "custom_rules": true
  }
}
```

**Required Fields:**
- `scan_id` (string): Unique identifier for the scan
- `repository_name` (string): Repository to scan in "owner/repo" format
- `configurations` (object): Scanner-specific configuration options

### 3. Response Format

Scanner services **MUST** respond with an SSE stream containing progress updates:

#### Response Headers
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
Access-Control-Allow-Origin: *
```

#### SSE Message Format

Each SSE message **MUST** follow this JSON structure:

```
data: {"status": "scanning", "progress_percent": 45, "message": "Analyzing JavaScript files...", "timestamp": "2025-01-20T10:30:00Z"}

```

**Message Fields:**
- `status` (string, required): Current scan status
- `progress_percent` (integer, required): Progress percentage (0-100)
- `message` (string, required): Human-readable progress description
- `timestamp` (string, required): ISO 8601 timestamp
- `vulnerabilities` (array, optional): Vulnerability objects (for final results)
- `error` (string, optional): Error message (for failure states)

### 4. Status Values

Scanner services **MUST** use these standardized status values:

| Status | Description | Progress Range |
|--------|-------------|----------------|
| `initializing` | Starting up the scanner | 0-5% |
| `cloning` | Cloning/downloading repository | 5-15% |
| `analyzing` | Analyzing code structure | 15-25% |
| `scanning` | Running security scans | 25-90% |
| `processing` | Processing results | 90-95% |
| `saving` | Saving results to database | 95-99% |
| `completed` | Scan finished successfully | 100% |
| `failed` | Scan failed with errors | 100% |

### 5. Complete Example Flow

#### Initial Request (Main Server → Scanner Service)
```bash
curl -X POST http://scanner-service:8000/scan \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "scan_id": "507f1f77bcf86cd799439011",
    "repository_name": "example-org/vulnerable-app",
    "configurations": {
      "scan_type": "secrets",
      "depth": "full"
    }
  }'
```

#### SSE Response Stream (Scanner Service → Main Server)
```
data: {"status": "initializing", "progress_percent": 0, "message": "Initializing secret scanner...", "timestamp": "2025-01-20T10:30:00Z"}

data: {"status": "cloning", "progress_percent": 10, "message": "Cloning repository...", "timestamp": "2025-01-20T10:30:05Z"}

data: {"status": "scanning", "progress_percent": 30, "message": "Scanning JavaScript files...", "timestamp": "2025-01-20T10:30:15Z"}

data: {"status": "scanning", "progress_percent": 60, "message": "Scanning configuration files...", "timestamp": "2025-01-20T10:30:25Z"}

data: {"status": "processing", "progress_percent": 90, "message": "Processing found secrets...", "timestamp": "2025-01-20T10:30:35Z"}

data: {"status": "completed", "progress_percent": 100, "message": "Scan completed successfully", "timestamp": "2025-01-20T10:30:40Z", "vulnerabilities": [{"type": "secret", "severity": "high", "description": "API key found in .env file", "location": {"file": ".env", "line": 5}}]}

```

## Implementation Guidelines

### 1. Error Handling

Scanner services **MUST** handle errors gracefully and report them via SSE:

```
data: {"status": "failed", "progress_percent": 100, "message": "Repository not found", "error": "HTTP 404: Repository 'example-org/non-existent' not found", "timestamp": "2025-01-20T10:30:45Z"}

```

### 2. Connection Management

- **Timeout**: Scanner services should complete scans within 1 hour
- **Keep-alive**: Send progress updates at least every 30 seconds
- **Cleanup**: Close SSE connection when scan completes or fails

### 3. Resource Management

Scanner services should:
- Limit concurrent scans per service instance
- Clean up temporary files after scan completion
- Implement proper logging for debugging

### 4. Vulnerability Format

When reporting vulnerabilities in the final message, use this format:

```json
{
  "vulnerabilities": [
    {
      "type": "secret|sast|dast|dependency",
      "severity": "critical|high|medium|low",
      "description": "Human-readable description",
      "location": {
        "file": "path/to/file.js",
        "line": 42,
        "column": 15
      },
      "metadata": {
        "cwe": "CWE-89",
        "pattern": "API_KEY=",
        "confidence": "high",
        "value_masked": "sk-***"
      }
    }
  ]
}
```

## Configuration

### Main Server Configuration

The main server defines scanner service URLs in `SCANNER_HOSTS`:

```python
SCANNER_HOSTS = {
    "secret_scanner": "http://secret-scanner-service:8000/scan",
    "sast_scanner": "http://sast-scanner-service:8000/scan", 
    "llm_scanner": "http://llm-scanner-service:8000/scan",
    "dast_scanner": "http://dast-scanner-service:8000/scan",
}
```

### Environment Variables

Scanner services should support these environment variables:

```bash
# Service configuration
SCANNER_PORT=8000
SCANNER_HOST=0.0.0.0
MAX_CONCURRENT_SCANS=5
SCAN_TIMEOUT=3600

# Integration
MAIN_SERVER_URL=http://main-server:8000
SERVICE_NAME=secret_scanner
```

## Sample Implementation

### Python FastAPI Example

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from datetime import datetime

app = FastAPI()

async def scan_progress_stream(scan_data):
    """Generate scan progress updates."""
    scan_id = scan_data["scan_id"]
    repository = scan_data["repository_name"]
    
    steps = [
        {"status": "initializing", "progress": 0, "message": "Starting scan..."},
        {"status": "cloning", "progress": 10, "message": f"Cloning {repository}..."},
        {"status": "scanning", "progress": 50, "message": "Running security analysis..."},
        {"status": "processing", "progress": 90, "message": "Processing results..."},
        {"status": "completed", "progress": 100, "message": "Scan completed"}
    ]
    
    for step in steps:
        message = {
            "status": step["status"],
            "progress_percent": step["progress"],
            "message": step["message"],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Add vulnerabilities to final message
        if step["status"] == "completed":
            message["vulnerabilities"] = [
                {
                    "type": "secret",
                    "severity": "high", 
                    "description": "API key found",
                    "location": {"file": ".env", "line": 5}
                }
            ]
        
        yield json.dumps(message)
        await asyncio.sleep(2)  # Simulate work

@app.post("/scan")
async def start_scan(scan_request: dict):
    """Start scan and return SSE stream."""
    return EventSourceResponse(
        scan_progress_stream(scan_request),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
```

### Node.js Express Example

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/scan', (req, res) => {
    const { scan_id, repository_name, configurations } = req.body;
    
    // Set SSE headers
    res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*'
    });
    
    let progress = 0;
    const interval = setInterval(() => {
        progress += 20;
        
        const message = {
            status: progress < 100 ? 'scanning' : 'completed',
            progress_percent: progress,
            message: `Processing... ${progress}%`,
            timestamp: new Date().toISOString()
        };
        
        res.write(`data: ${JSON.stringify(message)}\n\n`);
        
        if (progress >= 100) {
            clearInterval(interval);
            res.end();
        }
    }, 1000);
    
    // Handle client disconnect
    req.on('close', () => {
        clearInterval(interval);
    });
});

app.listen(8000, () => {
    console.log('Scanner service listening on port 8000');
});
```

## Testing Your Implementation

### 1. Test SSE Endpoint

```bash
# Test your scanner service SSE endpoint
curl -N -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/scan \
  -d '{"scan_id": "test-123", "repository_name": "test/repo", "configurations": {}}'
```

### 2. Integration with Main Server

1. Update `SCANNER_HOSTS` in main server configuration
2. Start your scanner service
3. Use the main server's test endpoints:
   ```bash
   POST /api/v1/scans/?use_sse=true
   GET /api/v1/scans/{scan_id}/stream
   ```

### 3. Validation Checklist

- [ ] Endpoint responds to POST `/scan` with SSE stream
- [ ] Messages follow required JSON format
- [ ] Progress updates are sent regularly (< 30s intervals)
- [ ] Status values match specification
- [ ] Final message includes vulnerabilities or error
- [ ] Connection closes after completion/failure
- [ ] Handles client disconnections gracefully

## Security Considerations

### 1. Authentication (Future)

While not currently implemented, future versions may require:
- Service-to-service authentication via API keys
- JWT tokens for request validation
- TLS encryption for all communications

### 2. Input Validation

Scanner services **MUST**:
- Validate all input parameters
- Sanitize repository names and paths
- Limit configuration values to safe ranges
- Prevent path traversal attacks

### 3. Resource Limits

- Implement timeouts for repository operations
- Limit memory and CPU usage per scan
- Prevent scanner from accessing unauthorized resources

## Troubleshooting

### Common Issues

1. **SSE Connection Drops**
   - Ensure regular progress updates (< 30s)
   - Check for proxy/load balancer timeout settings
   - Verify proper SSE headers

2. **Invalid JSON Format**
   - Validate JSON structure before sending
   - Ensure proper escaping of special characters
   - Use consistent timestamp formats

3. **Main Server Can't Connect**
   - Verify scanner service is accessible on configured URL
   - Check firewall and network connectivity
   - Ensure proper HTTP response codes

### Debug Mode

Enable detailed logging in your scanner service:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Log all SSE messages
def log_sse_message(message):
    logging.debug(f"SSE: {message}")
    return message
```

## Support

For questions about this specification or integration issues:

1. Check the [SSE Integration Guide](./SSE_INTEGRATION.md) for frontend examples
2. Review the [Local Testing Guide](./LOCAL_TESTING_GUIDE.md) for setup instructions
3. Examine the main server's `scan_service.py` for reference implementation
4. Test with the provided `test_sse.py` script

---

**Version**: 1.0  
**Last Updated**: January 2025  
**Compatibility**: Xployt Main Server v1.0+