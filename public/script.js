// 전역 변수
let audioContext;
let musicSource;
let micSource;
let musicAnalyser;
let micAnalyser;
let isPlaying = false;
let animationFrameId;
let pitchHistory = [];
let lastAPICall = 0;
const API_CALL_INTERVAL = 100; // 100ms마다 API 호출 (초당 10회)

// DOM 요소
const musicPlayer = document.getElementById('musicPlayer');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const resetBtn = document.getElementById('resetBtn');
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
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        return true;
    } catch (error) {
        console.error('AudioContext 초기화 실패:', error);
        return false;
    }
}

// 백엔드 API URL
const API_BASE_URL = 'http://localhost:5000';

// 백엔드 API 호출 - 음정 분석
async function analyzePitchWithAPI(audioData, sampleRate, targetPitch) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze-pitch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                audioData: Array.from(audioData), // Float32Array를 일반 배열로 변환
                sampleRate: sampleRate,
                targetPitch: targetPitch
            })
        });
        
        if (!response.ok) {
            throw new Error('API 호출 실패');
        }
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('API 호출 오류:', error);
        return null;
    }
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
        // mediaDevices 지원 확인
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('이 브라우저는 마이크 접근을 지원하지 않습니다.\n최신 브라우저(Chrome, Edge, Firefox)를 사용해주세요.');
            return false;
        }
        
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });
        
        micSource = audioContext.createMediaStreamSource(stream);
        micAnalyser = audioContext.createAnalyser();
        micAnalyser.fftSize = 2048;
        micAnalyser.smoothingTimeConstant = 0.3;
        micSource.connect(micAnalyser);
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

// 실시간 분석 및 렌더링
async function analyzeAndRender() {
    if (!isPlaying) return;
    
    const now = Date.now();
    const bufferLength = micAnalyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const timeDomainArray = new Float32Array(micAnalyser.fftSize);
    
    // 마이크 데이터 가져오기
    micAnalyser.getByteFrequencyData(dataArray);
    micAnalyser.getFloatTimeDomainData(timeDomainArray);
    
    // 음악 목표 음정 감지 (간단한 FFT 기반 주파수 추출)
    let targetPitch = null;
    if (musicAnalyser) {
        const musicTimeDomain = new Float32Array(musicAnalyser.fftSize);
        musicAnalyser.getFloatTimeDomainData(musicTimeDomain);
        // 목표 음정은 클라이언트에서 감지하거나, 백엔드로 전송할 수 있습니다
        // 여기서는 간단한 주파수 추출 (실제로는 백엔드에서 처리하는 것이 더 정확)
    }
    
    // 일정 간격으로 백엔드 API 호출 (너무 자주 호출하지 않도록)
    if (now - lastAPICall >= API_CALL_INTERVAL) {
        lastAPICall = now;
        
        // 백엔드 API로 음정 분석 요청
        const result = await analyzePitchWithAPI(
            timeDomainArray,
            audioContext.sampleRate,
            targetPitch
        );
        
        if (result && result.success) {
            const userPitch = result.userPitch;
            const targetPitchFromAPI = result.targetPitch || targetPitch;
            const score = result.score || 0;
            const accuracy = result.accuracy || 0;
            
            // UI 업데이트
            if (userPitch) {
                currentPitchElement.textContent = `${userPitch} Hz`;
                pitchHistory.push({ 
                    user: userPitch, 
                    target: targetPitchFromAPI, 
                    time: now 
                });
                
                // 최근 100개만 유지
                if (pitchHistory.length > 100) {
                    pitchHistory.shift();
                }
            } else {
                currentPitchElement.textContent = '- Hz';
            }
            
            if (targetPitchFromAPI) {
                targetPitchElement.textContent = `${targetPitchFromAPI} Hz`;
            } else {
                targetPitchElement.textContent = '- Hz';
            }
            
            // 점수 표시
            scoreElement.textContent = score;
            accuracyElement.textContent = `${accuracy}%`;
            scoreBarFill.style.width = `${accuracy}%`;
        }
    }
    
    // 그래프 그리기 (실시간으로 업데이트)
    drawGraph();
    
    animationFrameId = requestAnimationFrame(analyzeAndRender);
}

// 그래프 그리기
function drawGraph() {
    ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    if (pitchHistory.length < 2) return;
    
    const padding = 20;
    const graphWidth = pitchCanvas.width - padding * 2;
    const graphHeight = pitchCanvas.height - padding * 2;
    
    // 배경 그리드
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (graphHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + graphWidth, y);
        ctx.stroke();
    }
    
    // 주파수 범위 설정 (80Hz ~ 800Hz)
    const minFreq = 80;
    const maxFreq = 800;
    
    // 목표 음정 그래프 (파란색)
    ctx.strokeStyle = 'rgba(100, 200, 255, 0.6)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    let firstTarget = true;
    
    pitchHistory.forEach((point, index) => {
        if (point.target) {
            const x = padding + (graphWidth / pitchHistory.length) * index;
            const normalizedFreq = (point.target - minFreq) / (maxFreq - minFreq);
            const y = padding + graphHeight - (normalizedFreq * graphHeight);
            
            if (firstTarget) {
                ctx.moveTo(x, y);
                firstTarget = false;
            } else {
                ctx.lineTo(x, y);
            }
        }
    });
    ctx.stroke();
    
    // 사용자 음정 그래프 (노란색/금색)
    ctx.strokeStyle = '#ffd700';
    ctx.lineWidth = 2;
    ctx.beginPath();
    let firstUser = true;
    
    pitchHistory.forEach((point, index) => {
        if (point.user) {
            const x = padding + (graphWidth / pitchHistory.length) * index;
            const normalizedFreq = (point.user - minFreq) / (maxFreq - minFreq);
            const y = padding + graphHeight - (normalizedFreq * graphHeight);
            
            if (firstUser) {
                ctx.moveTo(x, y);
                firstUser = false;
            } else {
                ctx.lineTo(x, y);
            }
        }
    });
    ctx.stroke();
    
    // 범례
    ctx.font = '12px Arial';
    ctx.fillStyle = 'rgba(100, 200, 255, 0.8)';
    ctx.fillText('목표 음정', padding + 10, padding + 15);
    ctx.fillStyle = '#ffd700';
    ctx.fillText('사용자 음정', padding + 100, padding + 15);
}

// 시작 버튼
startBtn.addEventListener('click', async () => {
    if (!audioContext) {
        const success = await initAudioContext();
        if (!success) return;
    }
    
    if (audioContext.state === 'suspended') {
        await audioContext.resume();
    }
    
    const micSuccess = await setupMicrophone();
    if (!micSuccess) return;
    
    musicPlayer.volume = volumeSlider.value / 100;
    musicPlayer.play();
    
    await analyzeMusic();
    
    isPlaying = true;
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusElement.textContent = '녹음 중';
    
    analyzeAndRender();
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

// 리셋 버튼
resetBtn.addEventListener('click', () => {
    isPlaying = false;
    musicPlayer.pause();
    musicPlayer.currentTime = 0;
    
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
    
    pitchHistory = [];
    scoreElement.textContent = '0';
    accuracyElement.textContent = '0%';
    scoreBarFill.style.width = '0%';
    currentPitchElement.textContent = '- Hz';
    targetPitchElement.textContent = '- Hz';
    statusElement.textContent = '대기 중';
    
    ctx.clearRect(0, 0, pitchCanvas.width, pitchCanvas.height);
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
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
    drawGraph();
});

// 초기화
initAudioContext();

