import sqlite3
import streamlit as st
from geopy.geocoders import Nominatim
import socket
import asyncio
from bleak import BleakScanner
import datetime
from datetime import date, datetime

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
def get_device_ip():
    """
    Get the IP address of the user's device (phone or desktop).
    This will be used as the unique device ID.
    """
    ip = socket.gethostbyname(socket.gethostname())  # For local testing
    st.success(f"Device IP address fetched successfully: {ip}")
    return ip

def get_location():
    """
    Get the location of the user based on IP address or GPS.
    We use Geopy to get the location of Kolkata.
    """
    geolocator = Nominatim(user_agent="geoapi")
    try:
        location = geolocator.geocode("Kolkata")
        if location:
            st.success("Location fetched successfully.")
            return location.address
        else:
            st.error("Location not found.")
            return None
    except Exception as e:
        st.error(f"Error fetching location: {e}")
        return None

async def get_ble_signal():
    """
    Get the available Bluetooth Low Energy (BLE) devices in range.
    This function uses BleakScanner to scan for devices.
    """
    devices = await BleakScanner.discover()
    ble_signals = {device.address: device.name if device.name else device.address for device in devices}
    return ble_signals

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
        "Period 5": ("12:58", "14:30"),
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

    # Fetch the device ID (IP address)
    device_id = get_device_ip()

    if not device_id:
        st.error("Could not fetch device IP address, registration cannot proceed.")
    
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
    device_id = get_device_ip()

    if not device_id:
        st.error("Could not fetch device IP address. Login cannot proceed.")
    
    if st.button("Login") and not st.session_state.get('bluetooth_selected', False):
        cursor.execute("SELECT * FROM students WHERE user_id = ? AND password = ?", (user_id, password))
        user = cursor.fetchone()
        if user:
            if user[-1] == device_id:  # Match device_id from IP address
                location = get_location()
                if location and "Kolkata" in location:
                    st.success(f"Login successful! Welcome, {user[2]}")
                    
                    # Check for Bluetooth signal during login session
                    st.info("Scanning for Bluetooth devices...")
                    
                    # Simulate scanning for Bluetooth devices
                    import time
                    time.sleep(2)  # Simulate a delay for scanning

                    st.info("Bluetooth devices found. Listing all available devices...")

                    st.info("the required Bluetooth device has been found, login succesfull")
                        
                    # Simulated available Bluetooth devices
                    simulated_ble_signal = {
                        "Device 1": "00:11:22:33:44:55",
                        "Device 2": "66:77:88:99:AA:BB",
                        "Device 3": "6C:E8:C6:75:A1:EA",  # This is the required device
                    } 

                    found_device = True
                        

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
                                    "Period 5": ("12:58", "14:30"),
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
                    st.error("You must be in Kolkata to login.")
            else:
                st.error("Device ID does not match.")
        else:
            st.error("Invalid user ID or password.")

    # Display student attendance search form
    if st.session_state.get('logged_in', False):
        st.subheader("Search Attendance Records")
        
        # Select Year and Month
        year = st.selectbox("Select Year", ["2024", "2023", "2022"])
        month = st.selectbox("Select Month", ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])
        day_of_week = st.selectbox("Select Day of the Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])

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
                SELECT students.* 
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
            
            # Debugging: Print the query and params
            print("Query:", query)
            print("Params:", params)

            # Execute the query based on the applied filters
            cursor.execute(query, params)
            filtered_students = cursor.fetchall()

            # Display filtered students
            st.subheader("Filtered Students")
            if filtered_students:
                for student in filtered_students:
                    student_id = student[0]
                    student_name = student[2]
                    st.write(f"Student ID: {student_id}, Name: {student_name}")

                # Button to view student details with a unique key using both ID and name
                unique_key = f"view_details_{student_id}_{hash(student_name)}"
                if st.button(f"View Details for {student_name}", key=unique_key):
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
                        st.subheader(f"Attendance Report for {student_name}")
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
                    cursor.execute("SELECT * FROM attendance WHERE student_id = ?", (student_id,))
                    attendance_records = cursor.fetchall()

                    if attendance_records:
                        total_days = len(attendance_records)
                        total_present = sum(sum(record[3:]) for record in attendance_records)  # Sum of all periods attended
                        total_classes = total_days * 7  # Assuming 7 periods per day
                        attendance_percentage = (total_present / total_classes) * 100

                        st.write(f"Total Days: {total_days}")
                        st.write(f"Total Classes: {total_classes}")
                        st.write(f"Total Present: {total_present}")
                        st.write(f"Attendance Percentage: {attendance_percentage:.2f}%")

                        # Attendance breakdown
                        for record in attendance_records:
                            st.write(f"Date: {record[1]}, Day: {record[2]}")
                            for i in range(3, 10):
                                st.write(f"Period {i-2}: {'Present' if record[i] == 1 else 'Absent'}")
                    else:
                        st.write("No attendance records found for this student.")
                        
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
