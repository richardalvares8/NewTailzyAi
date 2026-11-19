from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
from google import genai
from google.genai import types

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

JWT_SECRET = os.environ.get('JWT_SECRET', 'tailzyai-secret-key-2025')

# Copilot chat: Google Gemini. Get a key at https://aistudio.google.com/apikey
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-flash-latest')
_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=503, detail="Copilot is not configured (GEMINI_API_KEY missing)")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client
JWT_ALGORITHM = "HS256"

# Models
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class PetCreate(BaseModel):
    name: str
    species: str
    breed: Optional[str] = None
    dob: Optional[str] = None
    photo_url: Optional[str] = None
    microchip_id: Optional[str] = None
    weight: Optional[str] = None
    allergies: Optional[str] = None
    health_conditions: Optional[str] = None

class Pet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    name: str
    species: str
    breed: Optional[str] = None
    dob: Optional[str] = None
    photo_url: Optional[str] = None
    microchip_id: Optional[str] = None
    weight: Optional[str] = None
    allergies: Optional[str] = None
    health_conditions: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: str

class ActivityCreate(BaseModel):
    pet_id: str
    type: str
    description: str
    date: str
    notes: Optional[str] = None

class Activity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    pet_id: str
    type: str
    description: str
    date: str
    notes: Optional[str] = None
    created_at: str

class HealthRecordCreate(BaseModel):
    pet_id: str
    type: str
    description: str
    date: str
    notes: Optional[str] = None

class HealthRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    pet_id: str
    type: str
    description: str
    date: str
    notes: Optional[str] = None
    created_at: str

class JournalCreate(BaseModel):
    pet_id: str
    content: str
    mood: Optional[str] = None
    date: str

class Journal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    pet_id: str
    content: str
    mood: Optional[str] = None
    date: str
    created_at: str

class ChatMessageCreate(BaseModel):
    message: str

class ChatMessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str

# Auth helper
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")

# Health check route
@api_router.get("/")
async def root():
    return {"message": "Tailzyai API is running", "status": "healthy"}

