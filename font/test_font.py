#!/usr/bin/env python3
"""test_font.py -- shapes text through a patched font and reads back what a
reader would see.

The corpus is the one in `fcitx5-addon/test/test_rules.cpp` and `test/e2e`,
read backwards: what the input methods fold, the font unfolds. Anything that
round-trips through both should come out where it started.

The check runs the real shaper rather than reading the tables back, because
what is being claimed here is about HarfBuzz's behaviour, not about the bytes:
lookups in the wrong order, or a context that never fires, both build a font
that looks perfectly well-formed.

    test_font.py [-q] FONT[=ORIGINAL]...

Giving the font it was patched from, after an `=`, adds the checks that say
the original survived the patch.
"""

import sys

import uharfbuzz as hb
from fontTools.ttLib import TTFont

TUTUQ = "ʻ"  # what the corpus below is written with

CASES = [
    # The four rules, undone.
    ("şahar", "shahar"),
    ("çoy", "choy"),
    ("özbek", f"o{TUTUQ}zbek"),
    ("ǧalaba", f"g{TUTUQ}alaba"),

    # Capitals follow the neighbours, exactly as the input methods decide them.
    ("Şahar", "Shahar"),
    ("ŞAHAR", "SHAHAR"),
    ("Çoy", "Choy"),
    ("ÇOY", "CHOY"),
    ("Özbekiston", f"O{TUTUQ}zbekiston"),
    ("ǦALABA", f"G{TUTUQ}ALABA"),

    # A capital at the end of a word in capitals is led into, not followed.
    ("toş", "tosh"),
    ("TOŞ", "TOSH"),
    ("IŞ", "ISH"),

    # Two of them in a row: the H the first one grew is itself a capital, so
    # the second one sees it and follows.
    ("ŞÇ", "SHCH"),

    # More than one rule in a word.
    ("işçi", "ishchi"),
    ("öqiş", f"o{TUTUQ}qish"),
    ("ǧişt", f"g{TUTUQ}isht"),
    ("çöçiş", f"cho{TUTUQ}chish"),

    # Left alone: ng, a literal apostrophe, and text with none of the four.
    ("ming", "ming"),
    ("as'hob", "as'hob"),
    ("school", "school"),
    ("", ""),

    # The known limitation of the input methods, seen from the other side:
    # `school` typed at them comes out `sçool`, and this is what that then
    # draws as -- which is the argument for the doubling escape.
    ("sçool", "school"),
]


def reader(path):
    """Returns a function from text to the text a reader would see."""
    font = TTFont(path, fontNumber=0)
    order = font.getGlyphOrder()
    spelling = {}
    for cp, glyph in sorted(font.getBestCmap().items()):
        spelling.setdefault(glyph, chr(cp))

    face = hb.Face(hb.Blob.from_file_path(path))
    shaper = hb.Font(face)

    def drawn(text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(shaper, buf)
        out = []
        for info in buf.glyph_infos:
            glyph = order[info.codepoint]
            out.append(spelling.get(glyph, f"<{glyph}>"))
        return "".join(out)

    return drawn, font, spelling


def check_shaping(path, log):
    drawn, font, spelling = reader(path)

    # A font without U+02BB is patched with the closest shape it does have,
    # and then the corpus is about that shape instead. Asking the font what it
    # draws ö as is the least presumptuous way to find out which one it chose.
    belgisi = drawn("ö")[1:] or TUTUQ

    # A base font that has no glyph for a reformed letter cannot be made to
    # spell it, and ǧ is missing often enough to be worth saying so plainly
    # rather than reporting it as a failure of the patch.
    missing = {c for c in "şŞçÇöÖǧǦ" if drawn(c) == c}

    failures = 0
    for sent, want in CASES:
        if missing & set(sent):
            letters = " ".join(sorted(missing & set(sent)))
            log("skip " + repr(sent) + f"   the font has no {letters}")
            continue
        want = want.replace(TUTUQ, belgisi)
        got = drawn(sent)
        ok = got == want
        log(("ok   " if ok else "FAIL ") + repr(sent) + " -> " + repr(got) +
            ("" if ok else "   want " + repr(want)), ok)
        failures += not ok
    font.close()
    return failures


def check_survives(patched, original, log):
    """The base font's own tables have to come through untouched.

    Rebuilding a font's features instead of appending to them is the easy way
    to do this and it silently throws away kerning, so it is worth pinning.
    """
    failures = 0
    before, after = TTFont(original, fontNumber=0), TTFont(patched, fontNumber=0)

    def features(f):
        if "GSUB" not in f:
            return set()
        return {r.FeatureTag for r in f["GSUB"].table.FeatureList.FeatureRecord}

    for label, ok in (
        ("GPOS (kerning) survives", ("GPOS" in before) <= ("GPOS" in after)),
        ("the font's own features survive", features(before) <= features(after)),
        ("no glyphs added", before.getGlyphOrder() == after.getGlyphOrder()),
        ("the family is renamed", after["name"].getDebugName(1) !=
                                  before["name"].getDebugName(1)),
    ):
        log(("ok   " if ok else "FAIL ") + label, ok)
        failures += not ok
    before.close()
    after.close()
    return failures


def main(argv):
    quiet = "-q" in argv or "--quiet" in argv
    fonts = [a for a in argv if not a.startswith("-")]
    if not fonts:
        print("usage: test_font.py [-q] FONT[=ORIGINAL]...", file=sys.stderr)
        return 2

    failures = 0
    for path in fonts:
        original = None
        if "=" in path:
            path, original = path.split("=", 1)
        name = path.split("/")[-1]
        # Quietly is one line per font, and the whole log for any font that
        # has something to say -- which over a family is the difference
        # between a readable build log and five hundred lines of one.
        held = []

        def log(line, ok=True, held=held):
            held.append(line)
            if not quiet:
                print(line)

        if not quiet:
            print(f"== {name} ==")
        before = failures
        failures += check_shaping(path, log)
        if original:
            failures += check_survives(path, original, log)
        if quiet:
            if failures == before:
                print(f"ok   {name}   {len(held)} checks")
            else:
                print(f"== {name} ==")
                print("\n".join(held))
        else:
            print()

    if failures:
        print(f"{failures} failure(s)")
        return 1
    print("all font tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
