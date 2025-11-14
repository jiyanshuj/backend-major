import os
import pickle
import face_recognition
import numpy as np
from typing import List, Dict, Optional
import io
from PIL import Image

from db import (
    get_students_by_section_year,
    get_images_by_section_year,
    get_all_teachers,
    get_all_teacher_images,
    upload_to_supabase_storage,
    store_model_metadata,
    supabase
)
from capture import download_from_url

def load_image_from_url(url: str) -> Optional[np.ndarray]:
    """
    Load image from URL and convert to numpy array for face_recognition
    
    Args:
        url: Image URL
        
    Returns:
        Image as numpy array or None
    """
    try:
        # Download image
        image_data = download_from_url(url)
        
        if not image_data:
            return None
        
        # Convert to PIL Image
        pil_image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array
        image_array = np.array(pil_image)
        
        return image_array
        
    except Exception as e:
        print(f"Error loading image from URL: {e}")
        return None

def extract_face_encodings(image_url: str, num_jitters: int = 5) -> List[np.ndarray]:
    """
    Extract face encodings from an image URL with balanced accuracy and speed
    
    Args:
        image_url: URL of the image
        num_jitters: Number of times to re-sample face (5 = good balance)
        
    Returns:
        List of face encodings (128-dimensional vectors)
    """
    try:
        # Load image
        image = load_image_from_url(image_url)
        
        if image is None:
            return []
        
        # Find face locations using HOG (much faster than CNN)
        face_locations = face_recognition.face_locations(image, model="hog", number_of_times_to_upsample=1)
        
        if not face_locations:
            print(f"No faces found in image: {image_url}")
            return []
        
        # Extract face encodings with balanced quality
        # num_jitters=5: Good balance between speed and accuracy
        encodings = face_recognition.face_encodings(image, face_locations, num_jitters=num_jitters)
        
        print(f"Extracted {len(encodings)} face encoding(s) from image")
        
        return encodings
        
    except Exception as e:
        print(f"Error extracting face encodings: {e}")
        return []

