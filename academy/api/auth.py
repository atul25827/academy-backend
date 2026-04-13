import frappe
import re
import random
import hashlib
from frappe import _
from frappe.utils import cint, now_datetime, add_to_date
from frappe.utils.password import check_password, update_password
from frappe.auth import LoginManager
from academy.api.utils import send_mail
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESET_TOKEN_EXPIRY_HOURS = 24
MIN_PASSWORD_LENGTH = 8

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_email(email: str) -> bool:
    """Return True if email is syntactically valid."""
    pattern = r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]+$"
    return bool(re.match(pattern, email))


def _validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    Rules:
      - Minimum 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\[\]\\/'`;~+=]", password):
        return False, "Password must contain at least one special character."
    return True, "OK"


def _json_response(data: dict, status: int = 200):
    """Attach HTTP status code to response and return data dict."""
    frappe.local.response["http_status_code"] = status
    return data


def _error(message: str, status: int = 400, log_message: str = None):
    """
    Return a standardised error response without raising an exception.
    Logs to Frappe Error Log when log_message is provided.
    """
    if log_message:
        frappe.log_error(title="Auth API Error", message=log_message)
    frappe.local.response["http_status_code"] = status
    return {
        "success_key": 0,
        "message": message,
    }


# ===========================================================================
# 1. LOGIN
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    """
    Authenticate user and return session details.

    Endpoint: POST /api/method/academy.api.auth.login
    """
    try:
        if not usr or not pwd:
            return _error("Email and password are required.", 400)

        login_manager = LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()

    except frappe.AuthenticationError:
        frappe.clear_messages()
        return _error("Authentication Failed. Invalid Username or Password.", 401)
    except Exception as e:
        return _error("An unexpected error occurred during login.", 500,
                      log_message=f"Login error for {usr}: {str(e)}")

    user = frappe.get_doc("User", frappe.session.user)

    excluded_roles = ["All", "Guest", "Desk User"]
    user_roles = [r.role for r in user.roles if r.role not in excluded_roles]
    role_profile = user.role_profile_name

    # Set cookies
    frappe.local.cookie_manager.set_cookie("user_id", user.name)
    frappe.local.cookie_manager.set_cookie("full_name", user.full_name)
    frappe.local.cookie_manager.set_cookie("sid", frappe.session.sid)

    # Remove default keys added by post_login
    for key in ("home_page", "full_name"):
        frappe.local.response.pop(key, None)

    frappe.local.response["http_status_code"] = 200
    return {
        "success_key": 1,
        "message": "Logged In Successfully",
        "sid": frappe.session.sid,
        "user_id": user.name,
        "role": user_roles,
        "role_profile": role_profile,
        "full_name": user.full_name,
    }


# ===========================================================================
# 2. GET LOGGED USER
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def get_logged_user():
    """
    Return details of the currently authenticated user.

    Endpoint: GET /api/method/academy.api.auth.get_logged_user
    """
    if frappe.session.user == "Guest":
        return _error("Session expired or invalid. Please login again.", 401)

    try:
        user = frappe.get_doc("User", frappe.session.user)
        excluded_roles = ["All", "Guest", "Desk User"]
        roles = [r for r in frappe.get_roles(user.name) if r not in excluded_roles]
        role_profile = user.role_profile_name

        employee_code = None
        emp = frappe.db.get_value(
            "Master Employee",
            {"linked_user": user.name},
            "employee_code"
        )
        if emp:
            employee_code = emp

        frappe.local.response["http_status_code"] = 200
        return {
            "success_key": 1,
            "user_id": user.name,
            "full_name": user.full_name,
            "email": user.email,
            "role": roles,
            "role_profile": role_profile,
            "employee_code": employee_code,
            "image": user.user_image,
        }

    except Exception as e:
        return _error("Failed to fetch user details.", 500,
                      log_message=f"get_logged_user error: {str(e)}")


