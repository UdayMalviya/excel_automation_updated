from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class StartTaskRequest(BaseModel):
    url: HttpUrl
    username: str
    password: str
    action: str = Field(default="login_only")
    transaction_type: str | None = None
    loan_type: int | None = None
    loan_mode: int | None = None
    season: int | None = None
    date: str | None = None
    amount: str | None = None


class SubmitCaptchaRequest(BaseModel):
    session_id: str
    captcha_text: str


class TaskResponse(BaseModel):
    status: str
    message: str
    url: str | None = None
    session_id: str | None = None
    title: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    logs: list[dict]
