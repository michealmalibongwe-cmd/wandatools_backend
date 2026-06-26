"""
WandaTools — services/email.py
Location: services/ folder (services/email.py)

SMTP email service — all transactional emails sent by WandaTools.

Source of truth:
  Low-level send_email(), _contact_email_html(), _contact_confirm_html()
  are defined in main.py and RE-EXPORTED here.
  EmailService adds higher-level methods on top.

Methods:
  send_email()                  — low-level passthrough (any email)
  send_verification_email()     — account email verification link
  send_password_reset_email()   — password reset link
  send_mfa_otp()                — 6-digit OTP for MFA login
  send_welcome_email()          — welcome message after registration
  send_contact_notification()   — notify support team of contact form
  send_contact_confirmation()   — confirm receipt to the submitting user

Railway env vars required:
  SMTP_HOST      (default: smtp.gmail.com)
  SMTP_PORT      (default: 587)
  SMTP_USER      your sending email address
  SMTP_PASSWORD  Gmail App Password or SMTP password
  SUPPORT_EMAIL  email that receives contact form submissions
  FRONTEND_URL   base URL for links (e.g. https://wandatools.vercel.app)
"""

import logging
import os
from datetime import datetime

from main import (
    send_email,
    _contact_email_html,
    _contact_confirm_html,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    SUPPORT_EMAIL,
)

log = logging.getLogger("wandatools.email")

# Frontend URL for building links in emails
FRONTEND_URL   = os.getenv("FRONTEND_URL", "https://wandatools.vercel.app")

# Brand colours
_BRAND_PRIMARY = "#007BFF"
_BRAND_SUCCESS = "#28A745"
_BRAND_WARNING = "#FFC107"
_BRAND_DANGER  = "#DC3545"


# ─────────────────────────────────────────────────────────────
# SHARED TEMPLATE HELPERS
# ─────────────────────────────────────────────────────────────

