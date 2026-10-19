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
    TradeProfile,
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

    # --- Rule 2.5: Apparent Operability Assessment ---
    @classmethod
    def evaluate_apparent_operability(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
        infra_items: List[Dict[str, Any]],
    ) -> List[Alert]:
        """
        Apparent Operability Rule: If an item shows non-operational heuristics
        for M consecutive samples, raise NON_FUNCTIONAL_EQUIPMENT alert.
        Auto-resolves when operational signals resume.
        Note: Operability is a heuristic indication, not an electrical/mechanical diagnostic.
        """
        alerts_raised: List[Alert] = []
        m_samples = settings.operability_consecutive_samples

        for item_data in infra_items:
            item_name = item_data.get("item")
            operability = item_data.get("operability", "operational")
            signals = item_data.get("signals", {})

            if not item_name:
                continue

            open_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.item == item_name,
                Alert.type == "NON_FUNCTIONAL_EQUIPMENT",
                Alert.status == "open",
            ).first()

            if operability == "non_operational":
                recent_events = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(m_samples).all()

                if len(recent_events) >= m_samples:
                    all_non_op = True
                    for ev in recent_events:
                        ev_item = next((i for i in ev.infrastructure if i.get("item") == item_name), None)
                        if not ev_item or ev_item.get("operability") != "non_operational":
                            all_non_op = False
                            break

                    if all_non_op:
                        sig_summary = ", ".join(f"{k}={v}" for k, v in signals.items()) if signals else "no activity"
                        severity = "HIGH" if item_name.lower() in ["lathe", "welding machine", "drill press", "sewing machine"] else "MEDIUM"
                        msg = (
                            f"Heuristic non-functional alert for '{item_name}' in zone '{zone}': "
                            f"Equipment flagged non-operational for {m_samples} consecutive samples "
                            f"({sig_summary}). (Note: Heuristic indication based on computer vision signals, not a diagnostic)."
                        )

                        if not open_alert:
                            new_alert = Alert(
                                centre_id=centre_id,
                                camera_id=camera.id,
                                zone=zone,
                                item=item_name,
                                type="NON_FUNCTIONAL_EQUIPMENT",
                                severity=severity,
                                message=msg,
                                status="open",
                            )
                            db.add(new_alert)
                            db.commit()
                            db.refresh(new_alert)
                            alerts_raised.append(new_alert)
            elif operability == "operational":
                if open_alert:
                    open_alert.status = "auto_resolved"
                    open_alert.review_notes = f"Auto-resolved: Operational activity detected for '{item_name}'."
                    open_alert.reviewed_at = utcnow()
                    db.commit()

        return alerts_raised

    # --- Rule 2.8: Camera Quality Gating ---
    @classmethod
    def evaluate_camera_quality(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
        current_event: DetectionEvent,
    ) -> Optional[Alert]:
        """
        Quality Gating Rule: If N consecutive frames are marked unreliable
        (e.g., severe blur, brightness issue, or occlusion), raise POOR_CAMERA_QUALITY.
        Auto-resolves when camera quality returns to reliable.
        """
        open_quality_alert = db.query(Alert).filter(
            Alert.centre_id == centre_id,
            Alert.camera_id == camera.id,
            Alert.type == "POOR_CAMERA_QUALITY",
            Alert.status == "open",
        ).first()

        if current_event.is_reliable:
            if open_quality_alert:
                open_quality_alert.status = "auto_resolved"
                open_quality_alert.review_notes = "Auto-resolved: Camera image quality restored to normal threshold."
                open_quality_alert.reviewed_at = utcnow()
                db.commit()
            return None

        # Current event is unreliable. Check previous N-1 events for persistence
        n_samples = settings.quality_consecutive_unreliable_samples
        recent_events = db.query(DetectionEvent).filter(
            DetectionEvent.camera_id == camera.id,
            DetectionEvent.timestamp <= event_time,
        ).order_by(DetectionEvent.timestamp.desc()).limit(n_samples).all()

        if len(recent_events) >= n_samples and all(not e.is_reliable for e in recent_events):
            metrics = current_event.quality_metrics or {}
            issues = metrics.get("issues", [])
            issues_str = ", ".join(issues) if issues else "metrics below threshold"

            msg = (
                f"Camera feed quality degraded on '{camera.id}' ({zone}): "
                f"{n_samples} consecutive samples unreliable ({issues_str}). "
                f"Attendance and equipment audits are gated while quality remains degraded."
            )

            if open_quality_alert:
                open_quality_alert.message = msg
                db.commit()
                return open_quality_alert

            new_alert = Alert(
                centre_id=centre_id,
                camera_id=camera.id,
                zone=zone,
                type="POOR_CAMERA_QUALITY",
                severity="HIGH",
                message=msg,
                status="open",
            )
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)
            return new_alert

        return None

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

    # --- Rule 5.5: Multi-Trade Additional Compliance Checks ---
    @classmethod
    def evaluate_trade_compliance_checks(
        cls,
        db: Session,
        centre_id: str,
        camera: Camera,
        zone: str,
        event_time: datetime,
        current_event: DetectionEvent,
    ) -> List[Alert]:
        """
        Evaluate additional compliance checks configured for the centre's trade profile:
        1. INSTRUCTOR_ABSENT: Trainer absent from demonstration dais during active batch
        2. PPE_VIOLATION: Aggregate safety gear compliance below trade threshold
        3. SAFETY_EQUIPMENT_MISSING: Fire extinguisher or first-aid box absent
        4. MANDATORY_SIGNAGE_MISSING: Government scheme signage or biometric terminal absent
        5. CAPACITY_DEFICIT: Workstations / seats insufficient for claimed batch size
        6. ZONE_IDLE_DURING_BATCH: Trainees idle with zero equipment engagement during class hours
        """
        alerts_raised: List[Alert] = []
        centre = db.query(Centre).filter(Centre.id == centre_id).first()
        if not centre:
            return alerts_raised

        tp = centre.trade_profile if centre.trade_profile else None
        if not tp and centre.trade_id:
            tp = db.query(TradeProfile).filter(TradeProfile.id == centre.trade_id).first()

        trade_checks = tp.compliance_checks if tp and tp.compliance_checks else {
            "instructor_presence": True,
            "ppe_compliance": True,
            "safety_items": True,
            "signage": True,
            "capacity": True,
            "activity_state": True,
        }
        if centre.trade_overrides and "compliance_checks" in centre.trade_overrides:
            trade_checks.update(centre.trade_overrides["compliance_checks"])

        active_batches = cls.get_active_batches(db, centre_id, event_time, zone=zone)
        metrics = current_event.compliance_metrics or {}
        trade_name = tp.name if tp else "Vocational Trade"

        # Check 1: Instructor Presence
        if trade_checks.get("instructor_presence", True):
            open_inst_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "INSTRUCTOR_ABSENT",
                Alert.status == "open",
            ).first()

            if active_batches:
                inst_present = metrics.get("instructor_present", True)
                if not inst_present:
                    k_windows = settings.instructor_consecutive_windows
                    recent = db.query(DetectionEvent).filter(
                        DetectionEvent.camera_id == camera.id,
                        DetectionEvent.zone == zone,
                        DetectionEvent.timestamp <= event_time,
                    ).order_by(DetectionEvent.timestamp.desc()).limit(k_windows).all()

                    all_absent = (
                        len(recent) >= k_windows
                        and all(not (e.compliance_metrics or {}).get("instructor_present", True) for e in recent)
                    )
                    if all_absent and not open_inst_alert:
                        b_name = active_batches[0].name
                        alert = Alert(
                            centre_id=centre_id,
                            camera_id=camera.id,
                            zone=zone,
                            type="INSTRUCTOR_ABSENT",
                            severity="HIGH",
                            message=(
                                f"Trainer/instructor absent from demonstration podium during active batch '{b_name}' "
                                f"in zone '{zone}' (sustained for {k_windows} consecutive windows)."
                            ),
                            status="open",
                        )
                        db.add(alert)
                        db.commit()
                        db.refresh(alert)
                        alerts_raised.append(alert)
                else:
                    if open_inst_alert:
                        open_inst_alert.status = "auto_resolved"
                        open_inst_alert.review_notes = "Auto-resolved: Instructor detected in demonstration zone."
                        open_inst_alert.reviewed_at = utcnow()
                        db.commit()
            else:
                if open_inst_alert:
                    open_inst_alert.status = "auto_resolved"
                    open_inst_alert.review_notes = "Auto-resolved: Batch window ended."
                    open_inst_alert.reviewed_at = utcnow()
                    db.commit()

        # Check 2: Aggregate PPE Compliance
        if trade_checks.get("ppe_compliance", True) and tp and tp.required_ppe:
            open_ppe_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "PPE_VIOLATION",
                Alert.status == "open",
            ).first()

            ppe_info = metrics.get("ppe_compliance", {})
            compliance_pct = ppe_info.get("compliance_pct", 100.0)
            is_compliant = ppe_info.get("is_compliant", True)
            trainees_count = ppe_info.get("total_trainees", current_event.person_count_raw)

            if trainees_count >= 2 and not is_compliant:
                k_windows = settings.ppe_consecutive_windows
                recent = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(k_windows).all()

                all_violating = (
                    len(recent) >= k_windows
                    and all(not (e.compliance_metrics or {}).get("ppe_compliance", {}).get("is_compliant", True) for e in recent)
                )
                if all_violating and not open_ppe_alert:
                    sev = "HIGH" if tp.id in ["welding", "electrical"] else "MEDIUM"
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="PPE_VIOLATION",
                        severity=sev,
                        message=(
                            f"Safety compliance violation in {trade_name} zone '{zone}': "
                            f"Aggregate PPE compliance is {compliance_pct}% (below mandatory 75% threshold). "
                            f"Observed {trainees_count} trainees in active trade workshop."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alerts_raised.append(alert)
            elif is_compliant or trainees_count < 2:
                if open_ppe_alert:
                    open_ppe_alert.status = "auto_resolved"
                    open_ppe_alert.review_notes = f"Auto-resolved: Aggregate PPE compliance restored to {compliance_pct}%."
                    open_ppe_alert.reviewed_at = utcnow()
                    db.commit()

        # Check 3: Safety Items Presence
        if trade_checks.get("safety_items", True):
            open_safety_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "SAFETY_EQUIPMENT_MISSING",
                Alert.status == "open",
            ).first()

            safety_info = metrics.get("safety_items", {})
            all_present = safety_info.get("all_present", True)
            missing = safety_info.get("missing_items", [])

            if not all_present and missing:
                k_samples = settings.safety_consecutive_samples
                recent = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(k_samples).all()

                all_missing = (
                    len(recent) >= k_samples
                    and all(not (e.compliance_metrics or {}).get("safety_items", {}).get("all_present", True) for e in recent)
                )
                if all_missing and not open_safety_alert:
                    missing_str = ", ".join(m.replace("_", " ").title() for m in missing)
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="SAFETY_EQUIPMENT_MISSING",
                        severity="HIGH",
                        message=(
                            f"Mandatory safety infrastructure absent in '{zone}': "
                            f"{missing_str} not detected for {k_samples} consecutive samples."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alerts_raised.append(alert)
            elif all_present:
                if open_safety_alert:
                    open_safety_alert.status = "auto_resolved"
                    open_safety_alert.review_notes = "Auto-resolved: Mandatory safety equipment detected."
                    open_safety_alert.reviewed_at = utcnow()
                    db.commit()

        # Check 4: Mandatory Signage & Attendance Device
        if trade_checks.get("signage", True):
            open_sign_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "MANDATORY_SIGNAGE_MISSING",
                Alert.status == "open",
            ).first()

            sign_info = metrics.get("signage_and_devices", {})
            all_visible = sign_info.get("all_visible", True)
            missing_signs = sign_info.get("missing_signage", [])

            if not all_visible and missing_signs:
                k_samples = settings.signage_consecutive_samples
                recent = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(k_samples).all()

                all_miss = (
                    len(recent) >= k_samples
                    and all(not (e.compliance_metrics or {}).get("signage_and_devices", {}).get("all_visible", True) for e in recent)
                )
                if all_miss and not open_sign_alert:
                    missing_str = ", ".join(s.replace("_", " ").title() for s in missing_signs)
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="MANDATORY_SIGNAGE_MISSING",
                        severity="MEDIUM",
                        message=(
                            f"Scheme signage / terminal missing in '{zone}': "
                            f"{missing_str} not visible for {k_samples} consecutive samples."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alerts_raised.append(alert)
            elif all_visible:
                if open_sign_alert:
                    open_sign_alert.status = "auto_resolved"
                    open_sign_alert.review_notes = "Auto-resolved: Mandatory signage/biometric device verified."
                    open_sign_alert.reviewed_at = utcnow()
                    db.commit()

        # Check 5: Workstation / Seating Capacity vs Batch Size
        if trade_checks.get("capacity", True) and active_batches:
            open_cap_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "CAPACITY_DEFICIT",
                Alert.status == "open",
            ).first()

            cap_info = metrics.get("capacity_check", {})
            is_adequate = cap_info.get("is_adequate", True)
            deficit = cap_info.get("station_deficit", 0)

            if not is_adequate and deficit > 0:
                if not open_cap_alert:
                    avail = cap_info.get("available_workstations", 0)
                    batch_sz = cap_info.get("batch_size", 0)
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="CAPACITY_DEFICIT",
                        severity="MEDIUM",
                        message=(
                            f"Workstation capacity deficit in '{zone}': {avail} operational stations "
                            f"cannot accommodate scheduled batch size of {batch_sz} (deficit: {deficit} stations)."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alerts_raised.append(alert)
            elif is_adequate:
                if open_cap_alert:
                    open_cap_alert.status = "auto_resolved"
                    open_cap_alert.review_notes = "Auto-resolved: Workstation capacity adequate for active batch."
                    open_cap_alert.reviewed_at = utcnow()
                    db.commit()

        # Check 6: Zone Activity State (Active vs Idle)
        if trade_checks.get("activity_state", True) and active_batches:
            open_idle_alert = db.query(Alert).filter(
                Alert.centre_id == centre_id,
                Alert.camera_id == camera.id,
                Alert.zone == zone,
                Alert.type == "ZONE_IDLE_DURING_BATCH",
                Alert.status == "open",
            ).first()

            act_state = metrics.get("activity_state", "active")
            if act_state == "idle":
                k_samples = settings.activity_idle_consecutive_samples
                recent = db.query(DetectionEvent).filter(
                    DetectionEvent.camera_id == camera.id,
                    DetectionEvent.zone == zone,
                    DetectionEvent.timestamp <= event_time,
                ).order_by(DetectionEvent.timestamp.desc()).limit(k_samples).all()

                all_idle = (
                    len(recent) >= k_samples
                    and all((e.compliance_metrics or {}).get("activity_state") == "idle" for e in recent)
                )
                if all_idle and not open_idle_alert:
                    b_name = active_batches[0].name
                    trainees = current_event.person_count_raw
                    alert = Alert(
                        centre_id=centre_id,
                        camera_id=camera.id,
                        zone=zone,
                        type="ZONE_IDLE_DURING_BATCH",
                        severity="MEDIUM",
                        message=(
                            f"Unscheduled idle session detected during batch '{b_name}' in zone '{zone}': "
                            f"{trainees} trainees present with zero machine engagement or instructional motion for {k_samples} windows."
                        ),
                        status="open",
                    )
                    db.add(alert)
                    db.commit()
                    db.refresh(alert)
                    alerts_raised.append(alert)
            elif act_state in ["active", "empty"]:
                if open_idle_alert:
                    open_idle_alert.status = "auto_resolved"
                    open_idle_alert.review_notes = f"Auto-resolved: Zone activity state changed to '{act_state}'."
                    open_idle_alert.reviewed_at = utcnow()
                    db.commit()

        return alerts_raised

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

        # 4. Compliance Checks Rate
        compliance_alert_types = [
            "INSTRUCTOR_ABSENT",
            "PPE_VIOLATION",
            "SAFETY_EQUIPMENT_MISSING",
            "MANDATORY_SIGNAGE_MISSING",
            "CAPACITY_DEFICIT",
            "ZONE_IDLE_DURING_BATCH",
        ]
        open_compliance_alerts = db.query(Alert).filter(
            Alert.centre_id == centre_id,
            Alert.type.in_(compliance_alert_types),
            Alert.status == "open",
        ).count()
        comp_rate = max(0.0, 1.0 - (0.20 * open_compliance_alerts))

        # Weighted calculation
        w_att = settings.compliance_weight_attendance
        w_inf = settings.compliance_weight_infrastructure
        w_cam = settings.compliance_weight_camera

        base_score = (w_att * att_rate) + (w_inf * infra_rate) + (w_cam * camera_rate)
        # Apply compliance factor (deducts mildly if safety/instructor violations exist)
        raw_score = base_score * (0.90 + 0.10 * comp_rate)
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
            "compliance_checks_rate": round(comp_rate, 3),
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
