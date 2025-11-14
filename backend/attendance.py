"""
Attendance Management Module
Handles subject-based attendance with automatic absent marking
"""

from typing import Optional, Dict, List
from datetime import datetime, timedelta
from db import supabase

# =====================================================
# ATTENDANCE SESSION FUNCTIONS
# =====================================================

def start_attendance_session(
    teacher_id: str,
    subject_id: int,
    section: str,
    semester: int,
    class_name: str,
    duration_minutes: int = 60
) -> Optional[Dict]:
    """
    Start a new attendance session
    Automatically marks all students in the section as 'absent'
    
    Args:
        teacher_id: Teacher's ID
        subject_id: Subject ID from subjects table
        section: Section name (e.g., 'A', 'B')
        semester: Semester number (1-8)
        class_name: Class name (e.g., 'CSE-A')
        duration_minutes: Expected class duration
        
    Returns:
        Session data with session_id
    """
    try:
        print(f"\n=== Starting Attendance Session ===")
        print(f"Teacher: {teacher_id}")
        print(f"Subject ID: {subject_id}")
        print(f"Section: {section}, Semester: {semester}")
        print(f"Class: {class_name}")
        
        # Check if there's already an active session for this section/subject
        existing_active = supabase.table("attendance_sessions").select("*").eq(
            "section", section
        ).eq("semester", semester).eq("subject_id", subject_id).eq(
            "status", "active"
        ).execute()
        
        if existing_active.data:
            print(f"Active session already exists: {existing_active.data[0]['session_id']}")
            return existing_active.data[0]
        
        # Create new session
        session_data = {
            "teacher_id": teacher_id,
            "subject_id": subject_id,
            "section": section.upper(),
            "semester": semester,
            "class_name": class_name.upper(),
            "duration_minutes": duration_minutes,
            "status": "active",
            "session_date": datetime.now().date().isoformat(),
            "start_time": datetime.now().isoformat()
        }
        
        result = supabase.table("attendance_sessions").insert(session_data).execute()
        
        if result.data:
            session = result.data[0]
            print(f"✓ Session created: {session['session_id']}")
            print(f"✓ All students marked as absent automatically via trigger")
            return session
        
        return None
        
    except Exception as e:
        print(f"Error starting attendance session: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_active_session(section: str, semester: int, subject_id: int = None) -> Optional[Dict]:
    """
    Get the active attendance session for a section
    
    Args:
        section: Section name
        semester: Semester number
        subject_id: Optional subject ID filter
        
    Returns:
        Active session data or None
    """
    try:
        query = supabase.table("attendance_sessions").select("*").eq(
            "section", section.upper()
        ).eq("semester", semester).eq("status", "active")
        
        if subject_id:
            query = query.eq("subject_id", subject_id)
        
        result = query.order("start_time", desc=True).limit(1).execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error getting active session: {e}")
        return None


def end_attendance_session(session_id: str) -> bool:
    """
    End an attendance session
    
    Args:
        session_id: Session UUID
        
    Returns:
        True if successful
    """
    try:
        result = supabase.table("attendance_sessions").update({
            "status": "completed",
            "end_time": datetime.now().isoformat()
        }).eq("session_id", session_id).execute()
        
        print(f"✓ Session {session_id} ended")
        return bool(result.data)
        
    except Exception as e:
        print(f"Error ending session: {e}")
        return False


# =====================================================
# ATTENDANCE MARKING FUNCTIONS
# =====================================================

def mark_student_present(
    session_id: str,
    enrollment_number: str,
    confidence: float = 0.0,
    marked_by: str = "system"
) -> Optional[Dict]:
    """
    Mark a student as present in an attendance session
    
    Args:
        session_id: Session UUID
        enrollment_number: Student enrollment number
        confidence: Face recognition confidence score
        marked_by: Who marked the attendance ('system', 'manual', 'teacher_override')
        
    Returns:
        Updated attendance record
    """
    try:
        # Get session details to calculate time difference
        session = supabase.table("attendance_sessions").select("start_time").eq(
            "session_id", session_id
        ).execute()
        
        if not session.data:
            print(f"Session not found: {session_id}")
            return None
        
        start_time = datetime.fromisoformat(session.data[0]['start_time'].replace('Z', '+00:00'))
        current_time = datetime.now()
        time_diff_minutes = int((current_time - start_time).total_seconds() / 60)
        
        # Determine if student is late (more than 10 minutes after start)
        status = "late" if time_diff_minutes > 10 else "present"
        
        # Update attendance record
        update_data = {
            "status": status,
            "marked_at": current_time.isoformat(),
            "arrival_time": current_time.isoformat(),
            "time_difference_minutes": time_diff_minutes,
            "recognition_confidence": confidence,
            "marked_by": marked_by
        }
        
        result = supabase.table("attendance_records").update(update_data).eq(
            "session_id", session_id
        ).eq("enrollment_number", enrollment_number).execute()
        
        if result.data:
            record = result.data[0]
            print(f"✓ {enrollment_number} marked {status} ({time_diff_minutes}min, {confidence:.2%})")
            return record
        
        return None
        
    except Exception as e:
        print(f"Error marking attendance: {e}")
        import traceback
        traceback.print_exc()
        return None


def mark_student_absent(session_id: str, enrollment_number: str) -> Optional[Dict]:
    """
    Manually mark a student as absent (override)
    
    Args:
        session_id: Session UUID
        enrollment_number: Student enrollment number
        
    Returns:
        Updated attendance record
    """
    try:
        result = supabase.table("attendance_records").update({
            "status": "absent",
            "marked_by": "teacher_override",
            "marked_at": datetime.now().isoformat()
        }).eq("session_id", session_id).eq("enrollment_number", enrollment_number).execute()
        
        return result.data[0] if result.data else None
        
    except Exception as e:
        print(f"Error marking absent: {e}")
        return None


# =====================================================
# ATTENDANCE QUERY FUNCTIONS
# =====================================================

def get_session_attendance(session_id: str) -> List[Dict]:
    """
    Get all attendance records for a session
    
    Args:
        session_id: Session UUID
        
    Returns:
        List of attendance records
    """
    try:
        result = supabase.table("attendance_records").select("*").eq(
            "session_id", session_id
        ).order("student_name").execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"Error getting session attendance: {e}")
        return []


