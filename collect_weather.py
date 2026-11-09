import csv
import getpass
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


# 기상청 API허브: 지상관측자료 시간자료(기간조회) API.
API_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php"
TIMEOUT_SECONDS = 30
RAW_RESPONSE_PATH = Path(__file__).with_name("weather_raw.txt")
CSV_PATH = Path(__file__).with_name("weather.csv")

# 공식 출력의 헤더 번호는 1부터 시작한다: TM(1), WS(4), TA(12), HM(14).
FIELD_POSITIONS = {"TM": 1, "WS": 4, "TA": 12, "HM": 14}
CSV_COLUMNS = [
    "datetime",
    "temperature_C",
    "humidity_pct",
    "wind_speed_ms",
]


def extract_message(body: str) -> Optional[str]:
    """JSON 또는 일반 텍스트 응답에서 API 오류 message를 추출한다."""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        result = payload.get("result")
        if isinstance(result, dict) and result.get("message"):
            return str(result["message"])
        if payload.get("message"):
            return str(payload["message"])

    match = re.search(r'"message"\s*:\s*"([^"]+)"', body, re.IGNORECASE)
    if match:
        return match.group(1)

    for line in body.splitlines():
        if "message" in line.lower():
            return line.strip().lstrip("#").strip()
    return None


def save_raw_response(body: str) -> None:
    """분석 전 원본 응답을 UTF-8 파일로 보관한다."""
    RAW_RESPONSE_PATH.write_text(body, encoding="utf-8")


def print_response_preview(body: str) -> None:
    """설명 줄을 포함한 본문 앞부분과 실제 자료 행을 구분해 출력한다."""
    lines = body.splitlines()
    data_lines = [
        line for line in lines if line.strip() and not line.lstrip().startswith("#")
    ]

    print("\n[본문 앞 15줄]")
    for line in lines[:15]:
        print(line)

    print("\n[실제 데이터행 3개]")
    for line in data_lines[:3]:
        print(line)


def is_missing(value: str, field: str) -> bool:
    """공식 결측 코드만 빈 값으로 바꾸고, 정상적인 음수 기온은 보존한다."""
    normalized = value.strip()
    if not normalized:
        return True

    # TA의 -9.0은 실제 영하 기온일 수 있으므로 결측으로 간주하지 않는다.
    missing_values = {"-99", "-99.0", "-999", "-999.0", "-9999", "-9999.0"}
    if field != "TA":
        missing_values.update({"-9", "-9.0"})
    return normalized in missing_values


def parse_data_rows(body: str) -> list[dict[str, str]]:
    """# 설명 줄을 제외하고 지정된 열 번호의 자료 행을 표 형태로 변환한다."""
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(body.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        values = line.split()
        if len(values) < max(FIELD_POSITIONS.values()):
            raise ValueError(
                f"{line_number}번째 자료 행의 열 수가 부족합니다: {len(values)}개"
            )

        selected = {
            field: values[position - 1] for field, position in FIELD_POSITIONS.items()
        }
        try:
            timestamp = datetime.strptime(selected["TM"], "%Y%m%d%H%M")
        except ValueError as error:
            raise ValueError(
                f"{line_number}번째 자료 행의 TM 형식이 올바르지 않습니다."
            ) from error

        rows.append(
            {
                "datetime": timestamp.isoformat(sep=" "),
                "temperature_C": ""
                if is_missing(selected["TA"], "TA")
                else selected["TA"],
                "humidity_pct": ""
                if is_missing(selected["HM"], "HM")
                else selected["HM"],
                "wind_speed_ms": ""
                if is_missing(selected["WS"], "WS")
                else selected["WS"],
            }
        )
    return rows


def sort_and_remove_duplicates(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int]:
    """시각순으로 정렬하고 같은 시각의 중복 행은 첫 행만 남긴다."""
    rows.sort(key=lambda row: row["datetime"])
    unique_rows: list[dict[str, str]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for row in rows:
        if row["datetime"] in seen:
            duplicate_count += 1
            continue
        seen.add(row["datetime"])
        unique_rows.append(row)
    return unique_rows, duplicate_count


def save_csv(rows: list[dict[str, str]]) -> None:
    """정제된 자료를 인덱스 없이 UTF-8 BOM 형식의 CSV로 저장한다."""
    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str]], duplicate_count: int) -> None:
    """저장 결과의 행 수, 열별 결측 수, 시간 범위와 경로를 출력한다."""
    missing_counts = {
        column: sum(not row[column] for row in rows)
        for column in CSV_COLUMNS
    }
    print(f"\n행 수: {len(rows)}")
    print(f"중복 시각 제거 수: {duplicate_count}")
    print(f"열별 결측 수: {missing_counts}")
    print(f"첫 시각: {rows[0]['datetime'] if rows else ''}")
    print(f"마지막 시각: {rows[-1]['datetime'] if rows else ''}")
    print(f"원본 응답: {RAW_RESPONSE_PATH}")
    print(f"저장 위치: {CSV_PATH}")


def main() -> None:
    auth_key = getpass.getpass("인증키(authKey)를 입력하세요: ")
    if not auth_key:
        print("인증키가 입력되지 않았습니다.")
        return

    params = {
        "tm1": "202510010000",
        "tm2": "202510072300",
        "stn": "108",
        "help": "1",
        "authKey": auth_key,
    }
    try:
        response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        print("요청에 실패했습니다.")
        return

    print(f"HTTP 상태: {response.status_code} {response.reason}")
    # requests가 서버의 charset을 확인하고, 없을 때만 추정값을 사용한다.
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    body = response.text
    save_raw_response(body)

    if not response.ok:
        message = extract_message(body)
        print(f"오류 message: {message}" if message else "오류 message를 찾을 수 없습니다.")
        return

    print_response_preview(body)
    try:
        rows = parse_data_rows(body)
        rows, duplicate_count = sort_and_remove_duplicates(rows)
        save_csv(rows)
    except ValueError as error:
        print(f"자료 처리에 실패했습니다: {error}")
        return
    print_summary(rows, duplicate_count)


if __name__ == "__main__":
    main()
