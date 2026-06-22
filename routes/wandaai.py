"""
WandaTools — routes/wandaai.py
WandaAI financial intelligence endpoints.

Endpoints:
  POST  /api/v1/wandaai/query    — ask WandaAI a financial question
  GET   /api/v1/wandaai/modes    — list available AI modes
  GET   /api/v1/wandaai/prompts  — get sample questions to ask
  GET   /api/v1/wandaai/summary  — get a full financial snapshot (no question needed)
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from db import get_db
from main import User, Transaction
from routes.auth import get_current_user

log = logging.getLogger("wandatools.wandaai")

router = APIRouter(prefix="/api/v1/wandaai", tags=["WandaAI"])

# ─────────────────────────────────────────────────────────────
# VALID MODES
# ─────────────────────────────────────────────────────────────

VALID_MODES = {"insights", "recommendations", "business"}


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────────────────────

class AIQueryRequest(BaseModel):
    question: str
    mode:     str = "insights"
    months:   int = 3           # how many months of data to analyse

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


class AIResponse(BaseModel):
    response:        str
    mode:            str
    confidence:      float
    currency:        str
    summary:         dict
    insights:        dict | None
    recommendations: list[str]


# ─────────────────────────────────────────────────────────────
# CORE DATA HELPER — pulls and aggregates user transactions
# ─────────────────────────────────────────────────────────────

def _get_financial_summary(user: User, db: Session, months: int = 3) -> dict:
    """
    Query the last N months of transactions for the user and return
    a structured summary used by all AI response generators.
    Raises HTTPException 500 if the DB query fails.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=30 * months)
        transactions = (
            db.query(Transaction)
            .filter(
                Transaction.user_id          == user.id,
                Transaction.transaction_date >= cutoff,
            )
            .all()
        )
    except Exception as exc:
        log.error(f"wandaai DB query error for user {user.id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not load transaction data: {exc}",
        )

    income_txns  = [t for t in transactions if t.type == "income"]
    expense_txns = [t for t in transactions if t.type == "expense"]

    total_income   = sum(t.amount for t in income_txns)
    total_expenses = sum(t.amount for t in expense_txns)
    net_profit     = total_income - total_expenses
    profit_margin  = (net_profit / total_income * 100) if total_income > 0 else 0.0

    # Group by category
    income_by_category:  dict[str, float] = {}
    expense_by_category: dict[str, float] = {}

    for t in income_txns:
        income_by_category[t.category] = income_by_category.get(t.category, 0.0) + t.amount
    for t in expense_txns:
        expense_by_category[t.category] = expense_by_category.get(t.category, 0.0) + t.amount

    # Top categories (safe — returns None if empty)
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
    """
    Return a confidence score (0.0 – 1.0) based on how much data
    the user has. More transactions = higher confidence.
    This is honest — not a fake random number.
    """
    count = summary["transaction_count"]
    if count == 0:   return 0.10
    if count < 5:    return 0.40
    if count < 15:   return 0.65
    if count < 30:   return 0.80
    if count < 60:   return 0.90
    return 0.97


# ─────────────────────────────────────────────────────────────
# RESPONSE GENERATORS — one per topic keyword
# ─────────────────────────────────────────────────────────────

def _fmt(amount: float, currency: str) -> str:
    """Format a currency amount: E 1,234.56"""
    return f"{currency} {amount:,.2f}"


