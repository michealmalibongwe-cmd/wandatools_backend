# WandaTools Backend - Deployment Guide

Complete step-by-step guide to deploy your FastAPI backend to Render.com with PostgreSQL database.

---

## 📋 Prerequisites

- GitHub account with repo pushed
- Render.com account (free tier available)
- Credit card for Render (for production databases)

---

## 🚀 Step 1: Prepare Your GitHub Repository

### Create `.gitignore`
```bash
# In wandatools-backend/.gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.env
.env.local
venv/
ENV/
env/
.vscode/
.idea/
*.egg-info/
dist/
build/
.pytest_cache/
```

### Create `Procfile`
```bash
echo "web: uvicorn main:app --host 0.0.0.0 --port \$PORT" > Procfile
```

### Push to GitHub
```bash
git add .
git commit -m "Initial backend commit"
git push origin main
```

---

## 🔧 Step 2: Create PostgreSQL Database on Render

1. **Log in to Render.com**
   - Go to https://render.com
   - Sign up or log in with GitHub

2. **Create PostgreSQL Database**
   - Click "New" → "PostgreSQL"
   - Configure:
     - **Name**: `wandatools-db`
     - **Region**: Select closest to you (e.g., Frankfurt, Singapore)
     - **PostgreSQL Version**: 15
     - **Plan**: Free tier (1GB storage, 100MB/month bandwidth)
   - Click "Create Database"

3. **Save Connection Details**
   - Copy the **Internal Database URL**
   - Example: `postgresql://user:password@dpg-xyz.render.internal:5432/dbname`
   - You'll need this for the web service

---

## 🌐 Step 3: Deploy Web Service

1. **Create Web Service**
   - Click "New" → "Web Service"
   - Select your GitHub repository: `wandatools-backend`
   - Click "Connect"

2. **Configure Service**
   - **Name**: `wandatools-api`
   - **Environment**: `Python 3.10`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn main:app --host 0.0.0.0 --port 8000
     ```
   - **Region**: Same as database (or nearby)
   - **Plan**: Free tier ($0/month)

3. **Set Environment Variables**
   - Click "Advanced" → "Environment"
   - Add variables:
     ```env
     DATABASE_URL=postgresql://user:password@dpg-xyz.render.internal:5432/wandatools_db
     SECRET_KEY=your-super-secret-key-min-32-characters-long!
     ENVIRONMENT=production
     DEBUG=false
     CORS_ORIGINS=["https://wandatools.com","https://www.wandatools.com","https://yourfrontendurl.com"]
     ```

4. **Generate Strong Secret Key**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Copy the output and paste as `SECRET_KEY`

5. **Click "Create Web Service"**

---

## ⏳ Step 4: Wait for Deployment

Render will:
1. Build Docker image
2. Install dependencies
3. Start the application
4. Assign a URL: `https://wandatools-api.onrender.com`

**Check deployment status:**
- Go to "Events" tab
- Watch build logs in real-time
- Should see "Web service is live" when complete

---

## ✅ Step 5: Test Your API

### Health Check
```bash
curl https://wandatools-api.onrender.com/health
```

Response:
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2025-06-18T...",
  "version": "1.0.0"
}
```

### API Documentation
Visit:
```
https://wandatools-api.onrender.com/api/docs
```

### Test Registration
```bash
curl -X POST "https://wandatools-api.onrender.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "password": "TestPassword123!",
    "business_type": "Freelancer"
  }'
