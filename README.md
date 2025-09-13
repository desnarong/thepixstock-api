# 🚀 ThePixStock Complete Deployment Guide

## 📋 System Overview

ThePixStock เป็นแพลตฟอร์มขายภาพถ่ายงานอีเว้นท์ที่ใช้ AI Face Recognition ประกอบด้วย 4 VMs:

| VM | Component | IP | Specs | Status |
|----|-----------|----|----|--------|
| VM1 | API & Database | 192.168.1.10 | 4 vCPU, 16GB RAM, 500GB SSD | ✅ Ready |
| VM2 | AI Processing | 192.168.1.11 | 8 vCPU, 32GB RAM, 200GB SSD | ✅ Ready |
| VM3 | Web Frontend | 192.168.1.12 | 4 vCPU, 8GB RAM, 100GB SSD | ✅ Ready |
| VM4 | Monitoring | 192.168.1.13 | 4 vCPU, 8GB RAM, 200GB SSD | 🔄 Setup |

---

## 🎯 Quick Start Guide

### Step 1: Setup VM1 - API Server
```bash
# SSH to VM1
ssh root@192.168.1.10

# Download and run setup script
wget https://raw.githubusercontent.com/your-repo/vm1-setup.sh
chmod +x vm1-setup.sh
./vm1-setup.sh

# Deploy .NET API
cd ~/ThePixStock
./deploy.sh

# Check services
/usr/local/bin/check-services.sh
```

### Step 2: Setup VM2 - AI Processing
```bash
# SSH to VM2
ssh root@192.168.1.11

# Download and run setup script
wget https://raw.githubusercontent.com/your-repo/vm2-setup.sh
chmod +x vm2-setup.sh
./vm2-setup.sh

# Check Celery workers
supervisorctl status

# Access Flower monitoring
# http://192.168.1.11:5555
# Username: admin
# Password: SecurePassword123
```

### Step 3: Setup VM3 - Web Frontend
```bash
# SSH to VM3
ssh root@192.168.1.12

# Download and run setup script
wget https://raw.githubusercontent.com/your-repo/vm3-setup.sh
chmod +x vm3-setup.sh
./vm3-setup.sh

# Configure SSL certificates
certbot --nginx -d thepixstock.com -d www.thepixstock.com
certbot --nginx -d admin.thepixstock.com

# Deploy frontend
/var/www/thepixstock/deploy.sh
```

### Step 4: Setup VM4 - Monitoring
```bash
# SSH to VM4
ssh root@192.168.1.13

# Quick monitoring setup
apt update && apt upgrade -y
apt install -y curl wget git

# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.47.0/prometheus-2.47.0.linux-amd64.tar.gz
tar xzf prometheus-2.47.0.linux-amd64.tar.gz
cp prometheus-2.47.0.linux-amd64/prometheus /usr/local/bin/
cp prometheus-2.47.0.linux-amd64/promtool /usr/local/bin/

# Install Grafana
wget -q -O - https://packages.grafana.com/gpg.key | apt-key add -
echo "deb https://packages.grafana.com/enterprise/deb stable main" | tee /etc/apt/sources.list.d/grafana.list
apt update && apt install -y grafana-enterprise

# Start services
systemctl enable --now prometheus
systemctl enable --now grafana-server

# Access monitoring
# Prometheus: http://192.168.1.13:9090
# Grafana: http://192.168.1.13:3000 (admin/admin)
```

---

## 🔧 Configuration Files

### 1. Update API Connection Strings
```bash
# VM1: /var/www/thepixstock-api/appsettings.json
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=localhost;Database=thepixstock_db;Username=thepixstock;Password=SecurePassword123!",
    "Redis": "localhost:6379"
  },
  "PayNoi": {
    "ApiKey": "YOUR_ACTUAL_API_KEY",
    "KeyId": "YOUR_KEY_ID",
    "Account": "YOUR_ACCOUNT"
  }
}
```

### 2. Update Frontend Environment
```bash
# VM3: /var/www/thepixstock/customer-web/.env
VITE_API_URL=https://api.thepixstock.com

# VM3: /var/www/thepixstock/admin-panel/.env
VITE_API_URL=https://api.thepixstock.com
```

### 3. Update AI Processing Config
```bash
# VM2: /opt/thepixstock-ai/.env
API_BASE_URL=http://192.168.1.10:5000
REDIS_URL=redis://:YourRedisPassword123!@192.168.1.10:6379/0
MINIO_ENDPOINT=192.168.1.10:9000
```

---

## 📊 Service URLs & Credentials

### Public URLs
| Service | URL | Purpose |
|---------|-----|---------|
| Customer Web | https://thepixstock.com | หน้าเว็บสำหรับลูกค้า |
| Admin Panel | https://admin.thepixstock.com | แผงควบคุมสำหรับผู้ดูแล |
| API Documentation | https://api.thepixstock.com/swagger | API Documentation |

### Internal Services
| Service | URL | Credentials |
|---------|-----|-------------|
| MinIO Console | http://192.168.1.10:9001 | minioadmin / SecureMinioPassword123! |
| Flower (Celery) | http://192.168.1.11:5555 | admin / SecurePassword123 |
| Grafana | http://192.168.1.13:3000 | admin / admin (change on first login) |
| Prometheus | http://192.168.1.13:9090 | No auth |

