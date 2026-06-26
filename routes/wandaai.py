"""
WandaTools — routes/wandaai.py
Location: routes/ folder

WandaAI financial intelligence endpoints.

Imports:
  - DB session    → db.py
  - User model    → main.py
  - Transaction   → routes/transactions.py  ← correct path
  - Auth          → routes/auth.py

Endpoints:
  POST  /api/v1/wandaai/query    — ask WandaAI a financial question
  GET   /api/v1/wandaai/modes    — list available AI modes
  GET   /api/v1/wandaai/prompts  — get sample questions to ask
  GET   /api/v1/wandaai/summary  — get a full financial snapshot (no question needed)
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import User
from routes.transactions import Transaction, TransactionType   # ✅ correct path
from routes.auth import get_current_user

log    = logging.getLogger("wandatools.wandaai")
router = APIRouter(prefix="/api/v1/wandaai", tags=["WandaAI"])

VALID_MODES = {"insights", "recommendations", "business"}


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class AIQueryRequest(BaseModel):
    question: str
    mode:     str = "insights"
    months:   int = 3

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Question must be at least 3 characters")
        if len(v) > 500:
            raise ValueError("Question must be under 500 characters")
        return v

    @field_validator("mode")
    @classmethod
    def mode_must_be_valid(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_MODES:
            raise ValueError(f"Mode must be one of: {', '.join(VALID_MODES)}")
        return v

    @field_validator("months")
    @classmethod
    def months_in_range(cls, v: int) -> int:
        if not (1 <= v <= 12):
            raise ValueError("months must be between 1 and 12")
        return v


# ─────────────────────────────────────────────────────────────
# CORE DATA HELPER
# ─────────────────────────────────────────────────────────────

def _get_financial_summary(user: User, db: Session, months: int = 3) -> dict:
    """
    Query the last N months of transactions and return a structured summary.
    Raises HTTPException 500 if the DB query fails.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=30 * months)
        transactions = (
            db.query(Transaction)
            .filter(
                Transaction.user_id          == user.id,
                Transaction.transaction_date >= cutoff,
                Transaction.is_deleted       == False,   # noqa: E712
            )
            .all()
        )
    except Exception as exc:
        log.error(f"wandaai DB query error for user {user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load transaction data: {exc}",
        )

    income_txns  = [t for t in transactions if t.type == TransactionType.INCOME]
    expense_txns = [t for t in transactions if t.type == TransactionType.EXPENSE]

    total_income   = sum(t.amount for t in income_txns)
    total_expenses = sum(t.amount for t in expense_txns)
    net_profit     = total_income - total_expenses
    profit_margin  = (net_profit / total_income * 100) if total_income > 0 else 0.0

    income_by_category:  dict = {}
    expense_by_category: dict = {}
    for t in income_txns:
        income_by_category[t.category]  = income_by_category.get(t.category, 0.0)  + t.amount
    for t in expense_txns:
        expense_by_category[t.category] = expense_by_category.get(t.category, 0.0) + t.amount

    top_income_category  = max(income_by_category,  key=income_by_category.get)  if income_by_category  else None
    top_expense_category = max(expense_by_category, key=expense_by_category.get) if expense_by_category else None

    return {
        "total_income":          total_income,
        "total_expenses":        total_expenses,
        "net_profit":            net_profit,
        "profit_margin":         round(profit_margin, 2),
        "transaction_count":     len(transactions),
        "income_count":          len(income_txns),
        "expense_count":         len(expense_txns),
        "income_by_category":    income_by_category,
        "expense_by_category":   expense_by_category,
        "top_income_category":   top_income_category,
        "top_expense_category":  top_expense_category,
        "months_analysed":       months,
    }


# ─────────────────────────────────────────────────────────────
# CONFIDENCE SCORE — deterministic, based on data quality
# ─────────────────────────────────────────────────────────────

def _confidence_score(summary: dict) -> float:
    count = summary["transaction_count"]
    if count == 0:  return 0.10
    if count < 5:   return 0.40
    if count < 15:  return 0.65
    if count < 30:  return 0.80
    if count < 60:  return 0.90
    return 0.97


# ─────────────────────────────────────────────────────────────
# RESPONSE GENERATORS
# ─────────────────────────────────────────────────────────────

