-- This script sets up the PostgreSQL database for the Anthropology attendance system.
DROP TABLE IF EXISTS attendance_records CASCADE;
DROP TABLE IF EXISTS attendance_sessions CASCADE;
DROP TABLE IF EXISTS classes CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS session_device_fingerprints CASCADE;

-- Table for the single controller user
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'controller' CHECK (role = 'controller')
);

-- Table for student data
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    enrollment_no VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    batch VARCHAR(50) NOT NULL
);

-- Table for class data
CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    class_name VARCHAR(100) UNIQUE NOT NULL,
    controller_id INTEGER REFERENCES users(id)
);

-- Table to log attendance sessions created by the controller
CREATE TABLE attendance_sessions (
    id SERIAL PRIMARY KEY,
    class_id INT REFERENCES classes(id) ON DELETE CASCADE,
    controller_id INT REFERENCES users(id),
    session_token VARCHAR(32) UNIQUE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    -- NEW: Store the location for this specific session
    session_lat REAL,
    session_lon REAL
);

-- Table to store individual student attendance records for each session
CREATE TABLE attendance_records (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id INT REFERENCES students(id),
    timestamp TIMESTAMPTZ NOT NULL,
    latitude REAL,
    longitude REAL,
    ip_address TEXT,
    UNIQUE (session_id, student_id)
);

