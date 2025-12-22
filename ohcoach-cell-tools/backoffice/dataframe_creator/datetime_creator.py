from datetime import datetime

# 도움말 보러 가기
# https://www.notion.so/fitogether/backoffice-plotly-726b2761368b41e588466ba130035a21#4fe97cf68fbd445e9f1d0f90059715d8


def extract_year_month_day_from_datetime(datetime_str: str) -> dict:
    datetime_str = datetime_str.split("-")
    datetime_dict = {"year": datetime_str[0], "month": datetime_str[1], "day": datetime_str[2]}
    return datetime_dict


def get_now_datetime() -> list:
    now = datetime.now()
    return [now.year, now.month, now.day]
