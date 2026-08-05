
from fastapi import Depends, FastAPI, HTTPException 
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if SUPABASE_URL is None or SUPABASE_KEY is None:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)


load_dotenv()

class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length= 1)

class TaskCreate(BaseModel):
  title: str = Field(..., min_length=1)

class TaskUpdate(BaseModel):
  title: Optional[str] = Field(None, min_length=1)
  done: Optional[bool] = None

app = FastAPI()


engine = create_engine("sqlite:///tasks.db", connect_args={"check_same_thread":False})
sessionlocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    done = Column(Boolean, nullable=False)

Base.metadata.create_all(engine)


def init_db():
    if not os.path.exists("tasks.db"):
        Base.metadata.create_all(bind=engine)

    db = sessionlocal()
    try:
        task_count = db.query(Task).count()
        if task_count == 0:
            example_tasks = [
                Task(title="Buy groceries", done=False),
                Task(title="Clean the house", done=True),
                Task(title="Finish the project", done=False),
            ]
            for task in example_tasks:
                db.add(task)
            db.commit()
    finally:
        db.close()

def get_db():
    
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()

init_db()


@app.get("/")
def root():
    return {
        "name": "Task API"
    }

@app.get("/health")
def health():
    return {"status": "OK"}

@app.get("/tasks")
def read(db: Session = Depends(get_db)):
    return db.query(Task).all()

@app.post("/auth/signup")
def signup(user: UserAuth):
    try:
        response = supabase_client.auth.sign_up({
            "email": user.email,
            "password": user.password
        })

        if response.user:
            return {"status_code": 201, "user": {"id": response.user.id, "email": response.user.email}}

    except Exception as e:
        if not user.email or not user.password:
            return {"error": "Email and password are required", "status_code": 400}
        return {"error": str(e), "status_code": 400}

@app.post("/auth/login")
def login(user: UserAuth):
    try:
        response = supabase_client.auth.sign_in_with_password({
              "email": user.email,
             "password": user.password
        })
        if response.session:
            return {"message": "Welcome back", 
                    "access_token" : response.session.access_token }
        else:
            return {"error": "Wrong email or password"}
            
    except Exception as e:
        return {"error": f" Login failed: {str(e)}"}    


@app.get("/tasks/search")
def search_with_words(search: str, db: Session = Depends(get_db)):
    result = db.query(Task).filter(Task.title.ilike(f"%{search}%")).all()
    return result

@app.post("/tasks", status_code=201)
def create(task: TaskCreate, db: Session = Depends(get_db)):

    new_task = Task(title=task.title, done=False) # passing the parameters to the task class
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task



@app.get("/tasks/{id}")
def search_with_id(id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{id}")
def update(id: int, task: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task does not exist")
    for field, value  in task.dict(exclude_unset=True).items():
        setattr(db_task, field, value)

    db.commit()
    db.refresh(db_task)
    return db_task


@app.delete("/tasks/{id}", status_code=204)
def delete(id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task does not exist")
    db.delete(db_task)
    db.commit()
    return {}

@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    total_count = db.query(Task).count()
    print(total_count)
    completed_count = db.query(Task).where(Task.done == True).count()
    non_completed_count = total_count - completed_count
    return {
        "total_count": total_count,
        "completed_count": completed_count,
        "non_completed_count": non_completed_count,
    }

