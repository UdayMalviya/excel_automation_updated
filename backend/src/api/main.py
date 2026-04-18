from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.app import create_app
from src.schemas.task import StartTaskRequest, SubmitCaptchaRequest, TaskResponse
from src.services.playwright_service import PlaywrightService

logger = structlog.get_logger(__name__)
api_router = APIRouter()
app: FastAPI = create_app()


def get_playwright_service() -> PlaywrightService:
    return PlaywrightService()


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
    payload: StartTaskRequest,
    service: PlaywrightService = Depends(get_playwright_service),
) -> TaskResponse:
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


app.include_router(api_router)
