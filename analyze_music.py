"""
음악 파일을 분석하여 타임라인별 목표 음정 데이터를 생성하는 스크립트
"""
import json
import numpy as np
import os
import sys

try:
    from scipy.io import wavfile
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print('경고: scipy가 설치되지 않았습니다. librosa를 사용합니다.')

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    if not HAS_SCIPY:
        print('경고: scipy 또는 librosa가 필요합니다.')

try:
    import mido
    HAS_MIDO = True
except ImportError:
    HAS_MIDO = False
    print('경고: mido가 설치되지 않았습니다. MIDI 파일을 분석할 수 없습니다.')

try:
    import pretty_midi
    # pretty_midi가 로드되면 사용 가능
    HAS_PRETTY_MIDI = True
except (ImportError, FileNotFoundError, OSError) as e:
    # fluidsynth DLL 경로 문제 등으로 인한 오류도 처리
    HAS_PRETTY_MIDI = False
    print(f'경고: pretty_midi를 사용할 수 없습니다: {e}')
    print('노트 정보 추출만 필요하므로 mido를 사용합니다.')

def detect_pitch(buffer, sample_rate, volume_threshold=0.01):
    """
    Autocorrelation을 사용하여 음정(주파수)을 감지합니다.
    
    Args:
        buffer: 오디오 신호 데이터
        sample_rate: 샘플링 레이트
        volume_threshold: 최소 볼륨 임계값 (이보다 작으면 None 반환)
    """
    # 신호 강도(볼륨) 계산
    rms = np.sqrt(np.mean(buffer**2))
    if rms < volume_threshold:
        return None  # 너무 조용하면 음정 감지하지 않음
    
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
    
    if best_period > 0 and best_correlation > 0.15:  # 임계값을 0.1에서 0.15로 상향
        return sample_rate / best_period
    
    return None

def analyze_audio_file(audio_file_path, window_size=0.1, hop_size=0.05):
    """
    오디오 파일을 분석하여 타임라인별 음정 데이터를 생성합니다.
    
    Args:
        audio_file_path: 오디오 파일 경로 (WAV, MP3, MP4 등)
        window_size: 분석 윈도우 크기 (초)
        hop_size: 분석 간격 (초)
    
    Returns:
        타임라인별 음정 데이터 리스트
    """
    try:
        if HAS_LIBROSA:
            # librosa 사용 (더 정확함)
            audio_data, sample_rate = librosa.load(audio_file_path, sr=44100, mono=True)
            print(f'librosa로 파일 로드 완료: {len(audio_data)/sample_rate:.2f}초')
        elif HAS_SCIPY:
            # scipy 사용 (WAV 파일만)
            sample_rate, audio_data = wavfile.read(audio_file_path)
            if len(audio_data.shape) > 1:
                audio_data = np.mean(audio_data, axis=1)
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
                if audio_data.max() > 1.0:
                    audio_data = audio_data / 32768.0
        else:
            print('오류: scipy 또는 librosa가 필요합니다.')
            return None
        
        window_samples = int(window_size * sample_rate)
        hop_samples = int(hop_size * sample_rate)
        
        timeline_data = []
        total_samples = len(audio_data)
        
        print(f'분석 중... (총 {total_samples/sample_rate:.2f}초)')
        
        for start_idx in range(0, total_samples - window_samples, hop_samples):
            window = audio_data[start_idx:start_idx + window_samples]
            time_position = start_idx / sample_rate
            
            # 볼륨 임계값: 보컬이 있을 때만 음정 감지 (반주만 있을 때는 무시)
            # 보컬은 일반적으로 더 큰 볼륨을 가지므로 임계값을 높임
            pitch = detect_pitch(window, sample_rate, volume_threshold=0.02)
            
            timeline_data.append({
                'time': round(time_position, 3),
                'pitch': round(pitch, 2) if pitch else None
            })
            
            # 진행상황 표시 (10% 단위)
            progress = (start_idx / total_samples) * 100
            if int(progress) % 10 == 0 and start_idx % (hop_samples * 20) == 0:
                print(f'  진행률: {progress:.0f}%')
        
        return timeline_data
    
    except Exception as e:
        print(f'오디오 분석 오류: {str(e)}')
        import traceback
        traceback.print_exc()
        return None

