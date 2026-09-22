"""
CampusPulse AI - FastAPI Server
Handles REST APIs, Hardware RFID Webhooks, Server-Sent Events (SSE) for Real-Time Sync,
Multi-Agent Orchestration, and Background Escalation Tasks.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .database import get_db, init_db
from .agents import (
    NLIntakeAgent, 
    AvailabilityAgent, 
    NegotiationAgent, 
    EscalationAgent, 
    log_agent_thought
)

app = FastAPI(
    title="CampusPulse AI - Build for Billions",
    description="Autonomous Smart RFID & Agentic Faculty-Student Dispatch System",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active SSE Client Queues
sse_clients: List[asyncio.Queue] = []

async def broadcast_event(event_type: str, data: Any):
    """Pushes a real-time event to all connected web clients via SSE."""
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    for queue in list(sse_clients):
        try:
            await queue.put(payload)
        except Exception:
            if queue in sse_clients:
                sse_clients.remove(queue)

# ---------------------------------------------------------------------------
# Background Escalation Daemon
# ---------------------------------------------------------------------------
async def escalation_watchdog_loop():
    """Background task running every 45s to check for unhandled requests and auto-escalate."""
    while True:
        try:
            await asyncio.sleep(45)
            escalations = EscalationAgent.evaluate_and_escalate()
            if escalations:
                await broadcast_event("escalation_event", {"count": len(escalations), "details": escalations})
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[EscalationWatchdog] Error in loop: {e}")

@app.on_event("startup")
async def startup_event():
    init_db()
    asyncio.create_task(escalation_watchdog_loop())

# ---------------------------------------------------------------------------
# SSE Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/events")
async def sse_stream(request: Request):
    """Server-Sent Events endpoint for instant UI radar and notification updates."""
    client_queue = asyncio.Queue()
    sse_clients.append(client_queue)

    async def event_generator():
        try:
            # Send initial handshake event
            yield f"event: connected\ndata: {{\"status\": \"online\", \"timestamp\": \"{datetime.now(timezone.utc).isoformat()}\"}}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                data = await client_queue.get()
                yield data
        except asyncio.CancelledError:
            pass
        finally:
            if client_queue in sse_clients:
                sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
class RFIDTapPayload(BaseModel):
    reader_id: str
    tag_id: str
    direction: str = "ENTRY" # "ENTRY" or "EXIT"
    timestamp: Optional[str] = None
    confidence: Optional[float] = 1.0

class StudentAuthPayload(BaseModel):
    usn: str
    dob: str

class NLIntakePayload(BaseModel):
    text: str

class SlotNegotiationPayload(BaseModel):
    student_usn: str
    faculty_id: str
    topic: str
    urgency: str = "MEDIUM"

class CreateRequestPayload(BaseModel):
    student_usn: str
    faculty_id: str
    topic: str
    urgency: str
    selected_slot: Dict[str, Any]
    proposed_slots: List[Dict[str, Any]]

class RespondRequestPayload(BaseModel):
    status: str # "confirmed", "rejected", "rescheduled"
    notes: Optional[str] = ""

class StatusOverridePayload(BaseModel):
    status: str
    current_room: Optional[str] = None

# ---------------------------------------------------------------------------
# Hardware RFID Webhook & Simulator
# ---------------------------------------------------------------------------
@app.post("/api/rfid/tap")
async def handle_rfid_tap(payload: RFIDTapPayload):
    """
    Hardware Webhook Endpoint:
    Accepts door-tap telemetry from RFID/BLE physical readers (ESP32 / RC522 / BLE Gateway)
    or the in-browser RFID Hardware Simulator.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Lookup Room & Reader
    cursor.execute("SELECT * FROM rooms WHERE reader_id = ?", (payload.reader_id,))
    room = cursor.fetchone()
    if not room:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Reader ID '{payload.reader_id}' not recognized in campus room registry.")

    room = dict(room)

    # 2. Lookup Faculty by RFID Tag
    cursor.execute("SELECT * FROM faculty WHERE rfid_tag = ?", (payload.tag_id,))
    faculty = cursor.fetchone()
    if not faculty:
        conn.close()
        raise HTTPException(status_code=404, detail=f"RFID Tag '{payload.tag_id}' not bound to any faculty member.")

    faculty = dict(faculty)
    faculty_id = faculty["id"]
    now_iso = payload.timestamp or datetime.now(timezone.utc).isoformat()

    # 3. Determine New Status & Room based on Reader Type & Direction
    room_type = room["room_type"]
    new_status = faculty["status"]
    new_room = faculty["current_room"]

    if room["room_id"] == "GATE-MAIN":
        if payload.direction.upper() == "EXIT":
            new_status = "Off Campus"
            new_room = "Off Campus"
        else:
            new_status = "On Campus - Moving"
            new_room = "Campus Perimeter"
    elif room_type == "cabin":
        if payload.direction.upper() == "ENTRY":
            new_status = "In Cabin"
            new_room = room["name"]
        else:
            new_status = "On Campus - Moving"
            new_room = "Departed Cabin"
    elif room_type == "classroom":
        if payload.direction.upper() == "ENTRY":
            new_status = "In Lecture"
            new_room = room["name"]
        else:
            new_status = "On Campus - Moving"
            new_room = "Academic Corridor"
    elif room_type == "library":
        if payload.direction.upper() == "ENTRY":
            new_status = "In Library"
            new_room = room["name"]
        else:
            new_status = "On Campus - Moving"
            new_room = "Library Building Exit"

    # 4. Update Faculty State
    cursor.execute("""
    UPDATE faculty
    SET current_room = ?,
        status = ?,
        last_seen = ?
    WHERE id = ?
    """, (new_room, new_status, now_iso, faculty_id))

    # 5. Record Event Log
    cursor.execute("""
    INSERT INTO rfid_events (reader_id, room_id, tag_id, faculty_id, direction, timestamp, confidence)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (payload.reader_id, room["room_id"], payload.tag_id, faculty_id, payload.direction.upper(), now_iso, payload.confidence or 1.0))

    # 6. Log Agent Telemetry Note
    log_agent_thought(
        agent_name="AvailabilityAgent",
        action="rfid_telemetry_ingest",
        input_summary=f"Door Tap: Reader={payload.reader_id} ({room['name']}), Tag={payload.tag_id}, Direction={payload.direction}",
        thought_process=f"State transition computed: {faculty['name']} moved from '{faculty['status']}' to '{new_status}' at '{new_room}'. Triggered real-time radar push.",
        output_summary=f"Updated {faculty['name']} status to '{new_status}' in room '{new_room}'",
        conn=conn
    )

    conn.commit()
    conn.close()

    # 7. Check if Faculty Departure warrants Auto-Escalation
    if new_status in ["Off Campus"]:
        EscalationAgent.evaluate_and_escalate()

    event_broadcast_data = {
        "faculty_id": faculty_id,
        "faculty_name": faculty["name"],
        "status": new_status,
        "current_room": new_room,
        "last_seen": now_iso,
        "reader_name": room["name"],
        "direction": payload.direction.upper()
    }

    # Broadcast live update to all connected frontends
    await broadcast_event("rfid_update", event_broadcast_data)

    return {
        "success": True,
        "message": f"Telemetry processed: {faculty['name']} is now '{new_status}' at {new_room}.",
        "data": event_broadcast_data
    }

# ---------------------------------------------------------------------------
# Faculty APIs
# ---------------------------------------------------------------------------
@app.get("/api/faculty")
def get_all_faculty():
    """Returns all faculty with current location, RFID tag, and predictive availability."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faculty ORDER BY name ASC")
    rows = cursor.fetchall()
    
    faculty_list = []
    for r in rows:
        f = dict(r)
        # Fetch predictive availability
        pred = AvailabilityAgent.predict_availability(f["id"])
        f["prediction"] = pred
        faculty_list.append(f)
    conn.close()
    return faculty_list

