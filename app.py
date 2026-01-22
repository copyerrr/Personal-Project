from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import numpy as np
from scipy import signal
import os
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 음정 감지 함수 (Autocorrelation 기반)
def detect_pitch(buffer, sample_rate, volume_threshold=0.003):
    """
    Autocorrelation을 사용하여 음정(주파수)을 감지합니다.
    
    Args:
        buffer: 오디오 신호 데이터 (numpy array)
        sample_rate: 샘플링 레이트 (Hz)
        volume_threshold: 최소 볼륨 임계값 (RMS)
    
    Returns:
        감지된 주파수 (Hz), 없으면 None
    """
    # 신호 강도(볼륨) 계산
    rms = np.sqrt(np.mean(buffer**2))
    if rms < volume_threshold:
        return None  # 너무 조용하면 음정 감지하지 않음
    
    # 최소/최대 주기 설정 (80Hz ~ 800Hz 범위)
    min_period = int(sample_rate / 800)  # 최소 주기 (최대 800Hz)
    max_period = int(sample_rate / 80)   # 최대 주기 (최소 80Hz)
    
    if len(buffer) < max_period:
        return None
    
    best_period = 0
    best_correlation = 0
    
    # Autocorrelation 계산
    for period in range(min_period, max_period):
        correlation = np.corrcoef(buffer[:-period], buffer[period:])[0, 1]
        if not np.isnan(correlation) and correlation > best_correlation:
            best_correlation = correlation
            best_period = period
    
    if best_period > 0 and best_correlation > 0.15:  # 임계값 상향
        return sample_rate / best_period
    
    return None

# 두 주파수 간 차이 계산 (센트 단위)
def frequency_difference(freq1, freq2):
    """
    두 주파수 간의 차이를 센트 단위로 계산합니다.
    
    Args:
        freq1: 첫 번째 주파수 (Hz)
        freq2: 두 번째 주파수 (Hz)
    
    Returns:
        센트 차이
    """
    if not freq1 or not freq2 or freq1 <= 0 or freq2 <= 0:
        return None
    return 1200 * np.log2(freq2 / freq1)

# 점수 계산 함수 (개선된 버전)
def calculate_score(user_pitch, target_pitch):
    """
    사용자 음정과 목표 음정을 비교하여 점수를 계산합니다.
    노래방 시스템처럼 더 정교한 평가를 수행합니다.
        
    Args:
        user_pitch: 사용자 음정 (Hz)
        target_pitch: 목표 음정 (Hz)
    
    Returns:
        점수 (0-100)
    """
    if not user_pitch or not target_pitch:
        return 0
    
    diff = abs(frequency_difference(user_pitch, target_pitch))
    
    # 노래방 스타일 점수 계산
    # - 0센트 (완벽): 100점
    # - 10센트 이하 (거의 완벽): 95점 이상
    # - 20센트 이하 (좋음): 85점 이상
    # - 30센트 이하 (보통): 70점 이상
    # - 50센트 이하 (나쁨): 50점 이상
    # - 50센트 초과: 0점
    
    if diff <= 5:  # 5센트 이하: 거의 완벽
        score = 100 - (diff * 0.5)  # 100 ~ 97.5점
    elif diff <= 10:  # 10센트 이하: 매우 좋음
        score = 97.5 - ((diff - 5) * 0.5)  # 97.5 ~ 95점
    elif diff <= 20:  # 20센트 이하: 좋음
        score = 95 - ((diff - 10) * 1.0)  # 95 ~ 85점
    elif diff <= 30:  # 30센트 이하: 보통
        score = 85 - ((diff - 20) * 1.5)  # 85 ~ 70점
    elif diff <= 50:  # 50센트 이하: 나쁨
        score = 70 - ((diff - 30) * 1.0)  # 70 ~ 50점
    else:  # 50센트 초과: 매우 나쁨
        score = max(0, 50 - ((diff - 50) * 1.0))  # 50 ~ 0점
    
    return int(round(score))

# 음정 분석 API 엔드포인트
@app.route('/api/analyze-pitch', methods=['POST'])
def analyze_pitch():
    """
    음정 분석 및 점수 계산 API
    
    Request Body:
        {
            "audioData": [0.1, 0.2, 0.3, ...],  # 오디오 데이터 배열
            "sampleRate": 44100,                # 샘플링 레이트
            "targetPitch": 440                  # 목표 음정 (옵션)
        }
    
    Returns:
        {
            "success": true,
            "userPitch": 440,
            "targetPitch": 440,
            "score": 100,
            "accuracy": 100
        }
    """
    try:
        data = request.get_json()
        
        if not data or 'audioData' not in data:
            return jsonify({'error': '올바른 오디오 데이터가 필요합니다.'}), 400
        
        audio_data = np.array(data['audioData'], dtype=np.float32)
        sample_rate = data.get('sampleRate', 44100)
        target_pitch = data.get('targetPitch', None)
        
        # 사용자 음정 감지
        user_pitch = detect_pitch(audio_data, sample_rate)
        
        # 점수 계산
        score = 0
        accuracy = 0
        
        if user_pitch and target_pitch:
            score = calculate_score(user_pitch, target_pitch)
            accuracy = score
        
        return jsonify({
            'success': True,
            'userPitch': int(round(user_pitch)) if user_pitch else None,
            'targetPitch': int(round(target_pitch)) if target_pitch else None,
            'score': score,
            'accuracy': accuracy
        })
        
    except Exception as e:
        print(f'음정 분석 오류: {str(e)}')
        return jsonify({'error': '음정 분석 중 오류가 발생했습니다.'}), 500

# 타임라인 음정 데이터 로드 API
@app.route('/api/pitch-timeline', methods=['GET'])
def get_pitch_timeline():
    """
    미리 분석된 타임라인별 음정 데이터를 반환합니다.
    새로운 형식(metadata 포함)과 기존 형식 모두 지원합니다.
    """
    try:
        timeline_file = 'static/assets/music_pitch_data.json'
        if os.path.exists(timeline_file):
            with open(timeline_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 새로운 형식 (metadata 포함)인지 확인
            if isinstance(data, dict) and 'timeline' in data:
                timeline_data = data['timeline']
                metadata = data.get('metadata', {})
            else:
                # 기존 형식 (리스트)
                timeline_data = data
                metadata = {}
            
            return jsonify({
                'success': True,
                'timeline': timeline_data,
                'metadata': metadata  # BPM, beat_times 등
            })
        else:
            return jsonify({
                'success': False,
                'error': '타임라인 데이터가 없습니다. auto_analyze.py를 먼저 실행하세요.'
            }), 404
    except Exception as e:
        print(f'타임라인 데이터 로드 오류: {str(e)}')
        return jsonify({'error': '타임라인 데이터 로드 실패'}), 500

# 디버그 로그 API
@app.route('/api/debug-log', methods=['POST'])
def debug_log():
    """브라우저에서 보낸 디버그 로그를 터미널에 출력"""
    try:
        data = request.json
        log_message = data.get('message', '')
        log_level = data.get('level', 'INFO')
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f'[{timestamp}] [{log_level}] {log_message}')
        
        return jsonify({'success': True})
    except Exception as e:
        print(f'[ERROR] 로그 수신 오류: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# 메인 페이지 (Flask 템플릿 사용)
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    # 개발 서버 실행
    app.run(host='0.0.0.0', port=5000, debug=True)

