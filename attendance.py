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

# Database setup
conn = sqlite3.connect("asas.db", check_same_thread=False)
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
    device_id TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (
    admin_id TEXT PRIMARY KEY,
    password TEXT
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
    phone TEXT
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
def get_device_uuid():
    """
    Generate a unique mobile device identifier using mobile-specific attributes like
    device brand, model, operating system, and user-agent.
    """
    try:
        # Get the user-agent string (critical for mobile devices)
        user_agent = st.request.headers.get('User-Agent') if hasattr(st, 'request') else "unknown_agent"
        
        # Extract device and OS information from user-agent (we expect mobile patterns here)
        if user_agent:
            # Common mobile device identifiers (iOS and Android)
            if "iPhone" in user_agent or "iPad" in user_agent:
                device_brand = "Apple"
                device_model = user_agent.split('(')[-1].split(';')[0]  # iPhone model or iPad model
                os_version = "iOS " + user_agent.split('CPU iPhone OS ')[-1].split(' ')[0] if "iPhone" in user_agent else "iPadOS"
            elif "Android" in user_agent:
                device_brand = "Android"
                device_model = user_agent.split('Build/')[0].split(' ')[-1]  # Extracts model name
                os_version = user_agent.split('Android ')[-1].split(' ')[0]
            else:
                device_brand = "Unknown"
                device_model = "Unknown Model"
                os_version = "Unknown OS"
        else:
            device_brand = "Unknown"
            device_model = "Unknown Model"
            os_version = "Unknown OS"

        # Additional device information
        node_name = platform.node()  # Device name or hostname
        mac_address = uuid.getnode()  # MAC address (if available)

        # Fetch the client's IP address (if available in Streamlit)
        ip_address = st.query_params.get('ip', ['unknown_ip'])[0]

        # Combine all the device-specific info into a unique string
        unique_str = f"{device_brand}-{device_model}-{os_version}-{node_name}-{mac_address}-{ip_address}"

        # Hash the string to generate a fixed-length UUID
        device_uuid = hashlib.sha256(unique_str.encode()).hexdigest()

        st.success(f"Mobile Device ID fetched successfully: {device_uuid}")
        return device_uuid
    except Exception as e:
        st.error(f"Failed to fetch mobile device ID: {e}")
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

async def get_ble_signal():
    """
    Get the available Bluetooth Low Energy (BLE) devices in range.
    This function uses BleakScanner to scan for devices and checks if Bluetooth is on.
    """
    try:
        # Try to discover BLE devices
        devices = await BleakScanner.discover()
        
        # If no devices found, Bluetooth is likely on, but no devices are nearby
        ble_signals = {device.address: device.name if device.name else device.address for device in devices}
        
        return ble_signals
    
    except BleakError:
        # If there is an issue discovering devices (Bluetooth might be off)
        return {"status": "Bluetooth is off or unavailable. Please turn on Bluetooth."}
    
    except Exception as e:
        # Generic exception handling for any other unexpected errors
        return {"status": f"An unexpected error occurred or Bluetooth might be off ,please check: {str(e)}"}

def detect_ble_signal():
    """
    Run the BLE signal detection function using asyncio.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_ble_signal())

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
        "Period 5": ("13:40", "14:30"),
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

menu = st.sidebar.selectbox("Menu", ["Home", "Register", "Student Login", "Admin Login"])

if menu == "Home":
    st.write("Welcome to the Student Management System!")

# Assume get_device_ip() and get_device_uuid() are defined elsewhere in your code.

elif menu == "Register":
    st.header("Student Registration")
    name = st.text_input("Name")
    roll = st.text_input("Roll Number")
    section = st.text_input("Section")
    email = st.text_input("Email")
    enrollment_no = st.text_input("Enrollment Number")
    year = st.text_input("Year")
    semester = st.text_input("Semester")

    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")

    # Fetch the device ID (UUID based)
    device_id = get_device_uuid()  # Fetch UUID instead of IP

    if not device_id:
        st.error("Could not fetch device ID, registration cannot proceed.")
    
    if st.button("Register"):
        if device_id:
            # Check if the device has already registered
            cursor.execute("SELECT * FROM students WHERE device_id = ?", (device_id,))
            if cursor.fetchone():
                st.error("This device has already registered. Only one registration is allowed per device.")
            else:
                # Check if the user ID already exists
                cursor.execute("SELECT * FROM students WHERE user_id = ?", (user_id,))
                if cursor.fetchone():
                    st.error("User ID already exists.")
                else:
                    # Insert the new student registration
                    cursor.execute("""
                    INSERT INTO students (user_id, password, name, roll, section, email, enrollment_no, year, semester, device_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (user_id, password, name, roll, section, email, enrollment_no, year, semester, device_id))
                    conn.commit()
                    st.success(f"Registration successful! You are registered with the device ID: {device_id}")
        else:
            st.error("Device ID not found. Cannot register without a valid device.")

elif menu == "Student Login":
    st.header("Student Login")
    user_id = st.text_input("User ID")
    password = st.text_input("Password", type="password")
    
    # Fetch the device ID (IP address)
    device_id = get_device_uuid() 

    if not device_id:
        st.error("Could not fetch device Id. Login cannot proceed.")
    
    if st.button("Login") and not st.session_state.get('bluetooth_selected', False):
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND password = ?", (user_id, password))
        user = cursor.fetchone()
        if user:
            if user[-1] == device_id:  # Match device_id from IP address
                location = get_precise_location()
                st.write(f"Your current location is: {location}")
                if location and "Kolkata" in location:
                    st.success("user ID and password verification succesfull!")
                    st.success("you have passed the location check and your location has been verified")
                    st.success(f"your registered device has been verified successfully")
                    st.success(f"Login successful! Welcome, {user[2]}")
                    
                    # Check for Bluetooth signal during login session
                    st.info("just a step away from your dashboard !! Scanning for Bluetooth devices...")

                    # Get available Bluetooth devices
                    ble_signal = detect_ble_signal()

                    if ble_signal:
                        st.info("Bluetooth devices found. Listing all available devices...")
                        
                        # Display all available Bluetooth devices
                        st.write("Available Bluetooth devices:")
                        for device_name, mac_address in ble_signal.items():
                            st.write(f"Device Name: {device_name}, MAC Address: {mac_address}")

                        # Automatically check if the required Bluetooth device is in the list
                        required_device_name = "6C:E8:C6:75:A1:EA"
                        required_mac_id = "JR_JioSTB-RPCSBJG00013449"  # Replace with the actual MAC address if known

                        found_device = False
                        for device_name, mac_address in ble_signal.items():
                            if required_device_name in device_name or mac_address == required_mac_id:
                                st.success(f"Required Bluetooth device found! Device Name: {device_name}, MAC Address: {mac_address}")
                                found_device = True
                                break

                        if found_device:
                            # Save user login to session state
                            st.session_state.logged_in = True
                            st.session_state.user_id = user_id
                            st.session_state.bluetooth_selected = True  # Mark Bluetooth as selected

                            # Get the current period and mark attendance
                            current_period = get_current_period()
                            if current_period:
                                st.success(f"Attendance for {current_period} is being marked automatically.")
                                
                                # Define period times for attendance marking
                                period_times = {
                                    "Period 1": ("09:30", "10:20"),
                                    "Period 2": ("10:20", "11:10"),
                                    "Period 3": ("11:10", "12:00"),
                                    "Period 4": ("12:00", "12:50"),
                                    "Period 5": ("13:40", "14:30"),
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

                                # Display the day selector with the current day pre-selected
                                selected_day = st.selectbox("Select Day", days, index=days.index(current_day))  # Pre-select current day
                                
                                # Check if attendance record already exists for the student on the same date and day
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
                                    st.success(f"Attendance updated for {current_period} on {selected_day}!")
                                else:
                                    # Insert new attendance record
                                    cursor.execute("""
                                        INSERT INTO attendance (student_id, date, day, period_1, period_2, period_3, period_4, period_5, period_6, period_7)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """, (user_id, datetime.now().strftime('%Y-%m-%d'), selected_day, *attendance_data.values()))
                                    conn.commit()
                                    st.success(f"Attendance for {current_period} marked successfully for {selected_day}!")
                            else:
                                st.warning("No active class period at the moment.")
                        else:
                            st.error("Required Bluetooth device not found. Login failed.")
                    else:
                        st.error("No Bluetooth devices found.")
                else:
                    st.error("You must be in institute of Engineering and managment to login.")
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

        # Select Year, Month, and Day of the Week
        year = st.selectbox("Select Year", years)
        month = st.selectbox("Select Month", [
            "January", "February", "March", "April", "May", "June", 
            "July", "August", "September", "October", "November", "December"
        ])
        day_of_week = st.selectbox("Select Day of the Week", [
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
        ])

        # Convert month to numeric value for filtering
        month_num = datetime.strptime(month, "%B").month

        # Search Button
        if st.button("Search Attendance"):
            cursor.execute("""
                SELECT * FROM attendance 
                WHERE student_id = ? 
                AND strftime('%Y', date) = ? 
                AND strftime('%m', date) = ? 
                AND day = ? 
            """, (st.session_state.user_id, year, f"{month_num:02d}", day_of_week))
            attendance_records = cursor.fetchall()

            if attendance_records:
                for record in attendance_records:
                    st.write(f"Date: {record[1]}, Day: {record[2]}")
                    for i in range(3, 10):  # Periods are in columns 3 to 9
                        st.write(f"Period {i-2}: {'Present' if record[i] == 1 else 'Absent'}")
            else:
                st.write("No attendance records found for the selected filters.")

        # Logout button
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.bluetooth_selected = False  # Reset Bluetooth selection flag
            st.session_state.attendance_saved = False  # Reset attendance saved flag
            st.rerun()

elif menu == "Admin Login":
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False  # Initially, no one is logged in
    
    if 'admin_id' not in st.session_state:  # Ensure admin_id is initialized
        st.session_state.admin_id = None

    if st.session_state.logged_in:
        # Admin is logged in, show the dashboard
        st.success("Admin login successful!")

       # Admin Profile Section
        if st.session_state.admin_id:  # Check if admin_id exists before querying the database
            try:
                cursor.execute("SELECT * FROM admin_profile WHERE admin_id = ?", (st.session_state.admin_id,))
                profile = cursor.fetchone()

                if profile:
                    st.subheader("Admin Profile")
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

                    # Option to update Admin ID and Password
                    new_admin_id = st.text_input("New Admin ID", st.session_state.admin_id)
                    new_password = st.text_input("New Password", type="password")

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
                                SET name = ?, department = ?, designation = ?, email = ?, phone = ? 
                                WHERE admin_id = ? 
                            """, (new_name, new_department, new_designation, new_email, new_phone, st.session_state.admin_id))

                            # Update admin login credentials (admin ID and password)
                            if new_admin_id != st.session_state.admin_id:
                                cursor.execute(""" 
                                    UPDATE admin 
                                    SET admin_id = ?, password = ? 
                                    WHERE admin_id = ? 
                                """, (new_admin_id, new_password, st.session_state.admin_id))
                                st.session_state.admin_id = new_admin_id  # Update the session ID

                            conn.commit()
                            st.success("Profile and login credentials updated successfully!")

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

                    if st.button("Save Profile"):
                        # Check if admin ID already exists
                        cursor.execute("SELECT * FROM admin WHERE admin_id = ?", (new_admin_id,))
                        existing_admin = cursor.fetchone()
                        if existing_admin:
                            st.error("Admin ID already exists. Please choose a different one.")
                        else:
                            cursor.execute(""" 
                                INSERT INTO admin_profile (admin_id, name, department, designation, email, phone) 
                                VALUES (?, ?, ?, ?, ?, ?) 
                            """, (new_admin_id, new_name, new_department, new_designation, new_email, new_phone))

                            cursor.execute(""" 
                                INSERT INTO admin (admin_id, password) 
                                VALUES (?, ?) 
                            """, (new_admin_id, new_password))

                            conn.commit()
                            st.success("Profile and login credentials created successfully!")

            except sqlite3.OperationalError as e:
                st.error(f"Database error: {e}")
            except sqlite3.IntegrityError as e:
                st.error(f"Integrity error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

        else:
            st.error("Admin is not logged in. Please log in to view the dashboard.")


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
        search_by_date = st.date_input("Search by Date")

        if st.button("Search"):
            # Build SQL query based on user inputs
            query = """
                SELECT DISTINCT students.* 
                FROM students
                LEFT JOIN attendance ON students.user_id = attendance.student_id
                WHERE 1=1
            """
            params = []

            if student_name:
                query += " AND students.name LIKE ?"
                params.append(f"%{student_name}%")

            if student_id:
                query += " AND students.user_id = ?"
                params.append(student_id)

            if student_department:
                query += " AND students.department LIKE ?"
                params.append(f"%{student_department}%")

            if student_year and student_year != "All":
                query += " AND students.year = ?"
                params.append(student_year)

            # Add date-related filters to the query
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
                query += " OR attendance.date = ?"
                params.append(search_by_date.strftime('%Y-%m-%d'))
            
            # Execute the query based on the applied filters
            cursor.execute(query, params)
            filtered_students = cursor.fetchall()

            # Display filtered students and their details automatically
            st.subheader("Filtered Students")
            if filtered_students:
                for student in filtered_students:
                    student_id = student[0]
                    student_name = student[2]
                    st.write(f"Student ID: {student_id}, Name: {student_name}")

                    # Display student's full details directly (no button required)
                    cursor.execute("SELECT * FROM students WHERE user_id = ?", (student_id,))
                    student_data = cursor.fetchone()
                    if student_data:
                        st.write(f"User ID: {student_data[0]}")
                        st.write(f"Name: {student_data[2]}")
                        st.write(f"Roll: {student_data[3]}")
                        st.write(f"Section: {student_data[4]}")
                        st.write(f"Email: {student_data[5]}")
                        st.write(f"Enrollment No: {student_data[6]}")
                        st.write(f"Year: {student_data[7]}")
                        st.write(f"Semester: {student_data[8]}")
                        st.write(f"Device ID: {student_data[9]}")

                        # Show student's attendance report
                        st.subheader(f"Attendance Report for {student_data[2]}")
                        cursor.execute(""" 
                            SELECT * FROM attendance WHERE student_id = ? 
                        """, (student_id,))
                        attendance_records = cursor.fetchall()
                        if attendance_records:
                            total_classes = len(attendance_records)
                            total_present = sum([sum(record[3:]) for record in attendance_records])  # Sum of all periods attended
                            percentage = (total_present / (total_classes * 7)) * 100  # Assuming 7 periods each day
                            st.write(f"Total Classes: {total_classes}")
                            st.write(f"Total Present: {total_present}")
                            st.write(f"Attendance Percentage: {percentage:.2f}%")

                            # Detailed attendance for each day
                            for record in attendance_records:
                                st.write(f"Date: {record[1]}, Day: {record[2]}")
                                for i in range(3, 10):  # Periods are in columns 3 to 9
                                    st.write(f"Period {i-2}: {'Present' if record[i] == 1 else 'Absent'}")
                        else:
                            st.write("No attendance records found for this student.")
            else:
                st.write("No students found based on the search criteria.")
            
            
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
                                total_present = sum(sum(record[3:]) for record in attendance_records)  # Sum of all periods attended

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
                                    for i in range(3, 10):  # Assuming period information starts from index 3 to 9
                                        st.write(f"**Period {i-2}:** {'Present' if record[i] == 1 else 'Absent'}")
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

                    # Save changes button
                    if st.button("Save Changes", key=f"save_changes_{student_id}"):
                        try:
                            # Validate inputs
                            if not new_user_id or not new_password or not new_device_ip:
                                st.error("User ID, Password, and Device IP are required fields.")
                            else:
                                # Update student details in the database
                                cursor.execute("""
                                    UPDATE students
                                    SET user_id = ?, password = ?, device_id = ?, name = ?, roll = ?, section = ?, email = ?, enrollment_no = ?, year = ?, semester = ?
                                    WHERE user_id = ?
                                """, (
                                    new_user_id, new_password, new_device_ip, new_name, new_roll, new_section,
                                    new_email, new_enrollment_no, new_year, new_semester, student_id
                                ))
                                conn.commit()

                                # Confirm success
                                if cursor.rowcount > 0:
                                    st.success(f"Details for {student_name} have been successfully updated!")
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

            # Add Institute and Admin details
            content.append(styled_paragraph("Institute Name: XYZ University", title_style))
            content.append(styled_paragraph(f"Generated by: {admin_details['name']}", normal_style))
            content.append(styled_paragraph(f"Department: {admin_details['department']}", normal_style))
            content.append(styled_paragraph(f"Date Range: {start_date} to {end_date}", normal_style))

            # Add semester details
            content.append(styled_paragraph(f"Semester: {start_date.year} - {end_date.year}", normal_style))
            content.append(styled_paragraph(f"Total Class days: {total_classes_in_semester}", normal_style))
            content.append(styled_paragraph(f"Total Periods: {total_periods_in_semester}", normal_style))

            # Add student attendance report
            for student in students:
                content.append(styled_paragraph(f"Student: {student['name']}", heading_style))
                
                # Table data for attendance
                data = [["Date", "Attendance"]]
                
                total_classes = 0
                total_present_classes = 0
                total_periods = 0
                total_present_periods = 0
                attendance_periods = {}

                # Fetch attendance data for the selected period
                for record in student['attendance']:
                    record_date = datetime.strptime(record['date'], '%Y-%m-%d').date() if isinstance(record['date'], str) else record['date']
                    if start_date <= record_date <= end_date:
                        data.append([record_date, "Present" if record['status'] else "Absent"])

                        # Count total classes and presents
                        total_classes += 1
                        if record['status']:
                            total_present_classes += 1

                        # Count total periods and presents
                        total_periods += 1
                        if record['status']:
                            total_present_periods += 1

                        # Group attendance by period (e.g., month)
                        period_key = record_date.strftime('%Y-%m')  # Period as Year-Month
                        if period_key not in attendance_periods:
                            attendance_periods[period_key] = {"present": 0, "total": 0}
                        attendance_periods[period_key]["total"] += 1
                        if record['status']:
                            attendance_periods[period_key]["present"] += 1

                table = Table(data)
                table.setStyle(TableStyle([(
                    'BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                content.append(table)

                # Attendance percentage and pass/fail for classes attended
                if total_classes_in_semester > 0:
                    attendance_percentage_classes = (total_present_classes / total_classes_in_semester) * 100
                else:
                    attendance_percentage_classes = 0

                # Attendance percentage and pass/fail for periods attended
                if total_periods_in_semester > 0:
                    attendance_percentage_periods = (total_present_periods / total_periods_in_semester) * 100
                else:
                    attendance_percentage_periods = 0

                pass_fail_classes = "Pass" if attendance_percentage_classes >= 75 else "Fail"
                pass_fail_periods = "Pass" if attendance_percentage_periods >= 75 else "Fail"

                content.append(styled_paragraph(f"Attendance Percentage (Class days Attended): {attendance_percentage_classes:.2f}%", normal_style))
                content.append(styled_paragraph(f"Pass/Fail Status (Class days): {pass_fail_classes}", normal_style))

                content.append(styled_paragraph(f"Attendance Percentage (Periods Attended): {attendance_percentage_periods:.2f}%", normal_style))
                content.append(styled_paragraph(f"Pass/Fail Status (Periods): {pass_fail_periods}", normal_style))

                # Add Period-wise Attendance
                content.append(styled_paragraph("Period-wise Attendance:", heading_style))
                period_data = [["Period", "Present", "Total"]]
                for period, values in attendance_periods.items():
                    period_data.append([period, values["present"], values["total"]])

                period_table = Table(period_data)
                period_table.setStyle(TableStyle([(
                    'BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                content.append(period_table)

                # Graphs for Attendance (Modified to match the updated analysis)
                fig, ax = plt.subplots(figsize=(6, 4))

                # Assuming 'attendance_periods' is a dictionary with period-wise data
                periods = list(attendance_periods.keys())
                presents = [attendance_periods[period]["present"] for period in periods]
                total = [attendance_periods[period]["total"] for period in periods]

                # Create bar chart with Present and Absent counts
                ax.bar(periods, presents, label="Present", alpha=0.7, color='g')
                ax.bar(periods, [total[i] - presents[i] for i in range(len(periods))], label="Absent", alpha=0.7, color='r')

                # Set labels and title
                ax.set_xlabel('Period')
                ax.set_ylabel('Attendance Count')
                ax.set_title(f"Attendance Analysis for {student_name}")
                ax.legend()

                # Save plot to a buffer
                img_buffer = BytesIO()
                plt.savefig(img_buffer, format="png")
                img_buffer.seek(0)

                # Add space and the graph to the content
                content.append(Paragraph("<br/>", normal_style))  # Space before the image
                content.append(Image(img_buffer, width=400, height=300))  # Add the graph to the PDF

            # Build PDF document
            doc.build(content)
            
            # Save to buffer
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
                    attendance = [{"date": record[1], "status": sum(record[3:]) > 0} for record in attendance_records]
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
            semester = st.selectbox("Select Semester", [1, 2])

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
        admin_id = st.text_input("Admin ID")
        admin_password = st.text_input("Admin Password", type="password")

        if st.button("Login"):
            cursor.execute("SELECT * FROM admin WHERE admin_id = ? AND password = ?", (admin_id, admin_password))
            admin = cursor.fetchone()
            if admin:
                # Store login state in session_state
                st.session_state.logged_in = True
                st.session_state.admin_id = admin_id
                st.session_state.admin_name = admin[0]
                st.session_state.profile_data = True  # Admin profile is now accessible
                st.rerun()  # Refresh the page to show the admin dashboard
            else:
                st.error("Invalid admin ID or password.")
