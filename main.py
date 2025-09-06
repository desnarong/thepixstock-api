# ============================================================================
# IMPORTS
# ============================================================================
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
from dotenv import load_dotenv, find_dotenv
import uuid
import json
import pathlib


# ============================================================================
# ENVIRONMENT VARIABLES LOADING
# ============================================================================
def load_environment():
    """
    Load environment variables with debugging support.
    Tries multiple locations for .env file.
    
    Returns:
        tuple: (env_loaded: bool, env_path: str)
    """
    possible_paths = [
        '.env',
        '../.env', 
        './backend/.env',
        os.path.join(os.path.dirname(__file__), '.env'),
        os.path.join(os.path.dirname(__file__), '../.env')
    ]
    
    env_loaded = False
    env_path = None
    
    # Try find_dotenv first (automatic detection)
    found_env = find_dotenv()
    if found_env:
        env_loaded = load_dotenv(found_env)
        env_path = found_env
        print(f"Found .env using find_dotenv(): {found_env}")
    
    # If not found, try manual paths
    if not env_loaded:
        for path in possible_paths:
            if pathlib.Path(path).exists():
                env_loaded = load_dotenv(path)
                env_path = path
                print(f"Loaded .env from: {pathlib.Path(path).absolute()}")
                break
    
    if not env_loaded:
        print("WARNING: No .env file found or loaded!")
        print("Current working directory:", os.getcwd())
        print("Script directory:", os.path.dirname(__file__))
    
    return env_loaded, env_path


# Load environment variables at startup
env_loaded, env_file_path = load_environment()


# ============================================================================
# APP INITIALIZATION
# ============================================================================
app = FastAPI(
    title="Image Management System",
    description="FastAPI application for image management with face recognition",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log environment loading status
logger.info(f"Environment file loaded: {env_loaded}")
if env_file_path:
    logger.info(f"Environment file path: {env_file_path}")


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
def get_database_config():
    """
    Get database configuration from environment variables.
    
    Returns:
        dict: Database configuration dictionary
    """
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
        'database': os.getenv('POSTGRES_DB', 'postgres')
    }
    
    # Log configuration (hide password)
    safe_config = config.copy()
    safe_config['password'] = '***' if config['password'] else 'NOT SET'
    logger.info(f"Database config: {safe_config}")
    
    return config


db_config = get_database_config()
DATABASE_URL = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
pool = None


