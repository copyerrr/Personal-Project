# 박자 기반 점수 계산 방식 제안

## 아이디어
박자(beat) 단위로 센트 차이를 평가하여 1,2,3,4,5점으로 매기고, 그 점수들의 평균으로 전체 평균을 계산하는 방식

---

## 현재 구조 분석

### 사용 가능한 데이터
- `musicMetadata.beat_times`: 박자 시작 시간 배열 (예: [0.0, 0.43, 0.86, 1.29, ...])
- `pitchHistory`: 실시간 피치 데이터 배열
  ```javascript
  {
    user: 440.0,      // 사용자 음정 (Hz)
    target: 440.0,    // 목표 음정 (Hz)
    time: 2.5         // 시간 (초)
  }
  ```

### 현재 점수 계산 방식
- 매 프레임마다 즉시 점수 계산 (0~100점)
- 누적 평균 방식으로 전체 점수 계산
- `score > 0` 조건으로 0점 제외

---

## 제안: 박자 기반 점수 계산

### 개념
1. **박자 구간별 평가**: 각 박자 구간에 속한 모든 피치 데이터를 수집
2. **박자당 평균 센트 차이**: 해당 박자 구간의 평균 센트 차이 계산
3. **1~5점 등급**: 센트 차이에 따라 1~5점으로 매기기
4. **박자 점수들의 평균**: 모든 박자 점수의 평균으로 전체 점수 계산

---

## 구현 제안 코드

### 1. 박자 구간별 데이터 수집 및 점수 계산

```javascript
// 전역 변수 추가
let beatScores = [];  // [{beatIndex, beatTime, score, avgCentsDiff}]
let currentBeatIndex = 0;

// 박자별 점수 계산 함수
function calculateBeatScore(beatIndex, beatStartTime, beatEndTime) {
    // 해당 박자 구간에 속한 pitchHistory 데이터 수집
    const beatData = pitchHistory.filter(p => 
        p.time >= beatStartTime && p.time < beatEndTime &&
        p.user && p.target && p.target > 0
    );
    
    if (beatData.length === 0) {
        return null;  // 해당 박자에 데이터가 없으면 null 반환
    }
    
    // 각 데이터의 센트 차이 계산
    const centsDiffs = beatData.map(p => 
        Math.abs(1200 * Math.log2(p.user / p.target))
    );
    
    // 박자 구간의 평균 센트 차이
    const avgCentsDiff = centsDiffs.reduce((a, b) => a + b, 0) / centsDiffs.length;
    
    // 센트 차이에 따라 1~5점으로 매기기
    let score = 0;
    if (avgCentsDiff <= 10) {
        score = 5;  // 완벽: 10센트 이하
    } else if (avgCentsDiff <= 25) {
        score = 4;  // 매우 좋음: 25센트 이하
    } else if (avgCentsDiff <= 50) {
        score = 3;  // 좋음: 50센트 이하
    } else if (avgCentsDiff <= 100) {
        score = 2;  // 보통: 100센트 이하
    } else if (avgCentsDiff <= 200) {
        score = 1;  // 나쁨: 200센트 이하
    } else {
        score = 0;  // 매우 나쁨: 200센트 초과
    }
    
    return {
        beatIndex,
        beatTime: beatStartTime,
        score,
        avgCentsDiff,
        dataCount: beatData.length
    };
}
```

### 2. 실시간 박자 점수 업데이트 (analyzeAndRender 내부)

```javascript
// analyzeAndRender 함수 내부, 점수 계산 부분을 다음과 같이 수정:

// 현재 시간 기준으로 현재 박자 구간 확인
if (musicMetadata && musicMetadata.beat_times) {
    const beatTimes = musicMetadata.beat_times;
    const currentTime = musicPlayer.currentTime;
    
    // 현재 박자 인덱스 찾기
    let newBeatIndex = 0;
    for (let i = 0; i < beatTimes.length - 1; i++) {
        if (currentTime >= beatTimes[i] && currentTime < beatTimes[i + 1]) {
            newBeatIndex = i;
            break;
        }
    }
    
    // 박자가 바뀌었으면 이전 박자 점수 계산
    if (newBeatIndex !== currentBeatIndex && currentBeatIndex >= 0) {
        const prevBeatStart = beatTimes[currentBeatIndex];
        const prevBeatEnd = beatTimes[currentBeatIndex + 1] || prevBeatStart + 0.5;  // 마지막 박자는 추정
        
        // 이전 박자 점수 계산
        const beatScore = calculateBeatScore(currentBeatIndex, prevBeatStart, prevBeatEnd);
        
        if (beatScore !== null) {
            // 기존 박자 점수가 있으면 업데이트, 없으면 추가
            const existingIndex = beatScores.findIndex(b => b.beatIndex === currentBeatIndex);
            if (existingIndex >= 0) {
                beatScores[existingIndex] = beatScore;
            } else {
                beatScores.push(beatScore);
            }
            
            // 전체 박자 점수 평균 계산
            if (beatScores.length > 0) {
                const totalBeatScore = beatScores.reduce((sum, b) => sum + b.score, 0);
                const averageBeatScore = totalBeatScore / beatScores.length;
                
                // 1~5점을 0~100점 스케일로 변환하여 표시
                const displayScore = Math.round((averageBeatScore / 5) * 100);
                
                scoreElement.textContent = displayScore;
                accuracyElement.textContent = `${displayScore}%`;
                scoreBarFill.style.width = `${displayScore}%`;
            }
        }
        
        currentBeatIndex = newBeatIndex;
    }
}
```

