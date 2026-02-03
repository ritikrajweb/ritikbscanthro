-- Database Setup for "Practical 4th Sem" (Merged Batch: B.Sc. + B.A.)
-- Run this in your Supabase SQL Editor to reset and repopulate the database.

DROP TABLE IF EXISTS attendance_records CASCADE;
DROP TABLE IF EXISTS attendance_sessions CASCADE;
DROP TABLE IF EXISTS classes CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. Controller (Admin) Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'controller' CHECK (role = 'controller')
);

-- 2. Students Table (Merged B.A. & B.Sc.)
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    enrollment_no VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    batch VARCHAR(50) NOT NULL,
    password TEXT,              -- Stores password after registration
    device_id TEXT UNIQUE       -- Locks account to specific device
);

-- 3. Class Table
CREATE TABLE classes (
    id SERIAL PRIMARY KEY,
    class_name VARCHAR(100) UNIQUE NOT NULL,
    controller_id INTEGER REFERENCES users(id)
);

-- 4. Sessions Table
CREATE TABLE attendance_sessions (
    id SERIAL PRIMARY KEY,
    class_id INT REFERENCES classes(id) ON DELETE CASCADE,
    controller_id INT REFERENCES users(id),
    session_token VARCHAR(32) UNIQUE NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    session_lat REAL,
    session_lon REAL
);

-- 5. Attendance Records Table
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

-- === DATA SEEDING ===

-- Create Admin
INSERT INTO users (username, role) VALUES ('anthro_admin', 'controller');

-- Create Class
INSERT INTO classes (class_name, controller_id) 
VALUES ('Practical 4th Sem', (SELECT id FROM users WHERE username = 'anthro_admin'));

-- Insert MERGED Student List
INSERT INTO students (enrollment_no, name, batch) VALUES