-- Table to prevent multiple attendance markings from the same device in one session
CREATE TABLE session_device_fingerprints (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    student_id INT REFERENCES students(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL,
    UNIQUE (session_id, student_id),
    UNIQUE (session_id, fingerprint)
);

-- === INITIAL DATA INSERTION ===

-- Insert the single controller user
INSERT INTO users (username, role) VALUES ('controller', 'controller') ON CONFLICT (username) DO NOTHING;

-- Insert the class data for B.Sc. - Anthro (geofence info removed from here)
INSERT INTO classes (class_name, controller_id) VALUES
('B.Sc. - Anthro', (SELECT id FROM users WHERE username = 'controller'))
ON CONFLICT (class_name) DO NOTHING;

-- Insert all B.Sc. - Anthro student data
INSERT INTO students (enrollment_no, name, batch) VALUES
('Y24102001', 'Abhay Chadar', 'BSC'),
('Y24102002', 'Abhilasha', 'BSC'),
('Y24102003', 'Ajay Shukla', 'BSC'),
('Y24102004', 'Anwesha', 'BSC'),
('Y24102005', 'Bharti Kumai', 'BSC'),
('Y24102006', 'Bhumika Patel', 'BSC'),
('Y24102007', 'Ghanshyam', 'BSC'),
('Y24102008', 'Kanak Singh', 'BSC'),
('Y24102009', 'Karam Lakshana', 'BSC'),
('Y24102010', 'Lakhichand Chouhan', 'BSC'),
('Y24102011', 'Lalu Prasad Yadav', 'BSC'),
('Y24102012', 'Mahima Kumari Roy', 'BSC'),
('Y24102013', 'Manan Pawar', 'BSC'),
('Y24102014', 'Minakshi Kumari', 'BSC'),
('Y24102015', 'Nisha Patel', 'BSC'),
('Y24102016', 'Parth Bharadwaj', 'BSC'),
('Y24102017', 'Purvi Jain', 'BSC'),
('Y24102018', 'Rakhi Kumari', 'BSC'),
('Y24102019', 'Sahil Patel', 'BSC'),
('Y24102020', 'Saloni Dubey', 'BSC'),
('Y24102021', 'Shivani Kirad', 'BSC'),
('Y24102022', 'Shrishti Kumari', 'BSC'),
('Y24102023', 'Vaibhav Athya', 'BSC'),
('Y24102024', 'Saraswati Dangi', 'BSC'),
('Y24105001', 'Aashutosh Singh Dahiya', 'BSC'),
('Y24105002', 'Aastha Tiwari', 'BSC'),
('Y24105003', 'Amayra Gupta', 'BSC'),
('Y24105004', 'Anjini Saraf', 'BSC'),
('Y24105005', 'Annya Singh Yadav', 'BSC'),
('Y24105006', 'Anushree Shandilya', 'BSC'),
('Y24105007', 'Arushi Yadav', 'BSC'),
('Y24105008', 'Ayush Rajesh Singh', 'BSC'),
('Y24105009', 'B P Shyamendra Rao', 'BSC'),
('Y24105010', 'Dhanupratap Dhurvey', 'BSC'),
('Y24105011', 'Gayatri Prajapati', 'BSC'),
('Y24105012', 'Indrajeet Kumar', 'BSC'),
('Y24105013', 'Karuna Verma', 'BSC'),
('Y24105014', 'Kiran Singh Dhurvey', 'BSC'),
('Y24105015', 'Kumar Gaurav', 'BSC'),
('Y24105016', 'Madhvi Sharma', 'BSC'),
('Y24105017', 'Mohit Kurmi', 'BSC'),
('Y24105018', 'Naman Kumar Rawat', 'BSC'),
('Y24105019', 'Pankaj Ahirwar', 'BSC'),
('Y24105020', 'Poonam Ahirwar', 'BSC'),
('Y24105021', 'Poonam Lodhi', 'BSC'),
('Y24105022', 'Rashi Napit', 'BSC'),
('Y24105023', 'Renuka Priya', 'BSC'),
('Y24105024', 'Sanjeet Kumar', 'BSC'),
('Y24105025', 'Shreyansh Raikwar', 'BSC'),
('Y24105026', 'Sonam Singh Chouhan', 'BSC'),
('Y24105027', 'Sumit Raman Ray', 'BSC'),
('Y24105028', 'Namita Kumari', 'BSC'),
('Y24105029', 'Anvesha Jain', 'BSC'),
('Y24105030', 'Hari Kumar', 'BSC'),
('Y24105031', 'Shrishti Vaidya', 'BSC'),
('Y24105032', 'Vineet Sen', 'BSC'),
('Y20105009', 'Jyoti Sonkar', 'BSC'),
('Y21105023', 'Vasudev Tiwari', 'BSC'),
('Y24107001', 'Aalok Raj', 'BSC'),
('Y24107002', 'Abhigyan Shivam', 'BSC'),
('Y24107003', 'Arshia Singh', 'BSC'),
('Y24107004', 'Deepanjali Verma', 'BSC'),
('Y24107005', 'Dipti Shukla', 'BSC'),
('Y24107006', 'Esha Gouri Patel', 'BSC'),
('Y24107007', 'Janvi Kumari', 'BSC'),
('Y24107008', 'Likha Manyo', 'BSC'),
('Y24107009', 'Nitish Kumar Singh', 'BSC'),
('Y24107010', 'Preeti Raj Bansal', 'BSC'),
('Y24107011', 'Prerna', 'BSC'),
('Y24107012', 'Rajendra Singh', 'BSC'),
('Y24107013', 'Rimjhim Verma', 'BSC'),
('Y24107014', 'Ritika Singh', 'BSC'),
('Y24107015', 'Riya Sen', 'BSC'),
('Y24107016', 'Ruchi Rajak', 'BSC'),
('Y24107017', 'Sanidhya Tiwari', 'BSC'),
('Y24107018', 'Shailja Diwedi', 'BSC'),
('Y24107019', 'Shruti Kumari', 'BSC'),
('Y24107020', 'Shruti Kumari', 'BSC'),
('Y24107021', 'Sunil Singh Tomar', 'BSC'),
('Y24107022', 'Shushant Jaiswal', 'BSC'),
('Y24107023', 'Shushmit Mukherjee', 'BSC'),
('Y24107024', 'Vedika Bajpai', 'BSC'),
('Y24107025', 'Vishesh Kannaujiya', 'BSC'),
('Y24106001', 'Aarya Thakur', 'BSC'),
('Y24106002', 'Abhiraj Singh', 'BSC'),
('Y24106003', 'Abhishek Patel', 'BSC'),
('Y24106004', 'Akansha Choudhary', 'BSC'),
('Y24106005', 'Ananya Pandey', 'BSC'),
('Y24106006', 'Aniket Patel', 'BSC'),
('Y24106007', 'Anuj Kumar Patel', 'BSC'),
('Y24106008', 'Anushka Jha', 'BSC'),
('Y24106010', 'Atul Singh Dangi', 'BSC'),
('Y24106011', 'Kanika Jhanjhote', 'BSC'),
('Y24106012', 'Krishna Singh Lodhi', 'BSC'),
('Y24106013', 'Monit Choudhary', 'BSC'),
('Y24106014', 'Muskan Singh Dangi', 'BSC'),
('Y24106015', 'Pradeep Ahirwar', 'BSC'),
('Y24106016', 'Rounak Sen', 'BSC'),
('Y24106017', 'Rounak Sharma', 'BSC'),
('Y24106019', 'Shailendra Patel', 'BSC'),
('Y24106020', 'Shiva Ghoshi', 'BSC'),
('Y24106021', 'Shreya Yadav', 'BSC'),
('Y24106023', 'Tanisha Jha', 'BSC'),
('Y24106024', 'Tara Sen', 'BSC'),
('Y24106025', 'Divyansh Thakur', 'BSC'),
('Y24106027', 'Somil Jain', 'BSC'),
('Y24109001', 'Ashmika Martin', 'BSC'),
('Y24109002', 'Bhoomi Prajapati', 'BSC'),
('Y24109003', 'Bhoomika Jat', 'BSC'),
('Y24109004', 'Christy David', 'BSC'),
('Y24109005', 'Diksha Ahirwar', 'BSC'),
('Y24109006', 'Jainab Sheikh', 'BSC'),
('Y24109007', 'Shriram Sahu', 'BSC'),
('Y24109008', 'Amit Suryavanshi', 'BSC'),
('Y24109009', 'Ayush Pastor', 'BSC'),
('Y24109011', 'Sourabh Dangi', 'BSC'),
('Y24109013', 'Ankita Raja', 'BSC'),
('Y24109014', 'Antra Patel', 'BSC'),
('Y24109015', 'Aryan Patel', 'BSC'),
('Y24109017', 'Hans Raj Singh', 'BSC'),
('Y24109019', 'Namrata Raja Bundela', 'BSC'),
('Y24109020', 'Sanu Tiwari', 'BSC')
ON CONFLICT (enrollment_no) DO NOTHING;