def midi_note_to_frequency(note):
    """
    MIDI 노트 번호를 주파수(Hz)로 변환합니다.
    
    Args:
        note: MIDI 노트 번호 (0-127)
    
    Returns:
        주파수 (Hz)
    """
    # A4 (440Hz)는 MIDI 노트 69
    return 440.0 * (2.0 ** ((note - 69) / 12.0))

def analyze_midi_file(midi_file_path, time_resolution=0.05, vocal_track_idx=0):
    """
    MIDI 파일을 분석하여 타임라인별 음정 데이터를 생성합니다.
    pretty_midi를 사용하여 보컬 트랙만 추출합니다.
    
    Args:
        midi_file_path: MIDI 파일 경로
        time_resolution: 시간 해상도 (초 단위, 기본값 0.05초)
        vocal_track_idx: 보컬 트랙 인덱스 (기본값 0)
    
    Returns:
        타임라인별 음정 데이터 리스트
    """
    # pretty_midi를 우선 사용
    if HAS_PRETTY_MIDI:
        return analyze_midi_file_pretty_midi(midi_file_path, time_resolution, vocal_track_idx)
    
    if not HAS_MIDO:
        print('오류: pretty_midi 또는 mido 라이브러리가 필요합니다.')
        print('설치: pip install pretty_midi 또는 pip install mido')
        return None
    
    # mido를 사용한 기존 방식 (fallback)
    return analyze_midi_file_mido(midi_file_path, time_resolution, vocal_track_idx)