-- === B.A. Students (Kept as is) ===
('Y24120001', 'ANSHUL TAMRAKAR', 'BA'), ('Y24120002', 'KHUSHVEER SINGH SURYA', 'BA'),
('Y24120003', 'SHREYASHI JAIN', 'BA'), ('Y24120041', 'VIJAY KUMAR', 'BA'),
('Y24120060', 'AARYA GOANTIYA', 'BA'), ('Y24120061', 'ANIYA PARTE', 'BA'),
('Y24120062', 'SATYAM SEN', 'BA'), ('Y24120087', 'AGRATI AGRAWAL', 'BA'),
('Y24120088', 'SHUBHAM CHOUBEY', 'BA'), ('Y24120116', 'HARSH LODHI', 'BA'),
('Y24120127', 'RITIK RAJ', 'BA'), ('Y24120129', 'BOBI RAJA', 'BA'),
('Y24120150', 'JAYA RAIKWAR', 'BA'), ('Y24120151', 'KUNDAN RAJAK', 'BA'),
('Y24120152', 'VINAY SINGH THAKUR', 'BA'), ('Y24120184', 'BHARTESHU GRAY', 'BA'),
('Y24120185', 'RAGINI GOUND', 'BA'), ('Y24120187', 'RAMPAL SINGH THAKUR', 'BA'),
('Y24120188', 'SHREYA THAKUR', 'BA'), ('Y24120203', 'ABHISHEK YADAV', 'BA'),
('Y24120204', 'ADITYA SINGH', 'BA'), ('Y24120205', 'AVINASH AHIRWAR', 'BA'),
('Y24120206', 'HARSH KHANGAR', 'BA'), ('Y24120207', 'KRISH YADAV', 'BA'),
('Y24120244', 'ARJUN PATEL', 'BA'), ('Y24120245', 'DEEPAK SANJAY MUNDHE', 'BA'),
('Y24120246', 'NANCY PANDEY', 'BA'), ('Y24120260', 'AYUSH AHIRWAR', 'BA'),
('Y24120261', 'NEERAJ YADAV', 'BA'), ('Y24120280', 'ADITYA VINODIYA', 'BA'),
('Y24120282', 'RIMJHIM SONI', 'BA'), ('Y24120283', 'SHIVANSHU MISHRA', 'BA'),
('Y24120293', 'ABHI YADAV', 'BA'), ('Y24120294', 'ADITYA TIWARI', 'BA'),
('Y24120296', 'KRASHITA PANDEY', 'BA'), ('Y24120298', 'PRIYANSH SHRIVASTAVA', 'BA'),
('Y24120325', 'KRISHNA RAIKWAR', 'BA'), ('Y24120333', 'AYUSHI SURYAVANSHI', 'BA'),
('Y24120334', 'KHUSHI AHIRWAR', 'BA'), ('Y24120337', 'SHUBHAM AHIRWAR', 'BA'),
('Y24120339', 'ASHISH KUMAR', 'BA'), ('Y24120355', 'KULDEEP YADAV', 'BA'),
('Y24120356', 'NEETESH DANGI', 'BA'), ('Y24120393', 'NANCY JAIN', 'BA'),
('Y24120395', 'MEENAKSHI SEN', 'BA'), ('Y24120449', 'HARSH YADAV', 'BA'),
('Y24120526', 'RISHITA YADAV', 'BA'), ('Y24120547', 'NIHAL KAROSIA', 'BA'),
('Y24120548', 'SOMIL KAROSIYA', 'BA'), ('Y24120549', 'VINAY KUMAR YADAV', 'BA'),
('Y24120553', 'KHUSHI YADAV', 'BA'), ('Y24120554', 'PRATHMESH AHIRWAR', 'BA'),
('Y24120555', 'UDIT NAMDEV', 'BA'), ('Y24120556', 'VAISHALI SEN', 'BA'),
('Y24120594', 'SOURABH SINGH LODHI', 'BA'), ('Y24120599', 'KHUSHI SONI', 'BA'),
('Y24120600', 'MUKESH PRAJAPATI', 'BA'), ('Y24120607', 'JIYA SEN', 'BA'),
('Y24120618', 'ANSHIKA SIROTHIYA', 'BA'), ('Y24120621', 'APRAJITA PATHAK', 'BA'),
('Y24120634', 'PUNEET SEN', 'BA'), ('Y24120640', 'PRINCI JAIN', 'BA'),
('Y24120641', 'VIVEK AHIRWAR', 'BA'), ('Y24120646', 'ANJLEE YADAV', 'BA'),
('Y24120647', 'APOORVA THAKUR', 'BA'), ('Y24120657', 'AMAN KUMAR MARAVI', 'BA'),
('Y24120659', 'SHIVANSH VISHWAKARMA', 'BA'), ('Y24120661', 'SIMRAN BEE', 'BA'),
('Y24120664', 'HARSH SEN', 'BA'), ('Y24120665', 'PRATEEK NEGI', 'BA'),
('Y24120678', 'JIYA DUBEY', 'BA'), ('Y24120691', 'KHUSHBOO AHIRWAR', 'BA'),
('Y24120692', 'JAYANT SEN', 'BA'), ('Y24120697', 'JIGYASHA SHARMA', 'BA'),
('Y24130025', 'RAKSHA SINGH', 'BA'), ('Y24130066', 'AASHIYA RANGREJ', 'BA'),
('Y24130071', 'AMAN GHARU', 'BA'),

-- === B.Sc. Students (Added from Attendance List) ===

