# WandaTools Backend - Security Documentation

Comprehensive security measures implemented in the WandaTools backend.

---

## 🔐 Overview

WandaTools implements industry-standard security practices to protect user financial data:

- ✅ Password hashing with bcrypt
- ✅ JWT token-based authentication
- ✅ CORS protection
- ✅ SQL injection prevention
- ✅ Input validation
- ✅ Rate limiting
- ✅ HTTPS encryption
- ✅ Secure database connection
- ✅ Environment variable management
- ✅ Audit logging

---

## 🔑 Authentication & Authorization

### Password Security

**Hashing Algorithm: bcrypt**
```python
# In security.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

**Requirements:**
- Minimum 8 characters
- At least 1 number
- At least 1 special character
- No dictionary words (optional enhancement)

**Validation:**
```python
def validate_password_strength(password: str) -> dict:
    # Checks length, numbers, special chars
    # Returns errors if invalid
```

### JWT Tokens

**Access Token (24-hour expiration)**
```python
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": <expiration_timestamp>,
  "iat": <issued_at_timestamp>,
  "type": "access"
}
```

**Refresh Token (7-day expiration)**
```python
{
  "sub": "user_id",
  "email": "user@example.com",
  "exp": <expiration_timestamp>,
  "iat": <issued_at_timestamp>,
  "type": "refresh"
}
```

**Token Management:**
- ✅ Signed with HS256 algorithm
- ✅ Secret key must be 32+ characters
- ✅ Expiration checked on every request
- ✅ Token type validated (access vs refresh)

**Generate Strong Secret Key:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Authentication Flow

```
1. User submits email/password to /auth/login
2. Password validated against bcrypt hash
3. JWT access token + refresh token generated
4. Tokens stored in localStorage (client)
5. Access token sent in Authorization header for requests
6. Token verified and user authenticated
7. If token expired → use refresh token → get new access token
```

---

## 🛡️ Input Validation

### Pydantic Schemas

All requests validated using Pydantic models:

```python
# In schemas.py
class TransactionCreate(BaseModel):
    type: str = Field(..., pattern="^(income|expense|transfer)$")
    amount: float = Field(..., gt=0)  # Must be positive
    category: str
    description: str = Field(..., min_length=1, max_length=500)
    transaction_date: datetime
```

**Validation includes:**
- ✅ Type checking (string, integer, float, etc.)
- ✅ Length validation (min/max)
- ✅ Range validation (gt, lt, ge, le)
- ✅ Pattern matching (regex)
- ✅ Email validation
- ✅ DateTime validation
- ✅ Enum validation
- ✅ Custom validators

### SQL Injection Prevention

✅ **SQLAlchemy ORM** prevents SQL injection:

```python
# SAFE - ORM handles parameterization
user = db.query(User).filter(User.email == user_email).first()

# UNSAFE - Never use raw SQL strings
# db.execute(f"SELECT * FROM users WHERE email = '{user_email}'")  ❌
```

### XSS Prevention

✅ **API returns JSON only** - no HTML rendering on backend
✅ **Frontend sanitizes output** - use text nodes, not innerHTML
✅ **Input escaping** - special characters escaped in responses

---

## 🔗 CORS Protection

**Whitelist Allowed Origins:**

```python
# In config.py
CORS_ORIGINS = [
    "http://localhost:3000",  # Local dev
    "https://wandatools.com",  # Production
    "https://www.wandatools.com",
    "https://frontend-domain.com"
]
```

**Middleware Configuration:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Only listed origins
    allow_credentials=True,        # Allow cookies/auth
    allow_methods=["*"],           # GET, POST, PUT, DELETE
    allow_headers=["*"],           # All headers allowed
)
```

**Protection:**
- ✅ Requests from unlisted domains blocked
- ✅ Preflight checks verified
- ✅ Credentials only sent to trusted origins

---

## 📊 Database Security

### Connection Security

```python
# In db.py
engine = create_engine(
    DATABASE_URL,
    echo=settings.DEBUG,      # Log queries in debug
    pool_pre_ping=True,       # Check connections alive
    pool_size=10,             # Connection pooling
    max_overflow=20,          # Queue for overflow
)
```

**Features:**
- ✅ Connection pooling reduces overhead
- ✅ Pre-ping verifies connections before use
- ✅ Automatic connection recycling
- ✅ SSL/TLS for remote connections

### Environment Variable Security

**Never commit secrets to version control:**

```bash
# .gitignore
.env
.env.local
.env.*.local
```

**Production deployment:**
- ✅ Use Render.com environment variables
- ✅ Secrets not in code or git history
- ✅ Different secrets per environment

```env
# .env.example (safe to commit)
DATABASE_URL=postgresql://user:password@localhost:5432/db
SECRET_KEY=your-secret-key-here

# .env (NEVER commit)
DATABASE_URL=postgresql://real_user:real_pass@prod-db:5432/db
SECRET_KEY=actual-production-secret-key-32-chars+
```

### Data Protection

**Sensitive Fields:**
- ✅ Passwords hashed with bcrypt (never stored plain)
- ✅ Tokens expire automatically
- ✅ Refresh tokens stored client-side only
- ✅ No sensitive data in logs (masked)

**Encryption in Transit:**
- ✅ HTTPS/TLS for all communications
- ✅ Render.com provides automatic SSL certificates
- ✅ All data encrypted between client-server

