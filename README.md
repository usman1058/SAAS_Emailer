# SAAS Emailer - Bulk Email Sender & Lead Finder

A Django-based SaaS application for sending personalized bulk emails and finding business leads without websites using OpenStreetMap data.

## 🚀 Features

### Email Sender
- ✅ Send bulk emails using Excel (.xlsx) files
- ✅ Personalize emails with `{{name}}` placeholder
- ✅ Optional file attachments (PDF, images, documents)
- ✅ Duplicate prevention via SHA256 hashing
- ✅ Real-time kill switch to stop sending
- ✅ Automatic SMTP reconnection on failure
- ✅ Gmail SMTP support with App Passwords
- ✅ Job tracking with progress monitoring
- ✅ Responsive Bootstrap 5 UI with real-time logs

### Lead Finder (Website Gap Finder)
- ✅ Find local businesses via OpenStreetMap (Nominatim + Overpass API)
- ✅ No API keys required - completely free
- ✅ Identify businesses without websites
- ✅ Phone number classification (mobile vs landline) via libphonenumber
- ✅ WhatsApp wa.me links for mobile numbers
- ✅ Export to CSV, Excel (multi-sheet), and interactive HTML reports
- ✅ Priority leads: no website + mobile number
- ✅ Management command for CLI usage
- ✅ Web UI with filtering and pagination

## 📦 Tech Stack

- **Backend**: Django 5.2, Python 3.13
- **Data**: pandas, openpyxl (Excel), phonenumbers (phone validation)
- **Database**: SQLite (dev), PostgreSQL (production)
- **Cache/Queue**: Redis (Celery broker, kill switch)
- **Frontend**: Bootstrap 5, vanilla JS (streaming logs)
- **Deployment**: Docker, Vercel-ready, GitHub Actions CI

## 🛠 Quick Start

### Local Development

```bash
# Clone and setup
git clone <repo-url>
cd SAAS_Emailer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Visit `http://localhost:8000/` for Email Sender, `http://localhost:8000/leads/` for Lead Finder.

### Docker Development

```bash
# Copy environment template
cp .env.docker.example .env
# Edit .env with your values

# Build and start
docker-compose up -d --build

# Run migrations
docker-compose exec web python manage.py migrate
```

## 📧 Email Sender Usage

1. Navigate to `/` (Email Panel)
2. Fill in:
   - **Sender Email**: Your Gmail address
   - **Sender Password**: Gmail App Password (not regular password)
   - **Subject**: Email subject line
   - **Message**: Email body with `{{name}}` placeholder
   - **Excel File**: Must have "Email" column, optional "Name" column
   - **Attachment**: Optional (PDF, PNG, JPG, DOC, etc. max 10MB)
3. Click **🚀 Send Emails**
4. Monitor real-time logs in the side panel
5. Use **⛔ Kill Switch** to stop anytime

### Excel Format Example
```csv
Email,Name
john@example.com,John Smith
jane@example.com,Jane Doe
bob@example.com,Bob Wilson
```

## 🔍 Lead Finder Usage

### Web UI
1. Navigate to `/leads/`
2. Enter city (e.g., "Leeds"), optional country (e.g., "UK")
3. Enter comma-separated categories (e.g., "plumber, electrician, cafe")
4. Click **🔍 Search for Leads**
5. Filter results: All / No Website / Has Website / Mobile Only
6. Export: CSV / Excel / HTML Report

### CLI (Management Command)
```bash
python manage.py find_leads \
    --city "Leeds" \
    --country "UK" \
    --categories plumber electrician "hair salon" cafe \
    --output leeds_leads \
    --email your-email@example.com
```

Outputs:
- `leeds_leads_all.csv` - All businesses
- `leeds_leads_no_website.csv` - No website leads
- `leeds_leads_priority.csv` - No website + mobile
- `leeds_leads.xlsx` - Excel with 4 sheets
- `leeds_leads_report.html` - Interactive report

### Supported Categories
Plumber, electrician, hair salon, cafe, restaurant, dentist, lawyer, gym, car repair, and many more. See `leads/services/osm_client.py` for full list.

## 🌐 Vercel Deployment

### Prerequisites
- Vercel account
- PostgreSQL database (Neon, Supabase, Vercel Postgres)
- Redis for Celery (Upstash, Redis Cloud)
- SMTP credentials (Gmail App Password)

### Deploy Steps

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Ready for Vercel deployment"
   git push origin main
   ```

2. **Import in Vercel**
   - New Project → Import Git Repository
   - Framework Preset: Django
   - Root Directory: `./`

3. **Configure Environment Variables**
   ```
   SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
   DEBUG=False
   ALLOWED_HOSTS=<your-domain>.vercel.app
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://...
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=True
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password
   OSM_CONTACT_EMAIL=your-email@example.com
   ```

4. **Deploy**
   - Vercel will auto-detect `vercel.json` and build

### Vercel Limitations & Workarounds
- **No persistent storage**: Use external PostgreSQL + Redis
- **No Celery workers**: Lead search runs synchronously (use CLI for large searches)
- **Ephemeral /tmp**: Media files stored in `/tmp/media` (use S3 for persistence)
- **30s timeout**: Email sending limited to small batches

## 🐳 Production Deployment (Docker)

```bash
# Configure production environment
cp .env.docker.example .env
# Edit .env with production values

# Deploy with Docker Compose
docker-compose -f docker-compose.yml up -d --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

See `DEPLOYMENT.md` for detailed production deployment guide.

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=main --cov=leads --cov-report=html

# Lint
ruff check .

# Format
black .

# Type check
mypy .
```

## 📁 Project Structure

```
SAAS_Emailer/
├── api/index.py              # Vercel entry point
├── core/                     # Django project config
│   ├── settings.py           # Main settings (Vercel-aware)
│   ├── urls.py               # URL routing
│   └── wsgi.py               # WSGI entry
├── main/                     # Email Sender app
│   ├── models.py             # SendJob, SentEmailHash
│   ├── forms.py              # Validated EmailForm
│   ├── views.py              # Streaming email send
│   ├── services/email_sender.py  # Service layer
│   └── templates/send_emails.html
├── leads/                    # Lead Finder app
│   ├── models.py             # SearchJob, Lead, ExportFile
│   ├── services/
│   │   ├── osm_client.py     # Nominatim + Overpass
│   │   ├── phone_classifier.py # libphonenumber
│   │   └── exporters.py      # CSV/Excel/HTML
│   ├── management/commands/find_leads.py
│   ├── views.py              # Search, results, export
│   └── templates/leads/
├── tests/                    # Unit/integration tests
├── .github/workflows/ci.yml  # GitHub Actions
├── docker-compose.yml        # Full stack
├── Dockerfile                # Production image
├── vercel.json               # Vercel config
├── requirements.txt          # Pinned dependencies
└── DEPLOYMENT.md             # Deployment guide
```

## 🔒 Security Notes

- Never commit `.env` or secrets
- Use Gmail App Passwords, not regular passwords
- Generate new `SECRET_KEY` for production
- Set `DEBUG=False` and `ALLOWED_HOSTS` in production
- Use HTTPS (Vercel provides automatically)
- Regular dependency updates via Dependabot

## 📄 License

MIT License - feel free to use for your projects.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Run tests and linting
4. Submit PR

## 📞 Support

For issues, check:
- `DEPLOYMENT.md` for deployment troubleshooting
- GitHub Issues for bugs
- Django docs for framework questions