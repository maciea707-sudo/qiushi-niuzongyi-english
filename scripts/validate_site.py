"""Check the textbook index and every referenced static asset."""

import csv
import json
import pathlib
import re
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "data/manifest.json").read_text())
errors = []
pages = set()
sentence_ids = set()
audio_paths = set()
total = 0
page_items = {}


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
        page_items[number] = page["sentences"]
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
            if unit["id"] == 23 and number in range(149, 162):
                # Dictionary variants should be clean headwords, while the two
                # Wordlist headings legitimately contain a parenthesized label.
                check(not (sentence["text"].rstrip().endswith(")")
                           and not sentence["text"].startswith("Wordlist (")),
                      f"{sid}: wordlist variant still contains OCR annotation")
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

# Audited coordinates refer to words visible in the textbook image. A valid WAV
# on disk does not help if the printed word has no target at its actual location.
for entry in json.loads((ROOT / "data/hotspot-coverage.json").read_text()):
    word = entry["word"].casefold()
    x, y = entry["x"], entry["y"]
    check(any(
        word in item["text"].casefold() and any(
            box["x"] <= x <= box["x"] + box["w"]
            and box["y"] <= y <= box["y"] + box["h"]
            for box in item["rects"]
        ) for item in page_items[entry["page"]]
    ), f"Page {entry['page']}: no clickable target for printed {entry['word']} at ({x}, {y})")

for number, discarded in {150: {"vent"}, 163: {"vi", "en", "k", "ns", "t/"}}.items():
    for item in page_items[number]:
        check(item["text"].casefold() not in discarded,
              f"Page {number}: OCR fragment is still a learning item: {item['text']}")

# Cloze exercises can print one sentence across several rows and blanks. All
# printed fragments must select the same card, including the speaker identity.
for page, suffix, expected, speaker, minimum_regions in [
    (12, "s037", "Mr Wu … my favourite teacher!", "simon", 1),
    (22, "s022", "He often visits science … .", "millie", 1),
    (35, "s030", "… all have lunch there.", "simon", 2),
    (62, "s048", "Let’s get some …, some … and some … .", "simon", 3),
    (98, "s051", "My dad … (shop) in the supermarket, and my mum … (clean) the flat.", "sandy", 3),
    (106, "s043", "David and I … both good basketball players.", "simon", 3),
    (115, "s041", "But the field trip … (seldom/sometimes) takes place … early May.", "david", 3),
    (116, "s014", "I’m excited about our school trip this term!", "a", 1),
    (119, "s009", "Do you like sweet foods?", "a", 1),
    (124, "s056", "I don’t need … pencils or rulers, but I want to buy some books.", "sarah", 3),
    (127, "s052", "My mum … (clean) the house for our party tonight.", "emily", 3),
]:
    matching = [item for item in page_items[page] if item["id"].endswith(suffix)]
    check(len(matching) == 1 and matching[0]["text"] == expected
          and matching[0]["speaker"] == speaker
          and len(matching[0]["rects"]) >= minimum_regions,
          f"Page {page}: incomplete cloze card or incorrect dialogue role {suffix}")

# Long sentences cannot be fully read in a fraction of a second. This catches
# the class of truncated recordings which previously passed the existence test.
for number, items in page_items.items():
    for item in items:
        words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", item["text"])
        if len(words) < 3 or not item.get("audio") or not (ROOT / item["audio"]).is_file():
            continue
        with wave.open(str(ROOT / item["audio"])) as sound:
            duration = sound.getnframes() / sound.getframerate()
        check(len(words) / duration <= 4.8,
              f"Page {number}: recording too short for {item['text']!r} ({duration:.2f}s)")

if errors:
    raise SystemExit("\n".join(errors[:60]) + f"\nTotal errors: {len(errors)}")
print(f"Validated {len(manifest['units'])} units, {len(pages)} pages, {total} learning items, "
      f"{len(audio_paths)} referenced audio files.")
