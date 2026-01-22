// 전역 변수
let audioContext;
let musicSource;
let micSource;
let musicAnalyser;
let micAnalyser;
let isPlaying = false;
let animationFrameId;
let pitchHistory = [];
let pitchTimeline = []; // 타임라인별 목표 음정 데이터
let musicMetadata = null; // 음악 메타데이터 (BPM, beat_times 등)
let totalScore = 0; // 누적 점수
let scoreCount = 0; // 점수 계산 횟수
let lastTargetNoteName = null; // 이전 목표 계이름 (UI 업데이트 최적화용)
let lastTargetPitch = null; // 이전 목표 주파수 (계이름 안정화용)
const NOTE_CHANGE_THRESHOLD = 50; // 계이름이 바뀌려면 최소 50센트 차이 필요

// 피치 감지 관련 변수 (프론트엔드 직접 감지)
let detectPitchFunction = null; // pitchfinder 함수
let lastDetectedPitch = 0; // 스무딩을 위한 이전 피치 값
const SMOOTHING_FACTOR = 0.3; // 스무딩 계수 (0.0 ~ 1.0, 클수록 부드럽지만 반응 느림)
const VOLUME_THRESHOLD = 0.003; // 볼륨 임계값 (조용할 때는 분석하지 않음) - 감도 향상
const MAX_PITCH_CHANGE_CENTS = 500; // 최대 허용 피치 변화 (500센트 = 약 4반음, 튀는 값만 필터링)

// DOM 요소
const musicPlayer = document.getElementById('musicPlayer');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const resetBtn = document.getElementById('resetBtn');
const skipBtn = document.getElementById('skipBtn');
const volumeSlider = document.getElementById('volumeSlider');
const volumeValue = document.getElementById('volumeValue');
const scoreElement = document.getElementById('score');
const accuracyElement = document.getElementById('accuracy');
const scoreBarFill = document.getElementById('scoreBarFill');
const statusElement = document.getElementById('status');
const currentPitchElement = document.getElementById('currentPitch');
const targetPitchElement = document.getElementById('targetPitch');
const pitchCanvas = document.getElementById('pitchCanvas');
const ctx = pitchCanvas.getContext('2d');

// Canvas 설정
pitchCanvas.width = pitchCanvas.offsetWidth;
pitchCanvas.height = pitchCanvas.offsetHeight;

// AudioContext 초기화
async function initAudioContext() {
    try {
        console.log('AudioContext 초기화 시작...');
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        console.log('AudioContext 초기화 성공:', audioContext.state);
        return true;
    } catch (error) {
        console.error('AudioContext 초기화 실패:', error);
        alert('오디오 컨텍스트 초기화에 실패했습니다: ' + error.message);
        return false;
    }
}

// 백엔드 API URL
const API_BASE_URL = 'http://localhost:5000';

// 백엔드 API 호출 - 음정 분석
// 프론트엔드에서 직접 피치 감지 (서버 통신 없음)
function detectPitchLocal(audioData, sampleRate) {
    // pitchfinder가 없으면 폴백 (기존 Autocorrelation 방식)
    // 여러 방법으로 Pitchfinder 찾기
    const PitchfinderLib = typeof Pitchfinder !== 'undefined' ? Pitchfinder : 
                           (typeof window !== 'undefined' && window.Pitchfinder ? window.Pitchfinder : null) ||
                           (typeof global !== 'undefined' && global.Pitchfinder ? global.Pitchfinder : null);
    
    if (!PitchfinderLib) {
        // 첫 번째 호출 시에만 경고
        if (!window.pitchfinderWarningShown) {
            console.warn('⚠️ Pitchfinder가 로드되지 않았습니다. Autocorrelation 방식으로 폴백합니다.');
            console.warn('   Pitchfinder 변수 확인:', { 
                typeofPitchfinder: typeof Pitchfinder,
                windowPitchfinder: typeof window !== 'undefined' ? typeof window.Pitchfinder : 'window undefined'
            });
            window.pitchfinderWarningShown = true;
        }
        return detectPitchAutocorrelation(audioData, sampleRate);
    }
    
    if (!detectPitchFunction) {
        try {
            // pitchfinder 초기화 (YIN 알고리즘 사용)
            if (PitchfinderLib.YIN) {
                detectPitchFunction = PitchfinderLib.YIN({ sampleRate: sampleRate });
                console.log('✅ Pitchfinder 초기화 완료 (YIN 알고리즘)');
            } else {
                console.warn('⚠️ Pitchfinder.YIN을 찾을 수 없습니다. Autocorrelation 방식으로 폴백합니다.');
                return detectPitchAutocorrelation(audioData, sampleRate);
            }
        } catch (error) {
            console.error('Pitchfinder 초기화 오류:', error);
            return detectPitchAutocorrelation(audioData, sampleRate);
        }
    }
    
    try {
        // pitchfinder로 피치 감지
        const pitchHz = detectPitchFunction(audioData);
        
        if (pitchHz && pitchHz > 0 && !isNaN(pitchHz) && isFinite(pitchHz)) {
            // 유효한 범위 체크 (80Hz ~ 800Hz - 사람 목소리 범위)
            if (pitchHz >= 80 && pitchHz <= 800) {
                // 변화율 제한 (튀는 값 필터링)
                if (lastDetectedPitch > 0) {
                    const centsDiff = Math.abs(1200 * Math.log2(pitchHz / lastDetectedPitch));
                    
                    // 200센트(약 2반음) 이상 차이나면 튀는 값으로 간주하고 무시
                    if (centsDiff > MAX_PITCH_CHANGE_CENTS) {
                        // 튀는 값 무시, 이전 값 유지 (lastDetectedPitch 업데이트 안 함)
                        return null;
                    }
                    
                    // 스무딩 처리 (부드러운 UI를 위해)
                    const smoothedPitch = pitchHz * SMOOTHING_FACTOR + lastDetectedPitch * (1 - SMOOTHING_FACTOR);
                    lastDetectedPitch = smoothedPitch;
                    return smoothedPitch;
                } else {
                    // 첫 번째 감지값은 그대로 사용
                    lastDetectedPitch = pitchHz;
                    return pitchHz;
                }
            }
        }
        
        return null;
    } catch (error) {
        console.error('피치 감지 오류:', error);
        return detectPitchAutocorrelation(audioData, sampleRate);
    }
}

