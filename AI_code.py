from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
# ============================= This week's auth ====================================
import os
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client

# --- Supabase Setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-anon-key")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="FastAPI + Supabase Auth API")

# --- Security Scheme ---
# HTTPBearer automatically checks for an Authorization header with 'Bearer <token>'
security = HTTPBearer()


# --- Pydantic Schemas ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserSignup(BaseModel):
    email: EmailStr
    password: str


# --- Authentication Dependency (Middleware Check) ---
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Middleware dependency function to extract, check, and authenticate 
    the Bearer token against Supabase before letting users access protected routes.
    """
    # 1. Check if authorization credentials exist
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Check if the scheme explicitly starts with 'Bearer'
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Authorization header must start with 'Bearer '",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials

    # 3. Authenticate the token with Supabase
    try:
        # Calls Supabase auth API to verify the JWT token
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        return user_response.user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Public & Auth Endpoints ---

@app.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(credentials: UserSignup):
    """Sign up a new user with Supabase."""
    try:
        response = supabase.auth.sign_up({
            "email": credentials.email,
            "password": credentials.password
        })
        return {"message": "User created successfully", "user": response.user}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/login", status_code=status.HTTP_200_OK)
def login(credentials: UserLogin):
    """Log in an existing user and return access/refresh tokens."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        return {
            "message": "Login successful",
            "access_token": response.session.access_token,
            "token_type": "bearer",
            "user": response.user
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )


@app.post("/logout", status_code=status.HTTP_200_OK)
def logout(user: dict = Depends(get_current_user)):
    """Log out current session via Supabase."""
    try:
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Protected Routes ---

@app.get("/profile", status_code=status.HTTP_200_OK)
def get_profile(current_user: dict = Depends(get_current_user)):
    """Protected profile route welcoming the verified user."""
    return {
        "message": f"Welcome to your profile, {current_user.email}!",
        "user_id": current_user.id,
        "created_at": current_user.created_at,
        "user_metadata": current_user.user_metadata
    }


@app.get("/dashboard", status_code=status.HTTP_200_OK)
def get_dashboard(current_user: dict = Depends(get_current_user)):
    """Protected dashboard route."""
    return {
        "message": f"Welcome to your dashboard, {current_user.email}!",
        "stats": {
            "account_status": "Active",
            "last_sign_in": getattr(current_user, "last_sign_in_at", "N/A")
        }
    }





# ======================== Previous Code Snippet ========================
app = FastAPI(
    title="Task Management API",
    description="In-memory CRUD API built with FastAPI"
)

# In-Memory Database and Counter
tasks_db: Dict[int, dict] = {}
id_counter: int = 1


# --- Pydantic Data Schemas ---

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100, description="Title of the task")
    done: bool = Field(default=False, description="Completion status of the task")

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="New title")
    done: Optional[bool] = Field(None, description="Updated completion status")

class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool

class StatsResponse(BaseModel):
    total_tasks: int
    completed_tasks: int
    pending_tasks: int


# --- Root & Health Endpoints ---

@app.get("/", status_code=status.HTTP_200_OK)
def read_root():
    """Root endpoint detailing API info."""
    return {
        "name": "Task Management API",
        "version": "1.0.0",
        "description": "An in-memory RESTful CRUD API built with FastAPI.",
        "endpoints": [
            "GET /",
            "GET /health",
            "GET /tasks",
            "POST /tasks",
            "GET /tasks/search",
            "GET /tasks/stats",
            "GET /tasks/{task_id}",
            "PUT /tasks/{task_id}",
            "DELETE /tasks/{task_id}"
        ]
    }

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Health check endpoint to verify service status."""
    return {"status": "healthy", "database": "connected (in-memory)"}


# --- Additional Feature Endpoints ---

@app.get("/tasks/search", response_model=List[TaskResponse], status_code=status.HTTP_200_OK)
def search_tasks(keyword: str = Query(..., min_length=1, description="Word to match in title")):
    """Search tasks containing a keyword (case-insensitive)."""
    results = [
        task for task in tasks_db.values()
        if keyword.lower() in task["title"].lower()
    ]
    return results

@app.get("/tasks/stats", response_model=StatsResponse, status_code=status.HTTP_200_OK)
def get_task_stats():
    """Retrieve total count and completion statistics."""
    total = len(tasks_db)
    completed = sum(1 for task in tasks_db.values() if task["done"])
    pending = total - completed
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": pending
    }


# --- CRUD Endpoints ---

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task_data: TaskCreate):
    """Create a new task with auto-incremented ID."""
    global id_counter
    
    new_task = {
        "id": id_counter,
        "title": task_data.title,
        "done": task_data.done
    }
    tasks_db[id_counter] = new_task
    id_counter += 1
    
    return new_task

@app.get("/tasks", response_model=List[TaskResponse], status_code=status.HTTP_200_OK)
def read_all_tasks():
    """Get all tasks."""
    return list(tasks_db.values())

@app.get("/tasks/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def read_task_by_id(task_id: int):
    """Get a single task by ID."""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found."
        )
    return tasks_db[task_id]

@app.put("/tasks/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
def update_task(task_id: int, task_data: TaskUpdate):
    """Update title or completion status of an existing task."""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found."
        )
    
    task = tasks_db[task_id]
    if task_data.title is not None:
        task["title"] = task_data.title
    if task_data.done is not None:
        task["done"] = task_data.done
        
    return task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def delete_task(task_id: int):
    """Delete a task by ID."""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found."
        )
    deleted_task = tasks_db.pop(task_id)
    return {"message": f"Task '{deleted_task['title']}' deleted successfully."}