```python
import os
import asyncio
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import boto3
from minio import Minio
from minio.commonconfig import Tags
import aiohttp
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from dotenv import load_dotenv
import uuid
import json

load_dotenv()

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS SNS
sns_client = boto3.client(
    'sns',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

# Database
DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
pool = None

# MinIO
minio_client = Minio(
    os.getenv('MINIO_ENDPOINT'),
    access_key=os.getenv('MINIO_ACCESS_KEY'),
    secret_key=os.getenv('MINIO_SECRET_KEY'),
    secure=False
)

# Redis
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=int(os.getenv('REDIS_PORT')),
    db=int(os.getenv('REDIS_DB')),
    decode_responses=True
)

# JWT
SECRET_KEY = os.getenv('JWT_SECRET')
ALGORITHM = os.getenv('JWT_ALGORITHM')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# AI Process
AI_PROCESS_URL = os.getenv('AI_PROCESS_URL')

# Models
class UserCreate(BaseModel):
    username: str
    password: str
    role: str

class EventCreate(BaseModel):
    name: str

# Database connection
async def get_db():
    async with pool.acquire() as conn:
        yield conn

# JWT functions
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user

async def verify_admin(token: str = Depends(oauth2_scheme)):
    user = await get_current_user(token)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# Logging function with SNS notification
async def log_action(conn, user_id: str, action: str, details: dict, notify: bool = False):
    log_id = str(uuid.uuid4())
    details_json = json.dumps(details, default=str)  # Convert UUID to string
    await conn.execute(
        "INSERT INTO logs (log_id, user_id, action, details, notification_sent) VALUES ($1, $2, $3, $4, $5)",
        log_id, user_id, action, details_json, notify
    )
    if notify:
        try:
            # Convert user_id to string for JSON serialization
            sns_message = {
                'log_id': log_id,
                'user_id': str(user_id) if user_id else None,
                'action': action,
                'details': details,
                'timestamp': datetime.utcnow().isoformat()
            }
            sns_client.publish(
                TopicArn=os.getenv('AWS_SNS_TOPIC_ARN'),
                Message=json.dumps(sns_message, default=str),
                Subject=f"Image System Alert: {action}"
            )
            await conn.execute(
                "UPDATE logs SET notification_sent = TRUE WHERE log_id = $1",
                log_id
            )
        except Exception as e:
            logger.error(f"Failed to send SNS notification: {str(e)}")
            await conn.execute(
                "INSERT INTO logs (log_id, user_id, action, details, notification_sent) VALUES ($1, $2, $3, $4, $5)",
                str(uuid.uuid4()), None, "sns_notification_error", json.dumps({"error": str(e)}, default=str), False
            )

# Startup
@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    if not minio_client.bucket_exists("event-default"):
        minio_client.make_bucket("event-default")

# Login
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    async with pool.acquire() as conn:
        try:
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            if not user or not pwd_context.verify(password, user['password_hash']):
                await log_action(conn, None, "login_failed", {"username": username, "error": "Invalid credentials"}, notify=True)
                raise HTTPException(status_code=401, detail="Invalid credentials")
            access_token = jwt.encode(
                {"sub": username, "exp": datetime.utcnow() + timedelta(hours=1)},
                SECRET_KEY,
                algorithm=ALGORITHM
            )
            await log_action(conn, str(user['user_id']), "login_success", {"username": username}, notify=True)
            return {"access_token": access_token, "token_type": "bearer"}
        except Exception as e:
            await log_action(conn, None, "login_error", {"username": username, "error": str(e)}, notify=True)
            raise HTTPException(status_code=500, detail=str(e))

# Admin Dashboard
@app.get("/admin/dashboard")
async def get_dashboard(current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        image_counts = await conn.fetch("SELECT event_id, COUNT(*) as image_count FROM images GROUP BY event_id")
        user_counts = await conn.fetch("SELECT role, COUNT(*) as user_count FROM users GROUP BY role")
        recent_uploads = await conn.fetch(
            "SELECT event_id, COUNT(*) as upload_count FROM images WHERE timestamp > NOW() - INTERVAL '24 hours' GROUP BY event_id"
        )
        events = await conn.fetch(
            "SELECT e.event_id, e.name, e.created_by, e.created_at, u.username as created_by_username "
            "FROM events e JOIN users u ON e.created_by = u.user_id ORDER BY e.created_at DESC LIMIT 5"
        )
        dashboard_data = {
            "image_counts": [{"event_id": str(row['event_id']), "image_count": row['image_count']} for row in image_counts],
            "user_counts": [{"role": row['role'], "user_count": row['user_count']} for row in user_counts],
            "recent_uploads": [{"event_id": str(row['event_id']), "upload_count": row['upload_count']} for row in recent_uploads],
            "events": [{"event_id": str(row['event_id']), "name": row['name'], "created_by": str(row['created_by']), "created_at": row['created_at'].isoformat(), "created_by_username": row['created_by_username']} for row in events]
        }
        cache_key = f"dashboard_{current_user['user_id']}"
        await redis_client.setex(cache_key, 300, json.dumps(dashboard_data, default=str))
        await log_action(conn, str(current_user['user_id']), "view_dashboard", {"user": current_user['username']})
        return dashboard_data

# Users
@app.get("/users")
async def get_users(current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id, username, role, created_at FROM users")
        await log_action(conn, str(current_user['user_id']), "list_users", {"user_count": len(users)})
        return [{"user_id": str(row['user_id']), "username": row['username'], "role": row['role'], "created_at": row['created_at'].isoformat()} for row in users]

@app.post("/users")
async def create_user(user: UserCreate, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            password_hash = pwd_context.hash(user.password)
            user_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO users (user_id, username, password_hash, role) VALUES ($1, $2, $3, $4)",
                user_id, user.username, password_hash, user.role
            )
            await log_action(conn, str(current_user['user_id']), "create_user", {"username": user.username, "role": user.role}, notify=True)
            return {"message": "User created"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "create_user_failed", {"username": user.username, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.put("/users/{user_id}/role")
async def update_user_role(user_id: str, role: str, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            await conn.execute("UPDATE users SET role = $1 WHERE user_id = $2", role, user_id)
            await log_action(conn, str(current_user['user_id']), "update_user_role", {"user_id": user_id, "new_role": role}, notify=True)
            return {"message": "Role updated"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "update_user_role_failed", {"user_id": user_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
            await log_action(conn, str(current_user['user_id']), "delete_user", {"user_id": user_id}, notify=True)
            return {"message": "User deleted"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "delete_user_failed", {"user_id": user_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

# Events
@app.get("/events")
async def get_events(current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        events = await conn.fetch("SELECT * FROM events")
        await log_action(conn, str(current_user['user_id']), "list_events", {"event_count": len(events)})
        return [{"event_id": str(row['event_id']), "name": row['name'], "created_by": str(row['created_by']), "created_at": row['created_at'].isoformat()} for row in events]

@app.post("/events")
async def create_event(event: EventCreate, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            event_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO events (event_id, name, created_by) VALUES ($1, $2, $3)",
                event_id, event.name, current_user['user_id']
            )
            bucket_name = f"event-{event_id}"
            if not minio_client.bucket_exists(bucket_name):
                minio_client.make_bucket(bucket_name)
            await log_action(conn, str(current_user['user_id']), "create_event", {"event_id": event_id, "name": event.name}, notify=True)
            return {"message": "Event created"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "create_event_failed", {"name": event.name, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.delete("/events/{event_id}")
async def delete_event(event_id: str, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            await conn.execute("DELETE FROM images WHERE event_id = $1", event_id)
            await conn.execute("DELETE FROM faces WHERE event_id = $1", event_id)
            await conn.execute("DELETE FROM events WHERE event_id = $1", event_id)
            bucket_name = f"event-{event_id}"
            if minio_client.bucket_exists(bucket_name):
                objects = minio_client.list_objects(bucket_name, recursive=True)
                for obj in objects:
                    minio_client.remove_object(bucket_name, obj.object_name)
                minio_client.remove_bucket(bucket_name)
            await log_action(conn, str(current_user['user_id']), "delete_event", {"event_id": event_id}, notify=True)
            return {"message": "Event deleted"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "delete_event_failed", {"event_id": event_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

# Images
@app.post("/upload")
async def upload_image(file: UploadFile = File(...), event_id: str = Form(...), consent_given: bool = Form(...), current_user: dict = Depends(get_current_user)):
    async with pool.acquire() as conn:
        try:
            image_id = str(uuid.uuid4())
            bucket_name = f"event-{event_id}"
            if not minio_client.bucket_exists(bucket_name):
                await log_action(conn, str(current_user['user_id']), "upload_image_failed", {"event_id": event_id, "error": "Bucket not found"}, notify=True)
                raise HTTPException(status_code=400, detail="Bucket not found")
            file_content = await file.read()
            tags = Tags()
            tags["consent"] = "true" if consent_given else "false"
            minio_client.put_object(
                bucket_name,
                file.filename,
                file_content,
                len(file_content),
                content_type=file.content_type,
                tags=tags
            )
            consent_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO consents (consent_id, user_id, image_id, consent_given) VALUES ($1, $2, $3, $4)",
                consent_id, current_user['user_id'], image_id, consent_given
            )
            await conn.execute(
                "INSERT INTO images (id, event_id, filename, uploaded_by, consent_given) VALUES ($1, $2, $3, $4, $5)",
                image_id, event_id, file.filename, current_user['user_id'], consent_given
            )
            await log_action(conn, str(current_user['user_id']), "upload_image", {"image_id": image_id, "event_id": event_id, "filename": file.filename}, notify=True)
            return {"message": "Image uploaded"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "upload_image_failed", {"event_id": event_id, "filename": file.filename, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.get("/images")
async def get_images(event_id: str, page: int = 1, limit: int = 10, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            offset = (page - 1) * limit
            images = await conn.fetch(
                "SELECT id, event_id, filename, thumbnail_url, uploaded_by, consent_given, timestamp FROM images WHERE event_id = $1 ORDER BY timestamp DESC LIMIT $2 OFFSET $3",
                event_id, limit, offset
            )
            await log_action(conn, str(current_user['user_id']), "list_images", {"event_id": event_id, "image_count": len(images)})
            return {"images": [{"id": str(row['id']), "event_id": str(row['event_id']), "filename": row['filename'], "thumbnail_url": row['thumbnail_url'], "uploaded_by": str(row['uploaded_by']), "consent_given": row['consent_given'], "timestamp": row['timestamp'].isoformat()} for row in images]}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "list_images_failed", {"event_id": event_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.delete("/images/{event_id}/{image_id}")
async def delete_image(event_id: str, image_id: str, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            image = await conn.fetchrow("SELECT filename FROM images WHERE id = $1 AND event_id = $2", image_id, event_id)
            if not image:
                await log_action(conn, str(current_user['user_id']), "delete_image_failed", {"image_id": image_id, "event_id": event_id, "error": "Image not found"}, notify=True)
                raise HTTPException(status_code=404, detail="Image not found")
            bucket_name = f"event-{event_id}"
            minio_client.remove_object(bucket_name, image['filename'])
            await conn.execute("DELETE FROM faces WHERE image_id = $1", image_id)
            await conn.execute("DELETE FROM consents WHERE image_id = $1", image_id)
            await conn.execute("DELETE FROM images WHERE id = $1", image_id)
            await log_action(conn, str(current_user['user_id']), "delete_image", {"image_id": image_id, "event_id": event_id}, notify=True)
            return {"message": "Image deleted"}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "delete_image_failed", {"image_id": image_id, "event_id": event_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

@app.post("/search_face")
async def search_face(file: UploadFile = File(...), event_id: str = Form(...), current_user: dict = Depends(get_current_user)):
    async with pool.acquire() as conn:
        try:
            file_content = await file.read()
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field('file', file_content, filename=file.filename)
                async with session.post(AI_PROCESS_URL, data=form) as response:
                    if response.status != 200:
                        await log_action(conn, str(current_user['user_id']), "search_face_failed", {"event_id": event_id, "error": await response.text()}, notify=True)
                        raise HTTPException(status_code=response.status, detail=await response.text())
                    face_data = await response.json()
            embedding = face_data['embedding']
            results = await conn.fetch(
                "SELECT image_id, filename, thumbnail_url, uploaded_by FROM images WHERE event_id = $1 "
                "AND id IN (SELECT image_id FROM faces WHERE 1 - (face_embedding <=> $2) > 0.6)",
                event_id, embedding
            )
            await log_action(conn, str(current_user['user_id']), "search_face", {"event_id": event_id, "result_count": len(results)})
            return {"results": [{"image_id": str(row['image_id']), "filename": row['filename'], "thumbnail_url": row['thumbnail_url'], "uploaded_by": str(row['uploaded_by'])} for row in results]}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "search_face_failed", {"event_id": event_id, "error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))

# Logs
@app.get("/logs")
async def get_logs(page: int = 1, limit: int = 10, action: str = None, user_id: str = None, current_user: dict = Depends(verify_admin)):
    async with pool.acquire() as conn:
        try:
            query = "SELECT * FROM logs"
            params = []
            conditions = []
            if action:
                conditions.append("action LIKE $1")
                params.append(f"%{action}%")
            if user_id:
                conditions.append("user_id = $2")
                params.append(user_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC LIMIT $3 OFFSET $4"
            params.extend([limit, (page - 1) * limit])
            logs = await conn.fetch(query, *params)
            await log_action(conn, str(current_user['user_id']), "list_logs", {"log_count": len(logs)})
            return {"logs": [{"log_id": str(row['log_id']), "user_id": str(row['user_id']) if row['user_id'] else None, "action": row['action'], "details": row['details'], "timestamp": row['timestamp'].isoformat(), "notification_sent": row['notification_sent']} for row in logs]}
        except Exception as e:
            await log_action(conn, str(current_user['user_id']), "list_logs_failed", {"error": str(e)}, notify=True)
            raise HTTPException(status_code=400, detail=str(e))
```
