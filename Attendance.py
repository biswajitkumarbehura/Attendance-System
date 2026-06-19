import cv2
import mediapipe as mp
import face_recognition
import numpy as np
import mysql.connector
import time
from datetime import datetime, timedelta

# --- MySQL Database Engine Configuration ---
db_config = {
    'host': 'localhost',
    'user': 'root',         
    'password': 'admin123', # Modern MySQL 8.4 Authentication Password
    'database': 'attendance_system'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Load database profiles dynamically into operational RAM variables
def load_known_faces():
    known_encodings, known_roll_nos, known_names = [], [], []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT RollNo, Name, Encoding FROM students")
        rows = cursor.fetchall()
        for row in rows:
            roll_no, name, enc_str = row
            encoding = np.fromstring(enc_str, sep=',')
            known_encodings.append(encoding)
            known_roll_nos.append(roll_no)
            known_names.append(name)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DATABASE ERROR] Failed loading profiles: {e}")
    return known_encodings, known_roll_nos, known_names

known_encodings, known_roll_nos, known_names = load_known_faces()

# --- Initialize Optimized MediaPipe Hand Tracking ---
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False, 
    max_num_hands=1, 
    model_complexity=0, 
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)
mp_draw = mp.solutions.drawing_utils

# Variables for Performance & UI
last_action_time = 0
cooldown_seconds = 4  
status_msg = "System Active & Smooth"
msg_color = (0, 255, 0)

frame_count = 0
process_this_frame = True  
face_locations, face_encodings, face_names, face_rolls = [], [], [], []

def save_new_student(roll_no, name, encoding):
    global known_encodings, known_roll_nos, known_names
    encoding_str = ','.join(map(str, encoding))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (RollNo, Name, Encoding) VALUES (%s, %s, %s)",
            (roll_no, name, encoding_str)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        # Append to system tracking lists locally 
        known_encodings.append(encoding)
        known_roll_nos.append(roll_no)
        known_names.append(name)
        return True
    except Exception as e:
        print(f"[DB ERROR] Save failed: {e}")
        return False

def detect_gesture(hand_landmarks):
    lm = hand_landmarks.landmark
    thumb_is_open = lm[4].y < lm[3].y
    index_is_open = lm[8].y < lm[6].y
    middle_is_open = lm[12].y < lm[10].y
    ring_is_open = lm[16].y < lm[14].y
    pinky_is_open = lm[20].y < lm[18].y

    if index_is_open and middle_is_open and ring_is_open and pinky_is_open:
        return "FULL_PALM"
    if thumb_is_open and not index_is_open and not middle_is_open and not ring_is_open and not pinky_is_open:
        if lm[4].y < lm[0].y:
            return "THUMBS_UP"
    return "UNKNOWN"