### 3. 대안: 더 부드러운 등급 체계 (1~5점)

```javascript
function calculateBeatScore(beatIndex, beatStartTime, beatEndTime) {
    const beatData = pitchHistory.filter(p => 
        p.time >= beatStartTime && p.time < beatEndTime &&
        p.user && p.target && p.target > 0
    );
    
    if (beatData.length === 0) return null;
    
    const centsDiffs = beatData.map(p => 
        Math.abs(1200 * Math.log2(p.user / p.target))
    );
    const avgCentsDiff = centsDiffs.reduce((a, b) => a + b, 0) / centsDiffs.length;
    
    // 더 세밀한 등급 체계 (선택 가능)
    let score = 0;
    
    // 옵션 1: 간단한 5등급
    if (avgCentsDiff <= 10) score = 5;        // 완벽
    else if (avgCentsDiff <= 25) score = 4;   // 매우 좋음
    else if (avgCentsDiff <= 50) score = 3;   // 좋음
    else if (avgCentsDiff <= 100) score = 2;  // 보통
    else if (avgCentsDiff <= 200) score = 1;  // 나쁨
    // 200센트 초과는 0점
    
    // 옵션 2: 10등급 (더 세밀)
    // if (avgCentsDiff <= 5) score = 10;
    // else if (avgCentsDiff <= 10) score = 9;
    // else if (avgCentsDiff <= 20) score = 8;
    // else if (avgCentsDiff <= 30) score = 7;
    // else if (avgCentsDiff <= 50) score = 6;
    // else if (avgCentsDiff <= 75) score = 5;
    // else if (avgCentsDiff <= 100) score = 4;
    // else if (avgCentsDiff <= 150) score = 3;
    // else if (avgCentsDiff <= 200) score = 2;
    // else score = 1;
    
    return {
        beatIndex,
        beatTime: beatStartTime,
        score,
        avgCentsDiff,
        dataCount: beatData.length
    };
}
```

### 4. 리셋 시 박자 점수도 초기화

```javascript
// resetAll 함수에 추가
beatScores = [];
currentBeatIndex = 0;
```

### 5. 구간 연습 시 박자 점수 리셋

```javascript
// practiceBtn 클릭 이벤트 내부, 리셋 부분에 추가
beatScores = [];
currentBeatIndex = 0;
```

---

## 장점

1. **박자 단위 평가**: 음악의 리듬에 맞춘 자연스러운 평가
2. **명확한 등급**: 1~5점으로 직관적이고 이해하기 쉬움
3. **안정적인 평균**: 박자 단위로 묶어서 계산하므로 점수 변동이 적음
4. **구간별 성과 명확**: 각 박자의 성과를 개별적으로 평가 가능
5. **실패 구간 반영**: 박자 구간 전체가 나쁘면 낮은 점수 반영

---

## 단점 및 고려사항

1. **박자 데이터 필요**: `beat_times`가 없으면 사용 불가
2. **반응 속도**: 박자가 바뀌어야 점수가 업데이트됨 (즉각적이지 않음)
3. **박자 구간 길이**: 빠른 박자와 느린 박자의 데이터 수가 다를 수 있음
4. **등급 기준 조정**: 센트 차이 기준을 음악 스타일에 맞게 조정 필요

---

## 등급 기준 조정 옵션

### 현재 제안 (5등급)
- 5점: 10센트 이하 (완벽)
- 4점: 25센트 이하 (매우 좋음)
- 3점: 50센트 이하 (좋음)
- 2점: 100센트 이하 (보통)
- 1점: 200센트 이하 (나쁨)
- 0점: 200센트 초과 (매우 나쁨)

### 더 관대한 기준
- 5점: 20센트 이하
- 4점: 50센트 이하
- 3점: 100센트 이하
- 2점: 200센트 이하
- 1점: 300센트 이하

### 더 엄격한 기준
- 5점: 5센트 이하
- 4점: 15센트 이하
- 3점: 30센트 이하
- 2점: 60센트 이하
- 1점: 120센트 이하

---

## 대안: 하이브리드 방식

박자 점수(1~5점)와 실시간 점수(0~100점)를 모두 계산하고, 사용자가 선택하도록 하거나 혼합할 수 있음.

```javascript
// 박자 점수 (1~5점) → 0~100점 스케일
const beatBasedScore = (averageBeatScore / 5) * 100;

// 실시간 점수 (현재 방식)
const realtimeScore = Math.round(totalScore / scoreCount);

// 하이브리드: 박자 60% + 실시간 40%
const hybridScore = Math.round(beatBasedScore * 0.6 + realtimeScore * 0.4);
```


