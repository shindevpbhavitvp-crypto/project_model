from database.db import get_db

LOW_ATTENDANCE_THRESHOLD = 75.0

def get_student_attendance(student_id: str):
    """
    Fetch attendance data for the specified student.
    Calculates percentage per subject and overall stats.
    Safely handles zero total classes.
    """
    if not student_id:
        return {"error": "Missing student ID"}
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT subject, attended, total
            FROM attendance
            WHERE UPPER(student_id) = UPPER(?)
            ORDER BY subject ASC
        """, (student_id.strip(),))
        rows = cursor.fetchall()
        
    records = []
    total_attended_sum = 0
    total_classes_sum = 0
    low_attendance_subjects = []
    
    for row in rows:
        subject = row["subject"]
        attended = int(row["attended"])
        total = int(row["total"])
        
        pct = round((attended / total * 100), 1) if total > 0 else 0.0
        is_low = pct < LOW_ATTENDANCE_THRESHOLD
        
        total_attended_sum += attended
        total_classes_sum += total
        
        if is_low:
            low_attendance_subjects.append({
                "subject": subject,
                "percentage": pct,
                "attended": attended,
                "total": total,
                "shortage": total - attended
            })
            
        records.append({
            "subject": subject,
            "attended": attended,
            "total": total,
            "percentage": pct,
            "is_low": is_low,
            "status": "Shortage" if is_low else "Eligible"
        })
        
    overall_pct = round((total_attended_sum / total_classes_sum * 100), 1) if total_classes_sum > 0 else 0.0
    overall_is_low = overall_pct < LOW_ATTENDANCE_THRESHOLD
    
    return {
        "student_id": student_id,
        "records": records,
        "overall_attended": total_attended_sum,
        "overall_total": total_classes_sum,
        "overall_percentage": overall_pct,
        "overall_is_low": overall_is_low,
        "low_attendance_count": len(low_attendance_subjects),
        "low_attendance_subjects": low_attendance_subjects,
        "threshold": LOW_ATTENDANCE_THRESHOLD
    }

def format_attendance_for_chat(student_id: str, query: str = ""):
    """
    Format attendance data into a friendly, clear chatbot message.
    Handles general attendance, specific subject inquiries, and low-attendance warnings.
    """
    data = get_student_attendance(student_id)
    if "error" in data or not data.get("records"):
        return "I could not find any attendance records under your student ID."
        
    records = data["records"]
    q = query.lower()
    
    # Check if asking specifically about low attendance
    if any(k in q for k in ["low", "shortage", "below", "defaulter", "risk", "warning"]):
        low_subs = data["low_attendance_subjects"]
        if not low_subs:
            return (
                f"Great news! You have **no subjects below the 75% threshold**.\n\n"
                f"Your overall aggregate attendance is **{data['overall_percentage']}%** "
                f"({data['overall_attended']}/{data['overall_total']} classes attended)."
            )
        else:
            lines = [
                f"**Attendance Shortage Alert!** The minimum required attendance is **{data['threshold']}%**.\n",
                f"You currently have **{len(low_subs)} subject(s)** below the threshold:\n"
            ]
            for s in low_subs:
                lines.append(f"- **{s['subject']}**: {s['percentage']}% ({s['attended']}/{s['total']} attended)")
            lines.append("\nPlease consult your respective faculty advisor to avoid debarment from semester exams.")
            return "\n".join(lines)
            
    # Check if asking about a specific subject
    for record in records:
        if record["subject"].lower() in q:
            status_text = "Satisfactory (Eligible for exams)" if not record["is_low"] else "⚠️ Warning: Below 75% threshold"
            return (
                f"**Attendance for {record['subject']}**:\n"
                f"- Attended: **{record['attended']}** out of **{record['total']}** classes\n"
                f"- Percentage: **{record['percentage']}%**\n"
                f"- Status: **{status_text}**"
            )
            
    # Default full summary
    lines = [
        f"**Your Attendance Summary**:\n",
        f"- **Overall Aggregate**: **{data['overall_percentage']}%** ({data['overall_attended']}/{data['overall_total']} classes)",
        f"- Status: {'⚠️ Below 75% Minimum Requirement' if data['overall_is_low'] else '✅ Eligible for Examinations'}\n",
        f"**Subject Breakdown**:"
    ]
    for r in records:
        flag = "⚠️" if r["is_low"] else "✅"
        lines.append(f"- {flag} **{r['subject']}**: {r['percentage']}% ({r['attended']}/{r['total']} classes)")
        
    if data["low_attendance_count"] > 0:
        lines.append(f"\n*Note: You have {data['low_attendance_count']} subject(s) below the mandatory 75% limit.*")
        
    return "\n".join(lines)
