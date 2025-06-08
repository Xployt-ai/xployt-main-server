Of course. Based on the project proposal for Xploit.ai, here is a detailed development plan and architectural design for the main server. The plan focuses on the FastAPI gateway, which will serve as the central nervous system of your platform.

### **Xploit.ai Main Server: Architectural & Development Plan**

This plan outlines the design for a robust, scalable, and modular main server using FastAPI, as specified in your project description. The server will act as the primary API gateway and orchestrator for the entire Xploit.ai platform.

---

### **1. High-Level Architecture Overview**

The main server is the user-facing entry point and the central coordinator in your microservices architecture. Its primary responsibilities are to handle user interactions, manage repositories, schedule and orchestrate security scans, and aggregate the results.

-   **Technology Stack:**

    -   **Framework:** Python 3.10+ with FastAPI for its performance and automatic documentation.
    -   **Database:** MongoDB for flexible data storage of user info, scan results, and repository metadata.
    -   **Task Queuing:** Celery with RabbitMQ as the message broker for dispatching and managing long-running scan tasks asynchronously.
    -   **Data Validation:** Pydantic for robust request/response data modeling and validation.

-   **Architectural Pattern:** Microservices. The main server will be one service, communicating with:
    1.  **Frontend (React):** Via a RESTful API.
    2.  **Worker Services (Python):** Via a RabbitMQ message queue. These workers perform the actual scans (Secret Scanning, LLM Analysis, DAST).
    3.  **TypeScript Language Server:** Via an internal REST API for deep code analysis.
    4.  **File System Proxy:** A service to handle cloning and accessing repository files securely.
    5.  **GitHub API:** For authentication and repository management.

---

### **2. Core Modules & Components**

The main server should be built with a modular structure. Here are the key components:

#### **A. User & Authentication Module**

-   **Functionality:** Handles user registration, login via GitHub OAuth, and session management.
-   **Implementation Details:**
    -   Implement the GitHub OAuth2 flow to authenticate users and obtain API access tokens.
    -   Use JSON Web Tokens (JWT) for managing user sessions. The server will issue a token upon successful login, which the frontend will include in subsequent requests.
    -   Store user information in a `users` collection in MongoDB. **Crucially, user GitHub tokens must be encrypted at rest in the database.**
-   **API Endpoints:**
    -   `POST /api/v1/auth/github`: Initiates the GitHub OAuth flow.
    -   `GET /api/v1/auth/github/callback`: The callback URL for GitHub to redirect to after authorization.
    -   `GET /api/v1/users/me`: Fetches the profile of the currently authenticated user.

#### **B. Repository Management Module**

-   **Functionality:** Allows users to link, view, and manage their GitHub repositories.
-   **Implementation Details:**
    -   Create a service that uses the authenticated user's GitHub token to interact with the GitHub API (e.g., using the `httpx` or `PyGitHub` library).
    -   Functions will include listing user repositories, listing branches, and retrieving repository metadata.
    -   Store linked repository information in a `repositories` collection, linking it to the user ID.
-   **API Endpoints:**
    -   `POST /api/v1/repositories`: Link a new repository to the user's account.
    -   `GET /api/v1/repositories`: List all repositories linked by the user.
    -   `GET /api/v1/repositories/{repo_id}/branches`: List branches for a specific repository.

#### **C. Scan Orchestration Module**

-   **Functionality:** The brain of the operation. It receives scan requests, creates tasks for the various analysis workers, and tracks their progress.
-   **Implementation Details:**
    -   Integrate Celery with a RabbitMQ broker.
    -   When a user requests a scan, the API endpoint will:
        1.  Create a new `scan` document in MongoDB with a `pending` status.
        2.  Trigger a request to the "File System Proxy" service to clone or update the repository code.
        3.  Once the code is ready, dispatch one or more tasks to the Celery queue (e.g., `tasks.surface_scan`, `tasks.llm_analysis`). Each task message will contain the necessary context, like the path to the cloned repository and the scan ID.
    -   Implement a mechanism for workers to report back their status (`running`, `completed`, `failed`). This can be done via Celery's result backend or by having workers update the `scan` document directly.
-   **API Endpoints:**
    -   `POST /api/v1/scans`: Trigger a new scan for a given repository and branch.
    -   `GET /api/v1/scans/{scan_id}`: Get the status and summary of a specific scan.

#### **D. Results & Reporting Module**