def analyze_midi_file_pretty_midi(midi_file_path, time_resolution=0.05, vocal_track_idx=0):
    """
    pretty_midi를 사용하여 보컬 트랙만 추출합니다.
    """
    try:
        # MIDI 파일 로드
        pm = pretty_midi.PrettyMIDI(midi_file_path)
        print(f'MIDI 파일 로드 완료: {len(pm.instruments)}개 악기, {pm.get_end_time():.2f}초')
        
        # 보컬 트랙 자동 선택 (화음 판별 알고리즘 사용)
        if vocal_track_idx is None:
            candidates = []
            
            print(f'  보컬 트랙 자동 탐색 중...')
            print(f'  {"Track":<6} | {"악기 이름":<15} | {"노트 수":<7} | {"겹침(화음)%":<10} | {"평균 음정":<10} | {"판정"}')
            print(f'  {"-" * 75}')
            
            for track_idx, instrument in enumerate(pm.instruments):
                # 드럼 트랙 제외
                if instrument.is_drum:
                    print(f'  Trk {track_idx:<2} | (Drums)         | {len(instrument.notes):<7} | -          | -          | [드럼]')
                    continue
                
                # 노트가 너무 적으면(50개 미만) 보컬 아님
                if len(instrument.notes) < 50:
                    print(f'  Trk {track_idx:<2} | {instrument.name[:10]:<10} | {len(instrument.notes):<7} | -          | -          | [너무 짧음]')
                    continue
                
                # 화음 판별: 겹침 비율 계산
                sorted_notes = sorted(instrument.notes, key=lambda x: x.start)
                if len(sorted_notes) < 2:
                    continue
                
                total_duration = sorted_notes[-1].end - sorted_notes[0].start
                overlap_duration = 0
                
                # 앞 노트가 끝나기 전에 뒷 노트가 시작되면 '겹침'으로 간주
                for j in range(len(sorted_notes) - 1):
                    curr_note = sorted_notes[j]
                    next_note = sorted_notes[j+1]
                    
                    # 0.05초 이상의 겹침만 인정
                    if curr_note.end > next_note.start + 0.05:
                        overlap = min(curr_note.end, next_note.end) - next_note.start
                        overlap_duration += overlap
                
                # 겹침 비율 (0.0 = 완전 단음/보컬, 0.5 = 절반이 화음/피아노)
                polyphony_rate = overlap_duration / total_duration if total_duration > 0 else 0
                
                # 음역대 확인
                pitches = [n.pitch for n in instrument.notes]
                avg_pitch = np.mean(pitches)
                
                # 판정 로직
                is_vocal_candidate = False
                type_str = ""
                
                # 화음 판별: 평균 음정이 높으면(60 이상) 보컬일 가능성 고려
                if polyphony_rate > 0.3:  # 30% 이상 겹치면 반주 악기
                    type_str = "[악기] 화음"
                elif avg_pitch < 40:      # 너무 낮으면 베이스
                    type_str = "[베이스]"
                elif polyphony_rate > 0.1 and avg_pitch >= 60:  # 화음이 있지만 음정이 높으면 보컬 후보
                    type_str = "[보컬 후보!] (약간의 화음)"
                    is_vocal_candidate = True
                else:
                    type_str = "[보컬 후보!]"
                    is_vocal_candidate = True
                
                print(f'  Trk {track_idx:<2} | {instrument.name[:10]:<10} | {len(instrument.notes):<7} | {polyphony_rate*100:5.1f}%     | {avg_pitch:5.1f}      | {type_str}')
                
                if is_vocal_candidate:
                    # 점수 계산: 화음이 적을수록(+), 노트가 많을수록(+)
                    score = (1 - polyphony_rate) * 100 + (len(instrument.notes) / 100)
                    candidates.append((track_idx, score, instrument))
            
            print(f'  {"-" * 75}')
            
            if candidates:
                best_track = max(candidates, key=lambda item: item[1])
                vocal_track_idx = best_track[0]
                print(f'  [최종 결론] Track {vocal_track_idx}번이 보컬(멜로디)입니다!')
            else:
                print(f'  [경고] 보컬 트랙을 찾지 못했습니다. Track 0을 사용합니다.')
                vocal_track_idx = 0
        
        # 보컬 트랙 선택
        if len(pm.instruments) <= vocal_track_idx:
            print(f'경고: 트랙 {vocal_track_idx}가 없습니다. 첫 번째 트랙을 사용합니다.')
            vocal_track_idx = 0
        
        vocal_track = pm.instruments[vocal_track_idx]
        track_name = vocal_track.name if hasattr(vocal_track, 'name') and vocal_track.name else f'Track {vocal_track_idx}'
        print(f'  보컬 트랙: {track_name} (총 {len(vocal_track.notes)}개 음표)')
        
        if len(vocal_track.notes) == 0:
            print('경고: 보컬 트랙에 음표가 없습니다.')
            return None
        
        # 보컬 트랙의 첫 노트 시작 시간 찾기
        vocal_start_time = min(note.start for note in vocal_track.notes)
        print(f'  보컬 시작 시간: {vocal_start_time:.2f}초 (이전 구간은 반주로 처리)')
        
        # 보컬 노트의 간격 분석 (반주 구간 감지용)
        sorted_notes = sorted(vocal_track.notes, key=lambda x: x.start)
        note_gaps = []  # 노트 간 간격 저장
        for i in range(len(sorted_notes) - 1):
            gap = sorted_notes[i+1].start - sorted_notes[i].end
            if gap > 0:
                note_gaps.append(gap)
        
        # 평균 간격 계산 (반주 구간 판단 기준)
        avg_gap = np.mean(note_gaps) if note_gaps else 0.5
        instrumental_threshold = max(0.3, avg_gap * 1.5)  # 평균의 1.5배 이상이면 반주 구간
        print(f'  보컬 노트 평균 간격: {avg_gap:.2f}초')
        print(f'  반주 구간 임계값: {instrumental_threshold:.2f}초 이상')
        
        # 타임라인별 음정 데이터 생성
        timeline_data = []
        total_time = pm.get_end_time()
        current_time = 0
        
        print(f'분석 중... (총 {total_time:.2f}초, {len(vocal_track.notes)}개 음표)')
        
        while current_time <= total_time:
            # 보컬 시작 시간 이전이면 무조건 null (반주 구간)
            if current_time < vocal_start_time:
                pitch = None
            else:
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
                    # 보컬이 없는 구간 - 추가 검증: 주변 노트와의 간격 확인
                    # 가장 가까운 이전 노트의 끝 시간
                    prev_note_end = None
                    # 가장 가까운 다음 노트의 시작 시간
                    next_note_start = None
                    
                    for note in sorted_notes:
                        if note.end <= current_time:
                            prev_note_end = note.end
                        if note.start > current_time:
                            next_note_start = note.start
                            break
                    
                    # 이전 노트와의 간격이 임계값보다 크면 반주 구간
                    is_instrumental = False
                    if prev_note_end is not None:
                        gap_from_prev = current_time - prev_note_end
                        if gap_from_prev > instrumental_threshold:
                            is_instrumental = True
                    
                    # 다음 노트와의 간격도 확인
                    if next_note_start is not None and not is_instrumental:
                        gap_to_next = next_note_start - current_time
                        if gap_to_next > instrumental_threshold:
                            is_instrumental = True
                    
                    # 반주 구간이면 null, 짧은 간격이면 이전/다음 노트의 음정 사용
                    if is_instrumental:
                        pitch = None
                    else:
                        # 짧은 간격이면 가장 가까운 노트의 음정 사용 (레가토 처리)
                        if prev_note_end is not None:
                            # 이전 노트 찾기
                            for note in reversed(sorted_notes):
                                if note.end <= current_time:
                                    pitch = midi_note_to_frequency(note.pitch)
                                    break
                        elif next_note_start is not None:
                            # 다음 노트 찾기
                            for note in sorted_notes:
                                if note.start > current_time:
                                    pitch = midi_note_to_frequency(note.pitch)
                                    break
                        else:
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
        
        return timeline_data
    
    except Exception as e:
        print(f'pretty_midi 분석 오류: {str(e)}')
        import traceback
        traceback.print_exc()
        return None

