# todo-service/main.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncpg
import uvicorn
import os
from contextlib import asynccontextmanager
import logging
from datetime import datetime
import httpx
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# Database Models
class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[str] = Field("medium", pattern="^(low|medium|high)$")

class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    user_id: str
    created_at: datetime
    updated_at: datetime

class UserInfo(BaseModel):
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None

# Database functions
async def init_db():
    """Initialize database connection pool and create tables"""
    global db_pool
    
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql://todouser:todopassword@postgres-todo:5432/todoapp"
    )
    
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        logger.info("Database connection pool created successfully")
        
        # Create tables if they don't exist
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
                    user_id VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_todos_completed ON todos(completed);
            """)
            
        logger.info("Database tables created/verified successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def close_db():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

# Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

# FastAPI app
app = FastAPI(
    title="Todo Microservice",
    description="A todo management service with user authentication",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth dependency
async def get_current_user(request: Request) -> UserInfo:
    """Extract user information from API Gateway headers or validate token directly"""
    
    # Try to get user info from API Gateway headers first (if using gateway)
    user_id = request.headers.get("X-User-ID")
    user_email = request.headers.get("X-User-Email") 
    user_name = request.headers.get("X-User-Name")
    
    if user_id:
        return UserInfo(
            user_id=user_id,
            email=user_email if user_email else None,
            name=user_name if user_name else None
        )
    
    # If no gateway headers, validate token directly with auth service
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. No valid token found."
        )
    
    token = auth_header.split(" ")[1]
    
    # Validate token with auth service
    auth_service_url = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{auth_service_url}/api/auth/validate",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication token"
                )
            
            user_data = response.json()
            user = user_data["user"]
            
            return UserInfo(
                user_id=str(user["id"]),
                email=user["email"],
                name=f"{user['first_name']} {user['last_name']}"
            )
    
    except httpx.TimeoutException:
        logger.error("Auth service timeout")
        raise HTTPException(
            status_code=503,
            detail="Authentication service timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"Auth service connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable"
        )
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return {"status": "healthy", "database": "connected"}
        else:
            return {"status": "unhealthy", "database": "not_connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# User info endpoint
@app.get("/api/auth/me", response_model=UserInfo)
async def get_user_info(current_user: UserInfo = Depends(get_current_user)):
    """Get current user information"""
    return current_user

# Todo CRUD endpoints
@app.get("/api/todos", response_model=List[TodoResponse])
async def get_todos(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: UserInfo = Depends(get_current_user)
):
    """Get todos for the current user"""
    query = """
        SELECT id, title, description, completed, priority, user_id, created_at, updated_at
        FROM todos 
        WHERE user_id = $1
    """
    params = [current_user.user_id]
    param_count = 1
    
    if completed is not None:
        param_count += 1
        query += f" AND completed = ${param_count}"
        params.append(completed)
    
    if priority:
        param_count += 1
        query += f" AND priority = ${param_count}"
        params.append(priority)
    
    query += " ORDER BY created_at DESC"
    
    if limit:
        param_count += 1
        query += f" LIMIT ${param_count}"
        params.append(limit)
    
    if offset:
        param_count += 1
        query += f" OFFSET ${param_count}"
        params.append(offset)
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        
    return [
        TodoResponse(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            completed=row['completed'],
            priority=row['priority'],
            user_id=row['user_id'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        for row in rows
    ]

@app.post("/api/todos", response_model=TodoResponse)
async def create_todo(
    todo: TodoCreate,
    current_user: UserInfo = Depends(get_current_user)
):
    """Create a new todo for the current user"""
    query = """
        INSERT INTO todos (title, description, priority, user_id)
        VALUES ($1, $2, $3, $4)
        RETURNING id, title, description, completed, priority, user_id, created_at, updated_at
    """
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            query, 
            todo.title, 
            todo.description, 
            todo.priority,
            current_user.user_id
        )
    
    return TodoResponse(
        id=row['id'],
        title=row['title'],
        description=row['description'],
        completed=row['completed'],
        priority=row['priority'],
        user_id=row['user_id'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )

@app.get("/api/todos/{todo_id}", response_model=TodoResponse)
async def get_todo(
    todo_id: int,
    current_user: UserInfo = Depends(get_current_user)
):
    """Get a specific todo"""
    query = """
        SELECT id, title, description, completed, priority, user_id, created_at, updated_at
        FROM todos 
        WHERE id = $1 AND user_id = $2
    """
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, todo_id, current_user.user_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    return TodoResponse(
        id=row['id'],
        title=row['title'],
        description=row['description'],
        completed=row['completed'],
        priority=row['priority'],
        user_id=row['user_id'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )

@app.put("/api/todos/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    todo_update: TodoUpdate,
    current_user: UserInfo = Depends(get_current_user)
):
    """Update a todo"""
    # Build dynamic update query
    update_fields = []
    params = []
    param_count = 0
    
    if todo_update.title is not None:
        param_count += 1
        update_fields.append(f"title = ${param_count}")
        params.append(todo_update.title)
    
    if todo_update.description is not None:
        param_count += 1
        update_fields.append(f"description = ${param_count}")
        params.append(todo_update.description)
    
    if todo_update.completed is not None:
        param_count += 1
        update_fields.append(f"completed = ${param_count}")
        params.append(todo_update.completed)
    
    if todo_update.priority is not None:
        param_count += 1
        update_fields.append(f"priority = ${param_count}")
        params.append(todo_update.priority)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    param_count += 1
    update_fields.append(f"updated_at = ${param_count}")
    params.append(datetime.utcnow())
    
    # Add WHERE conditions
    param_count += 1
    params.append(todo_id)
    param_count += 1
    params.append(current_user.user_id)
    
    query = f"""
        UPDATE todos 
        SET {', '.join(update_fields)}
        WHERE id = ${param_count-1} AND user_id = ${param_count}
        RETURNING id, title, description, completed, priority, user_id, created_at, updated_at
    """
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)
    
    if not row:
        raise HTTPException(status_code=404, detail="Todo not found")
    
    return TodoResponse(
        id=row['id'],
        title=row['title'],
        description=row['description'],
        completed=row['completed'],
        priority=row['priority'],
        user_id=row['user_id'],
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )

@app.delete("/api/todos/{todo_id}")
async def delete_todo(
    todo_id: int,
    current_user: UserInfo = Depends(get_current_user)
):
    """Delete a todo"""
    query = "DELETE FROM todos WHERE id = $1 AND user_id = $2"
    
    async with db_pool.acquire() as conn:
        result = await conn.execute(query, todo_id, current_user.user_id)
    
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Todo not found")
    
    return {"message": "Todo deleted successfully"}

# Statistics endpoint
@app.get("/api/todos/stats")
async def get_todo_stats(current_user: UserInfo = Depends(get_current_user)):
    """Get todo statistics for the current user"""
    query = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE completed = true) as completed,
            COUNT(*) FILTER (WHERE completed = false) as pending,
            COUNT(*) FILTER (WHERE priority = 'high') as high_priority,
            COUNT(*) FILTER (WHERE priority = 'medium') as medium_priority,
            COUNT(*) FILTER (WHERE priority = 'low') as low_priority
        FROM todos 
        WHERE user_id = $1
    """
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(query, current_user.user_id)
    
    return {
        "total": row['total'],
        "completed": row['completed'],
        "pending": row['pending'],
        "by_priority": {
            "high": row['high_priority'],
            "medium": row['medium_priority'],
            "low": row['low_priority']
        }
    }
