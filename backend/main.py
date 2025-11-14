from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
from datetime import datetime
import uuid

from db import (
    create_student, create_teacher, create_guest,
    get_student_images, store_file_record,
    store_teacher_file, store_guest_file
)
from capture import upload_to_cloudinary, generate_guest_token
from train import train_face_model
from test import recognize_face, recognize_multiple_faces

# Import attendance functions
from attendance import (
    start_attendance_session,
    end_attendance_session,
    get_active_session,
    mark_student_present,
    mark_student_absent,
    get_session_attendance,
    get_student_attendance_history,
    get_subject_attendance_stats,
    get_daily_attendance_report,
    get_low_attendance_students,
    update_attendance_summary
)

def roman_to_int(roman: str) -> int:
    """
    Convert Roman numeral to integer
    Supports I through VIII (1-8)
    """
    roman_map = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4,
        'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8
    }
    
    # Handle both uppercase and lowercase
    roman_upper = roman.upper().strip()
    
    # If it's already a number, return it
    try:
        return int(roman)
    except ValueError:
        pass
    
    # Convert Roman numeral
    if roman_upper in roman_map:
        return roman_map[roman_upper]
    
    raise ValueError(f"Invalid semester value: {roman}. Must be 1-8 or I-VIII")

app = FastAPI(title="Face Recognition System with Attendance")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Face Recognition System API with Attendance", 
        "status": "running",
        "version": "2.0",
        "features": [
            "Student/Teacher/Guest Registration",
            "Face Recognition Training",
            "Face Recognition Testing",
            "Subject-based Attendance Management"
        ]
    }

# =====================================================
# REGISTRATION ENDPOINTS
# =====================================================

