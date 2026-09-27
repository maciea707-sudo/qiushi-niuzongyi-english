"""Regenerate phonetic readings and add targets for printed, standalone sounds.

Run from the repository root: python scripts/repair_phonetics.py
This uses the installed Flite SLT voice and does not call an online service.
The phoneme inventory and positions are checked against textbook pages 13, 25,
37, 49, 63, 75, 87, 99, 130 and 131. Wordlist pages are deliberately excluded.
"""

import collections
import csv
import ctypes
from array import array
import json
import math
from pathlib import Path
import re
import tempfile
import wave


ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1481, 2096

# British textbook symbols -> closest phonetic units supported by Flite SLT.
# The backend is an American voice, so the historical British vowel qualities
# /ɒ/, /ɜː/, /ɪə/, /eə/ and /ʊə/ remain approximations.
PHONES = {
    "ɪ": "ih1", "iː": "iy1", "e": "eh1", "æ": "ae1", "ʌ": "ah1",
    "ɑː": "aa1", "ɒ": "ao1", "ɔː": "ao1", "ʊ": "uh1", "uː": "uw1",
    "ə": "ax ax ax", "ɜː": "er1", "eɪ": "ey1", "aɪ": "ay1", "ɔɪ": "oy1",
    "əʊ": "ow1", "aʊ": "aw1", "ɪə": "ih1 ax", "eə": "eh1 ax",
    "ʊə": "uh1 ax", "juː": "y uw1",
    "p": "p", "b": "b", "t": "t", "d": "d", "k": "k", "g": "g",
    "tʃ": "ch", "dʒ": "jh", "tr": "t r", "dr": "d r",
    "ts": "t s", "dz": "d z", "f": "f", "v": "v",
    "θ": "th", "ð": "dh", "s": "s", "z": "z", "ʃ": "sh",
    "ʒ": "zh", "h": "hh", "m": "m", "n": "n", "ŋ": "ng",
    "l": "l", "r": "r", "j": "y", "w": "w",
}
VOWELS = ["ɪ", "iː", "e", "æ", "ʌ", "ɑː", "ɒ", "ɔː", "ʊ", "uː",
          "ə", "ɜː", "eɪ", "aɪ", "ɔɪ", "əʊ", "aʊ", "ɪə", "eə", "ʊə"]
CONSONANTS = ["p", "b", "t", "d", "k", "g", "tʃ", "dʒ", "tr", "dr",
              "ts", "dz", "f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ",
              "h", "m", "n", "ŋ", "l", "r", "j", "w"]
assert len(VOWELS) == 20 and len(CONSONANTS) == 28


