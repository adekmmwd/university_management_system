import os
from flask import Flask, redirect, url_for, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ums-agile-phase1-2026")

# 1. Import your 3 Blueprints
from core.auth import auth_bp
from epic3_staff.routes import staff_bp
from epic4_community.routes import community_bp

# 2. Register them
app.register_blueprint(auth_bp)
app.register_blueprint(staff_bp)
app.register_blueprint(community_bp)


# 3. Root redirect
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("staff.profile"))
    return redirect(url_for("auth.login"))


if __name__ == "__main__":
    app.run(port=5050, debug=True)