@app.get("/api/faculty/{faculty_id}")
def get_faculty_detail(faculty_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM faculty WHERE id = ?", (faculty_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Faculty not found")
    f = dict(row)
    
    cursor.execute("SELECT * FROM timetable WHERE faculty_id = ? ORDER BY start_time ASC", (faculty_id,))
    f["timetable"] = [dict(t) for t in cursor.fetchall()]
    f["prediction"] = AvailabilityAgent.predict_availability(faculty_id)
    conn.close()
    return f

@app.post("/api/faculty/{faculty_id}/override")
async def override_faculty_status(faculty_id: str, payload: StatusOverridePayload):
    """Allows a faculty member to manually override their status in the portal."""
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    room = payload.current_room or "Cabin"
    cursor.execute("""
    UPDATE faculty
    SET status = ?, current_room = ?, last_seen = ?
    WHERE id = ?
    """, (payload.status, room, now_iso, faculty_id))
    conn.commit()
    conn.close()

    await broadcast_event("faculty_override", {
        "faculty_id": faculty_id,
        "status": payload.status,
        "current_room": room
    })
    return {"success": True, "status": payload.status}

# ---------------------------------------------------------------------------
# Student Auth & Directory
# ---------------------------------------------------------------------------
@app.post("/api/auth/student")
def authenticate_student(payload: StudentAuthPayload):
    """Authenticates student via mock ERP credentials (USN + DOB)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE UPPER(usn) = UPPER(?) AND dob = ?", (payload.usn.strip(), payload.dob.strip()))
    student = cursor.fetchone()
    conn.close()
    if not student:
        raise HTTPException(status_code=401, detail="Invalid USN or Date of Birth. Check mock demo credentials.")
    return {"success": True, "student": dict(student)}

@app.get("/api/students")
def get_sample_students():
    """Lists pre-seeded mock student credentials for easy 1-click hackathon demo login."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    students = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return students

