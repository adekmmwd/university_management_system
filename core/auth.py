from functools import wraps
import os
import re
import json
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, session, redirect, url_for, flash, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from core.database import supabase

auth_bp = Blueprint("auth", __name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _supabase_function_url(function_name: str) -> str:
    base = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("SUPABASE_URL is not configured")
    return f"{base}/functions/v1/{function_name}"


def _invoke_send_invitation_email(*, email: str, name: str, token: str) -> None:
    invite_secret = os.environ.get("INVITE_FUNCTION_SECRET") or ""
    if not invite_secret:
        raise RuntimeError("INVITE_FUNCTION_SECRET is not configured")

    payload = json.dumps({"email": email, "name": name, "token": token}).encode("utf-8")
    req = urllib.request.Request(
        _supabase_function_url("send-invitation"),
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Invite-Secret": invite_secret,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if getattr(resp, "status", 200) != 200:
                body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Invitation email failed: HTTP {resp.status}: {body}")
    except urllib.error.HTTPError as e:
        body = (e.read() or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"Invitation email failed: HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Invitation email failed: {e.reason}")


def _sanitize_username(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^a-z0-9@._+-]", "", value)
    return value or "user"


def _find_unique_username(preferred: str) -> str:
    base = _sanitize_username(preferred)
    candidate = base
    for i in range(0, 50):
        exists = (
            supabase.table("users").select("id").eq("username", candidate).limit(1).execute()
        )
        if not getattr(exists, "data", None):
            return candidate
        candidate = f"{base}{i + 1}"
    return f"{base}-{uuid.uuid4().hex[:6]}"


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return wrapped


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


def admin_or_head_staff_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") not in {"admin", "head_staff"}:
            flash("Access denied. Admin or Head Staff privileges required.", "danger")
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


@auth_bp.route("/invitations/send", methods=["POST"])
@admin_required
def send_invitation():
    target_type = (request.form.get("target_type") or "").strip().lower()
    target_id_raw = (request.form.get("target_id") or "").strip()
    next_url = request.form.get("next") or request.referrer or url_for("staff.directory")

    if target_type not in {"student", "staff"}:
        flash("Invalid invitation target.", "danger")
        return redirect(next_url)

    try:
        target_id = int(target_id_raw)
    except ValueError:
        flash("Invalid invitation target.", "danger")
        return redirect(next_url)

    if target_type == "student":
        resp = (
            supabase.table("students")
            .select("id,name,email,user_id")
            .eq("id", target_id)
            .limit(1)
            .execute()
        )
    else:
        resp = (
            supabase.table("staff")
            .select("id,name,email,user_id")
            .eq("id", target_id)
            .limit(1)
            .execute()
        )

    record = resp.data[0] if getattr(resp, "data", None) else None
    if not record:
        flash("User record not found.", "danger")
        return redirect(next_url)

    email = (record.get("email") or "").strip().lower()
    name = (record.get("name") or "").strip()

    if not email:
        flash("This record has no email address on file.", "danger")
        return redirect(next_url)

    now = _utc_now()
    existing = (
        supabase.table("invitations")
        .select("token")
        .eq("email", email)
        .eq("status", "Pending")
        .gt("expires_at", now.isoformat())
        .limit(1)
        .execute()
    )
    if getattr(existing, "data", None):
        flash("An active invitation is already pending for this email.", "warning")
        return redirect(next_url)

    token = str(uuid.uuid4())
    expires_at = now + timedelta(hours=48)

    insert_resp = (
        supabase.table("invitations")
        .insert(
            {
                "email": email,
                "token": token,
                "expires_at": expires_at.isoformat(),
                "status": "Pending",
            }
        )
        .execute()
    )

    if not getattr(insert_resp, "data", None):
        flash("Failed to create invitation. Please try again.", "danger")
        return redirect(next_url)

    try:
        _invoke_send_invitation_email(email=email, name=name, token=token)
    except Exception as e:
        supabase.table("invitations").delete().eq("token", token).execute()
        flash(f"Failed to send invitation email: {e}", "danger")
        return redirect(next_url)

    flash("Success! Invitation email queued.", "success")
    return redirect(next_url)


def course_coordinator_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "course_coordinator":
            flash(
                "Access denied. Course Coordinator privileges required.",
                "danger",
            )
            return redirect(url_for("staff.profile"))
        return f(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("staff.profile"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")

        response = (
            supabase.table("users").select("*").eq("username", username).execute()
        )

        if response.data and check_password_hash(
            response.data[0]["password_hash"], pwd
        ):
            user = response.data[0]
            session.update(
                {
                    "user_id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                }
            )
            flash(f"Welcome back, {user['full_name']}!", "success")

            return redirect(url_for("staff.profile"))

        flash("Invalid username or password.", "danger")

    return render_template("auth/login.html")


# Signup removed — admin registers users via student/staff management pages


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/set-password", methods=["GET", "POST"])
def set_password():
    token = (request.values.get("token") or "").strip()
    if not token:
        return render_template("auth/set_password.html", valid=False, reason="Missing token.")

    now = _utc_now()
    inv_resp = (
        supabase.table("invitations")
        .select("email,token,expires_at,status")
        .eq("token", token)
        .limit(1)
        .execute()
    )
    invitation = inv_resp.data[0] if getattr(inv_resp, "data", None) else None
    if not invitation:
        return render_template(
            "auth/set_password.html",
            valid=False,
            reason="This invitation link is invalid.",
        )

    status = (invitation.get("status") or "").strip()
    expires_at_raw = invitation.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
    except Exception:
        expires_at = now - timedelta(seconds=1)

    if status.lower() != "pending":
        return render_template(
            "auth/set_password.html",
            valid=False,
            reason="This invitation has already been used.",
        )
    if expires_at <= now:
        return render_template(
            "auth/set_password.html",
            valid=False,
            reason="This invitation has expired.",
        )

    email = (invitation.get("email") or "").strip().lower()

    student = (
        supabase.table("students")
        .select("id,user_id,name,email")
        .eq("email", email)
        .limit(1)
        .execute()
        .data
    )
    student = student[0] if student else None

    staff = (
        supabase.table("staff")
        .select("id,user_id,name,email")
        .eq("email", email)
        .limit(1)
        .execute()
        .data
    )
    staff = staff[0] if staff else None

    profile = student or staff
    role = "student" if student else "staff" if staff else "student"
    display_name = (profile or {}).get("name") or email

    if not profile:
        return render_template(
            "auth/set_password.html",
            valid=False,
            reason="No matching user record was found for this invitation.",
        )

    if request.method == "GET":
        return render_template(
            "auth/set_password.html",
            valid=True,
            token=token,
            email=email,
            name=display_name,
        )

    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""

    if len(password) < 8:
        return render_template(
            "auth/set_password.html",
            valid=True,
            token=token,
            email=email,
            name=display_name,
            error="Password must be at least 8 characters.",
        )
    if password != confirm:
        return render_template(
            "auth/set_password.html",
            valid=True,
            token=token,
            email=email,
            name=display_name,
            error="Passwords do not match.",
        )

    hashed = generate_password_hash(password)

    # If a linked user already exists, update password.
    linked_user_id = (profile or {}).get("user_id")
    if linked_user_id:
        supabase.table("users").update({"password_hash": hashed}).eq("id", linked_user_id).execute()
    else:
        # Use email as the username so the user can log in with what they already know.
        username = _sanitize_username(email)
        existing_user = (
            supabase.table("users").select("id").eq("username", username).limit(1).execute()
        )
        if getattr(existing_user, "data", None):
            new_user_id = existing_user.data[0]["id"]
            supabase.table("users").update({"password_hash": hashed}).eq("id", new_user_id).execute()
        else:
            user_resp = (
                supabase.table("users")
                .insert(
                    {
                        "username": username,
                        "password_hash": hashed,
                        "role": role,
                        "full_name": display_name,
                    }
                )
                .execute()
            )
            if not getattr(user_resp, "data", None):
                return render_template(
                    "auth/set_password.html",
                    valid=True,
                    token=token,
                    email=email,
                    name=display_name,
                    error="Failed to create your account. Please contact an administrator.",
                )

            new_user_id = user_resp.data[0]["id"]

        if student:
            supabase.table("students").update({"user_id": new_user_id}).eq("id", student["id"]).execute()
        elif staff:
            supabase.table("staff").update({"user_id": new_user_id}).eq("id", staff["id"]).execute()
        else:
            return render_template(
                "auth/set_password.html",
                valid=True,
                token=token,
                email=email,
                name=display_name,
                error="No matching user record was found for this invitation.",
            )

    supabase.table("invitations").update({"status": "Accepted"}).eq("token", token).execute()

    flash("Password set! You can now log in using your email address.", "success")
    return redirect(url_for("auth.login"))
