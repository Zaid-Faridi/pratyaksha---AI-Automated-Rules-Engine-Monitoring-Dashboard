"""
Ministry-ready Report Generation Engine for Pratyaksha.
Generates comprehensive CSV and PDF reports for national and per-centre audits.
Includes mandatory privacy statement: Aggregate counts only, zero PII or facial biometrics.
"""

import csv
import io
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Alert, AttendanceRecord, Batch, Camera, Centre, DetectionEvent, SanctionedInventory
from app.rules_engine import RulesEngine

# ReportLab imports for PDF generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DPDP_DISCLAIMER = (
    "DATA PRIVACY COMPLIANCE NOTICE (DPDP Act 2023 / MSDE Guidelines): "
    "This report is compiled strictly from aggregated object detections and anonymous headcount statistics. "
    "No facial recognition, biometric data, or personally identifiable information (PII) is captured, processed, or stored."
)


def compile_report_data(
    db: Session,
    centre_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Compile audit data across centres, attendance, equipment, and alerts."""
    centres_query = db.query(Centre)
    if centre_id:
        centres_query = centres_query.filter(Centre.id == centre_id)
    centres = centres_query.all()

    start_dt = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_dt = datetime.combine(end_date, datetime.max.time()) if end_date else None

    centre_summaries = []
    total_claimed = 0
    total_detected = 0
    total_alerts_open = 0
    total_alerts_verified = 0
    total_alerts_dismissed = 0

    for c in centres:
        breakdown = RulesEngine.calculate_compliance_score(db, c.id, start_date=start_dt, end_date=end_dt)

        # Claimed attendance
        att_q = db.query(AttendanceRecord).filter(AttendanceRecord.centre_id == c.id)
        if start_date:
            att_q = att_q.filter(AttendanceRecord.date >= start_date)
        if end_date:
            att_q = att_q.filter(AttendanceRecord.date <= end_date)
        claimed_sum = att_q.with_entities(func.coalesce(func.sum(AttendanceRecord.claimed_count), 0)).scalar()

        # Detected attendance
        cam_ids = [cam.id for cam in c.cameras]
        ev_q = db.query(DetectionEvent).filter(DetectionEvent.camera_id.in_(cam_ids))
        if start_dt:
            ev_q = ev_q.filter(DetectionEvent.timestamp >= start_dt)
        if end_dt:
            ev_q = ev_q.filter(DetectionEvent.timestamp <= end_dt)
        avg_detected = ev_q.with_entities(func.coalesce(func.avg(DetectionEvent.person_count_smoothed), 0)).scalar()

        # Alert counts
        al_q = db.query(Alert).filter(Alert.centre_id == c.id)
        if start_dt:
            al_q = al_q.filter(Alert.created_at >= start_dt)
        if end_dt:
            al_q = al_q.filter(Alert.created_at <= end_dt)

        open_count = al_q.filter(Alert.status == "open").count()
        verified_count = al_q.filter(Alert.status == "verified").count()
        dismissed_count = al_q.filter(Alert.status == "dismissed").count()

        # Equipment operability heuristic summary
        inventories = db.query(SanctionedInventory).filter(SanctionedInventory.centre_id == c.id).all()
        equipment_status_list = []
        for inv in inventories:
            equipment_status_list.append(f"{inv.item}: {inv.expected_count} expected")

        total_claimed += claimed_sum
        total_detected += int(round(avg_detected))
        total_alerts_open += open_count
        total_alerts_verified += verified_count
        total_alerts_dismissed += dismissed_count

        centre_summaries.append({
            "centre_id": c.id,
            "name": c.name,
            "state": c.state,
            "district": c.district,
            "compliance_score": breakdown["compliance_score"],
            "summary_status": breakdown["summary_status"],
            "attendance_rate": breakdown["attendance_rate"],
            "claimed_attendance": claimed_sum,
            "detected_attendance": int(round(avg_detected)),
            "open_alerts": open_count,
            "verified_alerts": verified_count,
            "dismissed_alerts": dismissed_count,
            "equipment_summary": "; ".join(equipment_status_list) if equipment_status_list else "None registered",
        })

    return {
        "is_single_centre": bool(centre_id),
        "selected_centre_id": centre_id,
        "start_date": str(start_date) if start_date else "All Time",
        "end_date": str(end_date) if end_date else "Present",
        "centres": centre_summaries,
        "totals": {
            "centres_count": len(centres),
            "claimed_attendance": total_claimed,
            "detected_attendance": total_detected,
            "open_alerts": total_alerts_open,
            "verified_alerts": total_alerts_verified,
            "dismissed_alerts": total_alerts_dismissed,
            "avg_compliance": round(sum(cs["compliance_score"] for cs in centre_summaries) / max(len(centre_summaries), 1), 1),
        },
    }


def generate_csv_report(data: Dict[str, Any]) -> str:
    """Export audit metrics as CSV formatted text."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header & DPDP Notice
    writer.writerow(["# PRATYAKSHA - AI VIDEO ANALYTICS COMPLIANCE REPORT"])
    writer.writerow([f"# Generated On: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    writer.writerow([f"# Period: {data['start_date']} to {data['end_date']}"])
    writer.writerow([f"# {DPDP_DISCLAIMER}"])
    writer.writerow([])

    # Overview Totals
    writer.writerow(["METRIC", "VALUE"])
    writer.writerow(["Total Centres Audited", data["totals"]["centres_count"]])
    writer.writerow(["Average Compliance Score (%)", f"{data['totals']['avg_compliance']}%"])
    writer.writerow(["Total Claimed Attendance", data["totals"]["claimed_attendance"]])
    writer.writerow(["Total Detected Headcount", data["totals"]["detected_attendance"]])
    writer.writerow(["Total Open Alerts", data["totals"]["open_alerts"]])
    writer.writerow(["Total Verified Alerts", data["totals"]["verified_alerts"]])
    writer.writerow(["Total Dismissed Alerts", data["totals"]["dismissed_alerts"]])
    writer.writerow([])

    # Table of Centres
    writer.writerow([
        "Centre ID",
        "Centre Name",
        "State",
        "District",
        "Compliance Score (%)",
        "Compliance Status",
        "Claimed Attendance",
        "Detected Attendance",
        "Open Alerts",
        "Verified Alerts",
        "Dismissed Alerts",
        "Sanctioned Equipment",
    ])

    for c in data["centres"]:
        writer.writerow([
            c["centre_id"],
            c["name"],
            c["state"],
            c["district"],
            f"{c['compliance_score']}%",
            c["summary_status"],
            c["claimed_attendance"],
            c["detected_attendance"],
            c["open_alerts"],
            c["verified_alerts"],
            c["dismissed_alerts"],
            c["equipment_summary"],
        ])

    return output.getvalue()


def generate_pdf_report(data: Dict[str, Any]) -> bytes:
    """Generate a high-polish, ministry-ready PDF document using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "GovTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "GovSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )
    disclaimer_style = ParagraphStyle(
        "GovDisclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("PRATYAKSHA (प्रत्यक्ष) — MSDE SKILLING COMPLIANCE AUDIT", title_style))
    elements.append(Paragraph(
        f"Official Ministry Summary Report &bull; Period: <b>{data['start_date']}</b> to <b>{data['end_date']}</b> &bull; "
        f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
        subtitle_style,
    ))

    # DPDP Privacy Safeguard Box
    disclaimer_box = Table(
        [[Paragraph(DPDP_DISCLAIMER, disclaimer_style)]],
        colWidths=[540],
    )
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(disclaimer_box)
    elements.append(Spacer(1, 14))

    # Executive Summary Card
    t = data["totals"]
    summary_data = [
        [
            Paragraph("<b>Total Centres</b>", cell_style),
            Paragraph(str(t["centres_count"]), cell_bold),
            Paragraph("<b>Average Compliance</b>", cell_style),
            Paragraph(f"{t['avg_compliance']}%", cell_bold),
        ],
        [
            Paragraph("<b>Total Claimed Attendance</b>", cell_style),
            Paragraph(str(t["claimed_attendance"]), cell_bold),
            Paragraph("<b>Total Detected Count</b>", cell_style),
            Paragraph(str(t["detected_attendance"]), cell_bold),
        ],
        [
            Paragraph("<b>Open Alerts</b>", cell_style),
            Paragraph(str(t["open_alerts"]), cell_bold),
            Paragraph("<b>Verified / Dismissed</b>", cell_style),
            Paragraph(f"{t['verified_alerts']} / {t['dismissed_alerts']}", cell_bold),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[150, 120, 150, 120])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#0284c7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # Centre Details Breakdown Table
    elements.append(Paragraph("<b>Centre Performance & Infrastructure Compliance Breakdown</b>", styles["Heading3"]))
    elements.append(Spacer(1, 4))

    headers = [
        Paragraph("<b>Centre & Location</b>", cell_bold),
        Paragraph("<b>Score</b>", cell_bold),
        Paragraph("<b>Status</b>", cell_bold),
        Paragraph("<b>Claimed vs Det.</b>", cell_bold),
        Paragraph("<b>Alerts (O/V/D)</b>", cell_bold),
        Paragraph("<b>Sanctioned Equipment</b>", cell_bold),
    ]
    table_rows = [headers]

    for c in data["centres"]:
        table_rows.append([
            Paragraph(f"<b>{c['name']}</b><br/><font color='#64748b'>{c['district']}, {c['state']}</font>", cell_style),
            Paragraph(f"<b>{c['compliance_score']}%</b>", cell_style),
            Paragraph(c["summary_status"], cell_style),
            Paragraph(f"{c['claimed_attendance']} / {c['detected_attendance']}", cell_style),
            Paragraph(f"{c['open_alerts']} / {c['verified_alerts']} / {c['dismissed_alerts']}", cell_style),
            Paragraph(c["equipment_summary"][:50] + ("..." if len(c["equipment_summary"]) > 50 else ""), cell_style),
        ])

    detail_table = Table(table_rows, colWidths=[140, 50, 80, 80, 80, 110])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 18))

    # Explanatory Notes & Legal Heuristic Notice
    notes = (
        "<b>Notice on Equipment Operability:</b> Equipment operability is evaluated via non-invasive computer vision heuristics "
        "(e.g., active screen luminescence, illuminated power indicators, tool interaction, and unobstructed workspaces). "
        "These are heuristic compliance indicators and do not constitute an electrical or diagnostic engineering certification."
    )
    elements.append(Paragraph(notes, disclaimer_style))

    doc.build(elements)
    return buffer.getvalue()
