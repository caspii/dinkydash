# Quickstart Guide: DinkyDash Multi-Tenant Web Application

**Feature**: 001-multitenant-rewrite
**Date**: 2025-12-04
**Purpose**: Setup, deployment, and operations guide for both local (SQLite/Pi) and cloud (PostgreSQL) environments

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup (SQLite)](#local-development-setup-sqlite)
3. [Raspberry Pi Deployment (SQLite)](#raspberry-pi-deployment-sqlite)
4. [Cloud Deployment (PostgreSQL)](#cloud-deployment-postgresql)
5. [Environment Configuration](#environment-configuration)
6. [Database Migrations](#database-migrations)
7. [Backup and Restore](#backup-and-restore)
8. [Troubleshooting](#troubleshooting)
9. [Operations and Monitoring](#operations-and-monitoring)

---

## Prerequisites

### All Environments

- **Python**: 3.11 or higher
- **Git**: For version control
- **Virtual environment**: `venv` or `virtualenv`

### Raspberry Pi Specific

- **Raspberry Pi**: Model 4 or newer (4GB RAM recommended)
- **OS**: Raspberry Pi OS (Debian-based) or Ubuntu Server
- **Nginx**: For reverse proxy
- **Systemd**: For service management (included in modern Linux distributions)

### Cloud Specific

- **PostgreSQL**: 14 or higher (managed service recommended: AWS RDS, DigitalOcean, Heroku Postgres)
- **Server**: Linux server with SSH access (DigitalOcean Droplet, AWS EC2, etc.)
- **Domain**: Optional but recommended for production

---

## Local Development Setup (SQLite)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/dinkydash.git
cd dinkydash
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt** (to be created):
```text
Flask==3.0.0
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-Migrate==4.0.5
SQLAlchemy==2.0.23
Werkzeug==3.0.1
Pillow==10.1.0
python-dotenv==1.0.0
WTForms==3.1.1
```

**requirements-dev.txt** (for development):
```text
pytest==7.4.3
pytest-flask==1.3.0
pytest-cov==4.1.0
black==23.11.0
flake8==6.1.0
```

### 4. Create Environment File

Create `.env` file in project root:

```bash
cp .env.example .env
```

**.env** (local development):
```bash
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///dinkydash-dev.db
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=5242880  # 5MB in bytes
```

### 5. Initialize Database

```bash
# Initialize migration repository (first time only)
flask db init

# Generate initial migration from models
flask db migrate -m "Initial schema"

# Apply migration to database
flask db upgrade
```

This creates `dinkydash-dev.db` in project root.

### 6. Run Development Server

```bash
flask run
# or
python app.py
```

Application runs at `http://localhost:5000`

### 7. Create First Account

Navigate to `http://localhost:5000/register` and create your family account.

---

## Raspberry Pi Deployment (SQLite)

### 1. Prepare Raspberry Pi

**Update system**:
```bash
sudo apt update
sudo apt upgrade -y
```

**Install dependencies**:
```bash
# Python 3.11+ (if not available via apt, use pyenv)
sudo apt install python3 python3-pip python3-venv -y

# Nginx for reverse proxy
sudo apt install nginx -y

# Emoji font support
sudo apt install fonts-noto-color-emoji -y

# Hide mouse cursor (optional, for kiosk mode)
sudo apt install unclutter -y
```

**Rotate display 180° (optional)**:
Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
```
Add line:
```
lcd_rotate=2
```
Reboot: `sudo reboot`

### 2. Clone and Setup Application

```bash
# Clone to home directory
cd ~
git clone https://github.com/yourusername/dinkydash.git
cd dinkydash

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Create `.env` file:
```bash
nano .env
```

**Content**:
```bash
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)  # Generate secure key
DATABASE_URL=sqlite:///dinkydash.db
UPLOAD_FOLDER=/home/pi/dinkydash/static/uploads
MAX_CONTENT_LENGTH=5242880
```

**Generate secure secret key**:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
Copy output to `SECRET_KEY` in `.env`.

### 4. Initialize Database

```bash
source venv/bin/activate
export FLASK_APP=dinkydash

# Apply migrations (creates SQLite database)
flask db upgrade
```

### 5. Configure Gunicorn (WSGI Server)

Install Gunicorn:
```bash
pip install gunicorn
```

Create Gunicorn config `gunicorn_config.py`:
```python
# gunicorn_config.py
bind = "127.0.0.1:8000"
workers = 2  # Pi has limited resources, 2 workers sufficient
worker_class = "sync"
timeout = 120
accesslog = "/home/pi/dinkydash/logs/access.log"
errorlog = "/home/pi/dinkydash/logs/error.log"
loglevel = "info"
```

Create logs directory:
```bash
mkdir -p /home/pi/dinkydash/logs
```

### 6. Create Systemd Service

Create service file:
```bash
sudo nano /etc/systemd/system/dinkydash.service
```

**Content**:
```ini
[Unit]
Description=DinkyDash Family Dashboard
After=network.target

[Service]
Type=notify
User=pi
Group=pi
WorkingDirectory=/home/pi/dinkydash
Environment="PATH=/home/pi/dinkydash/venv/bin"
ExecStart=/home/pi/dinkydash/venv/bin/gunicorn -c gunicorn_config.py "dinkydash:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dinkydash.service
sudo systemctl start dinkydash.service

# Check status
sudo systemctl status dinkydash.service
```

### 7. Configure Nginx Reverse Proxy

Create Nginx config:
```bash
sudo nano /etc/nginx/sites-available/dinkydash
```

**Content**:
```nginx
server {
    listen 80;
    server_name localhost;  # Or your Pi's IP address or domain

    # Serve static files directly (images, CSS)
    location /static/ {
        alias /home/pi/dinkydash/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy application requests to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }

    # Increase timeout for long-polling (HTMX)
    proxy_read_timeout 90s;
    proxy_connect_timeout 90s;
}
```

**Enable site**:
```bash
sudo ln -s /etc/nginx/sites-available/dinkydash /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

### 8. Access Application

Navigate to `http://<pi-ip-address>` from browser on local network.

**Find Pi's IP address**:
```bash
hostname -I
```

### 9. Auto-start on Boot

Systemd service is already configured to start on boot. Verify:
```bash
sudo systemctl is-enabled dinkydash.service
# Should output: enabled
```

### 10. Kiosk Mode (Optional)

To auto-launch browser in fullscreen on Pi:

**Install Chromium**:
```bash
sudo apt install chromium-browser -y
```

**Edit autostart**:
```bash
mkdir -p ~/.config/lxsession/LXDE-pi
nano ~/.config/lxsession/LXDE-pi/autostart
```

**Add lines**:
```
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.5 -root
@chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost
```

Reboot Pi. Browser launches in fullscreen displaying dashboard.

---

## Cloud Deployment (PostgreSQL)

### 1. Provision Server and Database

**Server options**:
- DigitalOcean Droplet (Ubuntu 22.04, $6/month)
- AWS EC2 (t3.micro or t3.small)
- Heroku (includes PostgreSQL add-on)
- Fly.io, Railway.app (Docker-based)

**Database options**:
- DigitalOcean Managed PostgreSQL ($15/month)
- AWS RDS PostgreSQL
- Heroku Postgres (free tier available)
- Supabase (PostgreSQL with free tier)

**Requirements**:
- PostgreSQL 14+
- 1GB RAM minimum (2GB recommended for 50+ families)
- 20GB storage

### 2. Provision PostgreSQL Database

Example: DigitalOcean Managed Database

1. Create database via control panel
2. Create database user with full permissions
3. Whitelist server IP address
4. Note connection details:
   - Host: `db-postgresql-nyc3-12345.ondigitalocean.com`
   - Port: `25060`
   - Database: `dinkydash`
   - User: `doadmin`
   - Password: `<generated-password>`

**Connection string format**:
```
postgresql://user:password@host:port/database?sslmode=require
```

### 3. Setup Server

**Connect via SSH**:
```bash
ssh root@<server-ip>
```

**Create application user**:
```bash
adduser dinkydash
usermod -aG sudo dinkydash
su - dinkydash
```

**Install dependencies**:
```bash
sudo apt update
sudo apt install python3.11 python3-pip python3-venv nginx git -y
```

### 4. Clone and Setup Application

```bash
cd ~
git clone https://github.com/yourusername/dinkydash.git
cd dinkydash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install PostgreSQL adapter
pip install psycopg2-binary
```

### 5. Configure Environment

Create `.env`:
```bash
nano .env
```

**Content**:
```bash
FLASK_ENV=production
SECRET_KEY=<generate-with-openssl-rand>
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require
UPLOAD_FOLDER=/home/dinkydash/dinkydash/static/uploads
MAX_CONTENT_LENGTH=5242880
```

**Generate secret key**:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 6. Initialize Database

```bash
source venv/bin/activate
export FLASK_APP=dinkydash

# Run migrations (creates tables in PostgreSQL)
flask db upgrade
```

### 7. Configure Gunicorn

Install Gunicorn:
```bash
pip install gunicorn
```

Create `gunicorn_config.py`:
```python
bind = "127.0.0.1:8000"
workers = 4  # Adjust based on CPU cores (2 * cores + 1)
worker_class = "sync"
timeout = 120
accesslog = "/home/dinkydash/dinkydash/logs/access.log"
errorlog = "/home/dinkydash/dinkydash/logs/error.log"
loglevel = "info"
```

Create logs directory:
```bash
mkdir -p logs
```

### 8. Create Systemd Service

```bash
sudo nano /etc/systemd/system/dinkydash.service
```

**Content** (adjust paths for user `dinkydash`):
```ini
[Unit]
Description=DinkyDash Family Dashboard
After=network.target

[Service]
Type=notify
User=dinkydash
Group=dinkydash
WorkingDirectory=/home/dinkydash/dinkydash
Environment="PATH=/home/dinkydash/dinkydash/venv/bin"
ExecStart=/home/dinkydash/dinkydash/venv/bin/gunicorn -c gunicorn_config.py "dinkydash:create_app()"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable dinkydash.service
sudo systemctl start dinkydash.service
sudo systemctl status dinkydash.service
```

### 9. Configure Nginx with SSL

**Install Certbot for SSL**:
```bash
sudo apt install certbot python3-certbot-nginx -y
```

**Create Nginx config**:
```bash
sudo nano /etc/nginx/sites-available/dinkydash
```

**Content** (replace `yourdomain.com`):
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location /static/ {
        alias /home/dinkydash/dinkydash/static/;
        expires 1d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }

    client_max_body_size 5M;  # Match MAX_CONTENT_LENGTH
    proxy_read_timeout 90s;
    proxy_connect_timeout 90s;
}
```

**Enable site**:
```bash
sudo ln -s /etc/nginx/sites-available/dinkydash /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Obtain SSL certificate**:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow prompts. Certbot automatically configures HTTPS and redirects HTTP to HTTPS.

### 10. Access Application

Navigate to `https://yourdomain.com`

---

## Environment Configuration

### Configuration Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_ENV` | Yes | `production` | Environment mode: `development`, `production`, `testing` |
| `SECRET_KEY` | Yes | None | Cryptographic secret for sessions (32-byte hex) |
| `DATABASE_URL` | Yes | `sqlite:///dinkydash.db` | Database connection string |
| `UPLOAD_FOLDER` | No | `static/uploads` | Path for uploaded images |
| `MAX_CONTENT_LENGTH` | No | `5242880` | Max upload size in bytes (5MB) |

### Database URL Formats

**SQLite** (local/Pi):
```
sqlite:///dinkydash.db  # Relative path (current directory)
sqlite:////absolute/path/dinkydash.db  # Absolute path (note 4 slashes)
```

**PostgreSQL** (cloud):
```
postgresql://user:password@host:port/database
postgresql://user:password@host:port/database?sslmode=require  # With SSL
```

### Configuration Classes

Application uses config classes defined in `config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///dinkydash.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'static/uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 5 * 1024 * 1024)
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dinkydash-dev.db'

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
```

Load config in app factory:
```python
def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        env = os.environ.get('FLASK_ENV', 'production')
        config_map = {
            'development': DevelopmentConfig,
            'production': ProductionConfig,
            'testing': TestConfig
        }
        config_class = config_map.get(env, ProductionConfig)

    app.config.from_object(config_class)
    # ... rest of app initialization
```

---

## Database Migrations

### Migration Workflow

**1. Initialize migration repository** (first time only):
```bash
flask db init
```

Creates `migrations/` directory.

**2. Generate migration from model changes**:
```bash
flask db migrate -m "Add user profile picture column"
```

Reviews current models vs database schema, generates migration script in `migrations/versions/`.

**3. Review migration script**:
```bash
cat migrations/versions/<generated_file>.py
```

**Always review auto-generated migrations** before applying. Check:
- Correct table/column changes
- No accidental data loss (e.g., column drops)
- Proper foreign key constraints

**4. Apply migration**:
```bash
flask db upgrade
```

**5. Rollback migration** (if needed):
```bash
flask db downgrade
```

### Testing Migrations

**Test on SQLite**:
```bash
export DATABASE_URL=sqlite:///test-migration.db
flask db upgrade
# Verify schema, then delete test database
rm test-migration.db
```

**Test on PostgreSQL**:
```bash
export DATABASE_URL=postgresql://user:pass@localhost/test_db
flask db upgrade
# Verify schema, then drop test database
```

### Migration Best Practices

- **Always review** auto-generated migrations
- **Test upgrade and downgrade** paths
- **Test on both SQLite and PostgreSQL** before production
- **Backup database** before applying migrations in production
- **Don't edit applied migrations** (create new migration instead)
- **Document breaking changes** in migration message

### Production Migration Process

**SQLite (Pi)**:
```bash
# Backup database
cp dinkydash.db dinkydash.db.backup

# Apply migration
source venv/bin/activate
flask db upgrade

# Restart application
sudo systemctl restart dinkydash.service
```

**PostgreSQL (Cloud)**:
```bash
# Backup database (via cloud provider UI or pg_dump)
pg_dump -h host -U user -d database > backup.sql

# Apply migration
source venv/bin/activate
flask db upgrade

# Restart application
sudo systemctl restart dinkydash.service
```

---

## Backup and Restore

### SQLite Backups (Pi)

**Manual backup**:
```bash
cp /home/pi/dinkydash/dinkydash.db /home/pi/backups/dinkydash-$(date +%Y%m%d).db
```

**Automated daily backup** (cron):
```bash
crontab -e
```

Add line:
```
0 2 * * * cp /home/pi/dinkydash/dinkydash.db /home/pi/backups/dinkydash-$(date +\%Y\%m\%d).db
```

Runs daily at 2 AM.

**Restore from backup**:
```bash
sudo systemctl stop dinkydash.service
cp /home/pi/backups/dinkydash-20250101.db /home/pi/dinkydash/dinkydash.db
sudo systemctl start dinkydash.service
```

### PostgreSQL Backups (Cloud)

**Managed database backups**:
Most cloud providers (DigitalOcean, AWS RDS) include automatic daily backups. Configure via provider UI.

**Manual backup with pg_dump**:
```bash
pg_dump -h host -U user -d database > dinkydash-backup-$(date +%Y%m%d).sql
```

**Restore from backup**:
```bash
psql -h host -U user -d database < dinkydash-backup-20250101.sql
```

**Backup uploaded images**:
```bash
# SQLite (Pi)
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz static/uploads/

# PostgreSQL (Cloud)
rsync -avz dinkydash@server:/home/dinkydash/dinkydash/static/uploads/ ./uploads-backup/
```

### Backup Schedule Recommendations

- **Daily**: Database backup
- **Weekly**: Full system backup (database + uploaded images)
- **Before migrations**: Always backup before applying schema changes
- **Retention**: Keep 30 daily backups, 12 weekly backups

---

## Troubleshooting

### Application Won't Start

**Check service status**:
```bash
sudo systemctl status dinkydash.service
```

**View logs**:
```bash
sudo journalctl -u dinkydash.service -n 50
```

**Common issues**:
- **Module not found**: Activate virtual environment, reinstall dependencies
- **Database locked** (SQLite): Stop service, check for stale connections
- **Port already in use**: Change port in `gunicorn_config.py`

### Database Connection Errors

**SQLite**:
- Check file permissions: `ls -la dinkydash.db`
- Ensure database file exists: `flask db upgrade`

**PostgreSQL**:
- Verify connection string in `.env`
- Check firewall rules (database must allow server IP)
- Test connection: `psql $DATABASE_URL`

### Image Uploads Fail

**Check upload folder permissions**:
```bash
ls -la static/uploads/
```

Should be writable by application user:
```bash
sudo chown -R dinkydash:dinkydash static/uploads/
chmod 755 static/uploads/
```

**Check max file size**:
- Flask config: `MAX_CONTENT_LENGTH`
- Nginx config: `client_max_body_size`

### HTMX Polling Not Working

**Check browser console** for JavaScript errors.

**Verify HTMX loaded**:
- View page source, check `<script src="https://unpkg.com/htmx.org@1.9.10"></script>`

**Verify polling endpoint**:
```bash
curl -H "HX-Request: true" http://localhost:5000/dashboard/1/content
```

Should return partial HTML.

### Performance Issues

**SQLite (Pi)**:
- Check disk I/O: `iostat -x 1 10`
- Reduce Gunicorn workers if memory constrained
- Check database size: `ls -lh dinkydash.db`

**PostgreSQL (Cloud)**:
- Check database connection pool size
- Monitor slow queries via cloud provider UI
- Add indexes for frequently queried columns (see `data-model.md`)

### Session Timeouts

Users logged out frequently:

- Check `PERMANENT_SESSION_LIFETIME` in config (default 30 min)
- Increase timeout: `PERMANENT_SESSION_LIFETIME = 3600` (1 hour)
- Verify `SECRET_KEY` is consistent (restart clears sessions if key changes)

---

## Operations and Monitoring

### Service Management

**Start/stop/restart**:
```bash
sudo systemctl start dinkydash.service
sudo systemctl stop dinkydash.service
sudo systemctl restart dinkydash.service
```

**View status**:
```bash
sudo systemctl status dinkydash.service
```

**View logs**:
```bash
# Application logs (systemd)
sudo journalctl -u dinkydash.service -f  # Follow logs

# Gunicorn logs (if configured)
tail -f logs/access.log
tail -f logs/error.log

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Health Monitoring

**Health check endpoint** (to be implemented):
```python
@app.route('/health')
def health():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        return {'status': 'healthy'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 503
```

**Monitor endpoint**:
```bash
curl http://localhost:5000/health
```

**Setup monitoring** (optional):
- UptimeRobot (free tier): Monitors HTTP endpoint every 5 minutes
- Netdata (self-hosted): Real-time performance monitoring
- Cloud provider monitoring (AWS CloudWatch, DigitalOcean Monitoring)

### Performance Metrics

**Track key metrics**:
- **Response time**: Dashboard page load <3s (success criteria)
- **Database query time**: <500ms for polling endpoint
- **Memory usage**: <512MB per Gunicorn worker (Pi constraint)
- **Concurrent users**: Support 50+ families (success criteria)

**Monitor with Netdata** (Pi):
```bash
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

Access dashboard: `http://<pi-ip>:19999`

### Updating Application

**Pull latest code**:
```bash
cd /home/dinkydash/dinkydash  # Or /home/pi/dinkydash
git pull origin main
```

**Install new dependencies** (if any):
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Apply migrations** (if any):
```bash
flask db upgrade
```

**Restart service**:
```bash
sudo systemctl restart dinkydash.service
```

### Zero-Downtime Updates (Cloud)

For production cloud deployments with multiple workers:

1. **Blue-green deployment**: Run two instances, switch traffic via load balancer
2. **Rolling restart**: Restart Gunicorn workers one at a time (not supported by systemd, requires custom orchestration)

For MVP, brief downtime (<30s) during restart is acceptable.

---

## Security Checklist

### Before Going to Production

- [ ] Change `SECRET_KEY` from default (use `openssl rand -hex 32`)
- [ ] Set `FLASK_ENV=production` (disables debug mode)
- [ ] Use HTTPS (configure SSL certificate via Certbot)
- [ ] Restrict database access (firewall rules, whitelist server IP)
- [ ] Disable SSH password authentication (use SSH keys only)
- [ ] Configure firewall (allow only ports 22, 80, 443)
- [ ] Set secure cookie flags (`SESSION_COOKIE_SECURE=True` in config)
- [ ] Enable CSRF protection (enabled by default in Flask-WTF)
- [ ] Validate uploaded images with Pillow (implemented in forms)
- [ ] Set up automated backups (daily database + weekly images)

---

## Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy 2.0 Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)
- [Flask-Migrate Documentation](https://flask-migrate.readthedocs.io/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [Certbot Documentation](https://certbot.eff.org/)

---

## Next Steps

After completing setup:

1. **Register first family account** via `/register`
2. **Create dashboard** (auto-created as "Family Dashboard")
3. **Add tasks and countdowns** via admin interface
4. **Customize layout size** for your display (small/medium/large)
5. **Test HTMX polling** (watch dashboard auto-refresh every 30s)
6. **Set up automated backups** (cron for SQLite, cloud provider for PostgreSQL)

For development contribution, see `CLAUDE.md` and `/specs/001-multitenant-rewrite/plan.md`.
