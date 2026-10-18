# Pratyaksha 3-Minute Presentation & Live Demo Script

**Audience:** MSDE Evaluators, Hackathon Jury, and Technical Observers  
**Target Duration:** 3 Minutes  
**Prerequisites:** Backend running (`localhost:8088`), Dashboard running (`localhost:5188`).

---

## Timeline & Narrative Breakdown

### [0:00 – 0:40] The Problem Statement & Privacy Philosophy
- **Presenter:**  
  *"Good morning, esteemed jury. Across thousands of government skilling centres funded under PMKVY and DDU-GKY, public funds rely on two assumptions: that enrolled students are genuinely attending classes, and that sanctioned high-value machinery is physically present.*  
  *Manual inspections are infrequent, and biometric punches suffer from proxy fraud and off-site claims. Commercial CCTV surveillance, on the other hand, introduces severe privacy risks with invasive facial recognition and demands impossible bandwidth on rural telecom towers.*  
  *Today, we present **Pratyaksha** — an AI video-analytics system designed from the ground up for privacy-preserving, ultra-low bandwidth monitoring."*

### [0:40 – 1:20] Live Dashboard Overview & National Map
*(Action: Open browser to `http://localhost:5188/`)*
- **Presenter:**  
  *"Here is our central monitoring dashboard. At a glance, an officer sees the national pulse: 5 centres, active alerts, and real-time compliance ratings.*  
  *Notice our national map: centres are color-coded by an automated compliance score computed from attendance accuracy, sanctioned equipment reconciliation, and camera uptime.*  
  *Let's click on **Jaipur Industrial Skilling Hub** — it’s marked red with a 61% rating. Opening the centre detail, we immediately see the live attendance chart: 25 students were claimed on the government portal, but our camera feed detects only 4 trainees present in the classroom zone. That’s a severe ghost batch violation."*

### [1:20 – 2:05] The Low-Bandwidth Edge & Privacy by Design
*(Action: Switch to terminal or show `docs/privacy_design_note.md` / `edge/`)*
- **Presenter:**  
  *"How does this work in rural centres with 2G or poor connectivity?*  
  *We don't stream video to the cloud. Our lightweight edge agent runs YOLO inference locally on low-cost hardware like a Raspberry Pi 4 or Intel N100 mini PC.*  
  *Crucially: **Zero facial identification. Zero raw video is ever stored or uploaded.**  
  *The edge writes numerical counts to a local SQLite outbox that survives power outages. When connectivity is available, it syncs compact, gzip-compressed payloads at **just 245 bytes per sample** — less than 1 megabyte per month!*  
  *Only when an anomaly triggers does it lazily upload a downscaled, $320\text{ px}$ thumbnail where **all human faces and bodies are permanently blurred at the edge** before leaving the device."*

### [2:05 – 2:45] Alert Queue Triage & Human-in-the-Loop Workflow
*(Action: Navigate to `http://localhost:5188/alerts` and open an active alert)*
- **Presenter:**  
  *"Back on the dashboard, let's step into the shoes of a Scheme Monitoring Officer triaging the Alert Queue.*  
  *Here is an open **ATTENDANCE_MISMATCH** alert. Opening the triage drawer, the officer reviews the evidence: claimed headcount of 25, rolling median of 4, and the pre-blurred diagnostic thumbnail confirming an empty classroom.*  
  *The officer clicks **Verify Alert**, enters written inspection notes, and submits. The alert is confirmed, the audit trail is permanently recorded, and the centre's compliance score automatically updates in real-time."*

### [2:45 – 3:00] Conclusion & Scalability
- **Presenter:**  
  *"In our quantitative benchmarks across 60 controlled test frames with low-light, blur, and occlusion degradations, Pratyaksha achieved a **0.79 person count MAE**, a **0.0% false positive alert rate**, and **33 millisecond inference on CPU**.*  
  *Pratyaksha proves that automated government compliance monitoring does not require sacrificing trainee privacy or blowing through telecom budgets.*  
  *Thank you, and we welcome your questions."*
