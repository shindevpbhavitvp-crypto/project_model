import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    """Application configuration for College AI Assistant."""
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", 
        "academic-prototype-college-assistant-secret-key-2026"
    )
    DATABASE_PATH = BASE_DIR / "database" / "college.db"
    DOCUMENTS_FOLDER = BASE_DIR / "documents"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
    
    # Session security settings suitable for local prototype
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # False for local HTTP development

    # Default demo credentials documentation
    DEMO_ACCOUNTS = {
        "students": [
            {"student_id": "STU001", "name": "Aarav Sharma", "class": "B.Tech CSE", "semester": 6, "password": "student123"},
            {"student_id": "STU002", "name": "Priya Patel", "class": "B.Tech IT", "semester": 4, "password": "student123"},
            {"student_id": "STU003", "name": "Rohan Verma", "class": "B.Tech CSE", "semester": 6, "password": "student123"}
        ],
        "admin": {
            "username": "admin",
            "name": "Prof. S. R. Deshmukh (Dean Academics)",
            "password": "admin123"
        }
    }
