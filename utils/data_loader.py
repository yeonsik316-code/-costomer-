from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "샘플데이터"

SALES_PATTERNS = ("sales",)
CUSTOMER_PATTERNS = ("customer",)
ACTIVITY_PATTERNS = ("activity",)

SALES_DATE_COLS = ["수주일", "납품일"]
CUSTOMER_DATE_COLS = ["첫거래일"]
ACTIVITY_DATE_COLS = ["활동일"]


def _find_data_file(patterns: tuple[str, ...]) -> Path | None:
    if not DATA_DIR.exists():
        return None

    candidates: list[Path] = []
    for path in DATA_DIR.iterdir():
        if not path.is_file():
            continue
        name_lower = path.stem.lower()
        if not any(p in name_lower for p in patterns):
            continue
        if path.suffix.lower() not in (".csv", ".xlsx", ".xls"):
            continue
        candidates.append(path)

    if not candidates:
        return None

    def sort_key(p: Path) -> tuple[int, str]:
        ext_priority = {".csv": 0, ".xlsx": 1, ".xls": 2}
        return (ext_priority.get(p.suffix.lower(), 99), p.name)

    return sorted(candidates, key=sort_key)[0]


def _read_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.read_excel(path, engine="openpyxl")


def _parse_dates(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _normalize_customer_name(name: str) -> str:
    if pd.isna(name):
        return ""
    return str(name).strip()


@st.cache_data
def load_all_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sales_path = _find_data_file(SALES_PATTERNS)
    customer_path = _find_data_file(CUSTOMER_PATTERNS)
    activity_path = _find_data_file(ACTIVITY_PATTERNS)

    if sales_path is None:
        raise FileNotFoundError(f"매출 데이터 파일을 찾을 수 없습니다: {DATA_DIR}")
    if customer_path is None:
        raise FileNotFoundError(f"고객 데이터 파일을 찾을 수 없습니다: {DATA_DIR}")
    if activity_path is None:
        raise FileNotFoundError(f"활동 데이터 파일을 찾을 수 없습니다: {DATA_DIR}")

    sales = _parse_dates(_read_file(sales_path), SALES_DATE_COLS)
    customers = _parse_dates(_read_file(customer_path), CUSTOMER_DATE_COLS)
    activities = _parse_dates(_read_file(activity_path), ACTIVITY_DATE_COLS)

    for df in (sales, customers, activities):
        if "거래처명" in df.columns:
            df["거래처명"] = df["거래처명"].apply(_normalize_customer_name)

    return sales, customers, activities
