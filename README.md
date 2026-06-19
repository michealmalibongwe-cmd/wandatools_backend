# WandaTools Backend API

AI-powered financial management system backend built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy**.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 12+
- pip (Python package manager)

### Installation

1. **Clone/download the repository**
   ```bash
   cd wandatools-backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your configuration:
   ```env
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/wandatools_db
   
   # Security
   SECRET_KEY=your-super-secret-key-min-32-characters-long!
   
   # Environment
   ENVIRONMENT=development
   DEBUG=true
   ```

5. **Create database**
   ```bash
   # Log into PostgreSQL
   psql
   CREATE DATABASE wandatools_db;
   \q
   ```

6. **Run migrations** (if using Alembic)
   ```bash
   alembic upgrade head
   ```

7. **Start server**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

Server will be available at: **http://localhost:8000**
- API Docs: **http://localhost:8000/api/docs** (Swagger UI)
- ReDoc: **http://localhost:8000/api/redoc** (Alternative docs)

---

## 📋 API Endpoints

### Authentication
- `POST /api/v1/auth/register` — Register new user
- `POST /api/v1/auth/login` — Login user
- `POST /api/v1/auth/refresh` — Refresh access token
- `GET /api/v1/auth/me` — Get current user
- `PUT /api/v1/auth/profile` — Update profile
- `POST /api/v1/auth/change-password` — Change password
- `DELETE /api/v1/auth/account` — Delete account

### Transactions & Dashboard
- `POST /api/v1/tools/transactions` — Create transaction
- `GET /api/v1/tools/transactions` — List transactions (paginated)
- `GET /api/v1/tools/transactions/{id}` — Get transaction
- `PUT /api/v1/tools/transactions/{id}` — Update transaction
- `DELETE /api/v1/tools/transactions/{id}` — Delete transaction
- `GET /api/v1/tools/dashboard/summary` — Get monthly summary
- `GET /api/v1/tools/dashboard/history` — Get multi-month history

### Documents
- `POST /api/v1/tools/documents` — Generate document
- `GET /api/v1/tools/documents` — List documents
- `GET /api/v1/tools/documents/{id}` — Get document
- `DELETE /api/v1/tools/documents/{id}` — Delete document

### WandaAI
- `POST /api/v1/wandaai/query` — Ask AI question
- `GET /api/v1/wandaai/modes` — Get AI modes
- `GET /api/v1/wandaai/prompts` — Get sample prompts

### Support
- `POST /api/v1/support/contact` — Submit contact form
- `GET /api/v1/support/faq` — Get FAQ items
- `GET /api/v1/support/status` — Get support status
- `GET /api/v1/support/health` — System health

---

## 🔐 Security Features

✅ **Password Security**
- bcrypt hashing with automatic salt
- Password strength validation
- Minimum 8 characters (configurable)
- Requires numbers and special characters

✅ **JWT Authentication**
- Access tokens (24-hour expiration)
- Refresh tokens (7-day expiration)
- Token signature verification
- Automatic expiration checks

✅ **CORS Protection**
- Whitelist allowed origins
- No credentials from untrusted domains
- Configurable in `config.py`

✅ **Database Security**
- SQL injection prevention (SQLAlchemy ORM)
- Connection pooling with health checks
- Parameterized queries

✅ **Input Validation**
- Pydantic schemas validate all requests
- Email validation
- Type checking
- Range validation (amounts, dates, etc.)

---

## 📦 Database Models

### Users
```
id | name | email | password_hash | business_type | timezone | is_active | is_verified | created_at | updated_at | last_login
```

### Transactions
```
id | user_id | type | amount | category | description | reference_id | transaction_date | created_at | updated_at | notes | is_recurring | tax_deductible
```

### Documents
```
id | user_id | type | status | filename | file_path | file_url | total_revenue | total_expenses | net_profit | created_at | downloaded_at | expires_at
```

### Notifications
```
id | user_id | type | status | title | message | icon | action_url | created_at | read_at | is_important | send_email | send_sms
```

---

## 🌐 Frontend Integration

### Request Headers
```javascript
// Authorization header for authenticated endpoints
headers: {
  "Authorization": "Bearer <access_token>",
  "Content-Type": "application/json"
}
```

### Example Fetch Calls

**Login:**
```javascript
const res = await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    email: "user@example.com",
    password: "SecurePassword123!"
  })
});
const data = await res.json();
localStorage.setItem("access_token", data.access_token);
localStorage.setItem("refresh_token", data.refresh_token);
```

**Get Transactions:**
```javascript
const token = localStorage.getItem("access_token");
const res = await fetch("http://localhost:8000/api/v1/tools/transactions?page=1&limit=10", {
  headers: { "Authorization": `Bearer ${token}` }
});
const transactions = await res.json();
```

---

## 🚀 Deployment (Render.com)

### Step 1: Prepare Repository

```bash
# Create .env.production for production settings
# (Don't commit secrets, use Render environment variables)

# Create Procfile for deployment
echo "web: uvicorn main:app --host 0.0.0.0 --port $PORT" > Procfile
```

### Step 2: Deploy to Render

1. Go to https://render.com
2. Create account and connect GitHub
3. Create New → Web Service
4. Select GitHub repo: `wandatools-backend`
5. Configure:
   - **Name**: `wandatools-api`
   - **Environment**: `Python 3.10`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 8000`

### Step 3: Add Database (PostgreSQL)

1. In Render Dashboard → Create → PostgreSQL
2. Set name: `wandatools-db`
3. Connect to web service
4. Copy `DATABASE_URL` from connection info

### Step 4: Set Environment Variables

In Render Dashboard, go to Web Service → Environment:

```env
DATABASE_URL=postgresql://user:pass@hostname:5432/dbname
SECRET_KEY=your-production-secret-key-min-32-chars
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=["https://wandatools.com", "https://www.wandatools.com"]
```

### Step 5: Deploy

```bash
git push origin main
# Render auto-deploys on push
```

Your API is now live at: `https://wandatools-api.onrender.com`

---

## 🔧 Configuration

Edit `config.py` to customize:

```python
# JWT expiration
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_NUMBERS = True
PASSWORD_REQUIRE_SPECIAL = True

# CORS allowed origins
CORS_ORIGINS = ["http://localhost:3000", "https://yourdomain.com"]

# Rate limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 60  # seconds
```

---

## 🧪 Testing

```bash
# Run tests with pytest
pytest

# Test with coverage
pytest --cov=.

# Test specific endpoint
pytest tests/test_auth.py
```

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc7519)

---

## 🐛 Troubleshooting

### "Database connection failed"
- Check PostgreSQL is running: `psql --version`
- Verify `DATABASE_URL` in `.env`
- Create database: `CREATE DATABASE wandatools_db;`

### "Invalid token"
- Ensure `SECRET_KEY` is the same between login and request
- Check token hasn't expired (24-hour window)
- Verify `Authorization: Bearer <token>` format

### CORS errors
- Add frontend URL to `CORS_ORIGINS` in `config.py`
- Restart server: `uvicorn main:app --reload`

---

## 📝 License

© 2025 WandaTools. All rights reserved.

---

## 👥 Support

Email: support@wandatools.com
Phone: +27 (0) 76 469 3531
