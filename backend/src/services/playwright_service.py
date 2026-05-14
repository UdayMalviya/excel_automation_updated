import asyncio
import json
from datetime import datetime, timezone
from tempfile import gettempdir
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
    _log_artifacts: dict[str, dict[str, str]] = {}
    _excel_mapper = ExcelTaskMapper()
    _ADD_FARMER_ACTIONS = {"add_farmer", "add_farmer_only"}
    _SOCIETY_BASE_URL = "https://mpapexbankutility.bank.in/DCCB_Branch/DccbSociety"
    _DASHBOARD_URL = f"{_SOCIETY_BASE_URL}/Default.aspx"
    _ADD_FARMER_URL = f"{_SOCIETY_BASE_URL}/FarmerDetails.aspx"
    _VIEW_FARMER_URL = f"{_SOCIETY_BASE_URL}/FarmerDetailsView.aspx"
    _VILLAGE_OPTIONS = {
        "KADODIYA": "कड़ोदिया",
        "HARUKHEDI": "हारूखेड़ी",
        "BUKHARI": "बुखारी",
        "BAGWADA": "बगवाड़ा",
        "RATNAKHEDI": "रत्नाखेड़ी",
        "SALANAKHEDI": "सालनाखेड़ी",
        "REHWARI": "रेहवारी",
        "MANASA": "मनासा",
    }
    _FARMER_TYPE_OPTIONS = {
        "small": "1",
        "marginal": "1",
        "small/marginal": "1",
        "small marginal": "1",
        "other": "2",
        "others": "2",
    }
    _CATEGORY_OPTIONS = {
        "gen": "Gen",
    }

    async def start(self, payload: StartTaskRequest) -> TaskResponse:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        logs: list[dict] = []
        session_id = str(uuid4())
        log_file_path = self._create_run_log_path(session_id, started_at)
        self._register_log_artifact(session_id, log_file_path)
        sequence = 0

        def add_log(stage: str, message: str, **extra) -> None:
            nonlocal sequence
            sequence += 1
            event = {
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed_ms": int((perf_counter() - started) * 1000),
                "stage": stage,
                "message": message,
                **extra,
            }
            logs.append(event)
            self._append_log_event(log_file_path, event)
            logger.info("automation.stage", session_id=session_id, **event)

        add_log("startup", "Launching Playwright browser", display=settings.display)
        add_log(
            "request",
            "Resolved automation payload",
            **self._payload_debug_fields(payload),
        )

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
            self._install_dialog_handler(page, add_log)

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
                "log_file_path": log_file_path,
                "logs": logs,
            }

            await page.screenshot(path="/tmp/last-run.png", full_page=True)
            add_log(
                "captcha",
                "Waiting for CAPTCHA input from UI",
                screenshot="/tmp/last-run.png",
            )
            await self._capture_page_state(page, "captcha", add_log)

            finished_at = datetime.now(timezone.utc)
            return TaskResponse(
                status="awaiting_captcha",
                message="Browser is ready. Read the CAPTCHA from the live browser and submit it from the UI.",
                url=str(payload.url),
                session_id=session_id,
                title=await page.title(),
                source_file_name=payload.source_file_name,
                source_row_number=payload.source_row_number,
                log_download_id=session_id,
                log_download_path=f"/download-log/{session_id}",
                log_file_name=Path(log_file_path).name,
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
                log_download_id=session_id,
                log_download_path=f"/download-log/{session_id}",
                log_file_name=Path(log_file_path).name,
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
        log_file_path: str | None = session.get("log_file_path")
        sequence = len(logs)

        def add_log(stage: str, message: str, **extra) -> None:
            nonlocal sequence
            sequence += 1
            event = {
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "elapsed_ms": int((perf_counter() - started) * 1000),
                "stage": stage,
                "message": message,
                **extra,
            }
            logs.append(event)
            if log_file_path:
                self._append_log_event(log_file_path, event)
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
            await self._capture_page_state(page, "captcha_submit", add_log)

            await page.locator("#btnLogout").wait_for(state="visible", timeout=10000)
            add_log("login", "Login successful")
            await self._capture_page_state(page, "login", add_log)
            await self._handle_post_login_popup(page, add_log)
            await self._capture_page_state(page, "popup", add_log)

            title = await page.title()
            add_log("inspection", "Collected page title", title=title)
            await self._capture_page_state(page, "inspection", add_log)

            if original_payload.source_file_path:
                batch_summary = await self._process_excel_workbook(
                    page, original_payload, add_log
                )
            else:
                await self._execute_payload_flow(page, original_payload, add_log)

            await page.screenshot(path="/tmp/last-run.png", full_page=True)
            add_log("artifacts", "Saved screenshot", path="/tmp/last-run.png")

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
                log_download_id=payload.session_id if log_file_path else None,
                log_download_path=f"/download-log/{payload.session_id}"
                if log_file_path
                else None,
                log_file_name=Path(log_file_path).name if log_file_path else None,
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
                log_download_id=payload.session_id if log_file_path else None,
                log_download_path=f"/download-log/{payload.session_id}"
                if log_file_path
                else None,
                log_file_name=Path(log_file_path).name if log_file_path else None,
                processed_rows=batch_summary["processed"] if batch_summary else None,
                successful_rows=batch_summary["successful"] if batch_summary else None,
                failed_rows=batch_summary["failed"] if batch_summary else None,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=int((perf_counter() - started) * 1000),
                logs=logs,
            )
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
        await self._capture_page_state(page, "navigation", add_log)

        await page.click("#rdbLoginType_3")
        await page.fill("#tbxUserName", username)
        await page.fill("#tbxPassword", password)
        await self._capture_page_state(page, "login_form", add_log)

        captcha_path = "/tmp/captcha.png"
        await page.locator("#imgCaptcha").screenshot(path=captcha_path)
        add_log("captcha", "Captured CAPTCHA image", path=captcha_path)
        await self._capture_page_state(page, "captcha_capture", add_log)

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
        if action in PlaywrightService._ADD_FARMER_ACTIONS:
            return "login_only"
        if action in {"fill_vitran_form", "vitran"}:
            return "fill_vitran_form"
        if action in {"fill_vasuli_form", "vasuli"}:
            return "fill_vasuli_form"
        raise ValueError(
            f"Unknown action: {action}. Expected 'login_only', 'add_farmer', 'fill_vitran_form', or 'fill_vasuli_form'."
        )

    async def _execute_payload_flow(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        await self._handle_post_login_popup(page, add_log, required=False)
        flow = self._resolve_flow(payload)
        add_farmer = self._should_add_farmer(payload)
        if flow == "login_only" and not add_farmer:
            return

        if add_farmer:
            await self._open_farmer_details_page(page, add_log, add_farmer=True)
            await self._add_new_farmer(page, payload, add_log)
            if flow == "login_only":
                return

        await self._open_farmer_details_page(page, add_log, add_farmer=False)
        await self._search_farmer_by_aadhaar(page, payload, add_log)
        await self._click_vitran_link(page, add_log, timeout=20000)
        await self._choose_transaction_form(page, flow, add_log)

        if flow == "fill_vitran_form":
            await self._fill_vitran_form(page, payload, add_log)
        elif flow == "fill_vasuli_form":
            await self._fill_vasuli_form(page, payload, add_log)

    async def _open_farmer_details_page(
        self, page: Page, add_log, add_farmer: bool = False
    ) -> None:
        await self._handle_post_login_popup(page, add_log, required=False)
        target_url = self._ADD_FARMER_URL if add_farmer else self._VIEW_FARMER_URL
        add_log(
            "navigation",
            "Opening Farmer Details page",
            mode="add" if add_farmer else "view",
            url=target_url,
        )
        await page.goto(target_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("domcontentloaded")
        await self._handle_post_login_popup(page, add_log, required=False)
        if add_farmer:
            await expect(
                page.locator("#ContentPlaceHolder1_tbxFarmarName")
            ).to_be_visible(timeout=10000)
        else:
            await expect(
                page.locator("#ContentPlaceHolder1_tbxSearchname")
            ).to_be_visible(timeout=10000)
        await self._capture_page_state(
            page,
            "navigation",
            add_log,
            mode="add" if add_farmer else "view",
        )

    async def _search_farmer_by_aadhaar(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        aadhaar_number = self._required_value(payload, "aadhaar_number")
        add_log("navigation", "Searching farmer by Aadhaar")
        await page.locator("#ContentPlaceHolder1_tbxSearchname").fill(aadhaar_number)
        search_btn = page.get_by_role("button", name="Search")
        await expect(search_btn).to_be_visible(timeout=10000)
        await search_btn.click()
        await self._wait_for_search_results(page, add_log)
        await self._capture_page_state(
            page,
            "search",
            add_log,
            aadhaar_number=self._mask_value(aadhaar_number),
        )

    async def _wait_for_search_results(self, page: Page, add_log) -> None:
        link_candidates = self._vitran_link_candidates()
        for link_text in link_candidates:
            link = page.locator(f"table a:has-text('{link_text}')").first
            try:
                await link.wait_for(state="visible", timeout=5000)
                add_log("search", "Search results loaded", matched_link_text=link_text)
                return
            except Exception:
                continue

        await self._capture_page_state(page, "search_no_vitran_link", add_log)
        raise RuntimeError(
            "Aadhaar search completed, but no Vitran link appeared in the result table."
        )

    async def _click_vitran_link(
        self,
        page: Page,
        add_log,
        timeout: int = 20000,
    ) -> None:
        await self._click_table_link(
            page,
            self._vitran_link_candidates(),
            add_log,
            timeout=timeout,
        )
        await self._wait_for_transaction_page(page, add_log)

    async def _click_table_link(
        self,
        page: Page,
        link_texts: list[str],
        add_log,
        timeout: int = 15000,
    ) -> None:
        table = page.locator("#ContentPlaceHolder1_gridFarmerdetails")
        await expect(table).to_be_visible(timeout=timeout)
        rows = table.locator("tr")
        await expect(rows.first).to_be_visible(timeout=timeout)

        last_error: Exception | None = None
        for link_text in link_texts:
            link = table.locator(f"a:has-text('{link_text}')").first
            try:
                await link.wait_for(state="visible", timeout=timeout)
                await link.scroll_into_view_if_needed(timeout=3000)
                add_log("table_click", "Located table link", link_text=link_text)
                try:
                    await link.click(force=True, timeout=5000)
                except Exception as click_error:
                    last_error = click_error
                    await link.evaluate("(element) => element.click()")
                add_log("table_click", "Clicked table link", link_text=link_text)
                await self._capture_page_state(
                    page, "table_click", add_log, link_text=link_text
                )
                return
            except Exception as exc:
                last_error = exc

        await self._capture_page_state(
            page,
            "table_click_failed",
            add_log,
            link_texts=link_texts,
            error=str(last_error) if last_error else None,
        )
        raise RuntimeError(
            "No Vitran link found in the search result table. "
            f"Tried: {', '.join(link_texts)}"
        )

    async def _wait_for_transaction_page(self, page: Page, add_log) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        selectors = (
            "#ContentPlaceHolder1_txtdateDR",
            "#ContentPlaceHolder1_txtdr",
            "#ContentPlaceHolder1_txtdaterec",
            "#ContentPlaceHolder1_txtcr",
            "#ContentPlaceHolder1_rblLoantype_0",
            "#ContentPlaceHolder1_rblLoantypeRec_0",
            "input[name='ctl00$ContentPlaceHolder1$rblLoantype']",
            "input[name='ctl00$ContentPlaceHolder1$rblLoantypeRec']",
        )
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=3000)
                add_log("navigation", "Transaction page loaded", selector=selector)
                return
            except Exception:
                continue

        await self._capture_page_state(page, "transaction_page_missing", add_log)
        raise RuntimeError("Clicked Vitran, but the transaction form did not load.")

    async def _choose_transaction_form(
        self, page: Page, flow: str, add_log
    ) -> None:
        if flow == "fill_vitran_form":
            ready_selectors = (
                "#ContentPlaceHolder1_txtdateDR",
                "#ContentPlaceHolder1_txtdr",
            )
            tab_texts = ("वितरण", "Vitran", "Distribution")
        elif flow == "fill_vasuli_form":
            ready_selectors = (
                "#ContentPlaceHolder1_txtdaterec",
                "#ContentPlaceHolder1_txtcr",
            )
            tab_texts = ("वसूली", "Vasuli", "Recovery")
        else:
            return

        if await self._all_attached(page, ready_selectors):
            add_log("form", "Target transaction form is already available", flow=flow)
            return

        for tab_text in tab_texts:
            control = page.locator(
                f"a:has-text('{tab_text}'), button:has-text('{tab_text}'), "
                f"label:has-text('{tab_text}'), input[value='{tab_text}']"
            ).first
            try:
                if await control.count() == 0:
                    continue
                if not await control.is_visible(timeout=500):
                    continue
                await control.click(force=True, timeout=3000)
                await self._wait_for_all_visible(page, ready_selectors, timeout=5000)
                add_log("form", "Selected transaction form", flow=flow, tab_text=tab_text)
                return
            except Exception:
                continue

        await self._capture_page_state(page, "transaction_form_missing", add_log, flow=flow)
        raise RuntimeError(f"Could not open the expected transaction form for {flow}.")

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
        await expect(date_input).to_be_visible(timeout=10000)
        await expect(amount_input).to_be_visible(timeout=10000)
        await self._check_radio(loan_type_option)
        await self._check_radio(loan_mode_option)
        await self._fill_input(date_input, payload.date or "")
        await self._fill_input(amount_input, payload.amount or "")
        add_log(
            "form",
            "Vitran form filled",
            loan_type=payload.loan_type,
            loan_mode=payload.loan_mode,
            date=payload.date,
            amount=payload.amount,
        )
        save_button = page.locator("#ContentPlaceHolder1_btndr")
        await save_button.wait_for(state="attached", timeout=10000)
        try:
            await save_button.click(force=True, timeout=5000)
        except Exception:
            await save_button.evaluate("(element) => element.click()")
        add_log(
            "form",
            "Vitran save button clicked",
            selector="#ContentPlaceHolder1_btndr",
        )
        await self._capture_page_state(page, "vitran_form", add_log)
        await page.wait_for_load_state("networkidle")

    async def _fill_vasuli_form(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        self._require_fields(payload, ["loan_type", "date", "amount"])
        season = payload.season if payload.season is not None else payload.loan_mode
        if season is None:
            raise ValueError(
                "Missing required field for action: season (or loan mode fallback)"
            )
        loan_type_option = page.locator(
            f"#ContentPlaceHolder1_rblLoantypeRec_{payload.loan_type}"
        )
        season_option = page.locator(
            f"#ContentPlaceHolder1_rblseasonrec_{season}"
        )
        date_input = page.locator("#ContentPlaceHolder1_txtdaterec")
        amount_input = page.locator("#ContentPlaceHolder1_txtcr")
        await expect(date_input).to_be_visible(timeout=10000)
        await expect(amount_input).to_be_visible(timeout=10000)
        await self._check_radio(loan_type_option)
        await self._check_radio(season_option)
        await self._fill_input(date_input, payload.date or "")
        await self._fill_input(amount_input, payload.amount or "")
        add_log(
            "form",
            "Vasuli form filled",
            loan_type=payload.loan_type,
            season=season,
            date=payload.date,
            amount=payload.amount,
        )
        save_button = page.locator("#ContentPlaceHolder1_Btncr")
        await save_button.wait_for(state="attached", timeout=10000)
        try:
            await save_button.click(force=True, timeout=5000)
        except Exception:
            await save_button.evaluate("(element) => element.click()")
        add_log(
            "form",
            "Vasuli save button clicked",
            selector="#ContentPlaceHolder1_Btncr",
        )
        await self._capture_page_state(page, "vasuli_form", add_log)
        await page.wait_for_load_state("networkidle")



    async def _add_new_farmer(
        self, page: Page, payload: StartTaskRequest, add_log
    ) -> None:
        self._require_fields(
            payload,
            [
                "farmer_name",
                "guardian_name",
                "gender",
                "village_name",
                "category",
                "savings_account_number",
                "mobile_number",
                "aadhaar_number",
                "erp_admission_number",
                "farmer_type",
            ],
        )

        await page.locator("#ContentPlaceHolder1_tbxFarmarName").fill(
            self._required_value(payload, "farmer_name")
        )
        await page.locator("#ContentPlaceHolder1_tbxFFatherName").fill(
            self._required_value(payload, "guardian_name")
        )
        await page.locator("#ContentPlaceHolder1_ddlgender").select_option(
            self._required_value(payload, "gender")
        )
        await self._select_option_candidates(
            page.locator("#ContentPlaceHolder1_ddlvillagename"),
            self._option_candidates(self._resolve_village_option(payload.village_name)),
        )
        await self._select_option_candidates(
            page.locator("#ContentPlaceHolder1_ddlfarmercat"),
            self._option_candidates(self._resolve_farmer_type_option(payload.farmer_type)),
        )

        CATEGORY_VALUE_MAP = {
            "GEN": "1",
            "GENERAL": "1",
            "OBC": "2",
            "SC": "3",
            "ST": "4",
        }
        category = self._required_value(payload, "category")
        value = CATEGORY_VALUE_MAP.get(category.upper())

        if not value:
            raise RuntimeError(f"Invalid category: {category}")

        await self._select_option_candidates(
            page.locator("#ContentPlaceHolder1_ddlcatgory"),
            [value, *self._option_candidates(category)],
        )

        await page.locator("#ContentPlaceHolder1_tbxsavingaccountno").fill(
            self._required_value(payload, "savings_account_number")
        )
        await page.locator("#ContentPlaceHolder1_tbxMobileNo").fill(
            self._required_value(payload, "mobile_number")
        )
        await page.locator("#ContentPlaceHolder1_tbxAadharno").fill(
            self._required_value(payload, "aadhaar_number")
        )
        await page.locator("#ContentPlaceHolder1_tbxAdmissionno").fill(
            self._required_value(payload, "erp_admission_number")
        )
        await page.locator("#ContentPlaceHolder1_btnSubmit").click()

        add_log(
            "form",
            "Kisan form filled",
            farmer_name=payload.farmer_name,
            guardian_name=payload.guardian_name,
            gender=payload.gender,
            village_name=payload.village_name,
            farmer_type=payload.farmer_type,
            category=payload.category,
            savings_account_number=payload.savings_account_number,
            mobile_number=payload.mobile_number,
            aadhaar_number=payload.aadhaar_number,
            erp_admission_number=payload.erp_admission_number,
        )
        await self._capture_page_state(page, "add_farmer_form", add_log)
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
            add_log(
                "excel_debug",
                "Resolved workbook row payload",
                row_number=row_index + 2,
                existing_remark=existing_remark,
                **self._payload_debug_fields(row_payload),
            )

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
            await page.goto(self._DASHBOARD_URL, wait_until="domcontentloaded")
            await self._handle_post_login_popup(page, add_log, required=False)


            try:
                add_log(
                    "excel",
                    "Processing workbook row",
                    row_number=row_index + 2,
                    farmer_name=farmer_name,
                    transaction_type=row_payload.transaction_type,
                )
                await self._capture_page_state(
                    page,
                    "excel_row_start",
                    add_log,
                    row_number=row_index + 2,
                )
                await self._execute_payload_flow(page, row_payload, add_log)
                self._excel_mapper.update_status_columns(
                    dataframe,
                    normalized_columns,
                    row_index=row_index,
                    farmer_remark="DONE",
                    transaction_remark=self._excel_mapper.build_success_remark(),
                )
                add_log(
                    "excel",
                    "Workbook row succeeded",
                    row_number=row_index + 2,
                    farmer_name=farmer_name,
                )
                await self._capture_page_state(
                    page,
                    "excel_row_success",
                    add_log,
                    row_number=row_index + 2,
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
                await self._capture_page_state(
                    page,
                    "excel_row_failed",
                    add_log,
                    row_number=row_index + 2,
                    error=str(exc)[:500],
                )
            finally:
                processed += 1
                await self._excel_mapper.save_workbook(dataframe, workbook_path)
                add_log(
                    "excel_debug",
                    "Workbook checkpoint saved",
                    row_number=row_index + 2,
                    processed=processed,
                    successful=successful,
                    failed=failed,
                )

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

    @classmethod
    def _require_fields(cls, payload: StartTaskRequest, fields: list[str]) -> None:
        missing = [field for field in fields if getattr(payload, field) in (None, "")]
        if missing:
            raise ValueError(
                "Missing required fields for action: "
                f"{', '.join(cls._excel_mapper.field_labels(missing))}"
            )

    @classmethod
    def _should_add_farmer(cls, payload: StartTaskRequest) -> bool:
        action = (payload.action or "").strip().lower()
        return payload.add_farmer or action in cls._ADD_FARMER_ACTIONS

    @classmethod
    def _required_value(cls, payload: StartTaskRequest, field: str) -> str:
        value = getattr(payload, field)
        if value in (None, ""):
            raise ValueError(
                "Missing required field for action: "
                f"{cls._excel_mapper.field_label(field)}"
            )
        return str(value).strip()

    @classmethod
    def _resolve_village_option(cls, value: str | None) -> str:
        if value is None:
            return ""
        cleaned = value.strip()
        return cls._VILLAGE_OPTIONS.get(cleaned.upper(), cleaned)

    @classmethod
    def _resolve_farmer_type_option(cls, value: str | None) -> str:
        if value is None:
            return ""

        cleaned = value.strip()
        normalized = cls._normalize_option_key(cleaned)
        return cls._FARMER_TYPE_OPTIONS.get(normalized, cleaned)

    @classmethod
    def _resolve_category_option(cls, value: str | None) -> str:
        if value is None:
            return ""
        cleaned = value.strip()
        normalized = (cleaned)
        
        return cls._CATEGORY_OPTIONS.get(normalized, cleaned.capitalize())

    @staticmethod
    def _option_candidates(value: str | None) -> list[str]:
        if value is None:
            return []
        cleaned = str(value).strip()
        if not cleaned:
            return []

        candidates = [
            cleaned,
            cleaned.upper(),
            cleaned.lower(),
            cleaned.capitalize(),
            cleaned.title(),
        ]
        return list(dict.fromkeys(candidates))

    @staticmethod
    async def _select_option_candidates(locator, candidates: list[str]) -> str:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                await locator.select_option(candidate, timeout=2000)
                return candidate
            except Exception as exc:
                last_error = exc

        candidate_list = ", ".join(repr(candidate) for candidate in candidates)
        raise RuntimeError(
            f"Could not select any option from [{candidate_list}]: {last_error}"
        )

    @staticmethod
    def _vitran_link_candidates() -> list[str]:
        return [
            "वितरण",
            "वितरण/वसूली",
            "कृषक के वितरण/वसूली की जानकारी",
            "Vitran",
            "Distribution",
        ]

    @staticmethod
    async def _is_visible(locator, timeout: int = 500) -> bool:
        try:
            return await locator.count() > 0 and await locator.is_visible(
                timeout=timeout
            )
        except Exception:
            return False

    @classmethod
    async def _all_visible(
        cls, page: Page, selectors: tuple[str, ...], timeout: int = 500
    ) -> bool:
        for selector in selectors:
            if not await cls._is_visible(page.locator(selector).first, timeout=timeout):
                return False
        return True

    @staticmethod
    async def _wait_for_all_visible(
        page: Page, selectors: tuple[str, ...], timeout: int = 5000
    ) -> None:
        for selector in selectors:
            await page.locator(selector).first.wait_for(
                state="visible", timeout=timeout
            )

    @staticmethod
    async def _all_attached(page: Page, selectors: tuple[str, ...]) -> bool:
        for selector in selectors:
            if await page.locator(selector).count() == 0:
                return False
        return True

    @staticmethod
    async def _check_radio(locator) -> None:
        await locator.wait_for(state="attached", timeout=10000)
        try:
            await locator.check(force=True, timeout=3000)
            return
        except Exception:
            pass

        await locator.evaluate(
            """(element) => {
                element.checked = true;
                element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }"""
        )

    @staticmethod
    async def _fill_input(locator, value: str) -> None:
        await locator.wait_for(state="attached", timeout=10000)
        try:
            await locator.fill(value, timeout=3000)
            return
        except Exception:
            pass

        await locator.evaluate(
            """(element, value) => {
                element.value = value;
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.dispatchEvent(new Event('blur', { bubbles: true }));
            }""",
            value,
        )

    @staticmethod
    def _normalize_option_key(value: str) -> str:
        normalized = " ".join(value.lower().replace("_", " ").split())
        return normalized.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")

    def _install_dialog_handler(self, page: Page, add_log) -> None:
        async def accept_dialog(dialog) -> None:
            try:
                dialog_type = dialog.type
                message = dialog.message
                await dialog.accept()
                add_log(
                    "popup",
                    "Accepted browser dialog",
                    dialog_type=dialog_type,
                    dialog_message=message,
                )
            except Exception as exc:
                add_log("popup", "Failed to accept browser dialog", error=str(exc))

        def schedule_accept(dialog) -> None:
            asyncio.create_task(accept_dialog(dialog))

        page.on("dialog", schedule_accept)

    async def _handle_post_login_popup(
        self, page: Page, add_log, *, required: bool = True
    ) -> bool:
        popup_selectors = (
            "button:has-text('Continue')",
            "button:has-text('Yes')",
            "button:has-text('Close')",
            "button:has-text('OK')",
            "button:has-text('Ok')",
            "a:has-text('Continue')",
            "a:has-text('Yes')",
            "a:has-text('Close')",
            "a:has-text('OK')",
            "input[value='Continue']",
            "input[value='Yes']",
            "input[value='Close']",
            "input[value='OK']",
            "[aria-label='Close']",
            ".ui-dialog-titlebar-close",
            ".modal button.close",
            ".modal .btn-close",
            ".popup-close",
            "#btnClose",
            "#btnOk",
        )

        dismissed = False
        for _ in range(2):
            clicked = False
            for selector in popup_selectors:
                locator = page.locator(selector).first
                try:
                    if await locator.count() == 0:
                        continue
                    if not await locator.is_visible(timeout=100):
                        continue
                    await locator.click(force=True, timeout=1000)
                    dismissed = True
                    clicked = True
                    add_log(
                        "popup",
                        "Dismissed post-login popup",
                        selector=selector,
                    )
                    await page.wait_for_timeout(300)
                    break
                except Exception:
                    continue
            if not clicked:
                break

        dialog = page.get_by_role("dialog").first
        try:
            if await dialog.count() > 0 and await dialog.is_visible(timeout=100):
                for button_text in ("Continue", "Yes", "OK", "Ok", "Close"):
                    close_button = (
                        dialog.get_by_role("button").filter(has_text=button_text).first
                    )
                    try:
                        if await close_button.count() == 0:
                            continue
                        if not await close_button.is_visible(timeout=100):
                            continue
                        await close_button.click(force=True, timeout=1000)
                        add_log(
                            "popup",
                            "Dismissed dialog popup",
                            selector="role=dialog",
                            button_text=button_text,
                        )
                        await page.wait_for_timeout(300)
                        return True
                    except Exception:
                        continue
        except Exception:
            pass

        if dismissed:
            return True

        if required:
            add_log("popup", "No post-login popup detected")
        return False

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

    async def _capture_page_state(
        self,
        page: Page,
        stage: str,
        add_log,
        **extra,
    ) -> None:
        snapshot: dict[str, object] = {**extra}
        try:
            snapshot["url"] = page.url
            snapshot["title"] = await page.title()
            snapshot["is_closed"] = page.is_closed()
            snapshot["viewport_size"] = page.viewport_size
            snapshot["locator_counts"] = await self._locator_counts(page)
        except Exception as exc:
            snapshot["snapshot_error"] = str(exc)

        add_log(stage, "Captured page debug state", debug=True, **snapshot)

    async def _locator_counts(self, page: Page) -> dict[str, int | str]:
        selectors = {
            "logout_button": "#btnLogout",
            "captcha_input": "#txtCaptchaInput",
            "captcha_image": "#imgCaptcha",
            "submit_buttons": "input[type=submit], button[type=submit]",
            "tables": "table",
            "farmer_name_input": "#ContentPlaceHolder1_tbxFarmarName",
            "aadhaar_input": "#ContentPlaceHolder1_tbxAadharno",
            "search_input": "#ContentPlaceHolder1_tbxSearchname",
            "vitran_date_input": "#ContentPlaceHolder1_txtdateDR",
            "vasuli_date_input": "#ContentPlaceHolder1_txtdaterec",
            "amount_inputs": "#ContentPlaceHolder1_txtdr, #ContentPlaceHolder1_txtcr",
        }
        counts: dict[str, int | str] = {}
        for name, selector in selectors.items():
            try:
                counts[name] = await page.locator(selector).count()
            except Exception as exc:
                counts[name] = f"error: {exc}"
        return counts

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

    @classmethod
    def _register_log_artifact(cls, session_id: str, file_path: str) -> None:
        cls._log_artifacts[session_id] = {
            "path": file_path,
            "filename": Path(file_path).name,
        }

    @classmethod
    def get_log_artifact(cls, artifact_id: str) -> dict[str, str] | None:
        return cls._log_artifacts.get(artifact_id)

    @staticmethod
    def _create_run_log_path(session_id: str, started_at: datetime) -> str:
        log_dir = (
            Path(settings.automation_log_dir)
            if settings.automation_log_dir
            else Path(gettempdir()) / "playwright-visible-logs"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = started_at.strftime("%Y%m%d_%H%M%S")
        return str(log_dir / f"automation_{timestamp}_{session_id}.jsonl")

    @staticmethod
    def _append_log_event(file_path: str, event: dict) -> None:
        try:
            with open(file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, default=str))
                handle.write("\n")
        except OSError as exc:
            logger.warning(
                "automation.log_write_failed",
                log_file_path=file_path,
                error=str(exc),
            )

    @staticmethod
    def _payload_debug_fields(payload: StartTaskRequest) -> dict[str, object]:
        return {
            "action": payload.action,
            "transaction_type": payload.transaction_type,
            "add_farmer": payload.add_farmer,
            "source_file_name": payload.source_file_name,
            "source_row_number": payload.source_row_number,
            "farmer_name": payload.farmer_name,
            "guardian_name": payload.guardian_name,
            "gender": payload.gender,
            "village_name": payload.village_name,
            "farmer_type": payload.farmer_type,
            "category": payload.category,
            "savings_account_number": PlaywrightService._mask_value(
                payload.savings_account_number
            ),
            "mobile_number": PlaywrightService._mask_value(payload.mobile_number),
            "aadhaar_number": PlaywrightService._mask_value(payload.aadhaar_number),
            "erp_admission_number": PlaywrightService._mask_value(
                payload.erp_admission_number
            ),
            "loan_type": payload.loan_type,
            "loan_mode": payload.loan_mode,
            "season": payload.season,
            "date": payload.date,
            "amount": payload.amount,
        }

    @staticmethod
    def _mask_value(value: str | None, visible_digits: int = 4) -> str | None:
        if not value:
            return value
        text = str(value)
        if len(text) <= visible_digits:
            return "*" * len(text)
        return f"{'*' * (len(text) - visible_digits)}{text[-visible_digits:]}"
