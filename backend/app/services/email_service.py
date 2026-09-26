import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

settings = get_settings()


def is_smtp_configured() -> bool:
    return all(
        [
            settings.smtp_host,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_from_email,
        ]
    )


def _from_header() -> str:
    if settings.smtp_from_email:
        return f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    return settings.smtp_from_name


async def send_password_reset_email(*, recipient_email: str, reset_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Reset your GenSmile password"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        "We received a request to reset your GenSmile password.\n\n"
        f"Use this link to choose a new password:\n{reset_url}\n\n"
        f"This link expires in {settings.password_reset_token_expire_minutes} minutes.\n\n"
        "If you did not request this, you can safely ignore this email."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>We received a request to reset your GenSmile password.</p>
        <p>
          <a href="{reset_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Reset Password</a>
        </p>
        <p>If the button does not work, copy this link into your browser:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>This link expires in {settings.password_reset_token_expire_minutes} minutes.</p>
        <p>If you did not request this, you can safely ignore this email.</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_staff_invite_email(
    *,
    recipient_email: str,
    recipient_name: str,
    doctor_name: str,
    clinic_name: str,
    setup_url: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = f"You've been added to {clinic_name} on GenSmile"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Dr. {doctor_name} has added you as a staff member at {clinic_name} on GenSmile.\n\n"
        "Please use the link below to set up your account and choose a password:\n"
        f"{setup_url}\n\n"
        "If you have any questions, please contact your clinic administrator."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi {recipient_name},</p>
        <p>Dr. {doctor_name} has added you as a staff member at <strong>{clinic_name}</strong> on GenSmile.</p>
        <p>Please click the button below to set up your account and choose a password:</p>
        <p>
          <a href="{setup_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Set up your account</a>
        </p>
        <p>If the button does not work, copy this link into your browser:</p>
        <p><a href="{setup_url}">{setup_url}</a></p>
        <p>If you have any questions, please contact your clinic administrator.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_new_patient_welcome_email(
    *,
    recipient_email: str,
    recipient_name: str,
    doctor_name: str,
    setup_url: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = "Welcome to GenSmile"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Dr. {doctor_name} has added you as a patient on GenSmile.\n\n"
        "Your account has been created. Please use the link below to set up your password:\n"
        f"{setup_url}\n\n"
        "If you have any questions, please contact your doctor's office."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi {recipient_name},</p>
        <p>Dr. {doctor_name} has added you as a patient on <strong>GenSmile</strong>.</p>
        <p>Your account has been created. Please click the button below to set up your password:</p>
        <p>
          <a href="{setup_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Set up your account</a>
        </p>
        <p>If the button does not work, copy this link into your browser:</p>
        <p><a href="{setup_url}">{setup_url}</a></p>
        <p>If you have any questions, please contact your doctor's office.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_email_verification_email(
    *, recipient_email: str, recipient_name: str, verification_url: str
) -> None:
    message = EmailMessage()
    message["Subject"] = "Verify your GenSmile email address"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi {recipient_name},\n\n"
        "Please verify your email address to complete your GenSmile account setup.\n\n"
        f"Verify here:\n{verification_url}\n\n"
        f"This link expires in {settings.email_verification_token_expire_hours} hours.\n\n"
        "If you did not create a GenSmile account, you can safely ignore this email."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi {recipient_name},</p>
        <p>Please verify your email address to complete your GenSmile account setup.</p>
        <p>
          <a href="{verification_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Verify Email Address</a>
        </p>
        <p>If the button does not work, copy this link into your browser:</p>
        <p><a href="{verification_url}">{verification_url}</a></p>
        <p>This link expires in {settings.email_verification_token_expire_hours} hours.</p>
        <p>If you did not create a GenSmile account, you can safely ignore this email.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_drip_campaign_email(
    *,
    recipient_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = _from_header()
    message["To"] = recipient_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_renewal_reminder_email(
    *,
    recipient_email: str,
    recipient_name: str,
    plan_name: str,
    renewal_date: str,
    days_until: int,
    billing_url: str,
) -> None:
    message = EmailMessage()
    day_word = "today" if days_until == 0 else "tomorrow" if days_until == 1 else f"in {days_until} days"
    message["Subject"] = f"Your GenSmile subscription renews {day_word}"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"Your {plan_name} subscription is set to renew {day_word}, on {renewal_date}. "
        "Your payment method on file will be charged automatically -- no action is needed "
        "if everything looks right.\n\n"
        "If you'd like to review your plan, update your payment method, or cancel before "
        "the renewal, you can do so here:\n"
        f"{billing_url}\n\n"
        "If you have any questions, just reply to this email."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi {recipient_name},</p>
        <p>Your <strong>{plan_name}</strong> subscription is set to renew <strong>{day_word}</strong>,
        on {renewal_date}. Your payment method on file will be charged automatically — no action
        is needed if everything looks right.</p>
        <p>
          <a href="{billing_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Review Billing</a>
        </p>
        <p>If you'd like to review your plan, update your payment method, or cancel before the
        renewal, you can do so at the link above.</p>
        <p>If you have any questions, just reply to this email.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_payment_failed_email(
    *,
    recipient_email: str,
    recipient_name: str,
    plan_name: str,
    billing_url: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = "Action needed: your GenSmile payment failed"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi {recipient_name},\n\n"
        f"We tried to charge your payment method on file for your {plan_name} subscription, "
        "but the charge did not go through.\n\n"
        "Your access continues for now while we retry automatically, but please update your "
        "payment method soon to avoid any interruption:\n"
        f"{billing_url}\n\n"
        "If you have any questions, just reply to this email."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi {recipient_name},</p>
        <p>We tried to charge your payment method on file for your <strong>{plan_name}</strong>
        subscription, but the charge did not go through.</p>
        <p>
          <a href="{billing_url}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#dc2626;color:#fff;text-decoration:none;font-weight:600;"
          >Update Payment Method</a>
        </p>
        <p>Your access continues for now while we retry automatically, but please update your
        payment method soon to avoid any interruption.</p>
        <p>If you have any questions, just reply to this email.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


def _send_message(message: EmailMessage) -> None:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise RuntimeError("SMTP is not configured.")

    if settings.smtp_use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            host=settings.smtp_host,
            port=settings.smtp_port,
            context=context,
            timeout=30,
        ) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return

    with smtplib.SMTP(
        host=settings.smtp_host,
        port=settings.smtp_port,
        timeout=30,
    ) as server:
        server.ehlo()
        if settings.smtp_use_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
            server.ehlo()
        server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


async def send_affiliate_welcome_email(
    *,
    recipient_email: str,
    inviter_name: str,
    commission_pct: int,
    referral_link: str,
    dashboard_link: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = "You're in! Your GenSmile affiliate marketer link is ready"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        "Hi,\n\n"
        f"Congratulations -- you've accepted {inviter_name}'s invite and are now a GenSmile "
        f"affiliate marketer. You'll earn {commission_pct}% of the commission {inviter_name} "
        "earns on every sale from someone who signs up through your link.\n\n"
        "Your referral link:\n"
        f"{referral_link}\n\n"
        "This same link is also your permanent dashboard -- bookmark it and come back anytime "
        "to grab your link, check your stats, and update your payout details:\n"
        f"{dashboard_link}\n\n"
        "There's nothing else to set up."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi,</p>
        <p>Congratulations — you've accepted <strong>{inviter_name}</strong>'s invite and are now a
        GenSmile affiliate marketer. You'll earn <strong>{commission_pct}%</strong> of the commission
        {inviter_name} earns on every sale from someone who signs up through your link.</p>
        <p>
          <a href="{dashboard_link}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >View Your Dashboard</a>
        </p>
        <p>Your referral link:</p>
        <p><a href="{referral_link}">{referral_link}</a></p>
        <p>The button above takes you to the same page — bookmark it, it's also your permanent
        dashboard. Come back anytime to grab your link, check your stats, and update your payout
        details:</p>
        <p><a href="{dashboard_link}">{dashboard_link}</a></p>
        <p>There's nothing else to set up.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)


async def send_affiliate_invite_email(
    *,
    recipient_email: str,
    inviter_name: str,
    commission_pct: int,
    invite_link: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = f"{inviter_name} invited you to earn as a GenSmile affiliate marketer"
    message["From"] = _from_header()
    message["To"] = recipient_email

    text_body = (
        f"Hi,\n\n"
        f"{inviter_name} has invited you to become an affiliate marketer on GenSmile. "
        f"You'll earn {commission_pct}% of the commission {inviter_name} earns on every sale "
        "from someone who signs up through your link.\n\n"
        "Accept your invite here:\n"
        f"{invite_link}\n\n"
        "No separate account setup needed -- just fill in your name, email, and a password "
        "on that page and your referral link is ready immediately."
    )
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <p>Hi,</p>
        <p><strong>{inviter_name}</strong> has invited you to become an affiliate marketer on GenSmile.
        You'll earn <strong>{commission_pct}%</strong> of the commission {inviter_name} earns on every
        sale from someone who signs up through your link.</p>
        <p>
          <a href="{invite_link}"
            style="display:inline-block;padding:12px 20px;border-radius:9999px;background:#0052cc;color:#fff;text-decoration:none;font-weight:600;"
          >Accept Invite</a>
        </p>
        <p>If the button does not work, copy this link into your browser:</p>
        <p><a href="{invite_link}">{invite_link}</a></p>
        <p>No separate account setup needed — just fill in your name, email, and a password on that page and your referral link is ready immediately.</p>
        <p style="color:#64748b;font-size:0.875rem;">— The GenSmile Team</p>
      </body>
    </html>
    """
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send_message, message)