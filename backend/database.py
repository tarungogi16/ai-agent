"""
CampusPulse AI - Database Module
SQLite database setup, schema initialization, and pre-seeded campus records.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "campuspulse.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Faculty Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faculty (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        department TEXT NOT NULL,
        designation TEXT NOT NULL,
        cabin_room TEXT NOT NULL,
        current_room TEXT NOT NULL,
        status TEXT NOT NULL,
        rfid_tag TEXT UNIQUE NOT NULL,
        last_seen TEXT NOT NULL,
        office_hours TEXT NOT NULL,
        bio TEXT,
        avatar TEXT,
        alternate_faculty_id TEXT,
        ta_name TEXT,
        ta_email TEXT
    )
    """)

    # 2. Students Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        usn TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        dob TEXT NOT NULL,
        email TEXT NOT NULL,
        department TEXT NOT NULL,
        semester INTEGER NOT NULL,
        section TEXT NOT NULL
    )
    """)

    # 3. Rooms & Gateways Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        room_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        block TEXT NOT NULL,
        floor INTEGER NOT NULL,
        reader_id TEXT NOT NULL,
        room_type TEXT NOT NULL
    )
    """)

    # 4. Routine & Timetables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        faculty_id TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        room_id TEXT NOT NULL,
        activity TEXT NOT NULL,
        FOREIGN KEY (faculty_id) REFERENCES faculty(id)
    )
    """)

    # 5. RFID Hardware Telemetry Events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rfid_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reader_id TEXT NOT NULL,
        room_id TEXT NOT NULL,
        tag_id TEXT NOT NULL,
        faculty_id TEXT,
        direction TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        confidence REAL DEFAULT 1.0
    )
    """)

    # 6. Meeting Requests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meeting_requests (
        id TEXT PRIMARY KEY,
        student_usn TEXT NOT NULL,
        faculty_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        urgency TEXT NOT NULL,
        status TEXT NOT NULL,
        proposed_slots TEXT,
        selected_slot TEXT,
        faculty_notes TEXT,
        escalated_to TEXT,
        escalation_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (student_usn) REFERENCES students(usn),
        FOREIGN KEY (faculty_id) REFERENCES faculty(id)
    )
    """)

    # 7. Agent Reasoning & Decision Logs (For Hackathon Judges)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        action TEXT NOT NULL,
        input_summary TEXT NOT NULL,
        thought_process TEXT NOT NULL,
        output_summary TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
    """)

    # 8. Real-time Notifications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_type TEXT NOT NULL,
        recipient_id TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()
    seed_data(conn)
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM faculty")
    if cursor.fetchone()[0] > 0:
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    # Seed Rooms
    rooms = [
        ("ROOM-304", "Cabin 304 (Prof. K. Rao)", "Tech Tower - CS Block", 3, "RDR-CABIN-304", "cabin"),
        ("ROOM-308", "Cabin 308 (Dr. Ananya Sharma)", "Tech Tower - CS Block", 3, "RDR-CABIN-308", "cabin"),
        ("ROOM-201", "Cabin 201 (Prof. Vikram Seth)", "Science Block", 2, "RDR-CABIN-201", "cabin"),
        ("ROOM-205", "Cabin 205 (Dr. Priya Nair)", "Science Block", 2, "RDR-CABIN-205", "cabin"),
        ("LH-101", "Lecture Hall 101 (Systems Lab)", "Academic Block A", 1, "RDR-LH-101", "classroom"),
        ("LH-102", "Lecture Hall 102 (Smart Classroom)", "Academic Block A", 1, "RDR-LH-102", "classroom"),
        ("LH-204", "Seminar Hall 204", "Academic Block B", 2, "RDR-LH-204", "classroom"),
        ("LIB-MAIN", "Central Library - 2nd Floor Reading Room", "Library Building", 2, "RDR-LIB-MAIN", "library"),
        ("GATE-MAIN", "Campus Main Security Gate", "Entrance Perimeter", 0, "RDR-GATE-MAIN", "gate")
    ]
    cursor.executemany("""
    INSERT INTO rooms (room_id, name, block, floor, reader_id, room_type)
    VALUES (?, ?, ?, ?, ?, ?)
    """, rooms)

    # Seed Faculty
    faculty_data = [
        (
            "FAC001",
            "Prof. K. Rao",
            "k.rao@university.edu",
            "Computer Science & Engineering",
            "Professor & Dean of Computing",
            "ROOM-304",
            "ROOM-304",
            "In Cabin",
            "TAG-RAO-7891",
            now_iso,
            "Mon/Wed/Fri: 14:00 - 16:00",
            "Chair of Distributed Systems & Cloud Architecture. Mentors final year capstones.",
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            "FAC002",
            "Rohan Deshmukh (M.Tech TA)",
            "rohan.ta@university.edu"
        ),
        (
            "FAC002",
            "Dr. Ananya Sharma",
            "ananya.sharma@university.edu",
            "Computer Science & Engineering",
            "Associate Professor (AI / ML Systems)",
            "ROOM-308",
            "LH-102",
            "In Lecture",
            "TAG-SHARMA-4412",
            now_iso,
            "Tue/Thu: 11:00 - 13:00, 15:30 - 17:00",
            "Lead Investigator at Campus NeuroAI Lab. Specializes in Deep Learning & NLP.",
            "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
            "FAC001",
            "Kavya Iyer (Ph.D Scholar)",
            "kavya.ai@university.edu"
        ),
        (
            "FAC003",
            "Prof. Vikram Seth",
            "vikram.seth@university.edu",
            "Information Science & Engineering",
            "Professor & Head of Department",
            "ROOM-201",
            "LIB-MAIN",
            "In Library",
            "TAG-SETH-9023",
            now_iso,
            "Daily: 16:00 - 17:30",
            "Expert in Cybersecurity, Network Protocol Audits, and Cryptography.",
            "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
            "FAC004",
            "Aditya Nair (Research Fellow)",
            "aditya.cyber@university.edu"
        ),
        (
            "FAC004",
            "Dr. Priya Nair",
            "priya.nair@university.edu",
            "Information Science & Engineering",
            "Assistant Professor (Data Engineering)",
            "ROOM-205",
            "GATE-MAIN",
            "Off Campus",
            "TAG-NAIR-3310",
            now_iso,
            "Wed/Fri: 10:00 - 12:00",
            "Focuses on Distributed Databases, Big Data Pipelines, and Real-time Stream Analytics.",
            "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&auto=format&fit=crop&q=80",
            "FAC003",
            "Varun Teja (M.Tech TA)",
            "varun.de@university.edu"
        )
    ]
    cursor.executemany("""
    INSERT INTO faculty (id, name, email, department, designation, cabin_room, current_room, status, rfid_tag, last_seen, office_hours, bio, avatar, alternate_faculty_id, ta_name, ta_email)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, faculty_data)

    # Seed Students
    students = [
        ("1MS21CS042", "Aarav Sharma", "2003-05-14", "aarav.1ms21cs042@campus.edu", "Computer Science & Engineering", 6, "A"),
        ("1MS21CS089", "Sneha Rao", "2003-08-22", "sneha.1ms21cs089@campus.edu", "Computer Science & Engineering", 6, "B"),
        ("1MS21IS015", "Karthik Verma", "2002-12-10", "karthik.1ms21is015@campus.edu", "Information Science & Engineering", 6, "A")
    ]
    cursor.executemany("""
    INSERT INTO students (usn, name, dob, email, department, semester, section)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, students)

    # Seed Timetables
    timetable_data = [
        # Prof Rao
        ("FAC001", "Monday", "09:00", "10:30", "LH-101", "CS401 High Performance Computing"),
        ("FAC001", "Monday", "11:00", "13:00", "ROOM-304", "Faculty Cabin Office Hours"),
        ("FAC001", "Monday", "14:00", "16:00", "LH-102", "CS301 Distributed Systems"),
        ("FAC001", "Tuesday", "10:00", "11:30", "LH-101", "CS401 High Performance Computing"),
        ("FAC001", "Tuesday", "14:00", "16:00", "ROOM-304", "Postgrad Capstone Mentorship"),
        ("FAC001", "Wednesday", "09:00", "11:00", "LH-102", "CS301 Distributed Systems"),
        ("FAC001", "Wednesday", "14:00", "16:00", "ROOM-304", "Open Student Consultations"),
        ("FAC001", "Thursday", "11:30", "13:00", "LH-204", "Academic Council Board Meeting"),
        ("FAC001", "Friday", "10:00", "12:00", "ROOM-304", "Department Project Evaluations"),
        
        # Dr Ananya Sharma
        ("FAC002", "Monday", "10:00", "12:00", "LH-102", "CS312 Neural Networks & Deep Learning"),
        ("FAC002", "Tuesday", "09:00", "11:00", "LH-102", "CS312 Neural Networks Lab"),
        ("FAC002", "Tuesday", "11:30", "13:00", "ROOM-308", "AI Research Lab Consultations"),
        ("FAC002", "Wednesday", "11:00", "12:30", "LH-101", "CS210 Data Structures & Algorithms"),
        ("FAC002", "Thursday", "14:00", "16:00", "ROOM-308", "Open Student Office Hours"),
        ("FAC002", "Friday", "11:00", "13:00", "LH-102", "AI Project Reviews"),

        # Prof Vikram Seth
        ("FAC003", "Monday", "11:00", "13:00", "LIB-MAIN", "Cybersecurity Journal Research"),
        ("FAC003", "Tuesday", "14:00", "16:00", "ROOM-201", "Department Administrative Hours"),
        ("FAC003", "Wednesday", "10:00", "12:00", "LH-204", "IS405 Network Security & Cryptography"),
        ("FAC003", "Thursday", "11:00", "13:00", "ROOM-201", "Office Consultations"),
        ("FAC003", "Friday", "15:00", "17:00", "ROOM-201", "Master's Thesis Viva"),

        # Dr Priya Nair
        ("FAC004", "Monday", "09:00", "11:00", "LH-101", "IS302 Big Data Architecture"),
        ("FAC004", "Wednesday", "10:00", "12:00", "ROOM-205", "Stream Analytics Lab Office Hours"),
        ("FAC004", "Friday", "14:00", "16:00", "LH-101", "Database Optimization Workshop")
    ]
    cursor.executemany("""
    INSERT INTO timetable (faculty_id, day_of_week, start_time, end_time, room_id, activity)
    VALUES (?, ?, ?, ?, ?, ?)
    """, timetable_data)

    # Seed sample initial meeting request
    req_id = "REQ-8801"
    slots = json.dumps([
        {
            "slot_time": "Today, 14:15 - 14:45",
            "location": "Room 304 (Tech Tower)",
            "reasoning": "Prof. Rao completes CS301 at 14:00. Dwell probability in cabin is 92% until 16:00 open office hours.",
            "confidence": 0.92
        },
        {
            "slot_time": "Tomorrow, 11:30 - 12:00",
            "location": "Room 304 (Tech Tower)",
            "reasoning": "Directly precedes postgrad project review block with zero overlapping student queue.",
            "confidence": 0.88
        }
    ])
    cursor.execute("""
    INSERT INTO meeting_requests (id, student_usn, faculty_id, topic, urgency, status, proposed_slots, selected_slot, faculty_notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req_id,
        "1MS21CS042",
        "FAC001",
        "Capstone Project Architecture Sign-off",
        "HIGH",
        "slots_offered",
        slots,
        None,
        None,
        now_iso,
        now_iso
    ))

    # Seed sample agent logs
    cursor.execute("""
    INSERT INTO agent_logs (agent_name, action, input_summary, thought_process, output_summary, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "NLIntakeAgent",
        "parse_student_utterance",
        "Student input: 'Urgent: need Prof Rao to review our distributed cache design for capstone'",
        "Parsed entities -> Faculty: Prof. K. Rao (FAC001), Topic: Capstone distributed cache design, Urgency: HIGH (due to keyword 'Urgent' and capstone milestone context).",
        "Mapped to FAC001, urgency=HIGH, topic='Capstone distributed cache design'",
        now_iso
    ))

    cursor.execute("""
    INSERT INTO agent_logs (agent_name, action, input_summary, thought_process, output_summary, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "AvailabilityAgent",
        "telemetry_and_routine_blend",
        "Querying RFID door sensor RDR-CABIN-304: Tag TAG-RAO-7891 entered 12m ago. Current routine: In Cabin until 16:00.",
        "Synthesizing slot windows based on dwell statistics and zero queue contention.",
        "Synthesized 2 slots with 92% and 88% availability confidence windows.",
        now_iso
    ))

    # Initial Notifications
    cursor.execute("""
    INSERT INTO notifications (recipient_type, recipient_id, title, message, type, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "student",
        "1MS21CS042",
        "AI Meeting Slots Generated",
        "CampusPulse Negotiation Agent proposed 2 optimal slots to meet Prof. K. Rao.",
        "info",
        now_iso
    ))

    conn.commit()

if __name__ == "__main__":
    init_db()
    print("Database initialized and pre-seeded successfully at:", DB_PATH)
