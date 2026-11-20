#!/usr/bin/env python3
"""Change the tempo of a track (or of one region of it) without changing its pitch.

Uses ffmpeg's `atempo` (WSOLA time stretching): speech stays at the same pitch, only faster/slower.
Clean for speech within roughly ±25 %; the allowed range is 0.5×…2× speed.

As a module: stretch(ffmpeg, src, dst, speed, start=None, end=None, codec_args=()).
From the command line:
    python3 tempo.py in.wav out.wav --speed 1.1            # 10 % faster (shorter)
    python3 tempo.py in.wav out.wav --length 3.2           # make the whole file 3.2 s long
    python3 tempo.py in.wav out.wav --speed 0.9 --start 1.0 --end 2.5   # only that region, slower
"""
import argparse
import shutil
import subprocess
import sys

MIN_SPEED, MAX_SPEED = 0.5, 2.0
XFADE = 0.01                      # 10 ms crossfade at region seams (no clicks)


def _atempo(speed):
    """atempo chain for the given speed (one stage handles 0.5…2.0)."""
    stages = []
    s = speed
    while s > 2.0:
        stages.append(2.0)
        s /= 2.0
    while s < 0.5:
        stages.append(0.5)
        s /= 0.5
    stages.append(s)
    return ",".join(f"atempo={x:.6f}" for x in stages)


def duration(ffprobe, path):
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def stretch(ffmpeg, src, dst, speed, start=None, end=None, total=None, codec_args=()):
    """Write `src` to `dst` with tempo × speed (>1 faster/shorter, <1 slower/longer).
    start/end (s) — only that region; total — duration of src (needed for a region)."""
    speed = float(speed)
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"Швидкість {speed:.2f}× поза межами {MIN_SPEED}…{MAX_SPEED}×")
    if start is None or end is None:
        cmd = [ffmpeg, "-v", "error", "-y", "-i", src, "-af", _atempo(speed), "-map_metadata", "0",
               *codec_args, dst]
    else:
        start, end = max(0.0, float(start)), float(end)
        if total is not None:
            end = min(end, total)
        if end - start < 0.05:
            raise ValueError("Виділення закоротке")
        head = start > XFADE * 2
        tail = total is None or end < total - XFADE * 2
        parts, chains = [], []
        n = 1 + head + tail
        chains.append(f"[0:a]asplit={n}" + "".join(f"[s{i}]" for i in range(n)))
        i = 0
        if head:
            chains.append(f"[s{i}]atrim=0:{start:.4f},asetpts=PTS-STARTPTS[a]")
            parts.append("[a]")
            i += 1
        chains.append(f"[s{i}]atrim={start:.4f}:{end:.4f},asetpts=PTS-STARTPTS,{_atempo(speed)}[b]")
        parts.append("[b]")
        i += 1
        if tail:
            chains.append(f"[s{i}]atrim={end:.4f},asetpts=PTS-STARTPTS[c]")
            parts.append("[c]")
        cur = parts[0]
        for k, nxt in enumerate(parts[1:]):
            out = "[out]" if k == len(parts) - 2 else f"[x{k}]"
            chains.append(f"{cur}{nxt}acrossfade=d={XFADE}:c1=tri:c2=tri{out}")
            cur = out
        if len(parts) == 1:
            chains[-1] = chains[-1].replace("[b]", "[out]")
        cmd = [ffmpeg, "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(chains), "-map", "[out]",
               "-map_metadata", "0", *codec_args, dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-300:])


def main():
    ap = argparse.ArgumentParser(description="Change tempo without changing pitch (ffmpeg atempo).")
    ap.add_argument("src")
    ap.add_argument("dst")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--speed", type=float, help="tempo factor: 1.1 = 10%% faster/shorter, 0.9 = slower/longer")
    g.add_argument("--length", type=float, help="target length in seconds (of the region, if given)")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        sys.exit("ffmpeg/ffprobe not found")
    total = duration(ffprobe, a.src)
    region = (a.end if a.end is not None else total) - (a.start or 0.0)
    speed = a.speed if a.speed else region / a.length
    part = a.start is not None or a.end is not None
    stretch(ffmpeg, a.src, a.dst, speed, ((a.start or 0.0) if part else None),
            (a.end if a.end is not None else total) if part else None, total)
    print(f"{total:.3f} s → {duration(ffprobe, a.dst):.3f} s (speed {speed:.3f}×)")


if __name__ == "__main__":
    main()
