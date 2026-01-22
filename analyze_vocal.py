"""
보컬 오디오 파일을 분석하여 정교한 음정 타임라인을 생성하는 스크립트
librosa의 PYIN 알고리즘을 사용하여 더 정확한 음정 감지를 수행합니다.
"""
import json
import numpy as np
import os
import sys

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print('오류: librosa가 설치되지 않았습니다.')

def get_vocal_start_time(audio_data, sample_rate, top_db=20):
    """
    보컬 오디오에서 실제로 소리가 나기 시작하는 시점을 찾습니다.
    
    Args:
        audio_data: 오디오 데이터
        sample_rate: 샘플링 레이트
        top_db: 무음 구간 판정 임계값 (dB)
    
    Returns:
        첫 보컬 시작 시간 (초)
    """
    try:
        # 무음 구간 제거 (Non-silent 구간 탐지)
        intervals = librosa.effects.split(audio_data, top_db=top_db)
        
        if len(intervals) == 0:
            print("  ⚠️ 보컬 소리를 찾을 수 없습니다. (0초에서 시작)")
            return 0.0
        
        # 첫 번째 구간의 시작 샘플 찾기
        first_vocal_sample = intervals[0][0]
        
        # 샘플 -> 시간(초) 변환
        start_time = librosa.samples_to_time(first_vocal_sample, sr=sample_rate)
        print(f"  🎤 실제 보컬 시작 시간: {start_time:.2f}초")
        
        return start_time
    except Exception as e:
        print(f"  ⚠️ 보컬 시작 시점 탐지 오류: {e} (0초로 설정)")
        return 0.0

def analyze_vocal_with_pyin(audio_file_path, time_resolution=0.05):
    """
    PYIN 알고리즘을 사용하여 보컬 오디오의 음정을 분석합니다.
    
    Args:
        audio_file_path: 보컬 오디오 파일 경로
        time_resolution: 시간 해상도 (초 단위, 기본값 0.05초)
    
    Returns:
        타임라인별 음정 데이터 리스트, 첫 보컬 시작 시간
    """
    if not HAS_LIBROSA:
        return None, None
    
    try:
        print(f"보컬 파일 로드 중: {audio_file_path}")
        # 오디오 로드 (모노, 44100Hz)
        audio_data, sample_rate = librosa.load(audio_file_path, sr=44100, mono=True)
        duration = len(audio_data) / sample_rate
        print(f"  길이: {duration:.2f}초, 샘플링 레이트: {sample_rate}Hz")
        
        # 실제 보컬 시작 시점 찾기
        print("보컬 시작 시점 탐지 중...")
        vocal_start_time = get_vocal_start_time(audio_data, sample_rate, top_db=20)
        
        # PYIN 알고리즘으로 음정 추출 (더 정확함)
        print("PYIN 알고리즘으로 음정 분석 중...")
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio_data,
            fmin=librosa.note_to_hz('C2'),  # 최소 주파수 (약 65Hz)
            fmax=librosa.note_to_hz('C7'),   # 최대 주파수 (약 2093Hz)
            frame_length=2048,
            hop_length=512
        )
        
        # 볼륨(신호 강도) 계산 - 실제 보컬 구간 판별용
        print("볼륨 분석 중... (실제 보컬 구간 필터링)")
        rms = librosa.feature.rms(y=audio_data, frame_length=2048, hop_length=512)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=512)
        
        # 볼륨 임계값 계산 (전체 RMS의 상위 10% 기준 - 더 관대하게)
        rms_sorted = np.sort(rms)
        volume_threshold = np.percentile(rms_sorted, 10)  # 하위 10%만 제외 (더 관대)
        
        # 무음 구간 찾기 (librosa.effects.split 사용)
        intervals = librosa.effects.split(audio_data, top_db=20)
        silent_regions = []
        if len(intervals) > 0:
            # 무음 구간 찾기 (intervals 사이의 공간)
            for i in range(len(intervals) - 1):
                silent_start = librosa.samples_to_time(intervals[i][1], sr=sample_rate)
                silent_end = librosa.samples_to_time(intervals[i + 1][0], sr=sample_rate)
                silent_regions.append((silent_start, silent_end))
        
        # 시간축 생성
        times = librosa.frames_to_time(np.arange(len(f0)), sr=sample_rate, hop_length=512)
        
        # 타임라인별 데이터 생성
        timeline_data = []
        current_time = 0
        
        print(f"타임라인 데이터 생성 중... (해상도: {time_resolution}초)")
        
        while current_time <= duration:
            # 실제 보컬 시작 시점 이전은 모두 반주 구간으로 처리
            if current_time < vocal_start_time:
                timeline_data.append({
                    'time': round(current_time, 3),
                    'pitch': None
                })
            else:
                # 무음 구간 체크
                is_silent = False
                for silent_start, silent_end in silent_regions:
                    if silent_start <= current_time <= silent_end:
                        is_silent = True
                        break
                
                if is_silent:
                    timeline_data.append({
                        'time': round(current_time, 3),
                        'pitch': None
                    })
                else:
                    # 가장 가까운 프레임 찾기
                    frame_idx = np.argmin(np.abs(times - current_time))
                    rms_idx = np.argmin(np.abs(rms_times - current_time))
                    
                    if frame_idx < len(f0) and rms_idx < len(rms):
                        pitch = f0[frame_idx]
                        is_voiced = voiced_flag[frame_idx] if frame_idx < len(voiced_flag) else False
                        volume = rms[rms_idx] if rms_idx < len(rms) else 0
                        confidence = voiced_probs[frame_idx] if frame_idx < len(voiced_probs) else 0
                        
                        # 실제 보컬 판별 조건:
                        # 1. voiced가 True
                        # 2. pitch가 유효
                        # 3. 볼륨이 임계값 이상 (실제 보컬 소리) - 또는 신뢰도가 높으면 허용
                        # 4. 신뢰도가 0.3 이상 (더 관대하게)
                        if (is_voiced and not np.isnan(pitch) and pitch > 0 and 
                            (volume >= volume_threshold or confidence >= 0.7) and confidence >= 0.2):
                            timeline_data.append({
                                'time': round(current_time, 3),
                                'pitch': round(float(pitch), 2)
                            })
                        else:
                            timeline_data.append({
                                'time': round(current_time, 3),
                                'pitch': None
                            })
                    else:
                        timeline_data.append({
                            'time': round(current_time, 3),
                            'pitch': None
                        })
            
            current_time += time_resolution
            
            # 진행상황 표시
            progress = (current_time / duration) * 100
            if int(progress) % 10 == 0 and len(timeline_data) % 20 == 0:
                print(f"  진행률: {progress:.0f}%")
        
        return timeline_data, vocal_start_time
    
    except Exception as e:
        print(f'음정 분석 오류: {str(e)}')
        import traceback
        traceback.print_exc()
        return None, None

