# Event Photo Sales - API Implementation Status & Next Steps

## 🎯 Current Implementation Status

### ✅ **What's Already Done**
- **FastAPI Structure** - Complete API skeleton with all 300+ endpoints
- **Router Organization** - Well-organized by functional areas
- **Authentication Framework** - OAuth2 + JWT structure ready
- **WebSocket Support** - Real-time updates foundation
- **File Upload Structure** - Single/Batch upload endpoints
- **Pydantic Models** - Basic model structure (placeholder)

### 🚧 **What Needs Implementation**

#### **1. Database & Models (Critical - Phase 0)**
```python
# ต้องสร้าง Database Models จริง
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    date = Column(DateTime)
    location = Column(String(255))
    status = Column(String(50))  # กำลังถ่าย/อัพโหลดเสร็จ/เปิดขาย/ปิดขาย
    sales_enabled = Column(Boolean, default=False)
    expiry_date = Column(DateTime)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Relationships
    photos = relationship("Photo", back_populates="event")
    photographers = relationship("EventPhotographer", back_populates="event")
    pricing = relationship("EventPricing", back_populates="event")

class Photographer(Base):
    __tablename__ = "photographers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True)
    phone = Column(String(20))
    status = Column(String(50))
    commission_rate = Column(Float, default=0.0)
    created_at = Column(DateTime)
    
    # Relationships
    event_assignments = relationship("EventPhotographer", back_populates="photographer")
    uploads = relationship("PhotoUpload", back_populates="photographer")

class Photo(Base):
    __tablename__ = "photos"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    photographer_id = Column(Integer, ForeignKey("photographers.id"))
    filename = Column(String(255))
    original_filename = Column(String(255))
    file_path = Column(String(500))
    file_size = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    camera_model = Column(String(255))
    taken_at = Column(DateTime)
    upload_at = Column(DateTime)
    approval_status = Column(String(50))  # pending/approved/rejected
    face_detection_status = Column(String(50))  # pending/completed/failed
    metadata = Column(Text)  # JSON
    
    # Relationships
    event = relationship("Event", back_populates="photos")
    faces = relationship("Face", back_populates="photo")
    order_items = relationship("OrderItem", back_populates="photo")

# เพิ่ม Models อื่นๆ: Face, Customer, Order, Payment, etc.
```

#### **2. Authentication & Security (Phase 0)**
```python
# JWT Implementation
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

#### **3. File Storage & Processing (Phase 1)**
```python
# File Storage Implementation
import boto3
from PIL import Image
import face_recognition

class FileStorageService:
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.bucket_name = 'thepixstock-photos'
    
    async def upload_photo(self, file: UploadFile, event_id: int, photographer_id: int):
        # 1. Save original file
        file_key = f"events/{event_id}/originals/{file.filename}"
        
        # 2. Upload to S3
        await self.s3_client.upload_fileobj(file.file, self.bucket_name, file_key)
        
        # 3. Create thumbnails
        await self.create_thumbnails(file_key, event_id)
        
        # 4. Add watermark for preview
        await self.add_watermark_preview(file_key, event_id)
        
        # 5. Extract metadata
        metadata = await self.extract_metadata(file_key)
        
        # 6. Queue for face detection
        await self.queue_face_detection(file_key)
        
        return file_key

    async def create_thumbnails(self, file_key: str, event_id: int):
        # Create multiple sizes: 150x150, 300x300, 800x600
        pass
    
    async def add_watermark_preview(self, file_key: str, event_id: int):
        # Add watermark for preview version
        pass
