"""Find what moves where it should not: wobble, jumps and one-frame glitches.

    uv run python check_motion.py recording frames/draw-board-raw [--from S --to S] [--calm S]
    uv run python check_motion.py rendered out/frames-<name> [--fps 30]

A recording should keep still unless something was done on purpose (an
unfold, a scroll, a fit): every shift of its content between two frames is
listed with its time, and shifts that turn back within two seconds count as
wobble. A part of the frame that moves while the rest keeps still (a button
pushed down by a line above it) is found in a grid of tiles ("local"). A rendered video is checked for jumps (a frame far from both of its
neighbours' changes) and flicker (a frame unlike the frames before and after,
which are alike). Both use small grayscale copies of the frames, so a check
of 3,000 frames takes about a minute.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


WIDTH = 480  # analysis width
TILES = (4, 4)  # rows, columns of the grid for local moves


def gray(path: Path, width: int = WIDTH) -> np.ndarray:
    image = Image.open(path).convert("L")
    height = round(image.height * width / image.width)
    return np.asarray(image.resize((width, height), Image.BILINEAR), dtype=np.float32)


def shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """How far b moved against a (dx, dy in analysis pixels) and how sure (peak)."""
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa, fb = np.fft.fft2(a * window), np.fft.fft2(b * window)
    cross = fa * np.conj(fb)
    cross /= np.abs(cross) + 1e-9
    corr = np.abs(np.fft.ifft2(cross))
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    h, w = a.shape
    dy = y if y <= h // 2 else y - h
    dx = x if x <= w // 2 else x - w
    return -float(dx), -float(dy), float(corr.max())


def local_moves(a: np.ndarray, b: np.ndarray) -> list[tuple[int, int, float, float]]:
    """Tiles whose content moved between a and b: (row, column, dx, dy)."""
    rows, cols = TILES
    th, tw = a.shape[0] // rows, a.shape[1] // cols
    moved = []
    for r in range(rows):
        for c in range(cols):
            ta = a[r * th:(r + 1) * th, c * tw:(c + 1) * tw]
            tb = b[r * th:(r + 1) * th, c * tw:(c + 1) * tw]
            if float(np.mean(np.abs(ta - tb))) < 1.0 or ta.std() < 4:
                continue
            dx, dy, peak = shift(ta, tb)
            if peak > 0.2 and max(abs(dx), abs(dy)) >= 2 and abs(dx) < tw / 3 and abs(dy) < th / 3:
                moved.append((r, c, dx, dy))
    return moved


def check_recording(folder: Path, start: float | None, end: float | None, calm: float | None = None) -> int:
    index = json.loads((folder / "index.json").read_text())
    frames = index["frames"]
    t0 = frames[0]["t"]
    scale = Image.open(folder / frames[0]["file"]).width / WIDTH
    events, prev = [], None
    for frame in frames:
        t = frame["t"] - t0
        if (start is not None and t < start) or (end is not None and t > end):
            continue
        img = gray(folder / frame["file"])
        if prev is not None and prev.shape == img.shape:
            change = float(np.mean(np.abs(img - prev)))
            if change > 0.4:
                dx, dy, peak = shift(prev, img)
                if peak > 0.08 and (abs(dx) >= 1 or abs(dy) >= 1):
                    events.append((t, "moved", dx * scale, dy * scale, change))
                elif peak <= 0.08 and change > 6:
                    events.append((t, "reflowed", 0.0, 0.0, change))
                else:
                    for r, c, ldx, ldy in local_moves(prev, img):
                        events.append((t, f"local {r},{c}", ldx * scale, ldy * scale, change))
        prev = img
    steps = [b["t"] - a["t"] for a, b in zip(frames, frames[1:]) if b["t"] < a["t"]]
    if steps:
        # Frame times from the wall clock (recordings before the monotonic clock): the stage would play them out of order
        print(f"{folder.name}: frame times step back {len(steps)} times (by {-min(steps):.2f} s at most): record again")
    wobble = 0
    moves = [e for e in events if e[1] == "moved"]
    for a, b in zip(moves, moves[1:]):
        turned = (a[2] * b[2] < 0 and min(abs(a[2]), abs(b[2])) > 2) or (a[3] * b[3] < 0 and min(abs(a[3]), abs(b[3])) > 2)
        if turned and b[0] - a[0] < 2.0:
            wobble += 1
    local = [e for e in events if e[1].startswith("local")]
    print(f"{folder.name}: {len(frames)} frames, {len(moves)} moves, {len(local)} local moves, "
          f"{sum(e[1] == 'reflowed' for e in events)} reflows, {wobble} turn-backs (wobble)")
    for t, kind, dx, dy, change in events:
        detail = f"change {change:.1f}" if kind == "reflowed" else f"dx {dx:+.0f} px, dy {dy:+.0f} px"
        print(f"  {t:7.2f} s  {kind:8s} {detail}")
    if calm:
        # The window of `calm` seconds with the least motion (a reflow weighs 100 px), inside --from/--to
        first = start if start is not None else 0.0
        last = min(end, frames[-1]["t"] - t0) if end is not None else frames[-1]["t"] - t0
        cost = lambda a: sum(abs(e[2]) + abs(e[3]) + (100 if e[1] == "reflowed" else 0) for e in events if a <= e[0] < a + calm)
        starts = [first + s / 10 for s in range(int((last - first - calm) * 10) + 1)]
        best = min(starts, key=lambda a: (cost(a), a)) if starts else first
        act = {m["name"]: m["t"] - t0 for m in index["marks"]}.get("act")
        offset = f", act {best - act:+.2f} s" if act is not None else ""
        print(f"  calmest {calm:g} s from {best:.1f} s{offset} (motion {cost(best):.0f} px)")
    return wobble


def check_rendered(folder: Path, fps: int) -> int:
    files = sorted(folder.glob("*.jpg")) or sorted(folder.glob("*.png"))
    imgs = [gray(f, 320) for f in files]
    diff = np.array([float(np.mean(np.abs(b - a))) for a, b in zip(imgs, imgs[1:])])
    median = float(np.median(diff)) + 0.05
    problems = 0
    for n in range(1, len(imgs) - 1):
        before, after = diff[n - 1], diff[n]
        skip = float(np.mean(np.abs(imgs[n + 1] - imgs[n - 1])))
        # Flicker: frame n stands out while n-1 and n+1 agree
        if before > 6 * median and after > 6 * median and skip < 0.35 * min(before, after):
            print(f"  flicker at {n / fps:7.2f} s (frame {n}): {before:.1f} / {after:.1f}, across {skip:.1f}")
            problems += 1
        # Jump: one change far above its neighbours
        elif before > 12 * median and before > 4 * max(diff[n - 2] if n > 1 else 0, after):
            print(f"  jump    at {n / fps:7.2f} s (frame {n}): {before:.1f} (median {median:.2f})")
            problems += 1
    print(f"{folder.name}: {len(files)} frames, median change {median:.2f}, {problems} jumps or flickers")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mode", choices=["recording", "rendered"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--from", dest="start", type=float)
    parser.add_argument("--to", dest="end", type=float)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--calm", type=float, help="also find the calmest window of this many seconds")
    args = parser.parse_args()
    if args.mode == "recording":
        check_recording(args.folder, args.start, args.end, args.calm)
    else:
        check_rendered(args.folder, args.fps)


if __name__ == "__main__":
    main()