def extract_rhythm_info(audio_file_path):
    """
    오디오 파일에서 리듬 정보(BPM, 박자)를 추출합니다.
    
    Args:
        audio_file_path: 오디오 파일 경로
    
    Returns:
        BPM, 박자 시작 시점 리스트
    """
    if not HAS_LIBROSA:
        return None, None
    
    try:
        print("리듬 정보 추출 중...")
        audio_data, sample_rate = librosa.load(audio_file_path, sr=44100, mono=True)
        
        # BPM 추출
        tempo, beats = librosa.beat.beat_track(y=audio_data, sr=sample_rate)
        beat_times = librosa.frames_to_time(beats, sr=sample_rate)
        
        # numpy 배열을 Python 리스트로 변환
        tempo_value = float(tempo) if hasattr(tempo, 'item') else float(tempo)
        beat_times_list = [float(t) for t in beat_times] if hasattr(beat_times, 'tolist') else list(beat_times)
        
        print(f"  BPM: {tempo_value:.1f}")
        print(f"  박자 수: {len(beats)}개")
        
        return tempo_value, beat_times_list
    
    except Exception as e:
        print(f'리듬 정보 추출 오류: {str(e)}')
        return None, None

def main():
    if len(sys.argv) < 2:
        print("사용법: python analyze_vocal.py <보컬_오디오_파일> [출력_JSON_파일]")
        sys.exit(1)
    
    vocal_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'static/assets/music_pitch_data.json'
    
    if not os.path.exists(vocal_file):
        print(f"오류: 파일을 찾을 수 없습니다: {vocal_file}")
        sys.exit(1)
    
    print(f"보컬 음정 분석 시작: {vocal_file}")
    print(f"출력 파일: {output_file}\n")
    
    # 음정 타임라인 분석
    timeline_data, vocal_start_time = analyze_vocal_with_pyin(vocal_file, time_resolution=0.05)
    
    if not timeline_data:
        print("분석 실패")
        sys.exit(1)
    
    # 리듬 정보 추출
    bpm, beat_times = extract_rhythm_info(vocal_file)
    
    # 결과 저장
    result = {
        'timeline': timeline_data,
        'metadata': {
            'bpm': bpm,
            'beat_times': beat_times,
            'source_file': vocal_file,
            'source_type': 'vocal_audio_only',  # music1.mp4의 보컬만 사용
            'vocal_start_time': vocal_start_time  # 실제 보컬 시작 시점
        }
    }
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 분석 완료!")
    print(f"  데이터 포인트: {len(timeline_data)}개")
    print(f"  결과 저장: {output_file}")
    
    # 통계 정보
    pitches = [d['pitch'] for d in timeline_data if d['pitch']]
    if pitches:
        print(f"\n통계:")
        print(f"  유효한 음정 데이터: {len(pitches)}/{len(timeline_data)}")
        print(f"  평균 음정: {np.mean(pitches):.2f} Hz")
        print(f"  최소 음정: {np.min(pitches):.2f} Hz")
        print(f"  최대 음정: {np.max(pitches):.2f} Hz")

if __name__ == '__main__':
    main()