def get_opencv_input(prompt_text):
    user_input = ""
    while True:
        input_bg = np.zeros((200, 600, 3), dtype=np.uint8)
        cv2.putText(input_bg, prompt_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(input_bg, user_input + "_", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(input_bg, "Press ENTER to confirm | ESC to cancel", (20, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA)
        
        cv2.imshow("Registration Entry", input_bg)
        key = cv2.waitKey(0)
        
        if key == 13: # Enter Key
            break
        elif key == 27: # Escape Key
            return None
        elif key == 127 or key == 8: # Backspace
            user_input = user_input[:-1]
        elif 32 <= key <= 126: # Valid characters
            user_input += chr(key)
            
    cv2.destroyWindow("Registration Entry")
    return user_input.strip()

def process_attendance(roll_no, name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today = datetime.now().strftime("%Y-%m-%d")
        now_time = datetime.now()
        now_str = now_time.strftime("%H:%M:%S")
        
        # Check database for today's logs
        cursor.execute(
            "SELECT * FROM attendance_log WHERE Date = %s AND RollNo = %s", (today, roll_no)
        )
        student_today = cursor.fetchone()
        
        if not student_today:
            # First interaction today -> Log them IN
            cursor.execute(
                "INSERT INTO attendance_log (Date, RollNo, Name, InTime, OutTime) VALUES (%s, %s, %s, %s, 'Pending')",
                (today, roll_no, name, now_str)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return f"In Logged: Welcome {name}!", (0, 255, 0)
        else:
            in_time_str = str(student_today['InTime'])
            out_time_str = student_today['OutTime']
            
            # If they already checked out completely today, deny further updates
            if out_time_str != 'Pending':
                cursor.close()
                conn.close()
                return f"{name} already logged out today.", (0, 165, 255)
                
            # Parse InTime and calculate duration of stay
            in_time_dt = datetime.strptime(f"{today} {in_time_str}", "%Y-%m-%d %H:%M:%S")
            time_difference = now_time - in_time_dt
            
            # STRICT LOCKOUT CRITERIA: 4 Hours
            required_duration = timedelta(hours=4)
            
            if time_difference >= required_duration:
                # 4 hours have elapsed -> Log them OUT
                cursor.execute(
                    "UPDATE attendance_log SET OutTime = %s WHERE Date = %s AND RollNo = %s",
                    (now_str, today, roll_no)
                )
                conn.commit()
                cursor.close()
                conn.close()
                return f"Out Logged: Goodbye {name}!", (255, 255, 0)
            else:
                # 4 hours have NOT elapsed -> Deny check out and show remaining time
                remaining_time = required_duration - time_difference
                total_seconds = int(remaining_time.total_seconds())
                
                hours_left = total_seconds // 3600
                minutes_left = (total_seconds % 3600) // 60
                
                cursor.close()
                conn.close()
                
                if hours_left > 0:
                    time_str = f"{hours_left}h {minutes_left}m left"
                else:
                    time_str = f"{minutes_left}m left"
                    
                return f"Denied: {time_str} for {name}", (0, 0, 255)
    except Exception as e:
        print(f"[SYSTEM ERROR] Attendance logic failed: {e}")
        return "Database Error!", (0, 0, 255)

# --- Camera Stream Execution Loop ---
video_capture = cv2.VideoCapture(0)
video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("[INFO] High Performance MySQL-Linked Engine Started. Press 'q' to exit.")

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    current_time = time.time()
    frame_count += 1

    process_this_frame = (frame_count % 3 == 0)

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    current_gesture = "UNKNOWN"
    
    # Track hands less aggressively to save CPU resources
    if frame_count % 2 == 0:
        hand_result = hands.process(rgb_frame)
        if hand_result.multi_hand_landmarks:
            for hand_landmarks in hand_result.multi_hand_landmarks:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                current_gesture = detect_gesture(hand_landmarks)

    if process_this_frame:
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)
        
        face_names = []
        face_rolls = []
        
        for face_encoding in face_encodings:
            name = "Unknown"
            roll_no = None
            
            if known_encodings:
                matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.5)
                face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                
                if True in matches:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = known_names[best_match_index]
                        roll_no = known_roll_nos[best_match_index]
            
            face_names.append(name)
            face_rolls.append(roll_no)

    for (top, right, bottom, left), name, roll_no in zip(face_locations, face_names, face_rolls):
        top *= 4
        right *= 4
        bottom *= 4
        left *= 4

        box_color = (0, 0, 255) if name == "Unknown" else (0, 255, 0)
        cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
        
        if name == "Unknown":
            cv2.putText(frame, "Unregistered Profile", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            if current_gesture == "FULL_PALM" and (current_time - last_action_time > cooldown_seconds):
                face_bound_box = [(top, right, bottom, left)]
                high_res_encoding = face_recognition.face_encodings(rgb_frame, face_bound_box)
                
                if high_res_encoding:
                    new_name = get_opencv_input("Enter Student's Full Name:")
                    new_roll = get_opencv_input(f"Enter Roll Number for {new_name}:") if new_name else None
                    
                    if new_name and new_roll:
                        if save_new_student(new_roll, new_name, high_res_encoding[0]):
                            status_msg = f"Saved to Database: {new_name}!"
                            msg_color = (0, 255, 0)
                            face_locations, face_names, face_rolls = [], [], []
                            break
                        else:
                            status_msg = "Database Error during save."
                            msg_color = (0, 0, 255)
                    else:
                        status_msg = "Registration Cancelled."
                        msg_color = (0, 0, 255)
                last_action_time = time.time()
        else:
            cv2.putText(frame, f"{name} [{roll_no}]", (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            if current_gesture == "THUMBS_UP" and (current_time - last_action_time > cooldown_seconds):
                status_msg, msg_color = process_attendance(roll_no, name)
                last_action_time = time.time()

    # Draw Status Bar Header
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (20, 20, 20), -1)
    cv2.putText(frame, f"SYSTEM STATUS: {status_msg}", (15, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, msg_color, 2)
    cv2.putText(frame, f"Gesture Mode: {current_gesture}", (15, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1)
    
    cv2.imshow('Biometric Attendance Core', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()