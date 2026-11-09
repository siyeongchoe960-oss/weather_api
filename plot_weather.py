from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "weather.csv"
OUTPUT_PATH = BASE_DIR / "temperature.png"


def load_weather_data(csv_path: Path) -> pd.DataFrame:
    """CSV를 읽고 datetime과 기온을 그래프에 사용할 형식으로 변환한다."""
    data = pd.read_csv(csv_path, encoding="utf-8-sig")
    required_columns = {"datetime", "temperature_C"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"필수 열이 없습니다: {missing}")

    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["temperature_C"] = pd.to_numeric(
        data["temperature_C"], errors="coerce"
    )
    data = data.dropna(subset=["datetime"]).sort_values("datetime")
    return data[["datetime", "temperature_C"]]


def make_hourly_data(data: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """누락된 시각을 1시간 간격으로 추가해 기온 결측을 NaN으로 유지한다."""
    if data.empty:
        raise ValueError("그래프로 그릴 날짜 자료가 없습니다.")

    data = data.drop_duplicates(subset="datetime", keep="first")
    data = data.set_index("datetime").sort_index()
    hourly_index = pd.date_range(
        start=data.index.min(),
        end=data.index.max(),
        freq="h",
        name="datetime",
    )
    hourly_data = data.reindex(hourly_index)
    missing_times = int(hourly_data["temperature_C"].isna().sum())
    return hourly_data, missing_times


def draw_temperature_plot(data: pd.DataFrame, output_path: Path) -> None:
    """시간별 기온을 그리고 결측 구간은 NaN으로 선을 끊어 PNG로 저장한다."""
    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(
        data.index,
        data["temperature_C"],
        color="tab:red",
        marker="o",
        markersize=3,
        linewidth=1.5,
    )
    axis.set_title("Temperature over time")
    axis.set_xlabel("Time (KST)")
    axis.set_ylabel("Temperature (°C)")
    axis.grid(True, alpha=0.3)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.show()
    plt.close(figure)


def main() -> None:
    """weather.csv를 읽어 시간순 기온 그래프를 저장하고 화면에 표시한다."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {CSV_PATH}")

    weather_data = load_weather_data(CSV_PATH)
    hourly_data, missing_count = make_hourly_data(weather_data)
    print(f"누락 시각 수: {missing_count}")
    if missing_count:
        print("누락 시각:")
        for timestamp in hourly_data.index[hourly_data["temperature_C"].isna()]:
            print(timestamp.strftime("%Y-%m-%d %H:%M:%S"))

    draw_temperature_plot(hourly_data, OUTPUT_PATH)
    print(f"저장 위치: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
