from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from pathlib import Path

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    expect,
)

from src.core.config import settings
from src.schemas.task import StartTaskRequest, SubmitCaptchaRequest, TaskResponse
from src.services.excel_service import ExcelTaskMapper

logger = structlog.get_logger(__name__)


class PlaywrightService:
    _sessions: dict[str, dict] = {}
    _downloads: dict[str, dict[str, str]] = {}
    _excel_mapper = ExcelTaskMapper()

    async def start(self, payload: StartTaskRequest) -> TaskResponse:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        logs: list[dict] = []
        session_id = str(uuid4())

        def add_log(stage: str, message: str, **extra) -> None:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "message": message,
                **extra,
            }
            logs.append(event)
            logger.info("automation.stage", session_id=session_id, **event)

        add_log("startup", "Launching Playwright browser", display=settings.display)

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=settings.playwright_headless,
                args=["--start-maximized"],
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                ignore_https_errors=True,
                no_viewport=True,
            )
            page = await context.new_page()

            await self._prepare_login(
                page, str(payload.url), payload.username, payload.password, add_log
            )

            self._sessions[session_id] = {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "payload": payload,
                "started_at": started_at,
                "logs": logs,
            }

            await page.screenshot(path="/tmp/last-run.png", full_page=True)
            add_log(
                "captcha",
                "Waiting for CAPTCHA input from UI",
                screenshot="/tmp/last-run.png",
            )

            finished_at = datetime.now(timezone.utc)
            return TaskResponse(
                status="awaiting_captcha",
                message="Browser is ready. Read the CAPTCHA from the live browser and submit it from the UI.",
                url=str(payload.url),
                session_id=session_id,
                title=await page.title(),
                source_file_name=payload.source_file_name,
                source_row_number=payload.source_row_number,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((perf_counter() - started) * 1000),
                logs=logs,
            )
        except Exception as exc:
            add_log("error", "Automation start failed", error=str(exc))
            await self._cleanup_session(session_id)
            finished_at = datetime.now(timezone.utc)
            return TaskResponse(
                status="error",
                message=f"Automation start failed: {exc}",
                url=str(payload.url),
                session_id=session_id,
                title=None,
                source_file_name=payload.source_file_name,
                source_row_number=payload.source_row_number,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((perf_counter() - started) * 1000),
                logs=logs,
            )

    async def submit_captcha(self, payload: SubmitCaptchaRequest) -> TaskResponse:
        session = self._sessions.get(payload.session_id)
        if not session:
            now = datetime.now(timezone.utc)
            return TaskResponse(
                status="error",
                message="Session not found or expired.",
                url=None,
                session_id=payload.session_id,
                title=None,
                started_at=now,
                finished_at=now,
                duration_ms=0,
                logs=[],
            )

        started = perf_counter()
        logs = session["logs"]
        page: Page = session["page"]
        original_payload: StartTaskRequest = session["payload"]
        started_at: datetime = session["started_at"]

        def add_log(stage: str, message: str, **extra) -> None:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "message": message,
                **extra,
            }
            logs.append(event)
            logger.info("automation.stage", session_id=payload.session_id, **event)

        title: str | None = None
        batch_summary: dict[str, int] | None = None
        download_id: str | None = None
        download_path: str | None = None
        result_file_name: str | None = None

        try:
            await page.fill("#txtCaptchaInput", payload.captcha_text)
            await page.click("input[type=submit]")
            add_log("captcha", "Submitted CAPTCHA from UI")

            await page.locator("#btnLogout").wait_for(state="visible", timeout=10000)
            add_log("login", "Login successful")
            await self._handle_post_login_popup(page, add_log)

            title = await page.title()
            add_log("inspection", "Collected page title", title=title)

            if original_payload.source_file_path:
                batch_summary = await self._process_excel_workbook(
                    page, original_payload, add_log
                )
            else:
                await self._execute_payload_flow(page, original_payload, add_log)

            await page.screenshot(path="/tmp/last-run.png", full_page=True)
            add_log("artifacts", "Saved screenshot", path="/tmp/last-run.png")

            if settings.playwright_keep_open_ms > 0:
                add_log(
                    "viewer",
                    "Keeping browser open for live viewing",
                    keep_open_ms=settings.playwright_keep_open_ms,
                )
                await page.wait_for_timeout(settings.playwright_keep_open_ms)

            finished_at = datetime.now(timezone.utc)
            if original_payload.source_file_path:
                download_id, result_file_name = self._register_download_artifact(
                    original_payload.source_file_path,
                    self._excel_mapper.workbook_result_name(
                        original_payload.source_file_name, finished_at
                    ),
                )
                download_path = f"/download-result/{download_id}"
            return TaskResponse(
                status="success",
                message=self._build_success_message(batch_summary),
                url=str(original_payload.url),
                session_id=payload.session_id,
                title=title,
                source_file_name=original_payload.source_file_name,
                source_row_number=original_payload.source_row_number,
                result_file_name=result_file_name,
                download_id=download_id,
                download_path=download_path,
                processed_rows=batch_summary["processed"] if batch_summary else None,
                successful_rows=batch_summary["successful"] if batch_summary else None,
                failed_rows=batch_summary["failed"] if batch_summary else None,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((perf_counter() - started) * 1000),
                logs=logs,
            )
        except Exception as exc:
            add_log("error", "Automation failed", error=str(exc))
            await self._capture_debug(page, "captcha_submit", add_log)
            finished_at = datetime.now(timezone.utc)
            if (
                original_payload.source_file_path
                and Path(original_payload.source_file_path).exists()
            ):
                download_id, result_file_name = self._register_download_artifact(
                    original_payload.source_file_path,
                    self._excel_mapper.workbook_result_name(
                        original_payload.source_file_name, finished_at
                    ),
                )
                download_path = f"/download-result/{download_id}"
            return TaskResponse(
                status="error",
                message=f"Automation failed: {exc}",
                url=str(original_payload.url),
                session_id=payload.session_id,
                title=title,
                source_file_name=original_payload.source_file_name,
                source_row_number=original_payload.source_row_number,
                result_file_name=result_file_name,
                download_id=download_id,
                download_path=download_path,
                processed_rows=batch_summary["processed"] if batch_summary else None,
                successful_rows=batch_summary["successful"] if batch_summary else None,
                failed_rows=batch_summary["failed"] if batch_summary else None,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((perf_counter() - started) * 1000),
                logs=logs,
            )
        finally:
            await self._cleanup_session(payload.session_id)

    async def _prepare_login(
        self,
        page: Page,
        url: str,
        username: str,
        password: str,
        add_log,
    ) -> None:
        add_log("navigation", "Navigating to login page", url=url)
        await page.goto(
            url, wait_until="domcontentloaded", timeout=settings.playwright_timeout_ms
        )

        await page.click("#rdbLoginType_3")
        await page.fill("#tbxUserName", username)
        await page.fill("#tbxPassword", password)

        captcha_path = "/tmp/captcha.png"
        await page.locator("#imgCaptcha").screenshot(path=captcha_path)
        add_log("captcha", "Captured CAPTCHA image", path=captcha_path)

    @staticmethod
    def _resolve_flow(payload: StartTaskRequest) -> str:
        transaction_type = (payload.transaction_type or "").strip().lower()
        action = (payload.action or "").strip().lower()

        if transaction_type:
            if transaction_type == "vitran":
                return "fill_vitran_form"
            if transaction_type == "vasuli":
                return "fill_vasuli_form"
            if transaction_type == "login_only":
                return "login_only"
            raise ValueError(
                f"Unknown transaction_type: {transaction_type}. Expected 'vitran', 'vasuli', or 'login_only'."
            )

        if action in {"", "login_only"}:
            return "login_only"
        if action in {"fill_vitran_form", "vitran"}:
            return "fill_vitran_form"
        if action in {"fill_vasuli_form", "vasuli"}:
            return "fill_vasuli_form"
        raise ValueError(
            f"Unknown action: {action}. Expected 'login_only', 'fill_vitran_form', or 'fill_vasuli_form'."
        )

    async def _execute_payload_flow(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        flow = self._resolve_flow(payload)
        if flow == "login_only":
            return

        await self._open_farmer_details_page(page, add_log)
        await self._trigger_search(page, add_log)
        await self._click_table_link(
            page,
            "वितरण",
            add_log,
            timeout=15000,
        )
        await page.wait_for_load_state("networkidle")

        if flow == "fill_vitran_form":
            await self._fill_vitran_form(page, payload, add_log)
        elif flow == "fill_vasuli_form":
            await self._fill_vasuli_form(page, payload, add_log)

    async def _open_farmer_details_page(self, page: Page, add_log) -> None:
        add_log("navigation", "Opening Farmer Details page")
        await page.locator("span:has-text('Intrest Subvention')").click()
        link = page.locator("a[href='FarmerDetailsView.aspx']")
        await expect(link).to_be_visible(timeout=10000)
        await link.click()
        await page.wait_for_load_state("domcontentloaded")

    async def _trigger_search(self, page: Page, add_log) -> None:
        add_log("navigation", "Triggering search")
        search_btn = page.get_by_role("button", name="Search")
        await expect(search_btn).to_be_visible(timeout=10000)
        await search_btn.click()

    async def _click_table_link(
        self,
        page: Page,
        link_text: str,
        add_log,
        timeout: int = 15000,
    ) -> None:
        table = page.locator("table")
        await expect(table).to_be_visible(timeout=timeout)
        rows = table.locator("tr")
        await expect(rows.first).to_be_visible(timeout=timeout)
        target_row = table.locator(f"tr:has(a:has-text('{link_text}'))").first
        await expect(target_row).to_be_visible(timeout=timeout)
        link = target_row.locator(f"a:has-text('{link_text}')")
        count = await link.count()
        add_log(
            "table_click",
            "Located table link candidates",
            link_text=link_text,
            count=count,
        )
        if count == 0:
            raise RuntimeError(f"Link '{link_text}' not found in table")
        await link.first.click(force=True)
        add_log("table_click", "Clicked table link", link_text=link_text)

    async def _fill_vitran_form(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        self._require_fields(payload, ["loan_type", "loan_mode", "date", "amount"])
        loan_type_option = page.locator(
            f"#ContentPlaceHolder1_rblLoantype_{payload.loan_type}"
        )
        loan_mode_option = page.locator(
            f"#ContentPlaceHolder1_rblLoantypecase_{payload.loan_mode}"
        )
        date_input = page.locator("#ContentPlaceHolder1_txtdateDR")
        amount_input = page.locator("#ContentPlaceHolder1_txtdr")
        await expect(
            page.locator("input[name='ctl00$ContentPlaceHolder1$rblLoantype']").first
        ).to_be_visible(timeout=10000)
        await expect(loan_type_option).to_be_visible(timeout=10000)
        await expect(loan_mode_option).to_be_visible(timeout=10000)
        await expect(date_input).to_be_visible(timeout=10000)
        await expect(amount_input).to_be_visible(timeout=10000)
        await loan_type_option.check()
        await loan_mode_option.check()
        await date_input.fill(payload.date or "")
        await amount_input.fill(payload.amount or "")
        add_log(
            "form",
            "Vitran form filled",
            loan_type=payload.loan_type,
            loan_mode=payload.loan_mode,
            date=payload.date,
            amount=payload.amount,
        )
        await page.wait_for_load_state("networkidle")

    async def _fill_vasuli_form(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        self._require_fields(payload, ["loan_type", "season", "date", "amount"])
        loan_type_option = page.locator(
            f"#ContentPlaceHolder1_rblLoantypeRec_{payload.loan_type}"
        )
        season_option = page.locator(
            f"#ContentPlaceHolder1_rblseasonrec_{payload.season}"
            
        )
        date_input = page.locator("#ContentPlaceHolder1_txtdaterec")
        amount_input = page.locator("#ContentPlaceHolder1_txtcr")
        await expect(loan_type_option).to_be_visible(timeout=10000)
        await expect(season_option).to_be_visible(timeout=10000)
        await expect(date_input).to_be_visible(timeout=10000)
        await expect(amount_input).to_be_visible(timeout=10000)
        await loan_type_option.check()
        await season_option.check()
        await date_input.fill(payload.date or "")
        await amount_input.fill(payload.amount or "")
        add_log(
            "form",
            "Vasuli form filled",
            loan_type=payload.loan_type,
            season=payload.season,
            date=payload.date,
            amount=payload.amount,
        )
        await page.wait_for_load_state("networkidle")

    async def _process_excel_workbook(
        self,
        page: Page,
        payload: StartTaskRequest,
        add_log,
    ) -> dict[str, int]:
        workbook_path = payload.source_file_path
        if not workbook_path:
            raise ValueError("Workbook path is missing for Excel processing.")

        dataframe = await self._excel_mapper.load_workbook(workbook_path)
        normalized_columns = self._excel_mapper.normalized_columns(dataframe)
        self._excel_mapper.ensure_status_columns(dataframe, normalized_columns)
        normalized_columns = self._excel_mapper.normalized_columns(dataframe)

        processed = 0
        successful = 0
        failed = 0

        for row_index, row in dataframe.iterrows():
            if not self._excel_mapper.row_has_values(row):
                continue

            row_payload = self._excel_mapper.build_request_from_row(
                base_payload=payload,
                normalized_columns=normalized_columns,
                row=row,
                row_index=row_index,
                filename=payload.source_file_name or "uploaded.xlsx",
                workbook_path=workbook_path,
            )
            farmer_name = row_payload.farmer_name or f"Row {row_index + 2}"
            existing_remark = (row_payload.farmer_added_remark or "").strip().upper()

            if existing_remark in {"DONE", "PROCESSING"}:
                add_log(
                    "excel",
                    "Skipping row already marked complete",
                    row_number=row_index + 2,
                    farmer_name=farmer_name,
                    remark=existing_remark,
                )
                continue

            self._excel_mapper.update_status_columns(
                dataframe,
                normalized_columns,
                row_index=row_index,
                farmer_remark="PROCESSING",
                transaction_remark="Started processing...",
            )
            await self._excel_mapper.save_workbook(dataframe, workbook_path)

            try:
                add_log(
                    "excel",
                    "Processing workbook row",
                    row_number=row_index + 2,
                    farmer_name=farmer_name,
                    transaction_type=row_payload.transaction_type,
                )
                await self._execute_payload_flow(page, row_payload, add_log)
                self._excel_mapper.update_status_columns(
                    dataframe,
                    normalized_columns,
                    row_index=row_index,
                    farmer_remark="DONE",
                    transaction_remark=self._excel_mapper.build_success_remark(),
                )
                successful += 1
            except Exception as exc:
                self._excel_mapper.update_status_columns(
                    dataframe,
                    normalized_columns,
                    row_index=row_index,
                    farmer_remark="FAILED",
                    transaction_remark=str(exc)[:500],
                )
                failed += 1
                add_log(
                    "excel",
                    "Workbook row failed",
                    row_number=row_index + 2,
                    farmer_name=farmer_name,
                    error=str(exc),
                )
            finally:
                processed += 1
                await self._excel_mapper.save_workbook(dataframe, workbook_path)

        add_log(
            "excel",
            "Workbook processing complete",
            processed=processed,
            successful=successful,
            failed=failed,
            workbook_path=workbook_path,
        )
        return {
            "processed": processed,
            "successful": successful,
            "failed": failed,
        }

    @staticmethod
    def _require_fields(payload: StartTaskRequest, fields: list[str]) -> None:
        missing = [field for field in fields if getattr(payload, field) in (None, "")]
        if missing:
            raise ValueError(
                f"Missing required fields for action: {', '.join(missing)}"
            )

    async def _handle_post_login_popup(self, page: Page, add_log) -> None:
        popup_selectors = (
            "button:has-text('Close')",
            "button:has-text('OK')",
            "button:has-text('Ok')",
            "input[value='Close']",
            "input[value='OK']",
            ".modal button.close",
            ".popup-close",
        )

        for selector in popup_selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=1500)
                if await locator.is_visible():
                    await locator.click(force=True)
                    add_log("popup", "Dismissed post-login popup", selector=selector)
                    await page.wait_for_timeout(500)
                    return
            except Exception:
                continue

        dialog = page.get_by_role("dialog").first
        try:
            await dialog.wait_for(state="visible", timeout=1500)
            if await dialog.is_visible():
                close_button = (
                    dialog.get_by_role("button").filter(has_text="Close").first
                )
                await close_button.wait_for(state="visible", timeout=1000)
                if await close_button.is_visible():
                    await close_button.click(force=True)
                    add_log("popup", "Dismissed dialog popup", selector="role=dialog")
                    await page.wait_for_timeout(500)
                    return
        except Exception:
            pass

        add_log("popup", "No post-login popup detected")

    async def _capture_debug(self, page: Page, tag: str, add_log) -> None:
        screenshot_path = f"/tmp/error_{tag}.png"
        html_path = f"/tmp/error_{tag}.html"
        await page.screenshot(path=screenshot_path)
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        add_log(
            "debug",
            "Captured debug artifacts",
            screenshot=screenshot_path,
            html=html_path,
        )

    async def _cleanup_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if not session:
            return

        page = session.get("page")
        context: BrowserContext | None = session.get("context")
        browser: Browser | None = session.get("browser")
        playwright: Playwright | None = session.get("playwright")

        try:
            if page and not page.is_closed():
                await page.close()
        except Exception:
            pass
        try:
            if context:
                await context.close()
        except Exception:
            pass
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if playwright:
                await playwright.stop()
        except Exception:
            pass

    @staticmethod
    def _build_success_message(batch_summary: dict[str, int] | None) -> str:
        if not batch_summary:
            return "Automation completed"
        return (
            "Automation completed. "
            f"Processed {batch_summary['processed']} rows, "
            f"succeeded {batch_summary['successful']}, "
            f"failed {batch_summary['failed']}."
        )

    @classmethod
    def _register_download_artifact(
        cls, file_path: str, download_name: str | None
    ) -> tuple[str, str]:
        artifact_id = str(uuid4())
        safe_name = download_name or Path(file_path).name
        cls._downloads[artifact_id] = {
            "path": file_path,
            "filename": safe_name,
        }
        return artifact_id, safe_name

    @classmethod
    def get_download_artifact(cls, artifact_id: str) -> dict[str, str] | None:
        return cls._downloads.get(artifact_id)
