import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash

# Add project root to path for direct execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config

from contextlib import contextmanager

@contextmanager
def get_db():
    """Get SQLite database connection with row factory enabled."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()

def split_text_into_chunks(text, max_chunk_words=120, overlap_words=25):
    """
    Split text into overlapping chunks for retrieval.
    Ideal for academic documents and local retrieval.
    """
    words = text.split()
    if not words:
        return []
        
    chunks = []
    i = 0
    step = max(1, max_chunk_words - overlap_words)
    while i < len(words):
        chunk_words = words[i:i + max_chunk_words]
        chunk_text = " ".join(chunk_words)
        if chunk_text.strip():
            chunks.append(chunk_text.strip())
        i += step
        if i >= len(words):
            break
    return chunks

def init_db():
    """
    Initialize SQLite database schema and seed demonstration records.
    Does NOT overwrite or wipe data if already initialized.
    """
    Config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Students table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                class_name TEXT NOT NULL,
                semester INTEGER NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Admins table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Timetable table (organized by class and semester)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                semester INTEGER NOT NULL,
                day TEXT NOT NULL,
                time TEXT NOT NULL,
                subject TEXT NOT NULL,
                room TEXT NOT NULL,
                faculty TEXT NOT NULL
            )
        """)
        
        # 4. Attendance table (tied to student_id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                attended INTEGER NOT NULL,
                total INTEGER NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
            )
        """)
        
        # 5. Uploaded Documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_date TEXT NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # 6. Document Chunks table for RAG retrieval
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                FOREIGN KEY (document_id) REFERENCES uploaded_documents(id) ON DELETE CASCADE
            )
        """)
        
        # Seed Students if table empty
        student_count = cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        if student_count == 0:
            student_records = [
                ("STU001", "Aarav Sharma", "aarav.sharma@college.edu", "B.Tech CSE", 6, generate_password_hash("student123")),
                ("STU002", "Priya Patel", "priya.patel@college.edu", "B.Tech IT", 4, generate_password_hash("student123")),
                ("STU003", "Rohan Verma", "rohan.verma@college.edu", "B.Tech CSE", 6, generate_password_hash("student123"))
            ]
            cursor.executemany("""
                INSERT INTO students (student_id, name, email, class_name, semester, password_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, student_records)
            
        # Seed Admins if table empty
        admin_count = cursor.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
        if admin_count == 0:
            cursor.execute("""
                INSERT INTO admins (username, name, password_hash)
                VALUES (?, ?, ?)
            """, ("admin", "Prof. S. R. Deshmukh (Dean Academics)", generate_password_hash("admin123")))
            
        # Seed Timetable if table empty
        timetable_count = cursor.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
        if timetable_count == 0:
            # Timetable for B.Tech CSE Semester 6
            cse_timetable = [
                ("B.Tech CSE", 6, "Monday", "09:00 - 10:00", "Machine Learning", "Lab 3", "Prof. Dr. K. Sharma"),
                ("B.Tech CSE", 6, "Monday", "10:00 - 11:00", "Cloud Computing", "Room 302", "Prof. V. Patil"),
                ("B.Tech CSE", 6, "Monday", "11:15 - 12:15", "Cyber Security", "Room 302", "Prof. R. Joshi"),
                ("B.Tech CSE", 6, "Monday", "01:15 - 03:15", "Machine Learning Lab", "AI Lab A", "Prof. Dr. K. Sharma"),
                
                ("B.Tech CSE", 6, "Tuesday", "09:00 - 10:00", "Software Engineering", "Room 302", "Prof. M. Kulkarni"),
                ("B.Tech CSE", 6, "Tuesday", "10:00 - 11:00", "Machine Learning", "Room 302", "Prof. Dr. K. Sharma"),
                ("B.Tech CSE", 6, "Tuesday", "11:15 - 12:15", "Cloud Computing", "Room 302", "Prof. V. Patil"),
                ("B.Tech CSE", 6, "Tuesday", "01:15 - 03:15", "Cloud & DevOps Lab", "Systems Lab 2", "Prof. V. Patil"),
                
                ("B.Tech CSE", 6, "Wednesday", "09:00 - 10:00", "Cyber Security", "Room 302", "Prof. R. Joshi"),
                ("B.Tech CSE", 6, "Wednesday", "10:00 - 11:00", "Software Engineering", "Room 302", "Prof. M. Kulkarni"),
                ("B.Tech CSE", 6, "Wednesday", "11:15 - 12:15", "Machine Learning", "Room 302", "Prof. Dr. K. Sharma"),
                ("B.Tech CSE", 6, "Wednesday", "01:15 - 03:15", "Cyber Security & Pen Testing Lab", "Network Lab", "Prof. R. Joshi"),
                
                ("B.Tech CSE", 6, "Thursday", "09:00 - 10:00", "Cloud Computing", "Room 302", "Prof. V. Patil"),
                ("B.Tech CSE", 6, "Thursday", "10:00 - 11:00", "Cyber Security", "Room 302", "Prof. R. Joshi"),
                ("B.Tech CSE", 6, "Thursday", "11:15 - 12:15", "Software Engineering", "Room 302", "Prof. M. Kulkarni"),
                ("B.Tech CSE", 6, "Thursday", "01:15 - 02:15", "Capstone Project Seminar", "Seminar Hall 1", "Dr. A. P. Mehta"),
                
                ("B.Tech CSE", 6, "Friday", "09:00 - 10:00", "Machine Learning", "Room 302", "Prof. Dr. K. Sharma"),
                ("B.Tech CSE", 6, "Friday", "10:00 - 11:00", "Software Engineering", "Room 302", "Prof. M. Kulkarni"),
                ("B.Tech CSE", 6, "Friday", "11:15 - 12:15", "Open Elective (Generative AI)", "Auditorium 2", "Dr. N. Gupta"),
                ("B.Tech CSE", 6, "Friday", "02:00 - 04:00", "Coding Hub & Technical Mentorship", "CS Hub", "Prof. M. Kulkarni")
            ]
            
            # Timetable for B.Tech IT Semester 4
            it_timetable = [
                ("B.Tech IT", 4, "Monday", "09:00 - 10:00", "Database Management Systems", "Room 204", "Prof. S. Naik"),
                ("B.Tech IT", 4, "Monday", "10:00 - 11:00", "Computer Networks", "Room 204", "Prof. P. Iyer"),
                ("B.Tech IT", 4, "Monday", "11:15 - 12:15", "Operating Systems", "Room 204", "Prof. G. Sen"),
                ("B.Tech IT", 4, "Monday", "01:15 - 03:15", "DBMS & SQL Lab", "Lab 1", "Prof. S. Naik"),
                
                ("B.Tech IT", 4, "Tuesday", "09:00 - 10:00", "Web Technologies", "Room 204", "Prof. A. Roy"),
                ("B.Tech IT", 4, "Tuesday", "10:00 - 11:00", "Operating Systems", "Room 204", "Prof. G. Sen"),
                ("B.Tech IT", 4, "Tuesday", "11:15 - 12:15", "Computer Networks", "Room 204", "Prof. P. Iyer"),
                ("B.Tech IT", 4, "Tuesday", "01:15 - 03:15", "Web Development Full-Stack Lab", "Web Lab", "Prof. A. Roy"),
                
                ("B.Tech IT", 4, "Wednesday", "09:00 - 10:00", "Database Management Systems", "Room 204", "Prof. S. Naik"),
                ("B.Tech IT", 4, "Wednesday", "10:00 - 11:00", "Web Technologies", "Room 204", "Prof. A. Roy"),
                ("B.Tech IT", 4, "Wednesday", "11:15 - 12:15", "Computer Networks", "Room 204", "Prof. P. Iyer"),
                ("B.Tech IT", 4, "Wednesday", "01:15 - 03:15", "Operating Systems & Shell Scripting Lab", "Unix Lab", "Prof. G. Sen"),
                
                ("B.Tech IT", 4, "Thursday", "09:00 - 10:00", "Operating Systems", "Room 204", "Prof. G. Sen"),
                ("B.Tech IT", 4, "Thursday", "10:00 - 11:00", "Database Management Systems", "Room 204", "Prof. S. Naik"),
                ("B.Tech IT", 4, "Thursday", "11:15 - 12:15", "Web Technologies", "Room 204", "Prof. A. Roy"),
                ("B.Tech IT", 4, "Thursday", "01:15 - 02:15", "Mini-Project Review", "Seminar Hall 2", "Prof. S. Naik"),
                
                ("B.Tech IT", 4, "Friday", "09:00 - 10:00", "Computer Networks", "Room 204", "Prof. P. Iyer"),
                ("B.Tech IT", 4, "Friday", "10:00 - 11:00", "Database Management Systems", "Room 204", "Prof. S. Naik"),
                ("B.Tech IT", 4, "Friday", "11:15 - 12:15", "Discrete Mathematics", "Room 204", "Dr. H. Nair"),
                ("B.Tech IT", 4, "Friday", "02:00 - 04:00", "Competitive Programming Club", "Lab 4", "Prof. P. Iyer")
            ]
            
            cursor.executemany("""
                INSERT INTO timetable (class_name, semester, day, time, subject, room, faculty)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, cse_timetable + it_timetable)
            
        # Seed Attendance if table empty
        attendance_count = cursor.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
        if attendance_count == 0:
            attendance_records = [
                # STU001 (Aarav Sharma - CSE Sem 6) - Good Attendance (89.3%)
                ("STU001", "Machine Learning", 36, 40),
                ("STU001", "Cloud Computing", 34, 38),
                ("STU001", "Cyber Security", 31, 36),
                ("STU001", "Software Engineering", 32, 35),
                
                # STU002 (Priya Patel - IT Sem 4) - Excellent Attendance (93.3%)
                ("STU002", "Database Management Systems", 38, 40),
                ("STU002", "Computer Networks", 35, 38),
                ("STU002", "Operating Systems", 33, 36),
                ("STU002", "Web Technologies", 34, 36),
                
                # STU003 (Rohan Verma - CSE Sem 6) - Low Attendance Alert in Cloud & Cyber Security!
                ("STU003", "Machine Learning", 32, 40),
                ("STU003", "Cloud Computing", 25, 38),     # 65.8% (Alert!)
                ("STU003", "Cyber Security", 24, 36),      # 66.7% (Alert!)
                ("STU003", "Software Engineering", 29, 35)
            ]
            cursor.executemany("""
                INSERT INTO attendance (student_id, subject, attended, total)
                VALUES (?, ?, ?, ?)
            """, attendance_records)
            
        # Seed Uploaded Documents & Chunks if table empty
        doc_count = cursor.execute("SELECT COUNT(*) FROM uploaded_documents").fetchone()[0]
        if doc_count == 0 and Config.DOCUMENTS_FOLDER.exists():
            for doc_file in Config.DOCUMENTS_FOLDER.iterdir():
                if doc_file.is_file() and doc_file.suffix.lower() in Config.ALLOWED_EXTENSIONS:
                    try:
                        content = doc_file.read_text(encoding="utf-8", errors="ignore")
                        chunks = split_text_into_chunks(content)
                        size = doc_file.stat().st_size
                        date_str = datetime.fromtimestamp(doc_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                        
                        cursor.execute("""
                            INSERT INTO uploaded_documents (filename, original_name, file_type, file_size, upload_date, chunk_count)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (doc_file.name, doc_file.name, doc_file.suffix.lower().replace(".", "").upper(), size, date_str, len(chunks)))
                        doc_id = cursor.lastrowid
                        
                        chunk_rows = []
                        for idx, chunk in enumerate(chunks):
                            chunk_rows.append((doc_id, idx, chunk, len(chunk.split())))
                            
                        cursor.executemany("""
                            INSERT INTO document_chunks (document_id, chunk_index, chunk_text, token_count)
                            VALUES (?, ?, ?, ?)
                        """, chunk_rows)
                    except Exception as e:
                        print(f"Error indexing initial document {doc_file.name}: {e}")
                        
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
