import io
import pytest
from app.config import settings
from app.services.storage_service import StorageService

MINIMAL_VALID_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n"
    b"0 4\n"
    b"0000000000 65535 f \n"
    b"0000000010 00000 n \n"
    b"0000000060 00000 n \n"
    b"0000000117 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n"
    b"190\n"
    b"%%EOF"
)

MINIMAL_VALID_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

VALID_TXT_REPORT = b"CLINICAL LABORATORY REPORT\nPatient: Alex Morgan\nSpecimen: Peripheral Blood\nHemoglobin: 13.5 g/dL (Normal)\n"

def test_valid_pdf_upload(client):
    """
    Test uploading a valid PDF document.
    Verifies storage, checksum computation, QUEUED processing state, and job creation.
    """
    # Get Alex Morgan ID
    patients = client.get("/api/patients").json()
    alex = next(p for p in patients if p["mrn"] == "SYN-1001")

    files = {
        "file": ("metabolic_panel.pdf", io.BytesIO(MINIMAL_VALID_PDF), "application/pdf")
    }
    data = {
        "patient_id": alex["id"],
        "document_type": "LABORATORY_REPORT",
        "facility": "St. Jude Clinical Labs",
        "source": "Outpatient Clinic"
    }

    res = client.post("/api/documents/upload", files=files, data=data)
    assert res.status_code == 201
    payload = res.json()

    doc = payload["document"]
    assert doc["original_filename"] == "metabolic_panel.pdf"
    assert doc["patient_id"] == alex["id"]
    assert doc["processing_status"] == "QUEUED"
    assert doc["file_type"] == "application/pdf"
    assert doc["sha256_checksum"] == StorageService.compute_sha256(MINIMAL_VALID_PDF)

    # Verify processing job is created in QUEUED state
    job = payload["job"]
    assert job["document_id"] == doc["id"]
    assert job["status"] == "QUEUED"
    assert job["current_step"] == "INGESTION_COMPLETED"

    # Verify document download endpoint
    dl_res = client.get(f"/api/documents/{doc['id']}/download")
    assert dl_res.status_code == 200
    assert dl_res.content == MINIMAL_VALID_PDF


def test_invalid_file_extension_and_mime(client):
    """
    Test rejection of invalid file extensions and mismatched MIME / magic bytes.
    """
    patients = client.get("/api/patients").json()
    alex = patients[0]

    # 1. Disallowed extension (.exe)
    res_exe = client.post(
        "/api/documents/upload",
        files={"file": ("malicious_script.exe", io.BytesIO(b"MZ\x90\x00\x03"), "application/x-msdownload")},
        data={"patient_id": alex["id"]}
    )
    assert res_exe.status_code == 400
    assert "Unsupported file type" in res_exe.json()["detail"]

    # 2. Pretending to be PDF but containing plain text without %PDF- magic bytes
    res_fake_pdf = client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"This is just a text file renamed to pdf"), "application/pdf")},
        data={"patient_id": alex["id"]}
    )
    assert res_fake_pdf.status_code == 400
    assert "Header magic bytes do not match" in res_fake_pdf.json()["detail"]


def test_oversized_file(client, monkeypatch):
    """
    Test rejection of files that exceed the maximum allowed upload size.
    """
    patients = client.get("/api/patients").json()
    alex = patients[0]

    # Monkeypatch limit to 1MB for isolated testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    oversized_content = b"%PDF-" + (b"A" * (1024 * 1024 + 500))
    res = client.post(
        "/api/documents/upload",
        files={"file": ("huge_report.pdf", io.BytesIO(oversized_content), "application/pdf")},
        data={"patient_id": alex["id"]}
    )
    assert res.status_code == 413
    assert "exceeds the maximum allowed limit" in res.json()["detail"]


def test_duplicate_document(client):
    """
    Test duplicate detection by SHA-256 checksum per patient.
    """
    patients = client.get("/api/patients").json()
    alex = patients[0]

    custom_pdf = MINIMAL_VALID_PDF + b"%unique_duplicate_test_marker_123"

    # First upload: Success
    res1 = client.post(
        "/api/documents/upload",
        files={"file": ("initial_report.pdf", io.BytesIO(custom_pdf), "application/pdf")},
        data={"patient_id": alex["id"]}
    )
    assert res1.status_code == 201

    # Second upload of identical content: 409 Conflict Duplicate
    res2 = client.post(
        "/api/documents/upload",
        files={"file": ("renamed_duplicate.pdf", io.BytesIO(custom_pdf), "application/pdf")},
        data={"patient_id": alex["id"]}
    )
    assert res2.status_code == 409
    assert "Duplicate document detected" in res2.json()["detail"]


