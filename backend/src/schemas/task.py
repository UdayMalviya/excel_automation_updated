from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class StartTaskRequest(BaseModel):
    url: HttpUrl
    username: str
    password: str
    action: str = Field(default="login_only")
    sr: str | None = None
    farmer_name: str | None = None
    guardian_name: str | None = None
    gender: str | None = None
    tehsil_name: str | None = None
    village_name: str | None = None
    farmer_type: str | None = None
    category: str | None = None
    savings_account_number: str | None = None
    mobile_number: str | None = None
    aadhaar_number: str | None = None
    erp_admission_number: str | None = None
    transaction_type: str | None = None
    loan_type: int | None = None
    loan_mode: int | None = None
    season: int | None = None
    date: str | None = None
    amount: str | None = None
    farmer_added_remark: str | None = None
    transaction_remark: str | None = None
    source_file_name: str | None = None
    source_file_path: str | None = None
    source_row_number: int | None = None


class SubmitCaptchaRequest(BaseModel):
    session_id: str
    captcha_text: str


class TaskResponse(BaseModel):
    status: str
    message: str
    url: str | None = None
    session_id: str | None = None
    title: str | None = None
    source_file_name: str | None = None
    source_row_number: int | None = None
    result_file_name: str | None = None
    download_id: str | None = None
    download_path: str | None = None
    processed_rows: int | None = None
    successful_rows: int | None = None
    failed_rows: int | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    logs: list[dict]
