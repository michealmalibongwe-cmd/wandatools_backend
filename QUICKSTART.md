# WandaTools Backend - Quick Start Guide

Get the backend running in 5 minutes!

---

## ⚡ 5-Minute Setup

### 1. Prerequisites (1 min)
```bash
# Check Python installed
python --version  # Should be 3.10+

# Check PostgreSQL installed
psql --version    # Should be 12+
```

Not installed? 
- Python: https://www.python.org/downloads/
- PostgreSQL: https://www.postgresql.org/download/

### 2. Clone/Download (1 min)
```bash
cd wandatools-backend
```

### 3. Run Setup Script (2 min)

**macOS/Linux:**
```bash
bash setup.sh
```

**Windows:**
```bash
setup.bat
```

This will:
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Create .env file from template

### 4. Configure Database (1 min)

```bash
# Create PostgreSQL database
psql -U postgres -c "CREATE DATABASE wandatools_db;"
```

Or with psql prompt:
```bash
psql
CREATE DATABASE wandatools_db;
\q
```

### 5. Start Server (instant)

```bash
# Activate virtual environment (if not done by setup)
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Start server
uvicorn main:app --reload
```

**Server running at:** http://localhost:8000 ✅

---

## 📖 What's Next?

### View API Documentation
Open in browser: **http://localhost:8000/api/docs**

### Test Endpoints
Use `test_requests.http` file:
1. Install VS Code Extension: "REST Client"
2. Open `test_requests.http`
3. Click "Send Request" above each request

### Connect Your Frontend
See `FRONTEND_INTEGRATION.md` for connecting frontend to this backend.

---

## 🚀 Deploy to Production

### One-Click Deploy to Render.com

1. Push code to GitHub:
```bash
git add .
git commit -m "WandaTools backend"
git push origin main
```

2. Go to https://render.com
3. Click "New" → "Web Service"
4. Select your GitHub repository
5. Follow deployment steps in `DEPLOYMENT.md`

**Your live API:** https://wandatools-api.onrender.com

---

## 🔍 Verify Installation

### Test health endpoint
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "version": "1.0.0"
}
```

### Test registration
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "TestPassword123!"
  }'
```

---

## 📁 Project Structure

```
wandatools-backend/
├── main.py                 # FastAPI entry point
├── config.py              # Configuration & environment
├── db.py                  # Database setup
├── security.py            # Authentication & encryption
├── schemas.py             # Request/response validation
├── models/                # Database models
│   ├── user.py           # User & preferences
│   ├── transaction.py    # Transactions
│   ├── document.py       # Documents/reports
│   └── notification.py   # Notifications
├── routes/                # API endpoints
│   ├── auth.py           # Authentication
│   ├── tools.py          # Transactions & dashboard
│   ├── wandaai.py        # AI assistant
│   └── support.py        # Support & contact
├── requirements.txt       # Dependencies
├── .env.example          # Environment template
├── Procfile              # Deployment config
└── README.md             # Full documentation
```

---

## 🔐 Security Checklist

Before deployment:

- [ ] Changed SECRET_KEY in .env
- [ ] Set ENVIRONMENT=production
- [ ] Configured DATABASE_URL for production
- [ ] Added CORS_ORIGINS for your frontend domain
- [ ] Disabled DEBUG mode
- [ ] Environment variables stored securely (not in .env file)

---

## 🛠️ Common Tasks

### Restart Server
```bash
# Press Ctrl+C to stop
# Then run again
uvicorn main:app --reload
```

### View Database
```bash
# Connect to database
psql -U postgres -d wandatools_db

# View tables
\dt

# Exit
\q
```

### Reset Database
```bash
# Drop and recreate
psql -U postgres -c "DROP DATABASE wandatools_db; CREATE DATABASE wandatools_db;"
```

### Generate Strong Secret Key
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 🐛 Troubleshooting

### "Database connection failed"
```
Error: could not connect to server
```
**Solution:**
- Check PostgreSQL is running: `psql --version`
- Verify DATABASE_URL in `.env`
- Create database: `psql -c "CREATE DATABASE wandatools_db;"`

### "ModuleNotFoundError: No module named 'fastapi'"
```
ModuleNotFoundError: No module named 'fastapi'
```
**Solution:**
- Ensure virtual environment is activated
- Run: `pip install -r requirements.txt`

### "Port 8000 already in use"
```
Address already in use
```
**Solution:**
- Kill existing process: `lsof -ti:8000 | xargs kill -9`
- Or use different port: `uvicorn main:app --port 8001`

### "CORS error when calling from frontend"
```
Access to XMLHttpRequest blocked by CORS policy
```
**Solution:**
- Add frontend URL to CORS_ORIGINS in `config.py`
- Restart server
- Check frontend is using correct API URL

---

## 📚 Documentation

- **README.md** - Full setup & configuration
- **API_REFERENCE.md** - All endpoints documented
- **FRONTEND_INTEGRATION.md** - Connect frontend
- **DEPLOYMENT.md** - Deploy to Render.com
- **SECURITY.md** - Security measures explained
- **test_requests.http** - Test API endpoints

---

## 🎯 Next Steps

1. ✅ **Backend running** - You're here!
2. 📱 **Connect frontend** - See FRONTEND_INTEGRATION.md
3. 🚀 **Test end-to-end** - Register, login, create transaction
4. 🌍 **Deploy to production** - See DEPLOYMENT.md
5. 🔐 **Enable advanced security** - See SECURITY.md

---

## 💡 Tips

- Use `http://localhost:8000/api/docs` for interactive API testing
- Install "REST Client" VS Code extension to run `test_requests.http`
- Keep `.env` file in `.gitignore` (never commit secrets)
- Check logs for debugging: `uvicorn main:app --reload`
- Test everything locally before deploying

---

## 🆘 Need Help?

**Common Issues:**
- Check Troubleshooting section above
- Review `README.md` for detailed setup
- See `SECURITY.md` for auth issues
- Check `API_REFERENCE.md` for endpoint documentation

**Stuck?**
1. Check error message carefully
2. Google the error message
3. Review relevant documentation file
4. Check API logs: `http://localhost:8000/api/docs`

---

## ✨ You're All Set!

Your backend is ready. Now:

1. Test with: http://localhost:8000/api/docs
2. Integrate frontend: See `FRONTEND_INTEGRATION.md`
3. Deploy: See `DEPLOYMENT.md`

**Happy building! 🎉**

---

**Questions?** Check the full `README.md` or `SECURITY.md` for more details.