def test_corrupted_document(client):
    """
    Test detection and rejection of corrupted or malformed documents.
    """
    patients = client.get("/api/patients").json()
    alex = patients[0]

    # Truncated PDF (has magic bytes but is only 15 bytes)
    truncated_pdf = b"%PDF-1.4\nshort"
    res = client.post(
        "/api/documents/upload",
        files={"file": ("corrupted.pdf", io.BytesIO(truncated_pdf), "application/pdf")},
        data={"patient_id": alex["id"]}
    )
    assert res.status_code == 400
    assert "Corrupted PDF" in res.json()["detail"]


def test_unauthorized_upload_non_existent_patient(client):
    """
    Test unauthorized upload attempting to associate a report with an unknown patient.
    """
    res = client.post(
        "/api/documents/upload",
        files={"file": ("report.pdf", io.BytesIO(MINIMAL_VALID_PDF), "application/pdf")},
        data={"patient_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert res.status_code == 404
    assert "Unauthorized document upload" in res.json()["detail"]


def test_valid_image_and_txt_uploads(client):
    """
    Test uploading medical report images (PNG) and clinical TXT records.
    """
    patients = client.get("/api/patients").json()
    jordan = next(p for p in patients if p["mrn"] == "SYN-1002")

    # 1. Valid PNG upload
    res_png = client.post(
        "/api/documents/upload",
        files={"file": ("radiology_xray.png", io.BytesIO(MINIMAL_VALID_PNG), "image/png")},
        data={"patient_id": jordan["id"], "document_type": "RADIOLOGY_REPORT"}
    )
    assert res_png.status_code == 201
    assert res_png.json()["document"]["file_type"] == "image/png"

    # 2. Valid TXT upload
    res_txt = client.post(
        "/api/documents/upload",
        files={"file": ("discharge_notes.txt", io.BytesIO(VALID_TXT_REPORT), "text/plain")},
        data={"patient_id": jordan["id"], "document_type": "DISCHARGE_SUMMARY"}
    )
    assert res_txt.status_code == 201
    assert res_txt.json()["document"]["file_type"] == "text/plain"


def test_document_retry_and_fail_workflow(client):
    """
    Test status tracking, explicit pipeline failure marking, and retry handling.
    """
    patients = client.get("/api/patients").json()
    taylor = next(p for p in patients if p["mrn"] == "SYN-1003")

    # Upload document
    unique_pdf = MINIMAL_VALID_PDF + b"%unique_retry_test_456"
    up_res = client.post(
        "/api/documents/upload",
        files={"file": ("allergy_panel.pdf", io.BytesIO(unique_pdf), "application/pdf")},
        data={"patient_id": taylor["id"]}
    )
    doc_id = up_res.json()["document"]["id"]

    # Mark failed
    fail_res = client.post(f"/api/documents/{doc_id}/fail?reason=OCR+confidence+threshold+not+met")
    assert fail_res.status_code == 200
    assert fail_res.json()["processing_status"] == "FAILED"
    assert "OCR confidence threshold not met" in fail_res.json()["processing_error"]

    # Verify status endpoint
    status_res = client.get(f"/api/documents/{doc_id}/status")
    assert status_res.status_code == 200
    assert status_res.json()["processing_status"] == "FAILED"

    # Retry processing
    retry_res = client.post(f"/api/documents/{doc_id}/retry")
    assert retry_res.status_code == 200
    assert retry_res.json()["status"] == "QUEUED"

    # Verify status is now QUEUED
    status_after = client.get(f"/api/documents/{doc_id}/status")
    assert status_after.json()["processing_status"] == "QUEUED"
    assert status_after.json()["processing_error"] is None


def test_original_document_never_overwritten(client):
    """
    Verify that uploading multiple documents with identical original filenames
    never overwrites the stored binary files on disk due to secure UUID segregation.
    """
    patients = client.get("/api/patients").json()
    taylor = next(p for p in patients if p["mrn"] == "SYN-1003")

    content1 = MINIMAL_VALID_PDF + b"%version_one_content"
    content2 = MINIMAL_VALID_PDF + b"%version_two_content"

    # Upload first document as "report.pdf"
    res1 = client.post(
        "/api/documents/upload",
        files={"file": ("report.pdf", io.BytesIO(content1), "application/pdf")},
        data={"patient_id": taylor["id"]}
    )
    doc1 = res1.json()["document"]

    # Upload second document with identical filename "report.pdf" but different content
    res2 = client.post(
        "/api/documents/upload",
        files={"file": ("report.pdf", io.BytesIO(content2), "application/pdf")},
        data={"patient_id": taylor["id"]}
    )
    doc2 = res2.json()["document"]

    # Stored filenames must be unique
    assert doc1["stored_filename"] != doc2["stored_filename"]
    assert doc1["sha256_checksum"] != doc2["sha256_checksum"]

    # Both documents must be intact and downloadable independently
    dl1 = client.get(f"/api/documents/{doc1['id']}/download")
    dl2 = client.get(f"/api/documents/{doc2['id']}/download")
    assert dl1.content == content1
    assert dl2.content == content2