async def test_database_connection():
    """
    Test database connection before creating pool.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        logger.info(f"Testing connection to {db_config['host']}:{db_config['port']}")
        conn = await asyncpg.connect(DATABASE_URL)
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        logger.info(f"Database connection successful. Version: {version[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        logger.error(f"Attempted to connect to: {db_config['host']}:{db_config['port']}")
        logger.error(f"Database: {db_config['database']}, User: {db_config['user']}")
        return False


async def get_db():
    """
    Database dependency for FastAPI routes.
    
    Yields:
        asyncpg.Connection: Database connection from pool
    """
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
    async with pool.acquire() as conn:
        yield conn


# ============================================================================
# REDIS CONFIGURATION
# ============================================================================
def get_redis_config():
    """
    Get Redis configuration from environment variables.
    
    Returns:
        dict: Redis configuration dictionary
    """
    config = {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', '6379')),
        'db': int(os.getenv('REDIS_DB', '0'))
    }
    logger.info(f"Redis config: {config}")
    return config


redis_config = get_redis_config()

try:
    redis_client = redis.Redis(
        host=redis_config['host'],
        port=redis_config['port'],
        db=redis_config['db'],
        decode_responses=True
    )
    logger.info("Redis client initialized successfully")
except Exception as e:
    logger.warning(f"Redis client initialization failed: {str(e)}")
    redis_client = None


# ============================================================================
# MINIO CONFIGURATION
# ============================================================================
def get_minio_config():
    """
    Get MinIO configuration from environment variables.
    
    Returns:
        dict: MinIO configuration dictionary
    """
    config = {
        'endpoint': os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
        'access_key': os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
        'secret_key': os.getenv('MINIO_SECRET_KEY', 'miniosecret')
    }
    safe_config = config.copy()
    safe_config['secret_key'] = '***' if config['secret_key'] else 'NOT SET'
    logger.info(f"MinIO config: {safe_config}")
    return config


minio_config = get_minio_config()

try:
    minio_client = Minio(
        minio_config['endpoint'],
        access_key=minio_config['access_key'],
        secret_key=minio_config['secret_key'],
        secure=False
    )
    logger.info("MinIO client initialized successfully")
except Exception as e:
    logger.warning(f"MinIO client initialization failed: {str(e)}")
    minio_client = None


# ============================================================================
# AWS SNS CONFIGURATION
# ============================================================================
def get_aws_config():
    """
    Get AWS configuration from environment variables.
    
    Returns:
        dict: AWS configuration dictionary
    """
    config = {
        'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'region': os.getenv('AWS_REGION', 'ap-southeast-1'),
        'topic_arn': os.getenv('AWS_SNS_TOPIC_ARN')
    }
    safe_config = config.copy()
    safe_config['secret_access_key'] = '***' if config['secret_access_key'] else 'NOT SET'
    logger.info(f"AWS config: {safe_config}")
    return config


aws_config = get_aws_config()

try:
    if aws_config['access_key_id'] and aws_config['secret_access_key']:
        sns_client = boto3.client(
            'sns',
            aws_access_key_id=aws_config['access_key_id'],
            aws_secret_access_key=aws_config['secret_access_key'],
            region_name=aws_config['region']
        )
        logger.info("AWS SNS client initialized successfully")
    else:
        logger.warning("AWS credentials not provided, SNS disabled")
        sns_client = None
except Exception as e:
    logger.warning(f"AWS SNS client initialization failed: {str(e)}")
    sns_client = None


# ============================================================================
# JWT CONFIGURATION
# ============================================================================
SECRET_KEY = os.getenv('JWT_SECRET', 'default-secret-change-this')
ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Warn if using default secret
if SECRET_KEY == 'default-secret-change-this':
    logger.warning("Using default JWT secret! Change JWT_SECRET in .env file for production")


# ============================================================================
# AI PROCESS CONFIGURATION
# ============================================================================
AI_PROCESS_URL = os.getenv('AI_PROCESS_URL', 'http://localhost:8001/process_face')
logger.info(f"AI Process URL: {AI_PROCESS_URL}")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================
class UserCreate(BaseModel):
    """Model for creating new users"""
    username: str
    password: str
    role: str


class EventCreate(BaseModel):
    """Model for creating new events"""
    name: str


# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
async def log_action(conn, user_id: str, action: str, details: dict, notify: bool = False):
    """
    Log user actions to database and optionally send SNS notification.
    
    Args:
        conn: Database connection
        user_id: User ID performing the action
        action: Action name/type
        details: Action details as dictionary
        notify: Whether to send SNS notification
    """
    log_id = str(uuid.uuid4())
    details_json = json.dumps(details, default=str)
    user_id_str = str(user_id) if user_id else None
    
    try:
        await conn.execute(
            "INSERT INTO logs (log_id, user_id, action, details, notification_sent) VALUES ($1, $2, $3, $4, $5)",
            log_id, user_id_str, action, details_json, notify
        )
        
        if notify and sns_client and aws_config['topic_arn']:
            try:
                sns_client.publish(
                    TopicArn=aws_config['topic_arn'],
                    Message=json.dumps({
                        'log_id': log_id,
                        'user_id': user_id_str,
                        'action': action,
                        'details': details,
                        'timestamp': datetime.utcnow().isoformat()
                    }, default=str),
                    Subject=f"Image System Alert: {action}"
                )
                await conn.execute(
                    "UPDATE logs SET notification_sent = TRUE WHERE log_id = $1",
                    log_id
                )
                logger.info(f"SNS notification sent for action: {action}")
            except Exception as e:
                logger.error(f"Failed to send SNS notification: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to log action: {str(e)}")
        # Don't raise exception for logging failures


# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Get current authenticated user from JWT token.
    
    Args:
        token: JWT token from Authorization header
    
    Returns:
        dict: User record from database
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
        
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user


async def verify_admin(token: str = Depends(oauth2_scheme)):
    """
    Verify user has admin role.
    
    Args:
        token: JWT token from Authorization header
    
    Returns:
        dict: Admin user record from database
    """
    user = await get_current_user(token)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ============================================================================
# APPLICATION EVENTS
# ============================================================================
@app.on_event("startup")
async def startup():
    """
    Initialize application components during startup.
    Sets up database pool and MinIO buckets.
    """
    global pool
    
    logger.info("Starting application initialization...")
    
    # Test database connection first
    if not await test_database_connection():
        logger.error("Database connection failed during startup")
        logger.error("Please check:")
        logger.error("1. PostgreSQL server is running")
        logger.error("2. Database credentials in .env file are correct")
        logger.error("3. Database host is accessible")
        
    try:
        # Create database connection pool
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60
        )
        logger.info("Database connection pool created successfully")
        
        # Test pool connection
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT version()")
            logger.info("Database pool test successful")
            
    except Exception as e:
        logger.error(f"Failed to create database pool: {str(e)}")
        logger.error("Database operations will be unavailable")
        pool = None
    
    # Initialize MinIO bucket if client is available
    if minio_client:
        try:
            if not minio_client.bucket_exists("event-default"):
                minio_client.make_bucket("event-default")
                logger.info("Created default MinIO bucket")
            else:
                logger.info("Default MinIO bucket already exists")
        except Exception as e:
            logger.warning(f"Failed to check/create MinIO bucket: {str(e)}")
    
    logger.info("Application startup completed")


@app.on_event("shutdown")
async def shutdown():
    """
    Clean up resources during application shutdown.
    """
    global pool
    
    logger.info("Shutting down application...")
    
    if pool:
        await pool.close()
        logger.info("Database pool closed")
    
    if redis_client:
        await redis_client.close()
        logger.info("Redis client closed")
    
    logger.info("Application shutdown completed")


# ============================================================================
# SYSTEM ENDPOINTS
# ============================================================================
@app.get("/")
async def root():
    """
    Root endpoint for basic connectivity test.
    
    Returns:
        dict: Basic application information
    """
    return {
        "message": "Image Management System API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify service status.
    
    Returns:
        dict: Status of all application components
    """
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "disconnected",
        "redis": "disconnected",
        "minio": "disconnected",
        "aws_sns": "disabled" if not sns_client else "enabled"
    }
    
    # Check database
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            status["database"] = "connected"
        except Exception as e:
            status["database"] = f"error: {str(e)}"
    
    # Check Redis
    if redis_client:
        try:
            await redis_client.ping()
            status["redis"] = "connected"
        except Exception as e:
            status["redis"] = f"error: {str(e)}"
    
    # Check MinIO
    if minio_client:
        try:
            minio_client.list_buckets()
            status["minio"] = "connected"
        except Exception as e:
            status["minio"] = f"error: {str(e)}"
    
    return status


