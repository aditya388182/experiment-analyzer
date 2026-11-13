"""Assemble PNG frames (NNNN_<holdMs>.png) into a GIF. Needs Pillow (not a project dependency):
    python scripts/make_gif.py <framesDir> docs/sample-run.gif
A frame's file name says how long to hold it; 0 means a 120 ms in-between frame.
"""

import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    frames_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    files = sorted(frames_dir.glob("*.png"))
    frames, durations = [], []
    for f in files:
        hold = int(f.stem.split("_")[1])
        img = Image.open(f).convert("RGB")
        img = img.resize((img.width * 3 // 4, img.height * 3 // 4), Image.LANCZOS)
        frames.append(img.quantize(colors=128, method=Image.Quantize.MEDIANCUT))
        durations.append(hold or 120)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"{out}: {len(frames)} frames, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