def printed_positions():
    """(symbol, x, y, width, height) in the original 1481 x 2096 image."""
    spots = collections.defaultdict(list)

    def add(page, symbol, x, y, w=55, h=35):
        assert symbol in PHONES, (page, symbol)
        spots[page].append((symbol, x, y, w, h))

    # Pronunciation lesson tables and repeated symbols on the exercises.
    for i, symbol in enumerate(["eɪ", "iː", "aɪ", "əʊ", "juː"]):
        add(13, symbol, 1245, 418 + 65 * i, 93, 45)
        add(13, symbol, [240, 485, 727, 967, 1210][i], 1155, 72, 50)
    for i, symbol in enumerate(["æ", "e", "ɪ", "ɒ", "ʌ"]):
        add(25, symbol, 1102, 447 + 59 * i, 103, 48)
        add(25, symbol, [277, 490, 720, 930, 1152][i],
            [1025, 1052, 1060, 1040, 1019][i], 70, 51)
    for i, (left, right) in enumerate(zip(["p", "b", "t", "d", "k", "g", "h"],
                                          ["m", "n", "ŋ", "l", "r", "j", "w"])):
        add(37, left, 628, 410 + 63 * i, 85, 51)
        add(37, right, 1259, 410 + 63 * i, 85, 51)
    for i, symbol in enumerate(["ɑː", "ɔː", "iː", "e", "uː", "ʊ", "ɜː", "ə"]):
        add(49, symbol, 1060, 410 + 57 * i, 162, 51)
    # Eight scattered leaves (the cropped image starts at original y=1006).
    for symbol, x, y in [("uː", 940, 1075), ("ʊ", 1083, 1112),
                         ("iː", 797, 1143), ("ɔː", 1193, 1163),
                         ("e", 937, 1204), ("ɜː", 1092, 1234),
                         ("ə", 1237, 1262), ("ɑː", 795, 1284)]:
        add(49, symbol, x, y, 81, 57)
    for i, symbol in enumerate(["f", "v", "ʃ", "ʒ", "θ", "ð", "s", "z"]):
        add(63, symbol, 223 + 145 * i, 581, 65, 51)
    for i, symbol in enumerate(["tr", "dr", "tʃ", "dʒ", "ts", "dz"]):
        add(63, symbol, 217 + 150 * i, 811, 77, 52)
    for i, symbol in enumerate(["eɪ", "aɪ", "ɔɪ", "əʊ", "aʊ", "ɪə", "eə", "ʊə"]):
        add(75, symbol, 994, 409 + 51 * i, 134, 48)
    for symbol, x in zip(["eə", "ɔɪ", "ɪə", "əʊ", "aɪ", "aʊ"],
                         [365, 506, 653, 791, 909, 1049]):
        add(75, symbol, x, 1165, 82, 48)

    # Seven tightly spaced consonant-cluster rows, including repeated /s/.
    for y, cells in [
        (461, [("b", 190), ("k", 240), ("f", 284), ("g", 327),
               ("p", 375), ("s", 418), ("l", 500)]),
        (516, [("b", 190), ("k", 240), ("f", 284), ("g", 327),
               ("p", 375), ("r", 505)]),
        (571, [("s", 190), ("k", 489), ("m", 539), ("n", 594),
               ("p", 647), ("t", 703)]),
        (626, [("s", 190), ("k", 489), ("p", 540), ("t", 599),
               ("r", 665)]),
        (681, [("k", 190), ("s", 240), ("t", 288), ("w", 508)]),
        (866, [("b", 190), ("p", 240), ("k", 284), ("d", 327),
               ("t", 375), ("s", 417), ("l", 501)]),
        (922, [("z", 190), ("s", 240), ("f", 284), ("v", 327),
               ("d", 375), ("n", 506)]),
    ]:
        for symbol, x in cells:
            add(87, symbol, x, y, 45 if len(symbol) == 1 else 50, 41)
    # On this page the sound symbols are also embedded in two explanatory sentences.
    for symbol, x, y, width in [("w", 177, 275, 69), ("v", 355, 275, 69),
                                ("w", 482, 358, 44), ("v", 482, 560, 44),
                                ("w", 449, 829, 49), ("v", 559, 829, 49)]:
        add(99, symbol, x, y, width, 48)

    for row, group in enumerate((VOWELS[:10], VOWELS[10:])):
        for col, symbol in enumerate(group):
            add(130, symbol, 394 + 94 * col, 285 + 65 * row, 72, 52)
    for row in range(4):
        for col, symbol in enumerate(CONSONANTS[row * 7:(row + 1) * 7]):
            add(130, symbol, 390 + 149 * col, 415 + 66 * row, 76, 52)
    for row, symbol in enumerate(VOWELS):
        # /ɔː/ wraps across a second printed line, without repeating its
        # symbol. Subsequent symbols therefore start one full line lower.
        add(130, symbol, 139, 783 + 55.4 * (row + (row >= 8)), 75, 44)
    for row, symbol in enumerate(CONSONANTS):
        add(131, symbol, 116, 230 + 55.4 * row, 84, 43)
    assert sum(len(rows) for rows in spots.values()) == 221
    return spots


def flite_voice():
    lib = ctypes.CDLL("libflite.so.1")
    slt = ctypes.CDLL("libflite_cmu_us_slt.so.1")
    lib.flite_init()
    slt.register_cmu_us_slt.argtypes = [ctypes.c_char_p]
    slt.register_cmu_us_slt.restype = ctypes.c_void_p
    voice = slt.register_cmu_us_slt(None)
    if not voice:
        raise RuntimeError("Flite SLT voice is unavailable")
    for name in ("flite_text_to_speech", "flite_phones_to_speech"):
        method = getattr(lib, name)
        method.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_char_p]
        method.restype = ctypes.c_float
    return lib, voice


