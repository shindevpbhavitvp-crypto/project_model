import re
from services.timetable_service import format_timetable_for_chat
from services.attendance_service import format_attendance_for_chat
from services.document_service import answer_document_query

# Keyword triggers for intent routing
ATTENDANCE_TRIGGERS = [
    "attendance", "attendence", "present", "absent", "percentage",
    "bunk", "classes attended", "conducted", "shortage", "defaulter",
    "eligible for exam", "exam eligibility", "low attendance"
]

TIMETABLE_TRIGGERS = [
    "timetable", "time table", "schedule", "classes today", "class today",
    "lecture", "lectures", "which class", "when is", "what time",
    "classroom", "room", "faculty", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "tomorrow's class", "today's class"
]

GREETING_TRIGGERS = [
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "who are you", "what can you do", "help", "commands"
]

def classify_intent(message: str) -> str:
    """
    Classify user message intent:
    - 'attendance'
    - 'timetable'
    - 'greeting'
    - 'document_qa'
    """
    msg = message.lower()
    
    # 1. Attendance intent
    if any(k in msg for k in ATTENDANCE_TRIGGERS):
        return "attendance"
        
    # 2. Timetable intent
    if any(k in msg for k in TIMETABLE_TRIGGERS):
        return "timetable"
        
    # 3. Greeting / capabilities
    words = set(re.findall(r"\w+", msg))
    if any(g in msg for g in GREETING_TRIGGERS) and len(words) <= 4:
        return "greeting"
        
    # 4. Default to document retrieval / college knowledge
    return "document_qa"

def process_chat_message(message: str, user_session: dict):
    """
    Central routing pipeline for chatbot queries.
    Uses authenticated user session data securely.
    """
    if not message or not message.strip():
        return {
            "answer": "Please ask a question regarding your timetable, attendance, or college documents.",
            "source": "Input Validation",
            "intent": "empty"
        }
        
    clean_msg = message.strip()
    intent = classify_intent(clean_msg)
    role = user_session.get("role", "student")
    user_id = user_session.get("user_id")
    user_name = user_session.get("name", "Student")
    
    # 1. TIMETABLE INTENT ROUTING
    if intent == "timetable":
        if role != "student":
            return {
                "answer": (
                    "You are currently logged in as an **Administrator**.\n\n"
                    "Timetables are personalized based on each student's specific class and semester. "
                    "To view a student's personal schedule, please sign in with a student demo account (e.g. `STU001` or `STU002`)."
                ),
                "source": "Timetable Routing Agent (Role Notice)",
                "intent": "timetable"
            }
        answer = format_timetable_for_chat(user_id, requested_day=clean_msg)
        return {
            "answer": answer,
            "source": f"Personal Timetable Agent ({user_session.get('class_name', 'Student Group')})",
            "intent": "timetable"
        }
        
    # 2. ATTENDANCE INTENT ROUTING
    elif intent == "attendance":
        if role != "student":
            return {
                "answer": (
                    "You are currently logged in as an **Administrator**.\n\n"
                    "Attendance records are strictly private and linked to individual enrolled students. "
                    "To inspect student attendance reports, log in with a student account (e.g. `STU001` or `STU003`)."
                ),
                "source": "Attendance Routing Agent (Role Notice)",
                "intent": "attendance"
            }
        answer = format_attendance_for_chat(user_id, query=clean_msg)
        return {
            "answer": answer,
            "source": f"Personal Attendance Agent (Student ID: {user_id})",
            "intent": "attendance"
        }
        
    # 3. GREETINGS & INTRO
    elif intent == "greeting":
        greeting_text = (
            f"Hello **{user_name}**! 👋\n\n"
            f"I am your **AI College Assistant**. Here are things I can assist you with:\n\n"
            f"- 📅 **Timetable Queries:** *'What is my timetable for today?'*, *'Show Monday's schedule'*\n"
            f"- 📊 **Attendance Tracking:** *'What is my overall attendance?'*, *'Which subjects have low attendance?'*\n"
            f"- 📖 **Curriculum & Syllabus:** *'Explain the Machine Learning syllabus'*, *'What are the topics in Cyber Security?'*\n"
            f"- 📋 **Exam Regulations & Policies:** *'What are the rules for exam eligibility?'*, *'What is the passing criteria?'*\n"
            f"- 🏢 **Campus Notices & Calendar:** *'What are the library timings?'*, *'Summarize the academic calendar'*\n\n"
            f"Feel free to ask any question or tap on the quick prompts below!"
        )
        return {
            "answer": greeting_text,
            "source": "College Assistant Guide",
            "intent": "greeting"
        }
        
    # 4. DOCUMENT RETRIEVAL / RAG PIPELINE
    doc_result = answer_document_query(clean_msg)
    if doc_result:
        return {
            "answer": doc_result["answer"],
            "source": doc_result["source"],
            "intent": "document_rag"
        }
        
    # 5. FALLBACK RESPONSE
    return {
        "answer": (
            "I could not find a direct answer to your question in the uploaded college documents or your academic profile.\n\n"
            "**Helpful suggestions:**\n"
            "- Ask about your **timetable** or **attendance**.\n"
            "- Ask about **examination rules**, **passing criteria**, or **malpractice penalties**.\n"
            "- Ask about the **academic calendar**, **semester dates**, or **holidays**.\n"
            "- Ask about the **B.Tech CSE or IT syllabus**.\n"
            "- Ask about **central library timings**, **hostel rules**, or **placement criteria**.\n\n"
            "*(If an official notice was recently issued, the administrator can upload it via the Admin portal to make it instantly searchable.)*"
        ),
        "source": "College Assistant Fallback",
        "intent": "unmatched"
    }
