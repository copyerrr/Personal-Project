"""
MIDI 파일을 오디오 파일로 변환하는 스크립트 (간단한 사인파 신디사이저 사용)
"""
import os
import sys
import numpy as np

try:
    import mido
    import soundfile as sf
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False
    print('경고: mido와 soundfile이 필요합니다.')
    print('설치: pip install mido soundfile')

def midi_note_to_frequency(note):
    """MIDI 노트 번호를 주파수로 변환"""
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

def generate_sine_wave(frequency, duration, sample_rate=44100, amplitude=0.3):
    """사인파 생성"""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    return wave

def midi_to_audio(midi_file_path, output_file_path, sample_rate=44100):
    """
    MIDI 파일을 오디오 파일로 변환합니다 (간단한 사인파 신디사이저 사용).
    
    Args:
        midi_file_path: MIDI 파일 경로
        output_file_path: 출력 오디오 파일 경로 (WAV)
        sample_rate: 샘플링 레이트 (기본값 44100)
    """
    if not HAS_MIDO:
        print('오류: mido와 soundfile이 필요합니다.')
        print('설치: pip install mido soundfile')
        return False
    
    try:
        print(f'MIDI 파일 로드 중: {midi_file_path}')
        mid = mido.MidiFile(midi_file_path)
        print(f'  길이: {mid.length:.2f}초')
        print(f'  트랙 수: {len(mid.tracks)}')
        
        # 전체 길이에 맞춰 오디오 배열 생성
        total_samples = int(sample_rate * mid.length)
        audio_data = np.zeros(total_samples, dtype=np.float32)
        
        # 모든 노트 이벤트 수집
        notes = []  # (start_time, end_time, note_number, velocity)
        active_notes = {}  # {channel: {note: (start_time, start_ticks)}}
        
        tempo = 500000  # 기본 템포 (120 BPM)
        
        for track in mid.tracks:
            current_ticks = 0
            for msg in track:
                current_ticks += msg.time
                current_time = mido.tick2second(current_ticks, mid.ticks_per_beat, tempo)
                
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    channel = msg.channel if hasattr(msg, 'channel') else 0
                    if channel not in active_notes:
                        active_notes[channel] = {}
                    active_notes[channel][msg.note] = (current_time, current_ticks, tempo, msg.velocity)
                    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    channel = msg.channel if hasattr(msg, 'channel') else 0
                    if channel in active_notes and msg.note in active_notes[channel]:
                        start_time, start_ticks, start_tempo, velocity = active_notes[channel][msg.note]
                        end_time = mido.tick2second(current_ticks, mid.ticks_per_beat, start_tempo)
                        notes.append({
                            'start': start_time,
                            'end': end_time,
                            'note': msg.note,
                            'velocity': velocity
                        })
                        del active_notes[channel][msg.note]
        
        # 남아있는 노트 처리
        for channel, channel_notes in active_notes.items():
            for note, (start_time, start_ticks, start_tempo, velocity) in channel_notes.items():
                notes.append({
                    'start': start_time,
                    'end': mid.length,
                    'note': note,
                    'velocity': velocity
                })
        
        print(f'  노트 수: {len(notes)}')
        print(f'오디오 생성 중...')
        
        # 각 노트를 사인파로 생성하여 오디오에 추가
        for i, note_info in enumerate(notes):
            if i % 10 == 0:
                print(f'  진행률: {i}/{len(notes)}')
            
            start_time = note_info['start']
            end_time = note_info['end']
            duration = end_time - start_time
            note_number = note_info['note']
            velocity = note_info['velocity']
            
            # 노트를 주파수로 변환
            frequency = midi_note_to_frequency(note_number)
            
            # 볼륨 조절 (velocity 0-127 -> 0.0-0.5)
            amplitude = (velocity / 127.0) * 0.5
            
            # 사인파 생성
            wave = generate_sine_wave(frequency, duration, sample_rate, amplitude)
            
            # 오디오 배열에 추가 (겹치는 노트는 합산)
            start_sample = int(start_time * sample_rate)
            end_sample = start_sample + len(wave)
            if end_sample <= len(audio_data):
                audio_data[start_sample:end_sample] += wave
        
        # 정규화 (클리핑 방지)
        max_val = np.abs(audio_data).max()
        if max_val > 1.0:
            audio_data = audio_data / max_val
        
        print(f'오디오 파일 저장 중: {output_file_path}')
        # WAV 파일로 저장
        sf.write(output_file_path, audio_data, sample_rate)
        
        print(f'변환 완료!')
        print(f'  입력: {midi_file_path}')
        print(f'  출력: {output_file_path}')
        print(f'  길이: {len(audio_data)/sample_rate:.2f}초')
        
        return True
        
    except Exception as e:
        print(f'변환 오류: {str(e)}')
        import traceback
        traceback.print_exc()
        return False

def main():
    """
    메인 함수
    """
    # 입력 파일 경로
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'public/assets/hello.mid'
    
    if not os.path.exists(input_file):
        print(f'파일을 찾을 수 없습니다: {input_file}')
        sys.exit(1)
    
    # 출력 파일 경로 (입력 파일과 같은 이름, 확장자만 변경)
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_dir = 'static/assets'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'{base_name}.wav')
    
    print(f'MIDI → 오디오 변환')
    print(f'입력: {input_file}')
    print(f'출력: {output_file}')
    print()
    
    success = midi_to_audio(input_file, output_file)
    
    if success:
        print(f'\n변환 성공!')
        print(f'이제 웹 애플리케이션에서 {output_file}를 사용할 수 있습니다.')
    else:
        print('\n변환 실패')
        sys.exit(1)

if __name__ == '__main__':
    main()

