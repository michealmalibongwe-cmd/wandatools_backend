# WandaTools API Reference

Complete documentation of all API endpoints with request/response examples.

---

## Authentication Endpoints

### Register User
**Endpoint:** `POST /api/v1/auth/register`

Create a new user account.

**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "SecurePassword123!",
  "business_type": "Freelancer",
  "timezone": "Africa/Johannesburg"
}
```

**Response:** `201 Created`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Errors:**
- `409 Conflict` - Email already registered
- `400 Bad Request` - Password doesn't meet requirements

---

### Login User
**Endpoint:** `POST /api/v1/auth/login`

Authenticate user and receive access/refresh tokens.

**Request:**
```json
{
  "email": "john@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Errors:**
- `401 Unauthorized` - Invalid email or password
- `403 Forbidden` - Account inactive

---

### Refresh Token
**Endpoint:** `POST /api/v1/auth/refresh`

Get new access token using refresh token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Errors:**
- `401 Unauthorized` - Invalid or expired refresh token

---

### Get Current User
**Endpoint:** `GET /api/v1/auth/me`

Get current authenticated user's information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "business_type": "Freelancer",
  "timezone": "Africa/Johannesburg",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-06-18T10:00:00",
  "last_login": "2025-06-18T14:30:00",
  "role": "user",
  "updated_at": "2025-06-18T14:30:00"
}
```

**Errors:**
- `401 Unauthorized` - Missing or invalid token

---

### Update Profile
**Endpoint:** `PUT /api/v1/auth/profile`

Update user profile information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "name": "John Doe Updated",
  "phone": "+27764693531",
  "timezone": "Africa/Johannesburg",
  "business_type": "Small Business"
}
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "name": "John Doe Updated",
  "email": "john@example.com",
  "timezone": "Africa/Johannesburg",
  "business_type": "Small Business",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-06-18T10:00:00"
}
```

---

### Change Password
**Endpoint:** `POST /api/v1/auth/change-password`

Change user password.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword456!"
}
```

**Response:** `200 OK`
```json
{
  "message": "Password changed successfully"
}
```

**Errors:**
- `401 Unauthorized` - Current password incorrect
- `400 Bad Request` - New password doesn't meet requirements

---

### Logout
**Endpoint:** `POST /api/v1/auth/logout`

Logout current user (invalidate token on client).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "message": "Logged out successfully"
}
```

---

## Transaction Endpoints

### Create Transaction
**Endpoint:** `POST /api/v1/tools/transactions`

Add a new transaction (income or expense).

**Headers:**
```
Authorization: Bearer <access_token>
```

**Request:**
```json
{
  "type": "income",
  "amount": 5000.00,
  "category": "Sales",
  "description": "Client Invoice #001",
  "transaction_date": "2025-06-18T10:30:00",
  "reference_id": "INV-001",
  "recipient_or_payer": "ABC Company",
  "notes": "Payment received",
  "is_recurring": "monthly",
  "tax_deductible": "Yes"
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "user_id": 1,
  "type": "income",
  "amount": 5000.00,
  "category": "Sales",
  "description": "Client Invoice #001",
  "transaction_date": "2025-06-18T10:30:00",
  "created_at": "2025-06-18T10:31:00",
  "updated_at": "2025-06-18T10:31:00",
  "reference_id": "INV-001",
  "recipient_or_payer": "ABC Company",
  "notes": "Payment received",
  "is_recurring": "monthly",
  "tax_deductible": "Yes"
}
```

---

### List Transactions
**Endpoint:** `GET /api/v1/tools/transactions`

Retrieve user's transactions with pagination and filters.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `skip` (int, default: 0) - Number of items to skip
- `limit` (int, default: 10, max: 100) - Number of items to return
- `transaction_type` (string) - Filter by: income, expense, transfer
- `category` (string) - Filter by category
- `start_date` (datetime) - Filter from date (ISO 8601)
- `end_date` (datetime) - Filter to date (ISO 8601)