def _generate_insight(question: str, summary: dict, currency: str) -> tuple[str, dict]:
    """
    Match the question to a financial topic and return
    (response_text, insights_dict).
    Falls back to a general overview if no topic matches.
    """
    q = question.lower()

    # ── Cash flow ─────────────────────────────────────────────
    if any(w in q for w in ["cash", "flow", "money", "liquidity"]):
        if summary["net_profit"] > 0:
            status_line = "✅ Your cash flow is **healthy**."
            advice      = (
                "Keep monitoring your largest expense categories monthly "
                "to protect this positive trend."
            )
        elif summary["net_profit"] == 0:
            status_line = "⚠️ Your cash flow is **breaking even**."
            advice      = "Look for small expense cuts to tip into profitability."
        else:
            status_line = "🔴 Your cash flow is **negative** — expenses exceed income."
            advice      = (
                "Review your top expense categories immediately and look for "
                "quick cost reductions."
            )

        text = (
            f"{status_line}\n\n"
            f"**Last {summary['months_analysed']} months:**\n"
            f"- Income:    {_fmt(summary['total_income'],   currency)}\n"
            f"- Expenses:  {_fmt(summary['total_expenses'], currency)}\n"
            f"- Net:       {_fmt(summary['net_profit'],     currency)}\n\n"
            f"{advice}"
        )
        return text, {"type": "cash_flow", "status": "positive" if summary["net_profit"] > 0 else "negative"}

    # ── Spending / expenses ───────────────────────────────────
    elif any(w in q for w in ["spend", "expense", "cost", "where", "buying", "paying"]):
        if not summary["expense_by_category"]:
            return (
                "No expense transactions found in this period. "
                "Add some expense records to get spending analysis.",
                {"type": "spending_analysis", "data_available": False},
            )

        top    = summary["top_expense_category"]
        top_amt = summary["expense_by_category"][top]
        pct    = (top_amt / summary["total_expenses"] * 100) if summary["total_expenses"] > 0 else 0

        lines = "\n".join(
            f"- {cat}: {_fmt(amt, currency)} ({amt / summary['total_expenses'] * 100:.1f}%)"
            for cat, amt in sorted(
                summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True
            )
        )

        text = (
            f"Your top spending category is **{top}** at {_fmt(top_amt, currency)} "
            f"({pct:.1f}% of total expenses).\n\n"
            f"**All expense categories:**\n{lines}\n\n"
            f"💡 Tip: Review **{top}** expenses first — they have the biggest impact on your bottom line."
        )
        return text, {"type": "spending_analysis", "top_category": top, "data_available": True}

    # ── Income / revenue ─────────────────────────────────────
    elif any(w in q for w in ["income", "revenue", "earn", "sales", "source"]):
        if not summary["income_by_category"]:
            return (
                "No income transactions found in this period. "
                "Add income records to get revenue analysis.",
                {"type": "income_analysis", "data_available": False},
            )

        top     = summary["top_income_category"]
        top_amt = summary["income_by_category"][top]

        lines = "\n".join(
            f"- {cat}: {_fmt(amt, currency)}"
            for cat, amt in sorted(
                summary["income_by_category"].items(), key=lambda x: x[1], reverse=True
            )
        )

        text = (
            f"Your strongest income source is **{top}** at {_fmt(top_amt, currency)}.\n\n"
            f"**All income sources:**\n{lines}\n\n"
            f"💡 Tip: Double down on **{top}** — it's your highest-performing revenue stream."
        )
        return text, {"type": "income_analysis", "top_source": top, "data_available": True}

    # ── Profit / margin ───────────────────────────────────────
    elif any(w in q for w in ["profit", "margin", "earnings", "return"]):
        margin = summary["profit_margin"]

        if margin > 50:
            verdict = "🌟 Exceptional — above 50% is outstanding for most businesses."
        elif margin > 30:
            verdict = "✅ Strong — above 30% is above industry average."
        elif margin > 10:
            verdict = "⚠️ Moderate — there's room to improve. Target 30%+."
        elif margin > 0:
            verdict = "🔴 Low — your cost structure needs review."
        else:
            verdict = "🔴 Negative margin — you are operating at a loss."

        text = (
            f"**Profitability Snapshot — Last {summary['months_analysed']} Months:**\n\n"
            f"- Gross Revenue:  {_fmt(summary['total_income'],   currency)}\n"
            f"- Total Expenses: {_fmt(summary['total_expenses'], currency)}\n"
            f"- Net Profit:     {_fmt(summary['net_profit'],     currency)}\n"
            f"- Profit Margin:  **{margin:.1f}%**\n\n"
            f"{verdict}"
        )
        return text, {"type": "profitability", "margin": margin}

    # ── Loan readiness ───────────────────────────────────────
    elif any(w in q for w in ["loan", "bank", "borrow", "finance", "funding", "credit"]):
        score   = 0
        factors = []

        if summary["net_profit"] > 0:
            score += 25
            factors.append(f"✅ Positive net profit ({_fmt(summary['net_profit'], currency)})")
        else:
            factors.append(f"❌ Negative net profit — lenders require positive cash flow")

        if summary["profit_margin"] >= 20:
            score += 25
            factors.append(f"✅ Profit margin {summary['profit_margin']:.1f}% (≥ 20% threshold)")
        else:
            factors.append(f"❌ Profit margin {summary['profit_margin']:.1f}% — lenders prefer 20%+")

        if summary["total_income"] >= summary["total_expenses"]:
            score += 25
            factors.append("✅ Income covers expenses")
        else:
            factors.append("❌ Expenses exceed income")

        if summary["transaction_count"] >= 20:
            score += 25
            factors.append(f"✅ {summary['transaction_count']} transactions — sufficient history")
        else:
            factors.append(f"⚠️ Only {summary['transaction_count']} transactions — build more history")

        if score >= 75:
            verdict = "**You appear loan-ready.** Present our Loan Application Report to your bank."
        elif score >= 50:
            verdict = "**Borderline.** Improve profitability and transaction history before applying."
        else:
            verdict = "**Not yet loan-ready.** Focus on positive cash flow and consistent income first."

        factor_list = "\n".join(f"  {f}" for f in factors)
        text = (
            f"**Loan Readiness Assessment:**\n\n"
            f"{factor_list}\n\n"
            f"**Score: {score}/100**\n\n"
            f"{verdict}"
        )
        return text, {"type": "loan_assessment", "score": score}

    # ── Savings / reduce costs ────────────────────────────────
    elif any(w in q for w in ["save", "saving", "reduce", "cut", "cheaper"]):
        if not summary["expense_by_category"]:
            return (
                "No expense data available. Add expense transactions to get savings tips.",
                {"type": "savings_advice", "data_available": False},
            )

        sorted_expenses = sorted(
            summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True
        )
        tips = []
        for i, (cat, amt) in enumerate(sorted_expenses[:3], 1):
            pct = (amt / summary["total_expenses"] * 100) if summary["total_expenses"] > 0 else 0
            tips.append(
                f"{i}. **{cat}** — {_fmt(amt, currency)} ({pct:.1f}% of expenses). "
                f"Review this for potential savings."
            )

        text = (
            f"**Top savings opportunities based on your data:**\n\n"
            + "\n".join(tips)
            + "\n\n💡 Even a 10% reduction in your top expense category saves "
            + _fmt(sorted_expenses[0][1] * 0.10, currency) + " over this period."
        )
        return text, {"type": "savings_advice", "data_available": True}

    # ── General fallback ─────────────────────────────────────
    else:
        top_expense = (
            f"**{summary['top_expense_category']}**"
            if summary["top_expense_category"]
            else "N/A (no expenses logged)"
        )
        top_income = (
            f"**{summary['top_income_category']}**"
            if summary["top_income_category"]
            else "N/A (no income logged)"
        )

        text = (
            f"**Your Financial Snapshot — Last {summary['months_analysed']} Months:**\n\n"
            f"- Transactions logged: **{summary['transaction_count']}**\n"
            f"- Total Income:  {_fmt(summary['total_income'],   currency)}\n"
            f"- Total Expenses:{_fmt(summary['total_expenses'], currency)}\n"
            f"- Net Profit:    {_fmt(summary['net_profit'],     currency)}\n"
            f"- Profit Margin: **{summary['profit_margin']:.1f}%**\n"
            f"- Top income source:  {top_income}\n"
            f"- Top expense source: {top_expense}\n\n"
            f"Try asking me about:\n"
            f"- Cash flow\n- Spending patterns\n- Profitability\n"
            f"- Loan readiness\n- Savings opportunities"
        )
        return text, {"type": "general_overview"}


