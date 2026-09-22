/**
 * CampusPulse AI - Front-End Application Logic
 * Build for Billions Hackathon - Agentic AI Track
 * 
 * Features:
 * - Real-time SSE telemetry synchronization (EventSource)
 * - 4 Autonomous Agents Client Interaction:
 *   1. NLIntakeAgent (speech/text parser)
 *   2. AvailabilityAgent (predictive dwell & probability)
 *   3. NegotiationAgent (autonomous multi-factor slot synthesis)
 *   4. EscalationAgent (watchdog SLA failover & re-routing)
 * - Interactive RFID Hardware Simulator & Webhook sender
 * - Agentic AI Brain Live Inspector for Hackathon Judges
 */

// Global State
const state = {
  currentStudent: {
    usn: "1MS21CS042",
    name: "Aarav Sharma",
    department: "Computer Science & Engineering"
  },
  currentFacultyId: "FAC001",
  facultyList: [],
  selectedFaculty: null,
  currentNegotiation: {
    slots: [],
    selectedSlot: null,
    topic: "",
    urgency: "MEDIUM"
  },
  activeRequests: [],
  notifications: [],
  sseSource: null
};

// ==========================================================================
// Initialization & SSE Setup
// ==========================================================================
document.addEventListener("DOMContentLoaded", async () => {
  initNavigation();
  initAuthShortcuts();
  initNLIntake();
  initHardwareSimulator();
  initBrainInspector();
  initModals();

  // Load initial data
  await loadFaculty();
  await loadStudentRequests();
  await loadFacultyPortal();
  await loadNotifications();
  await loadAgentLogs();

  // Start Real-Time SSE Stream
  setupEventSource();
});

function setupEventSource() {
  if (state.sseSource) {
    state.sseSource.close();
  }

  const indicator = document.getElementById("telemetry-indicator");
  state.sseSource = new EventSource("/api/events");

  state.sseSource.onopen = () => {
    if (indicator) {
      indicator.innerHTML = '<span class="pulse-indicator"></span><span class="telemetry-text">Telemetry: LIVE</span>';
      indicator.style.borderColor = "rgba(16, 185, 129, 0.4)";
    }
  };

  state.sseSource.onerror = () => {
    if (indicator) {
      indicator.innerHTML = '<span class="pulse-indicator" style="background:#ef4444"></span><span class="telemetry-text" style="color:#f87171">Telemetry: Reconnecting</span>';
    }
  };

  // RFID Tap Event
  state.sseSource.addEventListener("rfid_update", (e) => {
    const data = JSON.parse(e.data);
    showToast(`📡 RFID Door Tap: ${data.faculty_name} (${data.status}) at ${data.reader_name}`, "info");
    loadFaculty();
    loadFacultyPortal();
    updateSimulatorOccupants();
    loadAgentLogs();
  });

  // New Request Created
  state.sseSource.addEventListener("new_request", (e) => {
    const data = JSON.parse(e.data);
    showToast(`📋 New Meeting Request from ${data.student_usn} for ${data.topic}`, "info");
    loadStudentRequests();
    loadFacultyPortal();
    loadNotifications();
  });

  // Request Status Changed
  state.sseSource.addEventListener("request_status_change", (e) => {
    const data = JSON.parse(e.data);
    showToast(`🔔 Meeting status updated: ${data.status.toUpperCase()}`, "success");
    loadStudentRequests();
    loadFacultyPortal();
    loadNotifications();
  });

  // Escalation Event
  state.sseSource.addEventListener("escalation_event", (e) => {
    const data = JSON.parse(e.data);
    showToast(`🚨 Autonomous Escalation Triggered! ${data.count} request(s) re-routed.`, "escalation");
    loadStudentRequests();
    loadFacultyPortal();
    loadNotifications();
    loadAgentLogs();
  });

  // Agent Thought Log Broadcast
  state.sseSource.addEventListener("agent_thought", (e) => {
    loadAgentLogs();
  });
}