// Autocorrelation 방식 (폴백용) - 개선된 버전
function detectPitchAutocorrelation(buffer, sampleRate) {
    if (!buffer || buffer.length === 0) {
        return null;
    }
    
    // 신호 강도(볼륨) 계산
    let rms = 0;
    for (let i = 0; i < buffer.length; i++) {
        rms += buffer[i] * buffer[i];
    }
    rms = Math.sqrt(rms / buffer.length);
    
    if (rms < VOLUME_THRESHOLD) {
        return null; // 너무 조용하면 음정 감지하지 않음
    }
    
    // 최소/최대 주기 설정 (80Hz ~ 800Hz 범위 - 사람 목소리 범위)
    const minPeriod = Math.max(1, Math.floor(sampleRate / 800)); // 최소 주기 (최대 800Hz)
    const maxPeriod = Math.min(buffer.length / 2, Math.floor(sampleRate / 80)); // 최대 주기 (최소 80Hz)
    
    if (buffer.length < maxPeriod * 2) {
        return null; // 버퍼가 너무 짧으면 분석 불가
    }
    
    // 신호 정규화 (DC 오프셋 제거)
    let mean = 0;
    for (let i = 0; i < buffer.length; i++) {
        mean += buffer[i];
    }
    mean = mean / buffer.length;
    
    const normalizedBuffer = new Float32Array(buffer.length);
    for (let i = 0; i < buffer.length; i++) {
        normalizedBuffer[i] = buffer[i] - mean;
    }
    
    let bestPeriod = 0;
    let bestCorrelation = -1;
    
    // Autocorrelation 계산 (Pearson correlation 사용)
    for (let period = minPeriod; period < maxPeriod; period++) {
        let correlation = 0;
        let sum1 = 0;
        let sum2 = 0;
        let count = 0;
        
        // 정규화된 autocorrelation 계산 (Pearson correlation)
        for (let i = 0; i < normalizedBuffer.length - period; i++) {
            const val1 = normalizedBuffer[i];
            const val2 = normalizedBuffer[i + period];
            correlation += val1 * val2;
            sum1 += val1 * val1;
            sum2 += val2 * val2;
            count++;
        }
        
        if (count > 0 && sum1 > 0 && sum2 > 0) {
            // 정규화된 상관계수 (Pearson correlation)
            const normalizedCorr = correlation / Math.sqrt(sum1 * sum2);
            
            if (normalizedCorr > bestCorrelation) {
                bestCorrelation = normalizedCorr;
                bestPeriod = period;
            }
        }
    }
    
    // 임계값 조정 (0.2로 낮춤 - 더 많은 음정 감지)
    if (bestPeriod > 0 && bestCorrelation > 0.2) {
        const detectedFreq = sampleRate / bestPeriod;
        
        // 유효한 범위 체크 (80Hz ~ 800Hz - 사람 목소리 범위)
        if (detectedFreq >= 80 && detectedFreq <= 800) {
            // 변화율 제한 (튀는 값만 필터링 - 정상적인 음정 변화는 허용)
            if (lastDetectedPitch > 0) {
                const centsDiff = Math.abs(1200 * Math.log2(detectedFreq / lastDetectedPitch));
                
                // 500센트(약 4반음) 이상 차이나면 튀는 값으로 간주하고 무시
                // 정상적인 음정 변화(1-2옥타브)는 허용
                if (centsDiff > MAX_PITCH_CHANGE_CENTS) {
                    // 튀는 값 무시 (lastDetectedPitch 업데이트 안 함)
                    return null;
                }
                
                // 스무딩 처리 (부드러운 UI를 위해)
                const smoothedFreq = detectedFreq * SMOOTHING_FACTOR + lastDetectedPitch * (1 - SMOOTHING_FACTOR);
                lastDetectedPitch = smoothedFreq;
                return smoothedFreq;
            } else {
                // 첫 번째 감지값은 그대로 사용
                lastDetectedPitch = detectedFreq;
                return detectedFreq;
            }
        } else {
            // 범위 밖 주파수 (디버깅용 - 가끔만 로그)
            if (Math.random() < 0.001) {
                console.log('🔍 [범위 밖 주파수]', { detectedFreq: detectedFreq.toFixed(1), bestCorrelation: bestCorrelation.toFixed(3) });
            }
        }
    } else {
        // 상관계수 부족 (디버깅용 - 가끔만 로그)
        if (Math.random() < 0.001 && bestPeriod > 0) {
            const detectedFreq = sampleRate / bestPeriod;
            console.log('🔍 [상관계수 부족]', { 
                bestCorrelation: bestCorrelation.toFixed(3), 
                threshold: 0.2,
                detectedFreq: detectedFreq.toFixed(1),
                bestPeriod: bestPeriod
            });
        }
    }
    
    return null;
}

// 점수 계산 함수 (프론트엔드에서 직접 계산)
function calculateScoreLocal(userPitch, targetPitch) {
    if (!userPitch || !targetPitch) return 0;
    
    // 센트 차이 계산
    const centsDiff = Math.abs(1200 * Math.log2(userPitch / targetPitch));
    
    // 점수 계산 (백엔드와 동일한 로직)
    let score = 0;
    if (centsDiff <= 5) {
        score = 100 - (centsDiff * 0.5);
    } else if (centsDiff <= 10) {
        score = 97.5 - ((centsDiff - 5) * 0.5);
    } else if (centsDiff <= 20) {
        score = 95 - ((centsDiff - 10) * 1.0);
    } else if (centsDiff <= 30) {
        score = 85 - ((centsDiff - 20) * 1.5);
    } else if (centsDiff <= 50) {
        score = 70 - ((centsDiff - 30) * 0.4);
    }
    
    return Math.max(0, Math.round(score));
}

// 음악 분석 시작
async function analyzeMusic() {
    try {
        // 이미 musicSource가 생성되지 않은 경우에만 생성
        if (!musicSource) {
            // captureStream이 지원되는 경우 사용 (Chrome, Edge)
            if (musicPlayer.captureStream) {
                const stream = musicPlayer.captureStream();
                musicSource = audioContext.createMediaStreamSource(stream);
            } else if (musicPlayer.mozCaptureStream) {
                // Firefox
                const stream = musicPlayer.mozCaptureStream();
                musicSource = audioContext.createMediaStreamSource(stream);
            } else {
                // MediaElementAudioSourceNode 사용 (표준 방법)
                musicSource = audioContext.createMediaElementSource(musicPlayer);
                // 오디오 재생을 위해 destination에 연결
                musicSource.connect(audioContext.destination);
            }
        }
        
        // 분석기 생성 및 연결
        if (!musicAnalyser) {
            musicAnalyser = audioContext.createAnalyser();
            musicAnalyser.fftSize = 2048;
            musicAnalyser.smoothingTimeConstant = 0.8;
            musicSource.connect(musicAnalyser);
        }
    } catch (error) {
        console.error('음악 분석 시작 실패:', error);
    }
}

// 마이크 입력 설정
async function setupMicrophone() {
    try {
        console.log('마이크 설정 시작...');
        console.log('navigator.mediaDevices:', navigator.mediaDevices);
        
        // mediaDevices 지원 확인
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            console.error('getUserMedia를 지원하지 않습니다.');
            alert('이 브라우저는 마이크 접근을 지원하지 않습니다.\n최신 브라우저(Chrome, Edge, Firefox)를 사용해주세요.');
            return false;
        }
        
        console.log('getUserMedia 호출 중...');
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: false, // 음악용은 false가 나을 수 있음 (강약 조절 위해)
                latency: 0 // 가능한 최저 지연 시간 요청
            }
        });
        console.log('마이크 스트림 획득 성공:', stream);
        
        if (!audioContext) {
            console.error('audioContext가 초기화되지 않았습니다.');
            alert('오디오 컨텍스트가 초기화되지 않았습니다.');
            return false;
        }
        
        micSource = audioContext.createMediaStreamSource(stream);
        micAnalyser = audioContext.createAnalyser();
        micAnalyser.fftSize = 2048;
        micAnalyser.smoothingTimeConstant = 0.3;
        micSource.connect(micAnalyser);
        console.log('마이크 설정 완료');
        return true;
    } catch (error) {
        console.error('마이크 접근 실패:', error);
        
        let errorMessage = '마이크 접근 권한이 필요합니다.\n\n';
        
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMessage += '마이크 권한이 거부되었습니다.\n';
            errorMessage += '브라우저 주소창 옆의 자물쇠 아이콘을 클릭하여 마이크 권한을 허용해주세요.';
        } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
            errorMessage += '마이크를 찾을 수 없습니다.\n';
            errorMessage += '마이크가 연결되어 있는지 확인해주세요.';
        } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
            errorMessage += '마이크에 접근할 수 없습니다.\n';
            errorMessage += '다른 프로그램에서 마이크를 사용 중일 수 있습니다.';
        } else {
            errorMessage += `오류: ${error.name}\n`;
            errorMessage += '브라우저 설정에서 마이크 권한을 확인해주세요.';
        }
        
        alert(errorMessage);
        statusElement.textContent = '마이크 접근 실패';
        return false;
    }
}

// 현재 재생 시간에 해당하는 목표 음정 가져오기
function getTargetPitchAtTime(currentTime) {
    if (!pitchTimeline || pitchTimeline.length === 0) {
        return null;
    }
    
    // vocal.wav는 원본과 동일한 시간축을 가지므로 오프셋 불필요
    // 현재 시간에 가장 가까운 데이터 포인트 찾기 (이진 검색으로 최적화)
    let left = 0;
    let right = pitchTimeline.length - 1;
    let closestIndex = 0;
    let minDiff = Infinity;
    
    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        const diff = Math.abs(pitchTimeline[mid].time - currentTime);
        
        if (diff < minDiff) {
            minDiff = diff;
            closestIndex = mid;
        }
        
        if (pitchTimeline[mid].time < currentTime) {
            left = mid + 1;
        } else {
            right = mid - 1;
        }
    }
    
    // 가장 가까운 포인트의 음정 반환
    const targetPitch = pitchTimeline[closestIndex].pitch;
    
    // 반주 구간(null)은 그대로 null 반환
    // 반주 점프 기능이 제대로 작동하도록 하기 위해 주변에서 찾지 않음
    return targetPitch;
}

