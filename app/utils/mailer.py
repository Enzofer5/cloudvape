"""Envío de correos vía SMTP. Si no hay SMTP configurado, se registra en el log (modo desarrollo)."""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        current_app.logger.warning(
            "SMTP no configurado. Email para %s | %s\n%s", to, subject, text_body
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["MAIL_DEFAULT_SENDER"]
    msg["To"] = to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15) as smtp:
            if cfg.get("MAIL_USE_TLS"):
                smtp.starttls()
            if cfg.get("MAIL_USERNAME"):
                smtp.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        current_app.logger.exception("Error enviando email a %s", to)
        return False