@app.post("/register/student")
async def register_student(
    name: str = Form(...),
    enrollment_number: str = Form(...),
    section: str = Form(...),
    year: str = Form(...),
    email: str = Form(None),
    mobile: str = Form(None),
    fees: str = Form(None),
    branch: str = Form("CS"),
    images: List[UploadFile] = File(...)
):
    """Register a new student with face images"""
    try:
        print(f"\n=== Student Registration Request ===")
        print(f"Name: {name}")
        print(f"Enrollment: {enrollment_number}")
        print(f"Email: {email}")
        print(f"Mobile: {mobile}")
        print(f"Fees: {fees}")
        print(f"Section: {section}")
        print(f"Year: {year}")
        print(f"Branch: {branch}")
        print(f"Images count: {len(images)}")
        
        # Validate minimum images
        if len(images) < 5:
            raise HTTPException(status_code=400, detail="Minimum 5 images required")
        
        # Generate email if not provided
        if not email:
            email = f"{enrollment_number}@student.edu"
            print(f"Generated email: {email}")
        
        # Create student record
        print("Creating student record...")
        
        # Import here to avoid caching issues
        from db import supabase
        
        # Convert year/semester to integer (handles Roman numerals)
        try:
            semester_int = roman_to_int(year)
            print(f"Converted semester '{year}' to {semester_int}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Create or update student
        try:
            student_data = {
                "enrollment_number": enrollment_number,
                "name": name,
                "email": email,
                "mobile_number": mobile,
                "fees": fees,
                "section": section.upper(),
                "semester": semester_int,
                "branch": branch.upper()
            }

            # Check if student already exists
            existing = supabase.table("students").select("*").eq("enrollment_number", enrollment_number).execute()

            if existing.data:
                # Update existing student
                print(f"Student already exists, updating record...")
                result = supabase.table("students").update(student_data).eq("enrollment_number", enrollment_number).execute()
                student = result.data[0] if result.data else None
            else:
                # Insert new student
                result = supabase.table("students").insert(student_data).execute()
                student = result.data[0] if result.data else None

        except Exception as db_error:
            print(f"Database error: {db_error}")
            raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
        
        if not student:
            print("ERROR: Failed to create student record")
            raise HTTPException(status_code=400, detail="Failed to create student record. Check server logs for details.")
        
        print(f"Student created successfully: {student}")
        
        # Create folder structure: enrollmentNumber_branch_year_section
        folder_name = f"{enrollment_number}_{branch}_{year}_{section}"
        print(f"Uploading images to folder: {folder_name}")
        
        # Upload images to Cloudinary
        uploaded_files = []
        for idx, image in enumerate(images):
            print(f"Processing image {idx + 1}/{len(images)}...")
            # Read image data
            image_data = await image.read()
            
            # Upload to Cloudinary
            result = upload_to_cloudinary(
                image_data=image_data,
                folder=folder_name,
                filename=f"image_{idx}"
            )
            
            if result:
                print(f"Image {idx + 1} uploaded: {result['url']}")
                # Store file record in database
                file_record = store_file_record(
                    enrollment_number=enrollment_number,
                    file_type="face_image",
                    file_url=result['url'],
                    folder_path=folder_name
                )
                uploaded_files.append(result['url'])
            else:
                print(f"WARNING: Failed to upload image {idx + 1}")
        
        print(f"Successfully uploaded {len(uploaded_files)} images")
        
        return {
            "success": True,
            "message": "Student registered successfully",
            "student": student,
            "images_uploaded": len(uploaded_files),
            "folder": folder_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n=== Registration Error ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/register/teacher")
async def register_teacher(
    name: str = Form(...),
    teacher_id: str = Form(...),
    phone: str = Form(None),
    email: str = Form(None),
    salary: str = Form(None),
    images: List[UploadFile] = File(...)
):
    """Register a new teacher with face images"""
    try:
        print(f"\n=== Teacher Registration Request ===")
        print(f"Name: {name}")
        print(f"Teacher ID: {teacher_id}")
        print(f"Phone: {phone}")
        print(f"Email: {email}")
        print(f"Salary: {salary}")
        print(f"Images count: {len(images)}")

        if len(images) < 5:
            raise HTTPException(status_code=400, detail="Minimum 5 images required")

        from db import supabase, store_teacher_file

        # Prepare teacher data
        teacher_data = {
            "teacher_id": teacher_id,
            "teacher_name": name,
            "phone_number": phone,
            "email": email,
            "salary": salary
        }

        teacher = None

        # Check if teacher exists by teacher_id
        existing_by_id = supabase.table("teachers").select("*").eq("teacher_id", teacher_id).execute()

        if existing_by_id and existing_by_id.data:
            # Teacher exists - UPDATE
            print(f"Teacher {teacher_id} exists, overwriting data...")
            try:
                result = supabase.table("teachers").update(teacher_data).eq("teacher_id", teacher_id).execute()
                teacher = result.data[0] if result.data else None
                print(f"Teacher updated: {teacher}")
            except Exception as update_error:
                print(f"Update error: {update_error}")
                raise HTTPException(status_code=400, detail=f"Failed to update teacher: {str(update_error)}")
        else:
            # Check if email exists with different teacher_id
            if email:
                existing_by_email = supabase.table("teachers").select("*").eq("email", email).execute()

                if existing_by_email and existing_by_email.data:
                    existing_teacher = existing_by_email.data[0]
                    old_teacher_id = existing_teacher.get('teacher_id')

                    if old_teacher_id != teacher_id:
                        # Email exists with different teacher_id - UPDATE that record with new teacher_id
                        print(f"Email exists with teacher ID {old_teacher_id}, updating to new ID {teacher_id}...")
                        try:
                            result = supabase.table("teachers").update(teacher_data).eq("email", email).execute()
                            teacher = result.data[0] if result.data else None
                            print(f"Teacher updated: {teacher}")
                        except Exception as update_error:
                            print(f"Update error: {update_error}")
                            raise HTTPException(status_code=400, detail=f"Failed to update teacher: {str(update_error)}")
                    else:
                        # Same teacher_id and email - UPDATE
                        result = supabase.table("teachers").update(teacher_data).eq("teacher_id", teacher_id).execute()
                        teacher = result.data[0] if result.data else None
                else:
                    # New teacher - INSERT
                    print(f"Creating new teacher {teacher_id}...")
                    try:
                        result = supabase.table("teachers").insert(teacher_data).execute()
                        teacher = result.data[0] if result.data else None
                        print(f"Teacher created: {teacher}")
                    except Exception as insert_error:
                        print(f"Insert error: {insert_error}")
                        raise HTTPException(status_code=400, detail=f"Failed to create teacher: {str(insert_error)}")
            else:
                # No email provided - INSERT new teacher
                print(f"Creating new teacher {teacher_id}...")
                try:
                    result = supabase.table("teachers").insert(teacher_data).execute()
                    teacher = result.data[0] if result.data else None
                    print(f"Teacher created: {teacher}")
                except Exception as insert_error:
                    print(f"Insert error: {insert_error}")
                    raise HTTPException(status_code=400, detail=f"Failed to create teacher: {str(insert_error)}")

        if not teacher:
            raise HTTPException(status_code=400, detail="Failed to create or update teacher record")

        print(f"Teacher record ready: {teacher}")

        # Delete old images for this teacher (to overwrite)
        print(f"Deleting old images for teacher {teacher_id}...")
        try:
            supabase.table("teacher_files").delete().eq("teacher_id", teacher_id).execute()
            print("Old images deleted")
        except Exception as delete_error:
            print(f"Warning: Could not delete old images: {delete_error}")

        # Upload new images
        folder_name = f"teacher_{teacher_id}"
        uploaded_files = []

        for idx, image in enumerate(images):
            print(f"Processing image {idx + 1}/{len(images)}...")
            image_data = await image.read()

            result = upload_to_cloudinary(
                image_data=image_data,
                folder=folder_name,
                filename=f"image_{idx}"
            )

            if result:
                print(f"Image {idx + 1} uploaded: {result['url']}")
                # Store in teacher_files table
                file_record = store_teacher_file(
                    teacher_id=teacher_id,
                    file_type="teacher_face_image",
                    file_url=result['url'],
                    folder_path=folder_name
                )
                uploaded_files.append(result['url'])
            else:
                print(f"WARNING: Failed to upload image {idx + 1}")

        print(f"Successfully uploaded {len(uploaded_files)} images")

        return {
            "success": True,
            "message": "Teacher registered successfully",
            "teacher": teacher,
            "images_uploaded": len(uploaded_files),
            "folder": folder_name
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"\n=== Teacher Registration Error ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/register/guest")
async def register_guest(
    name: str = Form(...),
    duration: int = Form(...),
    images: List[UploadFile] = File(...)
):
    """Register a new guest with face images and auto-generate token"""
    try:
        if len(images) < 5:
            raise HTTPException(status_code=400, detail="Minimum 5 images required")
        
        # Generate unique guest token
        guest_token = generate_guest_token()
        
        guest = create_guest(
            guest_token=guest_token,
            name=name,
            duration=duration
        )
        
        if not guest:
            raise HTTPException(status_code=400, detail="Failed to create guest record")
        
        folder_name = f"guest_{guest_token}"
        
        uploaded_files = []
        for idx, image in enumerate(images):
            image_data = await image.read()
            result = upload_to_cloudinary(
                image_data=image_data,
                folder=folder_name,
                filename=f"image_{idx}"
            )
            
            if result:
                store_file_record(
                    enrollment_number=guest_token,
                    file_type="guest_face_image",
                    file_url=result['url'],
                    folder_path=folder_name
                )
                uploaded_files.append(result['url'])
        
        return {
            "success": True,
            "message": "Guest registered successfully",
            "guest": guest,
            "guest_token": guest_token,
            "images_uploaded": len(uploaded_files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# TRAINING ENDPOINTS
# =====================================================

@app.post("/train")
async def train_model(
    section: str = Form(''),  # Default to empty string
    year: str = Form('')      # Default to empty string
):
    """Train face recognition model for a specific section and year, or all teachers"""
    try:
        # Debug logging
        print(f"Received training request:")
        print(f"  Section: '{section}'")
        print(f"  Year: '{year}'")

        # Check if this is teacher training (empty section and year)
        if not section or not year or section.strip() == '' or year.strip() == '':
            print("=== TEACHER TRAINING MODE ===")
            print("Empty section/year detected - training teacher model")
        else:
            print(f"=== STUDENT TRAINING MODE ===")
            print(f"Training for section={section}, year={year}")

        # Call train function (it will detect empty strings and route accordingly)
        result = train_face_model(section=section, year=year)

        if result:
            # Check if this was teacher or student training
            entity_type = "teachers" if result.get('teachers_count') else "students"
            count = result.get('teachers_count', result.get('students_count', 0))

            if entity_type == "teachers":
                message = f"Teacher model trained successfully"
            else:
                message = f"Model trained successfully for {section} - Year {year}"

            return {
                "success": True,
                "message": message,
                "model_path": result.get('model_path'),
                f"{entity_type}_trained": count,
                "encodings_count": result.get('encodings_count', 0)
            }
        else:
            # Determine error message based on training type
            if not section or not year or section.strip() == '' or year.strip() == '':
                error_msg = "Teacher model training failed. Check if teachers with images exist."
            else:
                error_msg = f"Model training failed. Check if students with images exist for section {section}, year {year}."

            raise HTTPException(
                status_code=500,
                detail=error_msg
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Training error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# TESTING/RECOGNITION ENDPOINTS
# =====================================================

@app.post("/test")
async def test_recognition(
    image: UploadFile = File(...),
    section: str = Form(''),  # Changed from Form(...) to Form('')
    year: str = Form('')      # Changed from Form(...) to Form('')
):
    """Test face recognition on an image"""
    try:
        print(f"\n=== Recognition Request ===")
        print(f"Section: '{section}'")
        print(f"Year: '{year}'")
        
        # Read image data
        image_data = await image.read()
        
        # Perform face recognition
        result = recognize_face(
            image_data=image_data,
            section=section,
            year=year
        )
        
        print(f"Recognition result: {result.get('name', 'Unknown')} - {result.get('role', 'unknown')}")
        
        return result

    except Exception as e:
        print(f"Recognition error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test-multiple")
async def test_multiple_recognition(
    image: UploadFile = File(...),
    section: str = Form(''),  # Changed from Form(...) to Form('')
    year: str = Form('')      # Changed from Form(...) to Form('')
):
    """Test face recognition for multiple faces in an image"""
    try:
        print(f"\n=== Multiple Recognition Request ===")
        print(f"Section: '{section}'")
        print(f"Year: '{year}'")
        
        # Read image data
        image_data = await image.read()

        # Perform multi-face recognition
        results = recognize_multiple_faces(
            image_data=image_data,
            section=section,
            year=year
        )

        return {
            "success": True,
            "faces_detected": len(results),
            "faces": results
        }

    except Exception as e:
        print(f"Multiple recognition error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ATTENDANCE SESSION ENDPOINTS
# =====================================================

@app.post("/attendance/start-session")
async def start_attendance(
    teacher_id: str = Form(...),
    subject_id: int = Form(...),
    section: str = Form(...),
    semester: int = Form(...),
    class_name: str = Form(...),
    duration_minutes: int = Form(60)
):
    """
    Start a new attendance session
    Automatically marks all students as absent
    """
    try:
        print(f"\n=== API: Starting Attendance ===")
        print(f"Received: teacher_id={teacher_id}, subject_id={subject_id}, section={section}, semester={semester}")
        
        session = start_attendance_session(
            teacher_id=teacher_id,
            subject_id=subject_id,
            section=section,
            semester=semester,
            class_name=class_name,
            duration_minutes=duration_minutes
        )
        
        if session:
            return {
                "success": True,
                "message": "Attendance session started. All students marked as absent.",
                "session": session
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to start session - no session returned")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n=== ERROR in start_attendance endpoint ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/attendance/active-session")
async def get_active_attendance_session(
    section: str,
    semester: int,
    subject_id: Optional[int] = None
):
    """
    Get the active attendance session for a section
    """
    try:
        session = get_active_session(section, semester, subject_id)
        
        if session:
            # Get attendance records
            records = get_session_attendance(session['session_id'])
            
            return {
                "success": True,
                "session": session,
                "attendance_records": records
            }
        else:
            return {
                "success": False,
                "message": "No active session found"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/end-session")
async def end_attendance(
    session_id: str = Form(...)
):
    """
    End an active attendance session
    """
    try:
        success = end_attendance_session(session_id)
        
        if success:
            return {
                "success": True,
                "message": "Attendance session ended"
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to end session")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ATTENDANCE MARKING ENDPOINTS
# =====================================================

@app.post("/attendance/mark-present")
async def mark_attendance_present(
    session_id: str = Form(...),
    enrollment_number: str = Form(...),
    confidence: float = Form(0.0),
    marked_by: str = Form("system")
):
    """
    Mark a student as present in an active session
    """
    try:
        record = mark_student_present(
            session_id=session_id,
            enrollment_number=enrollment_number,
            confidence=confidence,
            marked_by=marked_by
        )
        
        if record:
            return {
                "success": True,
                "message": f"Student {enrollment_number} marked present",
                "record": record
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to mark attendance")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/mark-absent")
async def mark_attendance_absent(
    session_id: str = Form(...),
    enrollment_number: str = Form(...)
):
    """
    Manually mark a student as absent (teacher override)
    """
    try:
        record = mark_student_absent(session_id, enrollment_number)
        
        if record:
            return {
                "success": True,
                "message": f"Student {enrollment_number} marked absent",
                "record": record
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to mark attendance")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# LIVE ATTENDANCE WITH FACE RECOGNITION
# =====================================================

@app.post("/attendance/recognize-and-mark")
async def recognize_and_mark_attendance(
    image: UploadFile = File(...),
    section: str = Form(...),
    year: str = Form(...)
):
    """
    Recognize face and automatically mark attendance
    Combines face recognition with attendance marking
    """
    try:
        # Get active session
        session = get_active_session(section, int(year))
        
        if not session:
            return {
                "success": False,
                "message": "No active attendance session. Teacher must start attendance first."
            }
        
        # Read image data
        image_data = await image.read()
        
        # Perform face recognition
        recognition_result = recognize_face(
            image_data=image_data,
            section=section,
            year=year
        )
        
        # If face recognized, mark attendance
        if recognition_result.get('name') != 'Unknown':
            enrollment_number = recognition_result.get('id')
            confidence = recognition_result.get('confidence', 0.0)
            
            # Mark student present
            attendance_record = mark_student_present(
                session_id=session['session_id'],
                enrollment_number=enrollment_number,
                confidence=confidence,
                marked_by="system"
            )
            
            if attendance_record:
                return {
                    "success": True,
                    "message": f"Attendance marked for {recognition_result.get('name')}",
                    "recognition": recognition_result,
                    "attendance": attendance_record,
                    "status": attendance_record.get('status')  # 'present' or 'late'
                }
        
        return {
            "success": False,
            "message": "Face not recognized or not in database",
            "recognition": recognition_result
        }
        
    except Exception as e:
        print(f"Error in recognize and mark: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/recognize-multiple-and-mark")
async def recognize_multiple_and_mark_attendance(
    image: UploadFile = File(...),
    section: str = Form(...),
    year: str = Form(...)
):
    """
    Recognize multiple faces and mark attendance for all
    Useful for group photos or batch attendance
    """
    try:
        # Get active session
        session = get_active_session(section, int(year))
        
        if not session:
            return {
                "success": False,
                "message": "No active attendance session"
            }
        
        # Read image data
        image_data = await image.read()
        
        # Recognize all faces
        recognition_results = recognize_multiple_faces(
            image_data=image_data,
            section=section,
            year=year
        )
        
        marked_students = []
        
        # Mark attendance for each recognized face
        for result in recognition_results:
            if result.get('name') != 'Unknown':
                enrollment_number = result.get('id')
                confidence = result.get('confidence', 0.0)
                
                attendance_record = mark_student_present(
                    session_id=session['session_id'],
                    enrollment_number=enrollment_number,
                    confidence=confidence,
                    marked_by="system"
                )
                
                if attendance_record:
                    marked_students.append({
                        "name": result.get('name'),
                        "enrollment_number": enrollment_number,
                        "status": attendance_record.get('status'),
                        "confidence": confidence
                    })
        
        return {
            "success": True,
            "faces_detected": len(recognition_results),
            "students_marked": len(marked_students),
            "marked_students": marked_students
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# ATTENDANCE QUERY ENDPOINTS
# =====================================================

@app.get("/attendance/session/{session_id}")
async def get_session_attendance_records(session_id: str):
    """
    Get all attendance records for a specific session
    """
    try:
        records = get_session_attendance(session_id)
        
        return {
            "success": True,
            "count": len(records),
            "records": records
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/attendance/student/{enrollment_number}")
async def get_student_attendance(
    enrollment_number: str,
    subject_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get attendance history for a student
    """
    try:
        records = get_student_attendance_history(
            enrollment_number=enrollment_number,
            subject_id=subject_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate statistics
        total = len(records)
        present = sum(1 for r in records if r['status'] in ['present', 'late'])
        absent = sum(1 for r in records if r['status'] == 'absent')
        percentage = round(present / total * 100, 2) if total > 0 else 0.0
        
        return {
            "success": True,
            "enrollment_number": enrollment_number,
            "statistics": {
                "total_classes": total,
                "present": present,
                "absent": absent,
                "percentage": percentage
            },
            "records": records
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/attendance/subject-stats")
async def get_subject_stats(
    section: str,
    semester: int,
    subject_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get attendance statistics for a subject
    """
    try:
        stats = get_subject_attendance_stats(
            section=section,
            semester=semester,
            subject_id=subject_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "success": True,
            "section": section,
            "semester": semester,
            "subject_id": subject_id,
            "statistics": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/attendance/daily-report")
async def get_daily_report(
    date: str,
    section: Optional[str] = None
):
    """
    Get attendance report for a specific date
    """
    try:
        report = get_daily_attendance_report(date, section)
        
        return {
            "success": True,
            "date": date,
            "section": section,
            "sessions": report
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/attendance/low-attendance")
async def get_low_attendance_list(
    section: str,
    semester: int,
    subject_id: int,
    threshold: float = 75.0
):
    """
    Get students with attendance below threshold
    """
    try:
        students = get_low_attendance_students(
            section=section,
            semester=semester,
            subject_id=subject_id,
            threshold=threshold
        )
        
        return {
            "success": True,
            "threshold": threshold,
            "count": len(students),
            "students": students
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/attendance/update-summary")
async def update_summary(
    enrollment_number: str = Form(...),
    subject_id: int = Form(...),
    semester: int = Form(...)
):
    """
    Manually trigger attendance summary update for a student
    """
    try:
        update_attendance_summary(enrollment_number, subject_id, semester)
        
        return {
            "success": True,
            "message": "Attendance summary updated"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# DEBUG ENDPOINTS
# =====================================================

@app.get("/debug/students")
async def debug_students(section: str = None, year: str = None):
    """Debug endpoint to check students in database"""
    try:
        from db import get_all_students, get_students_by_section_year
        
        if section and year:
            students = get_students_by_section_year(section, year)
            return {
                "section": section,
                "year": year,
                "count": len(students),
                "students": students
            }
        else:
            students = get_all_students()
            return {
                "total_count": len(students),
                "students": students
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/teachers")
async def debug_teachers():
    """Debug endpoint to check teachers in database"""
    try:
        from db import get_all_teachers
        
        teachers = get_all_teachers()
        return {
            "total_count": len(teachers),
            "teachers": teachers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/files")
async def debug_files(section: str = None, year: str = None):
    """Debug endpoint to check files in database"""
    try:
        from db import get_images_by_section_year
        
        if section and year:
            images = get_images_by_section_year(section, year)
            return {
                "section": section,
                "year": year,
                "count": len(images),
                "images": images
            }
        else:
            return {"error": "Please provide section and year parameters"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/attendance-sessions")
async def debug_attendance_sessions(section: str = None, semester: int = None):
    """Debug endpoint to check attendance sessions"""
    try:
        from db import supabase
        
        query = supabase.table("attendance_sessions").select("*")
        
        if section:
            query = query.eq("section", section.upper())
        
        if semester:
            query = query.eq("semester", semester)
        
        result = query.order("start_time", desc=True).execute()
        
        return {
            "success": True,
            "count": len(result.data) if result.data else 0,
            "sessions": result.data if result.data else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/subjects")
async def debug_subjects():
    """Debug endpoint to check subjects in database"""
    try:
        from db import supabase
        
        result = supabase.table("subjects").select("*").execute()
        
        return {
            "success": True,
            "count": len(result.data) if result.data else 0,
            "subjects": result.data if result.data else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        from db import health_check as db_health_check
        
        db_status = db_health_check()
        
        return {
            "status": "healthy" if db_status else "unhealthy",
            "database": "connected" if db_status else "disconnected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)