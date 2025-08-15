# Dream Team Backend Documentation

## Overview

The Dream Team backend is a FastAPI-based Python application that serves as the API layer for a multi-agent AutoGen/Magentic One system. It provides endpoints for team management, agent orchestration, and chat functionality.

## Architecture

### Core Components

- **FastAPI Application**: Main web framework handling HTTP requests
- **AutoGen 0.4**: Multi-agent framework with Magentic One integration
- **Azure OpenAI**: LLM provider for agent interactions
- **Azure AI Search**: RAG (Retrieval Augmented Generation) capabilities
- **Azure Container Apps**: Hosting platform with dynamic sessions
- **Azure Cosmos DB**: Data persistence layer

### Key Technologies

- **Python 3.10+**: Runtime environment
- **FastAPI**: Web framework
- **UV**: Package manager and virtual environment tool
- **Playwright**: Web automation for browser-based agents
- **Docker**: Containerization

## Project Structure

```
backend/
├── main.py                 # FastAPI application entry point
├── crud.py                 # Database operations
├── database.py             # Database configuration
├── aisearch.py            # Azure AI Search integration
├── magentic_one_custom_agent.py # Custom agent implementations
├── Dockerfile             # Container configuration
├── pyproject.toml         # Project dependencies
└── .env                   # Environment variables
```

## Environment Configuration

### Required Environment Variables

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=your_openai_endpoint
AZURE_OPENAI_API_KEY=your_api_key

# Azure AI Search  
AZURE_SEARCH_SERVICE_ENDPOINT=your_search_endpoint
AZURE_SEARCH_ADMIN_KEY=your_search_key

# Azure Container Apps
POOL_MANAGEMENT_ENDPOINT=your_pool_endpoint

# Database
COSMOS_DB_URI=your_cosmos_uri
COSMOS_DB_DATABASE=your_database_name

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=your_insights_connection

# Authentication
AZURE_CLIENT_ID=your_client_id
```

## Deployment

### Docker Container

The application is containerized using a multi-stage Dockerfile:

```dockerfile
FROM python:3-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /code
COPY . /code

# Install dependencies with UV
RUN uv sync --locked --no-dev

# Configure environment
ENV PATH="/code/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install browser dependencies for Playwright
RUN playwright install --with-deps chromium

EXPOSE 3100
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3100", "--workers", "4"]
```

### Azure Container Apps

Deployed using Azure Container Apps with:
- Managed identity authentication
- Auto-scaling capabilities
- Integration with Azure services
- Dynamic session management for secure code execution

## Local Development

### Prerequisites

- Python 3.10+
- UV package manager
- Docker (for agent code execution)
- Playwright browsers

### Setup

```bash
# Clone repository
git clone <repository-url>
cd backend

# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv sync
playwright install --with-deps chromium

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run development server
uvicorn main:app --reload
```

## API Endpoints

### Team Management
- `GET /teams` - List all teams
- `POST /teams` - Create new team
- `PUT /teams/{team_id}` - Update team
- `DELETE /teams/{team_id}` - Delete team

### Agent Operations
- `POST /agents` - Add agent to team
- `PUT /agents/{agent_id}` - Update agent
- `DELETE /agents/{agent_id}` - Remove agent

### Chat Interface
- `POST /chat` - Send message to agent team
- `GET /chat/history` - Retrieve chat history
- `POST /chat/stop` - Stop current session

### File Upload
- `POST /upload` - Upload files for RAG indexing

## Agent Types

### Built-in Agents
- **MagenticOneOrchestrator**: Main orchestration agent
- **WebSurfer**: Web browsing and search capabilities
- **FileSurfer**: File system operations
- **Coder**: Code generation and execution
- **ComputerTerminal**: Terminal command execution

### Custom RAG Agents
- Dynamically created agents with access to indexed documents
- Integration with Azure AI Search for knowledge retrieval

## Security Features

- **Managed Identity**: Azure AD authentication
- **Secure Code Execution**: Sandboxed environments via Container Apps
- **Content Safety**: Azure OpenAI content filtering
- **API Key Management**: Azure Key Vault integration

## Monitoring & Observability

- **Application Insights**: Performance and usage tracking
- **PromptFlow Tracing**: Agent interaction debugging
- **Health Checks**: Container readiness and liveness probes
- **Logging**: Structured logging with correlation IDs

## Performance Considerations

- **Async Operations**: FastAPI async/await patterns
- **Connection Pooling**: Efficient database connections
- **Caching**: Redis integration for session management
- **Load Balancing**: Multiple worker processes

## Troubleshooting

### Common Issues

1. **Docker not running**: Required for code execution agents
2. **Playwright browsers**: Install with `playwright install --with-deps chromium`
3. **Environment variables**: Ensure all required variables are set
4. **Azure permissions**: Verify managed identity has proper roles

### Debug Mode

```bash
# Enable detailed logging
export LOG_LEVEL=DEBUG
uvicorn main:app --reload --log-level debug
```