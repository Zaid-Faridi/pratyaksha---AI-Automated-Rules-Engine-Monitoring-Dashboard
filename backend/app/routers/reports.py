"""
Reports Export Router for Pratyaksha.
Provides Ministry-ready CSV and PDF downloads with date filtering and DPDP 2023 compliance notices.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.database import get_db
from app.reports import compile_report_data, generate_csv_report, generate_pdf_report

router = APIRouter(prefix="/reports", tags=["Ministry Reports"])


@router.get("/csv")
def export_csv_report(
    centre_id: Optional[str] = Query(None, description="Optional filter by specific Centre ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Download a Ministry-ready CSV audit report.
    """
    data = compile_report_data(db, centre_id=centre_id, start_date=start_date, end_date=end_date)
    csv_content = generate_csv_report(data)

    filename = f"pratyaksha_report_{centre_id or 'all_centres'}_{date.today().isoformat()}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/pdf")
def export_pdf_report(
    centre_id: Optional[str] = Query(None, description="Optional filter by specific Centre ID"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Download a Ministry-ready PDF executive audit document.
    """
    data = compile_report_data(db, centre_id=centre_id, start_date=start_date, end_date=end_date)
    pdf_bytes = generate_pdf_report(data)

    filename = f"pratyaksha_summary_{centre_id or 'national'}_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
