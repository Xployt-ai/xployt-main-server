#!/usr/bin/env python3
"""
Simple SSE Testing Script

This script tests the SSE functionality locally without requiring full authentication setup.
It demonstrates the SSE message format and streaming capabilities.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import AsyncGenerator
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="SSE Test Server")

async def mock_scan_progress() -> AsyncGenerator[str, None]:
    """Generate mock scan progress events for testing SSE functionality."""
    
    scan_steps = [
        {"status": "pending", "progress_percent": 0, "progress_text": "Initializing scan..."},
        {"status": "cloning", "progress_percent": 10, "progress_text": "Cloning repository..."},
        {"status": "scanning", "progress_percent": 25, "progress_text": "Running secret scanner..."},
        {"status": "scanning", "progress_percent": 40, "progress_text": "Analyzing JavaScript files..."},
        {"status": "scanning", "progress_percent": 55, "progress_text": "Checking Node.js dependencies..."},
        {"status": "scanning", "progress_percent": 70, "progress_text": "Scanning React components..."},
        {"status": "scanning", "progress_percent": 85, "progress_text": "Analyzing MongoDB queries..."},
        {"status": "saving", "progress_percent": 95, "progress_text": "Finalizing results..."},
        {"status": "completed", "progress_percent": 100, "progress_text": "Scan completed successfully!"}
    ]
    
    for i, step in enumerate(scan_steps):
        # Create structured SSE message
        message_data = {
            "scan_id": "test-12345",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **step
        }
        
        # Format as SSE event
        yield f"data: {json.dumps(message_data)}\n\n"
        
        # Wait between progress updates (simulate real scan time)
        await asyncio.sleep(2.0)
        
        # Final message closes the connection
        if step["status"] == "completed":
            break

@app.get("/test-sse")
async def stream_test_progress():
    """SSE endpoint for testing scan progress streaming."""
    return EventSourceResponse(
        mock_scan_progress(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/")
async def get_test_page():
    """Serve the SSE test page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SSE Test - Xployt.ai</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 10px 0; }
        .progress-bar { width: 100%; height: 20px; background-color: #ddd; border-radius: 10px; margin: 10px 0; }
        .progress-fill { height: 100%; background-color: #4CAF50; border-radius: 10px; transition: width 0.3s ease; width: 0%; }
        .log { background: #000; color: #0f0; padding: 10px; height: 300px; overflow-y: auto; font-family: monospace; border-radius: 4px; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .status { font-weight: bold; padding: 5px; border-radius: 4px; }
        .status.pending { background: #fff3cd; }
        .status.cloning { background: #cce5ff; }
        .status.scanning { background: #cce5ff; }
        .status.saving { background: #e7f3ff; }
        .status.completed { background: #d4edda; }
        .status.failed { background: #f8d7da; }
        .info { background: #d1ecf1; padding: 15px; border-radius: 4px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🚀 SSE Functionality Test - Xployt.ai</h1>
    
    <div class="info">
        <strong>ℹ️ About this test:</strong><br>
        This page demonstrates the Server-Sent Events (SSE) streaming functionality that provides real-time scan progress updates.
        The test uses mock data to show how the SSE implementation works without requiring database setup or authentication.
    </div>
    
    <div class="container">
        <h3>📡 SSE Stream Test</h3>
        
        <button id="startTest">Start SSE Test</button>
        <button id="stopTest" disabled>Stop Test</button>
        
        <div style="margin: 10px 0;">
            <strong>Status:</strong> <span id="status" class="status pending">Ready to test</span>
        </div>
        
        <div>
            <strong>Progress:</strong>
            <div class="progress-bar">
                <div id="progressFill" class="progress-fill"></div>
            </div>
            <span id="progressText">0% - Click 'Start SSE Test' to begin</span>
        </div>
    </div>
    
    <div class="container">
        <h3>📋 Connection Log</h3>
        <div id="log" class="log">SSE Test ready. This demonstrates real-time progress streaming via Server-Sent Events.
        
Expected SSE message format:
{
  "scan_id": "test-12345",
  "status": "scanning", 
  "progress_percent": 45,
  "progress_text": "Analyzing code...",
  "timestamp": "2025-01-20T10:30:00Z"
}

Click 'Start SSE Test' to see it in action!
</div>
    </div>

    <div class="container">
        <h3>🔧 Implementation Details</h3>
        <ul>
            <li><strong>SSE Endpoint:</strong> <code>/test-sse</code> (this test) or <code>/api/v1/scans/{scan_id}/stream</code> (real API)</li>
            <li><strong>Message Format:</strong> JSON data with scan_id, status, progress_percent, progress_text, timestamp</li>
            <li><strong>Connection:</strong> Automatic close on completion, 1-hour timeout</li>
            <li><strong>Status Values:</strong> pending → cloning → scanning → saving → completed/failed</li>
        </ul>
    </div>

    <script>
        let eventSource = null;
        
        const statusEl = document.getElementById('status');
        const progressFillEl = document.getElementById('progressFill');
        const progressTextEl = document.getElementById('progressText');
        const logEl = document.getElementById('log');
        const startBtn = document.getElementById('startTest');
        const stopBtn = document.getElementById('stopTest');

        function log(message) {
            const timestamp = new Date().toLocaleTimeString();
            logEl.innerHTML += `\\n[${timestamp}] ${message}`;
            logEl.scrollTop = logEl.scrollHeight;
        }

        function updateProgress(data) {
            statusEl.textContent = data.status;
            statusEl.className = `status ${data.status}`;
            
            progressFillEl.style.width = `${data.progress_percent}%`;
            progressTextEl.textContent = `${data.progress_percent}% - ${data.progress_text}`;
            
            log(`📊 Progress: ${data.progress_percent}% | Status: ${data.status} | ${data.progress_text}`);
        }

        function startSSETest() {
            log('🔌 Starting SSE connection to /test-sse...');
            
            eventSource = new EventSource('/test-sse');
            
            eventSource.onopen = function(event) {
                log('✅ SSE connection established successfully!');
                startBtn.disabled = true;
                stopBtn.disabled = false;
            };
            
            eventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    log(`📥 SSE: ${event.data}`);
                    updateProgress(data);
                    
                    // Auto-close when scan completes
                    if (data.status === 'completed' || data.status === 'failed') {
                        log('🏁 Scan completed, closing SSE connection...');
                        stopSSETest();
                    }
                } catch (error) {
                    log(`❌ Error parsing SSE data: ${error.message}`);
                }
            };
            
            eventSource.onerror = function(event) {
                log(`🚨 SSE connection error: ${event.type}`);
                if (eventSource.readyState === EventSource.CLOSED) {
                    log('🔌 SSE connection closed');
                    stopSSETest();
                }
            };
        }

        function stopSSETest() {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
                log('🛑 SSE connection terminated');
            }
            
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }

        startBtn.addEventListener('click', startSSETest);
        stopBtn.addEventListener('click', stopSSETest);
        
        log('🎯 SSE Test Page loaded successfully!');
        log('💡 This simulates the real-time scan progress functionality.');
        log('🔍 In production, connect to /api/v1/scans/{scan_id}/stream with authentication.');
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    print("🚀 Starting SSE Test Server...")
    print("📡 Open http://localhost:3000 to test SSE functionality")
    print("🔧 This demonstrates the SSE streaming without requiring full app setup")
    print("⚡ Press Ctrl+C to stop")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="info"
    )