// 다음 보컬 시작 시간 찾기 (현재 시간 이후)
function findNextVocalStartTime(currentTime) {
    if (!pitchTimeline || pitchTimeline.length === 0) {
        return null;
    }
    
    // 단순하게 현재 시간 이후의 첫 번째 보컬 찾기
    for (let i = 0; i < pitchTimeline.length; i++) {
        const item = pitchTimeline[i];
        if (item.time > currentTime && 
            item.pitch !== null && 
            item.pitch !== undefined) {
            return item.time;
        }
    }
    
    return null;
}

// 반주 부분인지 확인 (목표 음정이 없는 구간)
function isInstrumental(currentTime) {
    const targetPitch = getTargetPitchAtTime(currentTime);
    return targetPitch === null;
}

// 실시간 분석 및 렌더링
async function analyzeAndRender() {
    // drawStaff는 항상 호출 (재생 중이 아니어도 화면 업데이트)
    try {
        drawStaff();
    } catch (error) {
        console.error('drawStaff 오류:', error);
    }
    
    // 재생 중이 아니면 여기서 종료 (마이크 분석은 하지 않음)
    if (!isPlaying) {
        animationFrameId = requestAnimationFrame(analyzeAndRender);
        return;
    }
    
    const now = Date.now();
    const bufferLength = micAnalyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const timeDomainArray = new Float32Array(micAnalyser.fftSize);
    
    // 마이크 데이터 가져오기
    micAnalyser.getByteFrequencyData(dataArray);
    micAnalyser.getFloatTimeDomainData(timeDomainArray);
    
    // 신호 강도(볼륨) 계산 - 조용할 때는 음정 감지하지 않음
    let rms = 0;
    for (let i = 0; i < timeDomainArray.length; i++) {
        rms += timeDomainArray[i] * timeDomainArray[i];
    }
    rms = Math.sqrt(rms / timeDomainArray.length);
    // VOLUME_THRESHOLD 사용 (전역 변수)
    
    // 현재 재생 시간에 해당하는 목표 음정 가져오기 (항상 타임라인에서 가져옴)
    const currentTime = musicPlayer.currentTime;
    const targetPitch = getTargetPitchAtTime(currentTime);
    
    // 카운트다운 중이면 목표 음정 업데이트하지 않음
    if (isCountingDown) {
        animationFrameId = requestAnimationFrame(analyzeAndRender);
        return;
    }
    
    // 목표 음정 표시 (계이름만, Hz 제거)
    // 계이름 안정화: 작은 주파수 변동은 무시하고 실제로 계이름이 바뀔 때만 업데이트
    if (targetPitch !== null && targetPitch !== undefined && targetPitch > 0) {
        // 이전 주파수와 비교하여 실제로 계이름이 바뀌는지 확인
        let shouldUpdate = false;
        
        if (lastTargetPitch === null) {
            // 첫 번째 음정이면 바로 표시
            shouldUpdate = true;
        } else {
            // 이전 주파수와의 차이를 센트로 계산
            const centsDiff = Math.abs(1200 * Math.log2(targetPitch / lastTargetPitch));
            
            // 50센트 이상 차이나면 계이름이 바뀐 것으로 간주
            if (centsDiff >= NOTE_CHANGE_THRESHOLD) {
                const targetNoteName = frequencyToNoteName(targetPitch, true);
                const lastNoteName = frequencyToNoteName(lastTargetPitch, true);
                
                // 실제로 계이름이 다를 때만 업데이트
                if (targetNoteName !== lastNoteName) {
                    shouldUpdate = true;
                }
            }
            // 50센트 미만이면 같은 음으로 간주하고 업데이트하지 않음
        }
        
        if (shouldUpdate) {
            const targetNoteName = frequencyToNoteName(targetPitch, true);
            targetPitchElement.textContent = targetNoteName;
            lastTargetNoteName = targetNoteName;
            lastTargetPitch = targetPitch;
        }
    } else {
        // 반주 구간일 때만 업데이트 (이전에 보컬 구간이었다면)
        if (lastTargetNoteName !== null) {
            targetPitchElement.textContent = '-';
            lastTargetNoteName = null;
            lastTargetPitch = null;
        }
    }
    
    // 프론트엔드에서 직접 피치 감지 (서버 통신 없음 - 실시간 반응)
    // 볼륨이 임계값 이상일 때만 분석
    if (rms >= VOLUME_THRESHOLD) {
        // 브라우저에서 직접 피치 감지
        const userPitch = detectPitchLocal(timeDomainArray, audioContext.sampleRate);
        
        // 🔍 디버깅: 피치 미감지 원인 분석 (가끔만 로그)
        if (!userPitch && Math.random() < 0.005) {
            // Autocorrelation 직접 테스트
            const testPitch = detectPitchAutocorrelation(timeDomainArray, audioContext.sampleRate);
            console.log('🔍 [피치 미감지 상세 분석]', {
                rms: rms.toFixed(4),
                lastDetectedPitch: lastDetectedPitch > 0 ? lastDetectedPitch.toFixed(1) + 'Hz' : '없음',
                directAutocorr: testPitch ? testPitch.toFixed(1) + 'Hz' : 'null',
                bufferLength: timeDomainArray.length,
                sampleRate: audioContext.sampleRate,
                bufferMax: Math.max(...Array.from(timeDomainArray)).toFixed(4),
                bufferMin: Math.min(...Array.from(timeDomainArray)).toFixed(4)
            });
        }
        
        if (userPitch && userPitch > 0 && !isNaN(userPitch) && isFinite(userPitch)) {
            // Hz를 계이름으로 변환
            const userNoteName = frequencyToNoteName(userPitch, true);
            
            // 🔍 분석용: 튀는 값 감지 및 로깅
            if (!window.pitchAnalysisData) {
                window.pitchAnalysisData = {
                    lastNoteName: null,
                    lastPitch: null,
                    consecutiveCount: 0,
                    outliers: [],
                    allDetections: []
                };
            }
            
            const analysis = window.pitchAnalysisData;
            const timeSinceLast = currentTime - (analysis.lastTime || 0);
            
            // 이전 값과 비교
            if (analysis.lastPitch && analysis.lastNoteName) {
                const pitchDiff = Math.abs(userPitch - analysis.lastPitch);
                const centsDiff = Math.abs(1200 * Math.log2(userPitch / analysis.lastPitch));
                
                // 같은 계이름이면 카운트 증가
                if (userNoteName === analysis.lastNoteName) {
                    analysis.consecutiveCount++;
                } else {
                    // 계이름이 바뀌었는데 큰 차이가 있으면 튀는 값일 수 있음
                    if (centsDiff > 200) { // 200센트 이상 차이 (약 2반음 이상)
                        analysis.outliers.push({
                            time: currentTime,
                            previous: { note: analysis.lastNoteName, pitch: analysis.lastPitch },
                            current: { note: userNoteName, pitch: userPitch },
                            centsDiff: centsDiff.toFixed(1),
                            timeSinceLast: timeSinceLast.toFixed(3)
                        });
                        
                        // 튀는 값 감지 시 콘솔에 로그 (최대 10개만)
                        if (analysis.outliers.length <= 10) {
                            console.warn('🎵 [피치 튀는 값 감지]', {
                                시간: currentTime.toFixed(2) + '초',
                                이전: `${analysis.lastNoteName} (${analysis.lastPitch.toFixed(1)}Hz)`,
                                현재: `${userNoteName} (${userPitch.toFixed(1)}Hz)`,
                                차이: centsDiff.toFixed(1) + '센트',
                                간격: timeSinceLast.toFixed(3) + '초'
                            });
                        }
                    }
                    analysis.consecutiveCount = 1;
                }
            }
            
            // 모든 감지 결과 저장 (최대 100개)
            if (analysis.allDetections.length < 100) {
                analysis.allDetections.push({
                    time: currentTime,
                    pitch: userPitch,
                    note: userNoteName,
                    rms: rms
                });
            }
            
            // 업데이트
            analysis.lastNoteName = userNoteName;
            analysis.lastPitch = userPitch;
            analysis.lastTime = currentTime;
            
            currentPitchElement.textContent = userNoteName;
            
            // pitchHistory에 저장
            pitchHistory.push({ 
                user: userPitch, 
                target: targetPitch,  // 현재 시간의 목표 음정 사용
                time: currentTime  // 실제 음악 시간 사용
            });
            
            // 최근 100개만 유지
            if (pitchHistory.length > 100) {
                pitchHistory.shift();
            }
            
            // 점수 계산 (프론트엔드에서 직접)
            if (targetPitch && targetPitch > 0) {
                const score = calculateScoreLocal(userPitch, targetPitch);
                
                if (score > 0) {
                    totalScore += score;
                    scoreCount++;
                    const averageScore = Math.round(totalScore / scoreCount);
                    
                    // 점수 표시 (누적 평균)
                    scoreElement.textContent = averageScore;
                    accuracyElement.textContent = `${averageScore}%`;
                    scoreBarFill.style.width = `${averageScore}%`;
                }
            }
        } else {
            // 피치 감지 실패 시
            if (rms > VOLUME_THRESHOLD * 2) {
                // 볼륨은 충분한데 피치가 감지 안 되면 디버깅 (첫 몇 번만)
                if (Math.random() < 0.01) { // 1% 확률로만 로그 (과도한 로그 방지)
                    console.log('볼륨 충분하지만 피치 미감지:', { rms: rms.toFixed(4), userPitch, bufferLength: timeDomainArray.length });
                }
            }
            currentPitchElement.textContent = '-';
        }
    } else {
        // 볼륨이 너무 낮으면 음정 감지하지 않음
        currentPitchElement.textContent = '-';
        // 목표 음정은 위에서 이미 처리됨 (계이름이 바뀔 때만 업데이트)
    }
    
    // 다음 프레임 요청 (항상 실행)
    animationFrameId = requestAnimationFrame(analyzeAndRender);
}

