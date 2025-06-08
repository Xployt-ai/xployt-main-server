# Xploit.ai: Web-Based Vulnerability Scanning Platform for MERN Projects

The Goal and Objectives:
Xploit.ai aims to help solo developers and small teams secure their MERN-stack applications by automatically identifying security issues before deployment. The primary goals are to integrate multiple analysis techniques into one user-friendly platform and to raise developer awareness of security best practices. Specific objectives include:
Automated Multi-Layer Scanning: Provide surface-level secret/misconfiguration scans, static code analysis, LLM-based logic checking, and dynamic sandbox testing.

Seamless Integration: Allow users to sign in and link private GitHub repositories for on-demand or scheduled scans.

Actionable Reporting: Present findings in clear dashboards with code references and remediation hints.

Developer Empowerment: Enable even non-experts to catch vulnerabilities early, bridging the gap where security often “takes a back seat” during fast development

A brief introduction to the project:
Xploit.ai is a project to build a web platform for MERN-stack security scanning. Users log in (e.g. via GitHub), connect their private GitHub repositories, and run automated scans. The system analyzes the code and configuration at multiple layers:
Surface-Level Scanning: Searches for exposed secrets (API keys, tokens) and common misconfigurations (e.g. public database endpoints) using pattern-matching tools.

LLM-Powered Reasoning: Leverage a large language model (LLM) to reason about application logic. The LLM can read functions or flows from the repository and flag suspicious behavior (e.g. unsafe authentication logic, business-logic flaws). By integrating an LLM (like GPT-4 or Code LLaMA), Xploit.ai provides a contextual review layer beyond pattern matching.

Dynamic Analysis (Sandbox Testing): Run the application (or critical parts) in a controlled environment and perform simulated attacks or fuzzing. Dynamic Application Security Testing (DAST) works by “monitoring an application’s behavior and observing its reaction to staged attacks” without needing source code. In practice, Xploit.ai will spin up a containerized sandbox (e.g. using Docker) to exercise the code and detect runtime issues (e.g. authentication bypass, SQL injection) that only appear when the app is running.
To enhance code analysis capabilities, internal tools will be developed to perform comprehensive scans. This includes leveraging TypeScript language servers to gain deeper insights into the codebase structure, facilitating the identification of potential vulnerabilities and improving overall code quality.

The platform then aggregates all findings into a dashboard. Users can see categorized reports (e.g. secrets found, injection paths, logical flaws, crashes) with code references and severity. By bundling these techniques, Xploit.ai will help developers catch vulnerabilities that are often “left unchecked” and ensure even solo coders can follow security best practices.

The scope of the project:
In Scope:
User Management: Sign-in (e.g. GitHub), user session management, and linking of one or more GitHub repositories.

Scanning Subsystems: Implementing three analysis layers as described (surface-level, LLM, dynamic) specifically for MERN-stack code and common config formats (.env files, JSON configs, Dockerfiles, etc.).

Reporting UI: A React-based dashboard to display scan results, filter issues by category/severity, and guide the user to fix problems.

Environment: A sandboxed container environment (cloud VM) to run dynamic tests safely, without exposing the host.
Continuous Monitoring: A Github action to automate re-running analysis based on code changes in the repository.
Documentation & Testing: Design and requirements documents, user manual, code documentation, and test cases (unit/integration).

Out of Scope:

This project is strictly limited to the MERN stack (MongoDB, Express.js, React, Node.js); other technology stacks will not be considered.
Comprehensive Enterprise-level Security: Xploit.ai focuses on MERN-specific app code and typical configuration issues. It will not cover network security (firewall, DDoS), non-MERN languages (PHP, .NET, etc.), or in-depth hardware security.
Automatic Fixing: The tool identifies and reports vulnerabilities but does not automatically remediate code. (It may, however, suggest common fixes.)
Target Audience
Solo Developers / Indie Teams: The primary users are individual or very small teams building MERN applications (e.g. startups, hobbyists, students). These users need security checks without requiring a dedicated security team.

Students and Educators: As an academic project, Xploit.ai may be of interest to students learning about web security, offering a hands-on tool to understand vulnerabilities.

In summary, the target audience is security-conscious MERN developers who lack time or resources to manually audit code. Xploit.ai lowers the entry barrier by providing integrated tooling and clear guidance.
Main Functionalities
The platform will offer the following key functions:
User Authentication & Repository Linking: Allow users to create an account (via GitHub OAuth or email/password) and securely connect their private GitHub repos. The system will fetch the repository code (read-only) for scanning.

Repository Management: Users can view a list of linked repositories and select which branches/tags to analyze. The UI will show basic repo info (name, last commit).

Secret & Config Scanning: Scan code, environment files, and configuration for hard-coded secrets (API keys, passwords) and insecure settings. For example, using tools like TruffleHog to “find secrets, passwords, and sensitive keys” in the repo. Also detect common misconfigurations (e.g. CORS overly permissive, debug modes enabled, public DB endpoints) and warn the user.

