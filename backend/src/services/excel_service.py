from __future__ import annotations

import asyncio
from datetime import datetime
from math import isnan
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pandas as pd

from src.schemas.task import StartTaskRequest


class ExcelTaskMapper:
    _COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
        "sr": ("sr",),
        "add_farmer": ("add farmer", "add_farmer", "add kisan", "add_kisan"),
        "farmer_name": ("कृषक का नाम", "farmer name"),
        "guardian_name": ("पिता/पति का नाम", "father/husband name"),
        "gender": ("महिला/पुरुष", "gender"),
        "tehsil_name": ("तहसील का नाम", "tehsil"),
        "village_name": ("ग्राम का नाम", "village"),
        "farmer_type": ("कृषक प्रकार", "farmer type"),
        "category": ("वर्ग", "category"),
        "savings_account_number": (
            "बचत खाता क्रमांक",
            "saving account number",
            "savings account number",
        ),
        "mobile_number": ("मोबाइल नंबर", "mobile number"),
        "aadhaar_number": ("आधार नंबर", "aadhaar number"),
        "erp_admission_number": (
            "erp (एडमिशन नंबर)",
            "erp",
            "admission number",
        ),
        "transaction_type": (
            "transaction type",
            "trasection",
            "transaction",
            "unnamed: 16",
        ),
        "loan_type": ("ऋण प्रकार", "क्रण प्रकार", "loan type"),
        "loan_mode": ("ऋण", "क्रण", "loan mode"),
        "season": ("season", "season index"),
        "amount": ("amount",),
        "date": ("date",),
        "farmer_added_remark": ("farmer added remark", "farmer remark"),
        "transaction_remark": ("trasection remark", "transaction remark"),
    }

    _TEXT_FIELDS = {
        "sr",
        "farmer_name",
        "guardian_name",
        "gender",
        "tehsil_name",
        "village_name",
        "farmer_type",
        "category",
        "savings_account_number",
        "mobile_number",
        "aadhaar_number",
        "erp_admission_number",
        "amount",
        "date",
        "farmer_added_remark",
        "transaction_remark",
    }

    _REQUIRED_STATUS_COLUMNS = {
        "farmer_added_remark": "Farmer Added Remark",
        "transaction_remark": "Trasection Remark",
    }

    async def prepare_request_from_excel(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        base_payload: StartTaskRequest,
    ) -> StartTaskRequest:
        workbook_path = await self._persist_upload(file_bytes, filename)
        dataframe = await self.load_workbook(workbook_path)
        normalized_columns = self.normalized_columns(dataframe)
        self.ensure_status_columns(dataframe, normalized_columns)
        normalized_columns = self.normalized_columns(dataframe)

        first_row_index, first_row = self.first_actionable_row(dataframe)
        await self.save_workbook(dataframe, workbook_path)

        return self.build_request_from_row(
            base_payload=base_payload,
            normalized_columns=normalized_columns,
            row=first_row,
            row_index=first_row_index,
            filename=filename,
            workbook_path=workbook_path,
        )

    async def load_workbook(self, workbook_path: str) -> pd.DataFrame:
        return await asyncio.to_thread(pd.read_excel, workbook_path)

    async def save_workbook(self, dataframe: pd.DataFrame, workbook_path: str) -> None:
        await asyncio.to_thread(dataframe.to_excel, workbook_path, index=False)

    def build_request_from_row(
        self,
        *,
        base_payload: StartTaskRequest,
        normalized_columns: dict[str, str],
        row: pd.Series,
        row_index: int,
        filename: str,
        workbook_path: str,
    ) -> StartTaskRequest:
        row_data = self.extract_row(normalized_columns, row)
        return base_payload.model_copy(
            update={
                "sr": row_data.get("sr") or base_payload.sr,
                "add_farmer": self.to_optional_bool(row_data.get("add_farmer"))
                if row_data.get("add_farmer") is not None
                else base_payload.add_farmer,
                "farmer_name": row_data.get("farmer_name") or base_payload.farmer_name,
                "guardian_name": row_data.get("guardian_name")
                or base_payload.guardian_name,
                "gender": self.normalize_title_value(row_data.get("gender"))
                or self.normalize_title_value(base_payload.gender),
                "tehsil_name": row_data.get("tehsil_name") or base_payload.tehsil_name,
                "village_name": row_data.get("village_name") or base_payload.village_name,
                "farmer_type": row_data.get("farmer_type") or base_payload.farmer_type,
                "category": row_data.get("category") or base_payload.category,
                "savings_account_number": row_data.get("savings_account_number")
                or base_payload.savings_account_number,
                "mobile_number": row_data.get("mobile_number")
                or base_payload.mobile_number,
                "aadhaar_number": row_data.get("aadhaar_number")
                or base_payload.aadhaar_number,
                "erp_admission_number": row_data.get("erp_admission_number")
                or base_payload.erp_admission_number,
                "transaction_type": self.normalize_transaction_type(
                    row_data.get("transaction_type")
                )
                or base_payload.transaction_type,
                "loan_type": self.to_optional_index(row_data.get("loan_type"))
                if row_data.get("loan_type") is not None
                else base_payload.loan_type,
                "loan_mode": self.to_optional_index(row_data.get("loan_mode"))
                if row_data.get("loan_mode") is not None
                else base_payload.loan_mode,
                "season": self.to_optional_index(row_data.get("season"))
                if row_data.get("season") is not None
                else base_payload.season,
                "amount": self.to_optional_string(row_data.get("amount"))
                or base_payload.amount,
                "date": self.to_excel_date_string(row_data.get("date"))
                or base_payload.date,
                "farmer_added_remark": row_data.get("farmer_added_remark")
                or base_payload.farmer_added_remark,
                "transaction_remark": row_data.get("transaction_remark")
                or base_payload.transaction_remark,
                "source_file_name": filename,
                "source_file_path": workbook_path,
                "source_row_number": row_index + 2,
            }
        )

    def ensure_status_columns(
        self,
        dataframe: pd.DataFrame,
        normalized_columns: dict[str, str] | None = None,
    ) -> None:
        normalized_columns = normalized_columns or self.normalized_columns(dataframe)
        for field_name, fallback_name in self._REQUIRED_STATUS_COLUMNS.items():
            if self.resolve_column_name(
                normalized_columns, self._COLUMN_ALIASES[field_name]
            ):
                continue
            dataframe[fallback_name] = ""

    def first_actionable_row(self, dataframe: pd.DataFrame) -> tuple[int, pd.Series]:
        for row_index, row in dataframe.iterrows():
            if self.row_has_values(row):
                return row_index, row
        raise ValueError("Uploaded Excel file does not contain any usable rows.")

    def row_has_values(self, row: pd.Series) -> bool:
        return row.notna().any()

    def extract_row(
        self,
        normalized_columns: dict[str, str],
        row: pd.Series,
    ) -> dict[str, str]:
        extracted: dict[str, str] = {}
        for target_field, aliases in self._COLUMN_ALIASES.items():
            original_column = self.resolve_column_name(normalized_columns, aliases)
            if original_column is None:
                continue
            value = row.get(original_column)
            if self.is_empty(value):
                continue
            if target_field in self._TEXT_FIELDS:
                text_value = self.to_optional_string(value)
                if text_value is not None:
                    extracted[target_field] = text_value
            else:
                extracted[target_field] = str(value)
        return extracted

    def resolve_column_name(
        self,
        normalized_columns: dict[str, str],
        aliases: tuple[str, ...],
    ) -> str | None:
        for alias in aliases:
            for normalized_alias in self.normalized_name_candidates(alias):
                column_name = normalized_columns.get(normalized_alias)
                if column_name is not None:
                    return column_name
        return None

    def update_status_columns(
        self,
        dataframe: pd.DataFrame,
        normalized_columns: dict[str, str],
        *,
        row_index: int,
        farmer_remark: str,
        transaction_remark: str,
    ) -> None:
        farmer_column = self.resolve_column_name(
            normalized_columns, self._COLUMN_ALIASES["farmer_added_remark"]
        )
        transaction_column = self.resolve_column_name(
            normalized_columns, self._COLUMN_ALIASES["transaction_remark"]
        )
        if farmer_column is None or transaction_column is None:
            raise ValueError("Workbook status columns are not available for updates.")
        dataframe.at[row_index, farmer_column] = farmer_remark
        dataframe.at[row_index, transaction_column] = transaction_remark

    def workbook_result_name(
        self,
        source_file_name: str | None,
        generated_at: datetime | None = None,
    ) -> str | None:
        if not source_file_name:
            return None
        source_path = Path(source_file_name)
        suffix = source_path.suffix or ".xlsx"
        timestamp = (generated_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
        return f"{source_path.stem}_processed_{timestamp}{suffix}"

    @staticmethod
    def normalized_columns(dataframe: pd.DataFrame) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for column in dataframe.columns:
            original = str(column)
            for normalized_name in ExcelTaskMapper.normalized_name_candidates(original):
                normalized[normalized_name] = original
        return normalized

    @staticmethod
    def normalize_column_name(value: str) -> str:
        return " ".join(
            value.replace("\n", " ").replace("_", " ").split()
        ).strip().lower()

    @classmethod
    def normalized_name_candidates(cls, value: str) -> set[str]:
        candidates = {cls.normalize_column_name(value)}
        repaired = cls.repair_mojibake(value)
        if repaired != value:
            candidates.add(cls.normalize_column_name(repaired))
        return candidates

    @staticmethod
    def repair_mojibake(value: str) -> str:
        try:
            repaired = value.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return value
        return repaired

    @staticmethod
    def is_empty(value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and isnan(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    @staticmethod
    def to_optional_string(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        return text or None

    @staticmethod
    def to_excel_date_string(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.strftime("%d/%m/%Y")
        text = str(value).strip()
        return text or None

    @staticmethod
    def normalize_transaction_type(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower().replace(" ", "_")
        if normalized in {"vitran", "fill_vitran_form"}:
            return "vitran"
        if normalized in {"vasuli", "fill_vasuli_form"}:
            return "vasuli"
        if normalized in {"login_only", "login"}:
            return "login_only"
        return normalized or None

    @staticmethod
    def normalize_title_value(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized.capitalize() if normalized else None

    @staticmethod
    def to_optional_index(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)

        cleaned = str(value).strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            return int(cleaned)
        try:
            return int(float(cleaned))
        except ValueError:
            pass

        direct_map = {
            "cash": 0,
            "नकद": 0,
            "vastu": 1,
            "वस्तु": 1,
        }
        mapped_value = direct_map.get(cleaned.lower())
        if mapped_value is not None:
            return mapped_value

        raise ValueError(f"Expected a numeric option index but received '{cleaned}'.")

    @staticmethod
    def to_optional_bool(value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        if isinstance(value, float):
            return int(value) == 1

        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        if cleaned in {"1", "true", "yes", "y", "add", "add_farmer"}:
            return True
        if cleaned in {"0", "false", "no", "n", "skip"}:
            return False

        raise ValueError(
            f"Expected add_farmer to be 1/0 or true/false but received '{value}'."
        )

    @staticmethod
    def build_success_remark() -> str:
        return f"Successfully added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    async def _persist_upload(self, file_bytes: bytes, filename: str) -> str:
        uploads_dir = Path(gettempdir()) / "playwright-visible-uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        target_path = uploads_dir / f"{uuid4()}_{Path(filename).name}"
        await asyncio.to_thread(target_path.write_bytes, file_bytes)
        return str(target_path)
