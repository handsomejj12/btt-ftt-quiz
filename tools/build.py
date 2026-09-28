"""Merge layout.json and the transcripts into the quiz data, then build the app.

Outputs:
  questions.js + index.html          local app (open index.html directly)
  dist/theory-test-drill.html        one self-contained page, images inlined

Transcripts come from data/verified (falling back to data/transcripts), with
hand fixes from data/fixes.json applied last. Every cross-check disagreement
is printed so it can be reviewed.
"""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LET = "ABC"


def load_transcripts():
    out = {}
    for sub in ["transcripts", "verified"]:  # verified overrides the draft
        for f in sorted((DATA / sub).glob("b*.json")):
            for x in json.loads(f.read_text(encoding="utf-8")):
                x["_src"] = sub
                out[x["id"]] = x
    fixes_file = DATA / "fixes.json"
    fixes = json.loads(fixes_file.read_text(encoding="utf-8")) if fixes_file.exists() else {}
    for qid, patch in fixes.items():
        x = out[qid]
        for field, value in patch.items():
            if field.startswith("options."):
                _, letter, key = field.split(".")
                x["options"][LET.index(letter)][key] = value
            else:
                x[field] = value
    return out


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def data_uri(path, fmt):
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    if fmt == "jpeg":
        im.save(buf, "JPEG", quality=82, optimize=True)
        mime = "image/jpeg"
    else:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    layout = {r["id"]: r for r in json.loads((DATA / "layout.json").read_text())}
    tr = load_transcripts()
    problems, notes = [], []
    missing = [qid for qid in layout if qid not in tr]
    if missing:
        problems.append(f"{len(missing)} images have no transcript: {missing[:10]}...")

    (ROOT / "img" / "opt").mkdir(parents=True, exist_ok=True)
    questions = []
    for qid, lay in layout.items():
        x = tr.get(qid)
        if not x:
            continue
        marked = x.get("marked")
        if marked != lay["correct"]:
            problems.append(f"{qid}: transcript marked {marked}, blue row is {lay['correct']}")
        if x.get("label") != lay["q"]:
            problems.append(f"{qid}: label {x.get('label')} != file number {lay['q']}")
        if bool(x.get("picture")) != lay["panel"]:
            problems.append(f"{qid}: picture={x.get('picture')!r} but panel detected={lay['panel']}")
        if not norm(x.get("question")):
            problems.append(f"{qid}: empty question")
        if x.get("notes"):
            notes.append(f"{qid}: {x['notes']}")
        opts = []
        for i, o in enumerate(x["options"]):
            if o.get("letter") != LET[i]:
                problems.append(f"{qid}: option {i} letter {o.get('letter')}")
            box = lay["opts"][i]
            item = {"x": o["text"].strip()}
            if o["type"] == "image":
                if not box:
                    problems.append(f"{qid}: option {LET[i]} is image but row is blank")
                else:
                    if box[3] - box[1] < 26:
                        problems.append(f"{qid}: option {LET[i]} is image but content is only {box[3]-box[1]}px tall")
                    p = ROOT / "img" / "opt" / f"{qid}_{LET[i]}.png"
                    Image.open(ROOT / "img" / "orig" / f"{qid}.jpg").crop(tuple(box)).save(p)
                    item["img"] = f"img/opt/{qid}_{LET[i]}.png"
            elif o["type"] != "text":
                problems.append(f"{qid}: option {LET[i]} has type {o['type']!r}")
            if not item["x"]:
                problems.append(f"{qid}: option {LET[i]} is empty")
            opts.append(item)
        q = {
            "id": qid,
            "t": lay["test"],
            "p": lay["paper"],
            "n": lay["q"],
            "q": x["question"].strip(),
            "o": opts,
            "a": LET.index(lay["correct"]),  # the blue row is the source of truth
            "k": norm(x["question"]) + "|" + "|".join(sorted(norm(o["x"]) for o in opts)),
            "orig": f"img/orig/{qid}.jpg",
        }
        if lay["panel"]:
            q["pic"] = f"img/pic/{qid}.jpg"
            q["picAlt"] = x.get("picture") or ""
        questions.append(q)

    questions.sort(key=lambda q: (q["t"], q["p"], q["n"]))

    src = (ROOT / "src" / "app.html").read_text(encoding="utf-8")
    split = src.index('<div class="wrap"')
    head, body = src[:split], src[split:]

    # Local build: files on disk.
    (ROOT / "questions.js").write_text(
        "window.QDATA = " + json.dumps({"questions": questions}, ensure_ascii=False) + ";\n", encoding="utf-8"
    )
    local = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + head
        + "</head>\n<body>\n"
        + body.replace("<!--DATA-->", '<script src="questions.js"></script>')
        + "</body>\n</html>\n"
    )
    (ROOT / "index.html").write_text(local, encoding="utf-8")

    # Published build: one page, images inlined, no links to the original screenshots.
    inlined = []
    for q in questions:
        c = {k: v for k, v in q.items() if k != "orig"}
        if "pic" in c:
            c["pic"] = data_uri(ROOT / c["pic"], "jpeg")
        c["o"] = [dict(o, img=data_uri(ROOT / o["img"], "png")) if "img" in o else o for o in c["o"]]
        inlined.append(c)
    page = src.replace(
        "<!--DATA-->",
        "<script>window.QDATA = " + json.dumps({"questions": inlined}, ensure_ascii=False).replace("</", "<\\/") + ";</script>",
    )
    (ROOT / "dist").mkdir(exist_ok=True)
    out = ROOT / "dist" / "theory-test-drill.html"
    out.write_text(page, encoding="utf-8")

    print(f"questions: {len(questions)}  (BTT {sum(q['t']=='BTT' for q in questions)}, FTT {sum(q['t']=='FTT' for q in questions)})")
    print(f"with picture: {sum('pic' in q for q in questions)}, image options: {sum('img' in o for q in questions for o in q['o'])}")
    for t in ["BTT", "FTT"]:
        print(f"unique {t}: {len({q['k'] for q in questions if q['t']==t})}")
    print(f"published page size: {out.stat().st_size/1e6:.2f} MB")
    print(f"sources: verified {sum(x['_src']=='verified' for x in tr.values())}, draft only {sum(x['_src']=='transcripts' for x in tr.values())}")
    (DATA / "notes.txt").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"transcriber notes (source typos etc.): {len(notes)}, see data/notes.txt")
    print(f"\n{len(problems)} things to review:")
    for p in problems:
        print(" -", p)


if __name__ == "__main__":
    main()
