## 관측 정보

- 관측소: `108` (서울)
- 관측 기간: `2025-10-01 00:00` ~ `2025-10-07 23:00` (KST)
- 관측 자료: 시간별 관측시각, 기온, 상대습도, 풍속
- 출처: [기상청 API허브 지상관측자료 시간자료 API](https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php)

## 실행 방법

프로젝트 폴더에서 가상환경을 활성화한 뒤 실행합니다.

```powershell
.\.venv\Scripts\Activate.ps1
```

### 1. API 자료 수집

```powershell
python collect_weather.py
```

실행 중 `getpass.getpass()`로 기상청 API 인증키를 입력합니다. 인증키는 화면에 표시되지 않으며, 요청 주소에도 출력하지 않습니다.

실행 결과:

- `weather.csv`: 정제된 관측 자료
- `weather_raw.txt`: API 원본 응답

### 2. 기온 그래프 생성

```powershell
python plot_weather.py
```

`weather.csv`를 다시 API에 요청하지 않고 읽어 시간순으로 정렬한 뒤, 1시간 간격으로 누락 시각을 확인합니다. 기온 결측 구간은 보간하지 않아 그래프의 선이 끊기며, 그래프는 `temperature.png`로 저장되고 화면에도 표시됩니다.
