import frappe
from frappe.utils.file_manager import get_file
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import smtplib

def send_mail(
    From: str,
    to: list[str],
    cc: list[str] = None,
    bcc: list[str] = None,
    subject: str = "",
    email_template_name: str = "",
    context: dict = None,
    attachments: list[dict[str, str]] = None,
    message: str = ""
) -> bool:
    """
    Sends an email with optional CC, BCC, and attachments using an email template rendered with context or a raw message in `message`.
    """

    cc = cc or []
    bcc = bcc or []
    attachments = attachments or []
    context = context or {}

    try:
        # SMTP settings from site_config.json
        config = frappe.get_conf()
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port")
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")

        # Render email template
        if email_template_name:
            template = frappe.get_doc("Email Template", email_template_name)
            html_message = frappe.render_template(template.response_html, context)
            subject = frappe.render_template(template.subject, context) or subject
        else:
            html_message = message

        # ✅ Create MIME message
        msg = MIMEMultipart()
        msg["From"] = str(From)                    # ensure string
        msg["To"] = ", ".join([str(x) for x in to])  # join list properly
        if cc:
            msg["Cc"] = ", ".join([str(x) for x in cc])
        msg["Subject"] = str(subject)              # ensure subject is string

        # Attach HTML body
        msg.attach(MIMEText(html_message, "html"))

        # Attachments
        for attachment in attachments:
            file_url = attachment.get("file_url")
            file_name = attachment.get("file_name")
            file_data = get_file(file_url)
            file_content = file_data[1]

            part = MIMEApplication(file_content, Name=file_name)
            part["Content-Disposition"] = f'attachment; filename="{file_name}"'
            msg.attach(part)

        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        recipients = to + cc + bcc   # BCC not added in header but sent here
        server.sendmail(From, recipients, msg.as_string())
        server.quit()

        print("")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


# ─── Academy Booking Email Helpers ───────────────────────────────────

BOOKING_EMAIL_SENDER = "noreply@merillife.com"
BOOKING_EMAIL_TEMPLATE = "Academy Booking Notification"


def get_booking_email_context(doc, message, subject, recipient_name, remark=None):
    """
    Build the full Jinja context dict for the Academy Booking Notification template.
    Accepts an optional 'remark' (approver comment) to include in the email body.
    """
    return {
        "subject": subject,
        "message": message,
        "recipient_name": recipient_name,
        "remark": remark or "",

        "booking_id": doc.name,
        "event_type": getattr(doc, "event_type", ""),
        "academy": getattr(doc, "academy", ""),
        "merilian_code": getattr(doc, "merilian_code", ""),
        "full_name": getattr(doc, "full_name", ""),
        "trainer_name": getattr(doc, "trainer_name", ""),
        "email": getattr(doc, "email", ""),
        "contact_number": getattr(doc, "contact_number", ""),
        "vertical": getattr(doc, "vertical", ""),
        "department": getattr(doc, "department", ""),
        "event_title": getattr(doc, "event_title", ""),
        "description": getattr(doc, "description", ""),
        "event_start_date": str(getattr(doc, "event_start_date", "")),
        "event_end_date": str(getattr(doc, "event_end_date", "")),
        "no_of_participants": getattr(doc, "no_of_participants", ""),
        "no_of_participants_international": getattr(doc, "no_of_participants_international", ""),
        "it_requirement": getattr(doc, "it_requirement", ""),
        "comment": getattr(doc, "comment", ""),
        "mats_event": getattr(doc, "mats_event", ""),
        "mats_request_number": getattr(doc, "mats_request_number", ""),
        "cancel_comment": getattr(doc, "cancel_comment", "") if getattr(doc, "cancel_request", 0) else None,

        "doc_link": f"{frappe.get_conf().get('frontend_url', frappe.utils.get_url())}"
    }


def _send_booking_email(to, subject, message, doc, recipient_name, remark=None):
    """
    Fires an email using the Academy Booking Notification template.
    Logs success/failure to Frappe Error Log for traceability.
    """
    try:
        context = get_booking_email_context(doc, message, subject, recipient_name, remark=remark)
        result = send_mail(
            From=BOOKING_EMAIL_SENDER,
            to=to if isinstance(to, list) else [to],
            subject=subject,
            email_template_name=BOOKING_EMAIL_TEMPLATE,
            context=context
        )
        if result:
            frappe.logger().info(f"✅ Email sent to {to} | Subject: {subject} | Booking: {doc.name}")
        else:
            frappe.log_error(
                title="Booking Email Send Failed",
                message=f"send_mail returned False.\nTo: {to}\nSubject: {subject}\nBooking: {doc.name}"
            )
    except Exception as e:
        frappe.log_error(
            title="Booking Email Exception",
            message=f"To: {to}\nSubject: {subject}\nBooking: {doc.name}\nError: {str(e)}"
        )
