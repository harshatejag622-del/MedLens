import os
import re
import uuid
import hashlib
from typing import Optional, Tuple
from fastapi import HTTPException, status
from app.config import settings

# Supported document types and magic bytes signatures
SUPPORTED_EXTENSIONS = {"pdf", "txt", "png", "jpg", "jpeg", "tiff", "webp"}

MAGIC_BYTE_SIGNATURES = {
    "pdf": [b"%PDF-"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "tiff": [b"II*\x00", b"MM\x00*"],
    "webp": [b"RIFF"],
}

MIME_TYPE_MAPPINGS = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "webp": "image/webp",
    "txt": "text/plain",
}

class StorageService:
    """
    Secure Storage Abstraction for clinical documents.
    Enforces file integrity, cryptographic hashing, directory traversal prevention,
    and guarantees that original documents are never overwritten.
    """

    @classmethod
    def get_storage_root(cls) -> str:
        base_dir = os.path.abspath(settings.STORAGE_DIR)
        os.makedirs(base_dir, exist_ok=True)
        return base_dir

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Removes path traversal components and unsafe characters.
        """
        # Strip path components
        base = os.path.basename(filename)
        # Remove any path traversal tokens like '..'
        base = base.replace("..", "")
        # Keep only alphanumeric, hyphens, underscores, spaces, and dots
        clean = re.sub(r'[^a-zA-Z0-9_\-\. ]', '_', base)
        return clean.strip() or "document"

    @classmethod
    def validate_file_upload(cls, filename: str, content: bytes, client_mime: Optional[str] = None) -> str:
        """
        Strict validation of file size, extension, MIME type, and magic bytes.
        Detects empty, oversized, disallowed, or corrupted documents.
        Returns the normalized MIME type string.
        """
        # 1. File size limit validation
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({len(content) / (1024 * 1024):.2f}MB) exceeds the maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        # 2. Non-empty file validation
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded. Medical reports must contain valid document data."
            )

        # 3. File extension validation
        parts = filename.rsplit(".", 1)
        if len(parts) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is missing an extension. Supported extensions: PDF, PNG, JPG, JPEG, TIFF, WEBP, TXT."
            )

        ext = parts[1].lower().strip()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '.{ext}'. Supported extensions: PDF, PNG, JPG, JPEG, TIFF, WEBP, TXT."
            )

        # 4. Content signature and corruption verification
        if ext in MAGIC_BYTE_SIGNATURES:
            signatures = MAGIC_BYTE_SIGNATURES[ext]
            # Check magic bytes within the first 1024 bytes (some PDFs have leading comment or whitespace)
            has_valid_header = any(sig in content[:1024] for sig in signatures)
            if not has_valid_header:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Corrupted or invalid {ext.upper()} document: Header magic bytes do not match standard {ext.upper()} format."
                )

            # Extra check for PDF structural corruption: Minimum viable size and EOF marker
            if ext == "pdf":
                if len(content) < 50:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupted PDF: Document payload is too small to constitute a valid PDF structure."
                    )
                # Ensure it's not a truncated placeholder
                if b"%EOF" not in content[-1024:]:
                    # Some PDFs might have trailing bytes, check if xref or obj exists
                    if b"obj" not in content and b"xref" not in content and b"trailer" not in content:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Corrupted PDF: Incomplete PDF stream, missing standard EOF and object cross-reference definitions."
                        )

            # Extra check for WEBP: must contain 'WEBP'
            if ext == "webp" and b"WEBP" not in content[:16]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted or invalid WEBP document: Missing WEBP sub-header."
                )

        elif ext == "txt":
            # Verify plain text encoding (UTF-8 or Latin-1) without null executable bytes
            if b"\x00" in content[:512]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid text document: Binary executable characters detected in plain text file."
                )
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content.decode("latin-1")
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Corrupted text file: Content could not be decoded with UTF-8 or Latin-1."
                    )

        return MIME_TYPE_MAPPINGS.get(ext, "application/octet-stream")

    @classmethod
    def compute_sha256(cls, content: bytes) -> str:
        """
        Computes SHA-256 cryptographic checksum.
        """
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def store_document(
        cls,
        patient_id: str,
        original_filename: str,
        content: bytes
    ) -> Tuple[str, str, int, str]:
        """
        Stores the original document separately in a secure isolated patient subdirectory.
        Guarantees that original documents are NEVER overwritten by appending a unique UUID.
        Returns (stored_filename, absolute_path, file_size_bytes, sha256_checksum).
        """
        storage_root = cls.get_storage_root()
        clean_patient_id = cls.sanitize_filename(patient_id)
        patient_dir = os.path.join(storage_root, clean_patient_id)
        os.makedirs(patient_dir, exist_ok=True)

        sanitized_name = cls.sanitize_filename(original_filename)
        # Ensure unique stored filename with UUID to guarantee no file is ever overwritten
        stored_filename = f"{uuid.uuid4()}_{sanitized_name}"
        destination_path = os.path.abspath(os.path.join(patient_dir, stored_filename))

        # Security check against path traversal
        if not destination_path.startswith(storage_root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Invalid storage destination path."
            )

        # Write binary content
        with open(destination_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        checksum = cls.compute_sha256(content)

        return stored_filename, destination_path, file_size, checksum

    @classmethod
    def get_document_path(cls, patient_id: str, stored_filename: str) -> str:
        """
        Retrieves absolute path with path traversal protection.
        """
        storage_root = cls.get_storage_root()
        clean_patient_id = cls.sanitize_filename(patient_id)
        clean_stored_name = os.path.basename(stored_filename)

        full_path = os.path.abspath(os.path.join(storage_root, clean_patient_id, clean_stored_name))
        if not full_path.startswith(storage_root):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Invalid storage path."
            )

        if not os.path.exists(full_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original document file not found on storage volume."
            )

        return full_path

    @classmethod
    def read_document_bytes(cls, patient_id: str, stored_filename: str) -> bytes:
        """
        Reads original document bytes securely.
        """
        path = cls.get_document_path(patient_id, stored_filename)
        with open(path, "rb") as f:
            return f.read()

    @classmethod
    def delete_document(cls, patient_id: str, stored_filename: str) -> bool:
        """
        Deletes the physical document file.
        """
        try:
            path = cls.get_document_path(patient_id, stored_filename)
            if os.path.exists(path):
                os.remove(path)
                return True
        except Exception:
            pass
        return False