# ---------------------------------------------------------------------------
# Campus Rooms & Gateways
# ---------------------------------------------------------------------------
@app.get("/api/rooms")
def get_campus_rooms():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rooms ORDER BY block, name")
    rooms = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rooms

# ---------------------------------------------------------------------------
# Agentic AI Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/agent/intake")
async def natural_language_intake(payload: NLIntakePayload):
    """
    Natural Language Intake Agent:
    Parses unstructured student query into structured booking intent.
    """
    result = await NLIntakeAgent.parse_request(payload.text)
    await broadcast_event("agent_thought", {
        "agent": "NLIntakeAgent",
        "action": "Parsed Student Utterance",
        "result": result
    })
    return result

@app.post("/api/agent/negotiate")
async def negotiate_meeting_slots(payload: SlotNegotiationPayload):
    """
    Meeting Negotiation Agent:
    Autonomously checks telemetry, routine, and queue to synthesize 2-3 optimal slots with reasoning.
    """
    slots = await NegotiationAgent.propose_slots(
        student_usn=payload.student_usn,
        faculty_id=payload.faculty_id,
        topic=payload.topic,
        urgency=payload.urgency
    )
    await broadcast_event("agent_thought", {
        "agent": "NegotiationAgent",
        "action": f"Synthesized {len(slots)} Candidate Slots for {payload.faculty_id}",
        "slots_count": len(slots)
    })
    return {"slots": slots}

@app.post("/api/agent/escalate")
async def trigger_escalation(request_id: Optional[str] = None):
    """
    Escalation Agent:
    Evaluates unhandled requests and triggers autonomous mitigation.
    """
    escalations = EscalationAgent.evaluate_and_escalate(request_id)
    if escalations:
        await broadcast_event("escalation_event", {"count": len(escalations), "details": escalations})
    return {"success": True, "escalated_count": len(escalations), "actions": escalations}