# ===========================================================================
# 2.5 OTP VERIFICATION
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def send_signup_otp(email: str, employee_code: str):
    """
    Send OTP for user signup registration.
    """
    try:
        if not email or not employee_code:
            return _error("Email and Employee Code are required", 400)
            
        email = email.strip().lower()
        if not _validate_email(email):
            return _error("Invalid email address format.", 400)
            
        if frappe.db.exists("User", email):
            return _error("User already registered.", 409)

        employee = frappe.db.get_value(
            "Master Employee",
            {"employee_code": employee_code},
            ["name", "email"],
            as_dict=True
        )

        if not employee:
            return _error("Employee not found or email mismatch.", 400)
            
        emp_emails = {(employee.email or "").strip().lower()}
        emp_emails.discard("")
        if email not in emp_emails:
            return _error("Employee not found or email mismatch.", 400)

        # Check rate limiting: max 3 attempts per 5 mins
        five_mins_ago = add_to_date(now_datetime(), minutes=-5)
        recent_attempts = frappe.db.count("User OTP Verification", filters={
            "email": email,
            "creation": (">", five_mins_ago)
        })
        
        if recent_attempts >= 3:
            return _error("Maximum OTP attempts reached. Please try again after 5 minutes.", 429)

        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        
        # Valid for 1 min in DB as per requirement, but template says 30 sec
        expiry_time = add_to_date(now_datetime(), seconds=60)
        
        # Delete old OTPs for this email to prevent clutter
        old_otps = frappe.get_all("User OTP Verification", filters={"email": email}, pluck="name")
        for old_otp in old_otps:
            frappe.delete_doc("User OTP Verification", old_otp, ignore_permissions=True)
            
        # Create new OTP record
        doc = frappe.get_doc({
            "doctype": "User OTP Verification",
            "email": email,
            "employee_code": employee_code,
            "otp_hash": otp_hash,
            "expiry_time": expiry_time,
            "is_verified": 0,
            "attempt_count": 0
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Send Email
        message = f"Your OTP is {otp}. Valid for 30 seconds."
        email_sent = send_mail(
            From="noreply@merillife.com",
            to=[email],
            subject="Your Signup OTP",
            context={},
            email_template_name="",
            message=message
        )
        
        if not email_sent:
            return _error("Failed to send OTP email.", 500)
            
        frappe.local.response["http_status_code"] = 200
        return {"success_key": 1, "message": "OTP sent successfully."}

    except Exception as e:
        frappe.db.rollback()
        return _error("An unexpected error occurred.", 500, log_message=f"send_signup_otp error: {str(e)}")


@frappe.whitelist(allow_guest=True)
def verify_signup_otp(email: str, employee_code: str, otp: str):
    """
    Verify the OTP for signup registration.
    """
    try:
        if not email or not employee_code or not otp:
            return _error("Email, Employee Code and OTP are required.", 400)
            
        email = email.strip().lower()
        
        otp_records = frappe.get_all(
            "User OTP Verification",
            filters={"email": email, "employee_code": employee_code},
            fields=["name", "otp_hash", "expiry_time", "is_verified", "attempt_count"],
            order_by="creation desc",
            limit=1
        )
        
        if not otp_records:
            return _error("No OTP found. Please request a new OTP.", 400)
            
        record = otp_records[0]
        
        if record.is_verified:
            return _error("OTP is already verified.", 400)
            
        if now_datetime() > record.expiry_time:
            return _error("OTP has expired. Please request a new one.", 400)
            
        otp_hash = hashlib.sha256(str(otp).encode()).hexdigest()
        
        if record.otp_hash != otp_hash:
            new_count = record.attempt_count + 1
            frappe.db.set_value("User OTP Verification", record.name, "attempt_count", new_count, update_modified=False)
            frappe.db.commit()
            return _error("Invalid OTP.", 400)
            
        # Match success
        frappe.db.set_value("User OTP Verification", record.name, "is_verified", 1, update_modified=False)
        frappe.db.commit()
        
        frappe.local.response["http_status_code"] = 200
        return {"success_key": 1, "message": "OTP verified successfully."}
        
    except Exception as e:
        frappe.db.rollback()
        return _error("An unexpected error occurred.", 500, log_message=f"verify_signup_otp error: {str(e)}")


# ===========================================================================
# 3. REGISTER USER
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def register_user(employee_code: str, email: str, password: str):
    """
    Register a new user account linked to a Master Employee record.

    Endpoint: POST /api/method/academy.api.auth.register_user

    Request body:
        {
            "employee_code": "EMP001",
            "email": "user@example.com",
            "password": "SecurePass@123"
        }

    Success (201):
        {"success_key": 1, "message": "User registered successfully"}

    Errors:
        400 – validation / already registered / employee not found
        500 – unexpected server error
    """
    try:
        # ── 1. Input validation ──────────────────────────────────────────
        if not employee_code or not email or not password:
            return _error("employee_code, email, and password are required.", 400)

        email = email.strip().lower()

        if not _validate_email(email):
            return _error("Invalid email address format.", 400)

        is_strong, reason = _validate_password_strength(password)
        if not is_strong:
            return _error(reason, 400)

        # ── 1.5 Verify OTP has been verified ────────────────────────────
        otp_records = frappe.get_all(
            "User OTP Verification",
            filters={"email": email, "employee_code": employee_code, "is_verified": 1},
            fields=["name"],
            order_by="creation desc",
            limit=1
        )
        if not otp_records:
            return _error("Please verify OTP before registration.", 400)
        otp_name = otp_records[0].name

        # ── 2. Check if User already exists ─────────────────────────────
        if frappe.db.exists("User", email):
            return _error("User already registered.", 409)

        # ── 3. Verify Employee Master ────────────────────────────────────
        employee = frappe.db.get_value(
            "Master Employee",
            {
                "employee_code": employee_code,
            },
            ["name", "employee_name", "email"],
            as_dict=True,
        )

        if not employee:
            return _error("Employee not found or email mismatch.", 400)

        emp_emails = {
            (employee.email or "").strip().lower(),
        }
        emp_emails.discard("")

        if email not in emp_emails:
            return _error("Employee not found or email mismatch.", 400)

        # ── 4. Create User ───────────────────────────────────────────────
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": employee.employee_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": password,
            "role_profile_name": "Academy User Club User",
        })
        user.insert(ignore_permissions=True)
        frappe.db.commit()

        # ── 5. Link employee to user ─────────────────────────────────────
        frappe.db.set_value(
            "Master Employee",
            employee.name,
            "linked_user",
            email,
            update_modified=False,
        )
        frappe.db.commit()

        # ── 6. Cleanup Verification Record ───────────────────────────────
        frappe.delete_doc("User OTP Verification", otp_name, ignore_permissions=True)
        frappe.db.commit()

        frappe.logger().info(
            f"register_user: New user '{email}' registered "
            f"and linked to employee '{employee_code}'."
        )

        frappe.local.response["http_status_code"] = 201
        return {"success_key": 1, "message": "User registered successfully"}

    except frappe.DuplicateEntryError:
        frappe.db.rollback()
        return _error("User already registered.", 409)

    except Exception as e:
        frappe.db.rollback()
        return _error("An unexpected error occurred during registration.", 500,
                      log_message=f"register_user error for {email}: {str(e)}")


