"""
WandaAI Routes
AI assistant endpoints for financial insights and recommendations
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random

from db import get_db
from models import User, Transaction
from schemas import AIQuery, AIResponse
from routes.auth import get_current_user

router = APIRouter(prefix="/wandaai", tags=["wandaai"])


# ═══ Helper Functions ═══
def get_user_transaction_summary(user: User, db: Session, months: int = 3):
    """Get user's transaction summary for the last N months"""
    cutoff_date = datetime.utcnow() - timedelta(days=30 * months)
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_date >= cutoff_date
    ).all()
    
    total_income = sum(t.amount for t in transactions if t.type == "income")
    total_expenses = sum(t.amount for t in transactions if t.type == "expense")
    
    income_by_category = {}
    expense_by_category = {}
    
    for t in transactions:
        if t.type == "income":
            income_by_category[t.category] = income_by_category.get(t.category, 0) + t.amount
        else:
            expense_by_category[t.category] = expense_by_category.get(t.category, 0) + t.amount
    
    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": total_income - total_expenses,
        "transaction_count": len(transactions),
        "income_by_category": income_by_category,
        "expense_by_category": expense_by_category,
        "profit_margin": (total_income - total_expenses) / total_income * 100 if total_income > 0 else 0
    }


def generate_insight_response(question: str, summary: dict) -> tuple[str, dict]:
    """Generate AI insight response based on user data"""
    question_lower = question.lower()
    
    # Cash flow insights
    if any(word in question_lower for word in ["cash", "flow", "money"]):
        if summary["net_profit"] > 0:
            response = f"Your cash flow is **healthy**! Over the last 3 months, you've had:\n\n"
            response += f"- **Income**: R {summary['total_income']:,.2f}\n"
            response += f"- **Expenses**: R {summary['total_expenses']:,.2f}\n"
            response += f"- **Net Profit**: R {summary['net_profit']:,.2f}\n\n"
            response += "Your income-to-expense ratio is solid. Keep monitoring your largest expense categories to find savings opportunities."
        else:
            response = "Your cash flow needs attention. Expenses are exceeding income. Consider reviewing your spending patterns."
        
        return response, {"type": "cash_flow_insight"}
    
    # Spending insights
    elif any(word in question_lower for word in ["spend", "expense", "cost", "where"]):
        if summary["expense_by_category"]:
            top_category = max(summary["expense_by_category"].items(), key=lambda x: x[1])
            response = f"Your top spending category is **{top_category[0]}** at R {top_category[1]:,.2f}.\n\n"
            response += "**All expenses by category**:\n"
            for cat, amount in sorted(summary["expense_by_category"].items(), key=lambda x: x[1], reverse=True):
                response += f"- {cat}: R {amount:,.2f}\n"
            response += f"\nConsider reviewing your {top_category[0]} expenses for potential savings."
        else:
            response = "No expense data available yet. Start logging transactions to get spending insights."
        
        return response, {"type": "spending_analysis"}
    
    # Profit insights
    elif any(word in question_lower for word in ["profit", "margin", "earnings"]):
        response = f"**Your Profitability Snapshot** (Last 3 Months):\n\n"
        response += f"- Gross Revenue: R {summary['total_income']:,.2f}\n"
        response += f"- Total Expenses: R {summary['total_expenses']:,.2f}\n"
        response += f"- Net Profit: R {summary['net_profit']:,.2f}\n"
        response += f"- **Profit Margin: {summary['profit_margin']:.1f}%**\n\n"
        
        if summary['profit_margin'] > 50:
            response += "Excellent! A profit margin above 50% is exceptional for most businesses."
        elif summary['profit_margin'] > 30:
            response += "Good performance! Your margin is above industry average (40%)."
        else:
            response += "Consider optimizing your cost structure to improve profitability."
        
        return response, {"type": "profitability_insight"}
    
    # Loan readiness
    elif any(word in question_lower for word in ["loan", "bank", "finance", "funding"]):
        response = f"**Loan Readiness Assessment**:\n\n"
        
        # Simple scoring
        score = 0
        if summary['net_profit'] > 10000:
            score += 25
            response += "✓ Strong profitability\n"
        if summary['profit_margin'] > 30:
            score += 25
            response += "✓ Healthy profit margin\n"
        if summary['total_income'] > summary['total_expenses']:
            score += 25
            response += "✓ Positive cash flow\n"
        if summary['transaction_count'] > 20:
            score += 25
            response += "✓ Consistent transaction history\n"
        
        response += f"\n**Loan Readiness Score: {score}/100**\n\n"
        
        if score >= 75:
            response += "You appear **loan-ready**! Your financial metrics are strong. Consider approaching your bank with our Loan Application Report."
        elif score >= 50:
            response += "You're on the right track. Focus on increasing profitability and consistent income to strengthen your loan application."
        else:
            response += "Build a stronger financial foundation before applying for loans. Focus on revenue growth and expense management."
        
        return response, {"type": "loan_assessment"}
    
    # Default response
    else:
        response = "Based on your financial data, here are some observations:\n\n"
        response += f"- You've logged **{summary['transaction_count']}** transactions\n"
        response += f"- Your profit margin is **{summary['profit_margin']:.1f}%**\n"
        response += f"- Your largest expense category is **{max(summary['expense_by_category'].items(), key=lambda x: x[1])[0] if summary['expense_by_category'] else 'N/A'}**\n\n"
        response += "Try asking me about cash flow, spending patterns, profitability, or loan readiness for deeper analysis!"
        
        return response, {"type": "general_insight"}


