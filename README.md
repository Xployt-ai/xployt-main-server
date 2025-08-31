# Xploit.ai - Main Server

A FastAPI-based vulnerability scanning platform for MERN stack applications.

### Setup Instructions

1. **Clone and Setup Environment**

    ```bash
    git clone <repository-url>
    cd xployt-main-backend
    cp .env.sample .env
    ```

2. **Configure Environment Variables**
   Edit `.env` file with your values:

    ```
    MONGODB_URL=mongodb://localhost:27017
    MONGODB_NAME=xploitai
    SECRET_KEY=your-super-secret-key-here
    GITHUB_CLIENT_ID=your-github-client-id
    GITHUB_CLIENT_SECRET=your-github-client-secret
    ```

3. **GitHub OAuth Setup**
    - Go to GitHub Settings > Developer settings > OAuth Apps
    - Create a new OAuth App with:
        - Application name: Xploit.ai
        - Homepage URL: http://localhost:8000
        - Authorization callback URL: http://localhost:8000/api/v1/auth/github/callback

### Running the Application

#### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

python run.py
```

### API Documentation

Once running, visit:

-   **Swagger UI**: http://localhost:8000/docs
-   **ReDoc**: http://localhost:8000/redoc

## SSE Real-Time Streaming

The platform supports real-time scan progress updates via Server-Sent Events (SSE). This enables frontend applications to receive live updates during scan execution instead of polling for status.

### Documentation

- **[SSE Integration Guide](./docs/SSE_INTEGRATION.md)** - Frontend integration examples and API usage
- **[Scanner Service Protocol](./docs/SCANNER_SERVICE_PROTOCOL.md)** - Interface specification for scanner services  
- **[Local Testing Guide](./docs/LOCAL_TESTING_GUIDE.md)** - Setup and testing instructions

### Quick Test

```bash
# Test SSE functionality locally
python test_sse.py
# Visit http://localhost:3000 for interactive demo

# Or use the main server test page
python run.py  
# Visit http://localhost:8000/docs/sse_test.html
```

### Key Features

- ✅ Real-time progress streaming via SSE
- ✅ Frontend WebSocket-like experience with standard HTTP
- ✅ Automatic connection management and error handling
- ✅ Backward compatibility with polling endpoints
- ✅ Comprehensive testing and documentation
