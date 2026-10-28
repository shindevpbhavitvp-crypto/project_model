from datetime import datetime
from database.db import get_db

DAY_ORDER = {
    "Monday": 1,
    "Tuesday": 2,
    "Wednesday": 3,
    "Thursday": 4,
    "Friday": 5,
    "Saturday": 6,
    "Sunday": 7
}

def get_student_class_and_sem(student_id: str):
    """Retrieve class name and semester for a given student."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT class_name, semester FROM students WHERE UPPER(student_id) = UPPER(?)", (student_id.strip(),))
        row = cursor.fetchone()
        if row:
            return row["class_name"], row["semester"]
    return None, None

def get_timetable_for_student(student_id: str, day_filter: str = None):
    """
    Fetch timetable records strictly for the student's assigned class and semester.
    Guarantees academic group isolation.
    """
    class_name, semester = get_student_class_and_sem(student_id)
    if not class_name:
        return {
            "error": "Student record not found",
            "class_name": None,
            "semester": None,
            "days": {}
        }
        
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT day, time, subject, room, faculty
            FROM timetable
            WHERE class_name = ? AND semester = ?
        """
        params = [class_name, semester]
        
        if day_filter:
            query += " AND LOWER(day) = LOWER(?)"
            params.append(day_filter)
            
        query += """
            ORDER BY
                CASE day
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    ELSE 7
                END,
                time ASC
        """
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
    grouped = {}
    for row in rows:
        d = row["day"]
        if d not in grouped:
            grouped[d] = []
        grouped[d].append({
            "time": row["time"],
            "subject": row["subject"],
            "room": row["room"],
            "faculty": row["faculty"]
        })
        
    return {
        "student_id": student_id,
        "class_name": class_name,
        "semester": semester,
        "timetable_by_day": grouped,
        "raw_entries": [dict(r) for r in rows]
    }

def format_timetable_for_chat(student_id: str, requested_day: str = None):
    """
    Generate an AI assistant response for timetable queries.
    Recognizes day requests like 'today', 'tomorrow', 'Monday', etc.
    """
    current_weekday = datetime.now().strftime("%A")
    
    target_day = None
    if requested_day:
        req_lower = requested_day.lower()
        if "today" in req_lower:
            target_day = current_weekday
        elif "tomorrow" in req_lower:
            # calculate tomorrow's weekday
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            today_idx = day_names.index(current_weekday) if current_weekday in day_names else 0
            target_day = day_names[(today_idx + 1) % 7]
        else:
            for day in DAY_ORDER.keys():
                if day.lower() in req_lower:
                    target_day = day
                    break
                    
    data = get_timetable_for_student(student_id, day_filter=target_day)
    if "error" in data:
        return "Unable to locate student records for timetable lookup."
        
    class_name = data["class_name"]
    semester = data["semester"]
    grouped = data["timetable_by_day"]
    
    if not grouped:
        if target_day:
            return f"No classes scheduled on **{target_day}** for **{class_name} (Semester {semester})**."
        return f"No timetable entries found for **{class_name} (Semester {semester})**."
        
    lines = []
    if target_day:
        lines.append(f"**Timetable for {target_day}** ({class_name}, Semester {semester}):\n")
        slots = grouped.get(target_day, [])
        for slot in slots:
            lines.append(f"- **{slot['time']}**: {slot['subject']} | Room: {slot['room']} | Faculty: {slot['faculty']}")
    else:
        lines.append(f"**Weekly Timetable Schedule** for **{class_name} (Semester {semester})**:\n")
        for day, slots in grouped.items():
            lines.append(f"**{day}:**")
            for slot in slots:
                lines.append(f"  * {slot['time']} - {slot['subject']} ({slot['room']}, {slot['faculty']})")
                
    return "\n".join(lines)