// ==========================================================================
// Navigation & View Switching
// ==========================================================================
function initNavigation() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.target;
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      document.querySelectorAll(".portal-view").forEach(view => {
        view.classList.add("hidden");
        view.classList.remove("active");
      });

      const targetView = document.getElementById(targetId);
      if (targetView) {
        targetView.classList.remove("hidden");
        targetView.classList.add("active");
      }

      // Refresh view-specific data
      if (targetId === "view-faculty") {
        loadFacultyPortal();
      } else if (targetId === "view-rfid") {
        updateSimulatorOccupants();
      } else if (targetId === "view-brain") {
        loadAgentLogs();
      }
    });
  });

  // Switch Account Button
  const btnSwitch = document.getElementById("btn-switch-account");
  if (btnSwitch) {
    btnSwitch.addEventListener("click", () => {
      const overlay = document.getElementById("student-auth-overlay");
      if (overlay) overlay.classList.remove("hidden");
    });
  }

  // Notification Bell Click
  const bell = document.getElementById("btn-notification-bell");
  const notifPanel = document.getElementById("notification-panel");
  if (bell && notifPanel) {
    bell.addEventListener("click", (e) => {
      e.stopPropagation();
      notifPanel.classList.toggle("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!notifPanel.contains(e.target) && e.target !== bell) {
        notifPanel.classList.add("hidden");
      }
    });
  }

  // Clear Notifs
  const btnClearNotifs = document.getElementById("btn-clear-notifs");
  if (btnClearNotifs) {
    btnClearNotifs.addEventListener("click", () => {
      const list = document.getElementById("notif-list");
      if (list) list.innerHTML = '<div class="empty-state">No new notifications</div>';
      const counter = document.getElementById("notif-counter");
      if (counter) counter.textContent = "0";
    });
  }
}

// ==========================================================================
// Student Auth & Demo Profiles
// ==========================================================================
async function initAuthShortcuts() {
  try {
    const res = await fetch("/api/students");
    const students = await res.json();
    const container = document.getElementById("demo-student-chips");
    if (container && students.length > 0) {
      container.innerHTML = "";
      students.forEach(s => {
        const chip = document.createElement("button");
        chip.className = "chip-btn";
        chip.textContent = `${s.name} (${s.usn})`;
        chip.onclick = () => {
          document.getElementById("input-usn").value = s.usn;
          document.getElementById("input-dob").value = s.dob;
        };
        container.appendChild(chip);
      });
    }
  } catch (err) {
    console.warn("Could not load sample students:", err);
  }

  const authForm = document.getElementById("student-login-form");
  if (authForm) {
    authForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const usn = document.getElementById("input-usn").value;
      const dob = document.getElementById("input-dob").value;

      try {
        const res = await fetch("/api/auth/student", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ usn, dob })
        });
        const data = await res.json();
        if (data.success) {
          state.currentStudent = data.student;
          updateUserDisplay();
          document.getElementById("student-auth-overlay").classList.add("hidden");
          showToast(`Welcome, ${data.student.name}!`, "success");
          loadStudentRequests();
          loadNotifications();
        } else {
          showToast(data.detail || "Authentication failed", "escalation");
        }
      } catch (err) {
        showToast("Error authenticating student", "escalation");
      }
    });
  }
}

function updateUserDisplay() {
  const nameEl = document.getElementById("user-display-name");
  const roleEl = document.getElementById("user-display-role");
  const initialsEl = document.getElementById("user-avatar-initials");

  if (nameEl) nameEl.textContent = state.currentStudent.name;
  if (roleEl) roleEl.textContent = state.currentStudent.usn;
  if (initialsEl) {
    const parts = state.currentStudent.name.split(" ");
    initialsEl.textContent = parts.map(p => p[0]).join("").substring(0, 2).toUpperCase();
  }
}