def analyze_midi_file_mido(midi_file_path, time_resolution=0.05, vocal_track_idx=0):
    """
    mido를 사용한 기존 분석 방식 (fallback)
    """
    
    try:
        mid = mido.MidiFile(midi_file_path)
        print(f'MIDI 파일 로드 완료: {len(mid.tracks)}개 트랙, {mid.length:.2f}초')
        print(f'  ticks_per_beat: {mid.ticks_per_beat}')
        
        # 보컬 트랙 자동 선택 (화음 판별 알고리즘 사용)
        if vocal_track_idx is None:
            candidates = []
            
            print(f'  보컬 트랙 자동 탐색 중...')
            print(f'  {"Track":<6} | {"노트 수":<7} | {"겹침(화음)%":<10} | {"평균 음정":<10} | {"판정"}')
            print(f'  {"-" * 60}')
            
            for track_idx, track in enumerate(mid.tracks):
                # 노트 이벤트 수집 (start, end, pitch)
                current_ticks = 0
                tempo = 500000
                note_events = []  # (start_time, end_time, pitch)
                active_notes = {}  # {note: (start_time, start_ticks, tempo)}
                
                for msg in track:
                    current_ticks += msg.time
                    if msg.type == 'set_tempo':
                        tempo = msg.tempo
                    
                    current_time = mido.tick2second(current_ticks, mid.ticks_per_beat, tempo)
                    
                    if msg.type == 'note_on' and msg.velocity > 0:
                        active_notes[msg.note] = (current_time, current_ticks, tempo)
                    elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                        if msg.note in active_notes:
                            start_time, start_ticks, start_tempo = active_notes[msg.note]
                            end_time = mido.tick2second(current_ticks, mid.ticks_per_beat, start_tempo)
                            note_events.append({
                                'start': start_time,
                                'end': end_time,
                                'pitch': msg.note
                            })
                            del active_notes[msg.note]
                
                # 남아있는 노트 처리
                for note, (start_time, start_ticks, start_tempo) in active_notes.items():
                    end_time = mid.length
                    note_events.append({
                        'start': start_time,
                        'end': end_time,
                        'pitch': note
                    })
                
                if len(note_events) < 50:
                    if len(note_events) > 0:
                        print(f'  Trk {track_idx:<2} | {len(note_events):<7} | -          | -          | [너무 짧음]')
                    continue
                
                # 화음 판별: 겹침 비율 계산
                sorted_notes = sorted(note_events, key=lambda x: x['start'])
                if len(sorted_notes) < 2:
                    continue
                
                total_duration = sorted_notes[-1]['end'] - sorted_notes[0]['start']
                overlap_duration = 0
                
                # 앞 노트가 끝나기 전에 뒷 노트가 시작되면 '겹침'으로 간주
                for j in range(len(sorted_notes) - 1):
                    curr_note = sorted_notes[j]
                    next_note = sorted_notes[j+1]
                    
                    # 0.05초 이상의 겹침만 인정
                    if curr_note['end'] > next_note['start'] + 0.05:
                        overlap = min(curr_note['end'], next_note['end']) - next_note['start']
                        overlap_duration += overlap
                
                # 겹침 비율 (100%를 넘을 수 없음)
                polyphony_rate = min(1.0, overlap_duration / total_duration) if total_duration > 0 else 0
                
                # 음역대 확인
                pitches = [n['pitch'] for n in note_events]
                avg_pitch = sum(pitches) / len(pitches) if pitches else 0
                
                # 판정 로직
                is_vocal_candidate = False
                type_str = ""
                
                # 화음 판별: 평균 음정이 높으면(60 이상) 보컬일 가능성 고려
                if polyphony_rate > 0.3:  # 30% 이상 겹치면 반주 악기
                    type_str = "[악기] 화음"
                elif avg_pitch < 40:      # 너무 낮으면 베이스
                    type_str = "[베이스]"
                elif polyphony_rate > 0.1 and avg_pitch >= 60:  # 화음이 있지만 음정이 높으면 보컬 후보
                    type_str = "[보컬 후보!] (약간의 화음)"
                    is_vocal_candidate = True
                else:
                    type_str = "[보컬 후보!]"
                    is_vocal_candidate = True
                
                print(f'  Trk {track_idx:<2} | {len(note_events):<7} | {polyphony_rate*100:5.1f}%     | {avg_pitch:5.1f}      | {type_str}')
                
                if is_vocal_candidate:
                    # 점수 계산: 화음이 적을수록(+), 노트가 많을수록(+)
                    score = (1 - polyphony_rate) * 100 + (len(note_events) / 100)
                    candidates.append((track_idx, score, note_events))
            
            print(f'  {"-" * 60}')
            
            if candidates:
                best_track = max(candidates, key=lambda item: item[1])
                vocal_track_idx = best_track[0]
                print(f'  [최종 결론] Track {vocal_track_idx}번이 보컬(멜로디)입니다!')
            else:
                # 보컬 후보가 없으면 노트가 있는 트랙 중에서 선택
                # 평균 음정이 높은 트랙 우선
                fallback_tracks = []
                for track_idx, track in enumerate(mid.tracks):
                    current_ticks = 0
                    tempo = 500000
                    note_events = []
                    active_notes = {}
                    
                    for msg in track:
                        current_ticks += msg.time
                        if msg.type == 'set_tempo':
                            tempo = msg.tempo
                        current_time = mido.tick2second(current_ticks, mid.ticks_per_beat, tempo)
                        if msg.type == 'note_on' and msg.velocity > 0:
                            active_notes[msg.note] = (current_time, current_ticks, tempo)
                        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                            if msg.note in active_notes:
                                start_time, start_ticks, start_tempo = active_notes[msg.note]
                                end_time = mido.tick2second(current_ticks, mid.ticks_per_beat, start_tempo)
                                note_events.append({'start': start_time, 'end': end_time, 'pitch': msg.note})
                                del active_notes[msg.note]
                    
                    if len(note_events) > 0:
                        avg_pitch = sum(n['pitch'] for n in note_events) / len(note_events)
                        fallback_tracks.append((track_idx, avg_pitch, len(note_events)))
                
                if fallback_tracks:
                    # 평균 음정이 높고 노트가 많은 트랙 선택
                    best_fallback = max(fallback_tracks, key=lambda x: (x[1] if x[1] >= 50 else 0, x[2]))
                    vocal_track_idx = best_fallback[0]
                    print(f'  [경고] 보컬 트랙을 찾지 못했습니다. Track {vocal_track_idx}을 사용합니다. (평균 MIDI: {best_fallback[1]:.1f}, 노트: {best_fallback[2]}개)')
                else:
                    print(f'  [경고] 노트가 있는 트랙이 없습니다. Track 0을 사용합니다.')
                    vocal_track_idx = 0
        
        # 보컬 트랙 지정 여부 확인
        if vocal_track_idx is not None:
            print(f'  사용할 보컬 트랙: Track {vocal_track_idx}')
            tracks_to_process = [(vocal_track_idx, mid.tracks[vocal_track_idx])]
        else:
            print(f'  모든 트랙 처리 (가장 높은 음정 선택)')
            tracks_to_process = enumerate(mid.tracks)
        
        # 트랙의 노트 이벤트 수집
        notes = []  # (start_time, end_time, note_number, frequency, track_idx)
        active_notes = {}  # {track_idx: {channel: {note: (start_time, start_ticks)}}}
        
        # 지정된 트랙(들)을 순회하며 노트 이벤트 수집
        for track_idx, track in tracks_to_process:
            if track_idx not in active_notes:
                active_notes[track_idx] = {}
            
            current_ticks = 0
            tempo = 500000  # 기본 템포 (120 BPM = 500000 microseconds per beat)
            
            for msg in track:
                current_ticks += msg.time
                
                # 템포 변경 메시지 처리
                if msg.type == 'set_tempo':
                    tempo = msg.tempo
                
                # ticks를 초로 변환
                current_time = mido.tick2second(current_ticks, mid.ticks_per_beat, tempo)
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    # 노트 시작
                    channel = msg.channel if hasattr(msg, 'channel') else 0
                    if channel not in active_notes[track_idx]:
                        active_notes[track_idx][channel] = {}
                    active_notes[track_idx][channel][msg.note] = (current_time, current_ticks, tempo)
                    
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    # 노트 종료
                    channel = msg.channel if hasattr(msg, 'channel') else 0
                    if channel in active_notes[track_idx] and msg.note in active_notes[track_idx][channel]:
                        start_time, start_ticks, start_tempo = active_notes[track_idx][channel][msg.note]
                        # 시작 시점의 템포를 사용하여 정확한 시간 계산
                        end_time = mido.tick2second(current_ticks, mid.ticks_per_beat, start_tempo)
                        notes.append({
                            'start': start_time,
                            'end': end_time,
                            'note': msg.note,
                            'frequency': midi_note_to_frequency(msg.note),
                            'track': track_idx
                        })
                        del active_notes[track_idx][channel][msg.note]
        
        # 남아있는 노트 처리 (끝까지 지속되는 노트)
        for track_idx, track_notes in active_notes.items():
            for channel, channel_notes in track_notes.items():
                for note, (start_time, start_ticks, start_tempo) in channel_notes.items():
                    notes.append({
                        'start': start_time,
                        'end': mid.length,
                        'note': note,
                        'frequency': midi_note_to_frequency(note),
                        'track': track_idx
                    })
        
        print(f'  총 {len(notes)}개 노트 수집 (모든 트랙)')
        
        if not notes:
            print('경고: MIDI 파일에서 노트를 찾을 수 없습니다.')
            return None
        
        # 보컬 트랙의 첫 노트 시작 시간 찾기
        vocal_start_time = None
        if vocal_track_idx is not None:
            vocal_track_notes = [n for n in notes if n['track'] == vocal_track_idx]
            if vocal_track_notes:
                vocal_start_time = min(n['start'] for n in vocal_track_notes)
                print(f'  보컬 시작 시간: {vocal_start_time:.2f}초 (이전 구간은 반주로 처리)')
        
        # 보컬 노트의 간격 분석 (반주 구간 감지용) - mido 버전
        if vocal_track_idx is not None:
            vocal_notes_sorted = sorted([n for n in notes if n['track'] == vocal_track_idx], key=lambda x: x['start'])
            note_gaps = []
            for i in range(len(vocal_notes_sorted) - 1):
                gap = vocal_notes_sorted[i+1]['start'] - vocal_notes_sorted[i]['end']
                if gap > 0:
                    note_gaps.append(gap)
            
            avg_gap = np.mean(note_gaps) if note_gaps else 0.5
            instrumental_threshold = max(0.3, avg_gap * 1.5)
            print(f'  보컬 노트 평균 간격: {avg_gap:.2f}초')
            print(f'  반주 구간 임계값: {instrumental_threshold:.2f}초 이상')
        else:
            instrumental_threshold = 0.5
            vocal_notes_sorted = []
        
        # 타임라인별 음정 데이터 생성
        timeline_data = []
        total_time = mid.length
        current_time = 0
        
        print(f'분석 중... (총 {total_time:.2f}초, {len(notes)}개 노트)')
        
        while current_time <= total_time:
            # 보컬 시작 시간 이전이면 무조건 null (반주 구간)
            if vocal_start_time is not None and current_time < vocal_start_time:
                pitch = None
            else:
                # 현재 시간에 활성화된 노트 찾기
                active_notes_at_time = []
                for note_info in notes:
                    if note_info['start'] <= current_time < note_info['end']:
                        active_notes_at_time.append(note_info)
                
                # 보컬 트랙이 지정된 경우: 해당 트랙의 음만 사용
                if vocal_track_idx is not None:
                    vocal_notes = [n for n in active_notes_at_time if n['track'] == vocal_track_idx]
                    if vocal_notes:
                        # 보컬 트랙의 음이 있으면 사용 (여러 음이 있으면 가장 높은 것)
                        pitch = max(vocal_notes, key=lambda x: x['frequency'])['frequency']
                    else:
                        # 보컬이 없는 구간 - 추가 검증: 주변 노트와의 간격 확인
                        prev_note_end = None
                        next_note_start = None
                        
                        for note in vocal_notes_sorted:
                            if note['end'] <= current_time:
                                prev_note_end = note['end']
                            if note['start'] > current_time:
                                next_note_start = note['start']
                                break
                        
                        is_instrumental = False
                        if prev_note_end is not None:
                            gap_from_prev = current_time - prev_note_end
                            if gap_from_prev > instrumental_threshold:
                                is_instrumental = True
                        
                        if next_note_start is not None and not is_instrumental:
                            gap_to_next = next_note_start - current_time
                            if gap_to_next > instrumental_threshold:
                                is_instrumental = True
                        
                        if is_instrumental:
                            pitch = None
                        else:
                            # 짧은 간격이면 가장 가까운 노트의 음정 사용
                            if prev_note_end is not None:
                                for note in reversed(vocal_notes_sorted):
                                    if note['end'] <= current_time:
                                        pitch = note['frequency']
                                        break
                            elif next_note_start is not None:
                                for note in vocal_notes_sorted:
                                    if note['start'] > current_time:
                                        pitch = note['frequency']
                                        break
                            else:
                                pitch = None
                else:
                    # 모든 트랙 처리: 멜로디 라인 추출 (가장 높은 음정 선택)
                    # 단, 너무 낮은 음(베이스, 60 미만)은 제외
                    melody_notes = [n for n in active_notes_at_time if n['note'] >= 60]
                    if melody_notes:
                        # 가장 높은 음정 선택
                        pitch = max(melody_notes, key=lambda x: x['frequency'])['frequency']
                    elif active_notes_at_time:
                        # 60 미만의 음만 있으면 그 중 가장 높은 것 선택
                        pitch = max(active_notes_at_time, key=lambda x: x['frequency'])['frequency']
                    else:
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
        
        return timeline_data
    
    except Exception as e:
        print(f'MIDI 분석 오류: {str(e)}')
        import traceback
        traceback.print_exc()
        return None


