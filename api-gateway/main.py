# api-gateway/main.py
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx
import os
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Gateway",
    description="Simple API Gateway for microservices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
TODO_SERVICE_URL = os.getenv("TODO_SERVICE_URL", "http://todo-service:8000")

async def validate_token_and_get_user(token: str):
    """Validate token with auth service and return user info"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE_URL}/api/auth/me",  # ✅ fixed path
                headers={"Authorization": f"Bearer {token}"}
            )

            if response.status_code == 200:
                data = response.json()
                return data  # return full user info
            else:
                logger.warning(f"Token validation failed: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None

async def forward_request(
    request: Request,
    target_url: str,
    add_user_headers: bool = False
):
    """Forward request to target service"""
    
    # Prepare headers
    headers = dict(request.headers)
    headers.pop("host", None)  # Remove host header
    
    # Handle authentication for protected routes
    user = None
    if add_user_headers:
        auth_header = headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            user = await validate_token_and_get_user(token)
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            
            # Add user headers
            headers["X-User-ID"] = str(user["id"])
            headers["X-User-Email"] = user["email"]
            headers["X-User-Name"] = f"{user['first_name']} {user['last_name']}"
    
    # Get request body
    body = await request.body()
    
    # Forward request
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=f"{target_url}{request.url.path}",
                params=request.query_params,
                headers=headers,
                content=body,
                timeout=30.0
            )
            
            # Return response
            return StreamingResponse(
                iter([response.content]),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
            
    except httpx.RequestError as e:
        logger.error(f"Request forwarding error: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Health check
@app.get("/health")
async def health_check():
    """Health check for API Gateway"""
    return {"status": "healthy", "service": "api-gateway"}

# Auth service routes (public)
@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_auth(request: Request):
    """Proxy requests to auth service"""
    return await forward_request(request, AUTH_SERVICE_URL, add_user_headers=False)

# Todo service routes (protected)
@app.api_route("/api/todos{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_todo_protected(request: Request):
    """Proxy protected requests to todo service"""
    return await forward_request(request, TODO_SERVICE_URL, add_user_headers=True)

@app.api_route("/api/user{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_user_protected(request: Request):
    """Proxy protected user requests to todo service"""
    return await forward_request(request, TODO_SERVICE_URL, add_user_headers=True)

# Todo service health (public)
@app.get("/api/todo-health")
async def proxy_todo_health(request: Request):
    """Proxy health check to todo service"""
    return await forward_request(request, f"{TODO_SERVICE_URL}/health", add_user_headers=False)

# Catch-all for other routes
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request):
    """Catch-all route"""
    return {"error": "Route not found", "path": request.url.path}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)