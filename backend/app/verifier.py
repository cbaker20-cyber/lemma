from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.models import LemmaCheck, LemmaStatus, Risk, Severity, Verdict, VerificationReportResponse

EMAIL_NAMES = ["JacksonE", "CopelandB", "QuinnL", "WolfgangAM", "KennyG"]


def verify_claim(goal: str, claim: str, evidence: str, report_id: str | None = None, created_at: datetime | None = None) -> VerificationReportResponse:
    """This is the function for the main verification.

    This is deterministic and readable on purpose to make it work for the MVP.
    Further into development, an LLM could generate better, more in-depth lemmas, but this should always work.
    """

    text = f"{goal}\n{claim}\n{evidence}".lower()

    if "email" in text or "reminder" in text or any(name.lower() in text for name in EMAIL_NAMES):
        return _email_report(goal, claim, evidence, report_id, created_at)
    if "file" in text or "drive" in text or "folder" in text:
        return _file_sorting_report(goal, claim, evidence, report_id, created_at)
    if "login" in text or "backend" in text or "test" in text:
        return _coding_report(goal, claim, evidence, report_id, created_at)
    if "refund" in text or "confirmation" in text:
        return _refund_report(goal, claim, evidence, report_id, created_at)
    return _generic_report(goal, claim, evidence, report_id, created_at)


def _new_report(
    goal: str,
    claim: str,
    evidence: str,
    lemmas: list[LemmaCheck],
    missing_proof: list[str],
    risks: list[Risk],
    fix_instruction: str,
    report_id: str | None,
    created_at: datetime | None,
) -> VerificationReportResponse:
    now = datetime.now(timezone.utc)
    verdict = _score_verdict(lemmas)
    confidence = _confidence(lemmas, verdict)
    summary = _summary(verdict, lemmas)

    return VerificationReportResponse(
        id=report_id or f"report_{uuid.uuid4().hex[:10]}",
        goal=goal,
        claim=claim,
        evidence=evidence,
        verdict=verdict,
        confidence=confidence,
        summary=summary,
        lemmas=lemmas,
        missing_proof=missing_proof,
        risks=risks,
        fix_instruction=fix_instruction,
        created_at=created_at or now,
        updated_at=now,
    )


def _email_report(goal: str, claim: str, evidence: str, report_id: str | None, created_at: datetime | None) -> VerificationReportResponse:
    lower = evidence.lower()
    lemmas: list[LemmaCheck] = []
    missing: list[str] = []

    for name in EMAIL_NAMES:
        if _name_has_sent_evidence(name, lower):
            lemmas.append(LemmaCheck(claim=f"Reminder email sent to {name}", status=LemmaStatus.PASSED, evidence=f"Evidence mentions {name} with send proof."))
        else:
            missing_msg = f"Timestamped send proof for {name}"
            lemmas.append(LemmaCheck(claim=f"Reminder email sent to {name}", status=LemmaStatus.FAILED, evidence="No send proof found.", missing_proof=missing_msg))
            missing.append(missing_msg)

    followup_names = [name for name in EMAIL_NAMES if name.lower() in lower and "follow-up" in lower or name.lower() in lower and "follow up" in lower]
    followup_all = ("follow up reminders created for JacksonE, CopelandB, QuinnL, WolfgangAM, and KennyG" in lower) or ("follow up reminders created for alex, priya, sam, maya, and jordan" in lower)
    if followup_all:
        lemmas.append(LemmaCheck(claim="Follow up reminders exist for all recipients", status=LemmaStatus.PASSED, evidence="Evidence says follow-up reminders were created for all five recipients."))
    elif "follow-up" in lower or "follow up" in lower:
        lemmas.append(LemmaCheck(claim="Follow up reminders exist for all recipients", status=LemmaStatus.PARTIAL, evidence="Some follow-up evidence exists, but coverage is incomplete.", missing_proof="Follow-up reminder proof for every recipient or clear non-reply rule"))
        missing.append("Complete follow up reminder proof for every recipient")
    else:
        lemmas.append(LemmaCheck(claim="Follow up reminders exist for all recipients", status=LemmaStatus.FAILED, evidence="No follow-up reminder proof found.", missing_proof="Follow-up reminders or follow-up rule"))
        missing.append("Follow up reminders or follow up rule")

    risks = []
    failed_count = sum(1 for lemma in lemmas if lemma.status == LemmaStatus.FAILED)
    if failed_count:
        risks.append(Risk(label="Gap in coverage", severity=Severity.HIGH, description="At least one intended recipient is not verified."))
    if any(lemma.status == LemmaStatus.PARTIAL for lemma in lemmas):
        risks.append(Risk(label="Incomplete follow-up loop", severity=Severity.MEDIUM, description="The automation may not recover if people do not reply."))

    missing_people = [name for name in EMAIL_NAMES if not _name_has_sent_evidence(name, lower)]
    if missing_people:
        fix = f"Rerun the reminder workflow for {', '.join(missing_people)} only. Create follow-up reminders for all recipients who do not reply. Return timestamped send logs and follow-up proof before marking the automation complete."
    elif any(lemma.status != LemmaStatus.PASSED for lemma in lemmas):
        fix = "Create some follow up reminders for every recipient/provide proof of an automatic non-reply follow up rule. Return the calendar or log evidence and chrck it again."
    else:
        fix = "No fix is necessary, as the reminder workflow is proven."

    return _new_report(goal, claim, evidence, lemmas, missing, risks, fix, report_id, created_at)