# ─────────────────────────────────────────────────────────────
# RECOMMENDATION GENERATOR
# ─────────────────────────────────────────────────────────────

def _generate_recommendations(mode: str, summary: dict, currency: str) -> list[str]:
    """
    Return a list of actionable recommendations tailored to
    the user's actual data and the requested mode.
    """
    recs: list[str] = []

    # ── Data-driven recommendations (always included first) ──
    if summary["net_profit"] < 0:
        recs.append(
            f"🔴 Your expenses exceed income by "
            f"{_fmt(abs(summary['net_profit']), currency)}. "
            f"Reducing your top expense category is the fastest fix."
        )

    if summary["profit_margin"] < 20 and summary["total_income"] > 0:
        recs.append(
            f"📈 Target a 20%+ profit margin. You're currently at "
            f"{summary['profit_margin']:.1f}%. "
            f"Either increase pricing or cut the top 2 expense categories."
        )

    if summary["transaction_count"] < 10:
        recs.append(
            "📝 Log transactions consistently — the more data you add, "
            "the more accurate WandaAI's insights become."
        )

    if summary["top_expense_category"]:
        top_amt = summary["expense_by_category"][summary["top_expense_category"]]
        recs.append(
            f"🔍 Review **{summary['top_expense_category']}** expenses "
            f"({_fmt(top_amt, currency)}) — your largest cost centre."
        )

    # ── Mode-specific recommendations ────────────────────────
    if mode == "recommendations":
        if summary["total_expenses"] > summary["total_income"] * 0.7:
            recs.append(
                "⚠️ Expenses are above 70% of income. "
                "Set a budget cap on discretionary spending."
            )
        recs.append("💰 Set aside 20% of monthly revenue as an emergency reserve.")
        recs.append("📅 Review your pricing strategy every quarter to stay profitable.")
        recs.append("🔄 Automate recurring expense tracking to save time each month.")

    elif mode == "business":
        if summary["top_income_category"]:
            recs.append(
                f"🚀 Double down on **{summary['top_income_category']}** — "
                f"your highest-performing revenue stream."
            )
        recs.append("🏦 Build a 3-month cash reserve for business resilience.")
        recs.append("📊 Schedule a quarterly financial review with your accountant.")
        recs.append(
            "📋 Track 3 key metrics monthly: profit margin, revenue growth, and expense ratio."
        )

    elif mode == "insights":
        if summary["net_profit"] > 0:
            recs.append(
                f"✅ Reinvest a portion of your "
                f"{_fmt(summary['net_profit'], currency)} profit into growth activities."
            )
        recs.append("📆 Compare this month vs last month to spot trends early.")

    # De-duplicate while preserving order, cap at 5
    seen:    set[str] = set()
    unique:  list[str] = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
        if len(unique) == 5:
            break

    return unique if unique else [
        "Keep logging transactions consistently to unlock more personalised insights."
    ]


# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────

@router.post("/query")
async def ask_wandaai(
    body:         AIQueryRequest,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Ask WandaAI a financial question.

    - **question**: What you want to know (cash flow, spending, profit, loans, savings…)
    - **mode**: insights | recommendations | business
    - **months**: How many months of data to analyse (1–12, default 3)
    """
    summary    = _get_financial_summary(current_user, db, body.months)
    currency   = current_user.currency
    confidence = _confidence_score(summary)

    if body.mode == "insights":
        response_text, insights = _generate_insight(body.question, summary, currency)

    elif body.mode == "recommendations":
        recs = _generate_recommendations("recommendations", summary, currency)
        response_text = (
            "**Smart Recommendations** based on your financial data:\n\n"
            + "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))
        )
        insights = {"type": "recommendations", "count": len(recs)}

    elif body.mode == "business":
        recs = _generate_recommendations("business", summary, currency)
        response_text = (
            "**Business Strategy Insights:**\n\n"
            + "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))
        )
        insights = {"type": "business_strategy", "count": len(recs)}

    else:
        # Should never reach here — Pydantic validator blocks invalid modes
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid mode '{body.mode}'. Use: insights, recommendations, business",
        )

    recommendations = _generate_recommendations(body.mode, summary, currency)

    log.info(
        f"🤖 WandaAI query — user {current_user.id} | "
        f"mode={body.mode} | months={body.months} | "
        f"txns={summary['transaction_count']} | confidence={confidence}"
    )

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
            {
                "id":          "insights",
                "name":        "Financial Insights",
                "description": "Analyse your income, expenses, cash flow, and profitability",
                "sample":      "How is my cash flow looking?",
            },
            {
                "id":          "recommendations",
                "name":        "Smart Recommendations",
                "description": "Get actionable tips to save money and grow revenue",
                "sample":      "How can I reduce my expenses?",
            },
            {
                "id":          "business",
                "name":        "Business Assistant",
                "description": "Strategic advice on pricing, planning, and growth",
                "sample":      "What should I focus on to grow my business?",
            },
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
    months:       int     = 3,
    current_user: User    = Depends(get_current_user),
    db:           Session = Depends(get_db),
):
    """
    Return a full structured financial summary without asking a question.
    Useful for dashboard cards and charts on the frontend.
    months: 1–12 (default 3)
    """
    if not (1 <= months <= 12):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="months must be between 1 and 12",
        )

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