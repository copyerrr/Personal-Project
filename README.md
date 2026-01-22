# 노래방 음정 점수 측정 시스템

프론트엔드와 백엔드로 분리된 노래방 음정 점수 측정 시스템입니다.

## 프로젝트 구조

```
music_score/
├── app.py             # 백엔드 서버 (Flask)
├── requirements.txt   # Python 패키지 의존성
├── README.md          # 이 파일
├── templates/         # HTML 템플릿 (Jinja2)
│   └── index.html
└── static/            # 정적 파일 (CSS, JS, 이미지 등)
    ├── css/
    │   └── style.css
    ├── js/
    │   └── script.js
    └── assets/
        └── music1.mp4
```

## 설치 및 실행 방법

### 1. Python 가상환경 생성 (권장)

```bash
python -m venv venv
```

### 2. 가상환경 활성화

**Windows (PowerShell):**
```bash
venv\Scripts\activate
```

**Windows (Git Bash):**
```bash
source venv/Scripts/activate
```

**Mac/Linux:**
```bash
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3-1. 음악 파일 분석 (필수)

음악 파일을 분석하여 타임라인별 목표 음정 데이터를 생성해야 합니다:

```bash
python analyze_music.py
```

이 스크립트는 `static/assets/music1.mp4`를 분석하여 `static/assets/music_pitch_data.json` 파일을 생성합니다.

### 4. 서버 실행

```bash
python app.py
```

서버가 정상적으로 실행되면 다음 메시지가 출력됩니다:

```
 * Running on http://127.0.0.1:5000
```

### 5. 브라우저에서 접속

서버가 실행되면 브라우저에서 다음 주소로 접속하세요:

```
http://localhost:5000
```

## 사용 방법

1. 브라우저에서 `http://localhost:5000` 접속
2. "시작" 버튼 클릭
3. 마이크 권한 허용 (브라우저에서 권한 요청 팝업이 나타남)
4. 음악이 재생되면서 실시간으로 음정 점수가 측정됩니다
5. "중지" 버튼으로 중단, "리셋" 버튼으로 초기화

## API 엔드포인트

### POST /api/analyze-pitch

음정 분석 및 점수 계산

**Request Body:**
```json
{
  "audioData": [0.1, 0.2, 0.3, ...],  # Float32Array를 배열로 변환
  "sampleRate": 44100,
  "targetPitch": 440  # 옵션: 목표 음정 (Hz)
}
```

**Response:**
```json
{
  "success": true,
  "userPitch": 440,
  "targetPitch": 440,
  "score": 100,
  "accuracy": 100
}
```

## 기술 스택

### 백엔드
- **Python 3.8+** - 프로그래밍 언어
- **Flask** - 웹 서버 프레임워크
- **Flask-CORS** - Cross-Origin Resource Sharing 처리
- **NumPy** - 수치 연산
- **SciPy** - 과학 계산 (신호 처리)

### 프론트엔드
- **HTML5** - 마크업
- **CSS3** - 스타일링
- **JavaScript (Vanilla)** - 클라이언트 사이드 로직
- **Web Audio API** - 오디오 처리 및 분석

## 주요 기능

- 🎵 음악 파일 재생 (MP4)
- 🎤 실시간 마이크 입력
- 🔊 실시간 음정 분석 (Autocorrelation 알고리즘)
- 📊 원본 음악과 사용자 음성의 음정 비교
- 🎯 센트 단위 기반 점수 계산
- 📈 실시간 피치 그래프 시각화
- 🎨 노래방 스타일 UI

## 주의사항

- Python 3.8 이상 버전 필요
- 최신 브라우저(Chrome, Edge, Firefox)에서 사용 권장
- HTTPS 또는 localhost 환경에서 마이크 접근 가능
- 마이크 권한이 필요합니다

## 마이크 접근 문제 해결

### 즉시 확인 사항

1. **브라우저 개발자 도구 열기** (F12)
2. **Console 탭** 확인
3. "시작" 버튼 클릭
4. 콘솔에 나타나는 메시지/에러 확인

**콘솔에서 확인할 내용:**
- "시작 버튼 클릭됨" 메시지가 나타나는지
- 에러 메시지가 있는지
- "getUserMedia 호출 중..." 이후 무슨 일이 일어나는지

### 브라우저에서 마이크 권한 허용 방법

**Chrome:**
1. 주소창 왼쪽의 **자물쇠 아이콘** 클릭
2. "사이트 설정" 클릭
3. "마이크" 옵션을 **"허용"**으로 변경
4. 페이지 새로고침 (F5)

**전역 Chrome 설정:**
- `chrome://settings/content/microphone` 접속
- "사이트에서 마이크 사용 전에 권한 요청" 체크 확인

### Windows에서 마이크 권한 확인
1. Windows 설정 (Win + I) > 개인 정보 > 마이크
2. "앱이 마이크에 액세스하도록 허용" 활성화
3. "마이크에 액세스할 수 있는 앱 선택"에서 Chrome 확인

### 자세한 문제 해결
`TROUBLESHOOTING.md` 파일을 참고하세요.

## 문제 해결

### librosa 설치 오류
librosa 설치에 문제가 있는 경우:

```bash
pip install --upgrade pip
pip install librosa
```

또는 librosa 없이도 작동하도록 requirements.txt에서 제거 가능합니다 (현재 코드는 librosa를 사용하지 않음).
