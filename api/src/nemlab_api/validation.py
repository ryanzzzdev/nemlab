"""Request field types matching the Java validators' strictness.

``LocalDate.parse`` accepts only ``YYYY-MM-DD``; pydantic and
``date.fromisoformat`` also take basic ``YYYYMMDD`` and week dates, so the
string shape is checked before conversion. Rejections surface as
``RequestValidationError`` → ``INVALID_REQUEST`` like a Java parse failure.
"""

import re
from datetime import date
from typing import Annotated

from pydantic import BeforeValidator

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _strict_date(value: object) -> object:
    if isinstance(value, str) and not _DATE.fullmatch(value):
        raise ValueError("not an ISO calendar date")
    return value


IsoDate = Annotated[date, BeforeValidator(_strict_date)]
