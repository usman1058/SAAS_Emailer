# Deployment Guide

## Quick Start with Docker Compose

### Prerequisites
- Docker and Docker Compose installed
- Domain name (for production)
- SMTP credentials (Gmail App Password or other)

### 1. Clone and Configure
```bash
git clone <your-repo>
cd SAAS_Emailer

# Copy environment template
cp .env.docker.example .env

# Edit .env with your values
# - Generate SECRET_KEY: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# - Set ALLOWED_HOSTS to your domain(s)
# - Configure DATABASE_URL (default uses postgres service)
# - Set EMAIL_* for SMTP
# - Set OSM_CONTACT_EMAIL for lead finder
```

### 2. Build and Start
```bash
docker-compose up -d --build
```

### 3. Run Migrations
```bash
docker-compose exec web python manage.py migrate
```

### 4. Create Superuser (Optional)
```bash
docker-compose exec web python manage.py createsuperuser
```

### 5. Access Application
- Main app: http://localhost:8000/
- Admin: http://localhost:8000/admin/
- Lead Finder: http://localhost:8000/leads/

## Production Deployment Options

### Option 1: Docker on VPS (DigitalOcean, Linode, etc.)
1. Provision a server with Docker installed
2. Configure firewall (ports 80, 443, 22)
3. Set up reverse proxy (Nginx/Traefik) for SSL
4. Use `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### Option 2: Render / Railway / Fly.io
These platforms support Docker natively:
1. Connect your GitHub repo
2. Add environment variables
3. Deploy

### Option 3: Traditional VPS with systemd
1. Install Python 3.13, PostgreSQL, Redis, Nginx
2. Create virtualenv and install requirements
3. Run migrations
4. Configure Gunicorn + Nginx
5. Set up systemd services for web, celery, celery-beat

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| SECRET_KEY | Yes | - | Django secret key (generate new for production) |
| DEBUG | No | True | Set to False in production |
| ALLOWED_HOSTS | Yes | localhost,127.0.0.1 | Comma-separated hostnames |
| DATABASE_URL | No | sqlite:///db.sqlite3 | PostgreSQL URL for production |
| REDIS_URL | No | redis://localhost:6379/0 | Redis connection string |
| CELERY_BROKER_URL | No | REDIS_URL | Celery broker URL |
| CELERY_RESULT_BACKEND | No | REDIS_URL | Celery result backend |
| EMAIL_BACKEND | No | console | Email backend (smtp/console) |
| EMAIL_HOST | If SMTP | - | SMTP host |
| EMAIL_PORT | If SMTP | 587 | SMTP port |
| EMAIL_USE_TLS | If SMTP | True | Use TLS |
| EMAIL_HOST_USER | If SMTP | - | SMTP username |
| EMAIL_HOST_PASSWORD | If SMTP | - | SMTP password |
| OSM_CONTACT_EMAIL | No | - | Contact email for OSM API |

## SSL/HTTPS Setup

### With Nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
}
```

### Get SSL Certificates
```bash
# Using Let's Encrypt
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Background Tasks (Celery)

The application uses Celery for:
- Long-running lead searches
- Scheduled email sending (future)

### Running Workers
```bash
# Development
celery -A core worker -l info

# Production (with systemd or Docker)
# See docker-compose.yml for service definitions
```

## Monitoring & Logs

### View Logs
```bash
# Docker
docker-compose logs -f web
docker-compose logs -f celery

# Systemd
journalctl -u saas-emailer-web -f
```

### Health Checks
- Web: `GET /` returns 200
- Database: `pg_isready`
- Redis: `redis-cli ping`

## Backup Strategy

### Database Backup
```bash
# Docker
docker-compose exec db pg_dump -U postgres saas_emailer > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T db psql -U postgres saas_emailer < backup_20240101.sql
```

### Media Files Backup
```bash
# Backup uploads and exports
tar -czf media_backup_$(date +%Y%m%d).tar.gz media/
```

## Scaling Considerations

### Horizontal Scaling
- Run multiple `web` instances behind load balancer
- Run multiple `celery` workers
- Use Redis for session storage (configure `SESSION_ENGINE`)

### Database Optimization
- Add indexes on frequently queried fields (already in models)
- Consider read replicas for heavy read workloads
- Monitor query performance with `django-debug-toolbar` in dev

### Rate Limiting
- Configure `django-ratelimit` for API endpoints
- Set up Nginx rate limiting for DDoS protection

## Troubleshooting

### Common Issues

1. **Static files not loading**
   - Run `python manage.py collectstatic`
   - Check `STATIC_ROOT` and `STATIC_URL`

2. **Database connection errors**
   - Verify `DATABASE_URL` format
   - Check PostgreSQL is running and accessible

3. **Email not sending**
   - Verify SMTP credentials
   - Check Gmail App Password (not regular password)
   - Test with `EMAIL_BACKEND=console` first

4. **Lead search not working**
   - Check OSM API availability
   - Verify `OSM_CONTACT_EMAIL` is set
   - Check network connectivity to Overpass/Nominatim

5. **Celery tasks not running**
   - Verify Redis is running
   - Check worker logs: `docker-compose logs celery`
   - Ensure tasks are imported in `core/celery.py`

## Security Checklist

- [ ] Generate new `SECRET_KEY` for production
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS` correctly
- [ ] Use PostgreSQL (not SQLite) in production
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Set secure cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)
- [ ] Configure CSP headers (already in settings)
- [ ] Use strong database passwords
- [ ] Limit database access (firewall)
- [ ] Regular security updates
- [ ] Monitor for suspicious activity
- [ ] Set up automated backups