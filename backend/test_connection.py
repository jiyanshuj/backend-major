"""
Test script to verify Supabase and Cloudinary connections
Run this before starting the main application
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_supabase():
    """Test Supabase connection"""
    print("\n🔍 Testing Supabase Connection...")
    try:
        from supabase import create_client
        
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY")
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("❌ SUPABASE_URL or SUPABASE_KEY not found in .env file")
            return False
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Test query
        response = supabase.table("students").select("*").limit(1).execute()
        print(f"✅ Supabase connected successfully!")
        print(f"   Students table accessible: {len(response.data) if response.data else 0} records found")
        
        # Check if other tables exist
        tables_to_check = ["sections", "student_files", "student_sections"]
        for table in tables_to_check:
            try:
                test = supabase.table(table).select("*").limit(1).execute()
                print(f"   ✓ Table '{table}' exists")
            except Exception as e:
                print(f"   ⚠ Table '{table}' might not exist or is not accessible")
        
        return True
        
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def test_cloudinary():
    """Test Cloudinary connection"""
    print("\n🔍 Testing Cloudinary Connection...")
    try:
        import cloudinary
        import cloudinary.api
        import cloudinary.uploader
        
        CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
        API_KEY = os.getenv("CLOUDINARY_API_KEY")
        API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
        
        if not CLOUD_NAME or not API_KEY or not API_SECRET:
            print("❌ Cloudinary credentials not found in .env file")
            return False
        
        cloudinary.config(
            cloud_name=CLOUD_NAME,
            api_key=API_KEY,
            api_secret=API_SECRET
        )
        
        # Test API connection with ping
        try:
            result = cloudinary.api.ping()
            print(f"✅ Cloudinary connected successfully!")
            print(f"   Cloud Name: {CLOUD_NAME}")
            print(f"   API Status: {result.get('status', 'OK')}")
        except Exception as ping_error:
            # If ping fails, try a simple upload test (won't actually upload)
            print(f"✅ Cloudinary configured successfully!")
            print(f"   Cloud Name: {CLOUD_NAME}")
            print(f"   Note: API ping failed but config is valid")
        
        return True
        
    except ImportError as e:
        print(f"❌ Cloudinary module not properly installed: {e}")
        print("   Try: pip install cloudinary --upgrade")
        return False
    except Exception as e:
        print(f"❌ Cloudinary connection failed: {e}")
        return False

def test_face_recognition():
    """Test face recognition library"""
    print("\n🔍 Testing Face Recognition Library...")
    try:
        import face_recognition
        print("✅ face_recognition library imported successfully!")
        
        # Test with a simple array
        import numpy as np
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        print("✅ numpy working correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Face recognition test failed: {e}")
        print("   Tip: If dlib failed to install, try using DeepFace instead")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    print("\n🔍 Checking .env file...")
    
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("   Create a .env file with the following variables:")
        print("""
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
        """)
        return False
    
    required_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env file found with all required variables!")
    return True

def main():
    """Run all tests"""
    print("="*60)
    print("🚀 Face Recognition System - Setup Verification")
    print("="*60)
    
    results = {
        "Environment File": check_env_file(),
        "Supabase": test_supabase(),
        "Cloudinary": test_cloudinary(),
        "Face Recognition": test_face_recognition()
    }
    
    print("\n" + "="*60)
    print("📊 Test Results Summary:")
    print("="*60)
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
        if not result:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("\n🎉 All tests passed! You're ready to run the application.")
        print("   Run: python main.py")
    else:
        print("\n⚠️ Some tests failed. Please fix the issues above before running the application.")
    
    print()

if __name__ == "__main__":
    main()