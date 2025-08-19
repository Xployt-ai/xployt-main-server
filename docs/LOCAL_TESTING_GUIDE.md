# Local Testing Guide for SSE Streaming

This guide explains how to test the SSE (Server-Sent Events) streaming functionality locally.

## Quick Start (Minimal Setup)

### 1. Install Dependencies and Start Server

```bash
# Clone and navigate to the repository
cd xployt-main-server

# Install Python dependencies
pip install -r requirements.txt

# Create basic environment file (MongoDB optional for SSE testing)
cp .env.sample .env

# Start the server
python run.py
```

The server will start on `http://localhost:8000`

### 2. Access Interactive Test Page

Open your browser and navigate to:
```
http://localhost:8000/docs/sse_test.html
```

This page provides:
- **Mock SSE Test**: Simulates the SSE functionality without requiring authentication
- **Visual Progress Bar**: Shows real-time progress updates
- **Connection Log**: Displays SSE message format and data flow
- **Start/Stop Controls**: Test connection management

### 3. Test API Documentation

Visit the interactive API documentation:
```
http://localhost:8000/docs
```

You can explore the SSE endpoints:
- `POST /api/v1/scans/?use_sse=true` - Start scan with SSE enabled
- `GET /api/v1/scans/{scan_id}/stream` - SSE streaming endpoint

## Complete Setup (With Authentication)

For full functionality testing including real API calls:

### 1. Database Setup (Optional but Recommended)

```bash
# Install MongoDB locally or use Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest

# Update .env file
MONGODB_URL=mongodb://localhost:27017
MONGODB_NAME=xploitai
```

### 2. GitHub OAuth Setup (For Authentication)

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Create a new OAuth App:
   - **Application name**: Xploit.ai Local
   - **Homepage URL**: `http://localhost:8000`
   - **Authorization callback URL**: `http://localhost:8000/api/v1/auth/github/callback`

3. Update `.env` file:
```env
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
SECRET_KEY=your-super-secret-key-here
```

### 3. Get Authentication Token

```bash
# Start the server
python run.py

# Open browser to authenticate
open http://localhost:8000/docs

# Use the GitHub OAuth flow to get a token
# Copy the bearer token from the response
```

## Testing Methods

### Method 1: Interactive HTML Test Page

**Best for**: Visual demonstration and basic functionality testing

```bash
# Open in browser
http://localhost:8000/docs/sse_test.html
```

**What it tests**:
- SSE message format
- Progress updates simulation
- Connection management
- Error handling

### Method 2: JavaScript Console Testing

**Best for**: Integration testing and debugging

```javascript
// Open browser developer console at http://localhost:8000

// Mock test without authentication
function testMockSSE() {
    // This simulates the SSE data format
    const mockData = {
        scan_id: 'test-123',
        status: 'scanning',
        progress_percent: 50,
        progress_text: 'Testing SSE...',
        timestamp: new Date().toISOString()
    };
    
    console.log('Mock SSE data:', mockData);
    return mockData;
}

testMockSSE();
```

### Method 3: cURL Testing (With Auth)

**Best for**: API endpoint testing

```bash
# 1. Start a scan with SSE enabled
curl -X POST "http://localhost:8000/api/v1/scans/?use_sse=true" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_name": "test-repo",
    "scanner_name": "secret_scanner",
    "configurations": {}
  }'

# Response: {"data": {"scan_id": "123abc", "sse_enabled": true}}

# 2. Connect to SSE stream
curl -N -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  "http://localhost:8000/api/v1/scans/123abc/stream"
```

### Method 4: Frontend JavaScript Testing

**Best for**: Real frontend integration

```javascript
// Example frontend integration test
async function testSSEIntegration() {
    try {
        // 1. Start scan with SSE
        const response = await fetch('/api/v1/scans/?use_sse=true', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer YOUR_TOKEN_HERE',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                repository_name: 'test-repo',
                scanner_name: 'secret_scanner',
                configurations: {}
            })
        });
        
        const result = await response.json();
        const scanId = result.data.scan_id;
        
        console.log('Scan started:', scanId);
        
        // 2. Connect to SSE stream
        const eventSource = new EventSource(`/api/v1/scans/${scanId}/stream`, {
            headers: {
                'Authorization': 'Bearer YOUR_TOKEN_HERE'
            }
        });
        
        eventSource.onopen = () => {
            console.log('SSE connection opened');
        };
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Progress update:', data);
            
            // Close when complete
            if (data.status === 'completed' || data.status === 'failed') {
                eventSource.close();
                console.log('Scan finished:', data.status);
            }
        };
        
        eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            eventSource.close();
        };
        
    } catch (error) {
        console.error('Test failed:', error);
    }
}

// Run the test
testSSEIntegration();
```

## Expected SSE Message Format

During testing, you should see messages in this format:

```json
{
  "scan_id": "123abc",
  "status": "scanning",
  "progress_percent": 45,
  "progress_text": "Analyzing code...",
  "timestamp": "2025-01-20T10:30:00Z"
}
```

**Status Values**:
- `pending` - Scan initialized
- `cloning` - Repository being cloned
- `scanning` - Scan in progress
- `saving` - Finalizing results
- `completed` - Scan finished successfully
- `failed` - Scan encountered an error

## Testing Scenarios

### Scenario 1: Basic Mock Scan
1. Open `http://localhost:8000/docs/sse_test.html`
2. Click "Start Mock Scan"
3. Watch progress bar and log messages
4. Verify connection closes on completion

### Scenario 2: API Integration Test
1. Authenticate via GitHub OAuth
2. Start scan with `use_sse=true`
3. Connect to SSE stream endpoint
4. Monitor real-time progress updates

### Scenario 3: Error Handling
1. Start SSE connection to non-existent scan
2. Verify 404 error response
3. Test connection timeout behavior
4. Test network disconnection handling

## Troubleshooting

### Common Issues

**Server won't start**:
```bash
# Check if port 8000 is available
lsof -i :8000

# Try different port
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**SSE test page not loading**:
- Ensure server is running on `http://localhost:8000`
- Check browser console for errors
- Try accessing `http://localhost:8000/docs` first

**Authentication errors**:
- Verify GitHub OAuth app configuration
- Check `.env` file has correct client ID/secret
- Ensure callback URL matches exactly

**SSE connection fails**:
- Check browser developer tools Network tab
- Verify authorization token is valid
- Check server logs for error messages

### Debug Logs

Enable debug logging:
```python
# In run.py, add:
uvicorn.run(
    "app.main:app",
    host="0.0.0.0",
    port=8000,
    reload=True,
    log_level="debug"  # Changed from "info"
)
```

## Browser Compatibility

SSE is supported in:
- ✅ Chrome 6+
- ✅ Firefox 6+
- ✅ Safari 5+
- ✅ Edge 79+
- ❌ Internet Explorer

For IE support, consider using EventSource polyfills.

## Next Steps

After local testing works:
1. Test with real scanner services
2. Configure `SCANNER_HOSTS` for your environment
3. Set up production SSE infrastructure
4. Monitor connection performance and scaling