def get_student_attendance_history(
    enrollment_number: str,
    subject_id: int = None,
    start_date: str = None,
    end_date: str = None
) -> List[Dict]:
    """
    Get attendance history for a student
    
    Args:
        enrollment_number: Student enrollment number
        subject_id: Optional subject filter
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        
    Returns:
        List of attendance records with session details
    """
    try:
        # Query using the view for detailed information
        query = supabase.table("student_attendance_details").select("*").eq(
            "enrollment_number", enrollment_number
        )
        
        if subject_id:
            query = query.eq("subject_id", subject_id)
        
        if start_date:
            query = query.gte("session_date", start_date)
        
        if end_date:
            query = query.lte("session_date", end_date)
        
        result = query.order("session_date", desc=True).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"Error getting student attendance history: {e}")
        return []


def get_subject_attendance_stats(
    section: str,
    semester: int,
    subject_id: int,
    start_date: str = None,
    end_date: str = None
) -> Dict:
    """
    Get attendance statistics for a subject
    
    Args:
        section: Section name
        semester: Semester number
        subject_id: Subject ID
        start_date: Optional start date
        end_date: Optional end date
        
    Returns:
        Statistics including total classes, present/absent counts per student
    """
    try:
        # Get all sessions for this subject/section
        query = supabase.table("attendance_sessions").select("session_id, session_date").eq(
            "section", section.upper()
        ).eq("semester", semester).eq("subject_id", subject_id)
        
        if start_date:
            query = query.gte("session_date", start_date)
        
        if end_date:
            query = query.lte("session_date", end_date)
        
        sessions = query.execute()
        
        if not sessions.data:
            return {
                "total_classes": 0,
                "students": []
            }
        
        session_ids = [s['session_id'] for s in sessions.data]
        
        # Get attendance records for these sessions
        records = supabase.table("attendance_records").select(
            "enrollment_number, student_name, status"
        ).in_("session_id", session_ids).execute()
        
        # Calculate statistics per student
        stats = {}
        for record in records.data:
            enr = record['enrollment_number']
            
            if enr not in stats:
                stats[enr] = {
                    "enrollment_number": enr,
                    "student_name": record['student_name'],
                    "total_classes": 0,
                    "present": 0,
                    "absent": 0,
                    "late": 0,
                    "percentage": 0.0
                }
            
            stats[enr]["total_classes"] += 1
            
            if record['status'] == 'present':
                stats[enr]["present"] += 1
            elif record['status'] == 'absent':
                stats[enr]["absent"] += 1
            elif record['status'] == 'late':
                stats[enr]["late"] += 1
        
        # Calculate percentages
        for student_data in stats.values():
            total = student_data["total_classes"]
            if total > 0:
                student_data["percentage"] = round(
                    (student_data["present"] + student_data["late"]) / total * 100, 2
                )
        
        return {
            "total_classes": len(sessions.data),
            "students": list(stats.values())
        }
        
    except Exception as e:
        print(f"Error getting subject attendance stats: {e}")
        import traceback
        traceback.print_exc()
        return {"total_classes": 0, "students": []}