// ==========================================================================
// 1. Natural Language Intake Agent
// ==========================================================================
function initNLIntake() {
  const form = document.getElementById("nl-intake-form");
  const input = document.getElementById("nl-query-input");

  // Sample quick buttons
  document.getElementById("btn-nl-sample-1")?.addEventListener("click", () => {
    input.value = "Need urgent meeting with Prof Rao about my capstone distributed cache before 4pm";
  });
  document.getElementById("btn-nl-sample-2")?.addEventListener("click", () => {
    input.value = "Want to meet Dr Ananya Sharma to clear doubts on neural network backprop lab";
  });
  document.getElementById("btn-nl-sample-3")?.addEventListener("click", () => {
    input.value = "Can I meet Prof Vikram Seth regarding cryptography assignment extension?";
  });

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text) return;

      const indicator = document.getElementById("intake-thinking-indicator");
      const thinkingText = document.getElementById("intake-thinking-text");

      if (indicator) indicator.classList.remove("hidden");
      if (thinkingText) thinkingText.textContent = "NL Intake Agent is extracting entities, faculty match, and urgency...";

      try {
        // Step 1: Call NL Intake Agent
        const res = await fetch("/api/agent/intake", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text })
        });
        const parsed = await res.json();

        if (thinkingText) thinkingText.textContent = `Matched ${parsed.faculty_name} (${parsed.urgency}). Negotiation Agent synthesizing slots...`;

        // Step 2: Call Negotiation Agent to generate candidate slots
        const negoRes = await fetch("/api/agent/negotiate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            student_usn: state.currentStudent.usn,
            faculty_id: parsed.faculty_id,
            topic: parsed.topic,
            urgency: parsed.urgency
          })
        });
        const negoData = await negoRes.json();

        // Step 3: Open Negotiation Modal for Student to choose slot
        openNegotiationModal({
          facultyId: parsed.faculty_id,
          facultyName: parsed.faculty_name,
          topic: parsed.topic,
          urgency: parsed.urgency,
          slots: negoData.slots
        });

      } catch (err) {
        showToast("Error processing request with Agent", "escalation");
        console.error(err);
      } finally {
        if (indicator) indicator.classList.add("hidden");
      }
    });
  }
}

// ==========================================================================
// 2. Faculty Radar & Availability Agent
// ==========================================================================
async function loadFaculty() {
  try {
    const res = await fetch("/api/faculty");
    const faculty = await res.json();
    state.facultyList = faculty;
    renderFacultyCards(faculty);
    populateFacultyProfileDropdown(faculty);
  } catch (err) {
    console.error("Error loading faculty:", err);
  }
}

function renderFacultyCards(facultyList) {
  const container = document.getElementById("faculty-cards-container");
  if (!container) return;

  const deptFilter = document.getElementById("filter-department")?.value || "ALL";
  const statusFilter = document.getElementById("filter-status")?.value || "ALL";

  const filtered = facultyList.filter(f => {
    const matchDept = deptFilter === "ALL" || f.department === deptFilter;
    const matchStatus = statusFilter === "ALL" || f.status === statusFilter;
    return matchDept && matchStatus;
  });

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-state" style="grid-column: 1/-1; padding: 40px; text-align: center; color: #94a3b8;">No faculty found matching the selected filters.</div>';
    return;
  }

  container.innerHTML = filtered.map(f => {
    const statusClass = getStatusClass(f.status);
    const pred = f.prediction || {};
    const probPercent = Math.round((pred.presence_probability || 0.85) * 100);

    return `
      <div class="faculty-card" id="card-${f.id}">
        <div class="faculty-card-top">
          <img src="${f.avatar}" alt="${f.name}" class="faculty-avatar">
          <div class="faculty-meta">
            <h4 class="faculty-name">${f.name}</h4>
            <p class="faculty-dept">${f.designation}</p>
            <span class="status-badge ${statusClass}">
              <span class="dot ${statusClass}"></span>
              ${f.status}
            </span>
          </div>
        </div>

        <div class="telemetry-row">
          <div>
            <span style="color:#94a3b8; font-size:0.7rem; display:block;">LIVE LOCATION</span>
            <span class="location-room">📍 ${f.current_room}</span>
          </div>
          <div class="rfid-indicator">
            <span>Tag: ${f.rfid_tag}</span>
          </div>
        </div>

        <div class="predictive-box">
          <div class="predictive-header">
            <span>⚡ Availability Agent</span>
            <span class="prob-score">${probPercent}% Presence Confidence</span>
          </div>
          <p class="predictive-state">${pred.predicted_state || 'RFID door sensor active'}</p>
          <div style="font-size:0.74rem; color:#818cf8; margin-top:4px;">
            <strong>Next Free:</strong> ${pred.next_free_window || 'Calculating...'}
          </div>
        </div>

        <div class="card-actions">
          <button class="action-btn" onclick="triggerDirectMeeting('${f.id}')">
            <span>⚡ Request Meeting</span>
          </button>
          <button class="action-btn secondary" title="View Routine & Cabin" onclick="showFacultyDetailsModal('${f.id}')">
            <span>ℹ️</span>
          </button>
        </div>
      </div>
    `;
  }).join("");

  // Attach filter listeners
  document.getElementById("filter-department")?.addEventListener("change", () => renderFacultyCards(state.facultyList));
  document.getElementById("filter-status")?.addEventListener("change", () => renderFacultyCards(state.facultyList));
}

