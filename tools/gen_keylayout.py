#!/usr/bin/env python3
"""Generates macos/UzbekMulga.keylayout from the vendored CLDR U.S. layout.

The base layer -- which key sits where, and what it produces in each of the
eight modifier combinations -- comes from CLDR rather than from memory. On top
of that this adds the four Uzbek rules as keyboard states, and carries the U.S.
layout's own dead keys (acute, grave, circumflex, tilde, diaeresis) across
unchanged.

.keylayout semantics this relies on: when a key's action has no `when` entry
for the current state, the terminator for that state is emitted and the action
is retried in state `none`. That is what releases a held `s` when the next key
turns out not to be `h`.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLDR = ROOT / "macos" / "cldr"
OUT = ROOT / "macos" / "UzbekMulga.keylayout"

LAYOUT_NAME = "Uzbek (Mulga)"
# Third-party layouts take a negative id; group 126 is the Latin script.
LAYOUT_ID = "-6021"
LAYOUT_GROUP = "126"

# The reform. Held letter -> {following character: what to emit}.
# `sH` and `cH` are absent on purpose, matching the other two implementations.
FOLD = {
    "s": {"h": "ş"},
    "S": {"h": "Ş", "H": "Ş"},
    "c": {"h": "ç"},
    "C": {"h": "Ç", "H": "Ç"},
    "o": {"'": "ö", "`": "ö"},
    "O": {"'": "Ö", "`": "Ö"},
    "g": {"'": "ğ", "`": "ğ"},
    "G": {"'": "Ğ", "`": "Ğ"},
}

# Keys CLDR does not model, because it only describes printable ones. These are
# the conventional macOS values; without them Return, Tab and the arrows would
# produce nothing at all. Unlike everything else in this file they come from
# convention rather than from published data.
SPECIAL = {
    36: "\r",      # Return
    48: "\t",      # Tab
    51: "\b",      # Delete
    53: "\x1b",    # Escape
    65: ".",       # keypad decimal
    67: "*",       # keypad multiply
    69: "+",       # keypad plus
    71: "\x1b",    # keypad Clear
    75: "/",       # keypad divide
    76: "\x03",    # keypad Enter
    78: "-",       # keypad minus
    81: "=",       # keypad equals
    82: "0", 83: "1", 84: "2", 85: "3", 86: "4",
    87: "5", 88: "6", 89: "7", 91: "8", 92: "9",
    114: "\x05",   # Help
    115: "\x01",   # Home
    116: "\x0b",   # Page Up
    117: "\x7f",   # Forward Delete
    119: "\x04",   # End
    121: "\x0c",   # Page Down
    123: "\x1c",   # Left
    124: "\x1d",   # Right
    125: "\x1f",   # Down
    126: "\x1e",   # Up
}
# Function keys F1-F20 all report the same character.
for _kc in (122, 120, 99, 118, 96, 97, 98, 100, 101, 109, 103, 111,
            105, 107, 113, 106, 64, 79, 80, 90):
    SPECIAL[_kc] = "\x10"

# Which physical modifiers select which of the eight key maps. Ordered to match
# the keyMaps in the CLDR file. `command?` on the base and shift entries is what
# keeps Cmd-C and Cmd-Shift-Z working.
MODIFIER_SELECTS = [
    "command?",                              # 0 base
    "anyShift caps? command?",               # 1 shift
    "caps",                                  # 2 caps lock
    "anyOption",                             # 3 option
    "anyShift caps? anyOption command?",     # 4 option + shift
    "caps anyOption",                        # 5 option + caps lock
    "anyControl command? anyOption? caps? anyShift?",  # 6 control
    "command anyOption caps?",               # 7 command + option
]


def unescape_cldr(text):
    """CLDR writes non-printables as \\u{XX}."""
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


def load_cldr():
    platform = ET.parse(CLDR / "_platform.xml").getroot()
    iso_to_keycode = {m.get("iso"): int(m.get("keycode"))
                      for m in platform.iter("map")}

    layout = ET.parse(CLDR / "en-t-k0-osx.xml").getroot()
    keymaps = []
    for km in layout.findall("keyMap"):
        cells = {}
        for m in km.findall("map"):
            cells[m.get("iso")] = (unescape_cldr(m.get("to")),
                                   m.get("transform") == "no")
        keymaps.append(cells)

    transforms = {}
    for t in layout.iter("transform"):
        transforms[unescape_cldr(t.get("from"))] = unescape_cldr(t.get("to"))
    return iso_to_keycode, keymaps, transforms


def xml_text(s):
    out = []
    for ch in s:
        if ch in "&<>\"'" or ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append("&#x%04X;" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def state_for_hold(ch):
    return "uz_%04X" % ord(ch)


def state_for_dead(ch):
    return "dead_%04X" % ord(ch)


def main():
    iso_to_keycode, keymaps, transforms = load_cldr()

    # A character is a dead key if some transform starts with it.
    dead_prefixes = {f[0] for f in transforms if f}

    actions = {}  # action id -> {state: (output or None, next state or None)}

    def literal_action(ch):
        aid = "out_" + "_".join("%04X" % ord(c) for c in ch)
        actions.setdefault(aid, {}).setdefault("none", (ch, None))
        return aid

    def dead_action(ch):
        aid = "arm_%04X" % ord(ch)
        actions.setdefault(aid, {})["none"] = (None, state_for_dead(ch))
        return aid

    # Pass 1: every cell of every key map becomes an action reference.
    cells = {}  # (map index, keycode) -> action id
    for index, km in enumerate(keymaps):
        for iso, (text, no_transform) in km.items():
            keycode = iso_to_keycode.get(iso)
            if keycode is None:
                continue
            if len(text) == 1 and text in dead_prefixes and not no_transform:
                cells[(index, keycode)] = dead_action(text)
            else:
                cells[(index, keycode)] = literal_action(text)

    # The keys CLDR does not describe behave the same under every modifier.
    for keycode, text in SPECIAL.items():
        aid = literal_action(text)
        for index in range(len(keymaps)):
            cells.setdefault((index, keycode), aid)

    # Pass 2: the reform. The held letters stop emitting anything of their own
    # and arm a state instead; the letters that complete a digraph learn what
    # to emit while one of those states is armed.
    for held, followers in FOLD.items():
        actions[literal_action(held)]["none"] = (None, state_for_hold(held))
        for follower, result in followers.items():
            actions[literal_action(follower)][state_for_hold(held)] = (result,
                                                                       None)

    # Pass 3: the U.S. layout's own dead keys, carried over unchanged.
    for source, result in transforms.items():
        if len(source) != 2:
            continue
        prefix, follower = source
        actions[literal_action(follower)][state_for_dead(prefix)] = (result,
                                                                     None)

    terminators = {}
    for held in FOLD:
        terminators[state_for_hold(held)] = held
    for ch in dead_prefixes:
        # CLDR spells the lone-dead-key case as "<prefix> ".
        terminators[state_for_dead(ch)] = transforms.get(ch + " ", ch)

    maxout = max(len(v[0]) for a in actions.values()
                 for v in a.values() if v[0] is not None)

    L = []
    L.append('<?xml version="1.1" encoding="UTF-8"?>')
    L.append('<!DOCTYPE keyboard SYSTEM '
             '"file://localhost/System/Library/DTDs/KeyboardLayout.dtd">')
    # XML comments may not contain a double hyphen, so none of these lines
    # may use one as punctuation.
    L.append('<!--')
    L.append('    %s : the reformed Uzbek Latin alphabet.' % LAYOUT_NAME)
    L.append('')
    L.append("    sh to ş, ch to ç, o' to ö, g' to ğ")
    L.append('')
    L.append('    Generated by tools/gen_keylayout.py. Do not edit by hand.')
    L.append('    The U.S. base layer comes from CLDR; see macos/cldr/PROVENANCE.')
    L.append('-->')
    L.append('<keyboard group="%s" id="%s" name="%s" maxout="%d">'
             % (LAYOUT_GROUP, LAYOUT_ID, xml_text(LAYOUT_NAME), maxout))
    L.append('  <layouts>')
    L.append('    <layout first="0" last="17" modifiers="commonModifiers" '
             'mapSet="ANSI"/>')
    L.append('    <layout first="18" last="255" modifiers="commonModifiers" '
             'mapSet="ANSI"/>')
    L.append('  </layouts>')

    L.append('  <modifierMap id="commonModifiers" defaultIndex="0">')
    for index, keys in enumerate(MODIFIER_SELECTS):
        L.append('    <keyMapSelect mapIndex="%d">' % index)
        L.append('      <modifier keys="%s"/>' % keys)
        L.append('    </keyMapSelect>')
    L.append('  </modifierMap>')

    L.append('  <keyMapSet id="ANSI">')
    for index in range(len(keymaps)):
        L.append('    <keyMap index="%d">' % index)
        for keycode in sorted(k for (i, k) in cells if i == index):
            L.append('      <key code="%d" action="%s"/>'
                     % (keycode, cells[(index, keycode)]))
        L.append('    </keyMap>')
    L.append('  </keyMapSet>')

    L.append('  <actions>')
    for aid in sorted(actions):
        L.append('    <action id="%s">' % aid)
        for state in sorted(actions[aid], key=lambda s: (s != "none", s)):
            output, nxt = actions[aid][state]
            bits = ['state="%s"' % state]
            if output is not None:
                bits.append('output="%s"' % xml_text(output))
            if nxt is not None:
                bits.append('next="%s"' % nxt)
            L.append('      <when %s/>' % " ".join(bits))
        L.append('    </action>')
    L.append('  </actions>')

    L.append('  <terminators>')
    for state in sorted(terminators):
        L.append('    <when state="%s" output="%s"/>'
                 % (state, xml_text(terminators[state])))
    L.append('  </terminators>')
    L.append('</keyboard>')

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote %s" % OUT.relative_to(ROOT))
    print("  key maps  %d" % len(keymaps))
    print("  keys      %d" % len({k for (_, k) in cells}))
    print("  actions   %d" % len(actions))
    print("  states    %d (%d from the reform, %d inherited dead keys)"
          % (len(terminators), len(FOLD), len(dead_prefixes)))
    print("  maxout    %d" % maxout)


if __name__ == "__main__":
    main()