# Auth routes
@api_router.post("/auth/signup", response_model=TokenResponse)
async def signup(user: UserSignup):
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user_id = str(uuid.uuid4())
    
    user_doc = {
        "id": user_id,
        "email": user.email,
        "name": user.name,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=30)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    
    return TokenResponse(
        token=token,
        user=UserResponse(id=user_id, email=user.email, name=user.name)
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(user: UserLogin):
    user_doc = await db.users.find_one({"email": user.email})
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(user.password.encode('utf-8'), user_doc['password_hash'].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = jwt.encode(
        {"user_id": user_doc['id'], "exp": datetime.now(timezone.utc) + timedelta(days=30)},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )
    
    return TokenResponse(
        token=token,
        user=UserResponse(id=user_doc['id'], email=user_doc['email'], name=user_doc['name'])
    )

# Pet routes
@api_router.post("/pets", response_model=Pet)
async def create_pet(pet: PetCreate, current_user: dict = Depends(get_current_user)):
    pet_id = str(uuid.uuid4())
    pet_doc = {
        "id": pet_id,
        "user_id": current_user['id'],
        **pet.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.pets.insert_one(pet_doc)
    return Pet(**pet_doc)

@api_router.get("/pets", response_model=List[Pet])
async def get_pets(current_user: dict = Depends(get_current_user)):
    pets = await db.pets.find({"user_id": current_user['id']}, {"_id": 0}).to_list(100)
    return pets

@api_router.get("/pets/{pet_id}", response_model=Pet)
async def get_pet(pet_id: str, current_user: dict = Depends(get_current_user)):
    pet = await db.pets.find_one({"id": pet_id, "user_id": current_user['id']}, {"_id": 0})
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet

@api_router.put("/pets/{pet_id}", response_model=Pet)
async def update_pet(pet_id: str, pet: PetCreate, current_user: dict = Depends(get_current_user)):
    existing = await db.pets.find_one({"id": pet_id, "user_id": current_user['id']})
    if not existing:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    await db.pets.update_one(
        {"id": pet_id},
        {"$set": pet.model_dump()}
    )
    updated = await db.pets.find_one({"id": pet_id}, {"_id": 0})
    return Pet(**updated)

# Activity routes
@api_router.post("/activities", response_model=Activity)
async def create_activity(activity: ActivityCreate, current_user: dict = Depends(get_current_user)):
    pet = await db.pets.find_one({"id": activity.pet_id, "user_id": current_user['id']})
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    activity_id = str(uuid.uuid4())
    activity_doc = {
        "id": activity_id,
        **activity.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.activities.insert_one(activity_doc)
    return Activity(**activity_doc)

@api_router.get("/activities", response_model=List[Activity])
async def get_activities(pet_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if pet_id:
        pet = await db.pets.find_one({"id": pet_id, "user_id": current_user['id']})
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        query["pet_id"] = pet_id
    else:
        user_pets = await db.pets.find({"user_id": current_user['id']}, {"_id": 0, "id": 1}).to_list(100)
        pet_ids = [p['id'] for p in user_pets]
        query["pet_id"] = {"$in": pet_ids}
    
    activities = await db.activities.find(query, {"_id": 0}).sort("date", -1).to_list(100)
    return activities

# Health records routes
@api_router.post("/health-records", response_model=HealthRecord)
async def create_health_record(record: HealthRecordCreate, current_user: dict = Depends(get_current_user)):
    pet = await db.pets.find_one({"id": record.pet_id, "user_id": current_user['id']})
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    record_id = str(uuid.uuid4())
    record_doc = {
        "id": record_id,
        **record.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.health_records.insert_one(record_doc)
    return HealthRecord(**record_doc)

@api_router.get("/health-records", response_model=List[HealthRecord])
async def get_health_records(pet_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if pet_id:
        pet = await db.pets.find_one({"id": pet_id, "user_id": current_user['id']})
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        query["pet_id"] = pet_id
    else:
        user_pets = await db.pets.find({"user_id": current_user['id']}, {"_id": 0, "id": 1}).to_list(100)
        pet_ids = [p['id'] for p in user_pets]
        query["pet_id"] = {"$in": pet_ids}
    
    records = await db.health_records.find(query, {"_id": 0}).sort("date", -1).to_list(100)
    return records

# Journal routes
@api_router.post("/journal", response_model=Journal)
async def create_journal(entry: JournalCreate, current_user: dict = Depends(get_current_user)):
    pet = await db.pets.find_one({"id": entry.pet_id, "user_id": current_user['id']})
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    
    journal_id = str(uuid.uuid4())
    journal_doc = {
        "id": journal_id,
        **entry.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.journal.insert_one(journal_doc)
    return Journal(**journal_doc)

@api_router.get("/journal", response_model=List[Journal])
async def get_journal(pet_id: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    query = {}
    if pet_id:
        pet = await db.pets.find_one({"id": pet_id, "user_id": current_user['id']})
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        query["pet_id"] = pet_id
    else:
        user_pets = await db.pets.find({"user_id": current_user['id']}, {"_id": 0, "id": 1}).to_list(100)
        pet_ids = [p['id'] for p in user_pets]
        query["pet_id"] = {"$in": pet_ids}
    
    entries = await db.journal.find(query, {"_id": 0}).sort("date", -1).to_list(100)
    return entries

# Chat routes
@api_router.post("/chat/message", response_model=ChatMessageResponse)
async def send_chat_message(msg: ChatMessageCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    user_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Get user's pets and their data for context
    pets = await db.pets.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    activities = await db.activities.find({"pet_id": {"$in": [p['id'] for p in pets]}}, {"_id": 0}).sort("date", -1).limit(20).to_list(20)
    health_records = await db.health_records.find({"pet_id": {"$in": [p['id'] for p in pets]}}, {"_id": 0}).sort("date", -1).limit(10).to_list(10)
    journal_entries = await db.journal.find({"pet_id": {"$in": [p['id'] for p in pets]}}, {"_id": 0}).sort("date", -1).limit(10).to_list(10)
    
    context = f"""You are Tailzyai's pet care copilot. You have access to the user's pet data:

Pets: {pets}

Recent Activities: {activities}

Health Records: {health_records}

Journal Entries: {journal_entries}

Provide helpful, caring advice about their pets based on this data. Be warm, friendly, and knowledgeable about pet care."""
    
    # Previous turns so the copilot remembers the conversation
    history = await db.chat_messages.find(
        {"user_id": user_id}, {"_id": 0, "role": 1, "content": 1}
    ).sort("timestamp", -1).limit(20).to_list(20)
    contents = [
        types.Content(
            role="model" if m["role"] == "assistant" else "user",
            parts=[types.Part(text=m["content"])],
        )
        for m in reversed(history)
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=msg.message)]))

    try:
        result = await get_gemini_client().aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=context),
        )
        response_text = result.text or "Sorry, I couldn't come up with an answer. Please try again."
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger(__name__).exception("Gemini request failed")
        raise HTTPException(status_code=502, detail="Copilot is unavailable right now. Please try again.") from e
    
    # Save messages to database
    message_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    user_msg_doc = {
        "id": message_id,
        "user_id": user_id,
        "role": "user",
        "content": msg.message,
        "timestamp": user_timestamp
    }
    await db.chat_messages.insert_one(user_msg_doc)
    
    ai_msg_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "role": "assistant",
        "content": response_text,
        "timestamp": timestamp
    }
    await db.chat_messages.insert_one(ai_msg_doc)
    
    return ChatMessageResponse(
        role="assistant",
        content=response_text,
        timestamp=timestamp
    )

@api_router.get("/chat/history", response_model=List[ChatMessageResponse])
async def get_chat_history(current_user: dict = Depends(get_current_user)):
    messages = await db.chat_messages.find(
        {"user_id": current_user['id']},
        {"_id": 0, "role": 1, "content": 1, "timestamp": 1}
    ).sort("timestamp", 1).limit(50).to_list(50)
    return messages

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()