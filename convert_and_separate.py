"""
music1.mp4를 WAV로 변환하고 보컬만 분리하는 스크립트
사용자가 제공한 코드 사용
"""
import os
import sys

def convert_mp4_to_wav(mp4_file, wav_file=None):
    """MP4를 WAV로 변환"""
    try:
        import librosa
        print(f"🔄 MP4를 WAV로 변환 중: {mp4_file}")
        audio_data, sample_rate = librosa.load(mp4_file, sr=44100, mono=False)
        
        if wav_file is None:
            wav_file = mp4_file.replace('.mp4', '.wav')
        
        import soundfile as sf
        sf.write(wav_file, audio_data.T, sample_rate)
        print(f"✅ 변환 완료: {wav_file}")
        return wav_file
    except Exception as e:
        print(f"❌ 변환 실패: {e}")
        return None

def split_mp4_to_stems(input_file, output_path="output"):
    """사용자가 제공한 코드 - 보컬 분리"""
    from spleeter.separator import Separator
    
    if not os.path.exists(input_file):
        print(f"❌ 오류: '{input_file}' 파일을 찾을 수 없습니다.")
        return None, None

    print(f"🔄 분석 시작: {input_file}")
    print("   (AI가 노래를 듣고 보컬을 분리하는 중입니다. 시간이 좀 걸립니다...)")

    try:
        # 2stems = 목소리 + 반주
        separator = Separator('spleeter:2stems')
        
        # 분리 실행
        separator.separate_to_file(input_file, output_path)
        
        # 출력 파일 경로 찾기
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        vocal_path = os.path.join(output_path, base_name, "vocals.wav")
        accompaniment_path = os.path.join(output_path, base_name, "accompaniment.wav")
        
        # 파일 확인
        if os.path.exists(vocal_path):
            print(f"✅ 분리 완료!")
            print(f"📂 보컬: {vocal_path}")
            print(f"📂 반주: {accompaniment_path}")
            return vocal_path, accompaniment_path
        else:
            # 다른 경로 시도
            possible_vocal = os.path.join(output_path, "vocals.wav")
            if os.path.exists(possible_vocal):
                print(f"✅ 분리 완료!")
                print(f"📂 보컬: {possible_vocal}")
                return possible_vocal, None
            else:
                print(f"❌ 보컬 파일을 찾을 수 없습니다")
                print(f"   찾은 파일들:")
                for root, dirs, files in os.walk(output_path):
                    for file in files:
                        print(f"     {os.path.join(root, file)}")
                return None, None
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    mp4_file = "public/assets/music1.mp4"
    
    if not os.path.exists(mp4_file):
        print(f"❌ 파일을 찾을 수 없습니다: {mp4_file}")
        sys.exit(1)
    
    print("="*60)
    print("🎤 music1.mp4 → WAV 변환 → 보컬 분리")
    print("="*60)
    print()
    
    # 1단계: MP4를 WAV로 변환 (선택사항 - spleeter가 MP4를 직접 지원하므로 생략 가능)
    # 하지만 WAV로 변환하면 더 빠를 수 있음
    wav_file = mp4_file.replace('.mp4', '.wav')
    
    if not os.path.exists(wav_file):
        wav_file = convert_mp4_to_wav(mp4_file, wav_file)
        if not wav_file:
            print("⚠️ WAV 변환 실패, MP4 직접 사용")
            wav_file = mp4_file
    else:
        print(f"✅ WAV 파일이 이미 존재합니다: {wav_file}")
    
    # 2단계: 보컬 분리
    print()
    print("="*60)
    print("[2단계] 보컬 분리")
    print("="*60)
    
    output_path = "public/assets/music1_separated"
    vocal_path, accompaniment_path = split_mp4_to_stems(wav_file, output_path)
    
    if not vocal_path:
        print("❌ 보컬 분리 실패")
        sys.exit(1)
    
    # 3단계: 보컬 파일로 음정 분석
    print()
    print("="*60)
    print("[3단계] 보컬 음정 분석")
    print("="*60)
    
    from analyze_vocal import analyze_vocal_with_pyin, extract_rhythm_info
    
    output_json = 'static/assets/music_pitch_data.json'
    timeline_data = analyze_vocal_with_pyin(vocal_path, time_resolution=0.05)
    
    if not timeline_data:
        print("❌ 음정 분석 실패")
        sys.exit(1)
    
    bpm, beat_times = extract_rhythm_info(vocal_path)
    
    result = {
        'timeline': timeline_data,
        'metadata': {
            'bpm': bpm,
            'beat_times': beat_times,
            'source_file': vocal_path,
            'source_type': 'vocal_audio_only',
            'audio_file': mp4_file,
            'wav_file': wav_file
        }
    }
    
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    import json
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    pitches = [d['pitch'] for d in timeline_data if d['pitch']]
    print(f"✅ 분석 완료: {len(pitches)}/{len(timeline_data)}개 유효한 음정")
    print(f"📄 저장: {output_json}")
    
    print()
    print("="*60)
    print("✅ 완료! music1.mp4의 보컬만 사용합니다")
    print("="*60)

if __name__ == '__main__':
    main()