```

#### **4. Face Recognition Implementation (Phase 2)**
```python
# Face Recognition Service
class FaceRecognitionService:
    def __init__(self):
        self.known_faces = []  # Database of known faces
    
    async def detect_faces_in_photo(self, photo_path: str) -> List[dict]:
        # Load image
        image = face_recognition.load_image_file(photo_path)
        
        # Find face locations
        face_locations = face_recognition.face_locations(image)
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        faces = []
        for i, encoding in enumerate(face_encodings):
            face_data = {
                "location": face_locations[i],
                "encoding": encoding.tolist(),
                "confidence": 0.95  # placeholder
            }
            faces.append(face_data)
        
        return faces
    
    async def search_faces_by_upload(self, search_image_path: str, event_id: int) -> List[dict]:
        # Load search image
        search_image = face_recognition.load_image_file(search_image_path)
        search_encodings = face_recognition.face_encodings(search_image)
        
        if not search_encodings:
            return []
        
        search_encoding = search_encodings[0]
        
        # Get all faces from event
        event_faces = await self.get_event_faces(event_id)
        
        matches = []
        for face in event_faces:
            # Compare faces
            distance = face_recognition.face_distance([search_encoding], face['encoding'])[0]
            
            if distance < 0.6:  # Threshold for match
                matches.append({
                    "photo_id": face['photo_id'],
                    "confidence": 1 - distance,
                    "face_location": face['location']
                })
        
        # Sort by confidence
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches
```

#### **5. Payment Gateway Integration (Phase 1)**
```python
# Payment Service
import stripe

class PaymentService:
    def __init__(self):
        stripe.api_key = "sk_test_..."  # Your Stripe secret key
    
    async def create_payment_intent(self, amount: int, order_id: int):
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount * 100,  # Convert to cents
                currency='thb',
                metadata={'order_id': order_id}
            )
            return intent
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    async def confirm_payment(self, payment_intent_id: str):
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if intent.status == 'succeeded':
                return True
            return False
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
```

---

## 🔧 **Implementation Priority**

### **Phase 0: Foundation (Week 1-2)**
1. **Database Setup** - SQLAlchemy models + migrations
2. **Authentication** - JWT + user management
3. **Basic CRUD** - Events, Photographers, Customers
4. **File Upload** - Single photo upload with storage

### **Phase 1: Core Features (Week 3-4)**
5. **Batch Upload** - Multiple photo upload
6. **Photo Processing** - Thumbnails, watermarks, metadata
7. **Approval System** - Admin approve/reject photos
8. **Payment Gateway** - Stripe integration
9. **Order System** - Create orders + download links

### **Phase 2: Advanced Features (Week 5-6)**
10. **Face Recognition** - Detect faces in photos
11. **Face Search** - Customer upload face to find photos
12. **Analytics** - Revenue reports, popular photos
13. **Email System** - Order confirmations, download links

### **Phase 3: Polish & Optimize (Week 7-8)**
14. **Real-time Updates** - WebSocket notifications
15. **Mobile APIs** - Optimize for mobile app
16. **Performance** - Caching, optimization
17. **Security** - Rate limiting, GDPR compliance

---

## 📋 **Next Steps Checklist**

### **Immediate Actions (This Week)**
- [ ] Setup PostgreSQL database
- [ ] Create SQLAlchemy models for all entities
- [ ] Implement JWT authentication
- [ ] Setup AWS S3 for file storage
- [ ] Create basic photo upload functionality

### **Development Environment**
```python
# requirements.txt additions needed:
sqlalchemy==1.4.48
alembic==1.12.1
psycopg2-binary==2.9.7
boto3==1.28.17
pillow==10.0.0
face-recognition==1.3.0
stripe==6.6.0
redis==4.6.0
celery==5.3.1
python-jose==3.3.0
passlib==1.7.4
python-bcrypt==4.0.1
```

### **Database Migration Setup**
```bash
# Initialize Alembic
alembic init alembic

# Create first migration
alembic revision --autogenerate -m "Initial tables"

# Run migration
alembic upgrade head
```

### **Environment Configuration**
```python
# .env file needed:
DATABASE_URL=postgresql://user:pass@localhost/thepixstock
SECRET_KEY=your-super-secret-jwt-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_BUCKET_NAME=thepixstock-photos
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
REDIS_URL=redis://localhost:6379
```

---

## 🎯 **Current Status Summary**

✅ **Complete:** API Structure (300+ endpoints)  
🚧 **In Progress:** Need to implement actual logic  
❌ **Missing:** Database, Authentication, File Processing, Face Recognition

**Ready for:** Full-scale backend development  
**Estimated Timeline:** 8 weeks for complete implementation  
**Team Size Recommended:** 2-3 backend developers + 1 DevOps

**Next Critical Decision:** Choose specific tech stack components (Database, Storage, Face Recognition library, Payment Gateway)