def generate(lib, voice, text, target, is_phone=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    synth = lib.flite_phones_to_speech if is_phone else lib.flite_text_to_speech
    synth(text.encode(), voice, str(target).encode())
    with wave.open(str(target)) as sound:
        assert sound.getnframes() > 0, target


def symbol_path(symbol):
    return "assets/audio/phonemes/ipa-" + "-".join(f"{ord(c):04x}" for c in symbol) + ".wav"


def clarify_isolated_sound(path, symbol):
    """Let users hear short, unvoiced consonant releases on ordinary devices."""
    with wave.open(str(path)) as source:
        channels, width, rate, _, _, _ = source.getparams()
        assert (channels, width) == (1, 2)
        samples = array("h", source.readframes(source.getnframes()))
    if symbol == "ɒ":
        # A shorter, rounded vowel distinguished from the long /ɔː/ in this
        # American backend; a British-quality /ɒ/ is not in its inventory.
        samples = samples[:int(.19 * rate)]
        edge = min(len(samples), int(.03 * rate))
        for index in range(edge):
            pos = len(samples) - edge + index
            samples[pos] = round(samples[pos] * (edge - index) / edge)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    if rms < 1800:
        gain = min(25, 1800 / max(rms, 1))
        if max(abs(sample) for sample in samples) * gain > 26000:
            gain = 26000 / max(abs(sample) for sample in samples)
        samples = array("h", (round(sample * gain) for sample in samples))
    with wave.open(str(path), "wb") as target:
        target.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        target.writeframes(b"\x00\x00" * int(rate * .06) + samples.tobytes()
                           + b"\x00\x00" * int(rate * .12))


def join_recording(parts, target):
    """Concatenate same-voice recordings with short pauses and a tiny edge fade."""
    fragments = []
    sample_rate = None
    for file in parts:
        with wave.open(str(file)) as sound:
            if sample_rate is None:
                sample_rate = sound.getframerate()
            assert (sound.getframerate(), sound.getsampwidth(), sound.getnchannels()) == (sample_rate, 2, 1)
            raw = sound.readframes(sound.getnframes())
        # Keep the quiet lead/tail on consonants; they are part of the release.
        fragments.append(raw)
    pause = b"\x00\x00" * round(sample_rate * .055)
    with wave.open(str(target), "wb") as output:
        output.setparams((1, 2, sample_rate, 0, "NONE", "not compressed"))
        output.writeframes(pause.join(fragments))


def main():
    spots = printed_positions()
    manifest_path = ROOT / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    units = {unit["id"]: json.loads((ROOT / f"data/unit-{unit['id']}.json").read_text())
             for unit in manifest["units"]}
    pages = {page["page"]: (unit, page) for unit in units.values() for page in unit["pages"]}
    # Idempotent: replace only the cards created by this script.
    for unit in units.values():
        for page in unit["pages"]:
            if page["page"] in spots:
                page["sentences"] = [card for card in page["sentences"]
                                     if not (re.search(r"-s2\d\d$", card["id"])
                                             and card["voice"].endswith("单独音标"))]

    lib, voice = flite_voice()
    phonemes = set(VOWELS + CONSONANTS + ["juː"])
    for rows in spots.values():
        phonemes.update(symbol for symbol, *_ in rows)
    for symbol in sorted(phonemes):
        path = ROOT / symbol_path(symbol)
        generate(lib, voice, PHONES[symbol], path, True)
        clarify_isolated_sound(path, symbol)

    # Every card with a *printed sound symbol*, including sounds within prose.
    # Enumerating IDs avoids treating grammatical alternatives like he/she/it
    # or website URLs as sound symbols. The wordlist contains no IDs here.
    cards = {
        "u00-p005-s060", "u01-p017-s029", "u02-p029-s004",
        "u03-p041-s018", "u04-p053-s017", "u05-p067-s019",
        "u06-p079-s020", "u08-p103-s004",
        *(f"u07-p087-s{i:03}" for i in [18, 20, 22, 23, 25, 29, 31]),
        *(f"u08-p099-s{i:03}" for i in [1, 2, 4, 28]),
    }
    pattern = re.compile(r"/([^/\s]+?)/")
    found = set()
    with tempfile.TemporaryDirectory() as temp:
        cache = Path(temp)
        for unit in units.values():
            for page in unit["pages"]:
                for card in page["sentences"]:
                    if card["id"] not in cards:
                        continue
                    found.add(card["id"])
                    chunks = pattern.split(card["text"])
                    assert len(chunks) > 1
                    parts = []
                    for index, chunk in enumerate(chunks):
                        if index % 2:
                            assert chunk in PHONES, (card["id"], chunk)
                            parts.append(ROOT / symbol_path(chunk))
                        elif re.search(r"[A-Za-z+]", chunk):
                            path = cache / f"{card['id']}-{index}.wav"
                            generate(lib, voice, chunk.replace("+", " plus "), path)
                            parts.append(path)
                    assert parts, card["id"]
                    join_recording(parts, ROOT / card["audio"])
                    # Fix the displayed transcription where letter names had
                    # been inserted instead of the printed sound values.
                    if card["id"] in {
                        "u00-p005-s060", "u08-p103-s004",
                        *(f"u07-p087-s{i:03}" for i in [18, 20, 22, 23, 25, 29, 31]),
                        *(f"u08-p099-s{i:03}" for i in [1, 2, 4, 28]),
                    }:
                        phonetic = card["ipa"]
                        for before, after in [("ˈdʌbəljuː", "w"), ("ˈviː", "v"),
                                               ("ˈbiː", "b"), ("ˈkeɪ", "k"),
                                               ("ˈef", "f"), ("ˈdʒiː", "g"),
                                               ("ˈpiː", "p"), ("ˈes", "s"),
                                               ("ˈel", "l"), ("ˈem", "m"),
                                               ("ˈen", "n"), ("ˈtiː", "t"),
                                               ("ˈdiː", "d"), ("ˈziː", "z")]:
                            # Replace complete letter names only: e.g. /ˈtiːθ/
                            # is the ordinary word 'teeth', not the letter T.
                            phonetic = re.sub(re.escape(before) + r"(?=$|[\s,./“])", after, phonetic)
                        if card["id"] == "u07-p087-s023":
                            phonetic = phonetic.replace("ˈɑː", "r")
                        card["ipa"] = phonetic.replace("“", "")
                        # A prior run with an unbounded replacement could have
                        # altered this ordinary word in the stored transcription.
                        if card["id"] == "u08-p099-s002":
                            card["ipa"] = card["ipa"].replace("ˈtɒp tθ", "ˈtɒp ˈtiːθ")
                    card["voice"] = "美式女声 · SLT · 音标已校正"
    assert found == cards, sorted(cards - found)

    new_cards = 0
    for number, rows in spots.items():
        _, page = pages[number]
        for index, (symbol, x, y, w, h) in enumerate(rows, 200):
            rect = {key: round(value, 4) for key, value in (
                ("x", x / WIDTH * 100), ("y", y / HEIGHT * 100),
                ("w", w / WIDTH * 100), ("h", h / HEIGHT * 100))}
            page["sentences"].append({
                "id": f"u{next(info['id'] for info in manifest['units'] if info['start'] <= number <= info['end']):02}-p{number:03}-s{index:03}",
                "speaker": "narrator", "text": f"/{symbol}/", "rects": [rect],
                "ipa": f"/{symbol}/", "meaning": f"音标 /{symbol}/：点击听这个音",
                "voice": "美式女声 · SLT · 单独音标",
                "audio": symbol_path(symbol),
            })
            new_cards += 1
    for info in manifest["units"]:
        unit = units[info["id"]]
        count = sum(len(page["sentences"]) for page in unit["pages"])
        info["sentences"] = info["sentenceCount"] = count
        path = ROOT / f"data/unit-{info['id']}.json"
        write_original_style(path, unit)
    write_original_style(manifest_path, manifest)
    with (ROOT / "data/sentence-audit.tsv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["unit", "page", "id", "speaker", "text", "rects"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for info in manifest["units"]:
            for page in units[info["id"]]["pages"]:
                for card in page["sentences"]:
                    writer.writerow({"unit": info["id"], "page": page["page"],
                                     "id": card["id"], "speaker": card["speaker"],
                                     "text": card["text"], "rects": len(card["rects"])})
    print(f"Corrected {len(cards)} embedded phonetic cards; added {new_cards} sound cards at "
          f"{sum(map(len, spots.values()))} printed positions and generated {len(phonemes)} unique sounds.")


def write_original_style(path, data):
    """Keep the repository's original JSON layout and line endings."""
    raw = path.read_bytes()
    pretty = raw.startswith((b"{\n", b"{\r\n"))
    windows = b"\r\n" in raw[:100]
    if pretty:
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    else:
        content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if windows:
        content = content.replace("\n", "\r\n")
    path.write_bytes(content.encode())


if __name__ == "__main__":
    main()
