"""
CampusPulse AI - Application Entrypoint
Autonomous Smart RFID & Agentic Faculty-Student Dispatch System
Build for Billions Hackathon - Agentic AI Track
"""

import sys
import os

# Set UTF-8 encoding for standard outputs on Windows
if sys.platform.startswith("win"):
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from backend.database import init_db

def main():
    print("=" * 65)
    print(" [CampusPulse AI] Autonomous Smart RFID & Agentic Dispatch ")
    print("    Build for Billions Hackathon (Agentic AI For Billions)    ")
    print("=" * 65)
    
    # Ensure database is initialized and seeded
    init_db()
    
    print("\n[+] Database loaded & verified.")
    print("[+] Server-Sent Events (SSE) telemetry hub ready.")
    print("[+] 4 Autonomous Agents activated:")
    print("    1. NLIntakeAgent (Natural Language Parsing & Entity Resolution)")
    print("    2. AvailabilityAgent (Telemetry & Routine Blend Probability)")
    print("    3. NegotiationAgent (Autonomous Slot Synthesis & Reasoning)")
    print("    4. EscalationAgent (Watchdog SLA Failover & Alternate Routing)")
    print("\n[+] Serving Web Application at: http://127.0.0.1:8000")
    print("[+] API Documentation at:       http://127.0.0.1:8000/docs")
    print("[+] Hardware RFID Webhook at:   POST http://127.0.0.1:8000/api/rfid/tap\n")
    print("=" * 65)

    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
