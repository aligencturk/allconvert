# 🚀 Production Deployment Rehberi

## 📋 Ön Gereksinimler

### Sistem Gereksinimleri
- **Python 3.7+** (önerilen: Python 3.9+)
- **pip** paket yöneticisi
- **Git** (kodları çekmek için)
- **FFmpeg** (ses/video işleme için)
- **RAM**: Minimum 2GB (önerilen: 4GB+)
- **Disk**: Minimum 10GB boş alan
- **Network**: İnternet bağlantısı

### Sunucu Gereksinimleri
- **Ubuntu 20.04+ / CentOS 8+ / Debian 11+**
- **Nginx** veya **Apache** (reverse proxy için)
- **SSL Sertifikası** (Let's Encrypt öneriliyor)
- **Domain adı** (örn: yourdomain.com)

## 🔧 Kurulum Adımları

### 1. Sunucuya Bağlanın
```bash
ssh username@your-server-ip
```

### 2. Sistem Güncellemesi
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### 3. Python ve Gerekli Paketleri Kurun
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv git nginx ffmpeg -y

# CentOS/RHEL
sudo yum install python3 python3-pip git nginx ffmpeg -y
```

### 4. Projeyi Klonlayın
```bash
cd /opt
sudo git clone [YOUR_REPOSITORY_URL] allconvert
sudo chown -R $USER:$USER /opt/allconvert
cd /opt/allconvert
```

### 5. Python Virtual Environment Oluşturun
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Environment Dosyasını Oluşturun
```bash
nano .env
```

**`.env` dosyası içeriği:**
```bash
# MUTLAKA DEĞİŞTİRİN!
SECRET_KEY=super-secret-production-key-change-this-immediately

# Production ayarları
CLEANUP_INTERVAL_HOURS=1
FILE_RETENTION_HOURS=24
MAX_CONCURRENT_DOWNLOADS=3
DISK_USAGE_WARNING_PERCENT=80
DISK_USAGE_CRITICAL_PERCENT=90

# Flask ayarları (production için)
FLASK_ENV=production
```

### 7. Gunicorn Kurun ve Yapılandırın
```bash
pip install gunicorn

# Gunicorn config dosyası oluşturun
nano gunicorn.conf.py
```

**`gunicorn.conf.py` içeriği:**
```python
import multiprocessing

# Sunucu ayarları
bind = "127.0.0.1:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "/var/log/allconvert/access.log"
errorlog = "/var/log/allconvert/error.log"
loglevel = "info"

# Process naming
proc_name = "allconvert"

# User ve group
user = "www-data"
group = "www-data"

# Pid dosyası
pidfile = "/var/run/allconvert.pid"

# Daemon
daemon = False
```

### 8. Log Klasörü Oluşturun
```bash
sudo mkdir -p /var/log/allconvert
sudo chown www-data:www-data /var/log/allconvert
```

### 9. Systemd Service Oluşturun
```bash
sudo nano /etc/systemd/system/allconvert.service
```

**Service dosyası içeriği:**
```ini
[Unit]
Description=AllConvert Flask Application
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/opt/allconvert
Environment=PATH=/opt/allconvert/venv/bin
ExecStart=/opt/allconvert/venv/bin/gunicorn --config gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
PIDFile=/var/run/allconvert.pid
Restart=always
RestartSec=1

[Install]
WantedBy=multi-user.target
```

### 10. Service'i Başlatın
```bash
sudo systemctl daemon-reload
sudo systemctl enable allconvert
sudo systemctl start allconvert
sudo systemctl status allconvert
```

## 🌐 Nginx Konfigürasyonu

### 1. Nginx Site Konfigürasyonu
```bash
sudo nano /etc/nginx/sites-available/allconvert
```

**Nginx config:**
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # HTTP'den HTTPS'e yönlendirme
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Sertifikaları (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL Güvenlik
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # Dosya yükleme limiti
    client_max_body_size 100M;
    client_body_timeout 120s;
    
    # Timeout ayarları
    proxy_connect_timeout 120s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static dosyalar için cache
    location /static {
        alias /opt/allconvert/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Güvenlik headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
}
```

### 2. Site'i Aktifleştirin
```bash
sudo ln -s /etc/nginx/sites-available/allconvert /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🔒 SSL Sertifikası (Let's Encrypt)

```bash
# Certbot kurun
sudo apt install certbot python3-certbot-nginx -y

# SSL sertifikası alın
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Otomatik yenileme
sudo crontab -e
# Şu satırı ekleyin:
0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔥 Firewall Konfigürasyonu

```bash
# UFW firewall kurun ve yapılandırın
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw status
```

## 📊 Monitoring ve Maintenance

### 1. Log Takibi
```bash
# Uygulama logları
sudo tail -f /var/log/allconvert/error.log
sudo tail -f /var/log/allconvert/access.log

# System logları
sudo journalctl -u allconvert -f
sudo journalctl -u nginx -f
```

### 2. Sistem Durumu Kontrolleri
```bash
# Service durumu
sudo systemctl status allconvert
sudo systemctl status nginx

# Disk kullanımı
df -h

# Memory kullanımı
free -h

# Process takibi
ps aux | grep gunicorn
```

### 3. Manuel Temizlik
```bash
# Curl ile admin endpoint'i kullanın
curl -X POST https://yourdomain.com/admin/cleanup

# Sistem durumu
curl https://yourdomain.com/admin/status
```

## ⚠️ Güvenlik Önerileri

### 1. SSH Güvenliği
```bash
# SSH key-based authentication kullanın
# Password authentication'ı devre dışı bırakın
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
sudo systemctl restart ssh
```

### 2. Fail2Ban Kurun
```bash
sudo apt install fail2ban -y
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Otomatik Güncellemeler
```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 🔄 Backup Stratejisi

### 1. Günlük Backup Script'i
```bash
sudo nano /opt/backup-allconvert.sh
```

```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/backups/allconvert"
mkdir -p $BACKUP_DIR

# Kod backup'ı
tar -czf $BACKUP_DIR/code_$DATE.tar.gz -C /opt allconvert --exclude=venv --exclude=downloads

# Log backup'ı
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/allconvert

# Eski backup'ları temizle (30 günden eski)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $DATE"
```

```bash
sudo chmod +x /opt/backup-allconvert.sh
sudo crontab -e
# Her gün saat 02:00'da backup al
0 2 * * * /opt/backup-allconvert.sh
```

## 🚨 Troubleshooting

### Yaygın Problemler ve Çözümleri

1. **503 Service Unavailable**
   ```bash
   sudo systemctl status allconvert
   sudo journalctl -u allconvert -n 50
   ```

2. **Disk Dolu**
   ```bash
   # Manuel temizlik
   curl -X POST http://localhost:5000/admin/cleanup
   # veya
   sudo systemctl restart allconvert
   ```

3. **Memory Kullanımı Yüksek**
   ```bash
   sudo systemctl restart allconvert
   ```

4. **SSL Problemi**
   ```bash
   sudo certbot renew
   sudo systemctl reload nginx
   ```

## 📞 İletişim ve Destek

Herhangi bir problem yaşarsanız:
1. Log dosyalarını kontrol edin
2. Sistem durumunu kontrol edin (`/admin/status`)
3. Service'leri restart edin
4. Gerekirse geliştiriciye ulaşın

---

**🎉 Tebrikler! Projeniz artık production'da çalışıyor!** 🎉 