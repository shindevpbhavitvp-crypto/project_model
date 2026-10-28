import os
import sys
from pathlib import Path
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash
)

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import Config
from database.db import init_db, get_db
from services.auth_service import authenticate_student, authenticate_admin, get_student_by_id
from services.attendance_service import get_student_attendance
from services.timetable_service import get_timetable_for_student
from services.document_service import (
    list_all_documents, save_and_index_document, delete_document
)
from services.chatbot_service import process_chat_message

app = Flask(__name__)
app.config.from_object(Config)

# Decorators for route protection
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access the Smart College Assistant.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("role") != "admin":
            flash("Administrator credentials are required to view that page.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Context processor for templates
@app.context_processor
def inject_user_context():
    return {
        "current_user": {
            "is_authenticated": "user_id" in session,
            "id": session.get("user_id"),
            "name": session.get("name"),
            "role": session.get("role"),
            "class_name": session.get("class_name"),
            "semester": session.get("semester"),
            "email": session.get("email")
        }
    }

# -----------------------------------------------------------------------------
# Authentication Routes
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("chat_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_type = request.form.get("login_type", "student")
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "").strip()
        
        if not identifier or not password:
            flash("Please enter both ID/Username and password.", "danger")
            return render_template("login.html", demo_accounts=Config.DEMO_ACCOUNTS)
            
        if login_type == "admin":
            admin_data = authenticate_admin(identifier, password)
            if admin_data:
                session.clear()
                session["user_id"] = admin_data["username"]
                session["name"] = admin_data["name"]
                session["role"] = "admin"
                flash(f"Welcome back, {admin_data['name']}!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid administrator username or password.", "danger")
        else:
            student_data = authenticate_student(identifier, password)
            if student_data:
                session.clear()
                session["user_id"] = student_data["student_id"]
                session["name"] = student_data["name"]
                session["email"] = student_data["email"]
                session["class_name"] = student_data["class_name"]
                session["semester"] = student_data["semester"]
                session["role"] = "student"
                flash(f"Welcome back, {student_data['name']}!", "success")
                return redirect(url_for("chat_dashboard"))
            else:
                flash("Invalid Student ID or password.", "danger")
                
    return render_template("login.html", demo_accounts=Config.DEMO_ACCOUNTS)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have successfully signed out.", "info")
    return redirect(url_for("login"))

# -----------------------------------------------------------------------------
# Student Assistant & Chat Routes
# -----------------------------------------------------------------------------

@app.route("/chat")
@login_required
def chat_dashboard():
    student_id = session.get("user_id")
    role = session.get("role")
    
    attendance_data = None
    timetable_data = None
    if role == "student":
        attendance_data = get_student_attendance(student_id)
        timetable_data = get_timetable_for_student(student_id)
        
    documents = list_all_documents()
    
    return render_template(
        "chat.html",
        attendance=attendance_data,
        timetable=timetable_data,
        documents=documents
    )

@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    
    if not message:
        return jsonify({
            "success": False,
            "error": "Message content cannot be blank."
        }), 400
        
    user_session = {
        "user_id": session.get("user_id"),
        "name": session.get("name"),
        "role": session.get("role"),
        "class_name": session.get("class_name"),
        "semester": session.get("semester")
    }
    
    response = process_chat_message(message, user_session)
    return jsonify({
        "success": True,
        "answer": response.get("answer"),
        "source": response.get("source"),
        "intent": response.get("intent")
    })

@app.route("/api/attendance", methods=["GET"])
@login_required
def api_attendance():
    if session.get("role") != "student":
        return jsonify({"error": "Available only for students"}), 403
    data = get_student_attendance(session.get("user_id"))
    return jsonify(data)

@app.route("/api/timetable", methods=["GET"])
@login_required
def api_timetable():
    if session.get("role") != "student":
        return jsonify({"error": "Available only for students"}), 403
    day = request.args.get("day")
    data = get_timetable_for_student(session.get("user_id"), day_filter=day)
    return jsonify(data)

# -----------------------------------------------------------------------------
# Administrator Portal Routes
# -----------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    documents = list_all_documents()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # All students
        cursor.execute("SELECT student_id, name, email, class_name, semester FROM students ORDER BY student_id ASC")
        students = [dict(r) for r in cursor.fetchall()]
        
        # Calculate attendance summaries for each student
        student_summaries = []
        defaulters = []
        for s in students:
            att = get_student_attendance(s["student_id"])
            s_data = {
                **s,
                "overall_percentage": att.get("overall_percentage", 0.0),
                "attended": att.get("overall_attended", 0),
                "total": att.get("overall_total", 0),
                "is_low": att.get("overall_is_low", False),
                "low_subjects": att.get("low_attendance_subjects", [])
            }
            student_summaries.append(s_data)
            if s_data["is_low"] or len(s_data["low_subjects"]) > 0:
                defaulters.append(s_data)
                
        # Total chunks count
        cursor.execute("SELECT COUNT(*) FROM document_chunks")
        total_chunks = cursor.fetchone()[0]
        
        # Timetable count
        cursor.execute("SELECT COUNT(*) FROM timetable")
        total_classes = cursor.fetchone()[0]
        
        # Timetable sample list
        cursor.execute("SELECT DISTINCT class_name, semester FROM timetable ORDER BY class_name, semester")
        classes_available = [dict(r) for r in cursor.fetchall()]
        
    stats = {
        "total_students": len(students),
        "total_documents": len(documents),
        "total_chunks": total_chunks,
        "defaulters_count": len(defaulters),
        "total_classes": total_classes
    }
    
    return render_template(
        "admin.html",
        documents=documents,
        students=student_summaries,
        defaulters=defaulters,
        classes_available=classes_available,
        stats=stats
    )

@app.route("/admin/upload", methods=["POST"])
@admin_required
def admin_upload_document():
    if "document" not in request.files:
        flash("No file was uploaded in the form request.", "danger")
        return redirect(url_for("admin_dashboard"))
        
    file = request.files["document"]
    if file.filename == "":
        flash("No file was selected for upload.", "warning")
        return redirect(url_for("admin_dashboard"))
        
    success, msg, doc_meta = save_and_index_document(file)
    if success:
        flash(f"Document indexed successfully: {msg}", "success")
    else:
        flash(f"Upload failed: {msg}", "danger")
        
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_doc/<int:doc_id>", methods=["POST"])
@admin_required
def admin_delete_document(doc_id: int):
    success, msg = delete_document(doc_id)
    if success:
        flash(msg, "info")
    else:
        flash(msg, "danger")
    return redirect(url_for("admin_dashboard"))

# -----------------------------------------------------------------------------
# Application Initializer
# -----------------------------------------------------------------------------

# Ensure database is initialized when the module loads
init_db()

if __name__ == "__main__":
    print(f"Starting Smart College Assistant on http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=True)