LLM-Powered Logic Review: Utilize an LLM (such as GPT-4, CodeBERT-based model, or a comparable open model) to perform contextual code review. The LLM will take selected code segments or describe code flows and answer prompts about security risks. We will incorporate an agentic loop so the LLM highlights suspicious patterns. Given that recent studies report high vulnerability-detection accuracy for LLMs, this layer helps catch flaws that static patterns miss (e.g. flawed business logic or mis-sequenced operations).

Dynamic (Runtime) Analysis: Launch the application or parts of it in a secure sandbox environment and perform automated tests. This could involve API fuzzing, sending malicious inputs, or simulating attack payloads. The process reflects DAST methodology: the system “simulates automated attacks on an application to trigger unexpected results”. For example, it might attempt common exploits like XSS or SQL injection against running endpoints. Any crashes, error messages, or unexpected behavior are recorded as potential vulnerabilities.

Vulnerability Reporting UI: All findings from the above scans will be compiled into a unified report per repository. The React-based frontend will display categorized issues (e.g. “Critical: SQL Injection in server.js”, “Medium: JWT token in state” with relevant lines). Each report entry will include: description of the issue, code snippet where it was found, severity level, and a brief remediation suggestion. Users can filter by severity, scan type, or date.

Github Action: Users can integrate our GitHub Action into their repositories by defining custom workflows that automatically trigger code re-analysis upon changes. This setup allows for flexible configuration based on specific events, such as file modifications or pull requests, ensuring continuous and tailored code quality assessments.
Tentative Technologies:

The technology choices balance modern frameworks, ease of development, and academic learning value.
Frontend: React will be used for the client-side UI (JavaScript).
Backend/API: The platform is split into focused micro-services. A FastAPI gateway handles authentication, scheduling, and the public REST interface, while dedicated Python worker services perform each analysis layer (surface scan, SAST, LLM reasoning, DAST) asynchronously with Celery/RabbitMQ. A separate Express server written in TypeScript powers the custom language-server tooling for deep code-structure insights, and a lightweight file-system proxy service manages secure repository clones and artifact storage.
DataBase: MongoDB will be used for the database in the backend server.
GitHub Integration: We will use the GitHub API to fetch repository contents. Python packages like PyGitHub or the requests library can call GitHub’s REST/GraphQL endpoints. For authentication, we’ll implement GitHub OAuth for user sign-in.

LLM Integration: Integration with an LLM (likely via an API) for code analysis. We may use OpenAI’s GPT. The system will format code snippets as prompts and parse responses.

Dynamic Sandbox: We plan to use Docker to create isolated containers for running code. Each scan could spin up a container with the user’s code, run basic test scripts or tools like OWASP ZAP or custom fuzzers, then destroy the container.

Database/Storage: We will initiate an empty database instance for projects. If necessary, we will request a database dump from the user to analyze relevant data (e.g., user accounts, scan results).

Miscellaneous: Git (version control), GitHub Actions or simple scripts for CI (testing, linting).
Each technology is chosen for relevance: React for modern UI, Python/FastAPI for quick API development, and Docker for safe execution.

Work Justification and Project Complexity
While this project leverages modern frameworks like React and FastAPI to accelerate development, the scope and depth of implementation amply justify the academic credits assigned. The effort required goes far beyond assembling off-the-shelf components — it involves substantial architectural design, research exploration, and system integration across multiple layers.
Frontend Complexity – Beyond Basic React:

React helps speed up UI development, but we must architect a robust component and state management system to accommodate expanding vulnerability types and diverse scan reports.

The interface must handle long-running background operations gracefully — providing real-time status feedback, handling edge-case failures, and maintaining responsiveness even under load.

Backend Research & Engineering Challenges:

Each layer of the security analysis pipeline (surface scan, SAST, LLM analysis, DAST) involves non-deterministic workflows, especially where AI and contextual reasoning are applied. This requires deep research, experimentation, and iterative refinement, not just routine programming.

Microservices Development:

The architecture is microservice-based to promote modularity and independent iteration. However, this also introduces complexity across technology stacks — requiring proficiency in both Python (FastAPI, Celery) and TypeScript (Express, custom language server). Communication, orchestration, and service discovery must be handled effectively.

Worker Queues and Middleware Architecture:

Computationally expensive tasks (e.g., static analysis, sandbox execution) need to be queued and distributed efficiently, demanding a carefully designed asynchronous task architecture. Middleware must be modular yet cohesive, handling authentication, logging, error propagation, and coordination between services.

Core Protocol & Analysis Integration:

The backbone server is not a simple API layer — it must support a pluggable protocol to dynamically incorporate new analysis modules, whether written in Python or other languages. This demands thoughtful API design, service registration mechanisms, and inter-process communication patterns.

DevOps and Sandbox Infrastructure:

Spinning up user applications automatically from GitHub repos involves advanced DevOps workflows: cloning code, installing dependencies, provisioning Docker containers, managing network isolation, and injecting test harnesses. Each of these steps introduces operational complexity and edge cases to handle.

Custom TypeScript Language Server:

Building or adapting a language server to understand project-specific constructs (e.g., tracing MongoDB queries, authentication logic) requires AST parsing, symbol resolution, and integration with external tooling — a technically involved task beyond typical Express usage.
