# ThePixStock - ระบบขายภาพถ่ายงานอีเว้นท์ด้วย AI Face Recognition

## 🎯 ภาพรวมระบบ

ThePixStock เป็นแพลตฟอร์มขายภาพถ่ายงานอีเว้นท์ที่ใช้ AI Face Recognition ให้ลูกค้าค้นหาภาพของตัวเองได้ง่าย พร้อมระบบชำระเงินผ่าน QR PromptPay

## 🏗️ สถาปัตยกรรมระบบ (4 VMs)

### VM1: API & Database Server
- **OS:** Debian 12
- **Specs:** 4 vCPU, 16GB RAM, 500GB SSD
- **Stack:**
  - .NET 8 API Server
  - PostgreSQL 15 (Database)
  - Redis (Cache & Session)
  - MinIO (Object Storage)
- **Services:**
  - RESTful API
  - Authentication & Authorization (JWT)
  - Payment Integration (PayNoi)
  - WebSocket for real-time updates

### VM2: AI Processing Server
- **OS:** Debian 12
- **Specs:** 8 vCPU, 32GB RAM, 200GB SSD, GPU (optional)
- **Stack:**
  - Python 3.11
  - Face Recognition (dlib, face_recognition)
  - Celery (Task Queue)
  - OpenCV (Image Processing)
- **Services:**
  - Face Detection & Recognition
  - Image Processing & Thumbnails
  - Watermark Generation
  - EXIF Metadata Extraction

### VM3: Web Frontend Server
- **OS:** Debian 12
- **Specs:** 4 vCPU, 8GB RAM, 100GB SSD
- **Stack:**
  - Vue.js 3 (Customer Web)
  - Vue.js 3 (Admin Panel)
  - Nginx (Web Server)
  - Node.js (SSR optional)
- **Services:**
  - Customer Website
  - Admin Dashboard
  - Photographer Portal
  - Real-time notifications

### VM4: Monitoring & Analytics
- **OS:** Debian 12
- **Specs:** 4 vCPU, 8GB RAM, 200GB SSD
- **Stack:**
  - Prometheus (Metrics)
  - Grafana (Visualization)
  - Loki (Logs)
  - AlertManager (Alerts)
- **Services:**
  - System Monitoring
  - Business Analytics
  - Alert Management
  - Log Aggregation

## 📊 Database Schema (PostgreSQL)

### Core Tables
```sql
-- Users & Authentication
users (id, email, password_hash, role, first_name, last_name, phone, created_at)
user_sessions (id, user_id, token, expires_at, created_at)

-- Events
events (id, name, description, event_date, location, venue, status, created_by)
event_photographers (event_id, photographer_id, role, permissions)
event_pricing (id, event_id, package_type, price, photo_count)

-- Photos
photos (id, event_id, photographer_id, filename, file_path, processing_status)
photo_metadata (photo_id, camera_make, camera_model, taken_at, gps_lat, gps_long)
photo_faces (id, photo_id, encoding, bounding_box, confidence, quality_score)

-- Orders & Payments
orders (id, customer_id, event_id, package_id, total_amount, status)
order_items (id, order_id, photo_id, price)
payments (id, order_id, transaction_id, amount, status, gateway, payment_method)

-- Business
customers (id, user_id, total_orders, total_spent)
photographers (id, user_id, commission_rate, total_earnings)
```

## 💼 Business Features

### For Customers
1. **ค้นหาภาพด้วยใบหน้า**
   - Upload รูปหรือถ่ายเซลฟี่
   - AI จะค้นหาภาพที่มีใบหน้าคล้ายกัน
   - ความแม่นยำสูงด้วย face_recognition

2. **เลือกแพ็คเกจ**
   - รูปเดี่ยว: 50-100 บาท
   - แพ็ค 5 รูป: 200 บาท
   - แพ็ค 10 รูป: 350 บาท
   - All Event: 500-1000 บาท

3. **ชำระเงินง่าย**
   - QR PromptPay ผ่าน PayNoi
   - ตรวจสอบสถานะอัตโนมัติ
   - ส่งลิงก์ดาวน์โหลดทันที

### For Photographers
1. **Upload ภาพ**
   - Batch upload ได้ครั้งละ 50+ รูป
   - ประมวลผลอัตโนมัติ
   - แยก Face สำหรับค้นหา

2. **จัดการงาน**
   - สร้างอีเว้นท์
   - กำหนดราคาแพ็คเกจ
   - ติดตามยอดขาย

3. **รายได้**
   - Commission 70-80%
   - รายงานยอดขายแบบ Real-time
   - ถอนเงินผ่านธนาคาร

### For Admin
1. **Dashboard**
   - ยอดขายรายวัน/เดือน
   - จำนวนลูกค้า
   - อีเว้นท์ที่กำลังดำเนินการ

2. **จัดการระบบ**
   - อนุมัติช่างภาพ
   - ตั้งค่า Commission
   - จัดการ Pricing

3. **Monitoring**
   - System Health
   - API Performance
   - Error Tracking

## 🔄 Workflow หลัก

### 1. Event Creation Flow
```
Admin/Photographer สร้างงาน → กำหนดรายละเอียด → ตั้งราคา → เปิดขาย
```

### 2. Photo Upload Flow
```
Photographer upload → AI ตรวจจับใบหน้า → สร้าง Thumbnails → 
Add Watermark → พร้อมขาย
```

