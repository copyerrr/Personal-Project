"""
pretty_midi를 사용하여 보컬 트랙만 추출하는 스크립트
"""
import json
import sys
import os

def midi_note_to_frequency(note):
    """MIDI 노트 번호를 주파수(Hz)로 변환"""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

def extract_vocal_track_simple(midi_file_path, output_json_path="static/assets/music_pitch_data.json", time_resolution=0.05):
    try:
        # pretty_midi import 시도 (fluidsynth 오류 무시)
        try:
            import pretty_midi
        except (ImportError, FileNotFoundError, OSError) as e:
            print(f"오류: pretty_midi를 로드할 수 없습니다: {e}")
            print("fluidsynth DLL 경로 문제일 수 있습니다.")
            print("mido를 사용하는 analyze_music.py를 사용하세요.")
            return None
        
        # 1. MIDI 파일 로드
        pm = pretty_midi.PrettyMIDI(midi_file_path)
        
        # 2. 보컬 트랙 선택 (첫 번째 트랙)
        if len(pm.instruments) < 1:
            print("오류: 악기 트랙이 없는 파일입니다.")
            return None

        vocal_track = pm.instruments[0] 
        track_name = vocal_track.name if hasattr(vocal_track, 'name') and vocal_track.name else "Track 0"
        print(f"보컬 트랙 발견: {track_name} (총 {len(vocal_track.notes)}개의 음표)")

        # 3. 타임라인별 음정 데이터 생성
        timeline_data = []
        total_time = pm.get_end_time()
        current_time = 0
        
        print(f"분석 중... (총 {total_time:.2f}초, {len(vocal_track.notes)}개 음표)")
        
        while current_time <= total_time:
            # 현재 시간에 활성화된 노트 찾기
            active_notes = []
            for note in vocal_track.notes:
                if note.start <= current_time < note.end:
                    active_notes.append(note)
            
            # 보컬은 보통 단일 음이므로, 여러 음이 있으면 가장 높은 음 선택
            if active_notes:
                # 가장 높은 음정 선택
                highest_note = max(active_notes, key=lambda n: n.pitch)
                pitch = midi_note_to_frequency(highest_note.pitch)
            else:
                # 보컬이 없는 구간 (반주 부분)
                pitch = None
            
            timeline_data.append({
                'time': round(current_time, 3),
                'pitch': round(pitch, 2) if pitch else None
            })
            
            current_time += time_resolution
            
            # 진행상황 표시 (10% 단위)
            progress = (current_time / total_time) * 100
            if int(progress) % 10 == 0 and len(timeline_data) % 20 == 0:
                print(f'  진행률: {progress:.0f}%')
        
        # 4. 결과 저장
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n추출 완료!")
        print(f"결과 저장: {output_json_path}")
        print(f"총 {len(timeline_data)}개의 데이터 포인트 생성")
        
        # 통계 정보
        pitches = [d['pitch'] for d in timeline_data if d['pitch']]
        if pitches:
            import numpy as np
            print(f"\n통계:")
            print(f"  유효한 음정 데이터: {len(pitches)}/{len(timeline_data)}")
            print(f"  평균 음정: {np.mean(pitches):.2f} Hz")
            print(f"  최소 음정: {np.min(pitches):.2f} Hz")
            print(f"  최대 음정: {np.max(pitches):.2f} Hz")
        
        return timeline_data

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    # 명령줄 인자 처리
    if len(sys.argv) > 1:
        midi_file = sys.argv[1]
    else:
        midi_file = 'public/assets/golden.mid'
    
    if not os.path.exists(midi_file):
        print(f"파일을 찾을 수 없습니다: {midi_file}")
        sys.exit(1)
    
    extract_vocal_track_simple(midi_file)