-- Group C.A.Z
('Y24102001', 'Abhay Chadar', 'BSC'), ('Y24102002', 'Abhilasha', 'BSC'),
('Y24102003', 'Ajay Shukla', 'BSC'), ('Y24102004', 'Anwesha', 'BSC'),
('Y24102005', 'Bharti Kumai', 'BSC'), ('Y24102006', 'Bhumika Patel', 'BSC'),
('Y24102007', 'Ghanshyam', 'BSC'), ('Y24102008', 'Kanak Singh', 'BSC'),
('Y24102009', 'Karam Lakshana', 'BSC'), ('Y24102010', 'Lakhichand Chouhan', 'BSC'),
('Y24102011', 'Lalu Prasad Yadav', 'BSC'), ('Y24102012', 'Mahima Kumari Roy', 'BSC'),
('Y24102013', 'Manan Pawar', 'BSC'), ('Y24102014', 'Minakshi Kumari', 'BSC'),
('Y24102015', 'Nisha Patel', 'BSC'), ('Y24102016', 'Parth Bharadwaj', 'BSC'),
('Y24102017', 'Purvi Jain', 'BSC'), ('Y24102018', 'Rakhi Kumari', 'BSC'),
('Y24102019', 'Sahil Patel', 'BSC'), ('Y24102020', 'Saloni Dubey', 'BSC'),
('Y24102021', 'Shivani Kirad', 'BSC'), ('Y24102022', 'Shrishti Kumari', 'BSC'),
('Y24102023', 'Vaibhav Athya', 'BSC'), ('Y24102024', 'Saraswati Dangi', 'BSC'),

-- Group B.A.Z
('Y24105001', 'Aashutosh Singh Dahiya', 'BSC'), ('Y24105002', 'Aastha Tiwari', 'BSC'),
('Y24105003', 'Amayra Gupta', 'BSC'), ('Y24105004', 'Anjini Saraf', 'BSC'),
('Y24105005', 'Annya Singh Yadav', 'BSC'), ('Y24105006', 'Anushree Shandilya', 'BSC'),
('Y24105007', 'Arushi Yadav', 'BSC'), ('Y24105008', 'Ayush Rajesh Singh', 'BSC'),
('Y24105009', 'B P Shyamendra Rao', 'BSC'), ('Y24105010', 'Dhanupratap Dhurvey', 'BSC'),
('Y24105011', 'Gayatri Prajapati', 'BSC'), ('Y24105012', 'Indrajeet Kumar', 'BSC'),
('Y24105013', 'Karuna Verma', 'BSC'), ('Y24105014', 'Kiran Singh Dhurvey', 'BSC'),
('Y24105015', 'Kumar Gaurav', 'BSC'), ('Y24105016', 'Madhvi Sharma', 'BSC'),
('Y24105017', 'Mohit Kurmi', 'BSC'), ('Y24105018', 'Naman Kumar Rawat', 'BSC'),
('Y24105019', 'Pankaj Ahirwar', 'BSC'), ('Y24105020', 'Poonam Ahirwar', 'BSC'),
('Y24105021', 'Poonam Lodhi', 'BSC'), ('Y24105022', 'Rashi Napit', 'BSC'),
('Y24105023', 'Renuka Priya', 'BSC'), ('Y24105024', 'Sanjeet Kumar', 'BSC'),
('Y24105025', 'Shreyansh Raikwar', 'BSC'), ('Y24105026', 'Sonam Singh Chouhan', 'BSC'),
('Y24105027', 'Sumit Raman Ray', 'BSC'), ('Y24105028', 'Namita Kumari', 'BSC'),
('Y24105029', 'Anvesha Jain', 'BSC'), ('Y24105030', 'Hari Kumar', 'BSC'),
('Y24105031', 'Shrishti Vaidya', 'BSC'), ('Y24105032', 'Vineet Sen', 'BSC'),

-- Re-Registration
('Y20105009', 'Jyoti Sonkar', 'BSC'), ('Y21105023', 'Vasudev Tiwari', 'BSC'),