def _fmt(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _generate_insight(question: str, summary: dict, currency: str) -> tuple:
    q = question.lower()

    if any(w in q for w in ["cash", "flow", "money", "liquidity"]):
        if summary["net_profit"] > 0:
            status_line = "✅ Your cash flow is **healthy**."
            advice      = "Keep monitoring your largest expense categories monthly."
        elif summary["net_profit"] == 0:
            status_line = "⚠️ Your cash flow is **breaking even**."
            advice      = "Look for small expense cuts to tip into profitability."
        else:
            status_line = "🔴 Your cash flow is **negative** — expenses exceed income."
            advice      = "Review your top expense categories immediately."
        text = (
            f"{status_line}\n\n**Last {summary['months_analysed']} months:**\n"
            f"- Income:   {_fmt(summary['total_income'],   currency)}\n"
            f"- Expenses: {_fmt(summary['total_expenses'], currency)}\n"
            f"- Net:      {_fmt(summary['net_profit'],     currency)}\n\n{advice}"
        )
        return text, {"type": "cash_flow", "status": "positive" if summary["net_profit"] > 0 else "negative"}

    elif any(w in q for w in ["spend", "expense", "cost", "where", "buying", "paying"]):
        if not summary["expense_by_category"]:
            return ("No expense transactions found. Add expense records to get spending analysis.",
                    {"type": "spending_analysis", "data_available": False})
        top    = summary["top_expense_category"]
        top_amt = summary["expense_by_category"][top]
        pct    = (top_amt / summary["total_expenses"] * 100) if summary["total_expenses"] > 0 else 0
        lines  = "\n".join(
            f"- {cat}: {_fmt(amt, currency)} ({amt / summary['total_expenses'] * 100:.1f}%)"
            for cat, amt in sorted(summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
        )
        text = (
            f"Your top spending category is **{top}** at {_fmt(top_amt, currency)} ({pct:.1f}%).\n\n"
            f"**All expense categories:**\n{lines}\n\n"
            f"💡 Review **{top}** expenses first — biggest impact on your bottom line."
        )
        return text, {"type": "spending_analysis", "top_category": top, "data_available": True}

    elif any(w in q for w in ["income", "revenue", "earn", "sales", "source"]):
        if not summary["income_by_category"]:
            return ("No income transactions found. Add income records to get revenue analysis.",
                    {"type": "income_analysis", "data_available": False})
        top     = summary["top_income_category"]
        top_amt = summary["income_by_category"][top]
        lines   = "\n".join(
            f"- {cat}: {_fmt(amt, currency)}"
            for cat, amt in sorted(summary["income_by_category"].items(), key=lambda x: x[1], reverse=True)
        )
        text = (
            f"Your strongest income source is **{top}** at {_fmt(top_amt, currency)}.\n\n"
            f"**All income sources:**\n{lines}\n\n"
            f"💡 Double down on **{top}** — your highest-performing revenue stream."
        )
        return text, {"type": "income_analysis", "top_source": top, "data_available": True}

    elif any(w in q for w in ["profit", "margin", "earnings", "return"]):
        margin = summary["profit_margin"]
        if margin > 50:   verdict = "🌟 Exceptional — above 50% is outstanding."
        elif margin > 30: verdict = "✅ Strong — above 30% is above industry average."
        elif margin > 10: verdict = "⚠️ Moderate — target 30%+ for a healthy business."
        elif margin > 0:  verdict = "🔴 Low — your cost structure needs review."
        else:             verdict = "🔴 Negative margin — you are operating at a loss."
        text = (
            f"**Profitability Snapshot — Last {summary['months_analysed']} Months:**\n\n"
            f"- Gross Revenue:  {_fmt(summary['total_income'],   currency)}\n"
            f"- Total Expenses: {_fmt(summary['total_expenses'], currency)}\n"
            f"- Net Profit:     {_fmt(summary['net_profit'],     currency)}\n"
            f"- Profit Margin:  **{margin:.1f}%**\n\n{verdict}"
        )
        return text, {"type": "profitability", "margin": margin}

    elif any(w in q for w in ["loan", "bank", "borrow", "finance", "funding", "credit"]):
        score   = 0
        factors = []
        if summary["net_profit"] > 0:
            score += 25; factors.append(f"✅ Positive net profit ({_fmt(summary['net_profit'], currency)})")
        else:
            factors.append("❌ Negative net profit — lenders require positive cash flow")
        if summary["profit_margin"] >= 20:
            score += 25; factors.append(f"✅ Profit margin {summary['profit_margin']:.1f}% (≥20% threshold)")
        else:
            factors.append(f"❌ Profit margin {summary['profit_margin']:.1f}% — lenders prefer 20%+")
        if summary["total_income"] >= summary["total_expenses"]:
            score += 25; factors.append("✅ Income covers expenses")
        else:
            factors.append("❌ Expenses exceed income")
        if summary["transaction_count"] >= 20:
            score += 25; factors.append(f"✅ {summary['transaction_count']} transactions — sufficient history")
        else:
            factors.append(f"⚠️ Only {summary['transaction_count']} transactions — build more history")
        if score >= 75:   verdict = "**You appear loan-ready.** Present our Loan Application Report to your bank."
        elif score >= 50: verdict = "**Borderline.** Improve profitability before applying."
        else:             verdict = "**Not yet loan-ready.** Focus on positive cash flow first."
        factor_list = "\n".join(f"  {f}" for f in factors)
        text = (
            f"**Loan Readiness Assessment:**\n\n{factor_list}\n\n"
            f"**Score: {score}/100**\n\n{verdict}"
        )
        return text, {"type": "loan_assessment", "score": score}

    elif any(w in q for w in ["save", "saving", "reduce", "cut", "cheaper"]):
        if not summary["expense_by_category"]:
            return ("No expense data available. Add expense transactions to get savings tips.",
                    {"type": "savings_advice", "data_available": False})
        sorted_expenses = sorted(summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True)
        tips = []
        for i, (cat, amt) in enumerate(sorted_expenses[:3], 1):
            pct = (amt / summary["total_expenses"] * 100) if summary["total_expenses"] > 0 else 0
            tips.append(f"{i}. **{cat}** — {_fmt(amt, currency)} ({pct:.1f}%). Review for savings.")
        text = (
            f"**Top savings opportunities:**\n\n" + "\n".join(tips)
            + f"\n\n💡 Even a 10% reduction in your top category saves "
            + _fmt(sorted_expenses[0][1] * 0.10, currency) + " this period."
        )
        return text, {"type": "savings_advice", "data_available": True}

    else:
        top_expense = f"**{summary['top_expense_category']}**" if summary["top_expense_category"] else "N/A"
        top_income  = f"**{summary['top_income_category']}**"  if summary["top_income_category"]  else "N/A"
        text = (
            f"**Your Financial Snapshot — Last {summary['months_analysed']} Months:**\n\n"
            f"- Transactions: **{summary['transaction_count']}**\n"
            f"- Total Income:  {_fmt(summary['total_income'],   currency)}\n"
            f"- Total Expenses:{_fmt(summary['total_expenses'], currency)}\n"
            f"- Net Profit:    {_fmt(summary['net_profit'],     currency)}\n"
            f"- Profit Margin: **{summary['profit_margin']:.1f}%**\n"
            f"- Top income source:  {top_income}\n"
            f"- Top expense source: {top_expense}\n\n"
            f"Try asking about: Cash flow · Spending · Profitability · Loan readiness · Savings"
        )
        return text, {"type": "general_overview"}


def _generate_recommendations(mode: str, summary: dict, currency: str) -> list:
    recs = []

    if summary["net_profit"] < 0:
        recs.append(f"🔴 Expenses exceed income by {_fmt(abs(summary['net_profit']), currency)}. Cut top expenses first.")
    if summary["profit_margin"] < 20 and summary["total_income"] > 0:
        recs.append(f"📈 Target 20%+ margin. Currently at {summary['profit_margin']:.1f}%.")
    if summary["transaction_count"] < 10:
        recs.append("📝 Log transactions consistently for more accurate insights.")
    if summary["top_expense_category"]:
        top_amt = summary["expense_by_category"][summary["top_expense_category"]]
        recs.append(f"🔍 Review **{summary['top_expense_category']}** ({_fmt(top_amt, currency)}) — your largest cost.")

    if mode == "recommendations":
        if summary["total_expenses"] > summary["total_income"] * 0.7:
            recs.append("⚠️ Expenses above 70% of income. Set a cap on discretionary spending.")
        recs.append("💰 Set aside 20% of monthly revenue as an emergency reserve.")
        recs.append("📅 Review your pricing strategy every quarter.")
        recs.append("🔄 Automate recurring expense tracking to save time.")
    elif mode == "business":
        if summary["top_income_category"]:
            recs.append(f"🚀 Double down on **{summary['top_income_category']}** — highest revenue stream.")
        recs.append("🏦 Build a 3-month cash reserve for business resilience.")
        recs.append("📊 Schedule a quarterly financial review with your accountant.")
        recs.append("📋 Track 3 key metrics monthly: margin, revenue growth, expense ratio.")
    elif mode == "insights":
        if summary["net_profit"] > 0:
            recs.append(f"✅ Reinvest a portion of your {_fmt(summary['net_profit'], currency)} profit into growth.")
        recs.append("📆 Compare this month vs last month to spot trends early.")

    seen   = set()
    unique = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
        if len(unique) == 5:
            break

    return unique or ["Keep logging transactions consistently to unlock personalised insights."]


# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.post("/query")
async def ask_wandaai(
    body:         AIQueryRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """Ask WandaAI a financial question about your data."""
    summary    = _get_financial_summary(current_user, db, body.months)
    currency   = current_user.currency
    confidence = _confidence_score(summary)

    if body.mode == "insights":
        response_text, insights = _generate_insight(body.question, summary, currency)
    elif body.mode == "recommendations":
        recs = _generate_recommendations("recommendations", summary, currency)
        response_text = "**Smart Recommendations:**\n\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))
        insights      = {"type": "recommendations", "count": len(recs)}
    elif body.mode == "business":
        recs = _generate_recommendations("business", summary, currency)
        response_text = "**Business Strategy Insights:**\n\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))
        insights      = {"type": "business_strategy", "count": len(recs)}
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode '{body.mode}'. Use: insights, recommendations, business",
        )

    recommendations = _generate_recommendations(body.mode, summary, currency)

    log.info(f"🤖 WandaAI: user={current_user.id} mode={body.mode} months={body.months} confidence={confidence}")

    return {
        "response":        response_text,
        "mode":            body.mode,
        "confidence":      confidence,
        "currency":        currency,
        "summary": {
            "total_income":    summary["total_income"],
            "total_expenses":  summary["total_expenses"],
            "net_profit":      summary["net_profit"],
            "profit_margin":   summary["profit_margin"],
            "transactions":    summary["transaction_count"],
            "months_analysed": summary["months_analysed"],
        },
        "insights":        insights,
        "recommendations": recommendations,
    }


@router.get("/modes")
async def get_ai_modes(current_user: User = Depends(get_current_user)):
    """List all available WandaAI analysis modes."""
    return {
        "modes": [
            {"id": "insights",        "name": "Financial Insights",    "description": "Analyse income, expenses, cash flow, and profitability",     "sample": "How is my cash flow looking?"},
            {"id": "recommendations", "name": "Smart Recommendations", "description": "Get actionable tips to save money and grow revenue",          "sample": "How can I reduce my expenses?"},
            {"id": "business",        "name": "Business Assistant",    "description": "Strategic advice on pricing, planning, and growth",           "sample": "What should I focus on to grow my business?"},
        ]
    }


@router.get("/prompts")
async def get_sample_prompts(current_user: User = Depends(get_current_user)):
    """Return sample questions users can ask WandaAI."""
    return {
        "prompts": [
            {"category": "Cash Flow",     "question": "How is my cash flow looking this month?"},
            {"category": "Spending",      "question": "Where am I spending the most money?"},
            {"category": "Income",        "question": "What is my strongest income source?"},
            {"category": "Profitability", "question": "What is my profit margin this quarter?"},
            {"category": "Savings",       "question": "How can I reduce my expenses?"},
            {"category": "Loans",         "question": "Am I ready to apply for a business loan?"},
            {"category": "Strategy",      "question": "What should I focus on to grow my business?"},
            {"category": "Overview",      "question": "Give me a full financial overview"},
        ]
    }


@router.get("/summary")
async def get_financial_summary(
    months:       int     = Query(3, ge=1, le=12),
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return a full structured financial summary without asking a question.
    Useful for dashboard cards and charts on the frontend.
    """
    summary  = _get_financial_summary(current_user, db, months)
    currency = current_user.currency

    return {
        "currency":             currency,
        "months_analysed":      summary["months_analysed"],
        "total_income":         summary["total_income"],
        "total_expenses":       summary["total_expenses"],
        "net_profit":           summary["net_profit"],
        "profit_margin":        summary["profit_margin"],
        "transaction_count":    summary["transaction_count"],
        "income_count":         summary["income_count"],
        "expense_count":        summary["expense_count"],
        "income_by_category":   summary["income_by_category"],
        "expense_by_category":  summary["expense_by_category"],
        "top_income_category":  summary["top_income_category"],
        "top_expense_category": summary["top_expense_category"],
        "confidence":           _confidence_score(summary),
        "recommendations":      _generate_recommendations("insights", summary, currency),
    }