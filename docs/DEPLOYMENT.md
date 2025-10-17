# Inventory System Deployment Guide

## Quick Start

### Development Setup
```bash
# Install dependencies
python deploy.py

# Run in development mode
uv run uvicorn app.main:app --reload
```

### Production Deployment

#### Option 1: Executable
```bash
# Create executable
python deploy.py exe

# Run the executable
./dist/inventory-app
```

#### Option 2: Docker
```bash
# Build Docker image
python deploy.py docker

# Run with Docker
docker run -p 8000:8000 -v /var/lib/inventory:/var/lib/inventory inventory-system
```

#### Option 3: Full Deployment
```bash
# Complete deployment (tests + build + package)
python deploy.py deploy
```

## Configuration

### Environment Variables

Create a `.env` file for production:

```env
# Required for production
INVENTORY_SECRET_KEY=your-secret-key-here-min-32-chars
INVENTORY_API_KEY=your-api-key-here
INVENTORY_BASIC_USER=admin
INVENTORY_BASIC_PASS=your-strong-password

# Optional
INVENTORY_APP_DIR=/var/lib/inventory
INVENTORY_AUDIT_DISABLED=false
INVENTORY_AUDIT_STDOUT=false
INVENTORY_MIGRATE=false

# Performance tuning
INVENTORY_DB_POOL_SIZE=20
INVENTORY_DB_MAX_OVERFLOW=30
INVENTORY_DB_POOL_RECYCLE=3600
```

### Security Setup

1. **Generate secure keys**:
```bash
# Generate secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate API key
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

2. **Set file permissions**:
```bash
# Create app directory
sudo mkdir -p /var/lib/inventory
sudo chown $USER:$USER /var/lib/inventory
chmod 750 /var/lib/inventory
```

## System Requirements

### Minimum Requirements
- Python 3.10+
- Node.js 18+
- 512MB RAM
- 100MB disk space

### Recommended Requirements
- Python 3.11+
- Node.js 20+
- 2GB RAM
- 1GB disk space

## Deployment Methods

### 1. Standalone Executable

Best for:
- Single-server deployments
- Simple installations
- Air-gapped environments

```bash
# Build executable
python deploy.py exe

# Install as service (Linux)
sudo cp dist/inventory-app /usr/local/bin/inventory-app
sudo chmod +x /usr/local/bin/inventory-app

# Create systemd service
sudo tee /etc/systemd/system/inventory.service > /dev/null <<EOF
[Unit]
Description=Inventory System
After=network.target

[Service]
Type=simple
User=inventory
Group=inventory
WorkingDirectory=/var/lib/inventory
Environment=INVENTORY_APP_DIR=/var/lib/inventory
Environment=INVENTORY_SECRET_KEY=your-secret-key
Environment=INVENTORY_API_KEY=your-api-key
ExecStart=/usr/local/bin/inventory-app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable inventory
sudo systemctl start inventory
```

### 2. Docker Deployment

Best for:
- Containerized environments
- Kubernetes deployments
- Scalable architectures

```bash
# Build image
python deploy.py docker

# Run with docker-compose
cat > docker-compose.yml <<EOF
version: '3.8'

services:
  inventory:
    image: inventory-system:latest
    ports:
      - "8000:8000"
    volumes:
      - inventory_data:/var/lib/inventory
    environment:
      - INVENTORY_SECRET_KEY=your-secret-key
      - INVENTORY_API_KEY=your-api-key
      - INVENTORY_BASIC_USER=admin
      - INVENTORY_BASIC_PASS=your-password
    restart: unless-stopped

volumes:
  inventory_data:
EOF

# Start services
docker-compose up -d
```

### 3. Cloud Deployment

#### AWS ECS
```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker tag inventory-system:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/inventory:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/inventory:latest
```

#### Google Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/PROJECT-ID/inventory
gcloud run deploy --image gcr.io/PROJECT-ID/inventory --platform managed
```

## Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Database Statistics
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/admin/stats
```

### Log Monitoring
```bash
# View application logs
tail -f /var/lib/inventory/app.log

# View system logs (systemd)
sudo journalctl -u inventory -f
```

## Backup and Recovery

### Database Backup
```bash
# Backup database
cp /var/lib/inventory/db.sqlite3 /backup/inventory-$(date +%Y%m%d).sqlite3

# Automated backup script
cat > /usr/local/bin/backup-inventory.sh <<EOF
#!/bin/bash
BACKUP_DIR="/backup/inventory"
mkdir -p "\$BACKUP_DIR"
cp /var/lib/inventory/db.sqlite3 "\$BACKUP_DIR/inventory-$(date +%Y%m%d_%H%M%S).sqlite3"
find "\$BACKUP_DIR" -name "*.sqlite3" -mtime +30 -delete
EOF

chmod +x /usr/local/bin/backup-inventory.sh

# Add to crontab
echo "0 2 * * * /usr/local/bin/backup-inventory.sh" | crontab -
```

### Restore from Backup
```bash
# Stop service
sudo systemctl stop inventory

# Restore database
cp /backup/inventory-YYYYMMDD.sqlite3 /var/lib/inventory/db.sqlite3
chown inventory:inventory /var/lib/inventory/db.sqlite3

# Start service
sudo systemctl start inventory
```

## Troubleshooting

### Common Issues

1. **Database locked errors**
   - Increase busy timeout in configuration
   - Check for long-running transactions
   - Consider using PostgreSQL for high concurrency

2. **Memory usage high**
   - Adjust connection pool settings
   - Monitor for memory leaks
   - Consider increasing system RAM

3. **Slow performance**
   - Check database indexes
   - Monitor query performance
   - Consider caching strategies

### Log Analysis
```bash
# View slow queries
grep "Slow query" /var/lib/inventory/app.log

# View error logs
grep "ERROR" /var/lib/inventory/app.log

# View access patterns
grep "http.access" /var/lib/inventory/app.log | cut -d'"' -f4 | sort | uniq -c | sort -nr
```

## Performance Tuning

### Database Optimization
```env
# Add to .env for better performance
INVENTORY_DB_POOL_SIZE=20
INVENTORY_DB_MAX_OVERFLOW=30
INVENTORY_DB_POOL_RECYCLE=3600
```

### Application Tuning
```env
# Enable production optimizations
INVENTORY_DEV_MODE=false
INVENTORY_AUDIT_DISABLED=false
```

### System Tuning
```bash
# Increase file descriptor limit
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize kernel parameters for SQLite
echo "vm.swappiness=10" >> /etc/sysctl.conf
echo "vm.vfs_cache_pressure=50" >> /etc/sysctl.conf
sysctl -p
```