# ===========================================================================
# 4. FORGOT PASSWORD
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def forgot_password(email: str):
    """
    Generate a password-reset token and send it to the user's email.

    Endpoint: POST /api/method/academy.api.auth.forgot_password

    Request body:
        {"email": "user@example.com"}

    Success (200):
        {"success_key": 1, "message": "Reset link sent to email"}

    Note:  We return a generic success even when the email does not exist
           to prevent user-enumeration attacks.
    """
    GENERIC_SUCCESS = {
        "success_key": 1,
        "message": "If an account exists for this email, a reset link has been sent.",
    }

    try:
        if not email:
            return _error("Email is required.", 400)

        email = email.strip().lower()

        if not _validate_email(email):
            return _error("Invalid email address format.", 400)

        # ── Prevent user enumeration – always return success ─────────────
        if not frappe.db.exists("User", email):
            frappe.logger().info(f"forgot_password: Ignored request for unregistered email '{email}'.")
            frappe.local.response["http_status_code"] = 200
            return GENERIC_SUCCESS

        # ── Generate token ───────────────────────────────────────────────
        token = frappe.generate_hash(length=64)
        expiry = add_to_date(now_datetime(), hours=RESET_TOKEN_EXPIRY_HOURS)

        frappe.db.set_value(
            "User",
            email,
            {
                "reset_password_key": token,
                "last_reset_password_key_generated_on": expiry,
            },
            update_modified=False,
        )
        frappe.db.commit()

        # ── Build reset link ─────────────────────────────────────────────
        frontend_url = frappe.get_conf().get("frontend_url", frappe.utils.get_url())
        reset_link = f"{frontend_url}/reset?token={token}"

        # ── Send email ───────────────────────────────────────────────────
        email_sent = send_mail(
            From="noreply@merillife.com",
            to=[email],
            subject="Reset Your Password",
            context={"reset_link": reset_link},
            email_template_name="", # We will pass raw message below if template is not strictly required.
            message=_get_reset_email_body(reset_link)
        )

        if not email_sent:
            raise Exception("utils.send_mail returned False indicating SMTP failure.")

        frappe.logger().info(f"forgot_password: Reset token generated and email sent for '{email}'.")

        frappe.local.response["http_status_code"] = 200
        return GENERIC_SUCCESS

    except Exception as e:
        frappe.db.rollback()
        return _error(f"Failed to send email. Check error logs. Error: {str(e)}", 500,
                      log_message=f"forgot_password error for {email}: {str(e)}")


