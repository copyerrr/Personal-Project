"""
보컬 분리 + 정교한 음정 분석으로 퍼펙트 스코어 시스템
1. 보컬 완벽 분리 (spleeter)
2. 보컬만으로 정확한 목표 음정 추출 (PYIN)
3. 사용자 음정과 비교하여 정확한 점수 계산
"""
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("사용법: python perfect_vocal_score.py <오디오_파일> [MIDI_파일]")
        print("\n예시:")
        print("  python perfect_vocal_score.py music1.mp4")
        print("  python perfect_vocal_score.py music1.mp4 golden.mid  # MIDI가 있으면 더 정확함")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    midi_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(audio_file):
        print(f"❌ 오류: 파일을 찾을 수 없습니다: {audio_file}")
        sys.exit(1)
    
    print("="*60)
    print("🎤 퍼펙트 보컬 스코어 시스템")
    print("="*60)
    print(f"\n📁 입력 파일: {audio_file}")
    if midi_file:
        print(f"🎹 MIDI 파일: {midi_file} (정확도 향상)")
    print()
    
    # 1단계: 보컬 분리 (개선된 방법)
    print("="*60)
    print("[1단계] 보컬 분리")
    print("="*60)
    
    from separate_vocal import separate_vocal
    
    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    base_dir = os.path.dirname(audio_file) or '.'
    separated_dir = os.path.join(base_dir, f"{base_name}_separated")
    
    vocal_file = os.path.join(separated_dir, base_name, "vocals.wav")
    if not os.path.exists(vocal_file):
        vocal_file = os.path.join(separated_dir, f"{base_name}_vocal.wav")
    
    if os.path.exists(vocal_file):
        print(f"✅ 보컬 파일이 이미 존재합니다: {vocal_file}")
    else:
        vocal_path, accompaniment_path = separate_vocal(audio_file, separated_dir, use_improved=True)
        if not vocal_path:
            print("❌ 보컬 분리 실패")
            sys.exit(1)
        vocal_file = vocal_path
    
    # 2단계: 음정 분석
    print("\n" + "="*60)
    print("[2단계] 음정 타임라인 분석")
    print("="*60)
    
    # MIDI 파일이 명시적으로 제공된 경우만 사용
    use_midi = False
    if midi_file and os.path.exists(midi_file):
        print(f"🎹 MIDI 파일 지정됨: {midi_file}")
        use_midi = True
    else:
        print("🎤 보컬 오디오로 분석 (MIDI 파일 없음)")
    
    if use_midi:
        print("🎹 MIDI 파일로 분석 (가장 정확함)")
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("analyze_music", "analyze_music.py")
            analyze_music = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(analyze_music)
            
            output_json = 'static/assets/music_pitch_data.json'
            timeline_data = analyze_music.analyze_midi_file(midi_file, time_resolution=0.05, vocal_track_idx=None)
            
            if timeline_data:
                result = {
                    'timeline': timeline_data,
                    'metadata': {
                        'source_file': midi_file,
                        'source_type': 'midi',
                        'audio_file': audio_file,
                        'vocal_file': vocal_file
                    }
                }
                
                os.makedirs(os.path.dirname(output_json), exist_ok=True)
                import json
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                pitches = [d['pitch'] for d in timeline_data if d['pitch']]
                print(f"✅ MIDI 분석 완료: {len(pitches)}/{len(timeline_data)}개 유효한 음정")
                print(f"📄 저장: {output_json}")
        except Exception as e:
            print(f"⚠️ MIDI 분석 실패, 보컬 오디오 분석으로 전환: {e}")
            use_midi = False
    
    # MIDI가 없거나 실패하면 보컬 오디오 분석
    if not use_midi:
        print("🎤 보컬 오디오로 분석 (PYIN 알고리즘)")
        from analyze_vocal import analyze_vocal_with_pyin, extract_rhythm_info
        
        output_json = 'static/assets/music_pitch_data.json'
        timeline_data = analyze_vocal_with_pyin(vocal_file, time_resolution=0.05)
        
        if not timeline_data:
            print("❌ 음정 분석 실패")
            sys.exit(1)
        
        bpm, beat_times = extract_rhythm_info(vocal_file)
        
        result = {
            'timeline': timeline_data,
            'metadata': {
                'bpm': bpm,
                'beat_times': beat_times,
                'source_file': vocal_file,
                'source_type': 'vocal_audio',
                'audio_file': audio_file
            }
        }
        
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        import json
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        pitches = [d['pitch'] for d in timeline_data if d['pitch']]
        print(f"✅ 보컬 분석 완료: {len(pitches)}/{len(timeline_data)}개 유효한 음정")
        print(f"📄 저장: {output_json}")
    
    print("\n" + "="*60)
    print("✅ 완료! 이제 Flask 앱을 실행하세요:")
    print("   python app.py")
    print("="*60)
    print("\n💡 팁:")
    print("   - 보컬만 분리되어 있어서 목표 음정이 매우 정확합니다")
    print("   - 사용자가 부른 음정과 비교하여 정확한 점수를 계산합니다")
    print("   - 반주 구간(null)에서는 점수가 계산되지 않습니다")

if __name__ == '__main__':
    main()

