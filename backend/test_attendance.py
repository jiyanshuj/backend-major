import requests
import json

BASE_URL = "http://localhost:8000"

def test_attendance_flow():
    # 1. Check if students exist
    print("1. Checking students in section M, semester 7...")
    response = requests.get(f"{BASE_URL}/debug/students?section=M&year=7")
    students = response.json()
    print(f"   Found {students.get('count', 0)} students")
    print(f"   Students: {json.dumps(students.get('students', []), indent=2)}")
    
    if students.get('count', 0) == 0:
        print("   ❌ No students found! Register students first.")
        return
    
    # 2. Check subjects
    print("\n2. Checking subjects...")
    response = requests.get(f"{BASE_URL}/debug/subjects")
    subjects = response.json()
    print(f"   Found {subjects.get('count', 0)} subjects")
    print(f"   Subjects: {json.dumps(subjects.get('subjects', []), indent=2)}")
    
    if subjects.get('count', 0) == 0:
        print("   ❌ No subjects found! Add subjects in Supabase.")
        return
    
    subject_id = subjects['subjects'][0]['subject_id']
    print(f"   Using subject_id: {subject_id}")
    
    # 3. Start attendance session
    print("\n3. Starting attendance session...")
    data = {
        "teacher_id": "TEACHER001",
        "subject_id": subject_id,
        "section": "M",
        "semester": 7,
        "class_name": "ML-M",
        "duration_minutes": 60
    }
    
    print(f"   Sending data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(f"{BASE_URL}/attendance/start-session", data=data)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text}")
        
        result = response.json()
        
        if result.get('success'):
            print("   ✅ Session started successfully!")
            session_id = result['session']['session_id']
            print(f"   Session ID: {session_id}")
            print(f"   Total students: {result['session'].get('total_students', 0)}")
            print(f"   Absent count: {result['session'].get('absent_count', 0)}")
            
            # 4. Check attendance records
            print("\n4. Checking attendance records...")
            response = requests.get(f"{BASE_URL}/attendance/session/{session_id}")
            records = response.json()
            print(f"   ✅ Found {records.get('count', 0)} attendance records")
            
            # Show all records
            for record in records.get('records', []):
                print(f"   - {record['student_name']} ({record['enrollment_number']}): {record['status']}")
        else:
            print(f"   ❌ Failed: {result.get('message', 'Unknown error')}")
            if 'detail' in result:
                print(f"   Detail: {result['detail']}")
                
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON decode error: {e}")
        print(f"   Raw response: {response.text}")

if __name__ == "__main__":
    test_attendance_flow()