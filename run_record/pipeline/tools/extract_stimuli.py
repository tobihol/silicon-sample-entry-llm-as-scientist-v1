#!/usr/bin/env python
"""Rebuild inputs/stimuli.json from the read-only questionnaire.

The 16 intervention texts and 3 control fillers live only inside
survey/questionnaire.txt. ssb.spec.stimuli() refuses to load a stale copy: it
compares the stored source_sha256 against the live file, so run this whenever the
benchmark template changes.

    python tools/extract_stimuli.py
"""
import csv, hashlib, json, re, sys
from pathlib import Path

BENCH = Path("/workspace/benchmark")
OUT = Path("/workspace/run/inputs/stimuli.json")

qpath = BENCH / "survey" / "questionnaire.txt"
lines = qpath.read_text().split("\n")

# section bounds: the CONDITION section, which is where the stimuli live
hdr = [i for i, l in enumerate(lines) if re.match(r"^=====+$", l)]
secs = [(i + 1, lines[i + 1].strip()) for i in hdr
        if i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r"^=+$", lines[i + 1])]
start = next(i for i, name in secs if name.startswith("CONDITION"))
end = next(i for i, name in secs if name.startswith("POST-TREATMENT"))

tag_of, codes_of = {}, {}
with (BENCH / "survey" / "condition_codenames.csv").open() as fh:
    for r in csv.DictReader(fh):
        tag_of[r["title"]] = r["tag"]
        codes_of.setdefault(r["title"], []).append(r["code_name"])


def clean(body: str) -> str:
    body = re.split(r"\n-{40,}\nTRANSITION", body)[0]
    body = re.sub(r"\n-{40,}\s*$", "", body)
    return re.sub(r"\n={40,}\s*$", "", body).strip()


stim = []
for part in re.split(r"^### ", "\n".join(lines[start:end]), flags=re.M)[1:]:
    head, _, body = part.partition("\n")
    head, body = head.strip(), clean(body)
    title = "control" if head.startswith("control") else head
    stim.append({"title": title, "variant_note": head if title == "control" else "",
                 "tag": tag_of.get(title, ""), "code_names": codes_of.get(title, []),
                 "n_words": len(body.split()), "text": body})

titles = {s["title"] for s in stim} - {"control"}
expected = set(tag_of) - {"control"}
if titles != expected:
    sys.exit(f"stimulus titles do not match condition_codenames.csv: {titles ^ expected}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    "source": str(qpath),
    "source_sha256": hashlib.sha256(qpath.read_bytes()).hexdigest(),
    "n_intervention_texts": len(titles),
    "n_control_fillers": sum(1 for s in stim if s["title"] == "control"),
    "extraction_note": ("The '### <title>' blocks of the CONDITION section, with the "
                        "questionnaire's own TRANSITION/rule scaffolding stripped."),
    "stimuli": stim}, indent=1, ensure_ascii=False))
print(f"wrote {OUT}: {len(titles)} interventions, "
      f"{sum(1 for s in stim if s['title'] == 'control')} control fillers")
