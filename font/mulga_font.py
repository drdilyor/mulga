#!/usr/bin/env python3
"""mulga_font.py -- show reformed Uzbek text in the old digraph spelling.

    ş -> sh    ç -> ch    ö -> oʻ    ǧ -> gʻ

The input methods in this repo fold the digraphs into single letters as they
are typed. This does the opposite, and does it at the last possible moment:
the file still holds ş, ç, ö and ǧ, and only the picture on the screen says
sh, ch, oʻ and gʻ. Select that text and copy it and the reformed letters are
what land in the clipboard, because nothing about the text has changed -- one
character is simply drawn as two.

That is what makes it useful while the reform is not universal. Write in the
reformed alphabet; hand the same file to someone who has to read, or print, or
submit it in the official spelling, and let their font undo it.

This is a patcher rather than a typeface. It takes any font and adds the four
rules to it as OpenType `ccmp` lookups that reuse that font's own s, h, c, o,
g and tutuq belgisi glyphs, so the result matches the original in weight,
width and every other respect -- and keeps its kerning, because the existing
GSUB and GPOS tables are left alone and appended to rather than rebuilt.

Capitals follow the same rule as the input methods: the case of the second
letter comes from the neighbours, so `Şahar` draws as `Shahar` and `ŞAHAR` as
`SHAHAR`. `ö` and `ǧ` need none of that -- the tutuq belgisi has no case.

Usage:
    mulga_font.py FONT... --out-dir DIR [--suffix NAME] [--apostrophe HEX]
    mulga_font.py FONT --print-rules      # resolved glyph rules, patch nothing
"""

import argparse
import os
import sys
import unicodedata

from fontTools.otlLib import builder as otl
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

# The reform, read backwards. `second_upper` is the capital of the second
# letter where it has one; the tutuq belgisi does not, which is why only sh
# and ch need to look at their neighbours to decide how to spell themselves.
REFORM = [
    # lower  upper   first  second  second_upper
    (0x015F, 0x015E, "s", "h", "H"),  # ş Ş  -> sh SH
    (0x00E7, 0x00C7, "c", "h", "H"),  # ç Ç  -> ch CH
    (0x00F6, 0x00D6, "o", None, None),  # ö Ö -> oʻ Oʻ
    (0x01E7, 0x01E6, "g", None, None),  # ǧ Ǧ -> gʻ Gʻ
]

# U+02BB is the tutuq belgisi the old standard prescribed, so it is what the
# old spelling should be drawn with. The rest are for fonts that do not carry
# it, in descending order of how close they look.
APOSTROPHES = [
    0x02BB,  # ʻ MODIFIER LETTER TURNED COMMA
    0x2018,  # ‘ LEFT SINGLE QUOTATION MARK
    0x02BC,  # ʼ MODIFIER LETTER APOSTROPHE
    0x2019,  # ’ RIGHT SINGLE QUOTATION MARK
    0x0027,  # ' APOSTROPHE
]

FEATURE = "ccmp"


class Unsupported(Exception):
    """The font cannot spell the old alphabet, so there is nothing to patch."""


# ---------------------------------------------------------------- the rules


