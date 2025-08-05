# OpsKube - Microservices Todo Application

A cloud-native todo application built with microservices architecture, featuring JWT authentication, PostgreSQL databases, and Kubernetes deployment on Google Cloud Platform.

## Architecture Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │────│ API Gateway  │────│Auth Service │    │Todo Service │
│   (Nginx)   │    │   (Port 8080)│    │ (Port 8001) │    │ (Port 8000) │
│  Port 3000  │    └──────────────┘    └─────────────┘    └─────────────┘
└─────────────┘                              │                     │
                                             │                     │
                                    ┌─────────────┐       ┌─────────────┐
                                    │PostgreSQL   │       │PostgreSQL   │
                                    │(Auth DB)    │       │(Todo DB)    │
                                    │Port 5433    │       │Port 5434    │
                                    └─────────────┘       └─────────────┘
```

## Services

### 🚪 API Gateway (Port 8080)
- **Framework**: FastAPI with HTTPx for async HTTP requests
- Central entry point routing requests to microservices
- JWT token validation and user header injection
- Automatic request forwarding with authentication context
- CORS handling and error management

### 🔐 Auth Service (Port 8001)
- **Framework**: FastAPI with AsyncPG for PostgreSQL
- **Security**: bcrypt password hashing + JWT tokens
- **Features**: User registration, login, token refresh, logout
- Refresh token management with database storage
- User profile management and admin endpoints
- Comprehensive token validation for other services

### ✅ Todo Service (Port 8000)
- **Framework**: FastAPI with AsyncPG for PostgreSQL
- **Features**: Full CRUD operations with priority levels (low/medium/high)
- User-isolated todo management with filtering and pagination
- Statistics endpoint for dashboard metrics
- Flexible authentication (API Gateway headers or direct JWT)
- Database indexing for optimal performance

### 🎨 Frontend (Port 3000)
- Static web application served by Nginx
- Responsive UI for todo management
- JWT-based authentication flow

## Prerequisites

- **Docker & Docker Compose** - For local development
- **kubectl** - Kubernetes command-line tool  
- **Terraform** - Infrastructure as Code (v1.0+)
- **Google Cloud SDK** - For GCP authentication and gcloud commands
- **Python 3.9+** - For local development (FastAPI, AsyncPG, bcrypt)
- **Git** - Version control

## Quick Start

### Local Development with Docker Compose

1. **Clone the repository**
   ```bash
   git clone https://github.com/asaadoov/OpsKube.git
   cd OpsKube
   ```

2. **Start all services**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - API Gateway: http://localhost:8080
   - Auth Service: http://localhost:8001
   - Todo Service: http://localhost:8000

4. **Health checks**
   ```bash
   # Check all services are healthy
   docker-compose ps
   
   # Test API endpoints
   curl http://localhost:8080/health
   curl http://localhost:8001/health
   curl http://localhost:8000/health
   ```

### Production Deployment on GCP

#### 1. Infrastructure Setup

```bash
cd terraform-k8s

# Initialize Terraform
terraform init

# Review and modify terraform.tfvars with your settings
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your GCP project details

# Plan and apply infrastructure
terraform plan
terraform apply
```

#### 2. Kubernetes Cluster Setup

```bash
# Follow the detailed guide
cat setup-k8s-cluster.md