def get_daily_attendance_report(date: str, section: str = None) -> List[Dict]:
    """
    Get attendance report for a specific date
    
    Args:
        date: Date in YYYY-MM-DD format
        section: Optional section filter
        
    Returns:
        List of sessions with attendance data
    """
    try:
        query = supabase.table("attendance_sessions").select(
            "*, subjects(subject_name), teachers(teacher_name)"
        ).eq("session_date", date)
        
        if section:
            query = query.eq("section", section.upper())
        
        result = query.order("start_time").execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"Error getting daily report: {e}")
        return []


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def get_low_attendance_students(
    section: str,
    semester: int,
    subject_id: int,
    threshold: float = 75.0
) -> List[Dict]:
    """
    Get students with attendance below threshold
    
    Args:
        section: Section name
        semester: Semester number
        subject_id: Subject ID
        threshold: Attendance percentage threshold (default 75%)
        
    Returns:
        List of students with low attendance
    """
    try:
        stats = get_subject_attendance_stats(section, semester, subject_id)
        
        low_attendance = [
            student for student in stats["students"]
            if student["percentage"] < threshold
        ]
        
        # Sort by percentage (lowest first)
        low_attendance.sort(key=lambda x: x["percentage"])
        
        return low_attendance
        
    except Exception as e:
        print(f"Error getting low attendance students: {e}")
        return []


def update_attendance_summary(enrollment_number: str, subject_id: int, semester: int):
    """
    Update or create attendance summary for a student
    
    Args:
        enrollment_number: Student enrollment number
        subject_id: Subject ID
        semester: Semester number
    """
    try:
        # Get all records for this student/subject
        records = supabase.table("attendance_records").select(
            "status, session_id"
        ).eq("enrollment_number", enrollment_number).execute()
        
        # Filter by subject
        sessions = supabase.table("attendance_sessions").select(
            "session_id"
        ).eq("subject_id", subject_id).eq("semester", semester).execute()
        
        session_ids = {s['session_id'] for s in sessions.data} if sessions.data else set()
        
        # Count attendance
        total = 0
        present = 0
        absent = 0
        late = 0
        
        for record in records.data:
            if record['session_id'] in session_ids:
                total += 1
                if record['status'] == 'present':
                    present += 1
                elif record['status'] == 'absent':
                    absent += 1
                elif record['status'] == 'late':
                    late += 1
        
        percentage = round((present + late) / total * 100, 2) if total > 0 else 0.0
        
        # Upsert summary
        summary_data = {
            "enrollment_number": enrollment_number,
            "subject_id": subject_id,
            "semester": semester,
            "total_classes": total,
            "present_count": present,
            "absent_count": absent,
            "late_count": late,
            "attendance_percentage": percentage
        }
        
        # Check if exists
        existing = supabase.table("attendance_summary").select("*").eq(
            "enrollment_number", enrollment_number
        ).eq("subject_id", subject_id).eq("semester", semester).execute()
        
        if existing.data:
            supabase.table("attendance_summary").update(summary_data).eq(
                "enrollment_number", enrollment_number
            ).eq("subject_id", subject_id).eq("semester", semester).execute()
        else:
            supabase.table("attendance_summary").insert(summary_data).execute()
        
        print(f"✓ Summary updated for {enrollment_number}: {percentage}%")
        
    except Exception as e:
        print(f"Error updating attendance summary: {e}")
        import traceback
        traceback.print_exc()