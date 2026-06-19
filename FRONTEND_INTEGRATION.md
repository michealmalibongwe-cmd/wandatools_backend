# Frontend Integration Guide

Complete guide to connect your WandaTools frontend to the FastAPI backend.

---

## 🔗 Backend API Base URL

**Development:**
```javascript
const API_BASE = "http://localhost:8000/api/v1";
```

**Production (Render.com):**
```javascript
const API_BASE = "https://wandatools-api.onrender.com/api/v1";
```

---

## 📝 Step 1: Update Frontend Configuration

Create or update `api.js` in your frontend:

```javascript
// frontend/utils/api.js

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000/api/v1";

// Helper function for authenticated requests
export async function apiCall(endpoint, options = {}) {
  const token = localStorage.getItem("access_token");
  
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });
  
  if (response.status === 401) {
    // Token expired, try to refresh
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiCall(endpoint, options); // Retry request
    } else {
      // Redirect to login
      window.location.href = "/profile.html";
    }
  }
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "API request failed");
  }
  
  return await response.json();
}

// Refresh token on expiration
export async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;
  
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    
    if (!response.ok) return false;
    
    const data = await response.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return true;
  } catch (error) {
    console.error("Token refresh failed:", error);
    return false;
  }
}
```

---

## 🔐 Step 2: Update Authentication

**Register:**
```javascript
export async function register(name, email, password, businessType = null) {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      email,
      password,
      business_type: businessType,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  const data = await response.json();
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  localStorage.setItem("wt_user_name", name);
  localStorage.setItem("wt_user_email", email);
  
  return data;
}

// Update in profile.html handleRegister()
async function handleRegister(e) {
  e.preventDefault();
  const name = document.getElementById("regName").value.trim();
  const email = document.getElementById("regEmail").value.trim();
  const password = document.getElementById("regPassword").value.trim();
  
  try {
    await register(name, email, password);
    showToast("Account created successfully!");
    setTimeout(() => showProfilePage(), 600);
  } catch (error) {
    showToast(error.message, "error");
  }
}
```

**Login:**
```javascript
export async function login(email, password) {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  const data = await response.json();
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  
  // Get user details
  const user = await apiCall("/auth/me");
  localStorage.setItem("wt_user_name", user.name);
  localStorage.setItem("wt_user_email", user.email);
  
  return data;
}

// Update in profile.html handleLogin()
async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value.trim();
  
  try {
    await login(email, password);
    showToast("Signed in successfully!");
    setTimeout(() => showProfilePage(), 600);
  } catch (error) {
    showToast(error.message, "error");
  }
}
```

---

## 💰 Step 3: Update Tools (Transactions & Dashboard)

**Create Transaction:**
```javascript
// In tools.html addTransaction()
async function addTransaction() {
  const desc = document.getElementById("txnDesc").value.trim();
  const amount = parseFloat(document.getElementById("txnAmount").value);
  const cat = document.getElementById("txnCategory").value;
  const date = document.getElementById("txnDate").value;
  
  if (!desc || !amount || !date) {
    showToast("Please fill in all fields.", "error");
    return;
  }
  
  try {
    const newTxn = await apiCall("/tools/transactions", {
      method: "POST",
      body: JSON.stringify({
        type: txnType,
        amount,
        category: cat,
        description: desc,
        transaction_date: new Date(date).toISOString(),
      }),
    });
    
    transactions.unshift(newTxn);
    renderTransactions();
    document.getElementById("txnDesc").value = "";
    document.getElementById("txnAmount").value = "";
    showToast("Transaction saved successfully!");
  } catch (error) {
    showToast(error.message, "error");
  }
}

// Get all transactions
async function renderTransactions() {
  try {
    const response = await apiCall("/tools/transactions?limit=100");
    const txns = response.items || [];
    
    const tbody = document.getElementById("txnTableBody");
    const rows = txns.map(t => `
      <tr>
        <td>${new Date(t.transaction_date).toLocaleDateString()}</td>
        <td>${t.description}</td>
        <td><span class="badge badge-blue">${t.category}</span></td>
        <td><span class="badge ${t.type === 'income' ? 'badge-green' : 'badge-red'}">
          ${t.type === 'income' ? 'Income' : 'Expense'}
        </span></td>
        <td style="font-weight:700;color:${t.type === 'income' ? 'var(--green)' : 'var(--red)'}">
          ${t.type === 'income' ? '+' : '-'} R ${Number(t.amount).toLocaleString('en-ZA', {minimumFractionDigits: 2})}
        </td>
        <td>
          <button onclick="deleteTxn(${t.id})" style="background:none;border:none;cursor:pointer;color:var(--red)">
            <i class="material-icons" style="font-size:1rem;">delete</i>
          </button>
        </td>
      </tr>
    `).join("");
    tbody.innerHTML = rows;
  } catch (error) {
    console.error("Error loading transactions:", error);
  }
}

// Delete transaction
async function deleteTxn(id) {
  if (!confirm("Delete this transaction?")) return;
  
  try {
    await apiCall(`/tools/transactions/${id}`, { method: "DELETE" });
    showToast("Transaction deleted.");
    renderTransactions();
  } catch (error) {
    showToast(error.message, "error");
  }
}
```

