"""
CSV Parser Service
==================
Parses an uploaded KPI CSV file into structured KPIRecord rows.

Expected CSV format (flexible — smart column detection):
  employee_email | metric_name | metric_value | period

The parser uses alias matching so column names like "email", "emp_email",
"kpi", "score", "quarter" etc. are all handled automatically.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Known aliases for each standard column name
COLUMN_ALIASES: dict[str, list[str]] = {
    "employee_email": [
        "email", "employee_email", "emp_email", "user_email",
        "employee email", "user email",
    ],
    "metric_name": [
        "metric", "metric_name", "kpi", "kpi_name", "indicator",
        "measure", "measurement", "metric name", "kpi name",
    ],
    "metric_value": [
        "value", "metric_value", "score", "result", "amount",
        "actual", "achieved", "metric value",
    ],
    "period": [
        "period", "quarter", "month", "timeframe", "cycle", "term",
    ],
}


def _detect_column(headers: list[str], aliases: list[str]) -> str | None:
    """
    Find the matching CSV header using known aliases (case-insensitive).
    Returns the original header string or None if not found.
    """
    headers_lower = [h.lower().strip() for h in headers]
    for alias in aliases:
        if alias.lower() in headers_lower:
            return headers[headers_lower.index(alias.lower())]
    return None


def parse_kpi_csv(file_content: bytes, dataset_id: str) -> list[dict[str, Any]]:
    """
    Parse raw CSV bytes into a list of dicts ready for KPIRecord insertion.

    Handles:
    - UTF-8 with/without BOM (Excel exports)
    - Non-numeric metric values (stored as metric_text)
    - Missing / unmapped columns (graceful fallback)
    - Empty rows are skipped automatically

    Parameters
    ----------
    file_content : bytes
        Raw bytes of the uploaded CSV file.
    dataset_id : str
        UUID of the parent KPIDataset row.

    Returns
    -------
    list[dict]
        Each dict has keys:
        id, dataset_id, employee_email, metric_name,
        metric_value, metric_text, period, raw_row
    """
    # Decode — utf-8-sig strips Excel BOM
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    headers: list[str] = list(reader.fieldnames or [])

    if not headers:
        raise ValueError("CSV has no headers. Please provide a header row.")

    # Detect standard columns dynamically
    col_email  = _detect_column(headers, COLUMN_ALIASES["employee_email"])
    col_metric = _detect_column(headers, COLUMN_ALIASES["metric_name"])
    col_value  = _detect_column(headers, COLUMN_ALIASES["metric_value"])
    col_period = _detect_column(headers, COLUMN_ALIASES["period"])

    logger.info(
        "CSV column mapping — email:%s, metric:%s, value:%s, period:%s",
        col_email, col_metric, col_value, col_period,
    )

    records: list[dict[str, Any]] = []

    for row in reader:
        # Skip completely empty rows
        if not any(v.strip() for v in row.values() if v):
            continue

        raw = json.dumps(dict(row), ensure_ascii=False)

        email      = row.get(col_email, "").strip() if col_email else None
        metric     = row.get(col_metric, "").strip() if col_metric else "unknown_metric"
        value_str  = row.get(col_value, "").strip() if col_value else ""
        period     = row.get(col_period, "").strip() if col_period else None

        # Try to parse as float; fall back to text
        try:
            metric_value: float | None = float(value_str) if value_str else None
            metric_text: str | None = None
        except ValueError:
            metric_value = None
            metric_text = value_str or None

        records.append({
            "id":             str(uuid.uuid4()),
            "dataset_id":     dataset_id,
            "employee_email": email or None,
            "metric_name":    metric,
            "metric_value":   metric_value,
            "metric_text":    metric_text,
            "period":         period or None,
            "raw_row":        raw,
        })

    if not records:
        raise ValueError("CSV parsed but contains no data rows.")

    logger.info("Parsed %d KPI records from CSV (dataset: %s)", len(records), dataset_id)
    return records
