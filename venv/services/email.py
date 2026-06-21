"""
Email service for WandaTools
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class EmailService:
    """Send emails via SMTP"""
    
    @staticmethod
    def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """Send email"""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_USER
            msg["To"] = to_email
            
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, to_email, msg.as_string())
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    @staticmethod
    def send_verification_email(email: str, token: str, name: str) -> bool:
        """Send email verification"""
        verification_url = f"https://your-domain.com/verify-email?token={token}"
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 20px; border-radius: 8px;">
                    <h1 style="color: #667eea;">Welcome to WandaTools, {name}!</h1>
                    <p>Thank you for signing up. Please verify your email to activate your account.</p>
                    
                    <div style="margin: 30px 0;">
                        <a href="{verification_url}" style="
                            display: inline-block;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 12px 30px;
                            border-radius: 8px;
                            text-decoration: none;
                            font-weight: bold;
                        ">Verify Email</a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">Or copy this link:</p>
                    <p style="background: white; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 12px;">
                        {verification_url}
                    </p>
                    
                    <p style="color: #999; font-size: 12px; margin-top: 20px;">
                        This link expires in 24 hours.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px;">
                        WandaTools - AI-Powered Financial Management<br>
                        © 2025 All rights reserved.
                    </p>
                </div>
            </body>
        </html>
        """
        
        return EmailService.send_email(email, "Verify Your WandaTools Email", html)
    
    @staticmethod
    def send_password_reset_email(email: str, token: str, name: str) -> bool:
        """Send password reset link"""
        reset_url = f"https://your-domain.com/reset-password?token={token}"
        
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 20px; border-radius: 8px;">
                    <h1 style="color: #667eea;">Password Reset Request</h1>
                    <p>Hi {name},</p>
                    <p>You requested to reset your WandaTools password. Click the button below to set a new password.</p>
                    
                    <div style="margin: 30px 0;">
                        <a href="{reset_url}" style="
                            display: inline-block;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 12px 30px;
                            border-radius: 8px;
                            text-decoration: none;
                            font-weight: bold;
                        ">Reset Password</a>
                    </div>
                    
                    <p style="color: #666; font-size: 14px;">Or copy this link:</p>
                    <p style="background: white; padding: 10px; border-radius: 4px; word-break: break-all; font-size: 12px;">
                        {reset_url}
                    </p>
                    
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 4px; margin: 20px 0;">
                        <p style="color: #856404; margin: 0;">
                            <strong>⚠️ Security Warning:</strong> If you didn't request this, ignore this email. Your password is safe.
                        </p>
                    </div>
                    
                    <p style="color: #999; font-size: 12px;">
                        This link expires in 1 hour.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px;">
                        WandaTools - AI-Powered Financial Management<br>
                        © 2025 All rights reserved.
                    </p>
                </div>
            </body>
        </html>
        """
        
        return EmailService.send_email(email, "Reset Your WandaTools Password", html)
    
    @staticmethod
    def send_mfa_otp(email: str, otp: str, name: str) -> bool:
        """Send MFA OTP"""
        html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 20px; border-radius: 8px;">
                    <h1 style="color: #667eea;">Your WandaTools Login Code</h1>
                    <p>Hi {name},</p>
                    <p>Your one-time password (OTP) for WandaTools is:</p>
                    
                    <div style="
                        background: white;
                        border: 2px solid #667eea;
                        border-radius: 8px;
                        padding: 20px;
                        text-align: center;
                        margin: 20px 0;
                    ">
                        <p style="font-size: 48px; font-weight: bold; color: #667eea; letter-spacing: 5px; margin: 0;">
                            {otp}
                        </p>
                    </div>
                    
                    <p style="color: #666;">This code expires in 10 minutes.</p>
                    
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; border-radius: 4px;">
                        <p style="color: #856404; margin: 0;">
                            <strong>🔒 Security:</strong> Never share this code with anyone. WandaTools will never ask for your OTP.
                        </p>
                    </div>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px;">
                        WandaTools - AI-Powered Financial Management<br>
                        © 2025 All rights reserved.
                    </p>
                </div>
            </body>
        </html>
        """
        
        return EmailService.send_email(email, "Your WandaTools Login Code", html)