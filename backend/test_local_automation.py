from src.schemas.task import StartTaskRequest, SubmitCaptchaRequest
from src.services.playwright_service import PlaywrightService
from src.utils.logger import configure_logging

import asyncio
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def prompt_int(label: str) -> int | None:
    value = input(label).strip()
    return int(value) if value else None


async def main() -> None:
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))

    url = input("URL: ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    transaction_type = (
        input(
            "Transaction type [login_only/vitran/vasuli] (default: login_only): "
        ).strip()
        or "login_only"
    )

    loan_type = None
    loan_mode = None
    season = None
    date = None
    amount = None

    if transaction_type == "vitran":
        loan_type = prompt_int("Loan type index: ")
        loan_mode = prompt_int("Loan mode index: ")
        date = input("Date (DD/MM/YYYY): ").strip()
        amount = input("Amount: ").strip()
    elif transaction_type == "vasuli":
        loan_type = prompt_int("Loan type index: ")
        season = prompt_int("Season index: ")
        date = input("Date (DD/MM/YYYY): ").strip()
        amount = input("Amount: ").strip()

    service = PlaywrightService()

    start_payload = StartTaskRequest(
        url=url,
        username=username,
        password=password,
        transaction_type=transaction_type,
        loan_type=loan_type,
        loan_mode=loan_mode,
        season=season,
        date=date,
        amount=amount,
    )

    start_response = await service.start(start_payload)
    print("\nStart response:")
    print(json.dumps(start_response.model_dump(mode="json"), indent=2, default=str))

    if start_response.status != "awaiting_captcha" or not start_response.session_id:
        return

    print(
        "\nRead the CAPTCHA from the visible browser window or saved screenshot, then enter it below."
    )
    captcha_text = input("CAPTCHA: ").strip()

    submit_response = await service.submit_captcha(
        SubmitCaptchaRequest(
            session_id=start_response.session_id,
            captcha_text=captcha_text,
        )
    )

    print("\nFinal response:")
    print(json.dumps(submit_response.model_dump(mode="json"), indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