function getStatusClass(status) {
  if (status === "In Cabin") return "cabin";
  if (status === "In Lecture") return "lecture";
  if (status === "In Library") return "library";
  if (status === "Off Campus") return "offcampus";
  return "moving";
}

// Direct Meeting Request from Card
window.triggerDirectMeeting = async function(facultyId) {
  const faculty = state.facultyList.find(f => f.id === facultyId);
  if (!faculty) return;

  const topic = prompt(`Enter topic/reason to meet ${faculty.name}:`, "Capstone Project & Coursework Discussion");
  if (!topic) return;

  try {
    showToast("Negotiation Agent synthesizing slots...", "info");
    const res = await fetch("/api/agent/negotiate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        student_usn: state.currentStudent.usn,
        faculty_id: facultyId,
        topic: topic,
        urgency: "HIGH"
      })
    });
    const data = await res.json();

    openNegotiationModal({
      facultyId: faculty.id,
      facultyName: faculty.name,
      topic: topic,
      urgency: "HIGH",
      slots: data.slots
    });
  } catch (err) {
    showToast("Error proposing slots", "escalation");
  }
};

// ==========================================================================
// 3. Meeting Negotiation Modal & Booking
// ==========================================================================
function initModals() {
  const modal = document.getElementById("negotiation-modal");
  const closeBtn = document.getElementById("btn-close-modal");
  const cancelBtn = document.getElementById("btn-cancel-modal");
  const confirmBtn = document.getElementById("btn-confirm-booking");

  const closeModal = () => {
    if (modal) modal.classList.add("hidden");
    state.currentNegotiation.selectedSlot = null;
  };

  if (closeBtn) closeBtn.onclick = closeModal;
  if (cancelBtn) cancelBtn.onclick = closeModal;

  if (confirmBtn) {
    confirmBtn.onclick = async () => {
      if (!state.currentNegotiation.selectedSlot) return;

      confirmBtn.disabled = true;
      confirmBtn.textContent = "Dispatched to Faculty...";

      try {
        const payload = {
          student_usn: state.currentStudent.usn,
          faculty_id: state.currentNegotiation.facultyId,
          topic: state.currentNegotiation.topic,
          urgency: state.currentNegotiation.urgency,
          selected_slot: state.currentNegotiation.selectedSlot,
          proposed_slots: state.currentNegotiation.slots
        };

        const res = await fetch("/api/requests", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
          showToast(`Meeting slot booked! Request ID: ${result.request_id}`, "success");
          closeModal();
          loadStudentRequests();
        } else {
          showToast("Failed to book slot", "escalation");
        }
      } catch (err) {
        showToast("Error submitting meeting request", "escalation");
      } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = "Confirm Selected Slot";
      }
    };
  }
}