def main():
    """
    메인 함수
    """
    # 입력 파일 경로 (명령줄 인자로 받거나 기본값 사용)
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # hello.mid 파일이 있으면 사용, 없으면 기본 파일 사용
        if os.path.exists('public/assets/hello.mid'):
            input_file = 'public/assets/hello.mid'
        elif os.path.exists('static/assets/music1.mp4'):
            input_file = 'static/assets/music1.mp4'
        else:
            print('오류: 분석할 파일을 찾을 수 없습니다.')
            print('사용법: python analyze_music.py <파일경로>')
            sys.exit(1)
    
    # 출력 파일 경로
    output_file = 'static/assets/music_pitch_data.json'
    
    if not os.path.exists(input_file):
        print(f'파일을 찾을 수 없습니다: {input_file}')
        sys.exit(1)
    
    print(f'음악 파일 분석 시작: {input_file}')
    print(f'출력 파일: {output_file}')
    
    # 파일 확장자에 따라 분석 방법 선택
    file_ext = os.path.splitext(input_file)[1].lower()
    
    if file_ext == '.mid' or file_ext == '.midi':
        # MIDI 파일 분석
        # 보컬 트랙 인덱스 (명령줄 인자로 받거나, golden.mid의 경우 Track 0이 보컬)
        vocal_track = None
        if len(sys.argv) > 2:
            try:
                vocal_track = int(sys.argv[2])
            except ValueError:
                pass
        
        # golden.mid의 경우 자동으로 보컬 트랙 찾기 (코드 내에서 처리)
        # vocal_track은 None으로 두면 analyze_midi_file에서 자동으로 찾음
        
        timeline_data = analyze_midi_file(input_file, time_resolution=0.05, vocal_track_idx=vocal_track)
    else:
        # 오디오 파일 분석 (librosa는 MP4를 직접 지원)
        timeline_data = analyze_audio_file(input_file, window_size=0.1, hop_size=0.05)
    
    if timeline_data:
        # JSON 파일로 저장
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        
        print(f'\n분석 완료! {len(timeline_data)}개의 데이터 포인트 생성')
        print(f'결과 저장: {output_file}')
        
        # 통계 정보 출력
        pitches = [d['pitch'] for d in timeline_data if d['pitch']]
        if pitches:
            print(f'\n통계:')
            print(f'  유효한 음정 데이터: {len(pitches)}/{len(timeline_data)}')
            print(f'  평균 음정: {np.mean(pitches):.2f} Hz')
            print(f'  최소 음정: {np.min(pitches):.2f} Hz')
            print(f'  최대 음정: {np.max(pitches):.2f} Hz')
        else:
            print('\n경고: 유효한 음정 데이터가 없습니다.')
    else:
        print('분석 실패')
        sys.exit(1)

if __name__ == '__main__':
    main()

