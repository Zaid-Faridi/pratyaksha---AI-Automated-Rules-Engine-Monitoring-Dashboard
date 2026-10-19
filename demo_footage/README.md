# Pratyaksha Demo Footage Library & Multi-Centre Manifest

This directory houses per-centre video footage and configuration manifests for the multi-trade, multi-centre live monitoring system.

---

## 1. Directory Structure

```text
demo_footage/
├── manifest.yaml               # Master mapping of centres, cameras, trade profiles, zones & scenarios
├── manifest.json               # Auto-synced JSON representation for browser/API consumers
├── README.md                   # This field instruction manual
├── centre_mh_01/
│   └── cam_01.mp4              # Pune - IT & Digital Skills Lab
├── centre_up_02/
│   └── cam_up_01.mp4           # Varanasi - Sewing & Apparel Workshop
├── centre_ka_03/
│   └── cam_ka_01.mp4           # Bengaluru - Electrical & Electronics Lab
├── centre_or_04/
│   └── cam_or_01.mp4           # Bhubaneswar - Welding & Fabrication Bay
├── centre_rj_05/
│   └── cam_rj_01.mp4           # Jaipur - Beauty & Wellness Salon
└── centre_dl_06/
    └── cam_dl_01.mp4           # Delhi - Retail Sales & POS Counter
```

---

## 2. Placing Your Own Real / Self-Recorded Footage

To use your own licensed CCTV recordings or field trial video:

1. Record or export video clips from the training centre's camera (e.g. 720p or 1080p, 10–30 FPS).
2. Place the video file in the corresponding centre folder:
   ```bash
   cp /path/to/my_recording.mp4 demo_footage/centre_up_02/cam_up_01.mp4
   ```
3. Update `demo_footage/manifest.yaml` if you need custom ROI zone polygons calibrated to your camera angle.
4. **Physical RTSP Streams:** If connecting to a live physical IP camera over the local network, replace the video file path in `manifest.yaml` with the RTSP URI:
   ```yaml
   video_source: "rtsp://admin:password@192.168.1.100:554/stream1"
   ```

---

## 3. Supported Formats & Codecs

- **Container:** `.mp4`, `.mkv`, `.avi`, `.mov`
- **Video Codec:** H.264 (AVC) or MPEG-4 (widely supported by OpenCV `cv2.VideoCapture`)
- **Recommended Resolution:** $1280 \times 720$ (HD) or $640 \times 360$ (SD)
- **Audio:** Audio tracks are ignored; video analytics processes visual frames only.

---

## 4. Demo Violation Scenarios

The system allows injecting demonstration scenarios per clip:
- `compliant`: Normal operating session, full attendance, verified safety equipment.
- `attendance_shortfall`: Inflated claimed attendance (e.g., claimed 25 vs 8 detected).
- `missing_machine`: Sanctioned machine missing or moved from zone.
- `missing_ppe`: Trainees working in industrial zone without required protective gear.
- `instructor_absent`: Podium/demonstration area vacant during active class hours.
- `capacity_deficit`: Insufficient workstations for the registered batch size.
- `idle_session`: Trainees present but completely inactive with no equipment running.