def _name_has_sent_evidence(name: str, lower_evidence: str) -> bool:
    name_l = name.lower()
    # Beginner-friendly heuristic: the name appears near sent/send/delivered.
    pattern = rf"{name_l}.{{0,40}}(sent|send|delivered)|(?:sent|send|delivered).{{0,40}}{name_l}"
    return re.search(pattern, lower_evidence) is not None


def _file_sorting_report(goal: str, claim: str, evidence: str, report_id: str | None, created_at: datetime | None) -> VerificationReportResponse:
    lower = evidence.lower()
    lemmas = []
    missing = []

    all_accounted = "all 20" in lower and ("accounted" in lower or "moved" in lower)
    if all_accounted:
        lemmas.append(LemmaCheck(claim="All 20 files are accounted for", status=LemmaStatus.PASSED, evidence="Evidence says all 20 files were accounted for."))
    elif "17 files" in lower:
        lemmas.append(LemmaCheck(claim="All 20 files are accounted for", status=LemmaStatus.FAILED, evidence="Only 17 files are shown as moved.", missing_proof="Status for all 20 files"))
        missing.append("Status for all 20 files")
    else:
        lemmas.append(LemmaCheck(claim="All files are accounted for", status=LemmaStatus.UNKNOWN, evidence="No complete file count proof found.", missing_proof="Moved-file count and unresolved-file count"))
        missing.append("Moved file count and unresolved-file count")

    if "duplicate report" in lower or "duplicates" in lower:
        lemmas.append(LemmaCheck(claim="Duplicates are detected have been and reported", status=LemmaStatus.PASSED, evidence="Evidence mentions duplicate handling."))
    else:
        lemmas.append(LemmaCheck(claim="Duplicates are detected have been and reported", status=LemmaStatus.UNKNOWN, evidence="No duplicate handling proof found.", missing_proof="Duplicate report"))
        missing.append("Duplicate report")

    if "rollback log" in lower and "no rollback" not in lower:
        lemmas.append(LemmaCheck(claim="Rollback/audit log exists", status=LemmaStatus.PASSED, evidence="Rollback/audit log is present."))
    else:
        lemmas.append(LemmaCheck(claim="Rollback/audit log exists", status=LemmaStatus.FAILED, evidence="No rollback/audit log found.", missing_proof="Rollback or audit log"))
        missing.append("Rollback or audit log")

    risks = [Risk(label="Data loss risk", severity=Severity.HIGH, description="Missing or unknown files can be lost without an audit trail.")] if missing else []
    fix = "Account for every file, save a duplicate report, and produce a rollback/audit log. Recheck with the updated file log."
    if not missing:
        fix = "No fix needed. File sorting is proven."
    return _new_report(goal, claim, evidence, lemmas, missing, risks, fix, report_id, created_at)


