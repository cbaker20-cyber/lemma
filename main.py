from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.database import create_db_and_tables, get_report as db_get_report, save_report
from app.demos import DEMOS, RECHECK_DEMOS, list_demos
from app.models import RecheckRequest, VerificationReportResponse, VerificationRequest
from app.verifier import verify_claim

app = FastAPI(
    title="Lemma API",
    description="A verification and repair loop for automation claims.",
    version="0.1.0",
)

# Create the SQLite table at import time so that the tests and local scripts work too.
# FastAPI startup also works when running uvicorn, but might be more friendly?


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lemma"}


@app.get("/demos")
def demos() -> list[dict[str, str]]:
    return list_demos()


@app.get("/demos/{demo_key}")
def get_demo(demo_key: str) -> VerificationRequest:
    if demo_key not in DEMOS:
        raise HTTPException(status_code=404, detail="Demo not found")
    return DEMOS[demo_key]


@app.post("/verify", response_model=VerificationReportResponse)
def verify(request: VerificationRequest) -> VerificationReportResponse:
    report = verify_claim(request.goal, request.claim, request.evidence)
    return save_report(report)


@app.post("/verify/demo/{demo_key}", response_model=VerificationReportResponse)
def verify_demo(demo_key: str) -> VerificationReportResponse:
    if demo_key not in DEMOS:
        raise HTTPException(status_code=404, detail="Demo not found")
    request = DEMOS[demo_key]
    report = verify_claim(request.goal, request.claim, request.evidence)
    return save_report(report)


@app.get("/reports/{report_id}", response_model=VerificationReportResponse)
def get_report(report_id: str) -> VerificationReportResponse:
    report = db_get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.post("/recheck/{report_id}", response_model=VerificationReportResponse)
def recheck(report_id: str, request: RecheckRequest) -> VerificationReportResponse:
    old_report = db_get_report(report_id)
    if old_report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    combined_evidence = old_report.evidence + "\n\nNEW EVIDENCE:\n" + request.new_evidence
    updated_report = verify_claim(
        old_report.goal,
        old_report.claim,
        combined_evidence,
        report_id=old_report.id,
        created_at=old_report.created_at,
    )
    return save_report(updated_report)


@app.post("/recheck/demo/{report_id}/{demo_key}", response_model=VerificationReportResponse)
def recheck_demo(report_id: str, demo_key: str) -> VerificationReportResponse:
    if demo_key not in RECHECK_DEMOS:
        raise HTTPException(status_code=404, detail="Demo recheck evidence not found")
    return recheck(report_id, RecheckRequest(new_evidence=RECHECK_DEMOS[demo_key]))