// MIDI 노트를 Y 위치로 변환 (점과 막대 표현용)
// Canvas Y 좌표: 위쪽이 작은 값(0), 아래쪽이 큰 값(height)
// 높은 음 → 작은 Y 값 (위쪽), 낮은 음 → 큰 Y 값 (아래쪽)
function midiToStaffY(midiNote, minMidi, maxMidi, canvasTop, canvasBottom) {
    if (midiNote === null || isNaN(midiNote)) return null;
    const note = Math.round(midiNote);
    
    // MIDI 범위를 Canvas 높이로 매핑
    const midiRange = maxMidi - minMidi;
    const availableHeight = canvasBottom - canvasTop;
    
    if (midiRange <= 0 || availableHeight <= 0) return canvasTop;
    
    // MIDI 노트를 0-1 범위로 정규화
    const normalized = (note - minMidi) / midiRange;
    
    // 정규화된 값을 Canvas Y 좌표로 매핑 (높은 음이 위쪽)
    // normalized = 0 (minMidi, 낮은 음) → canvasBottom (아래쪽)
    // normalized = 1 (maxMidi, 높은 음) → canvasTop (위쪽)
    let y = canvasBottom - (normalized * availableHeight);
    
    // 범위 체크 및 강제 제한 (무조건 Canvas 안에 들어오도록)
    y = Math.max(canvasTop, Math.min(canvasBottom, y));
    
    return y;
}