-   **Functionality:** Collects, stores, and serves the vulnerability findings from all scans.
-   **Implementation Details:**
    -   Design a flexible `vulnerabilities` collection in MongoDB. The schema should accommodate different data from different scanners (e.g., file path, line number, CVE, LLM reasoning, DAST payload).
    -   Workers, upon finding a vulnerability, will write directly to this collection, associating each finding with the `scan_id`.
    -   The API should provide powerful querying capabilities to the frontend.
-   **API Endpoints:**
    -   `GET /api/v1/results/{scan_id}`: Fetch all vulnerability results for a given scan, with support for filtering (`?severity=critical`, `?type=sast`) and pagination.

---

### **3. Database Schema Design (MongoDB)**

A non-relational database like MongoDB is ideal for its flexible schema.

-   **`users` collection:**

    -   `_id`: `ObjectId`
    -   `github_id`: `String` (Indexed)
    -   `username`: `String`
    -   `email`: `String`
    -   `avatar_url`: `String`
    -   `github_access_token`: `Binary` (Encrypted)
    -   `created_at`: `DateTime`

-   **`repositories` collection:**

    -   `_id`: `ObjectId`
    -   `user_id`: `ObjectId` (Reference to `users`)
    -   `github_repo_id`: `String` (Indexed)
    -   `name`: `String` (`owner/repo`)
    -   `private`: `Boolean`
    -   `webhook_id`: `String` (For CI integration)

-   **`scans` collection:**

    -   `_id`: `ObjectId`
    -   `repository_id`: `ObjectId` (Reference to `repositories`)
    -   `status`: `String` (`pending`, `running`, `completed`, `failed`)
    -   `triggered_by`: `String` (`user`, `webhook`)
    -   `created_at`: `DateTime`
    -   `finished_at`: `DateTime`

-   **`vulnerabilities` collection:**
    -   `_id`: `ObjectId`
    -   `scan_id`: `ObjectId` (Reference to `scans`, Indexed)
    -   `type`: `String` (`secret`, `sast`, `llm`, `dast`)
    -   `severity`: `String` (`critical`, `high`, `medium`, `low`)
    -   `description`: `String`
    -   `location`: `Object` { `file`: `String`, `line`: `Integer` }
    -   `metadata`: `Object` (A flexible field for scanner-specific details)

---

### **4. Phased Development Roadmap**

A phased approach will ensure a solid foundation and allow for iterative development.

-   **Phase 1: Foundation & Authentication**

    -   **Goal:** Get a basic server running and allow users to log in.
    -   **Tasks:**
        1.  Set up FastAPI project structure, linters, and formatters.
        2.  Implement the `users` model and GitHub OAuth2 logic.
        3.  Build the core auth endpoints (`/auth/github`, `/auth/github/callback`, `/users/me`).
        4.  Set up Dockerfile and Docker Compose for the main server.

-   **Phase 2: Repository Management**

    -   **Goal:** Allow users to connect their GitHub repos.
    -   **Tasks:**
        1.  Implement the `repositories` model.
        2.  Create the GitHub API service wrapper.
        3.  Build the API endpoints to list and link repositories.

-   **Phase 3: Asynchronous Scanning Backbone**

    -   **Goal:** Establish the core infrastructure for running scans.
    -   **Tasks:**
        1.  Integrate Celery and RabbitMQ into the project.
        2.  Define the `scans` and `vulnerabilities` database models.
        3.  Create the `POST /api/v1/scans` endpoint to create a scan job and dispatch a _mock_ task to Celery.
        4.  Set up a basic worker that can receive the task and update the scan status.

-   **Phase 4: Full Scan Integration & Results**

    -   **Goal:** Connect the main server to the actual scanning workers and process results.
    -   **Tasks:**
        1.  Finalize the API/message contract between the main server and each worker.
        2.  Develop the logic for workers to write results to the `vulnerabilities` collection.
        3.  Build the `GET /api/v1/results/{scan_id}` endpoint with filtering and pagination.

-   **Phase 5: Continuous Integration & Advanced Features**
    -   **Goal:** Implement CI features and refine the platform.
    -   **Tasks:**
        1.  Create an endpoint to handle GitHub webhooks for automated re-scans on push/PR events.
        2.  Implement logic for scheduled scans (e.g., using Celery Beat).
        3.  Add comprehensive logging, monitoring, and error handling.
