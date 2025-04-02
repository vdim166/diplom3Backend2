from fastapi import FastAPI, Depends, HTTPException, status, Body, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from FileDatabase import FileDatabase
from TaskDB import TaskDB, Task, TaskCreate, TaskUpdate, TaskMove
from typing import List, Optional, Dict
from StorageDB import StorageDB, Item, Storage, ItemCreate, ItemUpdate

# Database setup


# Initialize database
db = FileDatabase("database.json")
task_db = TaskDB()

storage_db = StorageDB()
# storage_db.init_storages()

# JWT settings
SECRET_KEY = "my-secret-key"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Models
class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str):
    return pwd_context.hash(password)

def get_user(username: str):
    user_data = db.get_user(username)
    if user_data:
        return UserInDB(**user_data)
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Routes
@app.post("/token", response_model=Token)
async def login_for_access_token(login_data: LoginRequest = Body(...)):
    user = authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register")
async def register_user(
    username: str = Body(...),
    password: str = Body(...),
    email: Optional[str] = Body(None),
    full_name: Optional[str] = Body(None)
):
    if db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(password)
    user_data = {
        "username": username,
        "email": email,
        "full_name": full_name,
        "hashed_password": hashed_password,
        "disabled": False,
    }
    db.create_user(user_data)
    return {"message": "User registered successfully"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/validate-token")
async def validate_token(authorization: str = Header(...)):
    try:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
        
        token = authorization.split(" ")[1]
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"verify_exp": False}
        )
        
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
            
        user = get_user(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
            
        return {
            "is_valid": True,
            "user": {
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            }
        }
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )

@app.post("/tasks/", response_model=Task)
async def create_task(task_data: TaskCreate = Body(...)):
    return task_db.create_task(task_data)

@app.get("/tasks/", response_model=Dict[str, Dict[str, List[Task]]])
async def get_all_tasks():
    return task_db.get_all_tasks()

@app.get("/tasks/{user}", response_model=Dict[str, List[Task]])
async def get_user_tasks(user: str):
    return task_db.get_user_tasks(user)

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: str, 
    update_data: TaskUpdate = Body(...)
):
    task = task_db.update_task(task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/tasks/{task_id}/move", response_model=Task)
async def move_task(
    task_id: str,
    move_data: TaskMove = Body(...)
):
    update_data = TaskUpdate(
        status=move_data.new_status,
        assigned_to=move_data.new_assignee
    )
    task = task_db.update_task(task_id, update_data)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/tasks/{task_id}", response_model=Dict[str, str])
async def delete_task(task_id: str):
    if not task_db.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}


@app.post("/storages/{storage_id}/items", response_model=Item)
async def add_item(storage_id: str, item_data: ItemCreate = Body(...)):
    try:
        return storage_db.add_item(storage_id, item_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/items", response_model=List[Item])
async def get_items(storage_id: Optional[str] = None):
    return storage_db.get_items(storage_id)

@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: str, update_data: ItemUpdate = Body(...)):
    item = storage_db.update_item(item_id, update_data)
    if not item:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return item

@app.delete("/items/{item_id}")
async def delete_item(item_id: str):
    if not storage_db.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Товар не найден")
    return {"message": "Товар удален"}

@app.get("/storages", response_model=Dict[str, Storage])
async def get_storages():
    return storage_db.storages


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)