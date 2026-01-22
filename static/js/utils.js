// 주파수를 계이름으로 변환하는 유틸리티 함수

// 계이름 (한국어 - 12음계)
const NOTE_NAMES_KO = ['도', '도#', '레', '레#', '미', '파', '파#', '솔', '솔#', '라', '라#', '시'];
const NOTE_NAMES_EN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

/**
 * 주파수를 MIDI 노트 번호로 변환
 * @param {number} frequency - 주파수 (Hz)
 * @returns {number|null} MIDI 노트 번호 (0-127)
 */
function frequencyToMidi(frequency) {
    if (!frequency || frequency <= 0) return null;
    // A4 (440Hz) = MIDI 69
    return 69 + 12 * Math.log2(frequency / 440);
}

/**
 * MIDI 노트 번호를 계이름으로 변환
 * @param {number} midiNote - MIDI 노트 번호
 * @param {boolean} useKorean - 한국어 사용 여부
 * @returns {string} 계이름 (예: "도4", "C4")
 */
function midiToNoteName(midiNote, useKorean = true) {
    if (midiNote === null || midiNote === undefined || isNaN(midiNote)) {
        return '-';
    }
    
    const note = Math.round(midiNote);
    const octave = Math.floor(note / 12) - 1;
    const noteIndex = note % 12;
    
    const noteName = useKorean ? NOTE_NAMES_KO[noteIndex] : NOTE_NAMES_EN[noteIndex];
    
    return `${noteName}${octave}`;
}

/**
 * 주파수를 계이름으로 직접 변환
 * @param {number} frequency - 주파수 (Hz)
 * @param {boolean} useKorean - 한국어 사용 여부
 * @returns {string} 계이름 (예: "도4", "C4")
 */
function frequencyToNoteName(frequency, useKorean = true) {
    if (!frequency || frequency <= 0) return '-';
    const midiNote = frequencyToMidi(frequency);
    return midiToNoteName(midiNote, useKorean);
}