def resolve(font, apostrophe=None):
    """Works out the glyph-level rules for one font.

    Returns (plain, upper, marks, apostrophe_codepoint):
    `plain` is every reformed letter to the spelling it gets on its own and
    `upper` is the two capitals that spell themselves differently next to
    another capital -- both {glyph: [glyph, glyph]}, which is what a
    MultipleSubst is. `marks` is {mark glyph: (base glyphs, tail glyph)} for
    the same letters written decomposed, which is how a shaper hands them over
    when the font has no glyph for the precomposed letter.
    """
    cmap = font.getBestCmap()

    def glyph(cp_or_char):
        cp = cp_or_char if isinstance(cp_or_char, int) else ord(cp_or_char)
        return cmap.get(cp)

    wanted = [apostrophe] if apostrophe else APOSTROPHES
    apos = next((cp for cp in wanted if cp in cmap), None)
    if apos is None:
        shapes = " ".join(f"U+{cp:04X}" for cp in wanted)
        raise Unsupported(f"no tutuq belgisi in the font (looked for {shapes})")

    plain, upper, marks = {}, {}, {}
    for lower_cp, upper_cp, first, second, second_upper in REFORM:
        tail = glyph(second) if second else glyph(apos)
        tail_upper = glyph(second_upper) if second_upper else tail
        # `Şahar` draws as `Shahar`, so on its own a capital takes the same
        # lowercase tail as its lowercase twin. SH is the exception below.
        for cp, head in ((lower_cp, glyph(first)),
                         (upper_cp, glyph(first.upper()))):
            here = glyph(cp)
            # A font missing the letter, or missing what it decomposes to, is
            # skipped rather than fatal: the other rules still work.
            if here is None or head is None or tail is None:
                continue
            plain[here] = [head, tail]

        # Next to another capital, Ş and Ç spell themselves SH and CH.
        if second_upper:
            here, head = glyph(upper_cp), glyph(first.upper())
            if here and head and tail_upper:
                upper[here] = [head, tail_upper]

        # ǧ is rare enough that plenty of fonts have no glyph for it, and a
        # shaper faced with that decomposes the letter into g and a combining
        # caron before any of this runs. Substituting the mark after its own
        # base letter catches that, and catches text that simply arrives in
        # NFD. It is only done for ö and ǧ: their second letter is the tutuq
        # belgisi, which has no case, so no neighbour needs consulting.
        if second is None:
            for cp in (lower_cp, upper_cp):
                pieces = unicodedata.normalize("NFD", chr(cp))
                if len(pieces) != 2:
                    continue
                base, mark = glyph(pieces[0]), glyph(pieces[1])
                if base and mark and tail:
                    shapes, _ = marks.setdefault(mark, ({}, tail))
                    for shape in variants(font, base):
                        shapes[shape] = base

    if not plain and not marks:
        raise Unsupported("none of ş, ç, ö or ǧ are in the font")
    return plain, upper, marks, apos


def variants(font, name):
    """A glyph and the font's alternates of it, by the usual naming.

    Fonts swap letters for alternates before we get a look in -- IBM Plex
    turns g into g.alt02 in its own ccmp precisely when a combining mark
    follows, which is the case this fallback exists for -- and our lookups are
    appended, so they run after that has already happened. The `g.alt02`
    convention for naming a variant is not a rule anyone enforces, so this is
    a guess; it costs nothing when it is wrong, since a glyph that never turns
    up in that position is a glyph the context never matches.
    """
    prefix = name + "."
    return {g for g in font.getGlyphOrder() if g == name or g.startswith(prefix)}


def uppercase_glyphs(font):
    """Every capital the font can draw -- the context that makes Ş into SH."""
    names = set()
    for cp, name in font.getBestCmap().items():
        if unicodedata.category(chr(cp)) == "Lu":
            names.add(name)
    return names


# --------------------------------------------------------------- the tables


def coverage(glyphs, font):
    return otl.buildCoverage(glyphs, font.getReverseGlyphMap())


def chain_subtable(font, prefix, here, suffix, lookup_index):
    """A format 3 chaining context that runs `lookup_index` on `here`."""
    st = ot.ChainContextSubst()
    st.Format = 3
    # Backtrack coverages are stored nearest-first, so reversed() of the text
    # order is what goes in the table.
    st.BacktrackCoverage = [coverage(g, font) for g in reversed(prefix)]
    st.BacktrackGlyphCount = len(st.BacktrackCoverage)
    st.InputCoverage = [coverage(here, font)]
    st.InputGlyphCount = 1
    st.LookAheadCoverage = [coverage(g, font) for g in suffix]
    st.LookAheadGlyphCount = len(st.LookAheadCoverage)
    record = ot.SubstLookupRecord()
    record.SequenceIndex = 0
    record.LookupListIndex = lookup_index
    st.SubstLookupRecord = [record]
    st.SubstCount = 1
    return st