def train_teacher_face_model() -> Optional[Dict]:
    """
    Train face recognition model for ALL teachers
    
    Returns:
        Dictionary with training results
    """
    try:
        print(f"\n{'='*60}")
        print(f"TRAINING TEACHER MODEL")
        print(f"{'='*60}\n")
        
        # Get all teachers
        teachers = get_all_teachers()
        
        if not teachers:
            print(f"❌ No teachers found in database")
            return None
        
        print(f"✓ Found {len(teachers)} teachers")
        
        # Get all teacher images with metadata
        images = get_all_teacher_images()
        
        if not images:
            print(f"❌ No teacher images found")
            return None
        
        print(f"✓ Found {len(images)} teacher images")
        
        # Prepare training data
        known_face_encodings = []
        known_face_names = []
        known_face_ids = []
        
        # Track per-teacher statistics
        teacher_encoding_count = {}
        
        # Process each image
        for idx, img_record in enumerate(images, 1):
            image_url = img_record['file_url']
            teacher_name = img_record['teacher_name']
            teacher_id = img_record['teacher_id']
            
            print(f"\n[{idx}/{len(images)}] Processing: {teacher_name} ({teacher_id})")
            print(f"    Image: {image_url[-50:]}")  # Show last 50 chars of URL
            
            # Extract face encodings with balanced quality
            encodings = extract_face_encodings(image_url, num_jitters=5)
            
            # Add each encoding
            if encodings:
                for encoding in encodings:
                    known_face_encodings.append(encoding)
                    known_face_names.append(teacher_name)
                    known_face_ids.append(teacher_id)
                    
                    # Track count
                    if teacher_id not in teacher_encoding_count:
                        teacher_encoding_count[teacher_id] = 0
                    teacher_encoding_count[teacher_id] += 1
                
                print(f"    ✓ Added {len(encodings)} encoding(s)")
            else:
                print(f"    ⚠ WARNING: No face detected in this image")
        
        if not known_face_encodings:
            print("\n❌ ERROR: No face encodings extracted from any images")
            print("Please ensure images contain clear, visible faces")
            return None
        
        print(f"\n{'='*60}")
        print(f"TRAINING SUMMARY")
        print(f"{'='*60}")
        print(f"Total encodings extracted: {len(known_face_encodings)}")
        print(f"Unique teachers trained: {len(teacher_encoding_count)}")
        print(f"\nEncodings per teacher:")
        for teacher_id, count in teacher_encoding_count.items():
            teacher_name = next((name for name, tid in zip(known_face_names, known_face_ids) if tid == teacher_id), "Unknown")
            print(f"  • {teacher_name} ({teacher_id}): {count} encodings")
            if count < 5:
                print(f"    ⚠ WARNING: Only {count} encodings. Recommend at least 5 images per teacher for accuracy")
        
        # Create model data
        model_data = {
            'encodings': known_face_encodings,
            'names': known_face_names,
            'ids': known_face_ids,
            'entity_type': 'teacher',
            'teachers_count': len(teachers),
            'training_params': {
                'num_jitters': 5,
                'model': 'hog',
                'upsample': 1
            }
        }
        
        # Serialize model to bytes
        print(f"\nSerializing model...")
        model_bytes = pickle.dumps(model_data)
        print(f"Model size: {len(model_bytes) / 1024:.2f} KB")
        
        # Create model path in Supabase Storage
        model_path = "models/teachers/model.pkl"
        
        # Upload to Supabase Storage
        print(f"Uploading to Supabase Storage...")
        bucket = "face-recognition-models"
        public_url = upload_to_supabase_storage(model_bytes, bucket, model_path)
        
        if not public_url:
            print("❌ Failed to upload model to Supabase Storage")
            return None
        
        print(f"✓ Model uploaded successfully")
        print(f"Storage path: {model_path}")
        
        # Store model metadata in database
        print(f"Storing model metadata...")
        try:
            # Use a special marker for teacher models (section='TEACHERS', year=0)
            metadata_data = {
                "section": "TEACHERS",
                "year": 0,
                "model_path": model_path,
                "students_count": len(teachers)  # Using students_count field for teachers_count
            }
            
            # Check if teacher model already exists
            existing = supabase.table("models").select("*").eq("section", "TEACHERS").eq("year", 0).execute()
            
            if existing.data:
                # Update existing
                result = supabase.table("models").update(metadata_data).eq("section", "TEACHERS").eq("year", 0).execute()
            else:
                # Insert new
                result = supabase.table("models").insert(metadata_data).execute()
            
            print(f"Metadata stored: {result.data[0] if result.data else 'Failed'}")
        except Exception as meta_error:
            print(f"Warning: Could not store metadata: {meta_error}")
        
        print(f"\n{'='*60}")
        print(f"✓ TEACHER TRAINING COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")
        
        return {
            'success': True,
            'model_path': model_path,
            'teachers_count': len(teachers),
            'encodings_count': len(known_face_encodings),
            'public_url': public_url,
            'teacher_encoding_count': teacher_encoding_count
        }
        
    except Exception as e:
        print(f"\n❌ ERROR training teacher model: {e}")
        import traceback
        traceback.print_exc()
        return None