# Or use the quick setup script
./terraform-k8s/scripts/init.sh
```

#### 3. Deploy Applications

```bash
# Apply Kubernetes manifests (to be created)
kubectl apply -f k8s/
```

## API Endpoints

### Authentication Service (`/api/auth/*`)
```
POST /api/auth/register     - User registration (email, password, names)
POST /api/auth/login        - User login (returns access + refresh tokens)
POST /api/auth/refresh      - Refresh access token
POST /api/auth/logout       - Logout (revoke refresh token)
GET  /api/auth/me          - Get current user profile
GET  /api/auth/validate    - Validate token (for other services)
GET  /api/auth/users       - List all users (admin)
GET  /health              - Health check
```

### Todo Service (`/api/todos/*`)
```
GET    /api/todos                    - Get user's todos (with filters)
  ?completed=true/false              - Filter by completion status
  ?priority=low/medium/high          - Filter by priority
  ?limit=100&offset=0               - Pagination
POST   /api/todos                   - Create new todo
GET    /api/todos/{id}              - Get specific todo
PUT    /api/todos/{id}              - Update todo (partial updates)
DELETE /api/todos/{id}              - Delete todo
GET    /api/todos/stats             - Get todo statistics
GET    /api/auth/me                 - Get current user info
GET    /health                      - Health check
```

### API Gateway (`/*`)
```
GET    /health                      - Gateway health check
/api/auth/*                        - Proxy to auth service (public)
/api/todos/*                       - Proxy to todo service (protected)
/api/user/*                        - Proxy to todo service (protected)
```

## Environment Variables

### Auth Service
```bash
AUTH_DATABASE_URL=postgresql://authuser:authpassword@postgres-auth:5432/authdb
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
```

### Todo Service
```bash
DATABASE_URL=postgresql://todouser:todopassword@postgres-todo:5432/todoapp
AUTH_SERVICE_URL=http://auth-service:8001
```

### API Gateway
```bash
AUTH_SERVICE_URL=http://auth-service:8001
TODO_SERVICE_URL=http://todo-service:8000
```

## Database Schema

### Auth Database (`authdb`)
```sql
-- Users table
users:
  - id (SERIAL PRIMARY KEY)
  - email (VARCHAR UNIQUE)
  - password_hash (VARCHAR)
  - first_name (VARCHAR)
  - last_name (VARCHAR)
  - is_active (BOOLEAN)
  - created_at, updated_at (TIMESTAMP)

-- Refresh tokens table
refresh_tokens:
  - id (SERIAL PRIMARY KEY)
  - user_id (INTEGER FK)
  - token_hash (VARCHAR)
  - expires_at (TIMESTAMP)
  - is_revoked (BOOLEAN)
  - created_at (TIMESTAMP)
```

### Todo Database (`todoapp`)
```sql
-- Todos table
todos:
  - id (SERIAL PRIMARY KEY)
  - title (VARCHAR 200)
  - description (TEXT)
  - completed (BOOLEAN DEFAULT FALSE)
  - priority (VARCHAR CHECK: low/medium/high)
  - user_id (VARCHAR 100)
  - created_at, updated_at (TIMESTAMP)
  
-- Indexes for performance
- idx_todos_user_id
- idx_todos_completed
```

## Development

### Running Individual Services (Development)

Each service can be run independently for development:

```bash
# Auth Service
cd auth-service
pip install fastapi asyncpg bcrypt pyjwt email-validator uvicorn
export AUTH_DATABASE_URL="postgresql://authuser:authpassword@localhost:5433/authdb"
export JWT_SECRET_KEY="your-development-secret-key"
python main.py

# Todo Service  
cd todo-service
pip install fastapi asyncpg httpx uvicorn
export DATABASE_URL="postgresql://todouser:todopassword@localhost:5434/todoapp"
export AUTH_SERVICE_URL="http://localhost:8001"
python main.py

# API Gateway
cd api-gateway  
pip install fastapi httpx uvicorn
export AUTH_SERVICE_URL="http://localhost:8001"
export TODO_SERVICE_URL="http://localhost:8000"
python main.py
```

**Note**: Make sure PostgreSQL databases are running (via docker-compose) before starting individual services.

### Testing

```bash
# Register a user
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "first_name": "Test",
    "last_name": "User"
  }'

# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'

# Create a todo (replace {access_token} from login response)
curl -X POST http://localhost:8080/api/todos \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {access_token}" \
  -d '{
    "title": "My First Todo",
    "description": "Complete the setup",
    "priority": "high"
  }'

# Get todos with filters
curl -H "Authorization: Bearer {access_token}" \
  "http://localhost:8080/api/todos?completed=false&priority=high&limit=10"

# Get todo statistics
curl -H "Authorization: Bearer {access_token}" \
  "http://localhost:8080/api/todos/stats"

# Update todo
curl -X PUT http://localhost:8080/api/todos/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {access_token}" \
  -d '{"completed": true, "priority": "medium"}'
```

## Security Features

- **JWT Authentication** - Stateless access tokens (30min) + refresh tokens (7 days)
- **Password Security** - bcrypt hashing with salt
- **Token Management** - Refresh token rotation and revocation
- **Database Isolation** - Separate PostgreSQL instances per service
- **Request Validation** - Pydantic models with field validation
- **Environment Secrets** - Configuration via environment variables
- **Health Monitoring** - Built-in health checks with database connectivity
- **User Isolation** - All todos are user-scoped with proper authorization
- **Input Sanitization** - SQL injection protection via parameterized queries

## Infrastructure

### GCP Resources (Terraform)
- **Compute Instances** - VM instances for Kubernetes nodes
- **Networking** - VPC, subnets, and firewall rules
- **Load Balancing** - External load balancer for ingress
- **Storage** - Persistent disks for databases

### Kubernetes Components
- **Deployments** - Stateless application containers
- **Services** - Internal service discovery
- **ConfigMaps** - Configuration management
- **Secrets** - Sensitive data management
- **Ingress** - External traffic routing

## Monitoring & Observability

### Health Checks
All services expose `/health` endpoints for:
- Application status
- Database connectivity
- Service dependencies

### Logging
- Application logs via Docker/Kubernetes
- Structured JSON logging
- Centralized log aggregation (planned)

## CI/CD Pipeline (Planned)

- **GitHub Actions** - Automated testing and deployment
- **Docker Registry** - Container image storage
- **GitOps** - Declarative deployment management