def ensure_gsub(font):
    if "GSUB" in font:
        return font["GSUB"].table
    table = newTable("GSUB")
    table.table = ot.GSUB()
    table.table.Version = 0x00010000
    table.table.ScriptList = ot.ScriptList()
    table.table.ScriptList.ScriptRecord = []
    table.table.FeatureList = ot.FeatureList()
    table.table.FeatureList.FeatureRecord = []
    table.table.LookupList = ot.LookupList()
    table.table.LookupList.Lookup = []
    font["GSUB"] = table
    return table.table


def every_langsys(gsub):
    if not gsub.ScriptList.ScriptRecord:
        record = ot.ScriptRecord()
        record.ScriptTag = "DFLT"
        record.Script = ot.Script()
        record.Script.DefaultLangSys = ot.LangSys()
        record.Script.DefaultLangSys.ReqFeatureIndex = 0xFFFF
        record.Script.DefaultLangSys.FeatureIndex = []
        record.Script.LangSysRecord = []
        gsub.ScriptList.ScriptRecord.append(record)
    out = []
    for record in gsub.ScriptList.ScriptRecord:
        script = record.Script
        if script is None:
            continue
        if script.DefaultLangSys is not None:
            out.append(script.DefaultLangSys)
        for entry in script.LangSysRecord or []:
            if entry.LangSys is not None:
                out.append(entry.LangSys)
    return out


def reference_from_feature(gsub, tag, lookup_indices):
    """Makes `tag` run `lookup_indices`, for every script the font has.

    Appends to the feature where it already exists -- a font's own ccmp
    lookups keep running, and ours run after them -- and adds the feature
    where it does not.
    """
    records = gsub.FeatureList.FeatureRecord
    added = None
    for langsys in every_langsys(gsub):
        indices = list(langsys.FeatureIndex or [])
        mine = [i for i in indices if records[i].FeatureTag == tag]
        if not mine:
            if added is None:
                added = len(records)
                record = ot.FeatureRecord()
                record.FeatureTag = tag
                record.Feature = ot.Feature()
                record.Feature.FeatureParams = None
                record.Feature.LookupListIndex = []
                records.append(record)
            indices.append(added)
            langsys.FeatureIndex = indices
            mine = [added]
        for index in mine:
            feature = records[index].Feature
            existing = list(feature.LookupListIndex or [])
            feature.LookupListIndex = existing + [
                i for i in lookup_indices if i not in existing
            ]
    if added is not None:
        sort_features(gsub)


def sort_features(gsub):
    """Puts the FeatureList back in tag order and repoints everything at it.

    The spec has FeatureRecords ordered by tag; appending one breaks that, so
    this re-sorts (stably, since several records may share a tag) and rewrites
    every index that pointed into the list.
    """
    records = gsub.FeatureList.FeatureRecord
    order = sorted(range(len(records)), key=lambda i: records[i].FeatureTag)
    if order == list(range(len(records))):
        return
    moved = {old: new for new, old in enumerate(order)}
    gsub.FeatureList.FeatureRecord = [records[i] for i in order]
    for langsys in every_langsys(gsub):
        langsys.FeatureIndex = [moved[i] for i in langsys.FeatureIndex or []]
        if langsys.ReqFeatureIndex not in (None, 0xFFFF):
            langsys.ReqFeatureIndex = moved[langsys.ReqFeatureIndex]
    variations = getattr(gsub, "FeatureVariations", None)
    for record in getattr(variations, "FeatureVariationRecord", None) or []:
        substitution = record.FeatureTableSubstitution
        for entry in getattr(substitution, "SubstitutionRecord", None) or []:
            entry.FeatureIndex = moved[entry.FeatureIndex]