function openNegotiationModal(data) {
  state.currentNegotiation = {
    ...data,
    selectedSlot: null
  };

  const modal = document.getElementById("negotiation-modal");
  const targetFacultyName = document.getElementById("modal-target-faculty-name");
  const reviewTopic = document.getElementById("modal-review-topic");
  const reviewUrgency = document.getElementById("modal-review-urgency");
  const slotsContainer = document.getElementById("modal-slots-container");
  const confirmBtn = document.getElementById("btn-confirm-booking");

  if (targetFacultyName) targetFacultyName.textContent = `Meeting with ${data.facultyName}`;
  if (reviewTopic) reviewTopic.textContent = data.topic;
  if (reviewUrgency) reviewUrgency.textContent = data.urgency;
  if (confirmBtn) confirmBtn.disabled = true;

  if (slotsContainer) {
    if (!data.slots || data.slots.length === 0) {
      slotsContainer.innerHTML = '<div class="empty-state">No slots generated.</div>';
    } else {
      slotsContainer.innerHTML = data.slots.map((s, idx) => `
        <div class="slot-option-card ${idx === 0 ? 'selected' : ''}" data-index="${idx}" onclick="selectModalSlot(${idx})">
          <div class="slot-top-row">
            <span class="slot-time-text">🕒 ${s.slot_time}</span>
            <span class="slot-conf-pill">${Math.round(s.confidence * 100)}% Match</span>
          </div>
          <div style="font-size:0.78rem; font-weight:700; color:#38bdf8;">📍 ${s.location}</div>
          <p class="slot-reasoning-text">${s.reasoning}</p>
        </div>
      `).join("");

      // Auto-select first slot
      selectModalSlot(0);
    }
  }

  if (modal) modal.classList.remove("hidden");
}

window.selectModalSlot = function(index) {
  const slots = state.currentNegotiation.slots;
  if (!slots || !slots[index]) return;

  state.currentNegotiation.selectedSlot = slots[index];

  document.querySelectorAll(".slot-option-card").forEach((card, idx) => {
    if (idx === index) {
      card.classList.add("selected");
    } else {
      card.classList.remove("selected");
    }
  });

  const confirmBtn = document.getElementById("btn-confirm-booking");
  if (confirmBtn) confirmBtn.disabled = false;
};