### Database Access
```bash
# PostgreSQL
Host: 192.168.1.10
Port: 5432
Database: thepixstock_db
Username: thepixstock
Password: SecurePassword123!

# Redis
Host: 192.168.1.10
Port: 6379
Password: YourRedisPassword123!
```

---

## 🧪 Testing the System

### 1. Test API Health
```bash
curl https://api.thepixstock.com/health
# Expected: {"status":"healthy","timestamp":"..."}
```

### 2. Test Face Detection
```bash
# SSH to VM2
cd /opt/thepixstock-ai
source venv/bin/activate
python test_face_detection.py
```

### 3. Test Payment Integration
```bash
# Create test payment via API
curl -X POST https://api.thepixstock.com/api/payment/test \
  -H "Content-Type: application/json" \
  -d '{"amount": 100}'
```

### 4. Load Testing
```bash
# Install Apache Bench
apt install apache2-utils

# Test API performance
ab -n 1000 -c 10 https://api.thepixstock.com/api/event
```

---

## 📈 Monitoring & Alerts

### Key Metrics to Monitor
1. **API Response Time** - Target: < 200ms (p95)
2. **Face Search Time** - Target: < 2 seconds
3. **Payment Success Rate** - Target: > 95%
4. **System Uptime** - Target: > 99.9%

### Setting up Alerts
```yaml
# Prometheus alert rules
- alert: APIHighResponseTime
  expr: http_request_duration_seconds{quantile="0.95"} > 0.5
  for: 5m
  annotations:
    summary: "API response time is high"

- alert: PaymentFailureRate
  expr: rate(payment_failed_total[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High payment failure rate"
```

---

## 🔒 Security Checklist

- [ ] Change all default passwords
- [ ] Configure SSL certificates for all domains
- [ ] Enable firewall on all VMs
- [ ] Set up fail2ban for SSH protection
- [ ] Configure backup strategy
- [ ] Enable audit logging
- [ ] Set up VPN for internal communication
- [ ] Regular security updates

---

## 🔄 Backup Strategy

### Daily Backups
```bash
# Database backup (VM1)
pg_dump thepixstock_db > /backup/db_$(date +%Y%m%d).sql

# MinIO backup (VM1)
mc mirror local/thepixstock /backup/minio/

# Code backup
git push origin main
```

### Backup Schedule
- **Database**: Daily at 2 AM
- **Files (MinIO)**: Daily at 3 AM
- **Code**: On every deployment
- **Configuration**: Weekly

---

## 🚨 Troubleshooting

### Common Issues

#### 1. API Not Responding
```bash
# Check API status
systemctl status thepixstock-api

# Check logs
journalctl -u thepixstock-api -n 100

# Restart API
systemctl restart thepixstock-api
```

#### 2. Face Detection Not Working
```bash
# Check Celery workers
supervisorctl status

# Check Redis connection
redis-cli -h 192.168.1.10 -a YourRedisPassword123! ping

# Restart workers
supervisorctl restart thepixstock-ai:*
```

#### 3. Payment Issues
```bash
# Check PayNoi credentials
cat /var/www/thepixstock-api/appsettings.json | grep PayNoi

# Test PayNoi API
curl https://paynoi.com/ppay_api/test
```

---

## 📞 Support Contacts

| Role | Name | Contact |
|------|------|---------|
| System Admin | Admin Team | admin@thepixstock.com |
| Developer | Dev Team | dev@thepixstock.com |
| PayNoi Support | PayNoi | support@paynoi.com |

---

## 🎉 Launch Checklist

### Pre-Launch
- [ ] All services running and healthy
- [ ] SSL certificates installed
- [ ] Backup system configured
- [ ] Monitoring alerts set up
- [ ] Load testing completed
- [ ] Security audit passed

### Launch Day
- [ ] Enable production mode
- [ ] Clear test data
- [ ] Enable payment gateway
- [ ] Monitor system metrics
- [ ] Standby support team

### Post-Launch
- [ ] Monitor error rates
- [ ] Check payment success rate
- [ ] Review performance metrics
- [ ] Collect user feedback
- [ ] Plan improvements

---

## 📚 Additional Resources

- [API Documentation](https://api.thepixstock.com/swagger)
- [Face Recognition Best Practices](https://github.com/ageitgey/face_recognition)
- [Vue.js Documentation](https://vuejs.org/)
- [.NET 8 Documentation](https://docs.microsoft.com/dotnet/)
- [PayNoi Integration Guide](https://paynoi.com/docs)

---

## 🎯 Success Metrics (Year 1 Target)

| Metric | Target | Current |
|--------|--------|---------|
| Total Events | 200+ | 0 |
| Photos Uploaded | 500,000+ | 0 |
| Active Customers | 50,000+ | 0 |
| Revenue | 5M THB+ | 0 |
| System Uptime | 99.9% | - |
| Customer Satisfaction | 4.5/5 | - |

---

**🚀 ThePixStock is Ready for Launch!**

The complete event photography platform with AI-powered face recognition is now deployed and ready to revolutionize how people find and purchase their event photos in Thailand!

For any questions or issues, refer to this guide or contact the support team.

**Happy Launching! 🎉**