```

---

## 🔗 Step 6: Connect Frontend

Update your frontend API configuration:

```javascript
// frontend/utils/api.js
const API_BASE = "https://wandatools-api.onrender.com/api/v1";
```

Also update CORS origins in backend if needed:
- Go to Render Dashboard
- Select `wandatools-api`
- Environment
- Edit `CORS_ORIGINS` to include your frontend URL

---

## 🔐 Security Configuration

### Enable HTTPS
✅ Render automatically provides SSL/TLS certificates

### Set Secure Secrets
In Render Dashboard → Environment:
- `SECRET_KEY` - Strong random key (32+ characters)
- Database credentials - Automatically secure
- `ENVIRONMENT=production` - Disable debug mode

### Database Security
✅ PostgreSQL runs in private network (internal URL)
✅ Automatic daily backups
✅ Connection pooling enabled
✅ SQL injection prevention (ORM)

---

## 📈 Monitoring & Logs

### View Real-time Logs
```bash
# In Render Dashboard
Select wandatools-api → Logs
```

### Common Issues in Logs

**Database Connection Error**
```
psycopg2.OperationalError: could not connect to server
```
**Solution:**
- Verify DATABASE_URL in Environment
- Check PostgreSQL service is running
- Restart web service

**Module Not Found**
```
ModuleNotFoundError: No module named 'fastapi'
```
**Solution:**
- Verify `requirements.txt` is in root directory
- Check build command includes `pip install -r requirements.txt`
- Trigger redeploy with fresh build

**Port Binding Error**
```
Address already in use
```
**Solution:**
- Build command must use `$PORT` variable
- Check Start Command uses `--port 8000` (Render manages mapping)

---

## 🔄 Auto-Deploy on Push

By default, Render auto-deploys when you push to `main` branch.

To disable:
- Render Dashboard → Service Settings
- Toggle "Auto-Deploy" off

To redeploy manually:
- Click "Manual Deploy" → "Deploy latest commit"

---

## 💾 Database Backups

### Automated Backups
✅ Render automatically backs up PostgreSQL daily

### Export Data
```bash
# In your local terminal
pg_dump postgresql://user:password@dpg-xyz.render.internal:5432/wandatools_db > backup.sql
```

### Restore Data
```bash
psql postgresql://user:password@dpg-xyz.render.internal:5432/wandatools_db < backup.sql
```

---

## 📊 Performance Optimization

### Connection Pooling
Already enabled in `config.py`:
```python
pool_size=10,
max_overflow=20,
```

### Add Caching (Future)
```python
# Install redis
pip install redis

# In config.py
REDIS_URL = os.getenv("REDIS_URL")
```

### Enable gzip Compression
```python
# In main.py
from fastapi.middleware.gzip import GZIPMiddleware

app.add_middleware(GZIPMiddleware, minimum_size=1000)
```

---

## 🆓 Free Tier Limits

**Web Service:**
- 0.5 CPU
- 512 MB RAM
- Unlimited bandwidth
- Public URL: `https://yourservice.onrender.com`

**PostgreSQL:**
- 1 GB storage
- 100 MB/month bandwidth (outbound only)
- No concurrent connections limit

**Good for:** Development, testing, small user base (< 1000 users)

**For Production:**
- Upgrade to Paid Plan
- Add environment: `ENVIRONMENT=production`
- Increase database storage if needed

---

## 💰 Cost Estimation

| Component | Free Tier | Paid Tier |
|-----------|-----------|-----------|
| Web Service | $0/month | $10-50/month |
| PostgreSQL | $0/month (1GB) | $15+/month |
| **Total** | **$0/month** | **$25-65/month** |

---

## 🆘 Troubleshooting

### Service Won't Start
1. Check logs: Render Dashboard → Logs
2. Look for error messages
3. Common causes:
   - Missing dependencies (check requirements.txt)
   - Wrong start command
   - Environment variables not set

### Database Connection Fails
1. Verify DATABASE_URL in Environment
2. Test connection from web service logs
3. Check PostgreSQL service status in Render

### CORS Error
1. Frontend getting 403 error?
2. Add frontend URL to CORS_ORIGINS
3. Redeploy or restart service

### Slow Requests
1. Check database query performance
2. Reduce request timeout settings
3. Optimize database indexes
4. Consider upgrading to paid plan

---

## 📞 Support

**Render.com Support:**
- Help Center: https://render.com/docs
- Email: support@render.com
- Status Page: https://status.render.com

**FastAPI Documentation:**
- https://fastapi.tiangolo.com
- Full API docs at `/api/docs` endpoint

---

## ✨ Next Steps

1. ✅ Deploy backend to Render
2. ✅ Connect frontend to backend API
3. ✅ Test end-to-end functionality
4. ✅ Set up custom domain (optional)
5. ✅ Monitor performance in production
6. ✅ Collect user feedback
7. ✅ Plan for scaling (upgrade tier)

---

**Your API is now live! 🎉**

Backend URL: `https://wandatools-api.onrender.com`
API Docs: `https://wandatools-api.onrender.com/api/docs`