// 악보 그리기 (점과 막대로 표현)
function drawStaff() {
    ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    // 배경색 설정
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    const padding = 30; // 여백
    const staffWidth = pitchCanvas.width - padding * 2;
    const staffTop = padding;
    const staffBottom = pitchCanvas.height - padding;
    const canvasTop = padding;
    const canvasBottom = pitchCanvas.height - padding;
    
    // 사용 가능한 높이 범위
    const availableHeight = staffBottom - staffTop;
    
    // 실제 데이터에서 MIDI 범위 계산 (동적)
    let minMidi = 36; // 기본값: C2
    let maxMidi = 96; // 기본값: C7
    
    if (pitchTimeline && pitchTimeline.length > 0) {
        // 실제 데이터에서 MIDI 범위 찾기
        const allMidis = [];
        pitchTimeline.forEach(point => {
            if (point.pitch !== null && point.pitch > 0) {
                const midi = frequencyToMidi(point.pitch);
                if (!isNaN(midi) && midi > 0 && midi < 200) { // 합리적인 범위 내에서만
                    allMidis.push(midi);
                }
            }
        });
        
        if (allMidis.length > 0) {
            const actualMin = Math.min(...allMidis);
            const actualMax = Math.max(...allMidis);
            
            // 여유 공간을 거의 없애고 실제 데이터 범위만 사용 (음정 간격 최대화)
            // 최소 1반음만 추가하여 가장자리가 잘리지 않도록
            minMidi = Math.floor(actualMin - 1);
            maxMidi = Math.ceil(actualMax + 1);
            
            // 합리적인 범위로 제한
            minMidi = Math.max(20, minMidi); // 최소 C1
            maxMidi = Math.min(120, maxMidi); // 최대 C9
        }
    }
    
    const midiRange = maxMidi - minMidi;
    
    // 타임라인 데이터를 기반으로 목표 음정 표시 (현재 시간 기준으로 앞뒤)
    // isPlaying 체크 제거 - 항상 그리기 (재생 중이 아니어도 표시)
    if (pitchTimeline.length > 0) {
        const currentTime = isPlaying && musicPlayer ? musicPlayer.currentTime : 0;
        const previewDuration = 3; // 앞으로 3초 미리보기
        const pastDuration = 1; // 뒤로 1초
        
        // 표시할 시간 범위
        const startTime = Math.max(0, currentTime - pastDuration);
        const endTime = currentTime + previewDuration;
        
        // 해당 범위의 타임라인 데이터 필터링
        const visibleNotes = pitchTimeline.filter(point => 
            point.time >= startTime && point.time <= endTime && point.pitch !== null
        );
        
        if (visibleNotes.length > 0) {
            const timeRange = endTime - startTime;
            
            // 목표 음정 점들 그리기
            const targetPoints = [];
            
            visibleNotes.forEach((point, index) => {
                const x = padding + (point.time - startTime) / timeRange * staffWidth;
                const targetMidi = frequencyToMidi(point.pitch);
                const targetY = midiToStaffY(targetMidi, minMidi, maxMidi, canvasTop, canvasBottom);
                
                if (targetY !== null) {
                    targetPoints.push({ x, y: targetY, time: point.time, pitch: point.pitch, midi: targetMidi });
                }
            });
            
            // 같은 음 구간을 막대로 표시, 다른 음은 점으로 표시
            if (targetPoints.length > 0) {
                const SAME_NOTE_THRESHOLD = 50; // 센트 단위 (50센트 = 반음의 절반)
                
                // 같은 음 구간 찾기
                let segmentStart = 0;
                
                for (let i = 0; i < targetPoints.length; i++) {
                    const isLast = i === targetPoints.length - 1;
                    const isDifferentNote = !isLast && 
                        Math.abs(1200 * Math.log2(targetPoints[i + 1].pitch / targetPoints[i].pitch)) > SAME_NOTE_THRESHOLD;
                    
                    // 구간이 끝나거나 마지막 점이면
                    if (isDifferentNote || isLast) {
                        const segmentEnd = isLast ? i : i;
                        const segmentPoints = targetPoints.slice(segmentStart, segmentEnd + 1);
                        
                        if (segmentPoints.length > 1) {
                            // 같은 음 구간: 양옆이 둥근 막대로 표시
                            const startX = segmentPoints[0].x;
                            const endX = segmentPoints[segmentPoints.length - 1].x;
                            const y = segmentPoints[0].y;
                            const barHeight = 8; // 막대 높이
                            
                            const timeDiff = Math.abs(segmentPoints[0].time - currentTime);
                            const opacity = timeDiff < 0.2 ? 1.0 : Math.max(0.3, 1.0 - timeDiff / previewDuration);
                            
                            // 둥근 직사각형으로 그리기
                            ctx.fillStyle = `rgba(100, 200, 255, ${opacity * 0.8})`;
                            const width = endX - startX;
                            const radius = barHeight / 2; // 반지름 = 높이의 절반
                            
                            ctx.beginPath();
                            // 왼쪽 반원
                            ctx.arc(startX, y, radius, Math.PI / 2, Math.PI * 3 / 2, false);
                            // 위쪽 직선
                            ctx.lineTo(startX + width, y - radius);
                            // 오른쪽 반원
                            ctx.arc(endX, y, radius, Math.PI * 3 / 2, Math.PI / 2, false);
                            // 아래쪽 직선
                            ctx.lineTo(startX, y + radius);
                            ctx.closePath();
                            ctx.fill();
                        } else {
                            // 단일 점: 점으로 표시
                            const point = segmentPoints[0];
                            const timeDiff = Math.abs(point.time - currentTime);
                            const opacity = timeDiff < 0.2 ? 1.0 : Math.max(0.3, 1.0 - timeDiff / previewDuration);
                            
                            ctx.fillStyle = `rgba(100, 200, 255, ${opacity * 0.9})`;
                            ctx.beginPath();
                            ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
                            ctx.fill();
                            ctx.strokeStyle = `rgba(100, 200, 255, ${opacity})`;
                            ctx.lineWidth = 2;
                            ctx.stroke();
                        }
                        
                        segmentStart = i + 1;
                    }
                }
            }
        }
    }
    
    // 사용자 음정 히스토리 표시 (실제로 부른 음)
    // 리셋 후 pitchHistory가 비어있으면 그리지 않음
    if (pitchHistory && pitchHistory.length > 0 && isPlaying && musicPlayer) {
        const currentTime = musicPlayer.currentTime;
        const previewDuration = 3;
        const pastDuration = 1;
        const startTime = Math.max(0, currentTime - pastDuration);
        const endTime = currentTime + previewDuration;
        const timeRange = endTime - startTime;
        
        if (timeRange <= 0) return; // 시간 범위가 유효하지 않으면 건너뛰기
        
        // 사용자 음정 점들 수집
        const userPoints = [];
        
        pitchHistory.forEach((point) => {
            if (point.user && point.time !== undefined && 
                point.time >= startTime && point.time <= endTime) {
                const x = padding + (point.time - startTime) / timeRange * staffWidth;
                const userMidi = frequencyToMidi(point.user);
                const userY = midiToStaffY(userMidi, minMidi, maxMidi, canvasTop, canvasBottom);
                if (userY !== null) {
                    userPoints.push({ x, y: userY, pitch: point.user, midi: userMidi });
                }
            }
        });
        
        // 같은 음 구간을 막대로 표시, 다른 음은 점으로 표시
        if (userPoints.length > 0) {
            const SAME_NOTE_THRESHOLD = 50; // 센트 단위 (50센트 = 반음의 절반)
            
            // 같은 음 구간 찾기
            let segmentStart = 0;
            
            for (let i = 0; i < userPoints.length; i++) {
                const isLast = i === userPoints.length - 1;
                const isDifferentNote = !isLast && 
                    Math.abs(1200 * Math.log2(userPoints[i + 1].pitch / userPoints[i].pitch)) > SAME_NOTE_THRESHOLD;
                
                // 구간이 끝나거나 마지막 점이면
                if (isDifferentNote || isLast) {
                    const segmentEnd = isLast ? i : i;
                    const segmentPoints = userPoints.slice(segmentStart, segmentEnd + 1);
                    
                    if (segmentPoints.length > 1) {
                        // 같은 음 구간: 양옆이 둥근 막대로 표시
                        const startX = segmentPoints[0].x;
                        const endX = segmentPoints[segmentPoints.length - 1].x;
                        const y = segmentPoints[0].y;
                        const barHeight = 8; // 막대 높이
                        
                        // 둥근 직사각형으로 그리기
                        ctx.fillStyle = 'rgba(255, 215, 0, 0.8)';
                        const width = endX - startX;
                        const radius = barHeight / 2; // 반지름 = 높이의 절반
                        
                        ctx.beginPath();
                        // 왼쪽 반원
                        ctx.arc(startX, y, radius, Math.PI / 2, Math.PI * 3 / 2, false);
                        // 위쪽 직선
                        ctx.lineTo(startX + width, y - radius);
                        // 오른쪽 반원
                        ctx.arc(endX, y, radius, Math.PI * 3 / 2, Math.PI / 2, false);
                        // 아래쪽 직선
                        ctx.lineTo(startX, y + radius);
                        ctx.closePath();
                        ctx.fill();
                    } else {
                        // 단일 점: 점으로 표시
                        const point = segmentPoints[0];
                        ctx.fillStyle = '#ffd700';
                        ctx.beginPath();
                        ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    
                    segmentStart = i + 1;
                }
            }
        }
    }
    
    // 현재 시간 표시선 (재생 중일 때만)
    if (isPlaying && musicPlayer && !musicPlayer.paused) {
        const currentTime = musicPlayer.currentTime;
        const previewDuration = 3;
        const pastDuration = 1;
        const startTime = Math.max(0, currentTime - pastDuration);
        const endTime = currentTime + previewDuration;
        const timeRange = endTime - startTime;
        
        if (timeRange > 0) {
            const currentX = padding + (currentTime - startTime) / timeRange * staffWidth;
            
            ctx.strokeStyle = '#ff0000';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(currentX, canvasTop);
            ctx.lineTo(currentX, canvasBottom);
            ctx.stroke();
        }
    }
    
    // 범례
    ctx.font = '12px Arial';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#64c8ff';
    ctx.fillText('목표', padding + 10, staffTop - 10);
    ctx.fillStyle = '#ffd700';
    ctx.fillText('사용자', padding + 60, staffTop - 10);
}

// 시작 버튼
startBtn.addEventListener('click', async () => {
    console.log('시작 버튼 클릭됨');
    
    try {
        if (!audioContext) {
            console.log('AudioContext 초기화 필요');
            const success = await initAudioContext();
            if (!success) {
                console.error('AudioContext 초기화 실패');
                return;
            }
        }
        
        if (audioContext.state === 'suspended') {
            console.log('AudioContext 재개 중...');
            await audioContext.resume();
        }
        
        console.log('마이크 설정 시도...');
        const micSuccess = await setupMicrophone();
        if (!micSuccess) {
            console.error('마이크 설정 실패');
            return;
        }
    
        console.log('음악 재생 시작...');
        musicPlayer.volume = volumeSlider.value / 100;
        musicPlayer.play();
        
        console.log('음악 분석 시작...');
        await analyzeMusic();
        
        isPlaying = true;
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusElement.textContent = '녹음 중';
        
        // timeupdate 이벤트로 강제 업데이트 (실시간 동기화)
        musicPlayer.addEventListener('timeupdate', () => {
            if (isPlaying) {
                // drawStaff만 호출 (빠른 업데이트)
                try {
                    drawStaff();
                } catch (error) {
                    console.error('drawStaff 오류:', error);
                }
            }
        });
        
        console.log('분석 및 렌더링 시작...');
        analyzeAndRender();
    } catch (error) {
        console.error('시작 버튼 처리 중 오류:', error);
        alert('오류가 발생했습니다: ' + error.message);
        statusElement.textContent = '오류 발생';
    }
});

// 중지 버튼
stopBtn.addEventListener('click', () => {
    isPlaying = false;
    musicPlayer.pause();
    
    if (micSource) {
        micSource.disconnect();
        micSource.mediaStream.getTracks().forEach(track => track.stop());
        micSource = null;
    }
    
    // musicSource 정리 (MediaStreamSource인 경우만 연결 해제)
    if (musicSource && musicSource.mediaStream) {
        musicSource.disconnect();
        musicSource = null;
    }
    if (musicAnalyser) {
        musicAnalyser = null;
    }
    
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
    }
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusElement.textContent = '중지됨';
});