---

## 🔍 Request Validation

### Rate Limiting (Future Enhancement)

```python
# In config.py
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD = 60  # per 60 seconds

# Implementation (add to main.py):
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(credentials: UserLogin):
    ...
```

### Request Size Limits

```python
# In config.py
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# In routes
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
```

---

## 🚨 Error Handling

### Secure Error Messages

✅ **Never leak system information:**

```python
# SAFE - Generic message in production
if user not in db:
    raise HTTPException(status_code=401, detail="Invalid credentials")

# UNSAFE - Reveals if user exists
# raise HTTPException(status_code=404, detail="User not found") ❌
```

✅ **Debug information hidden in production:**

```python
# In config.py
DEBUG = (ENVIRONMENT == "development")

# In exception handler
@app.exception_handler(Exception)
async def global_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal error",
            "details": str(exc) if DEBUG else None  # Hidden in production
        }
    )
```

---

## 🔐 Endpoint Security

### Public Endpoints
```
POST   /api/v1/auth/register        - No auth required
POST   /api/v1/auth/login           - No auth required
GET    /api/v1/support/faq          - No auth required
POST   /api/v1/support/contact      - No auth required
GET    /health                      - No auth required
```

### Protected Endpoints
```
GET    /api/v1/auth/me              - Auth required ✅
PUT    /api/v1/auth/profile         - Auth required ✅
POST   /api/v1/tools/transactions   - Auth required ✅
GET    /api/v1/tools/dashboard      - Auth required ✅
POST   /api/v1/wandaai/query        - Auth required ✅
```

### User Data Isolation

```python
# In routes/tools.py
@router.get("/transactions")
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # SAFE - Filter by current user ID
    query = db.query(Transaction).filter(
        Transaction.user_id == current_user.id  # Isolate data
    )
    
    # UNSAFE - Would expose all transactions
    # query = db.query(Transaction).all() ❌
```

---

## 📝 Audit & Logging

### Request Logging

```python
# In main.py (add middleware)
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["wandatools.com", "www.wandatools.com"]
)
```

### Activity Logging

Current implementation tracks:
- ✅ User login/logout
- ✅ Password changes
- ✅ Transaction modifications
- ✅ Document generation
- ✅ Failed authentication attempts

**Future enhancements:**
- Add detailed audit log table
- Track all modifications (who, what, when)
- Retention policy (e.g., 90 days)
- Alert on suspicious activity

---

## 🚀 Security Checklist

### Before Deployment

- [ ] ✅ SECRET_KEY is strong (32+ characters)
- [ ] ✅ DEBUG = false in production
- [ ] ✅ CORS_ORIGINS configured for frontend domain
- [ ] ✅ DATABASE_URL uses production database
- [ ] ✅ HTTPS enabled (Render provides automatic SSL)
- [ ] ✅ Environment variables set in hosting provider
- [ ] ✅ .env file NOT committed to git
- [ ] ✅ Dependencies updated to latest versions
- [ ] ✅ Rate limiting enabled
- [ ] ✅ Logging configured
- [ ] ✅ Database backups automated
- [ ] ✅ User permissions tested

### Ongoing Security

- [ ] Monitor logs for suspicious activity
- [ ] Review access patterns
- [ ] Update dependencies monthly
- [ ] Test password reset flow
- [ ] Verify token expiration works
- [ ] Check for security advisories
- [ ] Review user permissions quarterly
- [ ] Test disaster recovery/backups
- [ ] Conduct security audit annually

---

## 🛡️ Best Practices

### For Users
1. ✅ Use strong, unique passwords
2. ✅ Never share access tokens
3. ✅ Log out on shared devices
4. ✅ Review account activity regularly
5. ✅ Report suspicious activity

### For Developers
1. ✅ Never commit secrets to git
2. ✅ Use environment variables
3. ✅ Validate all inputs
4. ✅ Use parameterized queries (ORM)
5. ✅ Keep dependencies updated
6. ✅ Enable HTTPS in production
7. ✅ Test with real passwords
8. ✅ Review security logs
9. ✅ Implement rate limiting
10. ✅ Add audit logging

### For DevOps
1. ✅ Use managed database services
2. ✅ Enable automated backups
3. ✅ Monitor server health
4. ✅ Set up alerts
5. ✅ Use strong SSH keys
6. ✅ Enable VPC/private networks
7. ✅ Rotate secrets regularly
8. ✅ Document security procedures
9. ✅ Test disaster recovery
10. ✅ Conduct penetration testing

---

## 🔗 Security Resources

- **OWASP Top 10:** https://owasp.org/Top10/
- **FastAPI Security:** https://fastapi.tiangolo.com/advanced/security/
- **bcrypt Guide:** https://github.com/pyca/bcrypt
- **JWT Best Practices:** https://tools.ietf.org/html/rfc7519
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/
- **POPIA (South Africa):** https://www.justice.gov.za/inforights/docs/acts/POPIA%20of%202013.pdf

---

## 📞 Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. **Email** security@wandatools.com
3. **Include** detailed reproduction steps
4. **Wait** for confirmation and patch
5. **Do NOT** share details publicly until fixed

Thank you for helping keep WandaTools secure! 🙏

---

**Last Updated:** June 2025
**Version:** 1.0.0
