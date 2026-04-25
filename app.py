import os
from flask import Flask, redirect, url_for, session, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ums-agile-phase1-2026")

# Import and register the Auth Blueprint
from core.auth import auth_bp, login_required

app.register_blueprint(auth_bp)


# Root route redirects based on session status
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth.login"))


# Temporary Dashboard to test successful logins
@app.route("/dashboard")
@login_required
def dashboard():
    html = """
    {% extends "base.html" %}
    {% block content %}
    <div class="bg-white p-8 rounded-xl shadow-lg border border-slate-200">
        <h1 class="text-2xl font-bold text-green-600 mb-2">Login Successful!</h1>
        <p>You are logged in as: <strong>{{ session['username'] }}</strong></p>
        <p>Your role is: <strong>{{ session['role'] }}</strong></p>
    </div>
    {% endblock %}
    """
    return render_template_string(html)


if __name__ == "__main__":
    app.run(port=5050, debug=True)