// 반주 점프 버튼
skipBtn.addEventListener('click', () => {
    console.log('========================================');
    console.log('[반주 점프] 버튼 클릭됨!');
    console.log('========================================');
    
    if (!isPlaying) {
        console.log('[반주 점프] ❌ 재생 중이 아닙니다.');
        return;
    }
    
    if (pitchTimeline.length === 0) {
        console.log('[반주 점프] ❌ 타임라인 데이터가 없습니다.');
        console.log('   pitchTimeline 길이:', pitchTimeline.length);
        return;
    }
    
    const currentTime = musicPlayer.currentTime;
    console.log(`[반주 점프] 현재 시간: ${currentTime.toFixed(2)}초`);
    console.log(`[반주 점프] 타임라인 데이터 개수: ${pitchTimeline.length}개`);
    
    // 현재 시간 이후의 첫 번째 보컬 구간 찾기 (이미 지난 반주는 무시)
    console.log(`[반주 점프] 다음 보컬 찾는 중...`);
    const nextVocalTime = findNextVocalStartTime(currentTime);
    
    console.log(`[반주 점프] 찾은 다음 보컬 시간: ${nextVocalTime !== null ? nextVocalTime.toFixed(2) + '초' : 'null'}`);
    
    if (nextVocalTime === null) {
        console.log('[반주 점프] ❌ 다음 보컬 구간을 찾을 수 없습니다.');
        
        // 디버깅: 타임라인 확인
        const allVocals = pitchTimeline.filter(p => p.pitch !== null);
        console.log(`[반주 점프] 전체 보컬 구간 개수: ${allVocals.length}개`);
        if (allVocals.length > 0) {
            const firstVocal = allVocals[0];
            const lastVocal = allVocals[allVocals.length - 1];
            console.log(`[반주 점프] 첫 보컬: ${firstVocal.time.toFixed(2)}초, 마지막 보컬: ${lastVocal.time.toFixed(2)}초`);
            console.log(`[반주 점프] 현재 시간(${currentTime.toFixed(2)}초)이 마지막 보컬(${lastVocal.time.toFixed(2)}초) 이후입니다.`);
        }
        return;
    }
    
    if (nextVocalTime <= currentTime) {
        console.log(`[반주 점프] ⚠️ 다음 보컬(${nextVocalTime.toFixed(2)}초)이 현재 시간(${currentTime.toFixed(2)}초)보다 이전입니다.`);
        return;
    }
    
    // 보컬 시작 1초 전으로 점프
    const jumpTime = Math.max(0, nextVocalTime - 1.0);
    
    console.log(`[반주 점프] 🎯 점프 계산:`);
    console.log(`   현재 시간: ${currentTime.toFixed(2)}초`);
    console.log(`   다음 보컬 시작: ${nextVocalTime.toFixed(2)}초`);
    console.log(`   점프할 시간: ${jumpTime.toFixed(2)}초 (보컬 시작 1초 전)`);
    
    // currentTime 설정 전
    const beforeTime = musicPlayer.currentTime;
    console.log(`[반주 점프] musicPlayer.currentTime 설정 전: ${beforeTime.toFixed(2)}초`);
    
    // currentTime 설정
    musicPlayer.currentTime = jumpTime;
    
    // 즉시 확인
    const immediateTime = musicPlayer.currentTime;
    console.log(`[반주 점프] musicPlayer.currentTime 설정 직후: ${immediateTime.toFixed(2)}초`);
    
    // timeupdate 이벤트로 확인
    let checkCount = 0;
    const checkTime = () => {
        checkCount++;
        const actualTime = musicPlayer.currentTime;
        const diff = Math.abs(actualTime - jumpTime);
        console.log(`[반주 점프] ✅ timeupdate 이벤트 #${checkCount}: ${actualTime.toFixed(2)}초 (차이: ${diff.toFixed(2)}초)`);
        
        if (diff > 1.0) {
            console.warn(`[반주 점프] ⚠️ 경고: 예상(${jumpTime.toFixed(2)}초)과 실제(${actualTime.toFixed(2)}초)가 많이 다릅니다!`);
        }
        
        // 3번 확인 후 이벤트 제거
        if (checkCount >= 3) {
            musicPlayer.removeEventListener('timeupdate', checkTime);
            console.log(`[반주 점프] ========================================`);
        }
    };
    
    musicPlayer.addEventListener('timeupdate', checkTime);
    
    // setTimeout으로도 확인 (백업)
    setTimeout(() => {
        const actualTime = musicPlayer.currentTime;
        const diff = Math.abs(actualTime - jumpTime);
        console.log(`[반주 점프] ⏰ setTimeout 확인: ${actualTime.toFixed(2)}초 (차이: ${diff.toFixed(2)}초)`);
    }, 500);
});

// 리셋 버튼
resetBtn.addEventListener('click', () => {
    isPlaying = false;
    practiceMode = false;
    practiceSegment = null;
    isCountingDown = false;
    musicPlayer.pause();
    musicPlayer.currentTime = 0;
    
    // 애니메이션 프레임 취소
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    
    // 마이크 스트림 완전히 정리
    if (micSource) {
        try {
            micSource.disconnect();
            if (micSource.mediaStream) {
                micSource.mediaStream.getTracks().forEach(track => {
                    track.stop();
                    track.enabled = false;
                });
            }
        } catch (e) {
            console.error('마이크 정리 오류:', e);
        }
        micSource = null;
    }
    
    // 마이크 분석기 정리
    if (micAnalyser) {
        try {
            micAnalyser.disconnect();
        } catch (e) {
            console.error('마이크 분석기 정리 오류:', e);
        }
        micAnalyser = null;
    }
    
    // musicSource 정리 (MediaStreamSource인 경우만 연결 해제)
    if (musicSource) {
        try {
            if (musicSource.mediaStream) {
                musicSource.disconnect();
            }
        } catch (e) {
            console.error('음악 소스 정리 오류:', e);
        }
        musicSource = null;
    }
    
    if (musicAnalyser) {
        try {
            musicAnalyser.disconnect();
        } catch (e) {
            console.error('음악 분석기 정리 오류:', e);
        }
        musicAnalyser = null;
    }
    
    // AudioContext 정리 (선택적 - 재사용을 위해 유지할 수도 있음)
    // audioContext = null; // 필요시 주석 해제
    
    // 모든 데이터 리셋
    pitchHistory = [];
    totalScore = 0;
    scoreCount = 0;
    lastTargetNoteName = null;
    lastTargetPitch = null;
    lastAPICall = 0;
    
    // UI 리셋
    scoreElement.textContent = '0';
    accuracyElement.textContent = '0%';
    scoreBarFill.style.width = '0%';
    currentPitchElement.textContent = '-';
    targetPitchElement.textContent = '-';
    statusElement.textContent = '대기 중';
    
    // 스타일 리셋 (카운트다운 스타일 제거)
    targetPitchElement.style.fontSize = '';
    targetPitchElement.style.color = '';
    targetPitchElement.style.textAlign = '';
    
    // Canvas 리셋 (사용자 음정 히스토리 제거)
    ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    // 배경색 다시 그리기
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    // 빈 악보 그리기 (pitchHistory가 비어있으므로 사용자 음정은 안 그려짐)
    drawStaff();
    
    // 버튼 상태 리셋
    startBtn.disabled = false;
    stopBtn.disabled = true;
    
    console.log('✅ 리셋 완료');
});

// 볼륨 슬라이더
volumeSlider.addEventListener('input', (e) => {
    const volume = e.target.value;
    musicPlayer.volume = volume / 100;
    volumeValue.textContent = `${volume}%`;
});

// 윈도우 리사이즈 시 Canvas 크기 조정
window.addEventListener('resize', () => {
    pitchCanvas.width = pitchCanvas.offsetWidth;
    pitchCanvas.height = pitchCanvas.offsetHeight;
    drawStaff();
});

