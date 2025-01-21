import sqlite3
import streamlit as st
import asyncio
from bleak import BleakScanner,BleakError
import datetime
from datetime import date, datetime,timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from io import BytesIO
import matplotlib.pyplot as plt
import uuid
import hashlib
import platform
import requests
import cv2
import face_recognition
import numpy as np
from scipy.spatial.distance import euclidean
import time
import torch
from torchvision import transforms
from sklearn.cluster import DBSCAN
from sklearn.neighbors import KDTree
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

# Database setup
conn = sqlite3.connect("/Users/debojyotighosh/Desktop/asasspecial.db", check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    user_id TEXT PRIMARY KEY,
    password TEXT,
    name TEXT,
    roll TEXT,
    section TEXT,
    email TEXT,
    enrollment_no TEXT,
    year TEXT,
    semester TEXT,
    device_id TEXT,
    student_face BLOB 
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (
    admin_id TEXT PRIMARY KEY,
    password TEXT
    active INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    student_id TEXT,
    date TEXT,
    day TEXT,
    
    period_1 INTEGER,
    period_2 INTEGER,
    period_3 INTEGER,
    period_4 INTEGER,
    period_5 INTEGER,
    period_6 INTEGER,
    period_7 INTEGER,
    PRIMARY KEY (student_id, date, day)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_profile (
    admin_id TEXT PRIMARY KEY,
    name TEXT,
    department TEXT,
    designation TEXT,
    email TEXT,
    phone TEXT,
    face_encoding BLOB
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS semester_dates (
    year INTEGER,
    semester INTEGER,
    start_date DATE,
    end_date DATE,
    total_holidays INTEGER,
    total_classes INTEGER,
    total_periods INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS disputes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT,
    date TEXT,
    reason TEXT,
    status TEXT DEFAULT 'Pending'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL, -- e.g., Monday, Tuesday
    period TEXT NOT NULL, -- e.g., Period 1, Period 2
    subject TEXT NOT NULL,
    teacher TEXT NOT NULL
)              
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT NOT NULL,
    action TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    FOREIGN KEY (admin_id) REFERENCES admin (admin_id)
);
""")

# Commit the changes
conn.commit()

# Add default admin credentials
cursor.execute("INSERT OR IGNORE INTO admin (admin_id, password) VALUES ('admin', 'admin123')")
conn.commit()

# Register adapters and converters for SQLite
def adapt_date(d):
    return d.isoformat()

def adapt_datetime(dt):
    return dt.isoformat()

def convert_date(s):
    return date.fromisoformat(s.decode("utf-8"))

def convert_datetime(s):
    return datetime.fromisoformat(s.decode("utf-8"))

sqlite3.register_adapter(date, adapt_date)
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATE", convert_date)
sqlite3.register_converter("DATETIME", convert_datetime)

# Helper functions

def send_confirmation_email(admin_email, admin_name):
    # SMTP Configuration
    smtp_server = 'smtp-relay.brevo.com'
    smtp_port = 587
    smtp_user = '823c6b001@smtp-brevo.com'  # Replace with your SMTP username
    smtp_password = '6tOJHT2F4x8ZGmMw'      # Replace with your SMTP password
    from_email = 'debojyotighoshmain@gmail.com'  # Replace with your sending email address
    
    # Create the email content
    subject = "Welcome to the Admin Portal!"

    body = f"""
    Dear {admin_name},

    On behalf of the entire team, I am pleased to welcome you to the Admin Portal! We are thrilled to have you join our growing organization, where your role will be crucial in shaping our success.

    Your profile has been successfully created, and we would like to provide you with some important details about your account, features available to you, and your next steps:

    **Your Account Details:**
    - **Admin ID:** {new_admin_id}
    - **Name:** {new_name}
    - **Department:** {new_department}
    - **Designation:** {new_designation}
    - **Email:** {new_email}
    - **Phone:** {new_phone}

    **Features You Can Explore:**
    - **Profile Management:** Edit and manage your personal and professional details at any time.
    - **Data Analysis:** Gain insights from data reports and analytics dashboards.
    - **Report Generation:** Generate and share custom reports with other users.
    - **User Permissions:** Manage access rights and permissions for different users in the system.

    We believe that you will play a pivotal role in enhancing the experience for both administrators and users. Please take some time to familiarize yourself with the system, and if you have any questions or need assistance, do not hesitate to reach out to our support team.

    **Getting Started:**
    - Log in to the system using the credentials provided.
    - Begin by exploring the "Dashboard" for a high-level overview of key performance indicators and system notifications.
    - Customize your profile and update your contact preferences to stay informed about important updates.

    We are excited to have you as part of our organization, and we are confident that your expertise and leadership will help drive success. We look forward to working together and supporting you in your journey with us.

    Once again, welcome aboard!

    Best regards,
    The Admin Team
    """

    # Set up the MIME
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = admin_email
    msg['Subject'] = subject

    # Attach the body to the email
    msg.attach(MIMEText(body, 'plain'))

    # Establish a connection to the SMTP server
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Upgrade to secure connection
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, admin_email, msg.as_string())
        server.quit()  # Close the connection
        st.success("Email sent successfully.")
    except Exception as e:
        st.error(f"Failed to send email. Error: {str(e)}")
        
# SMTP Configuration
smtp_server = 'smtp-relay.brevo.com'
smtp_port = 587
smtp_user = '823c6b001@smtp-brevo.com'  # Replace with your SMTP username
smtp_password = '6tOJHT2F4x8ZGmMw'      # Replace with your SMTP password
from_email = 'debojyotighoshmain@gmail.com'  # Replace with your sending email address
    
# Function to calculate attendance percentage for each student
def get_low_attendance_students(threshold=75):
    # Fetch all students
    cursor.execute("SELECT user_id, name, email FROM students")
    all_students = cursor.fetchall()

    low_attendance = []

    for student in all_students:
        user_id, name, email = student

        # Fetch the student's year and semester
        cursor.execute("""
            SELECT year, semester FROM students WHERE user_id = ?
        """, (user_id,))
        student_semester = cursor.fetchone()

        if student_semester:
            year, semester = student_semester

            # Fetch total_classes and total_periods from semester_dates table
            cursor.execute("""
                SELECT total_classes, total_periods
                FROM semester_dates 
                WHERE year = ? AND semester = ?
            """, (year, semester))
            semester_details = cursor.fetchone()

            if semester_details:
                total_classes_in_semester, total_periods_in_semester = semester_details

                # Fetch the student's attendance records
                cursor.execute("SELECT * FROM attendance WHERE student_id = ?", (user_id,))
                attendance_records = cursor.fetchall()

                if attendance_records:
                    # Calculate total periods attended
                    total_present = sum(
                    sum(1 if record[i] == 1 else 0 for i in range(3, 10))  # Sum the periods attended (1 for present, 0 for absent)
                    for record in attendance_records
                )


                    # Calculate attendance percentage
                    if total_periods_in_semester > 0:  # Avoid division by zero
                        attendance_percentage = (total_present / total_periods_in_semester) * 100
                        
                        # Add to low attendance list if below the threshold
                        if attendance_percentage < threshold:
                            low_attendance.append((user_id, name, email, attendance_percentage))

    return low_attendance


def send_email(student_email, student_name, attendance_percentage):

    # Email Content
    subject = f"Attendance Alert - Immediate Attention Required"
    body = f"""
    Dear {student_name},

    This is to inform you that your attendance is currently at {attendance_percentage:.2f}%, 
    which is below the minimum required threshold of 75%.

    You are hereby advised to attend more classes and meet the required attendance criteria 
    to avoid being debarred from examinations or other academic activities.

    Regards,
    Admin Team
    Your Institution Name
    """

    try:
        # Create Email Message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = student_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to SMTP Server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Start TLS Encryption
            server.login(smtp_user, smtp_password)  # Login with SMTP credentials
            server.sendmail(from_email, student_email, msg.as_string())  # Send email

        st.success(f"Email successfully sent to {student_name} ({student_email}).")
    except smtplib.SMTPAuthenticationError:
        st.error(f"Failed to authenticate with SMTP server. Check your username and password.")
    except Exception as e:
        st.error(f"Failed to send email to {student_name} ({student_email}). Error: {str(e)}")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def capture_and_detect_faces():
    cap = cv2.VideoCapture(0)  # Open webcam
    if not cap.isOpened():
        st.error("Cannot access the webcam.")
        return None, None

    face_encodings = []
    face_locations = []

    while True:
        ret, frame = cap.read()
        if not ret:
            st.error("Failed to capture a frame from the webcam.")
            break

        # Convert the frame from BGR to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces in the frame
        face_locations = face_recognition.face_locations(rgb_frame)
        for top, right, bottom, left in face_locations:
            # Draw rectangles around detected faces
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

        # Convert frame to JPEG for Streamlit display
        _, jpeg_frame = cv2.imencode('.jpg', frame)
        st.image(jpeg_frame.tobytes(), channels="BGR", use_column_width=True, caption="Real-Time Face Detection")

        # Stop the loop if a face is detected
        if face_locations:
            try:
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                logging.info(f"Detected {len(face_encodings)} face(s).")
                break  # Stop after capturing faces
            except Exception as e:
                logging.error(f"Error generating face encodings: {e}")
                break

        # Add a "Stop" button to break the loop manually
        if st.button("Stop Capture"):
            break

    cap.release()
    return face_encodings, face_locations


def cluster_faces(face_encodings, eps=0.6, min_samples=2):
    """
    Cluster detected faces into groups of distinct individuals using DBSCAN.
    """
    if not face_encodings:
        logging.warning("No face encodings provided for clustering.")
        return 0, []

    db = DBSCAN(eps=eps, min_samples=min_samples, metric="euclidean")
    cluster_labels = db.fit_predict(face_encodings)

    num_people = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)  # -1 is noise
    logging.info(f"Identified {num_people} distinct individual(s).")
    return num_people, cluster_labels


def create_kdtree(database_encodings):
    # Explicitly check for an empty list
    if len(database_encodings) == 0:
        logging.error("Empty database encodings provided. Cannot create KD-Tree.")
        return None

    try:
        from sklearn.neighbors import KDTree
        return KDTree(database_encodings)
    except Exception as e:
        logging.error(f"Error creating KD-Tree: {e}")
        return None


def match_faces_with_database(captured_faces):
    """
    Match captured face encodings with entries in the database using a KD-Tree.
    """
    # Retrieve all face encodings and user details from the database
    cursor.execute("SELECT user_id, name, student_face FROM students")
    students = cursor.fetchall()

    if not students:
        logging.warning("No students found in the database.")
        return []

    database_encodings = []
    user_info = []

    for student in students:
        user_id, name, stored_face_encoding = student
        if stored_face_encoding:
            try:
                # Log the raw stored encoding data
                logging.debug(f"Processing face encoding for {name}, user_id: {user_id}")
                
                # Deserialize face encoding from BLOB to numpy array
                stored_encoding = np.frombuffer(stored_face_encoding, dtype=np.float64)
                
                # Verify the shape and size of the encoding
                if stored_encoding.size != 128:  # Expected size of face encoding
                    logging.warning(f"Face encoding for {name} seems to be an invalid size: {stored_encoding.size}")
                    continue

                database_encodings.append(stored_encoding)
                user_info.append((user_id, name))
            except Exception as e:
                logging.error(f"Error processing face encoding for {name}: {e}")

    # Log the number of valid encodings retrieved
    logging.info(f"Retrieved {len(database_encodings)} valid face encodings from the database.")

    if not database_encodings:
        logging.warning("No valid face encodings found in the database.")
        return []

    # Build a KD-Tree for efficient matching
    kdtree = create_kdtree(np.array(database_encodings))

    matched_students = []
    for captured_face in captured_faces:
        # Find the nearest neighbor in the database
        dist, index = kdtree.query([captured_face], k=1)
        if dist[0][0] <= 0.6:  # Match threshold
            matched_students.append(user_info[index[0][0]])
            logging.info(f"Match found: {user_info[index[0][0]]}")

    return matched_students


# Load the pre-trained MiDaS model for depth estimation on appropriate device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = torch.hub.load("intel-isl/MiDaS", "MiDaS_small")
model.eval().to(device)
def capture_face():
    st.write("Automatically turnig on your camera to capture the face.")
    cap = cv2.VideoCapture(0)  # Open the camera
    
    # Check if the camera is successfully opened
    if not cap.isOpened():
        st.error("Could not open camera.")
        return None

    st_frame = st.image([])

    captured_face = None  # Variable to store the captured face

    while True:
        ret, frame = cap.read()
        
        # Check if frame was successfully captured
        if not ret or frame is None or frame.size == 0:
            st.error("Failed to capture frame from the camera.")
            break
        
        st_frame.image(frame, channels="BGR")

        # Convert to RGB for face recognition
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_image)
        
        # If at least one face is detected, capture the first one
        if len(face_locations) > 0:
            captured_face = frame
            st.write("Face captured successfully!")
            break  # Exit the loop once a face is captured

    cap.release()  # Release the camera

    if captured_face is None:
        st.error("No valid face detected. Try again.")
        return None

    # Check if captured face is valid before proceeding with depth estimation
    if captured_face is None or captured_face.size == 0:
        st.error("Captured face is empty or invalid.")
        return None

    # Depth estimation: Convert the captured frame to RGB for MiDaS model
    rgb_frame = cv2.cvtColor(captured_face, cv2.COLOR_BGR2RGB)

    # Define the transformation (resize and normalization)
    transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize(384),  # Ensure it resizes to 384x384
    transforms.CenterCrop(384),  # Ensure the size matches the expected dimensions
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

    # Apply the transformations
    input_tensor = transform(rgb_frame).unsqueeze(0)

    # Predict the depth
    with torch.no_grad():
        depth_map = model(input_tensor)

    # Normalize the depth map for display
    depth_map = depth_map.squeeze().cpu().numpy()
    depth_map = cv2.normalize(depth_map, None, 0, 255, cv2.NORM_MINMAX)
    depth_map = np.uint8(depth_map)

    # Show depth map for debugging (optional)
    st.image(depth_map, channels="GRAY", caption="Depth Map")

    # Check if the depth map has sufficient variation (meaningful 3D object)
    depth_variation = np.std(depth_map)

    # Enhance the check to account for larger regions
    mean_depth = np.mean(depth_map)
    depth_threshold = 80  # Adjust threshold for a more reliable check

    # Check if depth variation and mean depth are consistent with 3D face
    if depth_variation < depth_threshold or mean_depth < 20:
        st.error("Depth variation too low or invalid depth detected! This might be a 2D image.")
        captured_face = None
        return None

    return captured_face  # Return the captured frame if everything is valid

# Preprocess face image to get encoding
def get_face_encoding(image):
    # Check if the image is None or empty
    if image is None or image.size == 0:
        st.error("Failed to capture face image. The image is empty.")
        return None
    
    # Convert the image to RGB (required by face_recognition)
    try:
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    except cv2.error as e:
        st.error(f"OpenCV error during color conversion: {e}")
        return None
    
    # Detect face locations
    face_locations = face_recognition.face_locations(rgb_image)
    
    if len(face_locations) == 0:
        st.error("No face detected. Try again!")
        return None
    
    # Get face encodings for the detected faces
    face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
    
    if len(face_encodings) > 0:
        return face_encodings[0]  # Return the encoding of the first detected face
    else:
        st.error("No face encoding found.")
        return None
    
def authenticate_with_face(captured_encoding, stored_encoding, threshold=0.6):
    # Calculate the Euclidean distance between the two encodings
    distance = euclidean(captured_encoding, stored_encoding)

    # Log the distance for debugging purposes
    st.write(f"Distance between captured and stored encoding: {distance}")

    # Compare the distance with a threshold
    if distance < threshold:
        return True
    return False
def fetch_user_agent_and_ip():
    """
    Automatically fetch User-Agent and IP from the client using an API and browser headers.
    Stores these values in the session state for easy access.
    """
    if "user_agent" not in st.session_state or "ip_address" not in st.session_state:
        try:
            # Fetch User-Agent via headers
            user_agent = st.session_state.get("user_agent", "unknown_agent")
            
            # Use external API to fetch IP
            response = requests.get("https://api64.ipify.org?format=json")
            ip_address = response.json().get("ip", "unknown_ip")

            # Save to session state
            st.session_state["user_agent"] = user_agent
            st.session_state["ip_address"] = ip_address

        except Exception as e:
            st.error(f"Failed to fetch User-Agent or IP: {e}")

def get_device_uuid():
    """
    Generate a unique identifier for the device accessing the Streamlit app.
    Automatically detects User-Agent and IP for mobile/desktop devices.
    """
    try:
        # Fetch User-Agent from session state
        user_agent = st.session_state.get("user_agent", "unknown_agent")

        # Fetch the client's public IP address
        ip_address = st.session_state.get("ip_address", "unknown_ip")

        # Default values for device attributes
        device_brand, device_model, os_version = "Unknown", "Unknown Model", "Unknown OS"

        # Parse User-Agent for mobile-specific information
        if "iPhone" in user_agent or "iPad" in user_agent:
            device_brand = "Apple"
            device_model = user_agent.split('(')[-1].split(';')[0]
            os_version = "iOS " + user_agent.split("CPU iPhone OS ")[-1].split(' ')[0]
        elif "Android" in user_agent:
            device_brand = "Android"
            device_model = user_agent.split('Build/')[0].split(' ')[-1]
            os_version = "Android " + user_agent.split('Android ')[-1].split(' ')[0]

        # Additional attributes
        node_name = platform.node()  # Hostname
        mac_address = uuid.getnode()  # MAC address

        # Generate a unique identifier by hashing key attributes
        unique_str = f"{device_brand}-{device_model}-{os_version}-{node_name}-{mac_address}-{ip_address}"
        device_uuid = hashlib.sha256(unique_str.encode()).hexdigest()

        st.success(f"Device ID generated successfully: {device_uuid}")
        return device_uuid

    except Exception as e:
        st.error(f"Error generating device ID: {e}")
        return None

def get_precise_location(api_key=None):
    if api_key:
        # Google Maps Geocode API URL
        google_maps_url = f'https://maps.googleapis.com/maps/api/geocode/json?latlng={{LATITUDE}},{{LONGITUDE}}&key={api_key}'
        
        # For now, we'll use some dummy coordinates (you can replace this with dynamic geolocation)
        latitude, longitude = 22.5726, 88.3639  # Example: Coordinates for Kolkata, India

        # Request to Google Maps Geocode API to fetch the precise address
        try:
            st.info("Requesting location from Google Maps API...")
            response = requests.get(google_maps_url.format(LATITUDE=latitude, LONGITUDE=longitude))

            if response.status_code == 200:
                data = response.json()
                if 'results' in data and len(data['results']) > 0:
                    # Parsing the address components
                    address_components = data['results'][0]['address_components']
                    full_address = {
                        'street_number': '',
                        'street_name': '',
                        'city': '',
                        'state': '',
                        'country': '',
                        'postal_code': ''
                    }

                    for component in address_components:
                        types = component['types']
                        if 'street_number' in types:
                            full_address['street_number'] = component['long_name']
                        elif 'route' in types:
                            full_address['street_name'] = component['long_name']
                        elif 'locality' in types:
                            full_address['city'] = component['long_name']
                        elif 'administrative_area_level_1' in types:
                            full_address['state'] = component['long_name']
                        elif 'country' in types:
                            full_address['country'] = component['long_name']
                        elif 'postal_code' in types:
                            full_address['postal_code'] = component['long_name']

                    detailed_address = (
                        f"Street: {full_address['street_number']} {full_address['street_name']}, "
                        f"City: {full_address['city']}, "
                        f"State: {full_address['state']}, "
                        f"Country: {full_address['country']}, "
                        f"Postal Code: {full_address['postal_code']}"
                    )
                    st.success("Google Maps API used successfully.")
                    return detailed_address
                else:
                    st.warning("Google Maps API did not return a valid address.")
                    return "Error fetching precise location from Google Maps API."
            else:
                st.error(f"Google Maps API request failed with status code {response.status_code}.")
                return "Error with Google Maps API request."
        except requests.exceptions.RequestException as e:
            st.error(f"Google Maps API request failed: {str(e)}")
            return "Error with Google Maps API request."

    # If no API key is provided, use ipinfo.io as a fallback
    else:
        url = 'https://ipinfo.io/json'  # Using ipinfo.io API to get location details
        try:
            st.info("Requesting location from ipinfo.io as fallback...")
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                city = data.get('city', 'Unknown city')  # Fetch city name
                st.info("Using ipinfo.io as fallback for location as Google maps API is unavailable.")
                return city
            else:
                st.error("Error fetching location from ipinfo.io.")
                return "Error fetching location."
        except requests.exceptions.RequestException as e:
            st.error(f"ipinfo.io request failed: {str(e)}")
            return "Error with ipinfo.io request."

# Get available Bluetooth devices using Flask API
def get_ble_signal_from_api():
    """
    Fetch BLE signals by making a GET request to the Flask BLE API server.
    Replace the URL with your Flask server's actual endpoint.
    """
    try:
        url = "http://127.0.0.1:5000"  # Replace with your Flask API URL
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()  # Parse and return the JSON response from the Flask server
        else:
            st.error(f"Failed to fetch BLE devices. Status Code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to the BLE API: {e}")
        return None

def get_current_period():
    """
    Get the current active period based on the current time.
    This function maps current time to the relevant period.
    """
    period_times = {
        "Period 1": ("09:30", "10:20"),
        "Period 2": ("10:20", "11:10"),
        "Period 3": ("11:10", "12:00"),
        "Period 4": ("12:00", "12:50"),
        "Period 5": ("13:20", "14:30"),
        "Period 6": ("14:30", "15:20"),
        "Period 7": ("15:20", "16:10")
    }

    current_time = datetime.now().time()

    # Convert current_time to minutes for easier comparison
    current_minutes = current_time.hour * 60 + current_time.minute

    for period, times in period_times.items():
        start_time = datetime.strptime(times[0], "%H:%M").time()
        end_time = datetime.strptime(times[1], "%H:%M").time()

        # Convert start_time and end_time to minutes
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute

        # Check if current time is within the period's range
        if start_minutes <= (current_minutes + current_time.second / 60) <= end_minutes:
            return period

    return None

# Streamlit UI
st.title("ADVANCED STUDENT ATTENDANCE SYSTEM")
st.subheader("developed by Debojyoti Ghosh")

menu = st.sidebar.selectbox("Menu", ["Home", "Register", "Student Login", "Admin Login","Admin Management","Lab Examination System"])

if menu == "Home":
    st.write("Welcome to the Student Management System!")

# Assume get_device_ip() and get_device_uuid() are defined elsewhere in your code.

elif menu == "Register":
    st.header("Student Registration")

    # Initialize session state variables for OTP and verification
    if "email_otp" not in st.session_state:
        st.session_state.email_otp = None
    if "email_verified" not in st.session_state:
        st.session_state.email_verified = False

    # Registration Form
    with st.form("registration_form"):
        # Input fields for student details
        st.subheader("Student Details")
        name = st.text_input("Name")
        roll = st.text_input("Roll Number")
        section = st.text_input("Section")
        email = st.text_input("Email")  # Use this email for OTP verification
        enrollment_no = st.text_input("Enrollment Number")
        year = st.text_input("Year")
        semester = st.text_input("Semester")
        user_id = st.text_input("User ID")
        password = st.text_input("Password", type="password")

        st.subheader("Email Verification")
        if not st.session_state.email_verified:
            # Send OTP Button
            if st.form_submit_button("Send OTP"):
                if email:
                    otp = str(np.random.randint(100000, 999999))
                    st.session_state.email_otp = otp

                    # SMTP Configuration
                    smtp_server = 'smtp-relay.brevo.com'
                    smtp_port = 587
                    smtp_user = '823c6b001@smtp-brevo.com'
                    smtp_password = '6tOJHT2F4x8ZGmMw'
                    from_email = 'debojyotighoshmain@gmail.com'

                    try:
                        # Send OTP via email
                        message = MIMEMultipart()
                        message["From"] = from_email
                        message["To"] = email
                        message["Subject"] = "Your OTP for Student Registration"

                        body = f"Your OTP for registration is: {otp}\n\nPlease enter this OTP to verify your email."
                        message.attach(MIMEText(body, "plain"))

                        with smtplib.SMTP(smtp_server, smtp_port) as server:
                            server.starttls()
                            server.login(smtp_user, smtp_password)
                            server.sendmail(from_email, email, message.as_string())

                        st.success(f"OTP sent to {email}. Please check your email.")
                    except Exception as e:
                        st.error(f"Failed to send OTP: {e}")
                else:
                    st.error("Please enter a valid email address.")

        # OTP Verification
        if st.session_state.email_otp and not st.session_state.email_verified:
            otp_input = st.text_input("Enter the OTP sent to your email")
            if st.form_submit_button("Verify OTP"):
                if otp_input == st.session_state.email_otp:
                    st.session_state.email_verified = True
                    st.success("Email verified successfully! You can proceed with registration.")
                else:
                    st.error("Invalid OTP. Please try again.")

        # Registration Button
        if st.session_state.email_verified:
            st.subheader("Complete Registration")
            if st.form_submit_button("Register"):
                fetch_user_agent_and_ip()

                # Fetch the device ID (UUID based)
                device_id = get_device_uuid()

                if not device_id:
                    st.error("Could not fetch device ID, registration cannot proceed.")
                else:
                    face_image = capture_face()  # Capture face using the defined function

                    if face_image is not None:
                        face_encoding = get_face_encoding(face_image)  # Get face encoding

                        if face_encoding is not None:
                            # Check if the device or user ID already exists
                            cursor.execute("SELECT * FROM students WHERE device_id = ?", (device_id,))
                            if cursor.fetchone():
                                st.error("This device has already registered. Only one registration is allowed per device.")
                            else:
                                cursor.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
                                if cursor.fetchone():
                                    st.error("User ID already exists.")
                                else:
                                    # Insert into database
                                    cursor.execute("""
                                    INSERT INTO students (user_id, password, name, roll, section, email, enrollment_no, year, semester, device_id, student_face)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (user_id, password, name, roll, section, email, enrollment_no, year, semester, device_id, face_encoding.tobytes()))
                                    conn.commit()
                                    st.success("Registration successful!")
                        else:
                            st.error("Failed to encode the captured face.")
                    else:
                        st.error("Failed to capture face. Please try again.")


elif menu == "Student Login":
    st.header("Student Login")
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    
    fetch_user_agent_and_ip()
    
    # Fetch the device ID (IP address)
    device_id = get_device_uuid() 

    if not device_id:
        st.error("Could not fetch device Id. Login cannot proceed.")
    
    if st.button("Login") and not st.session_state.get('bluetooth_selected', False):
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND password = ?", (user_id, password))
        user = cursor.fetchone()
        if user:
            if user[9] == device_id:  # Match device_id from IP address
                location = get_precise_location()
                st.write(f"Your current location is: {location}")
                if location and "Kolkata" in location:
                    time.sleep(2)
                    st.success("user ID and password verification succesfull!")
                    time.sleep(2)
                    st.success("you have passed the location check and your location has been verified")
                    time.sleep(2)
                    st.success(f"your registered device has been verified successfully")
                    time.sleep(2)
                    st.success(f"Login successful! Welcome, {user[2]}")
                    
                    # Check for Bluetooth signal during login session
                    st.info("just a step away from your dashboard !! Scanning for Bluetooth devices...")

                    # Replace the original BLE signal detection logic
                    ble_signal = get_ble_signal_from_api()
                    
                    if ble_signal:
                        if isinstance(ble_signal, dict) and "status" in ble_signal:
                            # Handle API status response (e.g., Bluetooth is off)
                            st.warning(ble_signal["status"])
                        else:
                            st.info("Bluetooth devices found. Listing all available devices...")
                            
                            # Display all available Bluetooth devices
                            st.write("Available Bluetooth devices:")
                            for device_name, mac_address in ble_signal.items():
                                st.write(f"Device Name: {mac_address}, MAC Address: {device_name}")
                    
                            # Automatically check if the required Bluetooth device is in the list
                            required_device_name = "76:6B:E1:0F:92:09"
                            required_mac_id = "INSTITUTE BLE VERIFY SIGNA"  # Replace with the actual MAC address if known
                    
                            found_device = False
                            for device_name, mac_address in ble_signal.items():
                                if required_device_name in device_name or mac_address == required_mac_id:
                                    st.success(f"Required Bluetooth device found! Device Name: {device_name}, MAC Address: {mac_address}")
                                    found_device = True
                                    break
                    
                            if found_device:
                                # Save user login to session state
                                st.session_state.logged_in = True
                                st.session_state.user_id = user_id  # Replace with actual user ID if available
                                st.session_state.bluetooth_selected = True  # Mark Bluetooth as selected

                            # Define constant for period times
                            PERIOD_TIMES = {
                                "Period 1": ("09:30", "10:20"),
                                "Period 2": ("10:20", "11:10"),
                                "Period 3": ("11:10", "12:00"),
                                "Period 4": ("12:00", "12:50"),
                                "Period 5": ("13:40", "14:30"),
                                "Period 6": ("14:30", "15:20"),
                                "Period 7": ("15:20", "16:10")
                            }

                            # Function to get the current period based on time
                            def get_current_period() -> Optional[str]:
                                now = datetime.now().strftime("%H:%M")  # Current time in HH:MM format
                                for period, (start, end) in PERIOD_TIMES.items():
                                    if start <= now <= end:
                                        return period
                                return None

                            # Attendance Marking Logic
                            current_period = get_current_period()

                            if current_period:
                                st.success(f"Attendance for {current_period} is being marked automatically. Waiting for confirmation from the server!")

                                current_day = datetime.now().strftime("%A")  # Get current weekday name

                                try:
                                    # Fetch timetable details
                                    cursor.execute("""
                                        SELECT subject, teacher FROM timetable 
                                        WHERE day = ? AND period = ?
                                    """, (current_day, current_period))
                                    period_details = cursor.fetchone()

                                    if period_details:
                                        subject, teacher = period_details
                                        st.info(f"Subject: {subject} | Teacher: {teacher}")

                                        # Check for existing attendance record
                                        cursor.execute("""
                                            SELECT * FROM attendance WHERE student_id = ? AND date = ? AND day = ?
                                        """, (user_id, datetime.now().strftime('%Y-%m-%d'), current_day))
                                        existing_record = cursor.fetchone()

                                        period_column = f"period_{list(PERIOD_TIMES.keys()).index(current_period) + 1}"

                                        if existing_record:
                                            # Update attendance
                                            cursor.execute(f"""
                                                UPDATE attendance 
                                                SET {period_column} = 1, subject = ?, teacher = ?
                                                WHERE student_id = ? AND date = ? AND day = ?
                                            """, (subject, teacher, user_id, datetime.now().strftime('%Y-%m-%d'), current_day))
                                            conn.commit()
                                            st.success(f"Attendance updated for {current_period} ({subject}) by {teacher} on {current_day}!")
                                        else:
                                            # Prepare attendance data
                                            attendance_data = {period: 0 for period in PERIOD_TIMES.keys()}
                                            attendance_data[current_period] = 1

                                            # Insert new attendance record
                                            cursor.execute("""
                                                INSERT INTO attendance (student_id, date, day, period_1, period_2, period_3, period_4, period_5, period_6, period_7, subject, teacher)
                                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """, (user_id, datetime.now().strftime('%Y-%m-%d'), current_day, *attendance_data.values(), subject, teacher))
                                            conn.commit()
                                            st.success(f"Attendance for {current_period} ({subject}) by {teacher} marked successfully for {current_day}!")
                                    else:
                                        st.error(f"No timetable entry found for {current_period} on {current_day}.")
                                except Exception as e:
                                    st.error(f"An error occurred: {e}")
                            else:
                                st.warning("No active class period at the moment.")

                        else:
                            st.error("Required Bluetooth device not found. Login failed.")
                    else:
                        st.error("No Bluetooth devices found.")
                else:
                    st.error("You must be in Kolkata to login.")
            else:
                st.error("Device ID does not match.")
        else:
            st.error("Invalid user ID or password.")

    # Display student attendance search form
    if st.session_state.get('logged_in', False):
        st.subheader("Search Attendance Records")

        # Dynamically generate the last 10 years for selection
        current_year = datetime.now().year
        years = [str(year) for year in range(current_year, current_year - 10, -1)]

        # Select Year, Month, Day of the Week, and Date
        year = st.selectbox("Select Year", years)
        month = st.selectbox("Select Month", [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ])
        day_of_week = st.selectbox("Select Day of the Week (Optional)", [
            "Any", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
        ])
        include_date = st.checkbox("Filter by Specific Date?")
        selected_date = None

        # Allow date selection if checkbox is enabled
        if include_date:
            selected_date = st.date_input("Select Date")

        # Convert month to numeric value for filtering
        month_num = datetime.strptime(month, "%B").month

        # Search Button
        if st.button("Search Attendance"):
            # Build SQL query dynamically based on user input
            query = """
                SELECT * FROM attendance 
                WHERE student_id = ? 
                AND strftime('%Y', date) = ? 
                AND strftime('%m', date) = ?
            """
            params = [st.session_state.user_id, year, f"{month_num:02d}"]

            # Add day of the week filter if selected
            if day_of_week != "Any":
                query += " AND day = ?"
                params.append(day_of_week)
            
            # Add specific date filter if enabled
            if include_date and selected_date:
                query += " AND date = ?"
                params.append(selected_date.strftime('%Y-%m-%d'))

            # Execute the query
            cursor.execute(query, tuple(params))
            attendance_records = cursor.fetchall()

            # Display attendance records or a message if none are found
            if attendance_records:
                st.write("### Attendance Records Found:")
                for record in attendance_records:
                    st.write(f"Date: {record[1]}, Day: {record[2]}")
                    for i in range(3, 10):  # Periods are in columns 3 to 9
                        st.write(f"Period {i-2}: {'Present' if record[i] == 1 else 'Absent'}")
            else:
                st.write("No attendance records found for the selected filters.")
                
        # Add dispute submission section
        st.subheader("Raise Attendance Dispute")
        st.info("If you feel there's a discrepancy in your attendance, please submit a dispute.")

        # Dispute Form
        dispute_reason = st.text_area("Describe the issue")
        submit_dispute = st.button("Submit Dispute")

        if submit_dispute:
            if dispute_reason.strip():
                # Insert dispute into the database
                cursor.execute("""
                    INSERT INTO disputes (student_id, date, reason)
                    VALUES (?, ?, ?)
                """, (user_id, datetime.now().strftime('%Y-%m-%d'), dispute_reason))
                conn.commit()
                st.success("Your dispute has been submitted successfully!")
            else:
                st.error("Please provide a reason for the dispute.")

        # Logout button
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.bluetooth_selected = False  # Reset Bluetooth selection flag
            st.session_state.attendance_saved = False  # Reset attendance saved flag
            st.rerun()

# Admin Login Flow with Face Recognition
if menu == "Admin Login":
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False  # Initially, no one is logged in
    
    if 'admin_id' not in st.session_state:  # Ensure admin_id is initialized
        st.session_state.admin_id = None

    if st.session_state.logged_in:
        # Admin is logged in, show the dashboard
        st.warning("id and password verification in progress!")
        time.sleep(2)
        st.warning("face id verification in progress!")

        # Admin Profile Section
        if st.session_state.admin_id:  # Check if admin_id exists before querying the database
            try:
                cursor.execute("SELECT * FROM admin_profile WHERE admin_id = ?", (st.session_state.admin_id,))
                profile = cursor.fetchone()
                
                if profile:
                    time.sleep(5)
                    st.info("the id and password verification is successfull!")
                    time.sleep(2)
                    st.info("the face id verification is successfull!")
                    time.sleep(2)
                    st.success("Admin login successful!")
                    st.success(f"welcome back to your dashboard, {profile[1]}!!")
                    st.header("Admin Profile")
                    st.write(f"Name: {profile[1]}")
                    st.write(f"Department: {profile[2]}")
                    st.write(f"Designation: {profile[3]}")
                    st.write(f"Email: {profile[4]}")
                    st.write(f"Phone: {profile[5]}")

                    # Option to update profile
                    st.write("---")
                    st.subheader("Update Profile")
                    new_name = st.text_input("New Name", profile[1])
                    new_department = st.text_input("New Department", profile[2])
                    new_designation = st.text_input("New Designation", profile[3])
                    new_email = st.text_input("New Email", profile[4])
                    new_phone = st.text_input("New Phone", profile[5])
                    st.error("please note : for safety admind id and password needs to be changed together and once changed the profile setup has to be done again!!")
                    # Option to update Admin ID and Password
                    new_admin_id = st.text_input("New Admin ID", st.session_state.admin_id)
                    new_password = st.text_input("New Password", type="password")

                    # Option to update face data
                    st.write("---")
                    st.subheader("Update Face Data")
                    if st.button("Capture New Face"):
                        captured_face = capture_face()  # Function to capture face image from webcam
                        st.image(captured_face, caption="Captured New Face")
                        new_face_encoding = get_face_encoding(captured_face)  # Function to get face encoding

                        if new_face_encoding is None:
                            st.error("Face capture failed. Please try again.")
                        else:
                            st.success("New face data captured successfully!")

                    if st.button("Save Changes"):
                        # Check if new admin ID already exists
                        cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (new_admin_id,))
                        existing_admin = cursor.fetchone()

                        if existing_admin and new_admin_id != st.session_state.admin_id:
                            st.error("Admin ID already exists. Please choose a different one.")
                        else:
                            # Update admin profile
                            cursor.execute(""" 
                                UPDATE admin_profile 
                                SET name = ?, department = ?, designation = ?, email = ?, phone = ?, face_encoding = ? 
                                WHERE admin_id = ? 
                            """, (
                                new_name,
                                new_department,
                                new_designation,
                                new_email,
                                new_phone,
                                sqlite3.Binary(new_face_encoding.tobytes()) if 'new_face_encoding' in locals() else profile[6],  # Update face encoding only if captured
                                st.session_state.admin_id,
                            ))

                            # Update admin login credentials (admin ID and password)
                            if new_admin_id != st.session_state.admin_id:
                                cursor.execute(""" 
                                    UPDATE admin 
                                    SET admin_id = ?, password = ? 
                                    WHERE admin_id = ? 
                                """, (new_admin_id, new_password, st.session_state.admin_id))
                                st.session_state.admin_id = new_admin_id  # Update the session ID

                            conn.commit()
                            st.success("Profile, login credentials, and face data updated successfully!")

                else:
                    st.error("Admin profile not found. Please complete your profile setup.")
                    st.write("---")
                    st.subheader("Complete Profile Setup")

                    # If no profile found, allow admin to create one
                    new_name = st.text_input("Name")
                    new_department = st.text_input("Department")
                    new_designation = st.text_input("Designation")
                    new_email = st.text_input("Email")
                    new_phone = st.text_input("Phone")
                    new_admin_id = st.text_input("Admin ID")
                    new_password = st.text_input("Password", type="password")

                    # Capture face image and encode during profile creation
                    if st.button("Capture Face"):
                        captured_face = capture_face()  # Capture face from webcam
                        st.image(captured_face, caption="Captured Face for Profile")
                        captured_encoding = get_face_encoding(captured_face)  # Get encoding of captured face
                        if captured_encoding is None:
                            st.error("Face capture failed. Please try again.")
                        else:
                            # Save profile and face encoding to the database
                            if new_name and new_department and new_designation and new_email and new_phone and new_admin_id and new_password:
                                cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (new_admin_id,))
                                existing_admin = cursor.fetchone()
                                if existing_admin:
                                    st.error("Admin ID already exists. Please choose a different one.")
                                else:
                                    # Save face encoding as BLOB in the database
                                    cursor.execute(""" 
                                        INSERT INTO admin_profile (admin_id, name, department, designation, email, phone, face_encoding) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?) 
                                    """, (new_admin_id, new_name, new_department, new_designation, new_email, new_phone, sqlite3.Binary(captured_encoding.tobytes())))

                                    cursor.execute(""" 
                                        INSERT INTO admin (admin_id, password) 
                                        VALUES (?, ?) 
                                    """, (new_admin_id, new_password))

                                    conn.commit()
                                    st.success("Profile and login credentials created successfully!")
                                    # Send the confirmation email
                                    send_confirmation_email(new_email, new_name)
                            else:
                                st.error("Please fill all fields.")

            except sqlite3.OperationalError as e:
                st.error(f"Database error: {e}")
            except sqlite3.IntegrityError as e:
                st.error(f"Integrity error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

        st.markdown("---")
        # Advanced Search Section for Registered Students
        st.subheader("Advanced Search for Registered Students")

        # Search Inputs for Student Filters
        student_name = st.text_input("Search by Name")
        student_id = st.text_input("Search by Student ID")
        student_department = st.text_input("Search by Department")
        student_year = st.selectbox("Search by Year", ["All", "1st Year", "2nd Year", "3rd Year", "4th Year"])

        # Search Inputs for Date, Month, Year, and Day (Attendance filters)
        search_by_month = st.selectbox("Search by Month", ["All", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])
        search_by_year = st.selectbox("Search by Year (Attendance)", ["All", "2024", "2023", "2022", "2021", "2020"])
        search_by_day = st.selectbox("Search by Day", ["All", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        search_by_date = st.date_input("Search by Date", value=None)

        if st.button("Search"):
            # Start building SQL query
            query = """
                SELECT DISTINCT students.* 
                FROM students
                LEFT JOIN attendance ON students.user_id = attendance.student_id
                WHERE 1=1
            """
            params = []

            # Apply filters based on input
            if student_name:
                query += " AND students.name LIKE ?"
                params.append(f"%{student_name}%")

            if student_id:
                query += " AND students.user_id = ?"
                params.append(student_id)

            if student_department:
                query += " AND students.section LIKE ?"
                params.append(f"%{student_department}%")

            if student_year and student_year != "All":
                query += " AND students.year = ?"
                params.append(student_year)

            if search_by_month != "All":
                query += " AND strftime('%m', attendance.date) = ?"
                month_number = {
                    "January": "01", "February": "02", "March": "03", "April": "04", 
                    "May": "05", "June": "06", "July": "07", "August": "08", 
                    "September": "09", "October": "10", "November": "11", "December": "12"
                }[search_by_month]
                params.append(month_number)

            if search_by_year != "All":
                query += " AND strftime('%Y', attendance.date) = ?"
                params.append(search_by_year)

            if search_by_day != "All":
                query += " AND strftime('%w', attendance.date) = ?"
                day_number = {
                    "Sunday": "0", "Monday": "1", "Tuesday": "2", "Wednesday": "3", 
                    "Thursday": "4", "Friday": "5", "Saturday": "6"
                }[search_by_day]
                params.append(day_number)

            if search_by_date:
                query += " AND attendance.date = ?"
                params.append(search_by_date.strftime('%Y-%m-%d'))

            # Execute the query based on the applied filters
            cursor.execute(query, params)
            filtered_students = cursor.fetchall()

            # Display filtered students and their details
            st.subheader("Filtered Students")
            if filtered_students:
                for student in filtered_students:
                    student_id = student[0]
                    student_name = student[2]
                    st.write(f"Student ID: {student_id}, Name: {student_name}")

                    # Display student's full details
                    st.write(f"User ID: {student[0]}")
                    st.write(f"Name: {student[2]}")
                    st.write(f"Roll: {student[3]}")
                    st.write(f"Section: {student[4]}")
                    st.write(f"Email: {student[5]}")
                    st.write(f"Enrollment No: {student[6]}")
                    st.write(f"Year: {student[7]}")
                    st.write(f"Semester: {student[8]}")
                    st.write(f"Device ID: {student[9]}")

                    # Fetch the student's year and semester
                    cursor.execute("""
                        SELECT year, semester 
                        FROM students 
                        WHERE user_id = ?
                    """, (student_id,))
                    student_details = cursor.fetchone()

                    if student_details:
                        year, semester = student_details

                        # Fetch semester details
                        cursor.execute("""
                            SELECT total_classes, total_periods 
                            FROM semester_dates 
                            WHERE year = ? AND semester = ?
                        """, (year, semester))
                        semester_details = cursor.fetchone()

                        if semester_details:
                            total_classes_in_semester, total_periods_in_semester = semester_details

                            # Fetch attendance records for the student
                            cursor.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,))
                            attendance_records = cursor.fetchall()

                            if attendance_records:
                                total_classes_attended = len(attendance_records)  # Number of days attended
                                total_periods_attended = sum(
                                    sum(1 if record[i] == 1 else 0 for i in range(3, 10))  # Count periods attended
                                    for record in attendance_records
                                )

                                # Calculate attendance percentage
                                if total_periods_in_semester > 0:  # Avoid division by zero
                                    attendance_percentage = (total_periods_attended / total_periods_in_semester) * 100
                                else:
                                    attendance_percentage = 0.0

                                # Display attendance summary
                                st.subheader(f"Attendance Report for {student_id}")
                                st.write(f"Total Classes in Semester: {total_classes_in_semester}")
                                st.write(f"Total Periods in Semester: {total_periods_in_semester}")
                                st.write(f"Classes Attended: {total_classes_attended}")
                                st.write(f"Periods Attended: {total_periods_attended}")
                                st.write(f"Attendance Percentage: {attendance_percentage:.2f}%")

                                # Detailed attendance
                                for record in attendance_records:
                                    st.write(f"Date: {record[1]}, Day: {record[2]}")
                                    for i in range(3, 10):  # Columns for periods
                                        period_status = 'Present' if record[i] == 1 else ('Absent' if record[i] == 0 else 'N/A')
                                        st.write(f"Period {i-2}: {period_status}")
                            else:
                                st.write("No attendance records found for this student.")
                        else:
                            st.write("Semester details not available. Cannot calculate attendance percentage.")
                    else:
                        st.write("Student details not found.")
                        
        st.markdown("---")
        st.markdown("---")
        # Section to View All Registered Students and Attendance Analysis
        st.subheader("Registered Students and Attendance Analysis")

        # Fetch all registered students
        cursor.execute("SELECT * FROM students")
        students = cursor.fetchall()

        if students:
            for student in students:
                student_id = student[0]
                student_name = student[2]
                st.write(f"Student ID: {student_id}, Name: {student_name}")

                # Button to view student details with a unique key
                if st.button(f"View Details for {student_name}", key=f"details_{student_id}"):
                    # Display student details
                    st.write(f"Roll: {student[3]}")
                    st.write(f"Section: {student[4]}")
                    st.write(f"Email: {student[5]}")
                    st.write(f"Enrollment No: {student[6]}")
                    st.write(f"Year: {student[7]}")
                    st.write(f"Semester: {student[8]}")

                    # Fetch the student's face encoding from the database
                    face_encoding_blob = student[10]  # Assuming 'student_face' is at index 10

                    if face_encoding_blob:
                        # Show a message indicating that face data is available
                        st.write("Face data is available for this student.")
                        
                        # Optional: Display the raw face encoding as text (for debugging purposes)
                        st.write(f"Raw Face Encoding (first 10 values): {list(face_encoding_blob[:10])}")
                    else:
                        st.write("No face data available for this student.")
                        
                    # Attendance Analysis for the student
                    st.subheader(f"Attendance Analysis for {student_name}")

                    # Fetch the student's year and semester from the students table
                    cursor.execute("""
                        SELECT year, semester FROM students WHERE user_id = ?
                    """, (student_id,))
                    student_semester = cursor.fetchone()

                    if student_semester:
                        year, semester = student_semester

                        # Fetch total_classes and total_periods from semester_dates table based on year and semester
                        cursor.execute("""
                            SELECT total_classes, total_periods
                            FROM semester_dates 
                            WHERE year = ? AND semester = ?
                        """, (year, semester))
                        semester_details = cursor.fetchone()

                        if semester_details:
                            total_classes_in_semester, total_periods_in_semester = semester_details
                            
                            # Fetch the student's attendance records
                            cursor.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,))
                            attendance_records = cursor.fetchall()

                            if attendance_records:
                                total_days = len(attendance_records)  # Number of days attended
                                
                                # Calculate total periods attended, treating None as 0 (absent)
                                total_present = sum(
                                    sum(1 if record[i] == 1 else 0 for i in range(3, 10))  # Sum the periods attended (1 for present, 0 for absent)
                                    for record in attendance_records
                                )

                                # Calculate attendance percentage based on total periods in the semester
                                attendance_percentage = (total_present / total_periods_in_semester) * 100

                                # Display detailed information for the attendance analysis
                                st.write(f"**Total class days in Semester:** {total_classes_in_semester}")
                                st.write(f"**Total Periods or classes in Semester:** {total_periods_in_semester}")
                                st.write(f"**Total Attendance Days:** {total_days}")
                                st.write(f"**Total Periods or classes Attended:** {total_present}")
                                st.write(f"**Attendance Percentage:** {attendance_percentage:.2f}%")

                                # Display Attendance Breakdown (Day-wise and Period-wise)
                                st.write("### Detailed Attendance Breakdown:")
                                for record in attendance_records:
                                    st.write(f"**Date:** {record[1]}, **Day:** {record[2]}")  # Date and Day
                                    
                                    # Fetch subject and teacher information for each period
                                    for i in range(3, 10):  # Assuming period information starts from index 3 to 9
                                        if record[i] == 1:  # Check if the student was present
                                            period = f"Period {i-2}"  # Periods are labeled starting from Period 1
                                            
                                            # Fetch the subject and teacher for the corresponding period
                                            period_number = i - 2  # Adjust the index to match periods 1-7
                                            
                                            cursor.execute("""
                                                SELECT subject, teacher 
                                                FROM timetable
                                                WHERE day = ? AND period = ?
                                            """, (record[2], period))  # Using the formatted period like "Period 1"
                                            
                                            timetable_entry = cursor.fetchone()
                                            
                                            if timetable_entry:
                                                subject, teacher = timetable_entry
                                                st.write(f"**{period}:** Present | **Subject:** {subject} | **Teacher:** {teacher}")
                                            else:
                                                st.write(f"**{period}:** Present | No timetable entry found.")


                                        else:
                                            period = f"Period {i-2}"  # Periods are labeled starting from 1
                                            st.write(f"**{period}:** Absent")
                            else:
                                st.write("No attendance records found for this student.")
                        else:
                            st.write("No semester details found for this student.")
                    else:
                        st.write("No year or semester information found for this student.")


                # Initialize session state for form visibility
                if f"form_shown_{student_id}" not in st.session_state:
                    st.session_state[f"form_shown_{student_id}"] = False

                # Button to toggle form visibility
                if st.button(f"View/Edit Details for {student_name}", key=f"edit_{student_id}"):
                    st.session_state[f"form_shown_{student_id}"] = not st.session_state[f"form_shown_{student_id}"]

                # Display the form if it's active
                if st.session_state[f"form_shown_{student_id}"]:
                    st.header(f"Edit Details for {student_name}")

                    # Pre-fill existing student data into form fields
                    new_name = st.text_input("Name", value=student[2], key=f"name_{student_id}")
                    new_roll = st.text_input("Roll Number", value=student[3], key=f"roll_{student_id}")
                    new_section = st.text_input("Section", value=student[4], key=f"section_{student_id}")
                    new_email = st.text_input("Email", value=student[5], key=f"email_{student_id}")
                    new_enrollment_no = st.text_input("Enrollment Number", value=student[6], key=f"enrollment_{student_id}")
                    new_year = st.selectbox(
                        "Year", ["1", "2", "3", "4"],
                        index=["1", "2", "3", "4"].index(student[7]),
                        key=f"year_{student_id}"
                    )
                    new_semester = st.text_input("Semester", value=student[8], key=f"semester_{student_id}")
                    new_user_id = st.text_input("User ID", value=student[0], key=f"user_id_{student_id}")
                    new_password = st.text_input("Password", type="password", value=student[1], key=f"password_{student_id}")
                    new_device_ip = st.text_input("Device IP", value=student[9], key=f"device_ip_{student_id}")

                    # Option to display existing face encoding
                    st.write("Current captured face encoding:")
                    if student[10]:
                        try:
                            # Show face encoding as a string (numerical array or list)
                            face_encoding_str = str(student[10])  # Convert the face encoding to a string format
                            st.text_area("Face Encoding", value=face_encoding_str, height=200)  # Display it as a text area
                        except Exception as e:
                            st.error(f"Failed to display the current face encoding: {str(e)}")

                    st.write("You can capture a new face for this student.")

                    new_face_encoding = None

                    # Save changes button - automatically handles face capture and data update
                    if st.button("Save Changes", key=f"save_changes_{student_id}"):
                        try:
                            # Step 1: Capture the new face image
                            st.write("Capturing new face data...")
                            new_face_image = capture_face()  # Capture face image using previously defined function
                            if new_face_image is not None:
                                new_face_encoding = get_face_encoding(new_face_image)  # Get face encoding from captured image
                                if new_face_encoding is not None:
                                    st.success("New face captured and encoded successfully!")
                                else:
                                    st.error("Failed to encode the captured face.")

                            else:
                                st.error("Failed to capture the face.")


                            # Step 2: Validate required fields
                            if not new_user_id or not new_password or not new_device_ip:
                                st.error("User ID, Password, and Device IP are required fields.")
                        

                            # Step 3: Prepare face encoding blob for updating
                            face_encoding_blob = new_face_encoding.tobytes() if new_face_encoding is not None else student[10]  # Retain old encoding if no new face captured

                            # Step 4: Update student details in the database, including the face encoding
                            st.write("Updating student details...")
                            cursor.execute("""
                                UPDATE students
                                SET user_id = ?, password = ?, device_id = ?, name = ?, roll = ?, section = ?, email = ?, enrollment_no = ?, year = ?, semester = ?, student_face = ?
                                WHERE user_id = ?
                            """, (
                                new_user_id, new_password, new_device_ip, new_name, new_roll, new_section,
                                new_email, new_enrollment_no, new_year, new_semester, face_encoding_blob, student_id
                            ))
                            conn.commit()

                            # Step 5: Confirm success
                            if cursor.rowcount > 0:
                                st.success(f"Details for {student_name} and face encoding have been successfully updated!")
                            else:
                                st.error("No changes were made. Please verify the details.")

                            # Close the form after successful update
                            st.session_state[f"form_shown_{student_id}"] = False

                        except Exception as e:
                            st.error(f"An error occurred while updating the details: {str(e)}")

                    # Cancel button to hide the form
                    if st.button("Cancel", key=f"cancel_edit_{student_id}"):
                        st.session_state[f"form_shown_{student_id}"] = False



                # Button to deregister a student
                if st.button(f"Deregister {student_name}", key=f"deregister_{student_id}"):
                    cursor.execute("DELETE FROM students WHERE user_id = ?", (student_id,))
                    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
                    conn.commit()
                    st.warning(f"Student {student_name} has been deregistered!")

                # Initialize session state for attendance form visibility
                if f"attendance_form_shown_{student_id}" not in st.session_state:
                    st.session_state[f"attendance_form_shown_{student_id}"] = False

                # Button to toggle attendance form visibility
                if st.button(f"Overwrite Attendance for {student_name}", key=f"toggle_attendance_{student_id}"):
                    st.session_state[f"attendance_form_shown_{student_id}"] = not st.session_state[f"attendance_form_shown_{student_id}"]

                # Display the attendance form if it's active
                if st.session_state[f"attendance_form_shown_{student_id}"]:
                    st.header(f"Manually Update Attendance for {student_name}")
                    st.error("PLEASE NOTE : only overwrite attendance in case of student unable to give attendance though present because any action otherwise can lead to improper calculation of attendance!!!!")

                    # Date input for selecting the attendance date
                    selected_date = st.date_input("Select Date", key=f"attendance_date_{student_id}")
                    selected_day = selected_date.strftime("%A")

                    # Fetch existing attendance for the selected date
                    cursor.execute("""
                        SELECT period_1, period_2, period_3, period_4, period_5, period_6, period_7
                        FROM attendance
                        WHERE student_id = ? AND date = ?
                    """, (student_id, selected_date))
                    existing_attendance = cursor.fetchone()

                    # Pre-fill attendance status for each period
                    attendance = []
                    for period in range(1, 8):
                        prefilled_status = "Present" if existing_attendance and existing_attendance[period - 1] == 1 else "Absent"
                        status = st.selectbox(
                            f"Period {period} Status",
                            ["Absent", "Present"],
                            index=["Absent", "Present"].index(prefilled_status),
                            key=f"attendance_period_{period}_{student_id}"
                        )
                        attendance.append(1 if status == "Present" else 0)

                    # Save changes button
                    if st.button("Save Attendance", key=f"save_attendance_{student_id}"):
                        try:
                            # Update attendance in the database
                            cursor.execute("""
                                REPLACE INTO attendance (student_id, date, day, period_1, period_2, period_3, period_4, period_5, period_6, period_7)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (student_id, selected_date, selected_day, *attendance))
                            conn.commit()

                            # Confirm success
                            if cursor.rowcount > 0:
                                st.success(f"Attendance for {student_name} on {selected_date} has been successfully updated!")
                            else:
                                st.error("No changes were made. Please verify the details.")

                            # Close the form after successful update
                            st.session_state[f"attendance_form_shown_{student_id}"] = False
                        except Exception as e:
                            st.error(f"An error occurred while updating the attendance: {str(e)}")

                    # Cancel button to hide the form
                    if st.button("Cancel", key=f"cancel_attendance_{student_id}"):
                        st.session_state[f"attendance_form_shown_{student_id}"] = False

        else:
            st.write("No registered students found.")
            
        st.markdown("---")
        # Helper function to style paragraphs
        def styled_paragraph(text, style):
            return Paragraph(text, style)

        # Function to generate PDF
        def generate_pdf(students, start_date, end_date, admin_details, total_classes_in_semester, total_periods_in_semester):
            # Create a file-like buffer to hold the PDF
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)

            # Styles
            styles = getSampleStyleSheet()
            title_style = styles['Title']
            heading_style = styles['Heading1']
            normal_style = styles['Normal']

            # PDF content
            content = []

            # Generate PDF content
            content.append(Paragraph(f"Generated by: {admin_details.get('name', 'Unknown')}", normal_style))
            content.append(Paragraph(f"Department: {admin_details.get('department', 'Not Present')}", normal_style))
            content.append(Paragraph(f"Designation: {admin_details.get('designation', 'Not Present')}", normal_style))
            content.append(Paragraph(f"Email: {admin_details.get('email', 'Unknown')}", normal_style))
            content.append(Paragraph(f"Phone: {admin_details.get('phone', 'Not Present')}", normal_style))
            content.append(Paragraph(f"Date Range: {start_date} to {end_date}", normal_style))

            # Add semester details
            content.append(Paragraph(f"Semester: {start_date.year} - {end_date.year}", normal_style))
            content.append(Paragraph(f"Total Class days: {total_classes_in_semester}", normal_style))
            content.append(Paragraph(f"Total Periods: {total_periods_in_semester}", normal_style))

            # Add student attendance report
            for student in students:
                content.append(Paragraph(f"Student: {student['name']}", heading_style))

                # Table data for attendance
                data = [["Date", "Attendance"]]
                total_classes = 0
                total_present_classes = 0
                total_periods = 0
                total_present_periods = 0
                attendance_periods = {}

                for record in student['attendance']:
                    record_date = datetime.strptime(record['date'], '%Y-%m-%d').date() if isinstance(record['date'], str) else record['date']
                    if start_date <= record_date <= end_date:
                        data.append([record_date, "Present" if record['status'] else "Absent"])
                        total_classes += 1
                        if record['status']:
                            total_present_classes += 1
                        total_periods += 1
                        if record['status']:
                            total_present_periods += 1
                        period_key = record_date.strftime('%Y-%m')
                        if period_key not in attendance_periods:
                            attendance_periods[period_key] = {"present": 0, "total": 0}
                        attendance_periods[period_key]["total"] += 1
                        if record['status']:
                            attendance_periods[period_key]["present"] += 1

                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                content.append(table)

                attendance_percentage_classes = (total_present_classes / total_classes_in_semester) * 100 if total_classes_in_semester > 0 else 0
                attendance_percentage_periods = (total_present_periods / total_periods_in_semester) * 100 if total_periods_in_semester > 0 else 0
                pass_fail_classes = "Pass" if attendance_percentage_classes >= 75 else "Fail"
                pass_fail_periods = "Pass" if attendance_percentage_periods >= 75 else "Fail"

                content.append(Paragraph(f"Attendance Percentage (Class days): {attendance_percentage_classes:.2f}%", normal_style))
                content.append(Paragraph(f"Pass/Fail Status (Class days): {pass_fail_classes}", normal_style))
                content.append(Paragraph(f"Attendance Percentage (Periods): {attendance_percentage_periods:.2f}%", normal_style))
                content.append(Paragraph(f"Pass/Fail Status (Periods): {pass_fail_periods}", normal_style))

                period_data = [["Period", "Present", "Total"]]
                for period, values in attendance_periods.items():
                    period_data.append([period, values["present"], values["total"]])

                period_table = Table(period_data)
                period_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                content.append(period_table)

                fig, ax = plt.subplots(figsize=(6, 4))
                periods = list(attendance_periods.keys())
                presents = [attendance_periods[period]["present"] for period in periods]
                total = [attendance_periods[period]["total"] for period in periods]

                ax.bar(periods, presents, label="Present", alpha=0.7, color='g')
                ax.bar(periods, [total[i] - presents[i] for i in range(len(periods))], label="Absent", alpha=0.7, color='r')
                ax.set_xlabel('Period')
                ax.set_ylabel('Attendance Count')
                ax.set_title(f"Attendance Analysis for {student['name']}")
                ax.legend()

                img_buffer = BytesIO()
                plt.savefig(img_buffer, format="png")
                img_buffer.seek(0)
                content.append(Paragraph("<br/>", normal_style))
                content.append(Image(img_buffer, width=400, height=300))

            doc.build(content)
            buffer.seek(0)
            return buffer

        # Section to select students and time period
        st.subheader("Generate Attendance Report (PDF)")

        # Admin details (fetched from the database)
        cursor.execute("SELECT * FROM admin_profile WHERE admin_id = '1'")  # Fetch admin details based on admin_id
        admin_data = cursor.fetchone()

        # Ensure admin_data is fetched correctly
        if admin_data:
            admin_details = {
                "name": admin_data['name'],
                "department": admin_data['department'],
                "designation": admin_data['designation'],
                "email": admin_data['email'],
                "phone": admin_data['phone']
            }
        else:
            admin_details = {
                "name": "Unknown",
                "department": "Unknown",
                "designation": "Unknown",
                "email": "Unknown",
                "phone": "Unknown"
            }

        # Filter by time period (start and end date)
        start_date = st.date_input("Select Start Date", date(2024, 1, 1))
        end_date = st.date_input("Select End Date", date(2024, 12, 31))

        # Dropdown to select semester and year
        cursor.execute("SELECT DISTINCT year, semester FROM semester_dates")
        semester_data = cursor.fetchall()
        semesters = [(f"Year: {item[0]}, Semester: {item[1]}", item[0], item[1]) for item in semester_data]
        selected_semester = st.selectbox("Select Semester", semesters, format_func=lambda x: x[0])

        # Ensure selected_semester has a valid value
        if selected_semester:
            # Unpack year and semester from the selected value
            year, semester = selected_semester[1], selected_semester[2]
            
            # Fetch the total_classes and total_periods for the selected semester
            cursor.execute("""
                SELECT total_classes, total_periods 
                FROM semester_dates 
                WHERE year = ? AND semester = ?
            """, (year, semester))
            semester_details = cursor.fetchone()

            if semester_details:
                total_classes_in_semester = semester_details[0]  # First element in tuple
                total_periods_in_semester = semester_details[1]  # Second element in tuple
            else:
                total_classes_in_semester = 0
                total_periods_in_semester = 0
        else:
            st.error("Please select a valid semester.")


        # Dropdown to select students
        cursor.execute("SELECT * FROM students")
        students_data = cursor.fetchall()
        student_names = [f"{student[2]} ({student[0]})" for student in students_data]
        selected_students = st.multiselect("Select Students", student_names)

        # Button to generate PDF
        if st.button("Generate Attendance Report"):
            # Filter the selected students' data
            students = []
            for student in students_data:
                if f"{student[2]} ({student[0]})" in selected_students:
                    student_id = student[0]
                    cursor.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,))
                    attendance_records = cursor.fetchall()
                    attendance = [{"date": record[1], "status": sum(x or 0 for x in record[3:]) > 0} for record in attendance_records]
                    students.append({
                        "name": student[2],
                        "attendance": attendance
                    })
            
            if students:
                # Generate and download the PDF
                pdf_buffer = generate_pdf(students, start_date, end_date, admin_details, total_classes_in_semester, total_periods_in_semester)
                
                # Allow the admin to download the PDF
                st.download_button(
                    label="Download Attendance Report",
                    data=pdf_buffer,
                    file_name="attendance_report.pdf",
                    mime="application/pdf"
                )
            else:
                st.error("No students selected or no attendance records available for the selected period.")

                
        st.markdown("---")    
        # Function to calculate the number of weekdays (excluding weekends) between two dates
        def calculate_weekdays(start_date, end_date):
            weekdays = 0
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:  # 0-4 are weekdays (Monday to Friday)
                    weekdays += 1
                current_date += timedelta(days=1)
            return weekdays

        # Function to calculate the total number of periods (assuming 7 periods per weekday)
        def calculate_total_periods(start_date, end_date, total_holidays):
            weekdays = calculate_weekdays(start_date, end_date)
            total_periods = weekdays * 7  # Assuming 7 periods per day
            total_periods -= total_holidays * 7  # Subtract holidays (7 periods per holiday)
            return total_periods

        # Function to display the form for adding start and end times for the selected semester
        def display_semester_form():
            st.title("Add Semester Details")

            # Dropdown for selecting Year (1-4)
            year = st.selectbox("Select Year", [1, 2, 3, 4])

            # Dropdown for selecting Semester (1 or 2)
            semester = st.selectbox("Select Semester", [1, 2, 3, 4, 5, 6, 7, 8])

            # Input fields for start date, end date, and total holidays
            start_date = st.date_input(f"Start Date (Year {year}, Semester {semester})")
            end_date = st.date_input(f"End Date (Year {year}, Semester {semester})")
            total_holidays = st.number_input(f"Total Holidays (Year {year}, Semester {semester})", min_value=0, value=0)

            # Button to save the semester details
            if st.button(f"Save Semester {semester} for Year {year}"):

                # Ensure that start_date is before end_date
                if start_date > end_date:
                    st.error("Start date cannot be after end date.")
                    return
                
                total_periods = calculate_total_periods(start_date, end_date, total_holidays)
                total_classes = total_periods // 7  # Assuming 7 periods per class

                # Save the data to the database
                try:
                    cursor.execute("""
                        INSERT INTO semester_dates (year, semester, start_date, end_date, total_holidays, total_classes, total_periods)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (year, semester, start_date, end_date, total_holidays, total_classes, total_periods))
                    conn.commit()

                    # Show confirmation
                    st.success(f"Semester {semester} for Year {year} saved successfully with {total_classes} class days and {total_periods} periods or classes.")
                    st.write(f"Total Class days: {total_classes}, Total Periods or classes: {total_periods}")
                except Exception as e:
                    st.error(f"Error saving semester details: {e}")

        # Call the function to display the form
        display_semester_form()
        
        st.markdown("---")
        # Create a Streamlit interface
        st.title("Face Recognition - Single beam Student ID Matching and Attendance Marking system")

        # Button to start capture and retry mechanism
        retry = True
        retry_count = 0  # Counter to make button keys unique

        while retry:
            # Add a button to start the face capture process with a unique key
            start_button = st.button("Start Capture / reset field for New Shot", key=f"start_capture_button_{retry_count}")

            if start_button:
                # Capture and detect faces
                captured_faces, face_locations = capture_and_detect_faces()

                if captured_faces:
                    # Cluster detected faces to group them by person
                    num_people, cluster_labels = cluster_faces(captured_faces)

                    st.write(f"Detected {len(captured_faces)} faces in total.")
                    st.write(f"Identified {num_people} distinct people.")

                    # Match captured faces with the database
                    matched_students = match_faces_with_database(captured_faces)

                    if matched_students:
                        logging.info(f"Matched Students: {matched_students}")

                        # Get current period and mark attendance
                        current_period = get_current_period()

                        if current_period:
                            st.success(f"Attendance for {current_period} is being marked automatically, waiting for confirmation from server!")

                            # Define period times for attendance marking
                            period_times = {
                                "Period 1": ("09:30", "10:20"),
                                "Period 2": ("10:20", "11:10"),
                                "Period 3": ("11:10", "12:00"),
                                "Period 4": ("12:00", "12:50"),
                                "Period 5": ("13:20", "14:30"),
                                "Period 6": ("14:30", "15:20"),
                                "Period 7": ("15:20", "16:10")
                            }

                            # Initialize attendance data for all periods as False (Absent)
                            attendance_data = {period: False for period in period_times.keys()}

                            # Mark the current period as present (True)
                            attendance_data[current_period] = True

                            # Define the days array
                            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

                            # Automatically set the current day from the system date
                            current_day = datetime.now().strftime("%A")  # Get the full weekday name (e.g., "Monday", "Tuesday")

                            # Check if today is a weekday
                            if current_day in days:
                                # Display the day selector with the current day pre-selected
                                selected_day = st.selectbox("Select Day", days, index=days.index(current_day))  # Pre-select current day

                                for user_id, name in matched_students:
                                    # Check if attendance record already exists for the student
                                    cursor.execute("""
                                        SELECT * FROM attendance WHERE student_id = ? AND date = ? AND day = ?
                                    """, (user_id, datetime.now().strftime('%Y-%m-%d'), selected_day))
                                    existing_record = cursor.fetchone()

                                    if existing_record:
                                        # Update the attendance for the current period
                                        period_column = f"period_{list(period_times.keys()).index(current_period) + 1}"
                                        cursor.execute(f"""
                                            UPDATE attendance 
                                            SET {period_column} = 1
                                            WHERE student_id = ? AND date = ? AND day = ?
                                        """, (user_id, datetime.now().strftime('%Y-%m-%d'), selected_day))
                                        conn.commit()
                                        st.success(f"Attendance updated for {name} in {current_period} on {selected_day}!")
                                    else:
                                        # Insert new attendance record
                                        cursor.execute("""
                                            INSERT INTO attendance (student_id, date, day, period_1, period_2, period_3, period_4, period_5, period_6, period_7)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (user_id, datetime.now().strftime('%Y-%m-%d'), selected_day, *attendance_data.values()))
                                        conn.commit()
                                        st.success(f"Attendance for {name} marked successfully in {current_period} on {selected_day}!")
                                        st.write("Face capture process completed.")
                            else:
                                # Display a warning if today is a weekend
                                st.warning(f"No attendance marking allowed on {current_day} as it is a holiday.")
                                st.write("Face capture process completed.")
                        else:
                            st.warning("No active class period at the moment.")
                            st.write("Face capture process completed.")
                    else:
                        logging.info("No matches found.")
                        st.write("Face capture process completed.")
                else:
                    logging.info("No faces detected or processed.try again!")
                    st.write("Face capture process completed.")

            # Option to retry capturing faces if needed with a unique key
            retry_count += 1  # Increment retry counter for unique key
            retry = st.button("enhanced scanning coming soon!!", key=f"retry_capture_button_{retry_count}")

            if not retry:
                st.write("mark attendance of upto 30 people!")
                
        st.markdown("---")       
        # Streamlit interface
        st.title("Debarred Students - Attendance Alert System")

        # Fetch students with attendance below 75%
        low_attendance_students = get_low_attendance_students()

        if low_attendance_students:
            st.subheader("Debarred Students")
            for student in low_attendance_students:
                user_id, name, email, attendance_percentage = student
                st.write(f"Name: {name}, Email: {email}, Attendance: {attendance_percentage:.2f}%")
                
                # Button to send alert email
                if st.button(f"Alert {name}", key=f"alert_{user_id}"):
                    send_email(email, name, attendance_percentage)
        else:
            st.info("No students have attendance below the threshold.")
            
        st.markdown("---")   
         # Notification Center for Disputes
        st.subheader("Dispute Notifications")
        st.info("Below are the pending disputes raised by students.")

        # Fetch pending disputes with student details
        cursor.execute("""
            SELECT d.id, d.student_id, s.name, s.enrollment_no, s.roll, d.date, d.reason 
            FROM disputes d
            JOIN students s ON d.student_id = s.user_id
            WHERE d.status = 'Pending'
        """)
        disputes = cursor.fetchall()

        if disputes:
            for dispute in disputes:
                dispute_id, student_id, student_name, enrollment_no, roll_no, date, reason = dispute
                st.write(f"**Dispute ID:** {dispute_id}")
                st.write(f"**Student ID:** {student_id}")
                st.write(f"**Name:** {student_name}")
                st.write(f"**Enrollment No.:** {enrollment_no}")
                st.write(f"**Roll No.:** {roll_no}")
                st.write(f"**Date:** {date}")
                st.write(f"**Reason:** {reason}")

                # Button to mark the dispute as resolved
                if st.button(f"Resolve Dispute {dispute_id}"):
                    cursor.execute("UPDATE disputes SET status = 'Resolved' WHERE id = ?", (dispute_id,))
                    conn.commit()
                    st.success(f"Dispute ID {dispute_id} marked as resolved.")
        else:
            st.write("No pending disputes.")
            
        st.markdown("---")
        # Timetable Entry Form
        st.title("Timetable Management")

        with st.form("add_timetable"):
            day = st.selectbox("Select Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            period = st.selectbox("Select Period", ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5", "Period 6", "Period 7"])
            subject = st.text_input("Subject Name")
            teacher = st.text_input("Teacher Name")
            submit = st.form_submit_button("Add Entry")

            if submit:
                if day and period and subject and teacher:
                    cursor.execute("""
                        INSERT INTO timetable (day, period, subject, teacher) 
                        VALUES (?, ?, ?, ?)
                    """, (day, period, subject, teacher))
                    conn.commit()
                    st.success(f"Timetable entry added: {day} - {period} - {subject} - {teacher}")
                else:
                    st.error("All fields are required!")

        # View Timetable
        st.header("View Timetable")
        selected_day = st.selectbox("Select Day to View", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        if selected_day:
            cursor.execute("""
                SELECT period, subject, teacher FROM timetable WHERE day = ? ORDER BY period
            """, (selected_day,))
            timetable = cursor.fetchall()

            if timetable:
                st.table(timetable)
            else:
                st.warning(f"No timetable found for {selected_day}.")
            
        # Logout Button
        if st.button("Logout"):
            st.session_state.logged_in = False  # Reset login state
            st.session_state.admin_id = None  # Clear stored admin ID
            st.session_state.admin_name = None  # Clear stored admin name
            st.session_state.profile_data = None  # Clear profile data
            st.rerun()  # Refresh the page after logout

    else:
        # Admin Login Form
        st.header("Admin Login")
        admin_id = st.text_input("Admin ID", key="login_admin_id")
        admin_password = st.text_input("Admin Password", type="password", key="login_admin_password")

        # Session State Initialization
        if "otp" not in st.session_state:
            st.session_state.otp = None
        if "otp_verified" not in st.session_state:
            st.session_state.otp_verified = False
        if "reset_admin_id" not in st.session_state:
            st.session_state.reset_admin_id = None

        # Forgot Password Form
        with st.form("Forgot Password Form"):
            st.subheader("Forgot Password?")
            reset_admin_id = st.text_input("Enter your Admin ID to reset password", key="reset_admin_id_input")
            submit_forgot_password = st.form_submit_button("Generate OTP")

            if submit_forgot_password:
                cursor.execute("SELECT email FROM admin_profile WHERE admin_id = ?", (reset_admin_id,))
                admin_email = cursor.fetchone()

                if admin_email:
                    admin_email = admin_email[0]
                    otp = str(np.random.randint(100000, 999999))  # Generate 6-digit OTP
                    st.session_state.otp = otp  # Store OTP in session state
                    st.session_state.reset_admin_id = reset_admin_id  # Save the admin ID for verification

                    # SMTP Configuration
                    smtp_server = 'smtp-relay.brevo.com'
                    smtp_port = 587
                    smtp_user = '823c6b001@smtp-brevo.com'
                    smtp_password = '6tOJHT2F4x8ZGmMw'
                    from_email = 'debojyotighoshmain@gmail.com'

                    # Send OTP to email
                    try:
                        message = MIMEMultipart()
                        message["From"] = from_email
                        message["To"] = admin_email
                        message["Subject"] = "Your OTP for Admin Login"

                        body = f"Your OTP for Admin login is: {otp}\n\nPlease use this OTP to complete your login."
                        message.attach(MIMEText(body, "plain"))

                        with smtplib.SMTP(smtp_server, smtp_port) as server:
                            server.starttls()
                            server.login(smtp_user, smtp_password)
                            server.sendmail(from_email, admin_email, message.as_string())

                        st.success(f"OTP sent to {admin_email}. Please check your email.")
                    except Exception as e:
                        st.error(f"Error sending OTP: {e}")
                else:
                    st.error("Admin ID not found in the database.")

        # OTP Verification
        if st.session_state.otp:
            with st.form("OTP Verification Form"):
                st.subheader("OTP Verification")
                otp_input = st.text_input("Enter the OTP sent to your email", key="otp_input")
                submit_otp = st.form_submit_button("Verify OTP")

                if submit_otp:
                    if otp_input == st.session_state.otp:
                        st.success("OTP verified successfully! Proceeding to face verification.")
                        st.session_state.otp_verified = True  # Mark OTP as verified
                    else:
                        st.error("Invalid OTP. Please try again.")

        # Face Verification After OTP
        if st.session_state.otp_verified:
            st.info("Face verification required.")
            
            # Only trigger face capture after OTP is verified
            if st.session_state.otp_verified:
                captured_face = capture_face()
                captured_encoding = get_face_encoding(captured_face)

                if captured_encoding is not None and len(captured_encoding) > 0:
                    cursor.execute("SELECT face_encoding FROM admin_profile WHERE admin_id = ?", (st.session_state.reset_admin_id,))  # Get admin profile
                    stored_encoding_data = cursor.fetchone()

                    if stored_encoding_data:
                        stored_encoding = np.frombuffer(stored_encoding_data[0], dtype=np.float64)
                        if authenticate_with_face(captured_encoding, stored_encoding):
                            st.session_state.logged_in = True
                            st.session_state.admin_id = st.session_state.reset_admin_id
                            st.success("Login successful with OTP and face verification!")
                            st.rerun()  # Refresh the page to load the admin dashboard
                        else:
                            st.error("Face recognition failed. Try again!")
                    else:
                        st.error("No stored face encoding found for this admin ID.")
                else:
                    st.error("Face capture failed. Please try again.")

        # Regular Admin Login (this part will be triggered only if OTP is not required)
        if st.button("Login"):
            cursor.execute("SELECT * FROM admin WHERE admin_id = ? AND password = ?", (admin_id, admin_password))
            admin = cursor.fetchone()

            if admin:
                # Check if admin account is active
                cursor.execute("SELECT active FROM admin WHERE admin_id = ?", (admin_id,))
                active_status = cursor.fetchone()

                if active_status and active_status[0] == 0:  # Account is deactivated
                    st.error("Your account has been deactivated. Please contact the system administrator.")
                else:
                    # Check if admin profile exists
                    cursor.execute("SELECT * FROM admin_profile WHERE admin_id = ?", (admin_id,))
                    profile = cursor.fetchone()

                    if profile:
                        # Admin profile exists, proceed with face verification
                        captured_face = capture_face()
                        captured_encoding = get_face_encoding(captured_face)

                        if captured_encoding is not None and len(captured_encoding) > 0:
                            cursor.execute("SELECT face_encoding FROM admin_profile WHERE admin_id = ?", (admin_id,))
                            stored_encoding_data = cursor.fetchone()

                            if stored_encoding_data:
                                stored_encoding = np.frombuffer(stored_encoding_data[0], dtype=np.float64)

                                if authenticate_with_face(captured_encoding, stored_encoding):
                                    st.session_state.logged_in = True
                                    st.session_state.admin_id = admin_id
                                    st.session_state.admin_name = admin[0]
                                    st.session_state.profile_data = True
                                    st.success("Login successful!")
                                    st.rerun()  # Refresh the page to show the admin dashboard
                                else:
                                    st.error("Face recognition failed as your face didn't match our records. Try again!")
                            else:
                                st.error("No stored face encoding found.")
                        else:
                            st.error("Face capture failed. Please try again.")
                    else:
                        # Admin profile does not exist, login without face ID verification
                        st.session_state.logged_in = True
                        st.session_state.admin_id = admin_id
                        st.session_state.admin_name = admin[0]
                        st.session_state.profile_data = False  # Profile not found, so no profile data
                        st.success("Login successful! Profile not found, proceed to complete your profile setup.")
                        st.rerun()  # Refresh the page to show the admin dashboard
            else:
                st.error("Invalid admin ID or password.")

                
# Section for Admin Management
elif menu == "Admin Management":
    st.header("Admin Account Management")

    # Session state for OTP, Admin login, and Admin credentials
    if "admin_otp" not in st.session_state:
        st.session_state.admin_otp = None
    if "otp_verified" not in st.session_state:
        st.session_state.otp_verified = False
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    # Admin Login (Admin ID & Password)
    if not st.session_state.admin_authenticated:
        st.subheader("Admin Login")

        admin_id = st.text_input("Enter Admin ID")
        admin_password = st.text_input("Enter Admin Password", type="password")

        if st.button("Login"):
            cursor.execute("SELECT * FROM admin WHERE admin_id = ? AND password = ?", (admin_id, admin_password))
            admin_data = cursor.fetchone()
            if admin_data:
                st.session_state.admin_authenticated = True
                st.session_state.logged_in_admin_id = admin_id  # Store logged-in admin ID
                st.success("Login successful.")
            else:
                st.error("Invalid Admin ID or Password.")

    # Admin Management (only available after successful login)
    if st.session_state.admin_authenticated:
        st.subheader("Registered Admin Accounts")

        # Fetch all registered admin accounts
        cursor.execute(""" 
        SELECT a.admin_id, a.active, ap.email 
        FROM admin a 
        LEFT JOIN admin_profile ap ON a.admin_id = ap.admin_id
        """)
        admins = cursor.fetchall()

        if admins:
            for admin in admins:
                admin_id, active, email = admin
                status = "Active" if active else "Inactive"

                col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
                with col1:
                    st.text(f"Admin ID: {admin_id}")
                with col2:
                    st.text(f"Status: {status}")
                with col3:
                    if st.button(f"Request OTP for {admin_id}") and email:
                        # Check if the admin ID is 'admin' (the logged-in admin ID)
                        if admin_id == "admin":
                            # Send OTP to logged-in admin's email
                            logged_in_admin_email = st.session_state.logged_in_admin_id

                            cursor.execute("SELECT email FROM admin_profile WHERE admin_id = ?", (logged_in_admin_email,))
                            logged_in_admin_email_result = cursor.fetchone()
                            logged_in_admin_email = logged_in_admin_email_result[0] if logged_in_admin_email_result else None
                        else:
                            # Send OTP to the respective admin's email
                            logged_in_admin_email = email

                        if logged_in_admin_email:
                            otp = str(np.random.randint(100000, 999999))
                            st.session_state.admin_otp = otp

                            # SMTP Configuration
                            smtp_server = 'smtp-relay.brevo.com'
                            smtp_port = 587
                            smtp_user = '823c6b001@smtp-brevo.com'
                            smtp_password = '6tOJHT2F4x8ZGmMw'
                            from_email = 'debojyotighoshmain@gmail.com'

                            try:
                                message = MIMEMultipart()
                                message["From"] = from_email
                                message["To"] = logged_in_admin_email
                                message["Subject"] = "Admin Action OTP Verification"

                                body = f"Your OTP for the requested admin action is: {otp}\n\nPlease enter this OTP to verify your request."
                                message.attach(MIMEText(body, "plain"))

                                with smtplib.SMTP(smtp_server, smtp_port) as server:
                                    server.starttls()
                                    server.login(smtp_user, smtp_password)
                                    server.sendmail(from_email, logged_in_admin_email, message.as_string())

                                st.success(f"OTP sent to your email {logged_in_admin_email}. Please check your email.")
                            except Exception as e:
                                st.error(f"Failed to send OTP: {e}")
                        else:
                            st.error("No email found for this admin. Cannot send OTP.")

                    # Verify OTP
                    otp_input = st.text_input(f"Enter OTP for {admin_id}", key=f"otp_{admin_id}")
                    if st.button(f"Verify OTP for {admin_id}"):
                        if otp_input == st.session_state.admin_otp:
                            st.session_state.otp_verified = True
                            st.success("OTP verified successfully!")
                        else:
                            st.error("Invalid OTP. Please try again.")

                    # Activate/Deactivate/Remove buttons (only enabled after OTP verification)
                    if st.session_state.otp_verified:
                        if active:
                            if st.button(f"Deactivate {admin_id}"):
                                cursor.execute("UPDATE admin SET active = 0 WHERE admin_id = ?", (admin_id,))
                                cursor.execute("INSERT INTO admin_audit (admin_id, action, timestamp) VALUES (?, 'Deactivated', ?)", (admin_id, datetime.now()))
                                conn.commit()
                                st.success(f"Admin account '{admin_id}' has been deactivated.")
                        else:
                            if st.button(f"Activate {admin_id}"):
                                cursor.execute("UPDATE admin SET active = 1 WHERE admin_id = ?", (admin_id,))
                                cursor.execute("INSERT INTO admin_audit (admin_id, action, timestamp) VALUES (?, 'Activated', ?)", (admin_id, datetime.now()))
                                conn.commit()
                                st.success(f"Admin account '{admin_id}' has been activated.")

                        if st.button(f"Remove {admin_id}"):
                            cursor.execute("DELETE FROM admin WHERE admin_id = ?", (admin_id,))
                            cursor.execute("DELETE FROM admin_profile WHERE admin_id = ?", (admin_id,))
                            cursor.execute("INSERT INTO admin_audit (admin_id, action, timestamp) VALUES (?, 'Removed', ?)", (admin_id, datetime.now()))
                            conn.commit()
                            st.success(f"Admin account '{admin_id}' and its profile have been removed.")
        else:
            st.info("No admin accounts found.")

        # Activity History Section
        st.subheader(f"Activity History for Admin: {st.session_state.logged_in_admin_id}")

        # Fetch the audit trail for the logged-in admin
        cursor.execute("""
        SELECT action, timestamp FROM admin_audit
        WHERE admin_id = ?
        ORDER BY timestamp DESC
        """, (st.session_state.logged_in_admin_id,))
        activities = cursor.fetchall()

        if activities:
            for activity in activities:
                action, timestamp = activity
                st.write(f"**Action:** {action}")
                st.write(f"**Timestamp:** {timestamp}")
                st.write("-" * 50)
        else:
            st.info("No activity history found for this admin.")

        # Option to reset the default admin account if needed
        st.subheader("Restore Default Admin Account")
        if st.button("Request OTP for Restore Default Admin"):
            # Generate OTP for restoring the default admin account
            otp = str(np.random.randint(100000, 999999))
            st.session_state.admin_otp = otp

            # Fetch the logged-in admin's email
            cursor.execute("SELECT email FROM admin_profile WHERE admin_id = ?", (st.session_state.logged_in_admin_id,))
            admin_email = cursor.fetchone()
            admin_email = admin_email[0] if admin_email else None

            if admin_email:
                # Send OTP to the logged-in admin
                try:
                    message = MIMEMultipart()
                    message["From"] = from_email
                    message["To"] = admin_email
                    message["Subject"] = "Admin Action OTP Verification"

                    body = f"Your OTP for restoring the default admin account is: {otp}\n\nPlease enter this OTP to verify your request."
                    message.attach(MIMEText(body, "plain"))

                    with smtplib.SMTP(smtp_server, smtp_port) as server:
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        server.sendmail(from_email, admin_email, message.as_string())

                    st.success(f"OTP sent to your email {admin_email}. Please check.")
                except Exception as e:
                    st.error(f"Failed to send OTP: {e}")
            else:
                st.error("No email found for the logged-in admin.")

        otp_input_restore = st.text_input("Enter OTP to Restore Default Admin")
        if st.button("Verify OTP to Restore"):
            if otp_input_restore == st.session_state.admin_otp:
                st.session_state.otp_verified = True
                st.success("OTP verified successfully!")
            else:
                st.error("Invalid OTP. Please try again.")

        if st.session_state.otp_verified:
            if st.button("Restore Default Admin"):
                cursor.execute(""" 
                INSERT OR IGNORE INTO admin (admin_id, password, active) 
                VALUES ('admin', 'admin123', 1)
                """)
                cursor.execute(""" 
                INSERT OR IGNORE INTO admin_profile (admin_id, name, department, designation, email, phone, face_encoding) 
                VALUES ('admin', 'Default Admin', 'IT', 'Administrator', 'defaultadmin@example.com', '1234567890', NULL)
                """)
                cursor.execute("INSERT INTO admin_audit (admin_id, action, timestamp) VALUES ('admin', 'Restored', ?)", (datetime.now(),))
                conn.commit()
                st.success("Default admin account has been restored.")

elif menu == "Lab Examination System" : 
    st.title("AI-Enabled Lab Examination System")
    st.title("AILES")
    st.success("Welcome to the Lab Examination System. Get started with your lab journey!")
    st.info("This system allows you to conduct lab examinations for students.")
    st.info("You can add questions, conduct exams, and view results here with a lot of patented features.")
    # Add a button with a modern design
    st.markdown(
        """
        <style>
        .redirect-button {
            display: inline-block;
            background-color:rgb(16, 55, 117);
            color:rgb(17, 42, 143);
            font-size: 18px;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            border-radius: 5px;
            transition: background-color 0.3s ease;
            box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
        }
        .redirect-button:hover {
            background-color:rgb(136, 41, 173);
            text-decoration: none;
        }
        </style>
        <a href="https://les-beta.netlify.app/" target="_blank" class="redirect-button">Let's Go!</a>
        """,
        unsafe_allow_html=True,
    )