def _coding_report(goal: str, claim: str, evidence: str, report_id: str | None, created_at: datetime | None) -> VerificationReportResponse:
    lower = evidence.lower()
    checks = [
        ("Login UI exists", "loginpage" in lower or "login page" in lower or "email and password" in lower, "Login page file or screenshot"),
        ("Backend auth route exists", "api/login" in lower or "auth route added" in lower or "backend auth route added" in lower, "Backend login/auth route"),
        ("Invalid login is handled", "invalid-login test" in lower and "no invalid-login" not in lower or "invalid login" in lower and "passing" in lower, "Invalid-login behavior or test"),
        ("Successful login redirects", "redirect" in lower and "dashboard" in lower and "no redirect" not in lower, "Redirect proof after successful login"),
        ("Tests pass", "test passed" in lower or "tests passed" in lower or "npm test passed" in lower, "Passing test output"),
        ("No password is logged", "password console log removed" in lower or "no console errors" in lower, "Proof password is not logged"),
    ]

    lemmas = []
    missing = []
    for claim_text, passed, missing_text in checks:
        if passed:
            lemmas.append(LemmaCheck(claim=claim_text, status=LemmaStatus.PASSED, evidence="Evidence supports this requirement."))
        else:
            lemmas.append(LemmaCheck(claim=claim_text, status=LemmaStatus.FAILED, evidence="Evidence does not prove this requirement.", missing_proof=missing_text))
            missing.append(missing_text)

    risks = []
    if "password" in lower and "console" in lower and "removed" not in lower:
        risks.append(Risk(label="Security risk", severity=Severity.HIGH, description="Evidence supports the idea that the password may be logged to the console."))
    if any("test" in item.lower() for item in missing):
        risks.append(Risk(label="Regression risk", severity=Severity.MEDIUM, description="Missing tests make the workflow for login hard to trust."))

    fix = "Add the missing backend route, invalid-login handling, redirect proof, passing tests, and remove password logging. Recheck with file changes and test output."
    if not missing:
        fix = "No fix needed. The login workflow is proven."
    return _new_report(goal, claim, evidence, lemmas, missing, risks, fix, report_id, created_at)


def _refund_report(goal: str, claim: str, evidence: str, report_id: str | None, created_at: datetime | None) -> VerificationReportResponse:
    lower = evidence.lower()
    has_confirmation = "confirmation number" in lower and ("rf-" in lower or re.search(r"\b[a-z]{1,4}-?\d{4,}\b", lower) is not None)
    has_receipt = "receipt" in lower or "email" in lower and "received" in lower

    lemmas = [
        LemmaCheck(claim="Refund form was submitted", status=LemmaStatus.PASSED if "submit" in lower or "submitted" in lower or has_confirmation else LemmaStatus.UNKNOWN, evidence="Submission evidence found." if "submit" in lower or "submitted" in lower or has_confirmation else "No clear submission proof found.", missing_proof=None if "submit" in lower or "submitted" in lower or has_confirmation else "Submission event proof"),
        LemmaCheck(claim="Confirmation number was saved", status=LemmaStatus.PASSED if has_confirmation else LemmaStatus.FAILED, evidence="Confirmation number found." if has_confirmation else "No confirmation number found.", missing_proof=None if has_confirmation else "Confirmation number"),
        LemmaCheck(claim="Receipt or follow-up proof exists", status=LemmaStatus.PASSED if has_receipt else LemmaStatus.PARTIAL, evidence="Receipt evidence found." if has_receipt else "No receipt proof found yet.", missing_proof=None if has_receipt else "Email receipt or downloadable confirmation"),
    ]
    missing = [lemma.missing_proof for lemma in lemmas if lemma.missing_proof]
    risks = [] if has_confirmation else [Risk(label="Unverifiable submission", severity=Severity.HIGH, description="Without a confirmation number, the refund may not have been submitted.")]
    fix = "Retrieve or resubmit the refund request and capture the confirmation number plus receipt. Recheck with that proof."
    if not missing:
        fix = "No fix is necessary. The worflow for refund has been proven."
    return _new_report(goal, claim, evidence, lemmas, missing, risks, fix, report_id, created_at)