// 타임라인 음정 데이터 로드
async function loadPitchTimeline() {
    try {
        console.log('타임라인 음정 데이터 로드 중...');
        // 캐시 방지를 위해 타임스탬프 추가
        const response = await fetch(`${API_BASE_URL}/api/pitch-timeline?t=${Date.now()}`);
        const data = await response.json();
        
        if (data.success && data.timeline) {
            pitchTimeline = data.timeline;
            musicMetadata = data.metadata || null; // 메타데이터 저장
            console.log(`✅ 타임라인 데이터 로드 완료: ${pitchTimeline.length}개 포인트`);
            if (musicMetadata) {
                console.log(`  BPM: ${musicMetadata.bpm}`);
                console.log(`  박자 수: ${musicMetadata.beat_times ? musicMetadata.beat_times.length : 0}개`);
            }
            
            // 유효한 pitch 값이 있는 데이터 포인트 개수 확인
            const validPitches = pitchTimeline.filter(p => p.pitch !== null && p.pitch !== undefined);
            const nullPitches = pitchTimeline.filter(p => p.pitch === null || p.pitch === undefined);
            console.log(`  유효한 음정(보컬): ${validPitches.length}개`);
            console.log(`  반주 구간(null): ${nullPitches.length}개`);
            
            // 보컬 시작 시점들 찾기
            const vocalStarts = [];
            for (let i = 0; i < pitchTimeline.length; i++) {
                if (pitchTimeline[i].pitch !== null && 
                    (i === 0 || pitchTimeline[i-1].pitch === null)) {
                    vocalStarts.push(pitchTimeline[i].time);
                }
            }
            console.log(`  보컬 시작 시점: ${vocalStarts.length}개 구간`);
            if (vocalStarts.length > 0) {
                console.log(`  첫 보컬: ${vocalStarts[0].toFixed(2)}초`);
                console.log(`  다음 보컬들: ${vocalStarts.slice(1, 6).map(t => t.toFixed(2)).join(', ')}초`);
            }
            
            if (validPitches.length > 0) {
                console.log('  첫 5개 유효한 데이터:', validPitches.slice(0, 5));
            } else {
                console.warn('⚠️ 유효한 음정 데이터가 없습니다!');
            }
        } else {
            console.warn('❌ 타임라인 데이터가 없습니다. perfect_vocal_score.py를 실행하세요.');
            console.warn(data.error || '알 수 없는 오류');
        }
    } catch (error) {
        console.error('❌ 타임라인 데이터 로드 실패:', error);
    }
}

// 구간별 연습 관련 변수
let practiceMode = false;
let practiceSegment = null;
let segmentScores = []; // 구간별 점수 저장
let countdownInterval = null;
let isCountingDown = false;

// DOM 요소 (구간별 연습)
const practiceSection = document.getElementById('practiceSection');
const segmentSelect = document.getElementById('segmentSelect');
const practiceBtn = document.getElementById('practiceBtn');
const resultModal = document.getElementById('resultModal');
const countdownModal = document.getElementById('countdownModal');
const countdownNumber = document.getElementById('countdownNumber');
const closeResultBtn = document.getElementById('closeResultBtn');
const practiceAgainBtn = document.getElementById('practiceAgainBtn');
const closeModalBtn = document.querySelector('.close');

// 노래 종료 시 전체 분석 결과 표시
musicPlayer.addEventListener('ended', () => {
    if (isPlaying) {
        isPlaying = false;
        showFinalResults();
    }
});

// 전체 분석 결과 계산 및 표시
function showFinalResults() {
    if (pitchHistory.length === 0) {
        alert('분석할 데이터가 없습니다.');
        return;
    }
    
    // 전체 점수 계산
    const finalScore = scoreCount > 0 ? Math.round(totalScore / scoreCount) : 0;
    const finalAccuracy = finalScore; // 점수 = 정확도
    
    // 구간별 분석
    const segments = analyzeBySegments();
    
    // 모달 내용 업데이트
    document.getElementById('finalScore').textContent = finalScore;
    document.getElementById('finalAccuracy').textContent = `${finalAccuracy}%`;
    document.getElementById('analyzedSegments').textContent = `${segments.length}개`;
    
    // 구간별 상세 결과
    const detailsDiv = document.getElementById('resultDetails');
    detailsDiv.innerHTML = '';
    
    segments.forEach((segment, index) => {
        const segmentDiv = document.createElement('div');
        segmentDiv.className = 'segment-result';
        segmentDiv.innerHTML = `
            <h4>구간 ${index + 1}: ${segment.startTime.toFixed(1)}초 ~ ${segment.endTime.toFixed(1)}초</h4>
            <p>점수: ${segment.score}점 | 정확도: ${segment.accuracy.toFixed(1)}%</p>
            <p>분석된 음정: ${segment.count}개</p>
        `;
        detailsDiv.appendChild(segmentDiv);
    });
    
    // 모달 표시
    resultModal.style.display = 'block';
}

// 구간별 분석
function analyzeBySegments() {
    if (pitchHistory.length === 0) return [];
    
    // 10초 단위로 구간 나누기
    const segmentDuration = 10; // 10초
    const segments = [];
    const maxTime = Math.max(...pitchHistory.map(p => p.time));
    
    for (let startTime = 0; startTime < maxTime; startTime += segmentDuration) {
        const endTime = Math.min(startTime + segmentDuration, maxTime);
        const segmentData = pitchHistory.filter(p => p.time >= startTime && p.time < endTime);
        
        if (segmentData.length > 0) {
            let segmentScore = 0;
            let segmentCount = 0;
            
            segmentData.forEach(point => {
                if (point.user && point.target) {
                    const diff = Math.abs(1200 * Math.log2(point.user / point.target));
                    let score = 0;
                    
                    if (diff <= 5) score = 100 - (diff * 0.5);
                    else if (diff <= 10) score = 97.5 - ((diff - 5) * 0.5);
                    else if (diff <= 20) score = 95 - ((diff - 10) * 1.0);
                    else if (diff <= 30) score = 85 - ((diff - 20) * 1.5);
                    else if (diff <= 50) score = 70 - ((diff - 30) * 0.4);
                    
                    segmentScore += score;
                    segmentCount++;
                }
            });
            
            const avgScore = segmentCount > 0 ? segmentScore / segmentCount : 0;
            
            segments.push({
                startTime,
                endTime,
                score: Math.round(avgScore),
                accuracy: avgScore,
                count: segmentCount
            });
        }
    }
    
    return segments;
}

// 박자표 감지 (beat_times 간격 분석)
function detectTimeSignature(beatTimes) {
    if (!beatTimes || beatTimes.length < 8) {
        return { numerator: 4, denominator: 4 }; // 기본값 4/4
    }
    
    // 박자 간격 계산
    const intervals = [];
    for (let i = 1; i < Math.min(beatTimes.length, 20); i++) {
        intervals.push(beatTimes[i] - beatTimes[i - 1]);
    }
    
    // 평균 박자 간격
    const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    
    // 강박 패턴 찾기 (간격이 더 긴 부분 = 강박)
    // 간단하게 4/4를 가정 (대부분의 팝/록 음악)
    // 더 정교한 감지는 librosa의 onset detection 필요
    
    return { numerator: 4, denominator: 4 }; // 기본값 4/4
}

// 마디 단위 구간 생성 (4마디씩 묶기)
function createMeasureSegments(beatTimes, timeSignature) {
    if (!beatTimes || beatTimes.length === 0) {
        return [];
    }
    
    const measures = [];
    const beatsPerMeasure = timeSignature.numerator; // 4/4면 4
    const measuresPerSegment = 4; // 4마디씩 묶기
    
    // beat_times를 4마디씩 묶어서 구간으로 만들기
    for (let i = 0; i < beatTimes.length; i += beatsPerMeasure * measuresPerSegment) {
        const segmentStart = beatTimes[i];
        const segmentEndBeatIndex = Math.min(i + (beatsPerMeasure * measuresPerSegment), beatTimes.length - 1);
        const segmentEnd = beatTimes[segmentEndBeatIndex];
        
        // 해당 구간(4마디)에 보컬이 있는지 확인
        const hasVocal = pitchTimeline.some(point => 
            point.pitch !== null && 
            point.time >= segmentStart && 
            point.time < segmentEnd
        );
        
        // 보컬이 있는 구간만 추가
        if (hasVocal) {
            const startMeasureNumber = Math.floor(i / beatsPerMeasure) + 1;
            const endMeasureNumber = Math.floor(segmentEndBeatIndex / beatsPerMeasure) + 1;
            
            measures.push({
                start: segmentStart,
                end: segmentEnd,
                measureNumber: startMeasureNumber,
                endMeasureNumber: endMeasureNumber
            });
        }
    }
    
    return measures;
}