-- Group G.A.F
('Y24107001', 'Aalok Raj', 'BSC'), ('Y24107002', 'Abhigyan Shivam', 'BSC'),
('Y24107003', 'Arshia Singh', 'BSC'), ('Y24107004', 'Deepanjali Verma', 'BSC'),
('Y24107005', 'Dipti Shukla', 'BSC'), ('Y24107006', 'Esha Gouri Patel', 'BSC'),
('Y24107007', 'Janvi Kumari', 'BSC'), ('Y24107008', 'Likha Manyo', 'BSC'),
('Y24107009', 'Nitish Kumar Singh', 'BSC'), ('Y24107010', 'Preeti Raj Bansal', 'BSC'),
('Y24107011', 'Prerna', 'BSC'), ('Y24107012', 'Rajendra Singh', 'BSC'),
('Y24107013', 'Rimjhim Verma', 'BSC'), ('Y24107014', 'Ritika Singh', 'BSC'),
('Y24107015', 'Riya Sen', 'BSC'), ('Y24107016', 'Ruchi Rajak', 'BSC'),
('Y24107017', 'Sanidhya Tiwari', 'BSC'), ('Y24107018', 'Shailja Diwedi', 'BSC'),
('Y24107019', 'Shruti Kumari', 'BSC'), ('Y24107020', 'Shruti Kumari', 'BSC'),
('Y24107021', 'Sunil Singh Tomar', 'BSC'), ('Y24107022', 'Shushant Jaiswal', 'BSC'),
('Y24107023', 'Shushmit Mukherjee', 'BSC'), ('Y24107024', 'Vedika Bajpai', 'BSC'),
('Y24107025', 'Vishesh Kannaujiya', 'BSC'),

-- Group G.A.P
('Y24106001', 'Aarya Thakur', 'BSC'), ('Y24106002', 'Abhiraj Singh', 'BSC'),
('Y24106003', 'Abhishek Patel', 'BSC'), ('Y24106004', 'Akansha Choudhary', 'BSC'),
('Y24106005', 'Ananya Pandey', 'BSC'), ('Y24106006', 'Aniket Patel', 'BSC'),
('Y24106007', 'Anuj Kumar Patel', 'BSC'), ('Y24106008', 'Anushka Jha', 'BSC'),
('Y24106010', 'Atul Singh Dangi', 'BSC'), ('Y24106011', 'Kanika Jhanjhote', 'BSC'),
('Y24106012', 'Krishna Singh Lodhi', 'BSC'), ('Y24106013', 'Monit Choudhary', 'BSC'),
('Y24106014', 'Muskan Singh Dangi', 'BSC'), ('Y24106015', 'Pradeep Ahirwar', 'BSC'),
('Y24106016', 'Rounak Sen', 'BSC'), ('Y24106017', 'Rounak Sharma', 'BSC'),
('Y24106019', 'Shailendra Patel', 'BSC'), ('Y24106020', 'Shiva Ghoshi', 'BSC'),
('Y24106021', 'Shreya Yadav', 'BSC'), ('Y24106023', 'Tanisha Jha', 'BSC'),
('Y24106024', 'Tara Sen', 'BSC'), ('Y24106025', 'Divyansh Thakur', 'BSC'),
('Y24106027', 'Somil Jain', 'BSC'),

-- Group A.P.Y
('Y24109001', 'Ashmika Martin', 'BSC'), ('Y24109002', 'Bhoomi Prajapati', 'BSC'),
('Y24109003', 'Bhoomika Jat', 'BSC'), ('Y24109004', 'Christy David', 'BSC'),
('Y24109005', 'Diksha Ahirwar', 'BSC'), ('Y24109006', 'Jainab Sheikh', 'BSC'),
('Y24109007', 'Shriram Sahu', 'BSC'), ('Y24109008', 'Amit Suryavanshi', 'BSC'),
('Y24109009', 'Ayush Pastor', 'BSC'), ('Y24109011', 'Sourabh Dangi', 'BSC'),
('Y24109013', 'Ankita Raja', 'BSC'), ('Y24109014', 'Antra Patel', 'BSC'),
('Y24109015', 'Aryan Patel', 'BSC'), ('Y24109017', 'Hans Raj Singh', 'BSC'),
('Y24109019', 'Namrata Raja Bundela', 'BSC'), ('Y24109020', 'Sanu Tiwari', 'BSC')

ON CONFLICT (enrollment_no) DO NOTHING;