def _generic_report(goal: str, claim: str, evidence: str, report_id: str | None, created_at: datetime | None) -> VerificationReportResponse:
    lower = evidence.lower()
    lemmas = [
        LemmaCheck(claim="Claimed output exists", status=LemmaStatus.PARTIAL if evidence.strip() else LemmaStatus.UNKNOWN, evidence="Some evidence was provided." if evidence.strip() else "No evidence provided.", missing_proof=None if evidence.strip() else "Output proof"),
        LemmaCheck(claim="Completion evidence exists", status=LemmaStatus.PARTIAL if any(word in lower for word in ["done", "sent", "created", "passed", "confirmation"]) else LemmaStatus.UNKNOWN, evidence="Evidence has completion-like language." if evidence.strip() else "No completion proof found.", missing_proof="Specific completion log"),
        LemmaCheck(claim="Failure handling exists", status=LemmaStatus.UNKNOWN, evidence="Failure handling was not checked by the generic verifier.", missing_proof="Failure or error-handling proof"),
        LemmaCheck(claim="Final confirmation exists", status=LemmaStatus.UNKNOWN, evidence="No final confirmation found.", missing_proof="Final confirmation output"),
    ]
    missing = [lemma.missing_proof for lemma in lemmas if lemma.missing_proof]
    risks = [Risk(label="Weak evidence", severity=Severity.MEDIUM, description="The generic verifier cannot strongly prove this claim without more structured evidence.")]
    fix = "Provide concrete proof such as logs, timestamps, output files, confirmation IDs, screenshots, or test results, then recheck."
    return _new_report(goal, claim, evidence, lemmas, missing, risks, fix, report_id, created_at)


def _score_verdict(lemmas: list[LemmaCheck]) -> Verdict:
    if not lemmas or all(lemma.status == LemmaStatus.UNKNOWN for lemma in lemmas):
        return Verdict.UNVERIFIABLE
    if all(lemma.status == LemmaStatus.PASSED for lemma in lemmas):
        return Verdict.PROVEN
    if any(lemma.status == LemmaStatus.FAILED for lemma in lemmas):
        return Verdict.NOT_PROVEN
    return Verdict.PARTIALLY_PROVEN


def _confidence(lemmas: list[LemmaCheck], verdict: Verdict) -> int:
    if not lemmas:
        return 0
    values = {
        LemmaStatus.PASSED: 1.0,
        LemmaStatus.PARTIAL: 0.55,
        LemmaStatus.UNKNOWN: 0.25,
        LemmaStatus.FAILED: 0.0,
    }
    score = sum(values[lemma.status] for lemma in lemmas) / len(lemmas)
    if verdict == Verdict.PROVEN:
        return max(90, round(score * 100))
    if verdict == Verdict.NOT_PROVEN:
        return max(70, round((1 - score) * 100))
    if verdict == Verdict.UNVERIFIABLE:
        return 35
    return round(score * 100)


def _summary(verdict: Verdict, lemmas: list[LemmaCheck]) -> str:
    passed = sum(1 for lemma in lemmas if lemma.status == LemmaStatus.PASSED)
    failed = sum(1 for lemma in lemmas if lemma.status == LemmaStatus.FAILED)
    partial = sum(1 for lemma in lemmas if lemma.status == LemmaStatus.PARTIAL)
    unknown = sum(1 for lemma in lemmas if lemma.status == LemmaStatus.UNKNOWN)

    if verdict == Verdict.PROVEN:
        return f"All {len(lemmas)} lemmas are proven. Thus, the automation's claim is verified."
    if verdict == Verdict.NOT_PROVEN:
        return f"The automation claim is not proven. {passed} lemmas passed, {failed} failed, {partial} were partial, and {unknown} were unknown."
    if verdict == Verdict.PARTIALLY_PROVEN:
        return f"The automation claim is partially proven. {passed} lemmas passed, but more proof is needed."
    return "The automation claim is unverifiable from the evidence provided."
