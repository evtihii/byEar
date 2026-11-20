#!/usr/bin/env python3
"""Add echo / room reverb to a track (or to one region of it) with two knobs: amount and tail.

A synthetic room response (a few early reflections + noise decaying to −60 dB over `tail` seconds,
darkened by a low-pass) is convolved with the voice (ffmpeg `afir`) and mixed back with the dry voice.
The track keeps its length; the reverb tail after a region spills into what follows, like a real room.

As a module: add(ffmpeg, src, dst, amount, tail, start=None, end=None, total=None, tone=4000, codec_args=()).
From the command line:
    python3 echo.py in.wav out.wav --amount 30 --tail 1.0               # whole file, 30 % echo, 1 s tail
    python3 echo.py in.wav out.wav --amount 50 --tail 2 --start 1 --end 2.4   # only that region
"""
import argparse
import array
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile

SR = 48000
MAX_TAIL = 4.0


def make_ir(path, tail, tone=4000.0, seed=7):
    """Room impulse response as raw float32 mono at 48 kHz."""
    rnd = random.Random(seed)
    n = int(SR * min(MAX_TAIL, tail) * 1.05) + 1
    ir = [0.0] * n
    # early reflections in the first ~60 ms
    for d, g in ((0.011, 0.55), (0.019, 0.42), (0.027, 0.35), (0.041, 0.28), (0.056, 0.22)):
        k = int(d * SR)
        if k < n:
            ir[k] += g * (1 if rnd.random() > 0.5 else -1)
    # diffuse tail: noise decaying to −60 dB over `tail` seconds
    a = 6.9 / max(0.05, tail)
    for i in range(int(0.008 * SR), n):
        ir[i] += rnd.gauss(0, 0.35) * math.exp(-a * i / SR)
    # darken with a one-pole low-pass
    c = math.exp(-2 * math.pi * tone / SR)
    y = 0.0
    for i in range(n):
        y = (1 - c) * ir[i] + c * y
        ir[i] = y
    e = math.sqrt(sum(v * v for v in ir)) or 1.0
    with open(path, "wb") as f:
        array.array("f", (v / e for v in ir)).tofile(f)


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg: " + p.stderr.strip()[-300:])


def _rms(ffmpeg, f, start=None, end=None):
    """RMS level in dB of the file or of [start, end]."""
    cut = ["-ss", f"{start:.3f}", "-t", f"{max(0.01, end - start):.3f}"] if start is not None else []
    p = subprocess.run([ffmpeg, "-hide_banner", "-nostats", *cut, "-i", f, "-af", "astats=metadata=0",
                        "-f", "null", "-"], capture_output=True, text=True)
    import re
    m = re.findall(r"RMS level dB:\s*(-?[\d.]+|-inf)", p.stderr)
    v = m[-1] if m else "-inf"
    return -120.0 if v == "-inf" else float(v)


def add(ffmpeg, src, dst, amount, tail, start=None, end=None, total=None, tone=4000.0, codec_args=()):
    """amount 0…100 (% of echo mixed in), tail 0.1…4 s (time for the echo to die out)."""
    amount, tail = float(amount), float(tail)
    if not 0 < amount <= 100:
        raise ValueError("Сила луни — від 1 до 100 %")
    if not 0.1 <= tail <= MAX_TAIL:
        raise ValueError(f"Хвіст луни — від 0.1 до {MAX_TAIL:g} с")
    tmp = tempfile.mkdtemp()
    try:
        ir = os.path.join(tmp, "ir.f32")
        make_ir(ir, tail, tone)
        g = amount / 100 * 1.6                       # wet gain: 100 % ≈ echo louder than a big hall
        region = start is not None and end is not None
        if region:
            start, end = max(0.0, float(start)), float(end)
            if total is not None:
                end = min(end, total)
            if end - start < 0.05:
                raise ValueError("Виділення закоротке")
            r = 0.01                                  # 10 ms fades so the region edge does not click
            src_wet = (f"[x]atrim={start:.4f}:{end:.4f},asetpts=PTS-STARTPTS,"
                       f"afade=t=in:d={r},afade=t=out:st={max(0, end - start - r):.4f}:d={r},"
                       f"adelay={int(round(start * 1000))}:all=1,apad[xr];[xr]")
        else:
            src_wet = "[x]apad[xr];[xr]"
        fc = (f"[0:a]aresample={SR},aformat=channel_layouts=mono,asplit[d][x];"
              f"{src_wet}[1:a]afir=dry=1:wet=1:irnorm=-1[w];"
              f"[d][w]amix=inputs=2:weights='1 {g:.4f}':normalize=0:duration=first[out]")
        mix = os.path.join(tmp, "mix.wav")
        _run([ffmpeg, "-v", "error", "-y", "-i", src, "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", ir,
              "-filter_complex", fc, "-map", "[out]", "-c:a", "pcm_f32le", mix])
        # keep the loudness the listener had: echo adds energy, so bring the level back
        # (whole file: overall RMS; region: the region and its tail only, with 20 ms ramps)
        if region:
            w0, w1 = start, min(end + tail, total or end + tail)
            db = _rms(ffmpeg, src, start, end) - _rms(ffmpeg, mix, start, end)
            gl = 10 ** (db / 20)
            vol = (f"asetnsamples=n=64:p=0,volume=volume='1+({gl:.6f}-1)*"
                   f"max(0,min(1,min((t-{w0:.4f})/0.02,({w1:.4f}-t)/0.02)))':eval=frame")
        else:
            db = _rms(ffmpeg, src) - _rms(ffmpeg, mix)
            vol = f"volume={db:.2f}dB"
        _run([ffmpeg, "-v", "error", "-y", "-i", mix, "-af",
              vol + ",alimiter=limit=0.891:attack=3:release=60:level=disabled",
              "-map_metadata", "0", *codec_args, dst])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Add echo / room reverb (amount, tail) to a track or a region.")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--amount", type=float, default=30, help="echo amount, %% (1…100)")
    ap.add_argument("--tail", type=float, default=1.0, help="tail length, s (0.1…4)")
    ap.add_argument("--tone", type=float, default=4000, help="low-pass of the echo, Hz (lower = darker)")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        sys.exit("ffmpeg not found")
    add(ffmpeg, a.src, a.dst, a.amount, a.tail, a.start, a.end, None, a.tone)
    print(f"echo {a.amount:g} %, tail {a.tail:g} s → {a.dst}")


if __name__ == "__main__":
    main()
