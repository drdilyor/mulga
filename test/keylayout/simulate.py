#!/usr/bin/env python3
"""Checks macos/UzbekMulga.keylayout without a Mac.

Implements the .keylayout state machine and runs the shared corpus through it.
Which physical key produces which character is taken from the CLDR U.S. data,
and what then happens is taken from the generated file, so this is not the
generator marking its own homework.

Also checks the things a typo would break silently: that the U.S. base layer
still says what CLDR says, that every referenced action exists, that every
state has a terminator, and that every action can be reached from `none`.
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KEYLAYOUT = ROOT / "macos" / "UzbekMulga.keylayout"
CLDR = ROOT / "macos" / "cldr"
CORPUS = ROOT / "spec" / "corpus.tsv"

HELD = set("sScCoOgG")

failures = []


def fail(what, detail):
    failures.append((what, detail))
    print("FAIL %s\n     %s" % (what, detail))


def unescape_cldr(text):
    out, i = [], 0
    while i < len(text):
        if text.startswith("\\u{", i):
            end = text.index("}", i)
            out.append(chr(int(text[i + 3:end], 16)))
            i = end + 1
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


# .keylayout files are XML 1.1 and reference control characters directly --
# Apple's own layouts do the same, and Return and the arrow keys need it.
# Python's expat only speaks XML 1.0 and rejects those references, so they are
# swapped for private-use characters before parsing and swapped back after.
CONTROL_REF = re.compile(r"&#x00([01][0-9A-Fa-f]|7[Ff]);")


def shield(raw):
    return CONTROL_REF.sub(
        lambda m: "&#x%04X;" % (0xE000 + int(m.group(1), 16)), raw)


def unshield(text):
    if text is None:
        return None
    return "".join(chr(ord(c) - 0xE000) if 0xE000 <= ord(c) <= 0xE0FF else c
                   for c in text)


def load_keylayout():
    raw = KEYLAYOUT.read_text(encoding="utf-8")
    if 'version="1.1"' not in raw.split("\n")[0]:
        fail("xml declaration", "must be version 1.1 to allow control refs")
    root = ET.fromstring(shield(raw))

    cells = {}
    for kms in root.findall("keyMapSet"):
        for km in kms.findall("keyMap"):
            index = int(km.get("index"))
            for key in km.findall("key"):
                cells[(index, int(key.get("code")))] = key.get("action")

    actions = {}
    for action in root.find("actions").findall("action"):
        table = {}
        for when in action.findall("when"):
            table[when.get("state")] = (unshield(when.get("output")),
                                        when.get("next"))
        actions[action.get("id")] = table

    terminators = {}
    for when in root.find("terminators").findall("when"):
        terminators[when.get("state")] = unshield(when.get("output"))

    return root, cells, actions, terminators


def load_cldr():
    platform = ET.parse(CLDR / "_platform.xml").getroot()
    iso_to_keycode = {m.get("iso"): int(m.get("keycode"))
                      for m in platform.iter("map")}
    layout = ET.parse(CLDR / "en-t-k0-osx.xml").getroot()
    keymaps = []
    for km in layout.findall("keyMap"):
        keymaps.append({m.get("iso"): (unescape_cldr(m.get("to")),
                                       m.get("transform") == "no")
                        for m in km.findall("map")})
    transforms = {unescape_cldr(t.get("from")): unescape_cldr(t.get("to"))
                  for t in layout.iter("transform")}
    return iso_to_keycode, keymaps, transforms


def main():
    root, cells, actions, terminators = load_keylayout()
    iso_to_keycode, keymaps, transforms = load_cldr()
    dead_prefixes = {f[0] for f in transforms if f}

    # -- structure ---------------------------------------------------------
    for (index, keycode), aid in sorted(cells.items()):
        if aid not in actions:
            fail("dangling action", "map %d key %d -> %s" % (index, keycode, aid))
    for aid, table in sorted(actions.items()):
        if "none" not in table:
            fail("action unreachable from none", aid)
        for state, (_out, nxt) in table.items():
            if state != "none" and state not in terminators:
                fail("state without terminator", "%s in %s" % (state, aid))
            if nxt and nxt not in terminators:
                fail("next state without terminator", "%s in %s" % (nxt, aid))
    declared = {sel.get("mapIndex")
                for sel in root.find("modifierMap").findall("keyMapSelect")}
    for index in {i for (i, _) in cells}:
        if str(index) not in declared:
            fail("key map not selectable", "index %d" % index)

    # -- the U.S. base layer still says what CLDR says ----------------------
    checked = 0
    for index, km in enumerate(keymaps):
        for iso, (text, no_transform) in km.items():
            keycode = iso_to_keycode.get(iso)
            if keycode is None:
                continue
            table = actions[cells[(index, keycode)]]
            out, nxt = table["none"]
            if text in HELD:
                if out is not None or not nxt:
                    fail("held letter should arm a state",
                         "map %d %s %r -> out=%r next=%r"
                         % (index, iso, text, out, nxt))
            elif len(text) == 1 and text in dead_prefixes and not no_transform:
                if out is not None or not nxt:
                    fail("dead key should arm a state",
                         "map %d %s %r" % (index, iso, text))
            elif out != text:
                fail("base layer changed",
                     "map %d %s expected %r got %r" % (index, iso, text, out))
            checked += 1
    print("base layer: %d cells agree with CLDR" % checked)

    # -- what a user can physically type -----------------------------------
    press = {}
    for index in (0, 1):
        for iso, (text, _no) in keymaps[index].items():
            keycode = iso_to_keycode.get(iso)
            if keycode is not None and len(text) == 1:
                press.setdefault(text, (index, keycode))

    def type_text(text):
        state = "none"
        out = []
        for ch in text:
            index, keycode = press[ch]
            table = actions[cells[(index, keycode)]]
            if state not in table:
                if state != "none":
                    out.append(terminators[state])
                state = "none"
            output, nxt = table[state]
            if output:
                out.append(output)
            state = nxt or "none"
        if state != "none":
            out.append(terminators[state])
        return "".join(out)

    # -- the shared corpus -------------------------------------------------
    ran = skipped = 0
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sent, want = line.split("\t")
        missing = [c for c in sent if c not in press]
        if missing:
            skipped += 1
            print("skip %-14r cannot be typed on this layout (%s)"
                  % (sent, " ".join("U+%04X" % ord(c) for c in missing)))
            continue
        got = type_text(sent)
        ran += 1
        if got == want:
            print("ok   %-14r -> %r" % (sent, got))
        else:
            fail("corpus", "%r -> %r, want %r" % (sent, got, want))

    # -- the inherited dead keys still work --------------------------------
    for source, want in sorted(transforms.items()):
        if len(source) != 2 or source[1] not in press:
            continue
        prefix, follower = source
        state = "dead_%04X" % ord(prefix)
        if state not in terminators:
            continue
        table = actions[cells[press[follower]]]
        if table.get(state, (None, None))[0] != want:
            fail("inherited dead key", "%r should give %r" % (source, want))
    print("inherited dead keys: %d transforms checked" % len(transforms))

    print("\ncorpus: %d run, %d skipped as untypeable" % (ran, skipped))
    if failures:
        print("%d FAILURE(S)" % len(failures))
        return 1
    print("all keylayout checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
