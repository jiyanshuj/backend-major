import os
import cloudinary
import cloudinary.uploader
from datetime import datetime
from typing import Optional, Dict
import io

# Cloudinary Configuration
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "dahfnjfof"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "789849686741558"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "8VrK2atnJ2Bkl6lOBNz8xdE_ToI")
)

def upload_to_cloudinary(image_data: bytes, folder: str, filename: str) -> Optional[Dict]:
    """
    Upload image to Cloudinary
    
    Args:
        image_data: Image bytes
        folder: Folder structure (e.g., "enrollmentNumber_branch_year_section")
        filename: Base filename without extension
        
    Returns:
        Dictionary with upload result including URL
    """
    try:
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            image_data,
            folder=f"face_recognition/{folder}",
            public_id=filename,
            resource_type="image",
            overwrite=True
        )
        
        return {
            "url": result.get("secure_url"),
            "public_id": result.get("public_id"),
            "folder": folder,
            "filename": filename
        }
        
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None

def download_from_cloudinary(public_id: str) -> Optional[bytes]:
    """
    Download image from Cloudinary using public_id
    
    Args:
        public_id: Cloudinary public ID
        
    Returns:
        Image bytes
    """
    try:
        import requests
        
        # Get the URL from Cloudinary
        url = cloudinary.CloudinaryImage(public_id).build_url()
        
        # Download the image
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.content
        return None
        
    except Exception as e:
        print(f"Error downloading from Cloudinary: {e}")
        return None

def download_from_url(url: str) -> Optional[bytes]:
    """
    Download image from direct URL
    
    Args:
        url: Direct image URL
        
    Returns:
        Image bytes
    """
    try:
        import requests
        
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.content
        return None
        
    except Exception as e:
        print(f"Error downloading from URL: {e}")
        return None

def generate_guest_token() -> str:
    """
    Generate unique guest token in format: guest_YYYYMMDD_NNN
    
    Returns:
        Unique guest token string
    """
    import random
    
    # Get current date
    date_str = datetime.now().strftime("%Y%m%d")
    
    # Generate random 3-digit number
    random_num = random.randint(100, 999)
    
    # Create token
    token = f"guest_{date_str}_{random_num}"
    
    return token

def validate_image(image_data: bytes) -> bool:
    """
    Validate if the uploaded file is a valid image
    
    Args:
        image_data: Image bytes
        
    Returns:
        True if valid image, False otherwise
    """
    try:
        from PIL import Image
        
        # Try to open the image
        img = Image.open(io.BytesIO(image_data))
        
        # Verify it's an image
        img.verify()
        
        return True
        
    except Exception as e:
        print(f"Image validation failed: {e}")
        return False

def resize_image(image_data: bytes, max_width: int = 800, max_height: int = 800) -> bytes:
    """
    Resize image to reduce storage size
    
    Args:
        image_data: Original image bytes
        max_width: Maximum width
        max_height: Maximum height
        
    Returns:
        Resized image bytes
    """
    try:
        from PIL import Image
        
        # Open image
        img = Image.open(io.BytesIO(image_data))
        
        # Calculate new size maintaining aspect ratio
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85)
        output.seek(0)
        
        return output.read()
        
    except Exception as e:
        print(f"Error resizing image: {e}")
        return image_data

def delete_from_cloudinary(public_id: str) -> bool:
    """
    Delete image from Cloudinary
    
    Args:
        public_id: Cloudinary public ID
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        result = cloudinary.uploader.destroy(public_id)
        
        return result.get("result") == "ok"
        
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")
        return False

def create_folder_name(enrollment_number: str, branch: str, year: str, section: str) -> str:
    """
    Create standardized folder name
    
    Args:
        enrollment_number: Student enrollment number
        branch: Branch/Department (e.g., CS, IT)
        year: Academic year/semester
        section: Section name
        
    Returns:
        Folder name string
    """
    return f"{enrollment_number}_{branch}_{year}_{section}"

def get_cloudinary_folder_url(folder: str) -> str:
    """
    Get Cloudinary folder URL
    
    Args:
        folder: Folder name
        
    Returns:
        Cloudinary folder URL
    """
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "YOUR_CLOUD_NAME")
    return f"https://res.cloudinary.com/{cloud_name}/image/upload/face_recognition/{folder}/"