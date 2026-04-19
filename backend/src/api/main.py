from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from src.api.app import create_app
from src.schemas.task import StartTaskRequest, SubmitCaptchaRequest, TaskResponse
from src.services.excel_service import ExcelTaskMapper
from src.services.playwright_service import PlaywrightService

logger = structlog.get_logger(__name__)
api_router = APIRouter()
app: FastAPI = create_app()


def get_playwright_service() -> PlaywrightService:
    return PlaywrightService()


def get_excel_task_mapper() -> ExcelTaskMapper:
    return ExcelTaskMapper()


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@api_router.get("/health")
async def health_check() -> JSONResponse:
    logger.info("healthcheck.ok", stage="health")
    return JSONResponse({"status": "ok"})


@api_router.post("/start-task", response_model=TaskResponse)
async def start_task(
    url: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    action: str = Form(default="login_only"),
    transaction_type: str | None = Form(default=None),
    loan_type: int | None = Form(default=None),
    loan_mode: int | None = Form(default=None),
    season: int | None = Form(default=None),
    date: str | None = Form(default=None),
    amount: str | None = Form(default=None),
    excel_file: UploadFile | None = File(default=None),
    service: PlaywrightService = Depends(get_playwright_service),
    excel_mapper: ExcelTaskMapper = Depends(get_excel_task_mapper),
) -> TaskResponse:
    payload = StartTaskRequest(
        url=url,
        username=username,
        password=password,
        action=action,
        transaction_type=transaction_type,
        loan_type=loan_type,
        loan_mode=loan_mode,
        season=season,
        date=date,
        amount=amount,
    )

    if excel_file is not None:
        payload = await excel_mapper.prepare_request_from_excel(
            file_bytes=await excel_file.read(),
            filename=excel_file.filename or "uploaded.xlsx",
            base_payload=payload,
        )

    logger.info("automation.request.received", stage="request", url=str(payload.url))
    return await service.start(payload)


@api_router.post("/submit-captcha", response_model=TaskResponse)
async def submit_captcha(
    payload: SubmitCaptchaRequest,
    service: PlaywrightService = Depends(get_playwright_service),
) -> TaskResponse:
    logger.info(
        "automation.captcha.received", stage="request", session_id=payload.session_id
    )
    return await service.submit_captcha(payload)


@api_router.get("/download-result/{download_id}")
async def download_result(
    download_id: str,
    service: PlaywrightService = Depends(get_playwright_service),
) -> FileResponse:
    artifact = service.get_download_artifact(download_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Processed Excel file not found.")
    return FileResponse(
        path=artifact["path"],
        filename=artifact["filename"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


app.include_router(api_router)