// ==========================================================================
// Student Requests & Escalation Timeline
// ==========================================================================
async function loadStudentRequests() {
  try {
    const res = await fetch(`/api/requests?student_usn=${state.currentStudent.usn}`);
    const requests = await res.json();
    state.activeRequests = requests;

    const countBadge = document.getElementById("active-requests-count");
    if (countBadge) countBadge.textContent = requests.length;

    const container = document.getElementById("student-requests-container");
    if (!container) return;

    if (requests.length === 0) {
      container.innerHTML = '<div class="empty-state" style="padding: 24px; text-align: center; color: #64748b;">No active requests. Use the AI bar above to schedule your first meeting!</div>';
      return;
    }

    container.innerHTML = requests.map(req => {
      let slotData = {};
      try {
        slotData = typeof req.selected_slot === "string" ? JSON.parse(req.selected_slot) : req.selected_slot;
      } catch (e) {
        slotData = { slot_time: req.selected_slot || "Pending" };
      }

      const isEscalated = req.status === "escalated";
      const statusClass = req.status.toLowerCase();

      return `
        <div class="request-card ${isEscalated ? 'escalated' : ''}">
          <div class="request-header">
            <span class="req-id">${req.id}</span>
            <span class="req-status-badge ${statusClass}">${req.status}</span>
          </div>
          <div class="req-faculty">${req.faculty_name}</div>
          <div class="req-topic"><strong>Topic:</strong> ${req.topic}</div>
          <div class="req-slot">🕒 ${slotData?.slot_time || 'AI Slot Selected'}</div>
          
          ${isEscalated ? `
            <div class="escalation-box">
              <strong>🚨 Autonomous Escalation:</strong>
              <div>${req.escalation_reason}</div>
              <div style="margin-top:4px; font-weight:700;">Rerouted to: ${req.escalated_to}</div>
            </div>
          ` : `
            <div style="display:flex; justify-content:flex-end; margin-top:4px;">
              <button class="text-btn" style="color:#ef4444; font-size:0.72rem;" onclick="triggerManualEscalation('${req.id}')">
                ⚡ Test Auto-Escalation
              </button>
            </div>
          `}
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading student requests:", err);
  }
}

window.triggerManualEscalation = async function(requestId) {
  try {
    showToast("Escalation Agent analyzing SLA and re-routing...", "info");
    const res = await fetch("/api/agent/escalate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId })
    });
    const data = await res.json();
    if (data.success) {
      showToast("Request escalated autonomously!", "escalation");
      loadStudentRequests();
      loadFacultyPortal();
      loadAgentLogs();
    }
  } catch (err) {
    showToast("Error triggering escalation", "escalation");
  }
};

// ==========================================================================
// Faculty Portal Logic
// ==========================================================================
function populateFacultyProfileDropdown(facultyList) {
  const select = document.getElementById("select-faculty-profile");
  if (!select) return;

  select.innerHTML = facultyList.map(f => `
    <option value="${f.id}" ${f.id === state.currentFacultyId ? 'selected' : ''}>
      ${f.name} — ${f.designation} (${f.status})
    </option>
  `).join("");

  select.onchange = (e) => {
    state.currentFacultyId = e.target.value;
    loadFacultyPortal();
  };
}

async function loadFacultyPortal() {
  if (!state.currentFacultyId) return;

  try {
    const res = await fetch(`/api/faculty/${state.currentFacultyId}`);
    const faculty = await res.json();

    // Update status bar
    const statusBadge = document.getElementById("faculty-portal-status-badge");
    const statusText = document.getElementById("faculty-portal-status-text");
    const roomText = document.getElementById("faculty-portal-room-text");

    if (statusText) statusText.textContent = faculty.status;
    if (roomText) roomText.textContent = `Detected in: ${faculty.current_room}`;
    if (statusBadge) {
      statusBadge.className = `status-chip prominent ${getStatusClass(faculty.status)}`;
    }

    // Timetable
    const ttContainer = document.getElementById("faculty-timetable-container");
    if (ttContainer && faculty.timetable) {
      ttContainer.innerHTML = faculty.timetable.map(t => `
        <div class="tt-item">
          <div>
            <span class="tt-time">${t.day_of_week} ${t.start_time} - ${t.end_time}</span>
            <div class="tt-activity">${t.activity}</div>
          </div>
          <span style="color:#94a3b8; font-size:0.74rem;">${t.room_id}</span>
        </div>
      `).join("");
    }

    // Delegate info
    const delegateBox = document.getElementById("faculty-delegate-box");
    if (delegateBox) {
      delegateBox.innerHTML = `
        <p><strong>Primary TA:</strong> ${faculty.ta_name || 'None Assigned'}</p>
        <p><strong>TA Email:</strong> ${faculty.ta_email || 'N/A'}</p>
        <p style="margin-top:6px;"><strong>Alternate Faculty Delegate:</strong> ${faculty.alternate_faculty_id || 'Department Head'}</p>
        <p style="font-size:0.74rem; color:#94a3b8; margin-top:4px;">* Autonomous Escalation Agent routes requests here if faculty is off-campus or SLA lapses.</p>
      `;
    }

    // Load Incoming Requests for this faculty
    const reqRes = await fetch(`/api/requests?faculty_id=${state.currentFacultyId}`);
    const queue = await reqRes.json();
    renderFacultyQueue(queue);

  } catch (err) {
    console.error("Error loading faculty portal:", err);
  }

  // Override Buttons
  document.getElementById("btn-override-cabin")?.addEventListener("click", () => overrideFacultyStatus("In Cabin", "Cabin"));
  document.getElementById("btn-override-dnd")?.addEventListener("click", () => overrideFacultyStatus("Do Not Disturb", "Cabin"));
  document.getElementById("btn-refresh-faculty-queue")?.addEventListener("click", loadFacultyPortal);
}

async function overrideFacultyStatus(status, room) {
  try {
    await fetch(`/api/faculty/${state.currentFacultyId}/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, current_room: room })
    });
    showToast(`Status overridden to ${status}`, "info");
    loadFaculty();
    loadFacultyPortal();
  } catch (err) {
    showToast("Error updating status", "escalation");
  }
}

