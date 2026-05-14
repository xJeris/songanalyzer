import os
import numpy as np
import librosa


def analyze_song(file_path: str, original_filename: str = None, duration: int = 60) -> dict:
    """Analyze an MP3 file for BPM and beat offset using multiple algorithms.

    Runs three independent tempo detection methods and cross-checks them.
    Agreement across methods indicates high confidence.

    Args:
        duration: Seconds of audio to analyze. 0 means full song.
    """
    if not os.path.isfile(file_path):
        return _error(f"File not found: {file_path}")

    # Get full song duration first
    try:
        full_duration = librosa.get_duration(path=file_path)
    except Exception:
        full_duration = None

    try:
        load_dur = duration if duration > 0 else None
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=load_dur)
    except Exception as exc:
        return _error(f"Could not load audio file: {exc}")

    analyzed_duration = round(len(y) / sr, 1) if sr > 0 else 0

    if len(y) == 0:
        return _error("Audio file appears to be empty")

    hop_length = 512

    # Shared onset envelope — all methods build on this
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    except Exception as exc:
        return _error(f"Onset detection failed: {exc}")

    # --- Method 1: Dynamic Programming (Ellis 2007) ---
    offset_dp = None
    try:
        tempo_dp, beat_frames = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr, hop_length=hop_length
        )
        bpm_dp = float(tempo_dp) if not hasattr(tempo_dp, "__len__") else float(tempo_dp[0])
        beat_times_dp = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)
        if len(beat_times_dp) > 0:
            offset_dp = int(round(beat_times_dp[0] * 1000))
    except Exception:
        bpm_dp = None
        beat_frames = np.array([])

    # --- Method 2: Autocorrelation Tempogram ---
    try:
        tempo_ac = librosa.feature.tempo(
            onset_envelope=onset_env, sr=sr, hop_length=hop_length
        )
        bpm_ac = float(tempo_ac[0]) if len(tempo_ac) > 0 else None
    except Exception:
        bpm_ac = None

    # --- Method 3: Predominant Local Pulse (Grosche & Muller 2011) ---
    offset_plp = None
    try:
        pulse = librosa.beat.plp(
            onset_envelope=onset_env, sr=sr, hop_length=hop_length
        )
        beats_plp = np.flatnonzero(librosa.util.localmax(pulse))
        if len(beats_plp) > 1:
            frame_rate = sr / hop_length
            bpm_plp = round(60.0 * frame_rate / np.median(np.diff(beats_plp)), 1)
            beat_times_plp = librosa.frames_to_time(beats_plp, sr=sr, hop_length=hop_length)
            if len(beat_times_plp) > 0:
                offset_plp = int(round(beat_times_plp[0] * 1000))
        else:
            bpm_plp = None
    except Exception:
        bpm_plp = None

    # --- Build methods list and determine consensus ---
    methods = []
    valid_bpms = []

    if bpm_dp is not None:
        methods.append({"name": "Dynamic Programming", "bpm": round(bpm_dp, 1), "offset_ms": offset_dp})
        valid_bpms.append(bpm_dp)
    if bpm_ac is not None:
        methods.append({"name": "Autocorrelation", "bpm": round(bpm_ac, 1), "offset_ms": None})
        valid_bpms.append(bpm_ac)
    if bpm_plp is not None:
        methods.append({"name": "Local Pulse", "bpm": round(bpm_plp, 1), "offset_ms": offset_plp})
        valid_bpms.append(bpm_plp)

    if not valid_bpms:
        return _error("All tempo detection methods failed")

    # Normalize half/double tempo before comparing.
    # Beat trackers sometimes report half or double the actual tempo.
    # Use the DP result (most reliable) as reference.
    reference = valid_bpms[0]
    normalized = []
    for bpm in valid_bpms:
        candidate = bpm
        # If a method reports roughly half or double, snap it
        if reference > 0:
            if 0.45 < bpm / reference < 0.55:
                candidate = bpm * 2
            elif 1.9 < bpm / reference < 2.1:
                candidate = bpm / 2
        normalized.append(candidate)

    # Primary BPM: median of normalized values
    primary_bpm = round(float(np.median(normalized)), 1)

    # Confidence: how well methods agree (within 5% of median)
    within_threshold = sum(
        1 for b in normalized if abs(b - primary_bpm) / primary_bpm < 0.05
    )
    if within_threshold == len(normalized) and len(normalized) >= 2:
        confidence = "high"
    elif within_threshold >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    # Tag each method with whether its raw BPM agrees with consensus.
    # Use the raw (not normalized) BPM — if a method tracked at double tempo,
    # its beat positions and offset will be different even if normalized BPM agrees.
    for m in methods:
        m["bpm_agrees"] = bool(abs(m["bpm"] - primary_bpm) / primary_bpm < 0.05)

    # Primary offset: prefer offsets from methods whose BPM agrees with consensus.
    # If a method's BPM is an outlier, its offset is less trustworthy.
    agreeing_offsets = [
        m["offset_ms"] for m in methods
        if m["bpm_agrees"] and m["offset_ms"] is not None
    ]

    if agreeing_offsets:
        offset_ms = min(agreeing_offsets)
    elif offset_dp is not None:
        offset_ms = offset_dp
    elif offset_plp is not None:
        offset_ms = offset_plp
    else:
        offset_ms = 0

    # Detect if half or double tempo is plausible.
    # Only offer alternative if a method actually reported roughly half or double.
    # When a method reports double, the alternative is half (and vice versa).
    alt_bpm = None
    for bpm in valid_bpms:
        ratio = bpm / primary_bpm if primary_bpm > 0 else 0
        if 0.45 < ratio < 0.55:
            # A method saw half tempo — offer double as alternative
            alt_bpm = round(primary_bpm * 2, 1)
            break
        elif 1.9 < ratio < 2.1:
            # A method saw double tempo — offer half as alternative
            alt_bpm = round(primary_bpm / 2, 1)
            break

    # Tempo variance detection (using DP beat positions)
    tempo_unstable = False
    warning = None
    beat_times_for_var = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length) if len(beat_frames) > 0 else np.array([])

    if len(beat_times_for_var) >= 4:
        intervals = np.diff(beat_times_for_var)
        if len(intervals) > 0:
            median_interval = np.median(intervals)
            if median_interval > 0:
                cv = np.std(intervals) / median_interval
                if cv > 0.1:
                    tempo_unstable = True
                    warning = (
                        f"Tempo may not be consistent throughout the song "
                        f"(beat interval variation: {cv:.0%}). "
                        f"The reported BPM is the dominant tempo."
                    )

    return {
        "bpm": primary_bpm,
        "alt_bpm": alt_bpm,
        "offset_ms": offset_ms,
        "filename": original_filename or os.path.basename(file_path),
        "confidence": confidence,
        "methods": methods,
        "tempo_unstable": tempo_unstable,
        "warning": warning,
        "song_duration": round(full_duration, 1) if full_duration else None,
        "analyzed_duration": analyzed_duration,
        "error": None,
    }


def _error(message: str) -> dict:
    return {
        "bpm": None,
        "offset_ms": None,
        "filename": None,
        "confidence": None,
        "methods": [],
        "tempo_unstable": False,
        "warning": None,
        "error": message,
    }
