"""
MIDI 파일을 분석하여 정확한 음정 타임라인을 생성하는 스크립트
오디오 분석보다 훨씬 정확합니다.
"""
import json
import os
import sys

# analyze_music.py의 함수들을 직접 import
import importlib.util
spec = importlib.util.spec_from_file_location("analyze_music", "analyze_music.py")
analyze_music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze_music)

HAS_ANALYZE_MUSIC = True

def extract_rhythm_from_midi(midi_file_path):
    """MIDI 파일에서 리듬 정보를 추출합니다."""
    try:
        import librosa
        # MIDI 파일을 오디오로 변환하지 않고 직접 분석하는 것은 복잡하므로
        # 간단히 BPM 정보만 추출하거나 None 반환
        return None, None
    except:
        return None, None

def main():
    if len(sys.argv) < 2:
        print("사용법: python analyze_from_midi.py <MIDI_파일> [출력_JSON_파일] [보컬_트랙_인덱스]")
        print("\n예시:")
        print("  python analyze_from_midi.py public/assets/golden.mid")
        print("  python analyze_from_midi.py public/assets/golden.mid static/assets/music_pitch_data.json 0")
        sys.exit(1)
    
    midi_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'static/assets/music_pitch_data.json'
    vocal_track_idx = int(sys.argv[3]) if len(sys.argv) > 3 else None  # None이면 자동 선택
    
    if not os.path.exists(midi_file):
        print(f"오류: 파일을 찾을 수 없습니다: {midi_file}")
        sys.exit(1)
    
    print(f"MIDI 파일 분석 시작: {midi_file}")
    print(f"출력 파일: {output_file}\n")
    
    # MIDI 파일 분석
    timeline_data = analyze_music.analyze_midi_file(midi_file, time_resolution=0.05, vocal_track_idx=vocal_track_idx)
    
    if not timeline_data:
        print("분석 실패")
        sys.exit(1)
    
    # 리듬 정보 추출 (간단히 None으로 설정, 필요시 추가)
    bpm, beat_times = extract_rhythm_from_midi(midi_file)
    
    # 결과 저장
    result = {
        'timeline': timeline_data,
        'metadata': {
            'bpm': bpm,
            'beat_times': beat_times,
            'source_file': midi_file,
            'source_type': 'midi'
        }
    }
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n[완료] 분석 완료!")
    print(f"  데이터 포인트: {len(timeline_data)}개")
    print(f"  결과 저장: {output_file}")
    
    # 통계 정보
    pitches = [d['pitch'] for d in timeline_data if d['pitch']]
    if pitches:
        import numpy as np
        print(f"\n통계:")
        print(f"  유효한 음정 데이터: {len(pitches)}/{len(timeline_data)}")
        print(f"  평균 음정: {np.mean(pitches):.2f} Hz")
        print(f"  최소 음정: {np.min(pitches):.2f} Hz")
        print(f"  최대 음정: {np.max(pitches):.2f} Hz")
    else:
        print("\n경고: 유효한 음정 데이터가 없습니다.")

if __name__ == '__main__':
    main()