function renderFacultyQueue(queue) {
  const container = document.getElementById("faculty-request-queue");
  if (!container) return;

  if (queue.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding: 30px; text-align: center; color: #94a3b8;">No pending requests in your queue. All students handled!</div>';
    return;
  }

  container.innerHTML = queue.map(req => {
    let slot = {};
    try {
      slot = typeof req.selected_slot === "string" ? JSON.parse(req.selected_slot) : req.selected_slot;
    } catch (e) {
      slot = { slot_time: req.selected_slot };
    }

    const isUrgent = req.urgency === "HIGH" || req.urgency === "EMERGENCY";
    const isEscalated = req.status === "escalated";

    return `
      <div class="queue-item-card ${isUrgent ? 'urgent' : ''}">
        <div class="queue-meta-row">
          <div class="student-info">
            <span class="student-tag">${req.student_usn}</span>
            <strong style="color:#ffffff;">${req.student_name}</strong>
          </div>
          <span class="req-status-badge ${req.status}">${req.status}</span>
        </div>

        <div>
          <div style="font-weight:700; color:#ffffff; font-size:0.92rem;">${req.topic}</div>
          <div style="font-size:0.78rem; color:#a5b4fc; margin-top:2px;">Proposed Slot: 🕒 ${slot?.slot_time || 'N/A'} (Location: ${slot?.location || 'Cabin'})</div>
        </div>

        ${isEscalated ? `
          <div class="escalation-box">
            <strong>Escalated:</strong> ${req.escalation_reason}
          </div>
        ` : `
          <div class="queue-actions">
            <button class="primary-btn btn-sm" onclick="respondToMeeting('${req.id}', 'confirmed')">
              ✓ Accept Slot
            </button>
            <button class="secondary-btn btn-sm" onclick="respondToMeeting('${req.id}', 'rejected')">
              ✕ Decline
            </button>
            <button class="secondary-btn btn-sm" style="color:#ef4444;" onclick="triggerManualEscalation('${req.id}')">
              ⚡ Escalate
            </button>
          </div>
        `}
      </div>
    `;
  }).join("");
}

window.respondToMeeting = async function(requestId, status) {
  const notes = prompt(`Optional note for student (${status}):`, status === "confirmed" ? "Please bring your rough architecture draft." : "Conflict with academic meeting.");
  try {
    const res = await fetch(`/api/requests/${requestId}/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, notes })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Request marked as ${status.toUpperCase()}`, "success");
      loadFacultyPortal();
      loadStudentRequests();
    }
  } catch (err) {
    showToast("Error responding to request", "escalation");
  }
};

// ==========================================================================
// 4. RFID Hardware Simulator
// ==========================================================================
function initHardwareSimulator() {
  const btnSendRaw = document.getElementById("btn-send-raw-tap");
  if (btnSendRaw) {
    btnSendRaw.addEventListener("click", async () => {
      const reader_id = document.getElementById("sim-input-reader").value;
      const tag_id = document.getElementById("sim-input-tag").value;
      const direction = document.getElementById("sim-input-direction").value;

      simulateTap(reader_id, tag_id, direction);
    });
  }
}

window.simulateTap = async function(readerId, tagId, direction) {
  try {
    showToast(`Sending hardware tap: ${readerId} [${direction}]...`, "info");
    const res = await fetch("/api/rfid/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reader_id: readerId,
        tag_id: tagId,
        direction: direction
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(result.message, "success");
      updateSimulatorOccupants();
    } else {
      showToast(result.detail || "Tap failed", "escalation");
    }
  } catch (err) {
    showToast("Error transmitting RFID webhook event", "escalation");
  }
};