def patch_tables(font, plain, upper, marks, uppers):
    """Adds the three lookups and hangs the two entry points off ccmp.

    Lookups run in LookupList order, so the context has to be built before the
    plain rules: by the time they run, ŞAHAR is already SHAHAR and there is no
    Ş left for them to spell any other way. The lookup the context calls is
    deliberately not listed in the feature -- reachable only from the context,
    it would otherwise turn every Ş into SH on its own.
    """
    gsub = ensure_gsub(font)
    lookups = gsub.LookupList.Lookup
    entry_points = []

    if upper:
        called = len(lookups)
        lookups.append(otl.buildLookup([otl.buildMultipleSubstSubtable(upper)]))
        letters = sorted(upper)
        subtables = [
            # ŞAHAR: a capital follows.
            chain_subtable(font, [], letters, [sorted(uppers)], called),
            # TOŞ: a capital leads.
            chain_subtable(font, [sorted(uppers)], letters, [], called),
        ]
        entry_points.append(len(lookups))
        lookups.append(otl.buildLookup(subtables))

    if marks:
        subtables = []
        # A font that swapped the letter for an alternate because a combining
        # mark was coming gets the plain letter back: the mark is about to
        # become a tutuq belgisi, which sits after the letter and no longer
        # has anything to collide with.
        restore = {shape: base for shapes, _ in marks.values()
                   for shape, base in shapes.items() if shape != base}
        if restore:
            restoring = len(lookups)
            lookups.append(otl.buildLookup(
                [otl.buildSingleSubstSubtable(restore)]))
            for mark, (shapes, _) in sorted(marks.items()):
                swapped = sorted(shape for shape in shapes if shape in restore)
                if swapped:
                    subtables.append(
                        chain_subtable(font, [], swapped, [[mark]], restoring))

        spelling = len(lookups)
        lookups.append(otl.buildLookup([otl.buildSingleSubstSubtable(
            {mark: tail for mark, (_, tail) in marks.items()})]))
        subtables += [
            chain_subtable(font, [sorted(shapes)], [mark], [], spelling)
            for mark, (shapes, _) in sorted(marks.items())
        ]
        entry_points.append(len(lookups))
        lookups.append(otl.buildLookup(subtables))

    if plain:
        entry_points.append(len(lookups))
        lookups.append(otl.buildLookup([otl.buildMultipleSubstSubtable(plain)]))

    reference_from_feature(gsub, FEATURE, entry_points)


# ---------------------------------------------------------------- the naming


def rename(font, suffix):
    """Renames the family so it sits beside the original instead of over it.

    A patched font that still calls itself DejaVu Sans is a font that
    fontconfig may hand out when something asks for DejaVu Sans, which would
    change how text renders in applications that never asked for any of this.
    """
    name = font["name"]
    family = name.getDebugName(16) or name.getDebugName(1) or "Unnamed"
    patched_family = f"{family} {suffix}"
    subfamily = name.getDebugName(17) or name.getDebugName(2) or "Regular"

    def with_suffix(value):
        # "DejaVu Sans" -> "DejaVu Sans Mulga", but also
        # "DejaVu Sans ExtraLight" -> "DejaVu Sans Mulga ExtraLight", so the
        # weight stays at the end where a font menu expects to find it.
        if value.startswith(family):
            return patched_family + value[len(family):]
        return f"{value} {suffix}"

    for record in list(name.names):
        value = str(record)
        if record.nameID in (1, 16, 18):
            record.string = with_suffix(value)
        elif record.nameID in (4,):
            record.string = with_suffix(value)
        elif record.nameID == 6:
            head, _, tail = value.partition("-")
            compact = suffix.replace(" ", "")
            record.string = f"{head}{compact}" + (f"-{tail}" if tail else "")
        elif record.nameID == 3:
            record.string = f"{with_suffix(value)}"

    full = name.getDebugName(4) or f"{patched_family} {subfamily}"
    if name.getDebugName(3) is None:
        name.setName(full, 3, 3, 1, 0x409)

    # CFF carries its own copy of the names, and a mismatch confuses tools
    # that read one and trust the other.
    if "CFF " in font:
        cff = font["CFF "].cff
        postscript = name.getDebugName(6) or full.replace(" ", "")
        top = cff[cff.fontNames[0]]
        cff.fontNames[0] = postscript
        if hasattr(top, "FamilyName"):
            top.FamilyName = patched_family
        if hasattr(top, "FullName"):
            top.FullName = full
    return patched_family, subfamily


