# auth-service/main.py
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import asyncpg
import uvicorn
import os
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta
import bcrypt
import jwt
import secrets
from email_validator import validate_email, EmailNotValidError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Database connection pool
db_pool = None
security = HTTPBearer()

# Pydantic Models
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Database functions
async def init_db():
    """Initialize database connection pool and create tables"""
    global db_pool
    
    DATABASE_URL = os.getenv(
        "AUTH_DATABASE_URL", 
        "postgresql://authuser:authpassword@postgres-auth:5432/authdb"
    )
    
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
        logger.info("Auth database connection pool created successfully")
        
        # Create tables if they don't exist
        async with db_pool.acquire() as conn:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    first_name VARCHAR(50) NOT NULL,
                    last_name VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Refresh tokens table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    is_revoked BOOLEAN DEFAULT FALSE
                );
            """)
            
            # Create indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);")
            
        logger.info("Auth database tables created/verified successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize auth database: {e}")
        raise

async def close_db():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Auth database connection pool closed")

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
    title="Auth Microservice",
    description="Authentication and user management service",
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

# Helper functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token() -> str:
    """Create a secure refresh token"""
    return secrets.token_urlsafe(32)

async def get_user_by_email(email: str):
    """Get user by email from database"""
    query = "SELECT id, email, password_hash, first_name, last_name, is_active, created_at FROM users WHERE email = $1"
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, email)

async def get_user_by_id(user_id: int):
    """Get user by ID from database"""
    query = "SELECT id, email, password_hash, first_name, last_name, is_active, created_at FROM users WHERE id = $1"
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, user_id)

async def create_user(user_data: UserRegister):
    """Create a new user in database"""
    password_hash = hash_password(user_data.password)
    query = """
        INSERT INTO users (email, password_hash, first_name, last_name)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, first_name, last_name, is_active, created_at
    """
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(
            query, user_data.email, password_hash, 
            user_data.first_name, user_data.last_name
        )

async def store_refresh_token(user_id: int, token: str) -> None:
    """Store refresh token in database"""
    token_hash = hash_password(token)  # Hash the refresh token
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    query = "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3)"
    async with db_pool.acquire() as conn:
        await conn.execute(query, user_id, token_hash, expires_at)

async def verify_refresh_token(token: str) -> Optional[int]:
    """Verify refresh token and return user_id if valid"""
    query = """
        SELECT rt.user_id, rt.token_hash, rt.expires_at, rt.is_revoked
        FROM refresh_tokens rt
        WHERE rt.expires_at > NOW() AND rt.is_revoked = FALSE
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query)
        
        for row in rows:
            if verify_password(token, row['token_hash']):
                return row['user_id']
    
    return None

async def revoke_refresh_token(token: str) -> None:
    """Revoke a refresh token"""
    query = """
        UPDATE refresh_tokens 
        SET is_revoked = TRUE 
        WHERE token_hash = $1
    """
    token_hash = hash_password(token)
    async with db_pool.acquire() as conn:
        await conn.execute(query, token_hash)

# Auth dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        token_type: str = payload.get("type")
        
        if user_id is None or email is None or token_type != "access":
            raise credentials_exception
            
        token_data = TokenData(user_id=user_id, email=email)
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = await get_user_by_id(token_data.user_id)
    if user is None:
        raise credentials_exception
    
    if not user['is_active']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

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

# Auth endpoints
@app.post("/api/auth/register", response_model=UserResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    # Check if user already exists
    existing_user = await get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    try:
        user = await create_user(user_data)
        return UserResponse(
            id=user['id'],
            email=user['email'],
            first_name=user['first_name'],
            last_name=user['last_name'],
            is_active=user['is_active'],
            created_at=user['created_at']
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/api/auth/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Login user and return tokens"""
    # Get user
    user = await get_user_by_email(user_credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(user_credentials.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user['is_active']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user['id'], "email": user['email']},
        expires_delta=access_token_expires
    )
    
    refresh_token = create_refresh_token()
    await store_refresh_token(user['id'], refresh_token)
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    user_id = await verify_refresh_token(refresh_request.refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = await get_user_by_id(user_id)
    if not user or not user['is_active']:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Revoke old refresh token
    await revoke_refresh_token(refresh_request.refresh_token)
    
    # Create new tokens
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user['id'], "email": user['email']},
        expires_delta=access_token_expires
    )
    
    new_refresh_token = create_refresh_token()
    await store_refresh_token(user['id'], new_refresh_token)
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@app.post("/api/auth/logout")
async def logout(
    refresh_request: RefreshTokenRequest,
    current_user = Depends(get_current_user)
):
    """Logout user by revoking refresh token"""
    await revoke_refresh_token(refresh_request.refresh_token)
    return {"message": "Successfully logged out"}

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user['id'],
        email=current_user['email'],
        first_name=current_user['first_name'],
        last_name=current_user['last_name'],
        is_active=current_user['is_active'],
        created_at=current_user['created_at']
    )

@app.get("/api/auth/validate")
async def validate_token(current_user = Depends(get_current_user)):
    """Validate token and return user info (for other services)"""
    return {
        "valid": True,
        "user": {
            "id": current_user['id'],
            "email": current_user['email'],
            "first_name": current_user['first_name'],
            "last_name": current_user['last_name']
        }
    }

# Admin endpoints (for user management)
@app.get("/api/auth/users", response_model=List[UserResponse])
async def list_users(
    current_user = Depends(get_current_user),
    limit: int = 100,
    offset: int = 0
):
    """List all users (admin only - you can add role-based access later)"""
    query = """
        SELECT id, email, first_name, last_name, is_active, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """
    
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, limit, offset)
    
    return [
        UserResponse(
            id=row['id'],
            email=row['email'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            is_active=row['is_active'],
            created_at=row['created_at']
        )
        for row in rows
    ]

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)