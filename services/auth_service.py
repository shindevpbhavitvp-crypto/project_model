from werkzeug.security import check_password_hash
from database.db import get_db

def authenticate_student(student_id: str, password: str):
    """
    Authenticate a student by student_id and password.
    Returns student profile dict if valid, otherwise None.
    """
    if not student_id or not password:
        return None
        
    student_id = student_id.strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT student_id, name, email, class_name, semester, password_hash
            FROM students
            WHERE UPPER(student_id) = UPPER(?)
        """, (student_id,))
        row = cursor.fetchone()
        
        if row and check_password_hash(row["password_hash"], password):
            return {
                "student_id": row["student_id"],
                "name": row["name"],
                "email": row["email"],
                "class_name": row["class_name"],
                "semester": row["semester"],
                "role": "student"
            }
    return None

def authenticate_admin(username: str, password: str):
    """
    Authenticate an administrator by username and password.
    Returns admin profile dict if valid, otherwise None.
    """
    if not username or not password:
        return None
        
    username = username.strip()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, name, password_hash
            FROM admins
            WHERE LOWER(username) = LOWER(?)
        """, (username,))
        row = cursor.fetchone()
        
        if row and check_password_hash(row["password_hash"], password):
            return {
                "id": row["id"],
                "username": row["username"],
                "name": row["name"],
                "role": "admin"
            }
    return None

def get_student_by_id(student_id: str):
    """Retrieve student information by student_id."""
    if not student_id:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT student_id, name, email, class_name, semester
            FROM students
            WHERE UPPER(student_id) = UPPER(?)
        """, (student_id.strip(),))
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None
