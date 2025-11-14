import pickle
import face_recognition
import numpy as np
from typing import Optional, Dict
import io
from PIL import Image

from db import get_model_path, download_from_supabase_storage, get_student, get_teacher, get_guest, supabase

def load_model(section: str, year: str) -> Optional[Dict]:
    """
    Load trained model for a specific section and year, or teacher model
    
    Args:
        section: Section name (empty string for teachers)
        year: Academic year (empty string for teachers)
        
    Returns:
        Model data dictionary or None
    """
    try:
        # Check if this is a teacher model request (empty section and year)
        if not section or not year or section.strip() == '' or year.strip() == '':
            print(f"[LOAD MODEL] Loading TEACHER model")
            model_path = "models/teachers/model.pkl"
        else:
            print(f"[LOAD MODEL] Loading STUDENT model for section={section}, year={year}")
            # Get model path from database
            model_path = get_model_path(section, year)
        
        if not model_path:
            print(f"[LOAD MODEL] No model found")
            return None
        
        print(f"[LOAD MODEL] Model path: {model_path}")
        
        # Download model from Supabase Storage
        bucket = "face-recognition-models"
        model_bytes = download_from_supabase_storage(bucket, model_path)
        
        if not model_bytes:
            print(f"[LOAD MODEL] Failed to download model from path: {model_path}")
            return None
        
        # Deserialize model
        model_data = pickle.loads(model_bytes)
        entity_type = model_data.get('entity_type', 'student')
        print(f"[LOAD MODEL] Model loaded successfully. Entity type: {entity_type}, Encodings: {len(model_data.get('encodings', []))}")
        
        return model_data
        
    except Exception as e:
        print(f"[LOAD MODEL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_face_encoding_from_bytes(image_data: bytes, verbose: bool = False) -> Optional[np.ndarray]:
    """
    Extract face encoding from image bytes with improved accuracy
    
    Args:
        image_data: Image bytes
        verbose: Enable detailed logging
        
    Returns:
        Face encoding (128-dimensional vector) or None
    """
    try:
        if verbose:
            print("[EXTRACT ENCODING] Starting face detection...")
        
        # Convert bytes to PIL Image
        pil_image = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array
        image_array = np.array(pil_image)
        if verbose:
            print(f"[EXTRACT ENCODING] Image shape: {image_array.shape}")
        
        # Find face locations using HOG (faster) with standard upsampling
        face_locations = face_recognition.face_locations(image_array, model="hog", number_of_times_to_upsample=1)
        
        if not face_locations:
            if verbose:
                print("[EXTRACT ENCODING] No faces detected in image")
            return None
        
        if verbose:
            print(f"[EXTRACT ENCODING] Found {len(face_locations)} face(s)")
        
        # Extract face encoding with balanced quality (num_jitters=3 for testing - fast but still accurate)
        encodings = face_recognition.face_encodings(image_array, face_locations, num_jitters=3)
        
        if encodings:
            if verbose:
                print(f"[EXTRACT ENCODING] Encoding extracted successfully")
            return encodings[0]
        
        if verbose:
            print("[EXTRACT ENCODING] Failed to compute encodings")
        return None
        
    except Exception as e:
        if verbose:
            print(f"[EXTRACT ENCODING ERROR] {e}")
            import traceback
            traceback.print_exc()
        return None

def recognize_face(image_data: bytes, section: str, year: str, tolerance: float = 0.5) -> Dict:
    """
    Recognize face in the given image using trained model
    
    Args:
        image_data: Image bytes
        section: Section name (empty for teachers)
        year: Academic year (empty for teachers)
        tolerance: Face matching tolerance (lower is stricter, default 0.5)
        
    Returns:
        Recognition result dictionary with name, role, color, confidence
    """
    try:
        # Load trained model (only log once)
        model_data = load_model(section, year)
        
        if not model_data:
            return {
                'name': 'Unknown',
                'id': 'N/A',
                'role': 'Unknown',
                'color': 'red',
                'confidence': 0.0,
                'message': 'Model not trained. Please train the model first.'
            }
        
        # Extract face encoding from test image (quiet mode)
        test_encoding = extract_face_encoding_from_bytes(image_data, verbose=False)
        
        if test_encoding is None:
            return {
                'name': 'Unknown',
                'id': 'N/A',
                'role': 'Unknown',
                'color': 'red',
                'confidence': 0.0,
                'message': 'No face detected in frame'
            }
        
        # Get known encodings from model
        known_encodings = model_data['encodings']
        known_names = model_data['names']
        known_ids = model_data['ids']
        entity_type = model_data.get('entity_type', 'student')
        
        # Compare face encodings
        face_distances = face_recognition.face_distance(known_encodings, test_encoding)
        
        # Find best match
        best_match_index = np.argmin(face_distances)
        best_distance = face_distances[best_match_index]
        
        # Check if match is within tolerance
        if best_distance <= tolerance:
            matched_name = known_names[best_match_index]
            matched_id = known_ids[best_match_index]
            confidence = 1.0 - best_distance  # Convert distance to confidence
            
            # Only log successful matches
            print(f"[MATCH] {matched_name} ({matched_id}) - Role: {entity_type} - Confidence: {confidence:.2%}")
            
            # Determine role and color based on entity type from model
            if entity_type == 'teacher':
                role = 'Teacher'
                color = 'green'
            elif matched_id.startswith('guest_'):
                role = 'Guest'
                color = 'yellow'
            else:
                role = 'Student'
                color = 'green'
            
            return {
                'name': matched_name,
                'id': matched_id,
                'role': role,
                'color': color,
                'confidence': float(confidence),
                'message': 'Face recognized successfully'
            }
        else:
            # No match found - only log occasionally
            return {
                'name': 'Unknown',
                'id': 'N/A',
                'role': 'Unknown',
                'color': 'red',
                'confidence': 0.0,
                'best_distance': float(best_distance),
                'message': 'Face not recognized - not in database'
            }
        
    except Exception as e:
        print(f"[RECOGNIZE FACE ERROR] {e}")
        return {
            'name': 'Unknown',
            'id': 'N/A',
            'role': 'Unknown',
            'color': 'red',
            'confidence': 0.0,
            'message': f'Recognition error: {str(e)}'
        }

def recognize_multiple_faces(image_data: bytes, section: str, year: str, tolerance: float = 0.5) -> list:
    """
    Recognize multiple faces in an image (for group photos or attendance)
    
    Args:
        image_data: Image bytes
        section: Section name (empty for teachers)
        year: Academic year (empty for teachers)
        tolerance: Face matching tolerance
        
    Returns:
        List of recognition results for each detected face
    """
    try:
        print(f"[RECOGNIZE MULTIPLE] Starting multi-face recognition")
        
        # Load trained model
        model_data = load_model(section, year)
        
        if not model_data:
            print("[RECOGNIZE MULTIPLE] Model not found")
            return []
        
        # Convert bytes to image array
        pil_image = Image.open(io.BytesIO(image_data))
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        image_array = np.array(pil_image)
        
        print(f"[RECOGNIZE MULTIPLE] Image shape: {image_array.shape}")
        
        # Find all face locations with standard settings
        face_locations = face_recognition.face_locations(image_array, model="hog", number_of_times_to_upsample=1)
        
        if not face_locations:
            print("[RECOGNIZE MULTIPLE] No faces detected")
            return []
        
        print(f"[RECOGNIZE MULTIPLE] Found {len(face_locations)} face(s)")
        
        # Extract encodings for all faces with balanced quality
        face_encodings = face_recognition.face_encodings(image_array, face_locations, num_jitters=3)
        
        results = []
        
        # Get known encodings from model
        known_encodings = model_data['encodings']
        known_names = model_data['names']
        known_ids = model_data['ids']
        entity_type = model_data.get('entity_type', 'student')
        
        # Process each detected face
        for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
            # Compare with known faces
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]
            
            print(f"[RECOGNIZE MULTIPLE] Face {i+1}: best_distance={best_distance:.4f}")
            
            if best_distance <= tolerance:
                matched_name = known_names[best_match_index]
                matched_id = known_ids[best_match_index]
                confidence = 1.0 - best_distance
                
                # Determine role and color based on entity type
                if entity_type == 'teacher':
                    role = 'Teacher'
                    color = 'green'
                elif matched_id.startswith('guest_'):
                    role = 'Guest'
                    color = 'yellow'
                else:
                    role = 'Student'
                    color = 'green'
                
                print(f"[RECOGNIZE MULTIPLE] Matched: {matched_name} ({matched_id})")
                
                results.append({
                    'name': matched_name,
                    'id': matched_id,
                    'role': role,
                    'color': color,
                    'confidence': float(confidence),
                    'location': face_location  # (top, right, bottom, left)
                })
            else:
                print(f"[RECOGNIZE MULTIPLE] Face {i+1}: Unknown")
                results.append({
                    'name': 'Unknown',
                    'id': 'N/A',
                    'role': 'Unknown',
                    'color': 'red',
                    'confidence': 0.0,
                    'location': face_location
                })
        
        print(f"[RECOGNIZE MULTIPLE] Processed {len(results)} faces successfully")
        return results
        
    except Exception as e:
        print(f"[RECOGNIZE MULTIPLE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return []

def verify_face(image_data: bytes, enrollment_number: str, tolerance: float = 0.6) -> Dict:
    """
    Verify if the face in the image matches a specific student/teacher/guest
    
    Args:
        image_data: Image bytes
        enrollment_number: Student enrollment number or employee ID or guest token
        tolerance: Face matching tolerance
        
    Returns:
        Verification result dictionary
    """
    try:
        from db import get_student_images, get_teacher_images, get_guest_images
        
        print(f"[VERIFY FACE] Verifying face for ID: {enrollment_number}")
        
        # Determine if this is a teacher, guest, or student
        stored_image_urls = None
        
        # Try teacher first
        teacher = get_teacher(enrollment_number)
        if teacher:
            stored_image_urls = get_teacher_images(enrollment_number)
        else:
            # Try guest
            guest = get_guest(enrollment_number)
            if guest:
                stored_image_urls = get_guest_images(enrollment_number)
            else:
                # Try student
                from db import get_student_images
                stored_image_urls = get_student_images(enrollment_number)
        
        if not stored_image_urls:
            return {
                'verified': False,
                'message': 'No stored images found for this person'
            }
        
        # Extract encoding from test image
        test_encoding = extract_face_encoding_from_bytes(image_data)
        
        if test_encoding is None:
            return {
                'verified': False,
                'message': 'No face detected in test image'
            }
        
        # Load and compare with stored images
        from capture import download_from_url
        
        matches = []
        
        for url in stored_image_urls[:5]:  # Check first 5 images
            stored_image_data = download_from_url(url)
            if stored_image_data:
                stored_encoding = extract_face_encoding_from_bytes(stored_image_data)
                if stored_encoding is not None:
                    distance = face_recognition.face_distance([stored_encoding], test_encoding)[0]
                    matches.append(distance)
        
        if not matches:
            return {
                'verified': False,
                'message': 'Could not extract encodings from stored images'
            }
        
        # Get average distance
        avg_distance = np.mean(matches)
        
        print(f"[VERIFY FACE] Average distance: {avg_distance:.4f}")
        
        if avg_distance <= tolerance:
            return {
                'verified': True,
                'confidence': float(1.0 - avg_distance),
                'message': 'Face verified successfully'
            }
        else:
            return {
                'verified': False,
                'confidence': float(1.0 - avg_distance),
                'message': 'Face does not match'
            }
        
    except Exception as e:
        print(f"[VERIFY FACE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {
            'verified': False,
            'message': f'Error: {str(e)}'
        }