"""
Rules Engine for Pratyaksha Backend.
Evaluates compliance rules, detects discrepancies, manages alert lifecycle
(de-duplication and auto-resolution), and computes weighted compliance scores.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Alert,
    AttendanceRecord,
    Batch,
    Camera,
    Centre,
    DetectionEvent,
    SanctionedInventory,
    utcnow,
)


class RulesEngine:
    """
    Core business logic and automated compliance auditor for skilling centres.
    """

    @staticmethod
    def is_time_in_batch_window(batch: Batch, dt: datetime) -> bool:
        """
        Check if datetime falls within a batch's scheduled days and time window.
        """
        if not batch or not batch.days:
            return False

        # Day check (accepts full names e.g. "Monday" or short "Mon")
        day_full = dt.strftime("%A")
        day_short = dt.strftime("%a")
        batch_days_lower = [d.lower() for d in batch.days]
        if day_full.lower() not in batch_days_lower and day_short.lower() not in batch_days_lower:
            return False

        # Time check (HH:MM strings)
        time_str = dt.strftime("%H:%M")
        return batch.start_time <= time_str <= batch.end_time

    @classmethod
    def get_active_batches(cls, db: Session, centre_id: str, dt: datetime, zone: Optional[str] = None) -> List[Batch]:
        """
        Find batches actively running at the specified centre, time, and zone.
        """
        query = db.query(Batch).filter(Batch.centre_id == centre_id)
        if zone:
            query = query.filter((Batch.zone == zone) | (Batch.zone.is_(None)))
        batches = query.all()
        return [b for b in batches if cls.is_time_in_batch_window(b, dt)]

    # --- Rule 1: Attendance Mismatch ---
    @classmethod
    def evaluate_attendance_mismatch(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
    ) -> Optional[Alert]:
        """
        Rule 1: During a batch's active window, if the median smoothed person count
        is below threshold (default 70%) of claimed attendance for N consecutive windows,
        raise an alert with severity scaled by the gap.
        Auto-resolves when attendance recovers.
        """
        active_batches = cls.get_active_batches(db, centre_id, event_time, zone=zone)
        if not active_batches:
            # Rule 4: Skip outside batch windows
            return None

        for batch in active_batches:
            # Look up claimed attendance for this batch on event date
            att_rec = db.query(AttendanceRecord).filter(
                AttendanceRecord.centre_id == centre_id,
                AttendanceRecord.batch_id == batch.id,
                AttendanceRecord.date == event_time.date(),
            ).first()

            if not att_rec or att_rec.claimed_count <= 0:
                continue

            claimed = att_rec.claimed_count
            n_windows = settings.attendance_consecutive_windows

            # Fetch the last N events for this camera and zone
            recent_events = db.query(DetectionEvent).filter(
                DetectionEvent.camera_id == camera.id,
                DetectionEvent.zone == zone,
                DetectionEvent.timestamp <= event_time,
            ).order_by(DetectionEvent.timestamp.desc()).limit(n_windows).all()

            if len(recent_events) < n_windows:
                # Need at least N samples to confirm persistent deficit
                continue

            smoothed_counts = [e.person_count_smoothed for e in recent_events]
            median_observed = float(np.median(smoothed_counts))

            ratio = median_observed / float(claimed)
            threshold = settings.attendance_threshold_ratio

            alert_type = "ATTENDANCE_MISMATCH"
            open_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == alert_type,
                Alert.status == "open",
            ).first()

            if ratio < threshold:
                # Persistent deficit detected: scale severity by gap
                gap_ratio = 1.0 - ratio
                if gap_ratio >= 0.70:
                    severity = "CRITICAL"
                elif gap_ratio >= 0.40:
                    severity = "HIGH"
                else:
                    severity = "MEDIUM"

                msg = (
                    f"Attendance shortfall in zone '{zone}' during batch '{batch.name}': "
                    f"median observed {median_observed:.1f} vs claimed {claimed} "
                    f"({ratio * 100:.1f}% attendance over last {n_windows} samples)."
                )

                if open_alert:
                    # Update severity/message if gap worsened
                    open_alert.severity = severity
                    open_alert.message = msg
                    db.commit()
                    return open_alert

                new_alert = Alert(
                    centre_id=centre_id,
                    camera_id=camera.id,
                    zone=zone,
                    type=alert_type,
                    severity=severity,
                    message=msg,
                    status="open",
                )
                db.add(new_alert)
                db.commit()
                db.refresh(new_alert)
                return new_alert

            else:
                # Condition cleared: Auto-resolve any existing open alert
                if open_alert:
                    open_alert.status = "auto_resolved"
                    open_alert.review_notes = (
                        f"Auto-resolved: Observed attendance recovered to {median_observed:.1f} "
                        f"(threshold {threshold*100:.0f}% of claimed {claimed})."
                    )
                    open_alert.reviewed_at = utcnow()
                    db.commit()

        return None

    # --- Rule 2: Infrastructure Gap & Surplus ---
    @classmethod
    def evaluate_infrastructure_discrepancies(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
        infra_items: List[Dict[str, Any]],
    ) -> List[Alert]:
        """
        Rule 2: If detected count is below expected for an item for M consecutive samples,
        flag missing equipment. Extra items flagged as informational surplus.
        Auto-resolves when equipment count returns to expected.
        """
        alerts_raised: List[Alert] = []
        m_samples = settings.infrastructure_consecutive_samples

        for item_data in infra_items:
            item_name = item_data.get("item")
            expected = item_data.get("expected", 0)
            detected = item_data.get("detected", 0)
            if not item_name or expected <= 0:
                continue

            open_gap_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.item == item_name,
                Alert.type == "INFRASTRUCTURE_GAP",
                Alert.status == "open",
            ).first()

            if detected < expected:
                # Check previous M-1 events to ensure deficit is sustained
                recent_events = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(m_samples).all()

                if len(recent_events) >= m_samples:
                    # Verify item was deficient across all M samples
                    all_deficient = True
                    for ev in recent_events:
                        ev_item = next((i for i in ev.infrastructure if i.get("item") == item_name), None)
                        if not ev_item or ev_item.get("detected", 0) >= ev_item.get("expected", 1):
                            all_deficient = False
                            break

                    if all_deficient:
                        deficit = expected - detected
                        severity = "CRITICAL" if deficit >= (expected * 0.5) else "HIGH"
                        msg = (
                            f"Sanctioned infrastructure deficit in zone '{zone}': "
                            f"{detected} of {expected} expected '{item_name}' detected "
                            f"({deficit} missing for {m_samples} consecutive samples)."
                        )

                        if not open_gap_alert:
                            alert = Alert(
                                centre_id=centre_id,
                                camera_id=camera.id,
                                zone=zone,
                                item=item_name,
                                type="INFRASTRUCTURE_GAP",
                                severity=severity,
                                message=msg,
                                status="open",
                            )
                            db.add(alert)
                            db.commit()
                            db.refresh(alert)
                            alerts_raised.append(alert)
            else:
                # Item is compliant: auto-resolve open gap alert
                if open_gap_alert:
                    open_gap_alert.status = "auto_resolved"
                    open_gap_alert.review_notes = (
                        f"Auto-resolved: Detected count for '{item_name}' restored to {detected} (expected {expected})."
                    )
                    open_gap_alert.reviewed_at = utcnow()
                    db.commit()

            # Surplus check: flag extra items as INFO only
            if detected > expected:
                open_surplus_alert = db.query(Alert).filter(
                    Alert.centre_id == centre_id,
                    Alert.camera_id == camera.id,
                    Alert.zone == zone,
                    Alert.item == item_name,
                    Alert.type == "INFRASTRUCTURE_SURPLUS",
                    Alert.status == "open",
                ).first()

                if not open_surplus_alert:
                    surplus_alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        item=item_name,
                        type="INFRASTRUCTURE_SURPLUS",
                        severity="INFO",
                        message=(
                            f"Surplus equipment in zone '{zone}': "
                            f"{detected} '{item_name}' detected vs {expected} sanctioned."
                        ),
                        status="open",
                    )
                    db.add(surplus_alert)
                    db.commit()
                    db.refresh(surplus_alert)
                    alerts_raised.append(surplus_alert)

        return alerts_raised

    # --- Rule 3: Camera Tamper or Offline ---
    @classmethod
    def evaluate_camera_tamper(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
        current_event: DetectionEvent,
    ) -> Optional[Alert]:
        """
        Rule 3 (Tamper): A sudden drop in detected objects across all classes
        (persons + infrastructure) while camera is transmitting and a batch is active.
        """
        active_batches = cls.get_active_batches(db, centre_id, event_time, zone=zone)
        if not active_batches:
            return None

        # Calculate current total detections
        curr_infra_total = sum(i.get("detected", 0) for i in current_event.infrastructure)
        curr_total = current_event.person_count_raw + curr_infra_total

        # Compare with recent history before this event
        prev_events = db.query(DetectionEvent).filter(
            DetectionEvent.camera_id == camera.id,
            DetectionEvent.zone == zone,
            DetectionEvent.timestamp < current_event.timestamp,
        ).order_by(DetectionEvent.timestamp.desc()).limit(5).all()

        if len(prev_events) >= 3:
            prev_totals = [
                e.person_count_raw + sum(i.get("detected", 0) for i in e.infrastructure)
                for e in prev_events
            ]
            avg_prev = float(np.mean(prev_totals))

            # Trigger if baseline had >= 4 objects and drops by >= threshold (default 80%)
            if avg_prev >= 4 and (curr_total <= avg_prev * (1.0 - settings.camera_tamper_drop_ratio)):
                open_tamper = db.query(Alert).filter(
                    Alert.centre_id == centre_id,
                    Alert.camera_id == camera.id,
                    Alert.type == "CAMERA_TAMPER",
                    Alert.status == "open",
                ).first()

                if not open_tamper:
                    camera.status = "tampered"
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="CAMERA_TAMPER",
                        severity="CRITICAL",
                        message=(
                            f"Possible camera occlusion or tampering detected on camera '{camera.id}' ({zone}): "
                            f"Total detected entities dropped suddenly from average {avg_prev:.1f} to {curr_total}."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    return alert

        return None

    @classmethod
    def check_camera_offline(cls, db: Session, camera: Camera, current_time: datetime) -> Optional[Alert]:
        """
        Rule 3 (Offline): No events received for X minutes during an active batch window.
        """
        active_batches = cls.get_active_batches(db, camera.centre_id, current_time)
        if not active_batches:
            return None

        timeout_delta = timedelta(minutes=settings.camera_offline_timeout_minutes)
        last_seen = camera.last_seen_at

        is_offline = False
        if last_seen is None:
            is_offline = True
        else:
            # Handle tz-aware vs naive comparisons safely
            if last_seen.tzinfo is None and current_time.tzinfo is not None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            elif last_seen.tzinfo is not None and current_time.tzinfo is None:
                current_time = current_time.replace(tzinfo=timezone.utc)

            if current_time - last_seen > timeout_delta:
                is_offline = True

        open_alert = db.query(Alert).filter(
            Alert.centre_id == camera.centre_id,
            Alert.camera_id == camera.id,
            Alert.type == "CAMERA_OFFLINE",
            Alert.status == "open",
        ).first()

        if is_offline:
            camera.status = "offline"
            if not open_alert:
                alert = Alert(
                    centre_id=camera.centre_id,
                    camera_id=camera.id,
                    type="CAMERA_OFFLINE",
                    severity="HIGH",
                    message=(
                        f"Camera '{camera.id}' is offline during scheduled batch window: "
                        f"no events or heartbeat received since {last_seen} "
                        f"(exceeds {settings.camera_offline_timeout_minutes}m timeout)."
                    ),
                    status="open",
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)
                return alert
        else:
            # Camera is active: auto-resolve offline alert if any
            if open_alert:
                open_alert.status = "auto_resolved"
                open_alert.review_notes = "Auto-resolved: Camera feed restored."
                open_alert.reviewed_at = utcnow()
                camera.status = "online"
                db.commit()

        return None

    # --- Rule 6: Weighted Compliance Score (0 - 100) ---
    @classmethod
    def calculate_compliance_score(
        cls,
        db: Session,
        centre_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Rule 6: Compute compliance score (0-100) weighted from:
        - Attendance match rate (w_att)
        - Infrastructure availability rate (w_infra)
        - Camera uptime rate (w_cam)
        """
        centre = db.query(Centre).filter(Centre.id == centre_id).first()
        if not centre:
            raise ValueError(f"Centre '{centre_id}' not found.")

        # 1. Attendance Match Rate
        # Compare claimed vs observed across batches
        att_records_query = db.query(AttendanceRecord).filter(AttendanceRecord.centre_id == centre_id)
        if start_date:
            att_records_query = att_records_query.filter(AttendanceRecord.date >= start_date.date())
        if end_date:
            att_records_query = att_records_query.filter(AttendanceRecord.date <= end_date.date())
        att_records = att_records_query.all()

        attendance_rates: List[float] = []
        for rec in att_records:
            if rec.claimed_count <= 0:
                continue
            # Find median detected attendance during that date and batch
            batch = db.query(Batch).filter(Batch.id == rec.batch_id).first()
            if batch:
                events = db.query(DetectionEvent).join(Camera).filter(
                    Camera.centre_id == centre_id,
                    func.date(DetectionEvent.timestamp) == rec.date,
                ).all()
                if events:
                    # Filter events in batch window
                    window_events = [e for e in events if cls.is_time_in_batch_window(batch, e.timestamp)]
                    if window_events:
                        med_obs = float(np.median([e.person_count_smoothed for e in window_events]))
                        match_ratio = min(1.0, med_obs / float(rec.claimed_count))
                        attendance_rates.append(match_ratio)

        att_rate = float(np.mean(attendance_rates)) if attendance_rates else 1.0

        # 2. Infrastructure Availability Rate
        # Ratio of sanctioned inventory items meeting or exceeding expected count in recent events
        sanctioned = db.query(SanctionedInventory).filter(SanctionedInventory.centre_id == centre_id).all()
        infra_rates: List[float] = []
        if sanctioned:
            for item in sanctioned:
                latest_event = (
                    db.query(DetectionEvent)
                    .join(Camera)
                    .filter(Camera.centre_id == centre_id, DetectionEvent.zone == item.zone)
                    .order_by(DetectionEvent.timestamp.desc())
                    .first()
                )
                if latest_event and latest_event.infrastructure:
                    entry = next((i for i in latest_event.infrastructure if i.get("item") == item.item), None)
                    if entry:
                        detected = entry.get("detected", 0)
                        infra_rates.append(min(1.0, detected / float(item.expected_count)))
                    else:
                        infra_rates.append(0.0)
                else:
                    infra_rates.append(1.0)
        infra_rate = float(np.mean(infra_rates)) if infra_rates else 1.0

        # 3. Camera Uptime Rate
        cameras = db.query(Camera).filter(Camera.centre_id == centre_id).all()
        if cameras:
            online_count = sum(1 for c in cameras if c.status == "online")
            camera_rate = online_count / float(len(cameras))
        else:
            camera_rate = 1.0

        # Weighted calculation
        w_att = settings.compliance_weight_attendance
        w_inf = settings.compliance_weight_infrastructure
        w_cam = settings.compliance_weight_camera

        raw_score = (w_att * att_rate) + (w_inf * infra_rate) + (w_cam * camera_rate)
        final_score = round(max(0.0, min(100.0, raw_score * 100.0)), 1)

        # Status categorization
        if final_score >= 85.0:
            status = "COMPLIANT"
        elif final_score >= 65.0:
            status = "NEEDS_ATTENTION"
        else:
            status = "NON_COMPLIANT"

        open_alerts = db.query(Alert).filter(
            Alert.centre_id == centre_id,
            Alert.status == "open",
        ).count()

        return {
            "centre_id": centre.id,
            "centre_name": centre.name,
            "compliance_score": final_score,
            "attendance_rate": round(att_rate, 3),
            "infrastructure_availability_rate": round(infra_rate, 3),
            "camera_uptime_rate": round(camera_rate, 3),
            "open_alerts_count": open_alerts,
            "weights": {
                "attendance": w_att,
                "infrastructure": w_inf,
                "camera": w_cam,
            },
            "summary_status": status,
        }

    # --- Data Retention: Privacy Policy Cleanup ---
    @classmethod
    def cleanup_old_events(cls, db: Session, retention_days: Optional[int] = None) -> int:
        """
        Delete detection events older than retention_days (default from config).
        Enforces privacy and minimal data retention.
        """
        days = retention_days or settings.data_retention_days
        cutoff = utcnow() - timedelta(days=days)
        deleted_count = db.query(DetectionEvent).filter(DetectionEvent.timestamp < cutoff).delete()
        db.commit()
        return deleted_count