def train_face_model(section: str, year: str) -> Optional[Dict]:
    """
    Train face recognition model for a specific section and year with improved accuracy
    
    Args:
        section: Section name (e.g., "A", "B") - if empty, trains teachers
        year: Academic year/semester - if empty, trains teachers
        
    Returns:
        Dictionary with training results
    """
    try:
        # Check if this is a teacher training request (empty section and year)
        if not section or not year or section.strip() == '' or year.strip() == '':
            print("\n=== Detected teacher training request (empty section/year) ===")
            return train_teacher_face_model()
        
        print(f"\n{'='*60}")
        print(f"TRAINING STUDENT MODEL: Section {section}, Year {year}")
        print(f"{'='*60}\n")
        
        # Get all students in this section/year
        students = get_students_by_section_year(section, year)
        
        if not students:
            print(f"❌ No students found for section {section}, year {year}")
            return None
        
        print(f"✓ Found {len(students)} students")
        
        # Get all images for these students
        images = get_images_by_section_year(section, year)
        
        if not images:
            print(f"❌ No images found for section {section}, year {year}")
            return None
        
        print(f"✓ Found {len(images)} images")
        
        # Prepare training data
        known_face_encodings = []
        known_face_names = []
        known_face_ids = []
        
        # Track per-student statistics
        student_encoding_count = {}
        
        # Process each image
        for idx, img_record in enumerate(images, 1):
            image_url = img_record['file_url']
            student_name = img_record['student_name']
            student_enrollment = img_record['student_enrollment']
            
            print(f"\n[{idx}/{len(images)}] Processing: {student_name} ({student_enrollment})")
            print(f"    Image: {image_url[-50:]}")  # Show last 50 chars of URL
            
            # Extract face encodings with balanced quality (num_jitters=5 for training)
            encodings = extract_face_encodings(image_url, num_jitters=5)
            
            # Add each encoding
            if encodings:
                for encoding in encodings:
                    known_face_encodings.append(encoding)
                    known_face_names.append(student_name)
                    known_face_ids.append(student_enrollment)
                    
                    # Track count
                    if student_enrollment not in student_encoding_count:
                        student_encoding_count[student_enrollment] = 0
                    student_encoding_count[student_enrollment] += 1
                
                print(f"    ✓ Added {len(encodings)} encoding(s)")
            else:
                print(f"    ⚠ WARNING: No face detected in this image")
        
        if not known_face_encodings:
            print("\n❌ ERROR: No face encodings extracted from any images")
            print("Please ensure images contain clear, visible faces")
            return None
        
        print(f"\n{'='*60}")
        print(f"TRAINING SUMMARY")
        print(f"{'='*60}")
        print(f"Total encodings extracted: {len(known_face_encodings)}")
        print(f"Unique students trained: {len(student_encoding_count)}")
        print(f"\nEncodings per student:")
        for enrollment, count in student_encoding_count.items():
            student_name = next((name for name, enr in zip(known_face_names, known_face_ids) if enr == enrollment), "Unknown")
            print(f"  • {student_name} ({enrollment}): {count} encodings")
            if count < 5:
                print(f"    ⚠ WARNING: Only {count} encodings. Recommend at least 5 images per student for accuracy")
        
        # Create model data
        model_data = {
            'encodings': known_face_encodings,
            'names': known_face_names,
            'ids': known_face_ids,
            'section': section,
            'year': year,
            'entity_type': 'student',
            'students_count': len(students),
            'training_params': {
                'num_jitters': 5,
                'model': 'hog',
                'upsample': 1
            }
        }
        
        # Serialize model to bytes
        print(f"\nSerializing model...")
        model_bytes = pickle.dumps(model_data)
        print(f"Model size: {len(model_bytes) / 1024:.2f} KB")
        
        # Create model path in Supabase Storage
        model_path = f"models/{section}_{year}/model.pkl"
        
        # Upload to Supabase Storage
        print(f"Uploading to Supabase Storage...")
        bucket = "face-recognition-models"
        public_url = upload_to_supabase_storage(model_bytes, bucket, model_path)
        
        if not public_url:
            print("❌ Failed to upload model to Supabase Storage")
            return None
        
        print(f"✓ Model uploaded successfully")
        print(f"Storage path: {model_path}")
        
        # Store model metadata in database
        print(f"Storing model metadata...")
        metadata = store_model_metadata(
            section=section,
            year=year,
            model_path=model_path,
            students_count=len(students)
        )
        
        print(f"\n{'='*60}")
        print(f"✓ TRAINING COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")
        
        return {
            'success': True,
            'model_path': model_path,
            'students_count': len(students),
            'encodings_count': len(known_face_encodings),
            'public_url': public_url,
            'student_encoding_count': student_encoding_count
        }
        
    except Exception as e:
        print(f"\n❌ ERROR training model: {e}")
        import traceback
        traceback.print_exc()
        return None

def retrain_specific_student(enrollment_number: str) -> bool:
    """
    Retrain model after adding/updating a specific student
    
    Args:
        enrollment_number: Student enrollment number
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from db import get_student
        
        # Get student details
        student = get_student(enrollment_number)
        
        if not student:
            return False
        
        section = student['section']
        year = str(student['semester'])
        
        # Retrain model for this section/year
        result = train_face_model(section, year)
        
        return result is not None
        
    except Exception as e:
        print(f"Error retraining for student: {e}")
        return False

def validate_model(section: str, year: str) -> bool:
    """
    Validate if a trained model exists for the given section and year
    
    Args:
        section: Section name
        year: Academic year
        
    Returns:
        True if model exists, False otherwise
    """
    try:
        from db import get_model_path
        
        model_path = get_model_path(section, year)
        
        return model_path is not None
        
    except Exception as e:
        print(f"Error validating model: {e}")
        return False