def _get_reset_email_body(reset_link: str) -> str:
    """Return the HTML body for the password-reset email."""
    return f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
        <h2>Password Reset Request</h2>
        <p>You requested a password reset. Click the button below to set a new password.</p>
        <p style="margin: 24px 0;">
            <a href="{reset_link}"
               style="background:#4F46E5;color:#fff;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold;">
                Reset Password
            </a>
        </p>
        <p style="color:#888;font-size:13px;">
            This link will expire in {RESET_TOKEN_EXPIRY_HOURS} hour(s).<br>
            If you did not request this, please ignore this email.
        </p>
    </div>
    """


# ===========================================================================
# 5. VERIFY RESET TOKEN  (NEW – decode token, check expiry, return user data)
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def verify_reset_token(token: str):
    """
    Verify a password-reset token and return the associated user data.

    Endpoint: GET /api/method/academy.api.auth.verify_reset_token?token=<token>

    Success (200):
        {
            "success_key": 1,
            "valid": true,
            "email": "user@example.com",
            "full_name": "John Doe",
            "message": "Token is valid"
        }

    Errors:
        400 – token missing / invalid / expired
    """
    try:
        if not token:
            return _error("Token is required.", 400)

        # ── Lookup user by token ─────────────────────────────────────────
        user_name = frappe.db.get_value(
            "User",
            {"reset_password_key": token},
            "name",
        )

        if not user_name:
            return _error("Invalid or expired reset token.", 400)

        # ── Check expiry ─────────────────────────────────────────────────
        expiry = frappe.db.get_value(
            "User",
            user_name,
            "last_reset_password_key_generated_on",
        )

        if not expiry or now_datetime() > expiry:
            return _error("Reset token has expired. Please request a new one.", 400)

        user = frappe.db.get_value(
            "User",
            user_name,
            ["name", "full_name", "first_name"],
            as_dict=True,
        )

        frappe.local.response["http_status_code"] = 200
        return {
            "success_key": 1,
            "valid": True,
            "email": user.name,
            "full_name": user.full_name,
            "first_name": user.first_name,
            "message": "Token is valid",
        }

    except Exception as e:
        return _error("An unexpected error occurred.", 500,
                      log_message=f"verify_reset_token error: {str(e)}")


# ===========================================================================
# 6. RESET PASSWORD
# ===========================================================================

@frappe.whitelist(allow_guest=True)
def reset_password(token: str, new_password: str):
    """
    Reset a user's password using a valid reset token.

    Endpoint: POST /api/method/academy.api.auth.reset_password

    Request body:
        {
            "token": "secure_token_here",
            "new_password": "NewSecurePass@123"
        }

    Success (200):
        {"success_key": 1, "message": "Password updated successfully"}

    Errors:
        400 – token invalid / expired / weak password
        500 – unexpected server error
    """
    try:
        if not token or not new_password:
            return _error("Token and new_password are required.", 400)

        # ── Validate password strength ───────────────────────────────────
        is_strong, reason = _validate_password_strength(new_password)
        if not is_strong:
            return _error(reason, 400)

        # ── Find user by token ───────────────────────────────────────────
        user_name = frappe.db.get_value(
            "User",
            {"reset_password_key": token},
            "name",
        )

        if not user_name:
            return _error("Invalid or expired reset token.", 400)

        # ── Validate expiry ──────────────────────────────────────────────
        expiry = frappe.db.get_value(
            "User",
            user_name,
            "last_reset_password_key_generated_on",
        )

        if not expiry or now_datetime() > expiry:
            return _error("Reset token has expired. Please request a new one.", 400)

        # ── Update password ──────────────────────────────────────────────
        update_password(user_name, new_password)

        # ── Clear reset token fields ─────────────────────────────────────
        frappe.db.set_value(
            "User",
            user_name,
            {
                "reset_password_key": "",
                "last_reset_password_key_generated_on": None,
            },
            update_modified=False,
        )
        frappe.db.commit()

        frappe.logger().info(f"reset_password: Password updated successfully for '{user_name}'.")

        frappe.local.response["http_status_code"] = 200
        return {"success_key": 1, "message": "Password updated successfully"}

    except Exception as e:
        frappe.db.rollback()
        return _error("An unexpected error occurred. Please try again.", 500,
                      log_message=f"reset_password error: {str(e)}")


# ===========================================================================
# 7. CLEANUP EXPIRED OTPS
# ===========================================================================

def cleanup_expired_otps():
    """
    Scheduled job to auto-delete expired OTPs.
    Call via hooks.py on daily or hourly basis.
    """
    try:
        expired_otps = frappe.get_all(
            "User OTP Verification",
            filters={"expiry_time": ("<", now_datetime())},
            pluck="name"
        )
        for name in expired_otps:
            frappe.delete_doc("User OTP Verification", name, ignore_permissions=True)
        if expired_otps:
            frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(title="OTP Cleanup Error", message=str(e))