### 3. Customer Purchase Flow
```
ลูกค้าเข้าเว็บ → เลือกอีเว้นท์ → ค้นหาด้วยใบหน้า → 
เลือกรูป → เลือกแพ็คเกจ → ชำระเงิน QR → ดาวน์โหลด
```

### 4. Face Search Flow
```
Upload/ถ่ายรูป → ตรวจจับใบหน้า → เปรียบเทียบ Encoding → 
แสดงผลเรียงตาม Similarity → เลือกรูปที่ต้องการ
```

## 🚀 Implementation Timeline

### Phase 1: Infrastructure (Week 1-2)
- [ ] Setup VMs และ OS
- [ ] Install PostgreSQL, Redis, MinIO
- [ ] Configure Networking & Security
- [ ] Setup Monitoring Stack

### Phase 2: Backend Development (Week 3-6)
- [ ] .NET API Development
- [ ] Database Schema & Migrations
- [ ] Authentication System
- [ ] Payment Integration
- [ ] Photo Management APIs

### Phase 3: AI Processing (Week 5-8)
- [ ] Face Detection Pipeline
- [ ] Face Recognition & Search
- [ ] Image Processing
- [ ] Celery Task Queue
- [ ] Performance Optimization

### Phase 4: Frontend Development (Week 7-10)
- [ ] Customer Website
- [ ] Admin Dashboard
- [ ] Photographer Portal
- [ ] Mobile Responsive
- [ ] Payment Flow UI

### Phase 5: Integration & Testing (Week 9-12)
- [ ] API Integration
- [ ] End-to-end Testing
- [ ] Performance Testing
- [ ] Security Testing
- [ ] UAT

### Phase 6: Deployment (Week 12-13)
- [ ] Production Deployment
- [ ] SSL Certificates
- [ ] Domain Setup
- [ ] Monitoring Setup
- [ ] Backup Configuration

### Phase 7: Go-Live (Week 14)
- [ ] Soft Launch
- [ ] Bug Fixes
- [ ] Performance Tuning
- [ ] Full Launch

## 💰 Pricing Strategy

### Customer Packages
| Package | Photos | Price (THB) | Per Photo |
|---------|--------|-------------|-----------|
| Single | 1 | 79 | 79 |
| Starter | 5 | 299 | 60 |
| Popular | 10 | 499 | 50 |
| Premium | 20 | 899 | 45 |
| All Event | Unlimited | 1,499 | - |

### Photographer Commission
| Sales Volume/Month | Commission Rate |
|-------------------|-----------------|
| 0 - 10,000 THB | 70% |
| 10,001 - 50,000 THB | 75% |
| 50,001+ THB | 80% |

## 🔐 Security Measures

1. **Authentication**
   - JWT with refresh tokens
   - 2FA for admin/photographers
   - Session management

2. **Data Protection**
   - Encrypted passwords (BCrypt)
   - HTTPS everywhere
   - Encrypted storage

3. **Payment Security**
   - No credit card storage
   - PayNoi handles payments
   - Transaction verification

4. **Privacy**
   - Face data encryption
   - GDPR compliance
   - Data retention policies

## 📈 Expected Metrics

### System Performance
- API Response: < 200ms (p95)
- Face Search: < 2 seconds
- Image Processing: < 5 seconds/photo
- Concurrent Users: 1,000+

### Business Targets (Year 1)
- Events: 200+
- Photos: 500,000+
- Customers: 50,000+
- Revenue: 5M THB+

## 🛠️ Technology Stack Summary

### Backend
- **API:** .NET 8, C#
- **Database:** PostgreSQL 15
- **Cache:** Redis
- **Storage:** MinIO
- **Queue:** Celery + Redis
- **AI:** Python, face_recognition, OpenCV

### Frontend
- **Framework:** Vue.js 3
- **UI:** Tailwind CSS
- **State:** Pinia
- **HTTP:** Axios
- **Build:** Vite

### Infrastructure
- **OS:** Debian 12
- **Web Server:** Nginx
- **Container:** Docker (optional)
- **Monitoring:** Prometheus + Grafana
- **Logs:** Loki + Promtail

### Integration
- **Payment:** PayNoi (PromptPay)
- **Email:** SendGrid/AWS SES
- **SMS:** Twilio (optional)
- **CDN:** Cloudflare

## 📝 Key Success Factors

1. **User Experience**
   - Face search ต้องแม่นยำ > 90%
   - หน้าเว็บโหลดเร็ว < 3 วินาที
   - ชำระเงินง่าย ไม่เกิน 3 คลิก

2. **Photographer Satisfaction**
   - Upload ง่าย รองรับไฟล์ใหญ่
   - Commission สูง 70-80%
   - รายงานยอดขาย Real-time

3. **System Reliability**
   - Uptime > 99.9%
   - Auto-scaling ready
   - Backup ทุก 6 ชั่วโมง

4. **Business Growth**
   - Marketing automation
   - Referral program
   - Partnership with event organizers

## 🎯 Next Steps

1. **Immediate Actions**
   - Setup development environment
   - Create Git repositories
   - Setup CI/CD pipeline
   - Begin API development

2. **Week 1 Goals**
   - Complete infrastructure setup
   - Database schema finalized
   - Basic API endpoints working
   - Face detection POC

3. **Month 1 Targets**
   - Core features completed
   - Admin panel functional
   - Payment integration tested
   - Beta version ready

---

**Ready to build ThePixStock!** 🚀

This system will revolutionize event photography sales in Thailand with cutting-edge AI technology and seamless user experience.