// 구간 선택 옵션 생성 (마디 단위)
function populateSegmentSelect() {
    if (pitchTimeline.length === 0) return;
    
    segmentSelect.innerHTML = '<option value="">전체 연주</option>';
    
    // 메타데이터에서 beat_times 가져오기
    if (musicMetadata && musicMetadata.beat_times && musicMetadata.beat_times.length > 0) {
        const beatTimes = musicMetadata.beat_times;
        
        // 박자표 감지
        const timeSignature = detectTimeSignature(beatTimes);
        console.log(`박자표 감지: ${timeSignature.numerator}/${timeSignature.denominator}`);
        
        // 마디 단위 구간 생성
        const measures = createMeasureSegments(beatTimes, timeSignature);
        
        console.log(`마디 구간 생성: ${measures.length}개 마디`);
        
        // 옵션 추가
        measures.forEach((measure, index) => {
            const option = document.createElement('option');
            option.value = index;
            const measureLabel = measure.endMeasureNumber 
                ? `마디 ${measure.measureNumber}-${measure.endMeasureNumber}`
                : `마디 ${measure.measureNumber}`;
            option.textContent = `${measureLabel}: ${measure.start.toFixed(1)}초 ~ ${measure.end.toFixed(1)}초`;
            option.dataset.start = measure.start;
            option.dataset.end = measure.end;
            segmentSelect.appendChild(option);
        });
    } else {
        // beat_times가 없으면 기존 방식 사용 (보컬 구간)
        console.warn('⚠️ beat_times 정보가 없어 기존 방식으로 구간을 나눕니다.');
        
        const vocalSegments = [];
        let segmentStart = null;
        
        for (let i = 0; i < pitchTimeline.length; i++) {
            const point = pitchTimeline[i];
            
            if (point.pitch !== null) {
                if (segmentStart === null) {
                    segmentStart = point.time;
                }
            } else {
                if (segmentStart !== null) {
                    const prevPoint = pitchTimeline[i - 1];
                    vocalSegments.push({
                        start: segmentStart,
                        end: prevPoint.time,
                        label: `${segmentStart.toFixed(1)}초 ~ ${prevPoint.time.toFixed(1)}초`
                    });
                    segmentStart = null;
                }
            }
        }
        
        // 마지막 구간 처리
        if (segmentStart !== null) {
            const lastPoint = pitchTimeline[pitchTimeline.length - 1];
            vocalSegments.push({
                start: segmentStart,
                end: lastPoint.time,
                label: `${segmentStart.toFixed(1)}초 ~ ${lastPoint.time.toFixed(1)}초`
            });
        }
        
        // 옵션 추가
        vocalSegments.forEach((segment, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = `구간 ${index + 1}: ${segment.label}`;
            option.dataset.start = segment.start;
            option.dataset.end = segment.end;
            segmentSelect.appendChild(option);
        });
    }
}

// 카운트다운 표시 (악보 Canvas에 표시)
function showCountdown(count, callback) {
    isCountingDown = true;
    
    // Canvas에 카운트다운 그리기
    const drawCountdown = () => {
        ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
        
        // 배경색 설정
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, pitchCanvas.width, pitchCanvas.height);
        
        // 카운트다운 숫자 표시
        ctx.fillStyle = '#ffd700';
        ctx.font = 'bold 120px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.shadowColor = 'rgba(255, 215, 0, 0.8)';
        ctx.shadowBlur = 20;
        ctx.fillText(count.toString(), pitchCanvas.width / 2, pitchCanvas.height / 2);
        ctx.shadowBlur = 0;
    };
    
    drawCountdown();
    
    if (count > 1) {
        // 다음 카운트다운
        setTimeout(() => {
            showCountdown(count - 1, callback);
        }, 1000);
    } else {
        // 카운트다운 완료
        setTimeout(() => {
            isCountingDown = false;
            // 원래 악보 그리기
            drawStaff();
            if (callback) callback();
        }, 1000);
    }
}

// 구간별 연습 시작
practiceBtn.addEventListener('click', async () => {
    const selectedIndex = segmentSelect.value;
    
    if (selectedIndex === '') {
        practiceMode = false;
        practiceSegment = null;
        alert('구간을 선택해주세요.');
        return;
    }
    
    const selectedOption = segmentSelect.options[segmentSelect.selectedIndex];
    const segmentStart = parseFloat(selectedOption.dataset.start);
    const segmentEnd = parseFloat(selectedOption.dataset.end);
    
    // 구간 시작 -1초 ~ 구간 끝까지
    practiceSegment = {
        start: Math.max(0, segmentStart - 1.0), // 최소 0초
        end: segmentEnd
    };
    
    practiceMode = true;
    
    // 오디오 컨텍스트 초기화 확인
    if (!audioContext) {
        const success = await initAudioContext();
        if (!success) {
            alert('오디오 초기화에 실패했습니다.');
            return;
        }
    }
    
    // 마이크 설정 확인
    if (!micSource) {
        const micSuccess = await setupMicrophone();
        if (!micSuccess) {
            alert('마이크 설정에 실패했습니다.');
            return;
        }
    }
    
    // 선택한 구간으로 이동 (재생은 하지 않음)
    musicPlayer.currentTime = practiceSegment.start;
    musicPlayer.pause();
    
    // 카운트다운 시작 (악보 Canvas에 표시)
    showCountdown(3, () => {
        // 카운트다운 후 재생 시작
        musicPlayer.currentTime = practiceSegment.start;
        musicPlayer.play();
        
        if (!isPlaying) {
            isPlaying = true;
            startBtn.disabled = true;
            stopBtn.disabled = false;
            statusElement.textContent = '구간 연습 중';
            analyzeAndRender();
        }
    });
});

// 구간 연습 모드에서 구간 끝나면 반복
let lastPracticeCheck = 0;
musicPlayer.addEventListener('timeupdate', () => {
    if (practiceMode && practiceSegment && !isCountingDown) {
        const currentTime = musicPlayer.currentTime;
        
        // 구간이 끝나면 일시정지하고 카운트다운 시작 (중복 방지)
        if (currentTime >= practiceSegment.end && currentTime - lastPracticeCheck > 0.5) {
            lastPracticeCheck = currentTime;
            musicPlayer.pause();
            
            // 해당 구간 범위 밖의 pitchHistory 제거 (이전 반복 데이터 삭제)
            if (pitchHistory.length > 0) {
                pitchHistory = pitchHistory.filter(point => 
                    point.time < practiceSegment.start || point.time > practiceSegment.end
                );
                // 구간 밖 데이터도 모두 제거 (깨끗하게 시작)
                pitchHistory = [];
            }
            
            // 점수도 리셋 (구간별로 독립적으로 측정)
            totalScore = 0;
            scoreCount = 0;
            scoreElement.textContent = '0';
            accuracyElement.textContent = '0%';
            scoreBarFill.style.width = '0%';
            
            // Canvas 초기화 (이전 그림 제거)
            ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0, 0, pitchCanvas.width, pitchCanvas.height);
            
            musicPlayer.currentTime = practiceSegment.start;
            
            // 카운트다운 후 다시 재생
            showCountdown(3, () => {
                musicPlayer.currentTime = practiceSegment.start;
                musicPlayer.play();
            });
        }
    }
});

// 모달 닫기
if (closeModalBtn) {
    closeModalBtn.addEventListener('click', () => {
        resultModal.style.display = 'none';
    });
}

if (closeResultBtn) {
    closeResultBtn.addEventListener('click', () => {
        resultModal.style.display = 'none';
    });
}

if (practiceAgainBtn) {
    practiceAgainBtn.addEventListener('click', () => {
        resultModal.style.display = 'none';
        resetBtn.click();
    });
}

// 페이지 로드 시 초기화
window.addEventListener('DOMContentLoaded', () => {
    console.log('페이지 로드 완료');
    console.log('시작 버튼:', startBtn);
    console.log('navigator.mediaDevices:', navigator.mediaDevices);
    
    // 타임라인 데이터 로드
    loadPitchTimeline().then(() => {
        // 구간 선택 옵션 생성
        populateSegmentSelect();
        
        // 구간별 연습 섹션 표시
        if (practiceSection) {
            practiceSection.style.display = 'block';
        }
    });
    
    // AudioContext는 사용자 상호작용(버튼 클릭) 전까지 초기화하지 않음
    // (브라우저 정책: 사용자 상호작용 후에만 오디오 컨텍스트 생성 가능)
});

