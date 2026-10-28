# AI-Based Smart College Assistant (RAG & Agentic AI)

An intelligent, local RAG-powered academic assistant for college students and faculty administrators. The system provides isolated timetable dispatching, real-time subject-wise attendance tracking with automatic 75% shortage alerts, document retrieval (curriculum, notices, exam regulations), and an administrative knowledge base portal.

---

## Key Features

- **Personalized Timetable Agent:** Dynamically resolves classes and lab schedules based on the student's enrolled program and semester.
- **Attendance Intelligence & Shortage Guard:** Computes aggregate and subject-level attendance percentages with automated defaulter alerts below the mandatory 75% threshold.
- **Local BM25 Document RAG:** Vector-less, high-precision retrieval over institutional documents (`.txt`, `.pdf`, `.docx`, `.md`) with chunking and source citation tags.
- **Interactive Multi-Modal Chat Interface:**
  - Dynamic bright theme with modern responsive cards.
  - Auto-scrolling conversation feed with lightweight client-side markdown parsing.
  - Web Speech API integration for speech-to-text input and voice synthesis narration.
  - Collapsible side drawer for full weekly schedules and granular attendance metrics.
- **Dean / Admin Management Portal:**
  - Real-time institutional metrics (Students, Documents, BM25 Chunks, Defaulters).
  - Drag-and-drop document ingestion and indexing pipeline.
  - Attendance defaulters table with immediate deficiency tracking.

---

## Project Structure

```text
Project_prototype/
│
├── app.py                      # Main Flask application & API routes
├── config.py                   # App configuration & demo accounts
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
│
├── database/
│   ├── db.py                   # SQLite database schema, seeding, and connection manager
│   └── college.db              # Local SQLite database
│
├── documents/                  # Default institutional reference documents
│   ├── academic_calendar.txt
│   ├── college_notices.txt
│   ├── examination_rules.txt
│   └── syllabus_btech_cse.txt
│
├── services/
│   ├── attendance_service.py   # Attendance calculations & alert formatting
│   ├── auth_service.py         # Student and Administrator authentication
│   ├── chatbot_service.py      # Intent classifier & query routing agent
│   ├── document_service.py     # Document text extraction, chunking, and BM25 RAG
│   └── timetable_service.py    # Timetable scheduling & day-filtering
│
├── static/
│   ├── css/
│   │   └── style.css           # Modern bright aesthetic design system
│   └── js/
│       └── chat.js             # Chat controller, speech API, & drawer logic
│
├── templates/
│   ├── base.html               # Master layout with navbar and user pill
│   ├── login.html              # Dual login with 1-click demo accounts
│   ├── chat.html               # Student conversational assistant
│   └── admin.html              # Dean / Admin knowledge management portal
│
└── tests/
    └── test_college_assistant.py # Unit test suite
```

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize Database & Seed Records
```bash
python database/db.py
```

### 3. Run Application Server
```bash
python app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## Demo Accounts

| Role | Username / ID | Password | Notes |
|---|---|---|---|
| Student | `STU001` | `student123` | Aarav Sharma (B.Tech CSE Sem 6) — 89.3% Attendance |
| Student | `STU002` | `student123` | Priya Patel (B.Tech IT Sem 4) — 93.3% Attendance |
| Student | `STU003` | `student123` | Rohan Verma (B.Tech CSE Sem 6) — Shortage Alert (<75%) |
| Admin / Dean | `admin` | `admin123` | Prof. S. R. Deshmukh (Dean Academics) |

---

## Running Unit Tests
```bash
python -m unittest tests/test_college_assistant.py
```