@app.get("/api/agent/logs")
def get_agent_logs():
    """Returns live agent thought traces for hackathon judge inspection."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_logs ORDER BY id DESC LIMIT 50")
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs

# ---------------------------------------------------------------------------
# Meeting Requests Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/requests")
def get_meeting_requests(student_usn: Optional[str] = None, faculty_id: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
    SELECT r.*, f.name as faculty_name, f.department as faculty_department, s.name as student_name
    FROM meeting_requests r
    JOIN faculty f ON r.faculty_id = f.id
    JOIN students s ON r.student_usn = s.usn
    """
    params = []
    conditions = []
    if student_usn:
        conditions.append("r.student_usn = ?")
        params.append(student_usn)
    if faculty_id:
        conditions.append("r.faculty_id = ?")
        params.append(faculty_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY r.created_at DESC"

    cursor.execute(query, params)
    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return requests

@app.post("/api/requests")
async def create_meeting_request(payload: CreateRequestPayload):
    """Student submits an AI-negotiated slot request."""
    conn = get_db()
    cursor = conn.cursor()

    req_id = f"REQ-{datetime.now().strftime('%M%S')}"
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT INTO meeting_requests (
        id, student_usn, faculty_id, topic, urgency, status,
        proposed_slots, selected_slot, created_at, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req_id,
        payload.student_usn,
        payload.faculty_id,
        payload.topic,
        payload.urgency,
        "slots_offered",
        json.dumps(payload.proposed_slots),
        json.dumps(payload.selected_slot),
        now_iso,
        now_iso
    ))

    # Notify Faculty
    cursor.execute("""
    INSERT INTO notifications (recipient_type, recipient_id, title, message, type, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "faculty",
        payload.faculty_id,
        f"New Meeting Request ({payload.urgency} Urgency)",
        f"Student {payload.student_usn} selected slot '{payload.selected_slot.get('slot_time')}' for: {payload.topic}",
        "info",
        now_iso
    ))

    # Notify Student
    cursor.execute("""
    INSERT INTO notifications (recipient_type, recipient_id, title, message, type, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "student",
        payload.student_usn,
        "Request Dispatched to Faculty",
        f"Slot '{payload.selected_slot.get('slot_time')}' forwarded to faculty queue with automated SLA monitoring.",
        "success",
        now_iso
    ))

    conn.commit()
    conn.close()

    await broadcast_event("new_request", {
        "request_id": req_id,
        "student_usn": payload.student_usn,
        "faculty_id": payload.faculty_id,
        "topic": payload.topic,
        "urgency": payload.urgency
    })

    return {"success": True, "request_id": req_id}

@app.post("/api/requests/{request_id}/respond")
async def respond_to_request(request_id: str, payload: RespondRequestPayload):
    """Faculty confirms or rejects request."""
    conn = get_db()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute("SELECT * FROM meeting_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()
    if not req:
        conn.close()
        raise HTTPException(status_code=404, detail="Request not found")

    req = dict(req)

    cursor.execute("""
    UPDATE meeting_requests
    SET status = ?, faculty_notes = ?, updated_at = ?
    WHERE id = ?
    """, (payload.status, payload.notes or "", now_iso, request_id))

    # Notify student
    notif_title = f"Meeting Confirmed! ({request_id})" if payload.status == "confirmed" else f"Meeting Update ({request_id})"
    notif_type = "success" if payload.status == "confirmed" else "warning"

    cursor.execute("""
    INSERT INTO notifications (recipient_type, recipient_id, title, message, type, timestamp)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "student",
        req["student_usn"],
        notif_title,
        f"Faculty responded: Status is {payload.status.upper()}. Notes: {payload.notes or 'None'}",
        notif_type,
        now_iso
    ))

    conn.commit()
    conn.close()

    await broadcast_event("request_status_change", {
        "request_id": request_id,
        "status": payload.status,
        "notes": payload.notes
    })

    return {"success": True, "status": payload.status}

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@app.get("/api/notifications")
def get_notifications(recipient_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM notifications 
    WHERE recipient_id = ? 
    ORDER BY timestamp DESC LIMIT 20
    """, (recipient_id,))
    notifs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return notifs

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ---------------------------------------------------------------------------
# Mount Frontend Static Directory
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
