import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app
from database.db import init_db, get_db
from services.auth_service import authenticate_student, authenticate_admin, get_student_by_id
from services.attendance_service import get_student_attendance, format_attendance_for_chat
from services.timetable_service import get_timetable_for_student, format_timetable_for_chat
from services.document_service import retrieve_relevant_chunks, answer_document_query, list_all_documents
from services.chatbot_service import classify_intent, process_chat_message

class TestCollegeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Ensure database is initialized before running tests."""
        init_db()
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

    def test_01_database_seeded_properly(self):
        """Verify initial database tables and seed rows exist."""
        with get_db() as conn:
            cursor = conn.cursor()
            student_count = cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0]
            admin_count = cursor.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
            tt_count = cursor.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
            att_count = cursor.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
            doc_count = cursor.execute("SELECT COUNT(*) FROM uploaded_documents").fetchone()[0]
            chunk_count = cursor.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]

            self.assertGreaterEqual(student_count, 3)
            self.assertGreaterEqual(admin_count, 1)
            self.assertGreaterEqual(tt_count, 30)
            self.assertGreaterEqual(att_count, 10)
            self.assertGreaterEqual(doc_count, 1)
            self.assertGreaterEqual(chunk_count, 5)

    def test_02_student_authentication(self):
        """Verify student login with valid and invalid credentials."""
        # Valid credentials
        stu = authenticate_student("STU001", "student123")
        self.assertIsNotNone(stu)
        self.assertEqual(stu["student_id"], "STU001")
        self.assertEqual(stu["role"], "student")

        # Invalid password
        bad_stu = authenticate_student("STU001", "wrongpass")
        self.assertIsNone(bad_stu)

        # Non-existent student
        none_stu = authenticate_student("NONEXISTENT", "student123")
        self.assertIsNone(none_stu)

    def test_03_admin_authentication(self):
        """Verify administrator login with valid and invalid credentials."""
        admin = authenticate_admin("admin", "admin123")
        self.assertIsNotNone(admin)
        self.assertEqual(admin["username"], "admin")
        self.assertEqual(admin["role"], "admin")

        bad_admin = authenticate_admin("admin", "badpassword")
        self.assertIsNone(bad_admin)

    def test_04_attendance_calculation(self):
        """Verify accurate percentage and shortage detection."""
        # STU001 has high attendance
        data_stu1 = get_student_attendance("STU001")
        self.assertFalse(data_stu1["overall_is_low"])
        self.assertGreaterEqual(data_stu1["overall_percentage"], 75.0)

        # STU003 has low attendance alert
        data_stu3 = get_student_attendance("STU003")
        self.assertGreater(data_stu3["low_attendance_count"], 0)
        low_sub_names = [s["subject"] for s in data_stu3["low_attendance_subjects"]]
        self.assertIn("Cloud Computing", low_sub_names)

        # Test Chatbot attendance formatting
        chat_msg = format_attendance_for_chat("STU003", query="low attendance")
        self.assertIn("Attendance Shortage Alert", chat_msg)

    def test_05_timetable_lookup(self):
        """Verify student timetable retrieval by day."""
        tt_stu1 = get_timetable_for_student("STU001")
        self.assertEqual(tt_stu1["class_name"], "B.Tech CSE")
        self.assertEqual(tt_stu1["semester"], 6)
        self.assertIn("Monday", tt_stu1["timetable_by_day"])

        # Test Day Filter
        tt_monday = get_timetable_for_student("STU001", day_filter="Monday")
        self.assertIn("Monday", tt_monday["timetable_by_day"])
        self.assertEqual(len(tt_monday["timetable_by_day"]), 1)

    def test_06_document_rag_retrieval(self):
        """Verify BM25 chunk retrieval from indexed college documents."""
        # Query library rules
        lib_chunks = retrieve_relevant_chunks("library timings book borrowing limit")
        self.assertGreater(len(lib_chunks), 0)
        self.assertIn("college_notices.txt", lib_chunks[0]["filename"])

        # Query exam passing criteria
        exam_ans = answer_document_query("passing criteria examination rules")
        self.assertIsNotNone(exam_ans)
        self.assertIn("examination_rules.txt", exam_ans["answer"])

    def test_07_chatbot_intent_classification(self):
        """Verify correct intent classification."""
        self.assertEqual(classify_intent("What is my timetable today?"), "timetable")
        self.assertEqual(classify_intent("Do I have low attendance?"), "attendance")
        self.assertEqual(classify_intent("Hello, who are you?"), "greeting")
        self.assertEqual(classify_intent("What are the hostel curfew hours?"), "document_qa")

    def test_08_chatbot_full_pipeline(self):
        """Verify end-to-end chat message response generation."""
        session_data = {
            "role": "student",
            "user_id": "STU001",
            "name": "Aarav Sharma",
            "class_name": "B.Tech CSE",
            "semester": 6
        }

        # Timetable inquiry
        tt_res = process_chat_message("Show my Monday classes", session_data)
        self.assertEqual(tt_res["intent"], "timetable")
        self.assertIn("Monday", tt_res["answer"])

        # Attendance inquiry
        att_res = process_chat_message("What is my attendance percentage?", session_data)
        self.assertEqual(att_res["intent"], "attendance")
        self.assertIn("Attendance Summary", att_res["answer"])

        # Document inquiry
        doc_res = process_chat_message("What are the campus placement eligibility rules?", session_data)
        self.assertEqual(doc_res["intent"], "document_rag")
        self.assertIn("college_notices.txt", doc_res["answer"])

    def test_09_flask_routes_and_access_control(self):
        """Verify HTTP endpoints and redirect behaviors."""
        # Unauthenticated user access to /chat redirects to /login
        res_chat = self.client.get("/chat", follow_redirects=False)
        self.assertEqual(res_chat.status_code, 302)
        self.assertIn("/login", res_chat.headers["Location"])

        # Login page renders 200
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Portal Access", res_login.data)

        # Authenticate via session as student
        with self.client.session_transaction() as sess:
            sess["user_id"] = "STU001"
            sess["name"] = "Aarav Sharma"
            sess["role"] = "student"
            sess["class_name"] = "B.Tech CSE"
            sess["semester"] = 6

        # Now /chat should succeed
        res_chat_auth = self.client.get("/chat")
        self.assertEqual(res_chat_auth.status_code, 200)
        self.assertIn(b"Apex AI Assistant", res_chat_auth.data)

        # Chat API POST endpoint
        res_api = self.client.post("/api/chat", json={"message": "What is my timetable?"})
        self.assertEqual(res_api.status_code, 200)
        json_data = res_api.get_json()
        self.assertTrue(json_data["success"])
        self.assertEqual(json_data["intent"], "timetable")

if __name__ == "__main__":
    unittest.main()