@app.get("/config")
async def config_check():
    """
    Check configuration status of all components.
    
    Returns:
        dict: Configuration status and values
    """
    config_status = {
        "env_file_loaded": env_loaded,
        "env_file_path": env_file_path,
        "database": {
            "host": db_config['host'],
            "port": db_config['port'],
            "database": db_config['database'],
            "user": db_config['user'],
            "password_set": bool(db_config['password'])
        },
        "redis": redis_config,
        "minio": {
            "endpoint": minio_config['endpoint'],
            "access_key": minio_config['access_key'],
            "secret_key_set": bool(minio_config['secret_key'])
        },
        "aws": {
            "region": aws_config['region'],
            "access_key_set": bool(aws_config['access_key_id']),
            "secret_key_set": bool(aws_config['secret_access_key']),
            "topic_arn": aws_config['topic_arn']
        },
        "ai_process_url": AI_PROCESS_URL,
        "jwt_secret_set": bool(SECRET_KEY != 'default-secret-change-this')
    }
    
    return config_status


# CORS preflight handler
@app.options("/{path:path}")
async def preflight_handler(path: str):
    """Handle CORS preflight requests"""
    return {"message": "OK"}


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """
    User login endpoint.
    
    Args:
        username: Username from form data
        password: Password from form data
    
    Returns:
        dict: Access token and token type
    """
    if pool is None:
        raise HTTPException(status_code=503, detail="Database not available")
        
    async with pool.acquire() as conn:
        try:
            user = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            if not user or not pwd_context.verify(password, user['password_hash']):
                await log_action(
                    conn, None, "login_failed", 
                    {"username": username, "error": "Invalid credentials"}, 
                    notify=True
                )
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            access_token = jwt.encode(
                {"sub": username, "exp": datetime.utcnow() + timedelta(hours=1)},
                SECRET_KEY,
                algorithm=ALGORITHM
            )
            
            await log_action(
                conn, user['user_id'], "login_success", 
                {"username": username}, notify=True
            )
            
            return {"access_token": access_token, "token_type": "bearer"}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, None, "login_error", 
                {"username": username, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN DASHBOARD ENDPOINTS
# ============================================================================
@app.get("/admin/dashboard")
async def get_dashboard(current_user: dict = Depends(verify_admin)):
    """
    Get admin dashboard data including statistics and recent activity.
    
    Args:
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Dashboard data with statistics
    """
    async with pool.acquire() as conn:
        # Get image counts by event
        image_counts = await conn.fetch(
            "SELECT event_id, COUNT(*) as image_count FROM images GROUP BY event_id"
        )
        
        # Get user counts by role
        user_counts = await conn.fetch(
            "SELECT role, COUNT(*) as user_count FROM users GROUP BY role"
        )
        
        # Get recent uploads (last 24 hours)
        recent_uploads = await conn.fetch(
            "SELECT event_id, COUNT(*) as upload_count FROM images "
            "WHERE timestamp > NOW() - INTERVAL '24 hours' GROUP BY event_id"
        )
        
        # Get recent events
        events = await conn.fetch(
            "SELECT e.event_id, e.name, e.created_by, e.created_at, u.username as created_by_username "
            "FROM events e JOIN users u ON e.created_by = u.user_id "
            "ORDER BY e.created_at DESC LIMIT 5"
        )
        
        dashboard_data = {
            "image_counts": [
                {"event_id": str(ic["event_id"]), "image_count": ic["image_count"]} 
                for ic in image_counts
            ],
            "user_counts": [dict(row) for row in user_counts],
            "recent_uploads": [
                {"event_id": str(ru["event_id"]), "upload_count": ru["upload_count"]} 
                for ru in recent_uploads
            ],
            "events": [
                {
                    "event_id": str(e["event_id"]), 
                    "name": e["name"], 
                    "created_by": str(e["created_by"]), 
                    "created_at": e["created_at"].isoformat() if e["created_at"] else None, 
                    "created_by_username": e["created_by_username"]
                } 
                for e in events
            ]
        }
        
        # Cache dashboard data in Redis if available
        if redis_client:
            try:
                cache_key = f"dashboard_{current_user['user_id']}"
                await redis_client.setex(cache_key, 300, json.dumps(dashboard_data, default=str))
            except Exception as e:
                logger.warning(f"Failed to cache dashboard data: {str(e)}")
        
        await log_action(
            conn, current_user['user_id'], "view_dashboard", 
            {"user": current_user['username']}
        )
        
        return dashboard_data


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================
@app.get("/users")
async def get_users(current_user: dict = Depends(verify_admin)):
    """
    Get all users (admin only).
    
    Args:
        current_user: Current admin user from JWT token
    
    Returns:
        list: List of all users (without passwords)
    """
    async with pool.acquire() as conn:
        users = await conn.fetch(
            "SELECT user_id, username, role, created_at FROM users"
        )
        
        await log_action(
            conn, current_user['user_id'], "list_users", 
            {"user_count": len(users)}
        )
        
        return [
            {
                "user_id": str(u["user_id"]), 
                "username": u["username"], 
                "role": u["role"], 
                "created_at": u["created_at"].isoformat() if u["created_at"] else None
            } 
            for u in users
        ]


@app.post("/users")
async def create_user(user: UserCreate, current_user: dict = Depends(verify_admin)):
    """
    Create new user (admin only).
    
    Args:
        user: User creation data
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message
    """
    async with pool.acquire() as conn:
        try:
            password_hash = pwd_context.hash(user.password)
            user_id = str(uuid.uuid4())
            
            await conn.execute(
                "INSERT INTO users (user_id, username, password_hash, role) VALUES ($1, $2, $3, $4)",
                user_id, user.username, password_hash, user.role
            )
            
            await log_action(
                conn, current_user['user_id'], "create_user", 
                {"username": user.username, "role": user.role}, 
                notify=True
            )
            
            return {"message": "User created successfully", "user_id": user_id}
            
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "create_user_failed", 
                {"username": user.username, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.put("/users/{user_id}/role")
async def update_user_role(user_id: str, role: str, current_user: dict = Depends(verify_admin)):
    """
    Update user role (admin only).
    
    Args:
        user_id: User ID to update
        role: New role for the user
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message
    """
    async with pool.acquire() as conn:
        try:
            result = await conn.execute(
                "UPDATE users SET role = $1 WHERE user_id = $2", 
                role, user_id
            )
            
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="User not found")
            
            await log_action(
                conn, current_user['user_id'], "update_user_role", 
                {"user_id": user_id, "new_role": role}, 
                notify=True
            )
            
            return {"message": "Role updated successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "update_user_role_failed", 
                {"user_id": user_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(verify_admin)):
    """
    Delete user (admin only).
    
    Args:
        user_id: User ID to delete
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message
    """
    async with pool.acquire() as conn:
        try:
            # Prevent admin from deleting themselves
            if user_id == str(current_user['user_id']):
                raise HTTPException(status_code=400, detail="Cannot delete your own account")
            
            result = await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)
            
            if result == "DELETE 0":
                raise HTTPException(status_code=404, detail="User not found")
            
            await log_action(
                conn, current_user['user_id'], "delete_user", 
                {"user_id": user_id}, 
                notify=True
            )
            
            return {"message": "User deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "delete_user_failed", 
                {"user_id": user_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# EVENT MANAGEMENT ENDPOINTS
# ============================================================================
@app.get("/events")
async def get_events(current_user: dict = Depends(verify_admin)):
    """
    Get all events (admin only).
    
    Args:
        current_user: Current admin user from JWT token
    
    Returns:
        list: List of all events
    """
    async with pool.acquire() as conn:
        events = await conn.fetch("SELECT * FROM events ORDER BY created_at DESC")
        
        await log_action(
            conn, current_user['user_id'], "list_events", 
            {"event_count": len(events)}
        )
        
        return [
            {
                "event_id": str(e["event_id"]), 
                "name": e["name"], 
                "created_by": str(e["created_by"]), 
                "created_at": e["created_at"].isoformat() if e["created_at"] else None
            } 
            for e in events
        ]


@app.post("/events")
async def create_event(event: EventCreate, current_user: dict = Depends(verify_admin)):
    """
    Create new event (admin only).
    
    Args:
        event: Event creation data
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message with event ID
    """
    async with pool.acquire() as conn:
        try:
            event_id = str(uuid.uuid4())
            
            await conn.execute(
                "INSERT INTO events (event_id, name, created_by) VALUES ($1, $2, $3)",
                event_id, event.name, current_user['user_id']
            )
            
            # Create MinIO bucket for event
            if minio_client:
                bucket_name = f"event-{event_id}"
                try:
                    if not minio_client.bucket_exists(bucket_name):
                        minio_client.make_bucket(bucket_name)
                        logger.info(f"Created MinIO bucket: {bucket_name}")
                except Exception as e:
                    logger.warning(f"Failed to create MinIO bucket {bucket_name}: {str(e)}")
            
            await log_action(
                conn, current_user['user_id'], "create_event", 
                {"event_id": event_id, "name": event.name}, 
                notify=True
            )
            
            return {"message": "Event created successfully", "event_id": event_id}
            
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "create_event_failed", 
                {"name": event.name, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.delete("/events/{event_id}")
async def delete_event(event_id: str, current_user: dict = Depends(verify_admin)):
    """
    Delete event and all associated data (admin only).
    
    Args:
        event_id: Event ID to delete
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message
    """
    async with pool.acquire() as conn:
        try:
            # Check if event exists
            event = await conn.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            
            # Delete associated data in correct order (foreign key constraints)
            await conn.execute("DELETE FROM faces WHERE event_id = $1", event_id)
            await conn.execute("DELETE FROM consents WHERE image_id IN (SELECT id FROM images WHERE event_id = $1)", event_id)
            await conn.execute("DELETE FROM images WHERE event_id = $1", event_id)
            await conn.execute("DELETE FROM events WHERE event_id = $1", event_id)
            
            # Delete MinIO bucket and all objects
            if minio_client:
                bucket_name = f"event-{event_id}"
                try:
                    if minio_client.bucket_exists(bucket_name):
                        objects = minio_client.list_objects(bucket_name, recursive=True)
                        for obj in objects:
                            minio_client.remove_object(bucket_name, obj.object_name)
                        minio_client.remove_bucket(bucket_name)
                        logger.info(f"Deleted MinIO bucket: {bucket_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete MinIO bucket {bucket_name}: {str(e)}")
            
            await log_action(
                conn, current_user['user_id'], "delete_event", 
                {"event_id": event_id, "event_name": event["name"]}, 
                notify=True
            )
            
            return {"message": "Event deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "delete_event_failed", 
                {"event_id": event_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# IMAGE MANAGEMENT ENDPOINTS
# ============================================================================
@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...), 
    event_id: str = Form(...), 
    consent_given: bool = Form(...), 
    current_user: dict = Depends(get_current_user)
):
    """
    Upload image to event.
    
    Args:
        file: Image file to upload
        event_id: Event ID to upload to
        consent_given: Whether user gave consent for face processing
        current_user: Current user from JWT token
    
    Returns:
        dict: Success message with image ID
    """
    async with pool.acquire() as conn:
        try:
            # Validate file type
            if not file.content_type or not file.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="Only image files are allowed")
            
            # Check if event exists
            event = await conn.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            
            image_id = str(uuid.uuid4())
            
            # Upload to MinIO if available
            if minio_client:
                bucket_name = f"event-{event_id}"
                
                if not minio_client.bucket_exists(bucket_name):
                    minio_client.make_bucket(bucket_name)
                    logger.info(f"Created MinIO bucket: {bucket_name}")
                
                file_content = await file.read()
                file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
                object_name = f"{image_id}.{file_extension}"
                
                # Add consent metadata as tags
                tags = Tags()
                tags["consent"] = "true" if consent_given else "false"
                tags["uploaded_by"] = str(current_user['user_id'])
                tags["upload_time"] = datetime.utcnow().isoformat()
                
                minio_client.put_object(
                    bucket_name,
                    object_name,
                    file_content,
                    len(file_content),
                    content_type=file.content_type,
                    tags=tags
                )
                
                stored_filename = object_name
            else:
                stored_filename = file.filename
                logger.warning("MinIO not available, file not actually stored")
            
            # Save consent record
            consent_id = str(uuid.uuid4())
            await conn.execute(
                "INSERT INTO consents (consent_id, user_id, image_id, consent_given) VALUES ($1, $2, $3, $4)",
                consent_id, current_user['user_id'], image_id, consent_given
            )
            
            # Save image record
            await conn.execute(
                "INSERT INTO images (id, event_id, filename, uploaded_by, consent_given, file_size, content_type) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                image_id, event_id, stored_filename, current_user['user_id'], consent_given, len(file_content) if 'file_content' in locals() else 0, file.content_type
            )
            
            await log_action(
                conn, current_user['user_id'], "upload_image", 
                {
                    "image_id": image_id, 
                    "event_id": event_id, 
                    "filename": file.filename,
                    "consent_given": consent_given,
                    "file_size": len(file_content) if 'file_content' in locals() else 0
                }, 
                notify=True
            )
            
            return {"message": "Image uploaded successfully", "image_id": image_id}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "upload_image_failed", 
                {"event_id": event_id, "filename": file.filename, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/images")
async def get_images(
    event_id: str, 
    page: int = 1, 
    limit: int = 10, 
    current_user: dict = Depends(verify_admin)
):
    """
    Get images for event with pagination (admin only).
    
    Args:
        event_id: Event ID to get images from
        page: Page number for pagination
        limit: Number of images per page
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Paginated list of images
    """
    async with pool.acquire() as conn:
        try:
            # Validate pagination parameters
            if page < 1:
                raise HTTPException(status_code=400, detail="Page must be >= 1")
            if limit < 1 or limit > 100:
                raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
            
            offset = (page - 1) * limit
            
            # Get total count
            total_count = await conn.fetchval(
                "SELECT COUNT(*) FROM images WHERE event_id = $1", event_id
            )
            
            # Get images
            images = await conn.fetch(
                "SELECT id, event_id, filename, thumbnail_url, uploaded_by, consent_given, timestamp, file_size, content_type "
                "FROM images WHERE event_id = $1 ORDER BY timestamp DESC LIMIT $2 OFFSET $3",
                event_id, limit, offset
            )
            
            await log_action(
                conn, current_user['user_id'], "list_images", 
                {"event_id": event_id, "image_count": len(images), "page": page}
            )
            
            return {
                "images": [
                    {
                        "id": str(img["id"]), 
                        "event_id": str(img["event_id"]), 
                        "filename": img["filename"], 
                        "thumbnail_url": img["thumbnail_url"], 
                        "uploaded_by": str(img["uploaded_by"]), 
                        "consent_given": img["consent_given"], 
                        "timestamp": img["timestamp"].isoformat() if img["timestamp"] else None,
                        "file_size": img["file_size"],
                        "content_type": img["content_type"]
                    } 
                    for img in images
                ],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "list_images_failed", 
                {"event_id": event_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/images/{event_id}/{image_id}")
async def get_image(
    event_id: str, 
    image_id: str, 
    current_user: dict = Depends(get_current_user)
):
    """
    Get specific image details.
    
    Args:
        event_id: Event ID
        image_id: Image ID
        current_user: Current user from JWT token
    
    Returns:
        dict: Image details
    """
    async with pool.acquire() as conn:
        try:
            image = await conn.fetchrow(
                "SELECT * FROM images WHERE id = $1 AND event_id = $2", 
                image_id, event_id
            )
            
            if not image:
                raise HTTPException(status_code=404, detail="Image not found")
            
            await log_action(
                conn, current_user['user_id'], "view_image", 
                {"image_id": image_id, "event_id": event_id}
            )
            
            return {
                "id": str(image["id"]),
                "event_id": str(image["event_id"]),
                "filename": image["filename"],
                "thumbnail_url": image["thumbnail_url"],
                "uploaded_by": str(image["uploaded_by"]),
                "consent_given": image["consent_given"],
                "timestamp": image["timestamp"].isoformat() if image["timestamp"] else None,
                "file_size": image["file_size"],
                "content_type": image["content_type"]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "view_image_failed", 
                {"image_id": image_id, "event_id": event_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.delete("/images/{event_id}/{image_id}")
async def delete_image(
    event_id: str, 
    image_id: str, 
    current_user: dict = Depends(verify_admin)
):
    """
    Delete image (admin only).
    
    Args:
        event_id: Event ID
        image_id: Image ID to delete
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Success message
    """
    async with pool.acquire() as conn:
        try:
            # Get image details before deletion
            image = await conn.fetchrow(
                "SELECT filename FROM images WHERE id = $1 AND event_id = $2", 
                image_id, event_id
            )
            
            if not image:
                raise HTTPException(status_code=404, detail="Image not found")
            
            # Remove from MinIO if available
            if minio_client:
                bucket_name = f"event-{event_id}"
                try:
                    minio_client.remove_object(bucket_name, image['filename'])
                    logger.info(f"Deleted object {image['filename']} from bucket {bucket_name}")
                except Exception as e:
                    logger.warning(f"Failed to delete object from MinIO: {str(e)}")
            
            # Remove from database (in correct order for foreign keys)
            await conn.execute("DELETE FROM faces WHERE image_id = $1", image_id)
            await conn.execute("DELETE FROM consents WHERE image_id = $1", image_id)
            await conn.execute("DELETE FROM images WHERE id = $1", image_id)
            
            await log_action(
                conn, current_user['user_id'], "delete_image", 
                {"image_id": image_id, "event_id": event_id, "filename": image['filename']}, 
                notify=True
            )
            
            return {"message": "Image deleted successfully"}
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "delete_image_failed", 
                {"image_id": image_id, "event_id": event_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# FACE SEARCH ENDPOINTS
# ============================================================================
@app.post("/search_face")
async def search_face(
    file: UploadFile = File(...), 
    event_id: str = Form(...), 
    threshold: float = Form(0.6),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for faces in event images using uploaded reference image.
    
    Args:
        file: Reference image file for face search
        event_id: Event ID to search in
        threshold: Similarity threshold (0.0 to 1.0)
        current_user: Current user from JWT token
    
    Returns:
        dict: List of matching images
    """
    async with pool.acquire() as conn:
        try:
            # Validate file type
            if not file.content_type or not file.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail="Only image files are allowed")
            
            # Validate threshold
            if not 0.0 <= threshold <= 1.0:
                raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 1.0")
            
            # Check if event exists
            event = await conn.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
            if not event:
                raise HTTPException(status_code=404, detail="Event not found")
            
            file_content = await file.read()
            
            # Send to AI processing service
            if not AI_PROCESS_URL:
                raise HTTPException(status_code=503, detail="AI processing service not configured")
            
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field('file', file_content, filename=file.filename, content_type=file.content_type)
                
                try:
                    async with session.post(AI_PROCESS_URL, data=form, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            await log_action(
                                conn, current_user['user_id'], "search_face_failed", 
                                {"event_id": event_id, "ai_service_error": error_text}, 
                                notify=True
                            )
                            raise HTTPException(
                                status_code=response.status, 
                                detail=f"AI processing failed: {error_text}"
                            )
                        face_data = await response.json()
                except aiohttp.ClientError as e:
                    await log_action(
                        conn, current_user['user_id'], "search_face_failed", 
                        {"event_id": event_id, "connection_error": str(e)}, 
                        notify=True
                    )
                    raise HTTPException(status_code=503, detail=f"Failed to connect to AI service: {str(e)}")
            
            # Extract embedding from AI response
            if 'embedding' not in face_data:
                raise HTTPException(status_code=400, detail="No face embedding found in AI response")
            
            embedding = face_data['embedding']
            
            # Search for similar faces in database
            # Using cosine similarity: 1 - (embedding1 <=> embedding2) > threshold
            results = await conn.fetch(
                "SELECT i.id, i.filename, i.thumbnail_url, i.uploaded_by, i.timestamp, "
                "f.face_id, 1 - (f.face_embedding <=> $2) as similarity "
                "FROM images i "
                "JOIN faces f ON i.id = f.image_id "
                "WHERE i.event_id = $1 AND 1 - (f.face_embedding <=> $2) > $3 "
                "ORDER BY similarity DESC LIMIT 50",
                event_id, embedding, threshold
            )
            
            await log_action(
                conn, current_user['user_id'], "search_face", 
                {
                    "event_id": event_id, 
                    "result_count": len(results), 
                    "threshold": threshold,
                    "filename": file.filename
                }
            )
            
            return {
                "results": [
                    {
                        "id": str(r["id"]), 
                        "filename": r["filename"], 
                        "thumbnail_url": r["thumbnail_url"], 
                        "uploaded_by": str(r["uploaded_by"]),
                        "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
                        "face_id": str(r["face_id"]),
                        "similarity": float(r["similarity"])
                    } 
                    for r in results
                ],
                "search_params": {
                    "event_id": event_id,
                    "threshold": threshold,
                    "total_matches": len(results)
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "search_face_failed", 
                {"event_id": event_id, "error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# LOGS ENDPOINTS
# ============================================================================
@app.get("/logs")
async def get_logs(
    page: int = 1, 
    limit: int = 10, 
    action: str = None, 
    user_id: str = None, 
    start_date: str = None,
    end_date: str = None,
    current_user: dict = Depends(verify_admin)
):
    """
    Get system logs with filtering and pagination (admin only).
    
    Args:
        page: Page number for pagination
        limit: Number of logs per page
        action: Filter by action type (partial match)
        user_id: Filter by user ID
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        current_user: Current admin user from JWT token
    
    Returns:
        dict: Paginated list of logs
    """
    async with pool.acquire() as conn:
        try:
            # Validate pagination parameters
            if page < 1:
                raise HTTPException(status_code=400, detail="Page must be >= 1")
            if limit < 1 or limit > 100:
                raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
            
            # Build query with filters
            query = "SELECT * FROM logs"
            count_query = "SELECT COUNT(*) FROM logs"
            params = []
            conditions = []
            
            param_count = 0
            
            if action:
                param_count += 1
                conditions.append(f"action ILIKE ${param_count}")
                params.append(f"%{action}%")
            
            if user_id:
                param_count += 1
                conditions.append(f"user_id = ${param_count}")
                params.append(user_id)
            
            if start_date:
                try:
                    datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    param_count += 1
                    conditions.append(f"timestamp >= ${param_count}")
                    params.append(start_date)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid start_date format. Use ISO format.")
            
            if end_date:
                try:
                    datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    param_count += 1
                    conditions.append(f"timestamp <= ${param_count}")
                    params.append(end_date)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid end_date format. Use ISO format.")
            
            if conditions:
                where_clause = " WHERE " + " AND ".join(conditions)
                query += where_clause
                count_query += where_clause
            
            # Get total count
            total_count = await conn.fetchval(count_query, *params)
            
            # Add pagination to main query
            query += f" ORDER BY timestamp DESC LIMIT ${param_count + 1} OFFSET ${param_count + 2}"
            params.extend([limit, (page - 1) * limit])
            
            logs = await conn.fetch(query, *params)
            
            await log_action(
                conn, current_user['user_id'], "list_logs", 
                {"log_count": len(logs), "page": page, "filters": {"action": action, "user_id": user_id}}
            )
            
            return {
                "logs": [
                    {
                        "log_id": str(log["log_id"]), 
                        "user_id": str(log["user_id"]) if log["user_id"] else None, 
                        "action": log["action"], 
                        "details": log["details"], 
                        "timestamp": log["timestamp"].isoformat() if log["timestamp"] else None, 
                        "notification_sent": log["notification_sent"]
                    } 
                    for log in logs
                ],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": (total_count + limit - 1) // limit
                },
                "filters": {
                    "action": action,
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "list_logs_failed", 
                {"error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


@app.get("/logs/actions")
async def get_log_actions(current_user: dict = Depends(verify_admin)):
    """
    Get list of all unique action types in logs (admin only).
    
    Args:
        current_user: Current admin user from JWT token
    
    Returns:
        dict: List of unique action types
    """
    async with pool.acquire() as conn:
        try:
            actions = await conn.fetch(
                "SELECT DISTINCT action FROM logs ORDER BY action"
            )
            
            return {
                "actions": [action["action"] for action in actions]
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================
@app.get("/stats/summary")
async def get_stats_summary(current_user: dict = Depends(verify_admin)):
    """
    Get overall system statistics summary (admin only).
    
    Args:
        current_user: Current admin user from JWT token
    
    Returns:
        dict: System statistics
    """
    async with pool.acquire() as conn:
        try:
            # Get basic counts
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_events = await conn.fetchval("SELECT COUNT(*) FROM events")
            total_images = await conn.fetchval("SELECT COUNT(*) FROM images")
            total_faces = await conn.fetchval("SELECT COUNT(*) FROM faces")
            
            # Get storage usage
            total_storage = await conn.fetchval("SELECT COALESCE(SUM(file_size), 0) FROM images")
            
            # Get recent activity (last 24 hours)
            recent_uploads = await conn.fetchval(
                "SELECT COUNT(*) FROM images WHERE timestamp > NOW() - INTERVAL '24 hours'"
            )
            recent_logins = await conn.fetchval(
                "SELECT COUNT(*) FROM logs WHERE action = 'login_success' AND timestamp > NOW() - INTERVAL '24 hours'"
            )
            
            # Get consent statistics
            consent_given = await conn.fetchval("SELECT COUNT(*) FROM images WHERE consent_given = true")
            consent_not_given = await conn.fetchval("SELECT COUNT(*) FROM images WHERE consent_given = false")
            
            await log_action(
                conn, current_user['user_id'], "view_stats_summary", 
                {"user": current_user['username']}
            )
            
            return {
                "summary": {
                    "total_users": total_users,
                    "total_events": total_events,
                    "total_images": total_images,
                    "total_faces": total_faces,
                    "total_storage_bytes": total_storage,
                    "total_storage_mb": round(total_storage / (1024 * 1024), 2) if total_storage else 0
                },
                "recent_activity": {
                    "recent_uploads_24h": recent_uploads,
                    "recent_logins_24h": recent_logins
                },
                "consent_stats": {
                    "consent_given": consent_given,
                    "consent_not_given": consent_not_given,
                    "consent_rate": round(consent_given / (consent_given + consent_not_given) * 100, 2) if (consent_given + consent_not_given) > 0 else 0
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            await log_action(
                conn, current_user['user_id'], "view_stats_summary_failed", 
                {"error": str(e)}, 
                notify=True
            )
            raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return {"error": "Not found", "detail": "The requested resource was not found"}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(exc)}")
    return {"error": "Internal server error", "detail": "An unexpected error occurred"}


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
