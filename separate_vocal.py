"""
원곡 오디오 파일에서 보컬을 자동으로 분리하는 스크립트
Spleeter를 사용하여 보컬과 반주를 분리합니다.
개선된 버전: separate_to_file 메서드 사용 (더 안정적)
"""
import os
import sys
import argparse

def separate_vocal(input_file, output_dir=None, use_improved=True):
    """
    오디오 파일에서 보컬을 분리합니다.
    
    Args:
        input_file: 입력 오디오 파일 경로 (MP3, WAV, MP4 등)
        output_dir: 출력 디렉토리 (기본값: 입력 파일과 같은 디렉토리)
        use_improved: True면 개선된 방법(separate_to_file) 사용, False면 기존 방법
    
    Returns:
        보컬 파일 경로, 반주 파일 경로
    """
    try:
        from spleeter.separator import Separator
    except ImportError as e:
        print(f"오류: spleeter를 import할 수 없습니다: {e}")
        print("설치: pip install spleeter tensorflow")
        import traceback
        traceback.print_exc()
        return None, None
    
    if not os.path.exists(input_file):
        print(f"오류: 파일을 찾을 수 없습니다: {input_file}")
        return None, None
    
    # 출력 디렉토리 설정
    if output_dir is None:
        base_dir = os.path.dirname(input_file) or '.'
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = os.path.join(base_dir, f"{base_name}_separated")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🔄 보컬 분리 시작: {input_file}")
    print(f"   (AI가 노래를 듣고 보컬을 분리하는 중입니다. 시간이 좀 걸립니다...)")
    print(f"📂 출력 디렉토리: {output_dir}")
    
    try:
        # Spleeter 초기화 (2 stems: 보컬 + 반주)
        separator = Separator('spleeter:2stems')
        
        if use_improved:
            # 개선된 방법: separate_to_file 사용 (더 안정적이고 간단함)
            print("   [개선된 방법 사용]")
            separator.separate_to_file(input_file, output_dir)
            
            # 출력 파일 경로 찾기
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            # spleeter는 {base_name}/vocals.wav 형식으로 저장
            vocal_path = os.path.join(output_dir, base_name, "vocals.wav")
            accompaniment_path = os.path.join(output_dir, base_name, "accompaniment.wav")
            
            # 파일이 실제로 생성되었는지 확인
            if not os.path.exists(vocal_path):
                # 다른 가능한 경로 시도
                possible_paths = [
                    os.path.join(output_dir, "vocals.wav"),
                    os.path.join(output_dir, f"{base_name}_vocals.wav"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        vocal_path = path
                        break
            
            if not os.path.exists(accompaniment_path):
                possible_paths = [
                    os.path.join(output_dir, "accompaniment.wav"),
                    os.path.join(output_dir, f"{base_name}_accompaniment.wav"),
                ]
                for path in possible_paths:
                    if os.path.exists(path):
                        accompaniment_path = path
                        break
            
        else:
            # 기존 방법 (하위 호환성)
            from spleeter.audio.adapter import AudioAdapter
            audio_adapter = AudioAdapter.default()
            
            print("오디오 파일 로드 중...")
            waveform, sample_rate = audio_adapter.load(input_file)
            
            print("보컬 분리 중... (시간이 걸릴 수 있습니다)")
            prediction = separator.separate(waveform)
            
            # 결과 저장
            vocal_waveform = prediction['vocals']
            accompaniment_waveform = prediction['accompaniment']
            
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            vocal_path = os.path.join(output_dir, f"{base_name}_vocal.wav")
            accompaniment_path = os.path.join(output_dir, f"{base_name}_accompaniment.wav")
            
            print("결과 저장 중...")
            audio_adapter.save(vocal_path, vocal_waveform, sample_rate)
            audio_adapter.save(accompaniment_path, accompaniment_waveform, sample_rate)
        
        if os.path.exists(vocal_path):
            print(f"\n✅ 보컬 분리 완료!")
            print(f"  보컬 파일: {vocal_path}")
            print(f"  반주 파일: {accompaniment_path}")
            return vocal_path, accompaniment_path
        else:
            print(f"\n❌ 보컬 파일을 찾을 수 없습니다: {vocal_path}")
            print("   출력 디렉토리 내용:")
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    print(f"     {os.path.join(root, file)}")
            return None, None
    
    except Exception as e:
        print(f"보컬 분리 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None

def main():
    parser = argparse.ArgumentParser(description='오디오 파일에서 보컬을 분리합니다.')
    parser.add_argument('input_file', help='입력 오디오 파일 경로')
    parser.add_argument('-o', '--output', help='출력 디렉토리 (기본값: 입력 파일과 같은 디렉토리)')
    
    args = parser.parse_args()
    
    vocal_path, accompaniment_path = separate_vocal(args.input_file, args.output)
    
    if vocal_path:
        print(f"\n다음 명령어로 음정 분석을 진행하세요:")
        print(f"python analyze_vocal.py {vocal_path}")

if __name__ == '__main__':
    main()