# ------------------------------------------------------------------- driving


def patch(path, out_dir, suffix, apostrophe):
    font = TTFont(path, fontNumber=0)
    plain, upper, marks, apos = resolve(font, apostrophe)
    patch_tables(font, plain, upper, marks, uppercase_glyphs(font))
    family, subfamily = rename(font, suffix)

    stem, extension = os.path.splitext(os.path.basename(path))
    out = os.path.join(out_dir, f"{stem}-{suffix.replace(' ', '')}{extension}")
    os.makedirs(out_dir, exist_ok=True)
    font.save(out)
    font.close()
    return out, family, subfamily, apos


def print_rules(path, apostrophe):
    font = TTFont(path, fontNumber=0)
    plain, upper, marks, apos = resolve(font, apostrophe)
    reverse = {}
    for cp, glyph in sorted(font.getBestCmap().items()):
        reverse.setdefault(glyph, chr(cp))

    def show(glyph):
        return f"{reverse.get(glyph, '?')} ({glyph})"

    print(f"{os.path.basename(path)}   tutuq belgisi U+{apos:04X}")
    for title, rules in (("on its own", plain), ("next to a capital", upper)):
        if not rules:
            continue
        print(f"  {title}:")
        for here, spelling in rules.items():
            drawn = " ".join(show(g) for g in spelling)
            print(f"    {show(here):22s} -> {drawn}")
    if marks:
        print("  written as a base and a combining mark:")
        for mark, (shapes, tail) in sorted(marks.items()):
            after = " ".join(show(b) for b in sorted(shapes))
            print(f"    {show(mark):22s} -> {show(tail)}   after {after}")
    font.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Patch fonts to draw reformed Uzbek in the old spelling.")
    parser.add_argument("fonts", nargs="+", metavar="FONT")
    parser.add_argument("-o", "--out-dir", metavar="DIR")
    parser.add_argument("--suffix", default="Mulga",
                        help="appended to the family name (default: Mulga)")
    parser.add_argument("--apostrophe", metavar="HEX",
                        help="tutuq belgisi codepoint, e.g. 2019 "
                             "(default: 02BB, or the closest the font has)")
    parser.add_argument("--print-rules", action="store_true",
                        help="show the rules a font would get, and patch none")
    args = parser.parse_args(argv)

    apostrophe = int(args.apostrophe, 16) if args.apostrophe else None
    if args.print_rules:
        for path in args.fonts:
            print_rules(path, apostrophe)
        return 0
    if not args.out_dir:
        parser.error("--out-dir is required unless --print-rules is given")

    # A font with none of the four letters in it is reported and stepped over
    # rather than fatal, because handing this a whole family means handing it
    # whatever else that package ships -- a symbol font, a math face -- and
    # only producing nothing at all is a failure worth stopping for.
    patched = 0
    for path in args.fonts:
        try:
            out, family, subfamily, apos = patch(
                path, args.out_dir, args.suffix, apostrophe)
        except Unsupported as reason:
            print(f"skip {os.path.basename(path)}: {reason}", file=sys.stderr)
            continue
        patched += 1
        print(f"{family} {subfamily}  U+{apos:04X}  -> {out}")
    if not patched:
        print("nothing patched", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
