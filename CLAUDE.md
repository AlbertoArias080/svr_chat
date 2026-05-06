# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the development server (http://127.0.0.1:5000)
python run.py

# Utility scripts
python check_setup.py   # Initialize the chat_messages DynamoDB table
python list_users.py    # List all users in DynamoDB
```

There is no test suite. Manual verification uses the utility scripts above and the `/create-admin` route to seed an admin account (`admin@bmc.com` / `admin123`).

## Architecture

Flask application for the **Bolsa Mercantil de Colombia (BMC)** that combines document management with an AI-powered chatbot. The UI and system prompts are in Spanish.

### AWS Services
- **DynamoDB** — sole database: `users`, `documents`, `chat_messages` tables (auto-created on first run). All tables use UUID primary keys and have GSIs on frequently queried fields (e.g., `email`, `user_id`).
- **S3** — document storage under `uploads/{category}/{user_id}/{uuid_filename}`. Original filename stored separately in DynamoDB metadata.
- **Bedrock Agent** — handles chat. Configured via `BEDROCK_AGENT_ID` and `BEDROCK_AGENT_ALIAS_ID`. Two modes: full agent invocation (with session/citations) or direct `RetrieveAndGenerate` from the Knowledge Base.
- **Bedrock Knowledge Base** — S3-backed vector store (`BEDROCK_KNOWLEDGE_BASE_ID`). Documents uploaded by admins sync automatically; sync status is visible at `/admin/sync-status`.

### Application Layers

```
Flask Routes (auth, main, admin, chat blueprints)
    ↓
app/models.py (DynamoDB wrapper — User, Document, ChatMessage, DynamoDB classes)
    ↓
app/services/ (S3Service, BedrockAgentService / BMCCustomAgent)
    ↓
AWS (DynamoDB, S3, Bedrock)
```

- **`app/__init__.py`** — application factory; instantiates `DynamoDB`, registers blueprints, sets up Flask-Login.
- **`config.py`** — loads `.env` via `python-dotenv`; all AWS IDs/secrets come from environment variables.
- **`app/models.py`** — `DynamoDB` class is the single data-access object for all three tables. `User` implements `UserMixin` for Flask-Login.
- **`app/services/bedrock_agent_service.py`** — `BedrockAgentService` (low-level) and `BMCCustomAgent` (high-level with system context).
- **`app/services/s3_service.py`** — file upload/delete and Bedrock Knowledge Base ingestion job status.

### Role-Based Access

Two roles: `user` and `admin`. Admin routes (`/admin/*`) check `current_user.role != 'admin'` directly in each view. All non-public routes are protected with `@login_required`.

### Required Environment Variables (`.env`)

```
SECRET_KEY=
S3_BUCKET_NAME=
BEDROCK_AGENT_ID=
BEDROCK_AGENT_ALIAS_ID=
BEDROCK_KNOWLEDGE_BASE_ID=
# AWS credentials must be configured (boto3 default chain or explicit vars)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=
```
