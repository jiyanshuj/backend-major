import os
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional, Dict, List
import requests

load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ensure_bucket_exists(bucket_name: str, public: bool = True) -> bool:
    """
    Ensure a storage bucket exists

    Args:
        bucket_name: Name of the bucket
        public: Whether the bucket should be public

    Returns:
        True if bucket exists or can be accessed, False otherwise
    """
    try:
        # Try to list buckets
        buckets = supabase.storage.list_buckets()
        print(f"Available buckets: {[b.get('name', b.get('id')) for b in buckets]}")

        # Check if bucket exists
        bucket_exists = any(bucket.get('name') == bucket_name or bucket.get('id') == bucket_name for bucket in buckets)

        if bucket_exists:
            print(f"Bucket '{bucket_name}' exists and is ready")
            return True

        # If not found in list, try to access it directly (it might exist but not be listed)
        print(f"Bucket not found in list, attempting direct access...")
        try:
            # Try to list files in the bucket (will fail if bucket doesn't exist)
            supabase.storage.from_(bucket_name).list()
            print(f"Bucket '{bucket_name}' is accessible!")
            return True
        except Exception as access_error:
            print(f"Cannot access bucket: {access_error}")

        print(f"Bucket '{bucket_name}' does not exist or is not accessible!")
        print(f"Please verify in Supabase Dashboard:")
        print(f"1. Go to Storage section")
        print(f"2. Check if bucket '{bucket_name}' exists")
        print(f"3. Make sure it's Public")
        print(f"4. Check RLS policies allow access")
        return False

    except Exception as e:
        print(f"Error checking bucket: {e}")
        # Even if listing fails, try to use the bucket anyway
        print(f"Assuming bucket exists and proceeding...")
        return True

def upload_to_supabase_storage(file_data: bytes, bucket: str, path: str) -> Optional[str]:
    """
    Upload file to Supabase Storage
    
    Args:
        file_data: File bytes
        bucket: Bucket name
        path: File path in bucket
        
    Returns:
        Public URL or None
    """
    try:
        # Check if bucket exists (don't try to create)
        if not ensure_bucket_exists(bucket, public=True):
            print(f"Bucket does not exist: {bucket}")
            print(f"Please create it manually in Supabase Dashboard")
            return None
        
        # Upload file with upsert option
        try:
            result = supabase.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options={"content-type": "application/octet-stream", "upsert": True}
            )
            print(f"Upload result: {result}")
        except Exception as upload_error:
            # If file exists, try to update it
            print(f"Upload error: {upload_error}")
            print(f"Attempting to update existing file...")
            
            # Delete existing file first
            try:
                supabase.storage.from_(bucket).remove([path])
                print(f"Deleted existing file: {path}")
            except:
                pass
            
            # Try upload again
            result = supabase.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options={"content-type": "application/octet-stream"}
            )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket).get_public_url(path)
        
        print(f"File uploaded successfully to: {public_url}")
        return public_url
        
    except Exception as e:
        print(f"Error uploading to Supabase Storage: {e}")
        import traceback
        traceback.print_exc()
        return None

def download_from_supabase_storage(bucket: str, path: str) -> Optional[bytes]:
    """
    Download file from Supabase Storage
    
    Args:
        bucket: Bucket name
        path: File path in bucket
        
    Returns:
        File bytes or None
    """
    try:
        result = supabase.storage.from_(bucket).download(path)
        return result
    except Exception as e:
        print(f"Error downloading from Supabase Storage: {e}")
        return None

