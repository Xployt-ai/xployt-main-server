# Xploit.ai Authentication Test Frontent

> Note: Contains Fully Ai generated code

A simple HTML frontend to test the GitHub OAuth authentication flow with the FastAPI backend.

## Quick Start

1. **Start the FastAPI server** (in the main project directory):

    ```bash
    # Make sure you have your .env file configured
    python run.py
    # or
    docker-compose up
    ```

2. **Start the test frontend server**:

    ```bash
    cd test/test-front
    python serve.py
    ```

3. **Open your browser** to http://localhost:3000

## What This Tests

### ✅ **Features Tested:**

-   API server connectivity
-   GitHub OAuth URL generation
-   GitHub OAuth callback flow
-   JWT token storage and management
-   Protected endpoint access (`/api/v1/auth/me`)
-   Token persistence in localStorage

### 🔧 **How to Use:**

1. **Test Connection**: Click "Test API Connection" to verify your FastAPI server is running
2. **GitHub Auth**: Click "Login with GitHub" to start the OAuth flow
3. **Follow OAuth**: Click the generated GitHub link to authenticate
4. **Automatic Redirect**: After GitHub auth, you'll be redirected back with a token
5. **Test Profile**: Click "Get My Profile" to test the protected endpoint

### 🐛 **Troubleshooting:**

**OAuth Callback Issues:**

-   Make sure your GitHub OAuth app callback URL is set to: `http://localhost:8000/api/v1/auth/github/callback`
-   The backend will redirect to `http://localhost:3000` after successful auth

**CORS Issues:**

-   The FastAPI server has CORS enabled for all origins in development mode

**Token Issues:**

-   Tokens are stored in localStorage and persist between sessions
-   Use "Clear Token" to reset authentication state
-   You can manually paste tokens in the token input field

### 📋 **Manual Testing Steps:**

If automatic OAuth doesn't work:

1. Get the GitHub OAuth URL from the API
2. Visit the URL and authorize the app
3. Copy the token from the callback URL
4. Paste it into the "Access Token" field
5. Click "Save Token"
6. Test the protected endpoint

### 🔍 **Expected Results:**

**Successful Authentication:**

```json
{
    "id": "user_object_id",
    "github_id": "123456789",
    "username": "your-github-username",
    "email": "your-email@example.com",
    "avatar_url": "https://avatars.githubusercontent.com/u/123456789",
    "created_at": "2024-01-01T00:00:00"
}
```

**Failed Authentication:**

```json
{
    "detail": "Could not validate credentials"
}
```

## Files

-   `index.html` - Main test interface
-   `serve.py` - Simple HTTP server to serve the frontend
-   `README.md` - This file

## Notes

-   This is a development/testing tool only
-   Tokens are stored in browser localStorage
-   The frontend assumes the API is running on `localhost:8000`
-   The frontend server runs on `localhost:3000`
