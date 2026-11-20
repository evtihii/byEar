"""Automatic check of an agent's result against the reference (and the previous version).

Measures duration, integrated loudness (LUFS) and median pitch (f0) with ffmpeg + pure Python
(no numpy), and flags large differences. The reviewer sees the numbers next to the agent's reply,
so a wrong voice, a pitch-shifted take or a much quieter file shows up before listening.
"""
import array
import math
import operator
import subprocess

SR = 8000            # pitch analysis rate
WIN = 320            # 40 ms window
HOP = 400            # 50 ms hop
LAG_MIN = SR // 800  # 800 Hz
LAG_MAX = SR // 70   # 70 Hz
MAX_SEC = 20         # analyse at most the first 20 s

# thresholds for "noticeably different"
DF0 = 0.20           # 20 % pitch
DLUFS = 3.0          # 3 LU loudness
DDUR = 0.15          # 15 % length


def _pcm(ffmpeg, full):
    r = subprocess.run([ffmpeg, "-v", "error", "-t", str(MAX_SEC), "-i", full, "-ac", "1", "-ar", str(SR),
                        "-f", "s16le", "-"], capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    return a


def pitch(ffmpeg, full):
    """Median f0 in Hz over voiced frames, or None."""
    x = _pcm(ffmpeg, full)
    if len(x) < WIN + LAG_MAX:
        return None
    peak = max(1, max(abs(v) for v in x))
    f0s = []
    mul = operator.mul
    for st in range(0, len(x) - WIN - LAG_MAX, HOP):
        a = x[st:st + WIN]
        e0 = sum(map(mul, a, a))
        if e0 < (0.03 * peak) ** 2 * WIN:            # quiet frame
            continue
        best, best_r = None, 0.0
        rs = []
        for lag in range(LAG_MIN, LAG_MAX + 1):
            b = x[st + lag:st + lag + WIN]
            eb = sum(map(mul, b, b))
            r = sum(map(mul, a, b)) / math.sqrt(e0 * eb) if eb else 0.0
            rs.append((lag, r))
            if r > best_r:
                best, best_r = lag, r
        if best is None or best_r < 0.6:              # unvoiced
            continue
        # prefer the first real peak close to the maximum (avoids dropping an octave),
        # then refine it with parabolic interpolation between neighbouring lags
        rv = [r for _, r in rs]
        k = rv.index(best_r)
        for i in range(1, len(rv) - 1):
            if rv[i] >= rv[i - 1] and rv[i] >= rv[i + 1] and rv[i] >= 0.85 * best_r:
                k = i
                break
        lag = float(rs[k][0])
        if 0 < k < len(rv) - 1:
            den = rv[k - 1] - 2 * rv[k] + rv[k + 1]
            if den:
                lag += 0.5 * (rv[k - 1] - rv[k + 1]) / den
        f0s.append(SR / lag)
    if len(f0s) < 5:
        return None
    f0s.sort()
    return round(f0s[len(f0s) // 2])


def measure(ffmpeg, measure_lufs, duration, full):
    """{dur, lufs, f0} for a file (values may be None)."""
    out = {"dur": None, "lufs": None, "f0": None}
    try:
        out["dur"] = round(duration(full), 2)
    except Exception:                                 # noqa: BLE001
        pass
    try:
        out["lufs"] = measure_lufs(full)[0]
    except Exception:                                 # noqa: BLE001
        pass
    try:
        out["f0"] = pitch(ffmpeg, full)
    except Exception:                                 # noqa: BLE001
        pass
    return out


def compare(new, ref, before=None):
    """List of human-readable warnings (Ukrainian, shown in the UI).

    Pitch is compared with the version before the edit (same voice): the reference is usually another actor
    in another language, so its pitch says nothing about whether our voice changed. Loudness and length are
    compared with the reference."""
    warn = []
    if not new:
        return warn
    if before and new["f0"] and before["f0"] and abs(new["f0"] - before["f0"]) / before["f0"] > DF0:
        warn.append(f"висота голосу змінилась: {new['f0']} Гц, до правки {before['f0']} Гц")
    if not ref:
        return warn
    if new["lufs"] is not None and ref["lufs"] is not None and abs(new["lufs"] - ref["lufs"]) > DLUFS:
        warn.append(f"гучність {new['lufs']} LUFS проти {ref['lufs']} в еталоні")
    if new["dur"] and ref["dur"] and abs(new["dur"] - ref["dur"]) / ref["dur"] > DDUR:
        warn.append(f"довжина {new['dur']} с проти {ref['dur']} с в еталоні")
    return warn
