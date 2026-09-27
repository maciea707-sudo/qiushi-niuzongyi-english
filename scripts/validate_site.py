"""Check the textbook index and every referenced static asset."""

import csv
import json
import pathlib
import re
import sys
import wave

sys.dont_write_bytecode = True
from repair_phonetics import PHONES, printed_positions, symbol_path


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
    (128, "s020", "David does not watch lion dance shows during the Lantern Festival.", "narrator", 2),
    (119, "s015", "She eats fruit like … as a snack when she is hungry.", "narrator", 4),
    (76, "s029", "Most qipao have beautiful pictures on them, like Chinese …, often with flowers.", "narrator", 3),
]:
    matching = [item for item in page_items[page] if item["id"].endswith(suffix)]
    check(len(matching) == 1 and matching[0]["text"] == expected
          and matching[0]["speaker"] == speaker
          and len(matching[0]["rects"]) >= minimum_regions,
          f"Page {page}: incomplete cloze card or incorrect dialogue role {suffix}")

for page, suffix, expected, minimum_regions in [
    (26, "s035", "They … every week and share their ideas about it.", 2),
    (94, "s038", "When the clock strikes 12, they jump off their chairs into the new year, in the hope of getting over any problem in the year ahead!", 3),
    (103, "s026", "It looks at all the interesting and exciting Chinese New Year traditions, such as the temple fair in Beijing and the lion dance in Hong Kong.", 3),
    (128, "s028", "It’s round.", 2),
]:
    matching = [item for item in page_items[page] if item["id"].endswith(suffix)]
    check(len(matching) == 1 and matching[0]["text"] == expected
          and len(matching[0]["rects"]) >= minimum_regions,
          f"Page {page}: incomplete wrapped sentence {suffix}")

# Workbook underlines can be invisible to text extraction. These coordinates
# are measured on the printed page and must belong to the correct card.
for page, suffix, text, x, y in [
    (48, "s029", "He … plays football on the sports field.", 57.4, 61.0),
    (59, "s020", "… eats cakes or sweets", 28.0, 51.2),
    (73, "s058", "…", 24.0, 81.0),
    (85, "s031", "We often use … (some, any) in negative sentences and questions.", 45.0, 49.7),
    (106, "s032", "… you happy at school, my dear?", 40.0, 58.2),
    (106, "s051", "… Nora interested in music, like you?", 40.0, 83.5),
    (106, "s062", "No, she … .", 48.0, 87.8),
    (113, "s021", "Watch students play different sports on the …", 45.0, 33.4),
    (113, "s022", "… See students’ pictures in the art room", 26.0, 36.0),
    (113, "s024", "Look at students’ work in the … lab", 74.0, 41.5),
    (120, "s024", "lunch and dinner: rice, … and some meat", 72.0, 54.7),
    (120, "s028", "… like an apple or orange", 69.0, 61.7),
]:
    matching = [item for item in page_items[page] if item["id"].endswith(suffix)]
    check(len(matching) == 1 and text in matching[0]["text"]
          and any(box["x"] <= x <= box["x"] + box["w"]
                  and box["y"] <= y <= box["y"] + box["h"]
                  for box in matching[0]["rects"]),
          f"Page {page}: printed underline at ({x}, {y}) outside {suffix}")

# Long sentences cannot be fully read in a fraction of a second. This catches
# the class of truncated recordings which previously passed the existence test.
for number, items in page_items.items():
    for item in items:
        # IPA labels are sounds, not English words: /b/, /p/ can be under a
        # second each without the sentence recording being truncated.
        prose = re.sub(r"/[^/\s]+/", "", item["text"])
        words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", prose)
        if len(words) < 3 or not item.get("audio") or not (ROOT / item["audio"]).is_file():
            continue
        with wave.open(str(ROOT / item["audio"])) as sound:
            duration = sound.getnframes() / sound.getframerate()
        check(len(words) / duration <= 4.8,
              f"Page {number}: recording too short for {item['text']!r} ({duration:.2f}s)")

# Each printed pronunciation symbol must be clickable in its actual location,
# speak the matching sound, and highlight only that one printed position.
positions = printed_positions()
check(sum(len(entries) for entries in positions.values()) == 221, "Phonetic spot count changed")
for number, entries in positions.items():
    for symbol, x, y, w, h in entries:
        cx, cy = (x + w / 2) / 1481 * 100, (y + h / 2) / 2096 * 100
        check(any(item["text"] == f"/{symbol}/" and item["audio"] == symbol_path(symbol)
                  and len(item["rects"]) == 1 and any(
                      box["x"] <= cx <= box["x"] + box["w"]
                      and box["y"] <= cy <= box["y"] + box["h"]
                      for box in item["rects"])
                  for item in page_items[number]),
              f"Page {number}: missing /{symbol}/ at printed position ({x}, {y})")
for number in range(149, 164):
    check(not any(item["id"].endswith(tuple(f"s{i:03}" for i in range(200, 300)))
                  and item["voice"].endswith("单独音标") for item in page_items[number]),
          f"Page {number}: wordlist sound accidentally split from its word")
for symbol in PHONES:
    check((ROOT / symbol_path(symbol)).is_file(), f"Missing phonetic sound /{symbol}/")
for unit in manifest["units"]:
    for page in json.loads((ROOT / f"data/unit-{unit['id']}.json").read_text())["pages"]:
        for item in page["sentences"]:
            if item["voice"].endswith("音标已校正"):
                check(not re.search(r"ˈ(?:dʌbəljuː|viː|biː|keɪ|ef|piː)(?=$|[\s,./])", item["ipa"]),
                      f"{item['id']}: letter name still displayed instead of sound")

if errors:
    raise SystemExit("\n".join(errors[:60]) + f"\nTotal errors: {len(errors)}")
print(f"Validated {len(manifest['units'])} units, {len(pages)} pages, {total} learning items, "
      f"{len(audio_paths)} referenced audio files.")