def download_from_url(url: str) -> Optional[bytes]:
    """
    Download file from a URL
    
    Args:
        url: File URL
        
    Returns:
        File bytes or None
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading from URL: {e}")
        return None

# Student Functions
def create_student(enrollment_number: str, name: str, section: str, year: str, 
                  email: str = None, mobile_number: str = None, fees: str = None, 
                  branch: str = "CS") -> Optional[Dict]:
    """Create a new student record"""
    try:
        # Generate email if not provided
        if not email:
            email = f"{enrollment_number}@student.edu"
        
        data = {
            "enrollment_number": enrollment_number,
            "name": name,
            "email": email,
            "mobile_number": mobile_number,      # NEW FIELD
            "fees": fees,                        # NEW FIELD
            "section": section.upper(),
            "semester": int(year),
            "branch": branch.upper()
        }
        
        result = supabase.table("students").insert(data).execute()
        print(f"Student created: {result.data[0] if result.data else 'Failed'}")
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error creating student: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_student(enrollment_number: str) -> Optional[Dict]:
    """Get student by enrollment number"""
    try:
        result = supabase.table("students").select("*").eq("enrollment_number", enrollment_number).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting student: {e}")
        return None

def get_students_by_section_year(section: str, year: str) -> List[Dict]:
    """Get all students in a section and year"""
    try:
        # Make section case-insensitive by converting to uppercase
        section_upper = section.upper()
        
        # First try with uppercase section
        result = supabase.table("students").select("*").eq("section", section_upper).eq("semester", int(year)).execute()
        
        # If no results, try with original case
        if not result.data or len(result.data) == 0:
            result = supabase.table("students").select("*").eq("section", section).eq("semester", int(year)).execute()
        
        print(f"Found {len(result.data) if result.data else 0} students for section={section}, year={year}")
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting students: {e}")
        import traceback
        traceback.print_exc()
        return []

def update_student(enrollment_number: str, data: Dict) -> Optional[Dict]:
    """Update student record"""
    try:
        result = supabase.table("students").update(data).eq("enrollment_number", enrollment_number).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error updating student: {e}")
        return None

def delete_student(enrollment_number: str) -> bool:
    """Delete student record"""
    try:
        supabase.table("students").delete().eq("enrollment_number", enrollment_number).execute()
        return True
    except Exception as e:
        print(f"Error deleting student: {e}")
        return False

def get_all_students() -> List[Dict]:
    """Get all students"""
    try:
        result = supabase.table("students").select("*").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting all students: {e}")
        return []

# Teacher Functions
def create_teacher(teacher_id: str, name: str, phone: str = None,
                  email: str = None, salary: str = None) -> Optional[Dict]:
    """Create a new teacher record"""
    try:
        data = {
            "teacher_id": teacher_id,
            "teacher_name": name,  # Column name is teacher_name, not name
            "phone_number": phone,  # Column name is phone_number, not phone
            "email": email,
            "salary": salary
        }
        
        result = supabase.table("teachers").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error creating teacher: {e}")
        return None

def get_teacher(teacher_id: str) -> Optional[Dict]:
    """Get teacher by teacher ID"""
    try:
        result = supabase.table("teachers").select("*").eq("teacher_id", teacher_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting teacher: {e}")
        return None

def get_all_teachers() -> List[Dict]:
    """Get all teachers"""
    try:
        result = supabase.table("teachers").select("*").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting all teachers: {e}")
        return []

def update_teacher(teacher_id: str, data: Dict) -> Optional[Dict]:
    """Update teacher record"""
    try:
        result = supabase.table("teachers").update(data).eq("teacher_id", teacher_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error updating teacher: {e}")
        return None

def delete_teacher(teacher_id: str) -> bool:
    """Delete teacher record"""
    try:
        supabase.table("teachers").delete().eq("teacher_id", teacher_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting teacher: {e}")
        return False

# Guest Functions
def create_guest(guest_token: str, name: str, duration: int) -> Optional[Dict]:
    """Create a new guest record"""
    try:
        data = {
            "guest_token": guest_token,
            "name": name,
            "duration": duration
        }
        
        result = supabase.table("guests").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error creating guest: {e}")
        return None

def get_guest(guest_token: str) -> Optional[Dict]:
    """Get guest by token"""
    try:
        result = supabase.table("guests").select("*").eq("guest_token", guest_token).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting guest: {e}")
        return None

def get_all_guests() -> List[Dict]:
    """Get all guests"""
    try:
        result = supabase.table("guests").select("*").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting all guests: {e}")
        return []

def update_guest(guest_token: str, data: Dict) -> Optional[Dict]:
    """Update guest record"""
    try:
        result = supabase.table("guests").update(data).eq("guest_token", guest_token).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error updating guest: {e}")
        return None

def delete_guest(guest_token: str) -> bool:
    """Delete guest record"""
    try:
        supabase.table("guests").delete().eq("guest_token", guest_token).execute()
        return True
    except Exception as e:
        print(f"Error deleting guest: {e}")
        return False

# File Storage Functions
def store_file_record(enrollment_number: str, file_type: str, file_url: str, folder_path: str) -> Optional[Dict]:
    """Store file record in database"""
    try:
        data = {
            "enrollment_number": enrollment_number,
            "file_type": file_type,
            "file_url": file_url,
            "folder_path": folder_path
        }
        
        result = supabase.table("files").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing file record: {e}")
        return None

def store_teacher_file(teacher_id: str, file_type: str, file_url: str, folder_path: str) -> Optional[Dict]:
    """Store teacher file record in teacher_files table"""
    try:
        data = {
            "teacher_id": teacher_id,
            "file_type": file_type,
            "file_url": file_url,
            "folder_path": folder_path
        }

        result = supabase.table("teacher_files").insert(data).execute()
        print(f"Teacher file record stored: {result.data[0] if result.data else 'Failed'}")
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing teacher file record: {e}")
        return None

def store_guest_file(guest_token: str, file_type: str, file_url: str, folder_path: str) -> Optional[Dict]:
    """Store guest file record in guest_files table"""
    try:
        data = {
            "guest_token": guest_token,
            "file_type": file_type,
            "file_url": file_url,
            "folder_path": folder_path
        }

        result = supabase.table("guest_files").insert(data).execute()
        print(f"Guest file record stored: {result.data[0] if result.data else 'Failed'}")
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing guest file record: {e}")
        return None

def get_teacher_images(teacher_id: str) -> List[str]:
    """Get all image URLs for a teacher"""
    try:
        result = supabase.table("teacher_files").select("file_url").eq("teacher_id", teacher_id).execute()
        return [record['file_url'] for record in result.data] if result.data else []
    except Exception as e:
        print(f"Error getting teacher images: {e}")
        return []

def get_all_teacher_images() -> List[Dict]:
    """
    Get all teacher images with metadata
    Returns list of dicts with file_url, teacher_name, teacher_id
    """
    try:
        print(f"\n=== Getting all teacher images ===")

        # Get all teachers first
        teachers = get_all_teachers()

        if not teachers:
            print("No teachers found")
            return []

        print(f"Found {len(teachers)} teachers")

        # Get all teacher files with teacher info
        all_images = []

        for teacher in teachers:
            teacher_id = teacher['teacher_id']
            teacher_name = teacher['teacher_name']

            print(f"Getting files for {teacher_name} ({teacher_id})")

            # Get files for this teacher
            result = supabase.table("teacher_files").select("*").eq("teacher_id", teacher_id).execute()

            if result.data:
                print(f"  Found {len(result.data)} files")
                for file_record in result.data:
                    all_images.append({
                        'file_url': file_record['file_url'],
                        'teacher_name': teacher_name,
                        'teacher_id': teacher_id
                    })
            else:
                print(f"  No files found")

        print(f"Total teacher images found: {len(all_images)}")
        return all_images

    except Exception as e:
        print(f"Error getting all teacher images: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_guest_images(guest_token: str) -> List[str]:
    """Get all image URLs for a guest"""
    try:
        result = supabase.table("guest_files").select("file_url").eq("guest_token", guest_token).execute()
        return [record['file_url'] for record in result.data] if result.data else []
    except Exception as e:
        print(f"Error getting guest images: {e}")
        return []

def get_student_images(enrollment_number: str) -> List[str]:
    """Get all image URLs for a student"""
    try:
        result = supabase.table("files").select("file_url").eq("enrollment_number", enrollment_number).execute()
        return [record['file_url'] for record in result.data] if result.data else []
    except Exception as e:
        print(f"Error getting student images: {e}")
        return []

def get_files_by_enrollment(enrollment_number: str) -> List[Dict]:
    """Get all files for a specific enrollment number"""
    try:
        result = supabase.table("files").select("*").eq("enrollment_number", enrollment_number).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting files: {e}")
        return []

def get_images_by_section_year(section: str, year: str) -> List[Dict]:
    """
    Get all images for students in a specific section and year
    Joins files table with students table
    """
    try:
        print(f"\n=== Getting images for section={section}, year={year} ===")
        
        # Get all students in this section/year
        students = get_students_by_section_year(section, year)
        
        if not students:
            print(f"No students found for section {section}, year {year}")
            return []
        
        print(f"Found {len(students)} students")
        enrollment_numbers = [s['enrollment_number'] for s in students]
        print(f"Enrollment numbers: {enrollment_numbers}")
        
        # Get all files for these students
        all_images = []
        
        for enrollment in enrollment_numbers:
            # Get student info
            student = next((s for s in students if s['enrollment_number'] == enrollment), None)
            
            if not student:
                continue
            
            print(f"Getting files for {student['name']} ({enrollment})")
            
            # Get files for this student
            result = supabase.table("files").select("*").eq("enrollment_number", enrollment).execute()
            
            if result.data:
                print(f"  Found {len(result.data)} files")
                for file_record in result.data:
                    all_images.append({
                        'file_url': file_record['file_url'],
                        'student_name': student['name'],
                        'student_enrollment': enrollment,
                        'section': section,
                        'year': year
                    })
            else:
                print(f"  No files found")
        
        print(f"Total images found: {len(all_images)}")
        return all_images
        
    except Exception as e:
        print(f"Error getting images by section/year: {e}")
        import traceback
        traceback.print_exc()
        return []

def delete_file_record(file_id: int) -> bool:
    """Delete file record from database"""
    try:
        supabase.table("files").delete().eq("id", file_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting file record: {e}")
        return False

def delete_files_by_enrollment(enrollment_number: str) -> bool:
    """Delete all files for a specific enrollment number"""
    try:
        supabase.table("files").delete().eq("enrollment_number", enrollment_number).execute()
        return True
    except Exception as e:
        print(f"Error deleting files: {e}")
        return False

# Model Storage Functions
def store_model_metadata(section: str, year: str, model_path: str, students_count: int) -> Optional[Dict]:
    """Store model metadata in database"""
    try:
        data = {
            "section": section,
            "year": int(year),
            "model_path": model_path,
            "students_count": students_count
        }
        
        # Check if model already exists
        existing = supabase.table("models").select("*").eq("section", section).eq("year", int(year)).execute()
        
        if existing.data:
            # Update existing
            result = supabase.table("models").update(data).eq("section", section).eq("year", int(year)).execute()
        else:
            # Insert new
            result = supabase.table("models").insert(data).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error storing model metadata: {e}")
        return None

def get_model_path(section: str, year: str) -> Optional[str]:
    """Get model path for a specific section and year"""
    try:
        result = supabase.table("models").select("model_path").eq("section", section).eq("year", int(year)).execute()
        return result.data[0]['model_path'] if result.data else None
    except Exception as e:
        print(f"Error getting model path: {e}")
        return None

def get_model_metadata(section: str, year: str) -> Optional[Dict]:
    """Get complete model metadata for a specific section and year"""
    try:
        result = supabase.table("models").select("*").eq("section", section).eq("year", int(year)).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error getting model metadata: {e}")
        return None

def get_all_models() -> List[Dict]:
    """Get all trained models"""
    try:
        result = supabase.table("models").select("*").execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting all models: {e}")
        return []

def delete_model_metadata(section: str, year: str) -> bool:
    """Delete model metadata"""
    try:
        supabase.table("models").delete().eq("section", section).eq("year", int(year)).execute()
        return True
    except Exception as e:
        print(f"Error deleting model metadata: {e}")
        return False

# Attendance Functions
def mark_attendance(enrollment_number: str, status: str = "present") -> Optional[Dict]:
    """Mark attendance for a student"""
    try:
        data = {
            "enrollment_number": enrollment_number,
            "status": status
        }
        
        result = supabase.table("attendance").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Error marking attendance: {e}")
        return None

def get_attendance_by_date(date: str) -> List[Dict]:
    """Get attendance records for a specific date"""
    try:
        result = supabase.table("attendance").select("*").eq("date", date).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting attendance: {e}")
        return []

def get_student_attendance(enrollment_number: str) -> List[Dict]:
    """Get all attendance records for a student"""
    try:
        result = supabase.table("attendance").select("*").eq("enrollment_number", enrollment_number).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting student attendance: {e}")
        return []

# Utility Functions
def health_check() -> bool:
    """Check if database connection is working"""
    try:
        result = supabase.table("students").select("count").execute()
        return True
    except Exception as e:
        print(f"Database health check failed: {e}")
        return False