def _base_template(title: str, body_html: str, accent: str = _BRAND_PRIMARY) -> str:
    """Consistent branded HTML wrapper for every email."""
    year = datetime.utcnow().year
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{title}</title>
    </head>
    <body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;color:#333;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:40px 20px;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;overflow:hidden;
                        box-shadow:0 2px 8px rgba(0,0,0,.08);max-width:600px;width:100%;">
            <tr>
              <td style="background:linear-gradient(135deg,{accent} 0%,#28A745 100%);
                         padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#fff;font-size:24px;letter-spacing:.5px;">
                  💚 WandaTools
                </h1>
                <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:13px;">
                  AI-Powered Financial Management · Eswatini 🇸🇿
                </p>
              </td>
            </tr>
            <tr><td style="padding:40px;">{body_html}</td></tr>
            <tr>
              <td style="background:#f9f9f9;padding:20px 40px;border-top:1px solid #eee;
                         text-align:center;">
                <p style="margin:0;color:#aaa;font-size:12px;">
                  © {year} WandaTools · admin@wandatools.com<br>
                  <a href="{FRONTEND_URL}" style="color:{accent};text-decoration:none;">
                    wandatools.vercel.app
                  </a>
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """


def _cta_button(text: str, url: str, color: str = _BRAND_PRIMARY) -> str:
    """Reusable CTA button block."""
    return f"""
    <div style="text-align:center;margin:32px 0;">
      <a href="{url}"
         style="display:inline-block;background:{color};color:#fff;
                padding:14px 36px;border-radius:8px;text-decoration:none;
                font-weight:bold;font-size:16px;">
        {text}
      </a>
    </div>
    <p style="text-align:center;color:#888;font-size:12px;margin-top:-16px;">
      Or copy this link:<br>
      <a href="{url}" style="color:{color};word-break:break-all;font-size:11px;">{url}</a>
    </p>
    """


def _warning_box(text: str, color: str = _BRAND_WARNING) -> str:
    """Reusable warning/info box."""
    return f"""
    <div style="background:#fff8e1;border-left:4px solid {color};
                padding:14px 18px;border-radius:4px;margin:24px 0;">
      <p style="margin:0;color:#7a6000;font-size:13px;">{text}</p>
    </div>
    """


# ─────────────────────────────────────────────────────────────
# EMAIL SERVICE
# ─────────────────────────────────────────────────────────────

class EmailService:
    """
    High-level email service for WandaTools transactional emails.
    All methods are static — no instantiation needed.

    Usage:
        from services.email import EmailService
        EmailService.send_welcome_email(email, name, currency)
    """

    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """Low-level passthrough — send any email via main.py's send_email()."""
        return send_email(to=to_email, subject=subject, html_body=html_content)

    @staticmethod
    def send_verification_email(email: str, token: str, name: str) -> bool:
        """Send account email verification link after registration."""
        url  = f"{FRONTEND_URL}/verify-email?token={token}"
        body = f"""
        <h2 style="color:#333;margin-top:0;">Welcome to WandaTools, {name}! 👋</h2>
        <p style="color:#555;line-height:1.7;">
          Please verify your email address to activate your account.
        </p>
        {_cta_button("✅ Verify My Email", url, _BRAND_SUCCESS)}
        {_warning_box("⏰ This link expires in <strong>24 hours</strong>. "
                      "If you didn't create a WandaTools account, ignore this email.")}
        """
        html = _base_template(f"Verify your WandaTools email — {name}", body, _BRAND_SUCCESS)
        sent = send_email(to=email, subject="✅ Verify your WandaTools email address", html_body=html)
        if sent:
            log.info(f"📧 Verification email sent to {email}")
        else:
            log.warning(f"⚠️  Verification email failed for {email}")
        return sent

    @staticmethod
    def send_password_reset_email(email: str, token: str, name: str) -> bool:
        """Send a password reset link. Token expires in 1 hour."""
        url  = f"{FRONTEND_URL}/reset-password?token={token}"
        body = f"""
        <h2 style="color:#333;margin-top:0;">Password Reset Request</h2>
        <p style="color:#555;line-height:1.7;">Hi <strong>{name}</strong>,</p>
        <p style="color:#555;line-height:1.7;">
          Click the button below to reset your WandaTools password.
        </p>
        {_cta_button("🔑 Reset My Password", url, _BRAND_PRIMARY)}
        {_warning_box(
            "⚠️ <strong>Security notice:</strong> This link expires in <strong>1 hour</strong>. "
            "If you did not request this, ignore this email.",
            _BRAND_DANGER
        )}
        """
        html = _base_template("Reset your WandaTools password", body, _BRAND_DANGER)
        sent = send_email(to=email, subject="🔑 Reset your WandaTools password", html_body=html)
        if sent:
            log.info(f"📧 Password reset email sent to {email}")
        else:
            log.warning(f"⚠️  Password reset email failed for {email}")
        return sent

    @staticmethod
    def send_mfa_otp(email: str, otp: str, name: str) -> bool:
        """Send a 6-digit OTP for email-based MFA. Expires in 10 minutes."""
        body = f"""
        <h2 style="color:#333;margin-top:0;">Your WandaTools Login Code</h2>
        <p style="color:#555;line-height:1.7;">Hi <strong>{name}</strong>,</p>
        <div style="background:#f0f4ff;border:2px solid {_BRAND_PRIMARY};border-radius:12px;
                    padding:24px;text-align:center;margin:24px 0;">
          <p style="font-size:48px;font-weight:bold;color:{_BRAND_PRIMARY};
                    letter-spacing:10px;margin:0;font-family:monospace;">
            {otp}
          </p>
        </div>
        <p style="text-align:center;color:#888;font-size:13px;">
          ⏰ This code expires in <strong>10 minutes</strong>.
        </p>
        {_warning_box(
            "🔒 <strong>Never share this code</strong> with anyone. "
            "WandaTools staff will never ask for your OTP.",
            _BRAND_WARNING
        )}
        """
        html = _base_template("Your WandaTools Login Code", body, _BRAND_PRIMARY)
        sent = send_email(to=email, subject=f"🔐 Your WandaTools code: {otp}", html_body=html)
        if sent:
            log.info(f"📧 MFA OTP sent to {email}")
        else:
            log.warning(f"⚠️  MFA OTP email failed for {email}")
        return sent

    @staticmethod
    def send_welcome_email(email: str, name: str, currency: str = "E") -> bool:
        """Send welcome email after successful registration."""
        dashboard_url = f"{FRONTEND_URL}/dashboard"
        body = f"""
        <h2 style="color:#333;margin-top:0;">You're in! Welcome to WandaTools 🎉</h2>
        <p style="color:#555;line-height:1.7;">Hi <strong>{name}</strong>,</p>
        <p style="color:#555;line-height:1.7;">Your account is ready. Here's what you can do:</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
          <tr>
            <td style="padding:10px;background:#f0fdf4;border-radius:8px;
                       border-left:4px solid {_BRAND_SUCCESS};">
              💰 <strong>Log transactions</strong> — track income &amp; expenses in {currency}
            </td>
          </tr>
          <tr><td style="height:8px;"></td></tr>
          <tr>
            <td style="padding:10px;background:#f0f4ff;border-radius:8px;
                       border-left:4px solid {_BRAND_PRIMARY};">
              📊 <strong>View your dashboard</strong> — charts, KPIs, monthly breakdowns
            </td>
          </tr>
          <tr><td style="height:8px;"></td></tr>
          <tr>
            <td style="padding:10px;background:#fff8e1;border-radius:8px;
                       border-left:4px solid {_BRAND_WARNING};">
              🤖 <strong>Ask WandaAI</strong> — get AI insights on your cash flow and spending
            </td>
          </tr>
        </table>
        {_cta_button("🚀 Go to my Dashboard", dashboard_url, _BRAND_SUCCESS)}
        <p style="color:#888;font-size:12px;text-align:center;">
          Questions? Email
          <a href="mailto:admin@wandatools.com" style="color:{_BRAND_PRIMARY};">
            admin@wandatools.com
          </a>
        </p>
        """
        html = _base_template(f"Welcome to WandaTools, {name}!", body, _BRAND_SUCCESS)
        sent = send_email(to=email, subject=f"🎉 Welcome to WandaTools, {name}!", html_body=html)
        if sent:
            log.info(f"📧 Welcome email sent to {email}")
        else:
            log.warning(f"⚠️  Welcome email failed for {email}")
        return sent

    @staticmethod
    def send_contact_notification(name: str, sender_email: str,
                                   subject: str, message: str, msg_id: int) -> bool:
        """Send contact form notification to support team."""
        return send_email(
            to=SUPPORT_EMAIL,
            subject=f"[WandaTools Support #{msg_id}] {subject}",
            html_body=_contact_email_html(name, sender_email, subject, message),
        )

    @staticmethod
    def send_contact_confirmation(name: str, recipient_email: str) -> bool:
        """Send confirmation to user after submitting contact form."""
        return send_email(
            to=recipient_email,
            subject="✅ We received your message — WandaTools Support",
            html_body=_contact_confirm_html(name),
        )