**Example:**
```
GET /api/v1/tools/transactions?skip=0&limit=10&transaction_type=income&category=Sales
```

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "type": "income",
      "amount": 5000.00,
      "category": "Sales",
      "description": "Client Invoice #001",
      "transaction_date": "2025-06-18T10:30:00",
      "created_at": "2025-06-18T10:31:00",
      "updated_at": "2025-06-18T10:31:00"
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 10,
  "total_pages": 5
}
```

---

### Get Transaction
**Endpoint:** `GET /api/v1/tools/transactions/{id}`

Get a specific transaction by ID.

**Response:** `200 OK`
```json
{
  "id": 1,
  "user_id": 1,
  "type": "income",
  "amount": 5000.00,
  "category": "Sales",
  "description": "Client Invoice #001",
  "transaction_date": "2025-06-18T10:30:00",
  "created_at": "2025-06-18T10:31:00",
  "updated_at": "2025-06-18T10:31:00"
}
```

**Errors:**
- `404 Not Found` - Transaction doesn't exist or not owned by user

---

### Update Transaction
**Endpoint:** `PUT /api/v1/tools/transactions/{id}`

Update a transaction.

**Request:**
```json
{
  "amount": 5500.00,
  "description": "Client Invoice #001 - Updated"
}
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "user_id": 1,
  "type": "income",
  "amount": 5500.00,
  "description": "Client Invoice #001 - Updated",
  "transaction_date": "2025-06-18T10:30:00",
  "updated_at": "2025-06-18T11:00:00"
}
```

---

### Delete Transaction
**Endpoint:** `DELETE /api/v1/tools/transactions/{id}`

Delete a transaction.

**Response:** `204 No Content`

---

## Dashboard Endpoints

### Get Month Summary
**Endpoint:** `GET /api/v1/tools/dashboard/summary`

Get income, expenses, and profit summary for a specific month.

**Query Parameters:**
- `month` (string, format: YYYY-MM) - Optional, defaults to current month

**Response:** `200 OK`
```json
{
  "total_income": 42500.00,
  "total_expenses": 18240.00,
  "net_profit": 24260.00,
  "transaction_count": 47,
  "month": "2025-06",
  "income_by_category": {
    "Sales": 25000.00,
    "Services": 17500.00
  },
  "expense_by_category": {
    "Rent": 6500.00,
    "Stock": 4200.00,
    "Salaries": 3600.00,
    "Marketing": 1800.00,
    "Utilities": 1140.00
  }
}
```

---

### Get Multi-Month History
**Endpoint:** `GET /api/v1/tools/dashboard/history`

Get dashboard data for multiple months.

**Query Parameters:**
- `months` (int, default: 6, max: 12) - Number of months to retrieve

**Response:** `200 OK`
```json
{
  "summaries": [
    {
      "month": "2025-01",
      "total_income": 38000.00,
      "total_expenses": 16200.00,
      "net_profit": 21800.00
    },
    {
      "month": "2025-02",
      "total_income": 40500.00,
      "total_expenses": 17100.00,
      "net_profit": 23400.00
    }
  ]
}
```

---

## Document Endpoints

### Generate Document
**Endpoint:** `POST /api/v1/tools/documents`

Generate a financial report or document.

**Request:**
```json
{
  "type": "audit_report",
  "period_start": "2025-01-01T00:00:00",
  "period_end": "2025-06-30T23:59:59"
}
```

**Document Types:**
- `audit_report` - Audit-ready report
- `loan_application` - Loan application package
- `investment_report` - Investment report
- `monthly_summary` - Monthly summary
- `cash_flow` - Cash flow analysis
- `tax_summary` - Tax summary

**Response:** `201 Created`
```json
{
  "id": 1,
  "user_id": 1,
  "type": "audit_report",
  "status": "ready",
  "filename": "audit_report_1718626260.pdf",
  "file_url": "/api/v1/documents/1/download",
  "created_at": "2025-06-18T10:31:00",
  "total_revenue": 42500.00,
  "total_expenses": 18240.00,
  "net_profit": 24260.00
}
```

---

### List Documents
**Endpoint:** `GET /api/v1/tools/documents`

Get user's generated documents.

**Query Parameters:**
- `skip` (int, default: 0)
- `limit` (int, default: 10, max: 100)

**Response:** `200 OK`
```json
{
  "items": [
    {
      "id": 1,
      "user_id": 1,
      "type": "audit_report",
      "status": "ready",
      "filename": "audit_report_1718626260.pdf",
      "file_url": "/api/v1/documents/1/download",
      "created_at": "2025-06-18T10:31:00"
    }
  ],
  "total": 5
}
```

---

### Get Document
**Endpoint:** `GET /api/v1/tools/documents/{id}`

Get a specific document.

**Response:** `200 OK` (Document object)

---

### Delete Document
**Endpoint:** `DELETE /api/v1/tools/documents/{id}`

Delete a document.

**Response:** `204 No Content`

---

## WandaAI Endpoints

### Query WandaAI
**Endpoint:** `POST /api/v1/wandaai/query`

Ask WandaAI a financial question.

**Request:**
```json
{
  "question": "How is my cash flow looking this month?",
  "mode": "insights"
}
```

**Modes:**
- `insights` - Financial analysis and insights
- `recommendations` - Smart money-saving tips
- `business` - Business strategy assistance

**Response:** `200 OK`
```json
{
  "response": "Your cash flow is **healthy**! Over the last 3 months...",
  "mode": "insights",
  "confidence": 0.92,
  "insights": {
    "type": "cash_flow_insight"
  },
  "recommendations": [
    "Review your largest expense categories quarterly",
    "Set aside 20% of revenue as emergency reserves"
  ]
}
```

---

### Get AI Modes
**Endpoint:** `GET /api/v1/wandaai/modes`

Get available WandaAI modes.

**Response:** `200 OK`
```json
{
  "modes": [
    {
      "name": "Financial Insights",
      "id": "insights",
      "description": "Analyse your income, expenses, and trends"
    },
    {
      "name": "Smart Recommendations",
      "id": "recommendations",
      "description": "Get actionable money-saving and growth tips"
    },
    {
      "name": "Business Assistant",
      "id": "business",
      "description": "Help with pricing, planning, and strategy"
    }
  ]
}
```

---

### Get Sample Prompts
**Endpoint:** `GET /api/v1/wandaai/prompts`

Get sample prompts for WandaAI.

**Response:** `200 OK`
```json
{
  "prompts": [
    "How is my cash flow looking this month?",
    "Where am I spending the most money?",
    "What is my profit margin this month?",
    "How can I reduce my expenses?",
    "Am I ready to apply for a business loan?",
    "What financial goals should I set for next month?"
  ]
}
```

---

## Support Endpoints

### Submit Contact Form
**Endpoint:** `POST /api/v1/support/contact`

Submit a contact form (no authentication required).

**Request:**
```json
{
  "name": "John Smith",
  "email": "john@example.com",
  "phone": "+27764693531",
  "subject": "Technical support needed",
  "message": "I'm having trouble with my account..."
}
```

**Response:** `201 Created`
```json
{
  "id": 1,
  "status": "received",
  "message": "Thank you for contacting WandaTools. We'll get back to you within 24 hours."
}
```

---

### Get FAQ
**Endpoint:** `GET /api/v1/support/faq`

Get FAQ items.

**Query Parameters:**
- `search` (string) - Search FAQ by keyword
- `category` (string) - Filter by category (security, billing, technical, general)

**Response:** `200 OK`
```json
{
  "faq_items": [
    {
      "id": 1,
      "category": "security",
      "question": "Is my financial data secure?",
      "answer": "Yes. WandaTools uses bank-level encryption..."
    }
  ],
  "total": 8
}
```

---

### Get Support Status
**Endpoint:** `GET /api/v1/support/status`

Get support system status and hours.

**Response:** `200 OK`
```json
{
  "status": "operational",
  "support_hours": {
    "monday_friday": "09:00 - 17:00 SAST",
    "saturday": "10:00 - 14:00 SAST",
    "sunday": "Closed"
  },
  "response_time": "24 hours",
  "contact_methods": [...]
}
```

---

### Health Check
**Endpoint:** `GET /health`

Check API health status.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2025-06-18T14:30:00",
  "version": "1.0.0"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": "Error type",
  "details": "Detailed error message (in development only)",
  "status_code": 400
}
```

### Common HTTP Status Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 204 | No Content | Request successful, no response body |
| 400 | Bad Request | Invalid request data - check parameters |
| 401 | Unauthorized | Missing or invalid token - log in again |
| 403 | Forbidden | Access denied - check permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Resource already exists (e.g., email) |
| 422 | Unprocessable Entity | Validation error - check field types |
| 429 | Too Many Requests | Rate limit exceeded - wait and retry |
| 500 | Server Error | Backend error - contact support |

---

## Rate Limiting

- **Limit:** 100 requests per 60 seconds
- **Headers in response:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- **Status code:** `429 Too Many Requests` when exceeded

---

## Pagination

List endpoints return paginated results:

```json
{
  "items": [...],
  "total": 47,
  "page": 1,
  "page_size": 10,
  "total_pages": 5
}
```

**Parameters:**
- `skip` - Number of items to skip (default: 0)
- `limit` - Items per page (default: 10, max: 100)

---

## Timestamps

All timestamps are in ISO 8601 format (UTC):
```
2025-06-18T14:30:00
```

---

## Testing

See `test_requests.http` for executable test requests using VS Code REST Client.

---

**Last Updated:** June 2025  
**API Version:** 1.0.0