**Get Dashboard Summary:**
```javascript
// In tools.html, update dashboard panel
async function updateDashboard() {
  try {
    const summary = await apiCall("/tools/dashboard/summary");
    
    document.getElementById("dashGreetName").textContent = 
      localStorage.getItem("wt_user_name").split(" ")[0];
    
    // Update stat cards
    updateStatCard(summary.total_income, summary.total_expenses, summary.net_profit);
    
    // Render bar chart with monthly data
    const history = await apiCall("/tools/dashboard/history?months=6");
    renderMonthlyChart(history.summaries);
  } catch (error) {
    console.error("Error loading dashboard:", error);
  }
}
```

---

## 🤖 Step 4: Update WandaAI

```javascript
// In wandaAI.html, update sendMessage()
async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  
  chatInput.value = "";
  autoResize(chatInput);
  sendBtn.disabled = true;
  addMessage("user", text);
  showTyping();
  
  try {
    const response = await apiCall("/wandaai/query", {
      method: "POST",
      body: JSON.stringify({
        question: text,
        mode: currentMode,
      }),
    });
    
    hideTyping();
    const insights = response.insights ? {
      title: "💡 Insight",
      body: JSON.stringify(response.insights).slice(0, 200)
    } : null;
    
    addMessage("ai", response.response, insights);
  } catch (error) {
    hideTyping();
    showToast(error.message, "error");
    addMessage("ai", "Sorry, I encountered an error. Please try again.");
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}
```

---

## 📧 Step 5: Update Support/Contact

```javascript
// In contact.html, update handleContactSubmit()
async function handleContactSubmit(e) {
  e.preventDefault();
  const form = document.getElementById("contactForm");
  
  if (!validateForm(form)) return;
  
  const formData = new FormData(form);
  const data = Object.fromEntries(formData);
  
  try {
    const response = await fetch(`${API_BASE}/support/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    
    if (!response.ok) throw new Error("Failed to submit");
    
    form.style.display = "none";
    document.getElementById("successMessage").style.display = "block";
    showToast("Message sent successfully!");
  } catch (error) {
    showToast(error.message, "error");
  }
}
```

---

## 🔄 Step 6: Update Authentication Helper

```javascript
// Update nav.js WandaAuth object
window.WandaAuth = {
  isLoggedIn: () => {
    const token = localStorage.getItem("wt_access_token") || 
                  localStorage.getItem("access_token");
    return token && token.trim().length > 0;
  },
  
  login: async (email, password) => {
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      
      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch (e) {
      return false;
    }
  },
  
  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("wt_user_name");
    localStorage.removeItem("wt_user_email");
    window.location.href = "profile.html";
  },
  
  getName: () => localStorage.getItem("wt_user_name") || "User",
  getEmail: () => localStorage.getItem("wt_user_email") || "",
  getToken: () => localStorage.getItem("access_token") || null,
};
```

---

## 🌐 Step 7: Environment Configuration

Create `.env` file in your frontend root:

```env
REACT_APP_API_BASE=http://localhost:8000/api/v1
REACT_APP_ENVIRONMENT=development
```

Or for production:

```env
REACT_APP_API_BASE=https://wandatools-api.onrender.com/api/v1
REACT_APP_ENVIRONMENT=production
```

---

## ✅ Testing Integration

1. **Start Backend:**
   ```bash
   cd wandatools-backend
   uvicorn main:app --reload
   ```

2. **Open Frontend:**
   ```bash
   Open index.html in browser or run your dev server
   ```

3. **Test Register:**
   - Fill form and submit
   - Check localStorage for tokens
   - Verify redirect to dashboard

4. **Test Transaction:**
   - Add a transaction
   - Check backend database: `SELECT * FROM transactions;`
   - Verify it appears in frontend

5. **Test WandaAI:**
   - Ask a question
   - Check API response includes insights

6. **Check Browser Console:**
   - No CORS errors
   - All requests show 200/201 status codes

---

## 🐛 Common Issues

### CORS Error
**Problem:** `Access to XMLHttpRequest blocked by CORS policy`

**Solution:**
- Add frontend URL to `CORS_ORIGINS` in `config.py`
- Restart backend: `uvicorn main:app --reload`

### 401 Unauthorized
**Problem:** "Invalid or expired token"

**Solution:**
- Clear localStorage: `localStorage.clear()`
- Log in again
- Check token isn't expired

### 404 Not Found
**Problem:** "Endpoint not found"

**Solution:**
- Verify API endpoint path in your fetch call
- Check API_BASE URL is correct
- Verify endpoint exists in routes files

---

## 📚 Complete API Request Examples

See `test_requests.http` for complete request/response examples using VS Code REST Client.

---

## 🚀 Deploy Together

**Frontend on Vercel, Backend on Render:**

1. Deploy backend first (see README.md)
2. Get backend URL: `https://wandatools-api.onrender.com`
3. Update frontend `.env` with backend URL
4. Deploy frontend to Vercel

---

## 📞 Support

Backend issues? Check:
- Backend logs: `uvicorn main:app --reload`
- Database connection: `psql -U postgres -d wandatools_db`
- API docs: `http://localhost:8000/api/docs`

Frontend issues? Check:
- Browser console for errors
- Network tab for failed requests
- localStorage for tokens

---

**Ready? Start building! 🎉**
