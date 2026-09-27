"""Check the textbook index and every referenced static asset."""

import csv
import json
import pathlib
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "data/manifest.json").read_text())
errors = []
pages = set()
sentence_ids = set()
audio_paths = set()
total = 0


def check(condition, message):
    if not condition:
        errors.append(message)


for unit in manifest["units"]:
    data = json.loads((ROOT / f"data/unit-{unit['id']}.json").read_text())
    check(len(data["pages"]) == unit["pages"], f"Unit {unit['id']}: page count")
    count = sum(len(page["sentences"]) for page in data["pages"])
    check(count == unit["sentences"] == unit["sentenceCount"], f"Unit {unit['id']}: sentence count")
    total += count
    for page in data["pages"]:
        number = page["page"]
        check(number not in pages, f"Duplicate page {number}")
        check(unit["start"] <= number <= unit["end"], f"Page {number}: wrong unit")
        pages.add(number)
        image = ROOT / page["image"]
        check(image.is_file() and image.read_bytes()[:4] == b"RIFF", f"Page {number}: image missing or invalid")
        for sentence in page["sentences"]:
            sid = sentence["id"]
            check(sid not in sentence_ids, f"Duplicate sentence {sid}")
            sentence_ids.add(sid)
            for field in ("text", "ipa", "meaning", "speaker", "voice", "audio", "rects"):
                check(bool(sentence.get(field)), f"{sid}: missing {field}")
            for rect in sentence.get("rects", []):
                x, y, width, height = (rect[key] for key in ("x", "y", "w", "h"))
                check(0 <= x <= 100 and 0 <= y <= 100 and width > 0 and height > 0
                      and x + width <= 100.1 and y + height <= 100.1, f"{sid}: invalid hotspot")
            if sentence.get("audio"):
                audio_paths.add(sentence["audio"])
            # The question mark in the source PDF was often extracted as 'g'.
            if sentence["meaning"].rstrip("。").endswith("？"):
                check(not sentence["ipa"].endswith("g/"), f"{sid}: question mark OCR error")
            check(not sentence["ipa"].endswith(" ˈen/"), f"{sid}: part of speech read as phonemes")

check(pages == set(range(166)), "Missing or duplicate textbook pages")
with (ROOT / "data/sentence-audit.tsv").open(newline="") as file:
    audit = {row["id"]: row["text"] for row in csv.DictReader(file, delimiter="\t")}
check(set(audit) == sentence_ids, "Sentence audit IDs differ from page data")
for unit in manifest["units"]:
    data = json.loads((ROOT / f"data/unit-{unit['id']}.json").read_text())
    for page in data["pages"]:
        for sentence in page["sentences"]:
            check(audit.get(sentence["id"]) == sentence["text"], f"{sentence['id']}: audit text differs")

for path in audio_paths:
    file = ROOT / path
    try:
        with wave.open(str(file)) as sound:
            check(sound.getnframes() > 0 and sound.getframerate() > 0, f"Invalid audio {path}")
    except (FileNotFoundError, OSError, wave.Error):
        errors.append(f"Missing or unreadable audio {path}")

if errors:
    raise SystemExit("\n".join(errors[:60]) + f"\nTotal errors: {len(errors)}")
print(f"Validated {len(manifest['units'])} units, {len(pages)} pages, {total} learning items, "
      f"{len(audio_paths)} referenced audio files.")
