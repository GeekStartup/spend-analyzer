from pydantic import BaseModel


class StatementUploadResponse(BaseModel):
    statement_reference: str
    original_file_name: str
    stored_file_name: str
    content_type: str
    file_size_bytes: int
    status: str
    institution: str | None = None
    account_type: str | None = None
    account_name: str | None = None
    statement_format: str | None = None