function updateSimulatorOccupants() {
  if (!state.facultyList || state.facultyList.length === 0) return;

  state.facultyList.forEach(f => {
    // Cabin 304
    const occ304 = document.getElementById("occupant-room-304");
    if (occ304) {
      if (f.id === "FAC001" && f.status === "In Cabin") {
        occ304.textContent = `Occupied: ${f.name}`;
        occ304.style.color = "#34d399";
      } else if (f.id === "FAC001") {
        occ304.textContent = "Vacant";
        occ304.style.color = "#94a3b8";
      }
    }

    // Cabin 308
    const occ308 = document.getElementById("occupant-room-308");
    if (occ308) {
      if (f.id === "FAC002" && f.status === "In Cabin") {
        occ308.textContent = `Occupied: ${f.name}`;
        occ308.style.color = "#34d399";
      } else if (f.id === "FAC002") {
        occ308.textContent = "Vacant";
        occ308.style.color = "#94a3b8";
      }
    }

    // LH-102
    const occLH102 = document.getElementById("occupant-lh-102");
    if (occLH102 && f.current_room.includes("102")) {
      occLH102.textContent = `In Session: ${f.name}`;
      occLH102.style.color = "#60a5fa";
    }

    // Library
    const occLib = document.getElementById("occupant-lib-main");
    if (occLib && f.status === "In Library") {
      occLib.textContent = `Present: ${f.name}`;
      occLib.style.color = "#a78bfa";
    }
  });
}

// ==========================================================================
// 5. Agentic AI Brain Inspector (Hackathon Judge Console)
// ==========================================================================
function initBrainInspector() {
  const btnTrigger = document.getElementById("btn-trigger-ai-escalation");
  const btnRefresh = document.getElementById("btn-refresh-agent-logs");

  if (btnTrigger) {
    btnTrigger.addEventListener("click", async () => {
      showToast("Watchdog daemon executing full escalation sweep...", "info");
      const res = await fetch("/api/agent/escalate", { method: "POST" });
      const data = await res.json();
      showToast(`Escalation sweep finished: ${data.escalated_count} actions taken.`, "success");
      loadAgentLogs();
      loadStudentRequests();
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", loadAgentLogs);
  }
}

async function loadAgentLogs() {
  const container = document.getElementById("agent-logs-container");
  if (!container) return;

  try {
    const res = await fetch("/api/agent/logs");
    const logs = await res.json();

    if (logs.length === 0) {
      container.innerHTML = '<div class="empty-state">No agent thoughts recorded yet.</div>';
      return;
    }

    container.innerHTML = logs.map(log => {
      const agentClean = log.agent_name.replace(/\[.*\]/, "").trim();
      const timeFormatted = new Date(log.timestamp).toLocaleTimeString();

      return `
        <div class="log-entry ${agentClean}">
          <div class="log-header">
            <span class="log-agent-name">${log.agent_name} » ${log.action}</span>
            <span class="log-time">${timeFormatted}</span>
          </div>
          <div style="color:#94a3b8; font-size:0.72rem;"><strong>Input Context:</strong> ${log.input_summary}</div>
          <div class="log-thought"><strong>Chain of Thought:</strong> ${log.thought_process}</div>
          <div class="log-output"><strong>Autonomous Decision:</strong> ${log.output_summary}</div>
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Error loading agent logs:", err);
  }
}

// ==========================================================================
// Notifications & Toast Utilities
// ==========================================================================
async function loadNotifications() {
  if (!state.currentStudent?.usn) return;

  try {
    const res = await fetch(`/api/notifications?recipient_id=${state.currentStudent.usn}`);
    const notifs = await res.json();
    state.notifications = notifs;

    const counter = document.getElementById("notif-counter");
    const list = document.getElementById("notif-list");

    if (counter) counter.textContent = notifs.length;
    if (list) {
      if (notifs.length === 0) {
        list.innerHTML = '<div class="empty-state">No new notifications</div>';
      } else {
        list.innerHTML = notifs.map(n => `
          <div class="notif-item ${n.type}">
            <div class="notif-title">${n.title}</div>
            <div class="notif-desc">${n.message}</div>
            <div class="notif-time">${new Date(n.timestamp).toLocaleTimeString()}</div>
          </div>
        `).join("");
      }
    }
  } catch (err) {
    console.error("Error loading notifications:", err);
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(20px)";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
