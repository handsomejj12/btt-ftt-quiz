"""Read every screenshot in img/orig and work out its layout without OCR.

For each image it finds the answer rows, which row is shaded blue (the
correct answer), whether there is a picture panel. It saves the picture
crop and records each answer's content box. Writes data/layout.json.
"""
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ORIG = ROOT / "img" / "orig"
PIC = ROOT / "img" / "pic"

LETTERS = "ABCDE"


def is_dark(p):
    return sum(p) < 330


def is_blue(p):
    r, g, b = p
    return b > 220 and 120 < r < 185 and 170 < g < 225


def is_white(p):
    return min(p) > 235


def content_runs(im, x):
    """Runs of non-dark pixels bounded by dark border pixels, down column x."""
    h = im.size[1]
    runs, start = [], None
    for y in range(h):
        d = is_dark(im.getpixel((x, y)))
        if not d and start is None and y > 0 and is_dark(im.getpixel((x, y - 1))):
            start = y
        elif d and start is not None:
            runs.append((start, y))
            start = None
    return runs


def find_rows(im):
    # Rows show as 40-100px tall bordered cells both at the far left and in the
    # answer column. The top question box is far taller, so it is excluded.
    left = {r for r in content_runs(im, 30) if 40 <= r[1] - r[0] <= 100}
    right = [r for r in content_runs(im, 780) if 40 <= r[1] - r[0] <= 100]
    rows = []
    for r in right:
        if any(abs(r[0] - l[0]) <= 3 and abs(r[1] - l[1]) <= 3 for l in left):
            rows.append(r)
    return rows


def blue_fraction(im, y0, y1):
    n = hit = 0
    for y in range(y0 + 3, y1 - 3, 2):
        for x in range(775, 885, 3):
            n += 1
            hit += is_blue(im.getpixel((x, y)))
    return hit / max(n, 1)


def has_panel(im):
    # A picture panel means the top box stops at ~x597; otherwise the white
    # question box runs to the right edge.
    nonwhite = 0
    tot = 0
    for y in range(30, 200, 4):
        for x in range(620, 870, 5):
            tot += 1
            nonwhite += not is_white(im.getpixel((x, y)))
    return nonwhite / tot > 0.3


# The picture panel sits in a fixed spot: signs in the short layout, a video
# frame (with a "Repeat Video" button under it) in the taller layout.
PIC_BOX = {478: (601, 32, 885, 243), 479: (601, 32, 885, 243), 504: (604, 14, 885, 224), 505: (601, 14, 885, 224)}


def option_crop(im, y0, y1):
    """Bounding box of non-white content right of the '( A )' label."""
    x_lo, x_hi = 56, 766
    ys, xs = [], []
    for y in range(y0 + 2, y1 - 2):
        for x in range(x_lo, x_hi, 2):
            p = im.getpixel((x, y))
            if not is_white(p):
                ys.append(y)
                xs.append(x)
    if not xs:
        return None
    return (max(min(xs) - 2, x_lo), max(min(ys) - 2, y0 + 1), min(max(xs) + 3, x_hi), min(max(ys) + 3, y1 - 1))


def main():
    PIC.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(ORIG.glob("*.jpg")):
        m = re.match(r"(BTT|FTT)_E_P(\d+)_Q(\d+)\.jpg", f.name)
        test, paper, q = m.group(1), int(m.group(2)), int(m.group(3))
        qid = f.stem
        im = Image.open(f).convert("RGB")
        rows = find_rows(im)
        blues = [round(blue_fraction(im, *r), 3) for r in rows]
        correct = [i for i, b in enumerate(blues) if b > 0.5]
        rec = {
            "id": qid,
            "test": test,
            "paper": paper,
            "q": q,
            "size": im.size,
            "rows": rows,
            "blue": blues,
            "correct": LETTERS[correct[0]] if len(correct) == 1 else None,
            "panel": has_panel(im),
            "pic": None,
            "opts": [],
        }
        if rec["panel"]:
            box = PIC_BOX[im.size[1]]
            im.crop(box).save(PIC / f"{qid}.jpg", quality=90)
            rec["pic"] = list(box)
        for i, (y0, y1) in enumerate(rows):
            box = option_crop(im, y0, y1)
            rec["opts"].append(list(box) if box else None)
        out.append(rec)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "layout.json").write_text(json.dumps(out, indent=1))
    bad = [r["id"] for r in out if r["correct"] is None or len(r["rows"]) != 3]
    print("images:", len(out))
    print("row counts:", sorted({len(r["rows"]) for r in out}))
    print("no/multiple correct or not 3 rows:", bad)
    print("with picture panel:", sum(r["panel"] for r in out))


if __name__ == "__main__":
    main()