def generate_recommendation(mode: str, summary: dict) -> list:
    """Generate AI recommendations based on mode and user data"""
    recommendations = []
    
    if mode == "insights":
        if summary['net_profit'] > 0:
            recommendations.append("Your positive cash flow is a strong foundation. Reinvest profits strategically.")
        
        if summary['profit_margin'] > 50:
            recommendations.append("Your profit margin is excellent. Consider scaling your business.")
        
        top_category = max(summary['expense_by_category'].items(), key=lambda x: x[1])[0] if summary['expense_by_category'] else None
        if top_category:
            recommendations.append(f"Your largest expense is {top_category}. Review this category quarterly for savings.")
    
    elif mode == "recommendations":
        if summary['total_expenses'] > summary['total_income'] * 0.7:
            recommendations.append("Consider reducing discretionary expenses to improve cash flow.")
        
        if summary['profit_margin'] < 30:
            recommendations.append("Focus on increasing revenue or reducing fixed costs to improve margins.")
        
        recommendations.append("Track recurring expenses monthly to identify reduction opportunities.")
        recommendations.append("Set aside 20% of revenue as emergency reserves.")
        recommendations.append("Review pricing strategy quarterly to ensure profitability.")
    
    elif mode == "business":
        recommendations.append("Growth strategy: Focus on your top-performing income categories.")
        recommendations.append("Consider automation for high-frequency transactions to save time.")
        recommendations.append("Build a 3-month cash reserve for business sustainability.")
        recommendations.append("Implement a quarterly financial review process with your accountant.")
        recommendations.append("Track key metrics (profit margin, revenue growth) to guide business decisions.")
    
    return recommendations if recommendations else ["Keep monitoring your financial metrics for better insights."]


# ═══ Endpoints ═══

@router.post("/query", response_model=AIResponse)
async def ask_wandaai(
    query: AIQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ask WandaAI a financial question
    
    - **question**: Your financial question
    - **mode**: insights, recommendations, or business
    """
    # Get user's transaction data
    summary = get_user_transaction_summary(current_user, db)
    
    # Generate response based on mode
    if query.mode == "insights":
        response_text, insights = generate_insight_response(query.question, summary)
    elif query.mode == "recommendations":
        recommendations = generate_recommendation("recommendations", summary)
        response_text = "**Smart Recommendations** based on your financial data:\n\n"
        for i, rec in enumerate(recommendations, 1):
            response_text += f"{i}. {rec}\n"
        insights = {"type": "recommendations", "count": len(recommendations)}
    elif query.mode == "business":
        recommendations = generate_recommendation("business", summary)
        response_text = "**Business Strategy Insights**:\n\n"
        for i, rec in enumerate(recommendations, 1):
            response_text += f"{i}. {rec}\n"
        insights = {"type": "business_strategy", "count": len(recommendations)}
    else:
        response_text = "I didn't understand that. Try asking about cash flow, spending, profitability, or loan readiness."
        insights = None
    
    # Generate recommendations based on mode
    recommendations = generate_recommendation(query.mode, summary)
    
    return AIResponse(
        response=response_text,
        mode=query.mode,
        confidence=random.uniform(0.85, 0.99),  # Simulated confidence
        insights=insights,
        recommendations=recommendations[:3]  # Top 3 recommendations
    )


@router.get("/modes")
async def get_ai_modes(current_user: User = Depends(get_current_user)):
    """Get available WandaAI modes"""
    return {
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


@router.get("/prompts")
async def get_sample_prompts(current_user: User = Depends(get_current_user)):
    """Get sample prompts for WandaAI"""
    return {
        "prompts": [
            "How is my cash flow looking this month?",
            "Where am I spending the most money?",
            "What is my profit margin this month?",
            "How can I reduce my expenses?",
            "Am I ready to apply for a business loan?",
            "What financial goals should I set for next month?"
        ]
    }
