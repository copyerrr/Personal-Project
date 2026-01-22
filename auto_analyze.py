"""
원곡 오디오 파일만 넣으면 자동으로 모든 분석을 수행하는 통합 스크립트
1. 보컬 분리
2. 음정 타임라인 생성
3. 리듬 정보 추출
"""
import os
import sys

# 직접 모듈 import하여 사용
try:
    from separate_vocal import separate_vocal
    from analyze_vocal import analyze_vocal_with_pyin, extract_rhythm_info
    HAS_MODULES = True
except ImportError as e:
    print(f"모듈 import 오류: {e}")
    HAS_MODULES = False

def main():
    if len(sys.argv) < 2:
        print("사용법: python auto_analyze.py <원곡_오디오_파일> [MIDI_파일]")
        print("\n예시:")
        print("  python auto_analyze.py music.mp3")
        print("  python auto_analyze.py static/assets/music1.mp4")
        print("  python auto_analyze.py static/assets/music1.mp4 public/assets/golden.mid")
        sys.exit(1)
    
    input_file = sys.argv[1]
    midi_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # MIDI 파일 자동 탐색 비활성화 (사용자가 명시적으로 지정한 경우만 사용)
    # 같은 디렉토리에서 자동으로 MIDI 파일 찾기 기능 제거
    
    if not os.path.exists(input_file):
        print(f"오류: 파일을 찾을 수 없습니다: {input_file}")
        sys.exit(1)
    
    # MIDI 파일이 명시적으로 제공된 경우만 사용
    if midi_file and os.path.exists(midi_file):
        print(f"\n[자동 분석 시작] MIDI 파일 우선 사용")
        print(f"  오디오 파일: {input_file}")
        print(f"  MIDI 파일: {midi_file}")
        print(f"{'='*60}\n")
        
        # MIDI 파일 분석
        print(f"{'='*60}")
        print(f"[*] MIDI 파일 분석 (가장 정확함)")
        print(f"{'='*60}")
        
        try:
            from analyze_from_midi import main as analyze_midi_main
            import sys as sys_module
            # analyze_from_midi.py의 main 함수를 직접 호출
            from analyze_from_midi import analyze_midi_file, extract_rhythm_from_midi
            from analyze_music import analyze_midi_file as analyze_midi_from_music
            
            output_json = 'static/assets/music_pitch_data.json'
            timeline_data = analyze_midi_from_music(midi_file, time_resolution=0.05, vocal_track_idx=None)
            
            if not timeline_data:
                print("\n[ERROR] MIDI 분석 실패")
                sys.exit(1)
            
            # 리듬 정보 추출
            bpm, beat_times = extract_rhythm_from_midi(midi_file)
            
            # 결과 저장
            result = {
                'timeline': timeline_data,
                'metadata': {
                    'bpm': bpm,
                    'beat_times': beat_times,
                    'source_file': midi_file,
                    'source_type': 'midi',
                    'audio_file': input_file
                }
            }
            
            os.makedirs(os.path.dirname(output_json), exist_ok=True)
            import json
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"[OK] 결과 저장: {output_json}")
            
            # 통계
            pitches = [d['pitch'] for d in timeline_data if d['pitch']]
            if pitches:
                import numpy as np
                print(f"\n통계:")
                print(f"  유효한 음정 데이터: {len(pitches)}/{len(timeline_data)}")
                print(f"  평균 음정: {np.mean(pitches):.2f} Hz")
            
            print(f"\n{'='*60}")
            print("[완료] MIDI 분석이 완료되었습니다!")
            print(f"{'='*60}")
            print(f"\n생성된 파일:")
            print(f"  - 음정 데이터: {output_json}")
            print(f"\n이제 Flask 앱을 실행하여 노래방 시스템을 사용할 수 있습니다:")
            print(f"  python app.py")
            return
            
        except Exception as e:
            print(f"[ERROR] MIDI 분석 중 오류: {e}")
            import traceback
            traceback.print_exc()
            print("\n오디오 분석으로 전환합니다...\n")
    
    print(f"\n[자동 분석 시작] {input_file}")
    print(f"{'='*60}\n")
    
    # 1단계: 보컬 분리
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    base_dir = os.path.dirname(input_file) or '.'
    separated_dir = os.path.join(base_dir, f"{base_name}_separated")
    # spleeter는 {base_name}/vocals.wav 형식으로 저장
    vocal_file = os.path.join(separated_dir, base_name, "vocals.wav")
    
    if not HAS_MODULES:
        print("[ERROR] 필요한 모듈을 import할 수 없습니다.")
        sys.exit(1)
    
    # 1단계: 보컬 분리
    print(f"\n{'='*60}")
    print(f"[*] 1단계: 보컬 분리")
    print(f"{'='*60}")
    
    if os.path.exists(vocal_file):
        print(f"[OK] 보컬 파일이 이미 존재합니다: {vocal_file}")
        print("   보컬 분리를 건너뜁니다. (다시 분리하려면 파일을 삭제하세요)")
    else:
        vocal_path, accompaniment_path = separate_vocal(input_file, separated_dir)
        if not vocal_path:
            print("\n[ERROR] 보컬 분리 실패")
            sys.exit(1)
        vocal_file = vocal_path
    
    # 2단계: 음정 분석
    if not os.path.exists(vocal_file):
        print(f"[ERROR] 보컬 파일을 찾을 수 없습니다: {vocal_file}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"[*] 2단계: 음정 타임라인 분석")
    print(f"{'='*60}")
    
    output_json = 'static/assets/music_pitch_data.json'
    timeline_data, vocal_start_time = analyze_vocal_with_pyin(vocal_file, time_resolution=0.05)
    
    if not timeline_data:
        print("\n[ERROR] 음정 분석 실패")
        sys.exit(1)
    
    # 리듬 정보 추출
    print(f"\n[*] 리듬 정보 추출 중...")
    bpm, beat_times = extract_rhythm_info(vocal_file)
    
    # 결과 저장
    result = {
        'timeline': timeline_data,
        'metadata': {
            'bpm': bpm,
            'beat_times': beat_times,
            'source_file': vocal_file,
            'vocal_start_time': vocal_start_time  # 실제 보컬 시작 시점
        }
    }
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    import json
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] 결과 저장: {output_json}")
    
    print(f"\n{'='*60}")
    print("[완료] 모든 분석이 완료되었습니다!")
    print(f"{'='*60}")
    print(f"\n생성된 파일:")
    print(f"  - 보컬 파일: {vocal_file}")
    print(f"  - 음정 데이터: {output_json}")
    print(f"\n이제 Flask 앱을 실행하여 노래방 시스템을 사용할 수 있습니다:")
    print(f"  python app.py")

if __name__ == '__main__':
    main()

