# Make Uzbek Language Great Again

An fcitx5 input method that types the reformed Uzbek Latin alphabet: the
digraphs fold into single letters as you type them.

| you type | you get | example |
| --- | --- | --- |
| `sh` | `ş` | `shahar` → `şahar` |
| `ch` | `ç` | `choy` → `çoy` |
| `o'` | `ö` | `o'zbek` → `özbek` |
| `g'` | `ǧ` | `g'alaba` → `ǧalaba` |

`ng` is left alone.

Capitals follow the first letter of the digraph, so `Shahar` → `Şahar` and
`SHAHAR` → `ŞAHAR`. Any of `'`, `` ` ``, `´`, `ʹ`, `ʻ`, `ʼ`, `'`, `'` or `′`
works as the tutuq belgisi in `o'` and `g'`, since that character arrives in a
different shape depending on the keyboard, the application and where the text
was pasted from.

There is also a font that undoes all of this at the other end, for readers who
want the old spelling out of a file that is written in the new one: [reading it
the old way](#reading-it-the-old-way).

## Plan

One set of rules, written out once per platform in whatever that platform
accepts as data. v1 is three targets:

| Target | Reaches | Format | State |
| --- | --- | --- | --- |
| fcitx5 addon | fcitx5 on Linux | C++ | working |
| m17n `.mim` | ibus, fcitx5 and SCIM on Linux | declarative sequence table | working |
| `.keylayout` | macOS | declarative state machine | working, but see below |

Deferred past v1:

| | Why |
| --- | --- |
| Windows | Unresolved. Windows dead keys can only emit a single character from a composition, so a literal `sh` cannot be typed without a dedicated extra key — which the requirements rule out. fcitx5 has no Windows port, so the realistic options are Keyman or a TSF input method, both of which cost more than v1 is worth. |
| iOS, Android | Needs an app whichever way you go; Keyman's is the cheap route. |
| Upstreaming the `.mim` | Later. Until then it is one file in `~/.m17n.d`, which needs no one's permission. |
| Converting existing text | Out of scope. This project fixes input. |

All three are held to the same conformance corpus in `spec/corpus.tsv`. Rows a
target cannot physically type — the exotic apostrophes, on a U.S. Mac keyboard —
are skipped and counted rather than quietly passing.

## Installing

There are two Linux routes and they can be installed side by side. The addon is
self-contained; the `.mim` needs `fcitx5-m17n` present but also works under
ibus and SCIM, and costs nothing to change.

### Names in the input method list

Both entries sit under **Uzbek**, alongside `Keyboard - Uzbek`,
`Keyboard - Uzbek - Uzbek (Latin)`, the two Dari/Afghanistan layouts and the
Cyrillic `kbd (M17N)`. Ours are:

| | Shows as | Unique name |
| --- | --- | --- |
| addon | **Uzbek (Mulga)** | `mulga` |
| `.mim` | **Mulga (M17N)** | `m17n_uz_Mulga` |

The `.mim` cannot be called "Uzbek (Mulga)": fcitx5-m17n builds every name as
`"{0} (M17N)"` from the m17n name symbol, and the override file that carries a
nicer name never loads, because its parser skips every non-empty line
(`if (!line.empty() || line[0] == '#') continue;` in `overrideparser.cpp`).
Capitalising the symbol, so the file is `uz-Mulga.mim`, is the whole of the
lever available.

### The m17n input method

No compilation and no root — m17n reads `~/.m17n.d` before anything else:

```sh
mkdir -p ~/.m17n.d
cp m17n/uz-Mulga.mim ~/.m17n.d/
```

Make sure `fcitx5-m17n` is among your fcitx5 addons, restart fcitx5, and add
**Mulga (M17N)** in `fcitx5-configtool`.

### macOS

Copy the layout in and log out and back in — macOS only rescans at login:

```sh
mkdir -p ~/Library/Keyboard\ Layouts
cp macos/UzbekMulga.keylayout ~/Library/Keyboard\ Layouts/
```

Then add **Uzbek (Mulga)** under System Settings, Keyboard, Input Sources. No
signing, no notarisation, no administrator rights: a keyboard layout is data,
not code.

It is a full U.S. layout with the reform on top, so everything else stays where
it was, including the option-key characters and the accent dead keys.

### The fcitx5 addon

On NixOS, add the flake as an input and hand the package to fcitx5:

```nix
{
  inputs.mulga.url = "path:/home/jester/code/mulga";   # or a git URL

  # in your system configuration
  i18n.inputMethod = {
    enable = true;
    type = "fcitx5";                                   # `enabled` on older nixpkgs
    fcitx5.addons = [ inputs.mulga.packages.x86_64-linux.mulga ];
  };
}
```

Then rebuild, restart fcitx5, and add **Uzbek (Mulga)** in
`fcitx5-configtool`.

To try either without touching the system configuration:

```sh
nix build .#fcitx5-with-mulga            # carries the addon and fcitx5-m17n
M17NDIR=$PWD/m17n ./result/bin/fcitx5 -r # -r replaces the running instance
```

## How it behaves

The engine holds back one character at a time — only `s`, `c`, `o`, `g` and
their capitals, since only those can begin a digraph — and shows it underlined
as preedit until the next keystroke decides what it is. Everything else is
passed straight through to the application, including Escape, Return and
anything with Ctrl, Alt or Super, so editors and terminals keep working
normally.

A held character is given back as plain text whenever the wait ends: the next
keystroke, focus moving away, switching input method, or the application
resetting us. Backspace on a held character takes back that character rather
than the one before it.

The apostrophe doubles as a separator, which is what keeps `as'hob` intact: it
releases the `s`, so the `h` after it has nothing left to attach to.

### Known limitation

Borrowings spelled with a literal `sh` or `ch` fold too — `school` comes out as
`sçool`. There is no escape character; switch input method for those. This is
pinned in the tests, so changing it is a deliberate act rather than an
accident.

`m17n/uz-Mulga.mim` carries a commented-out **doubling escape** that would fix
this: with `("chh" "ch")` in the table, typing `s c h h o o l` gives `school`.
It is the convention Vietnamese Telex already uses. It is off by default
because it is not free — `sh` and `ch` become prefixes of a longer rule, so
they stop committing until the following key arrives, and because Windows dead
keys cannot express it, adopting it would mean the platforms diverge.

### Where the two Linux routes differ

One case, found by the end-to-end tests. When the *application* resets the
input context — not a focus change, which both handle — the addon hands back a
held character and the `.mim` drops it, so `ming` can come out as `min`. That
is `M17NEngine::reset` in fcitx5-m17n committing nothing, which no rule in a
`.mim` can override. It costs at most one letter, and only when that letter is
`s`, `c`, `o` or `g` and it is the last thing typed before the reset.

## Reading it the old way

The reform does not have to be won one reader at a time. `font/` patches a
font so that reformed text draws in the old spelling:

| the file holds | the page shows |
| --- | --- |
| `şahar` | `shahar` |
| `çoy` | `choy` |
| `özbek` | `oʻzbek` |
| `ǧalaba` | `gʻalaba` |

Nothing about the text changes. Select it, copy it, search it, and it is still
ş, ç, ö and ǧ -- one character that happens to be drawn as two. So the same
file can be written in the reformed alphabet and handed to someone who has to
read, print or submit it in the official one.

It is a patcher rather than a typeface. `font/mulga_font.py` takes any font and
adds the four rules to it as OpenType `ccmp` lookups that reuse that font's own
s, h, c, o, g and tutuq belgisi glyphs, so the result matches the original in
weight, width and everything else. It also keeps its kerning: the GSUB and GPOS
tables the font already has are appended to rather than rebuilt, which is worth
saying because feaLib -- the obvious tool for the job -- replaces GSUB and
drops GPOS outright. That is pinned in the tests.

Capitals follow the same rule as the input methods, from the other side, so
`Şahar` draws as `Shahar` and `ŞAHAR` as `SHAHAR`: a capital spells itself SH
next to another capital and Sh otherwise. `ö` and `ǧ` need none of that, the
tutuq belgisi having no case.

```sh
nix build .#font                       # DejaVu Sans, Serif and Mono
mkdir -p ~/.local/share/fonts
cp result/share/fonts/truetype/*.ttf ~/.local/share/fonts/
fc-cache -f
```

Then choose **DejaVu Sans Mulga** wherever you would have chosen DejaVu Sans.
The family is renamed on purpose: a patched font that still calls itself DejaVu
Sans is one fontconfig may hand to an application that asked for DejaVu Sans
and wanted no part in any of this.

Any font can be patched, not just the one the flake builds. `font/default.nix`
takes a font package and gives back the same package patched, so a family is
one call:

```nix
{
  fonts.packages = [
    (inputs.mulga.lib.patchFont pkgs { font = pkgs.ibm-plex; })
  ];
}
```

`suffix` renames the family (`Mulga` by default), `apostrophe` picks the tutuq
belgisi by codepoint if U+02BB is not what you want, `exclude` drops faces by
pattern, and `doCheck` is the shaping tests, on by default. Without the flake
it is `pkgs.callPackage ./font { } { font = pkgs.ibm-plex; }` -- the empty set
is callPackage's, and the options are deliberately out of its reach, since it
fills in any argument it can find a package for and nixpkgs has a package
called `apostrophe`.

Or by hand, on a file rather than a package:

```sh
nix develop
python3 font/mulga_font.py --print-rules Font.ttf    # what it would do
python3 font/mulga_font.py Font.ttf -o out/
```

### What it costs

It is a font, so it applies to every language that font draws. German `schön`
comes out `schoʻn` and Turkish `çiçek` comes out `chichek`. This is a font to
set on a document written in Uzbek, not one to set as the system default.

Two glyphs also arrive where the layout expects one character, which matters
wherever the layout is a grid: in the monospaced faces `ş` advances exactly two
cells, and a terminal that has allotted it one will draw it over the character
after it. The mono faces are patched for completeness; the proportional ones
are the ones to use.

The base font has to carry the letters. ş, ç and ö are in almost everything,
since Turkish and German are; ǧ (U+01E7) is not -- IBM Plex Sans has no glyph
for it. A shaper faced with that decomposes the letter into g and a combining
caron before any font rule runs, and the patch catches that shape too, so ǧ
still draws as gʻ. Where a font is missing a letter outright the rule is
skipped rather than the font refused, and `--print-rules` says which.

## Development

```sh
nix develop           # clang-tools, cmake, fcitx5 headers, fontTools
nix build .#mulga     # builds the addon and runs the unit tests
nix build .#mim       # stages the .mim
nix build .#font      # patches every DejaVu text face and shapes the corpus
nix run .#e2e         # drives real keystrokes through a private fcitx5
nix run .#keylayout   # checks the macOS layout without a Mac

python3 tools/gen_mim.py        # regenerate the .mim
python3 tools/gen_keylayout.py  # regenerate the macOS layout
```

| | |
| --- | --- |
| `spec/corpus.tsv` | what you type, and what you should get. Every input target is held to it |
| `fcitx5-addon/` | the C++ engine and its unit tests |
| `m17n/uz-Mulga.mim` | the same alphabet as a declarative table. Generated |
| `macos/UzbekMulga.keylayout` | and again as a macOS layout. Generated |
| `macos/cldr/` | the published U.S. layout the macOS base is built from |
| `font/` | the same alphabet undone again, as an OpenType feature |
| `tools/` | the two generators |
| `test/e2e/` | drives both Linux routes through a real fcitx5 |
| `test/keylayout/` | implements the macOS state machine and runs the corpus |

Both generated files are checked in, so nothing has to be run to use the
project; the generators exist so that tables nobody wants to maintain by hand
stay honest as the rules change. `m17n/uz-Mulga.mim` needs generating because
fcitx5-m17n names an incoming key three different ways and a rule has to exist
for each; `macos/UzbekMulga.keylayout` because it carries a whole U.S. layout
underneath the four rules.

`fcitx5-addon/src/rules.{h,cpp}` holds the alphabet reform and the keystroke
state machine and deliberately includes no fcitx headers, so
`fcitx5-addon/test/test_rules.cpp` drives exactly the same code the input
method does. `fcitx5-addon/src/mulga.cpp` is the fcitx engine wrapped around
it.

`nix run .#e2e` goes further: it starts fcitx5 with both input methods on a
throwaway D-Bus session and its own config, sends key events over the D-Bus
frontend and checks what a client would receive — once per input method, so the
two routes are held to the same corpus. It needs no display and does not
disturb the fcitx5 you are running.

`font/test_font.py` holds the same corpus read backwards -- what the input
methods fold, the font unfolds -- and checks it by shaping the text through the
patched font with HarfBuzz rather than by reading the tables back, because what
is being claimed is about what a reader sees. Lookups in the wrong order and a
context that never fires both produce a font that inspects perfectly well; one
of them was how the capitals were wrong the first time.

That harness is worth the trouble: it caught the addon committing a held
character twice on focus out (`ming` → `mingg`), which happens because fcitx
commits the client preedit itself before calling `deactivate`. Neither the unit
tests nor reading the code had found it.

### What is and is not checked on macOS

Nobody here has a Mac, so `nix run .#keylayout` stands in for one. It implements
the `.keylayout` state machine and runs the shared corpus through it, taking
which key produces which character from the CLDR data and what then happens
from the generated file, so it is not the generator marking its own homework.
It confirms:

- the corpus, 21 of 24 rows, the other three being untypeable on a U.S. keyboard
- that all 392 cells of the U.S. base layer still say exactly what CLDR says
- that the 53 accent dead keys inherited from the U.S. layout still work
- that every action referenced exists, every state has a terminator, and every
  action is reachable from `none`

What it cannot confirm, and what to look at first if something is wrong:

- that macOS resolves an unmatched state the way this assumes — terminator
  first, then the key retried in state `none`. Everything rests on this. If it
  is wrong, a held `s` would vanish instead of being released
- the keys CLDR does not describe: Return, Tab, Escape, the arrows, the keypad
  and the function keys. Their values here are conventional, not published
- how the held letter is displayed while it waits, which is macOS's own marked
  text behaviour
- that the modifier map selects correctly on real hardware — in particular that
  Cmd-C and friends still reach the application

## Getting this to other platforms

Every platform can express these rules; what differs is whether it takes them
as data or wants compiled code, and what the user has to install.

### What fcitx5 itself accepts

fcitx5 has three non-code backends, so the C++ addon in this repo is one option
among several rather than the only way:

| Backend | Format | Compile step | Notes |
| --- | --- | --- | --- |
| `fcitx5-m17n` | m17n `.mim`, S-expression text | none | the same file works under ibus and SCIM |
| `table` (libime) | `.txt` → `.main.dict` | `libime_tabledict` | needs `AutoSelect` and `NoMatchAutoSelectLength=1` to commit without a candidate window, and every key has to be enumerated |
| `fcitx5-rime` | Rime schema YAML | none | candidate-oriented and heavy for four rules |

`.mim` is the one that fits. `latn-post.mim`, already in m17n-db, is built the
same way we are:

```lisp
("O'" "Ó")    ("o'" "ó")
("O''" "O'")  ("o''" "o'")   ; doubling the modifier types it literally
```

That second line is the escape hatch this repo's addon lacks: with a rule like
`("chh" "ch")`, typing `s c h h o o l` gives `school` instead of `sçool`. It is
the convention Vietnamese Telex already uses, so it is familiar rather than
novel. `uz-kbd.mim` (Cyrillic) also already ships in m17n-db, which is both a
precedent and a route upstream.

### Every platform

Bold is the native route, the one that puts the keyboard in the operating
system's own input picker rather than inside a third-party app.

| Platform | Framework | Format | Data or code | What it costs to ship |
| --- | --- | --- | --- | --- |
| Linux | **ibus** (GNOME default) | `.mim`, ibus-table, Rime, `.kmp` | data | nothing |
| Linux | **fcitx5** | `.mim`, libime table, Rime, C++ addon | either | nothing |
| Linux | XKB + `~/.XCompose` | compose sequences | data | nothing, but the semantics are awkward |
| Windows | **TSF** | C++ COM DLL | code | EV certificate |
| Windows | **MSKLC layout** | `.klc` → DLL | data in, binary out | admin install, SmartScreen warning while unsigned |
| Windows | Keyman | `.kmn` → `.kmp` | data | nothing; SIL signs the host app |
| Windows | Weasel (Rime) | Rime YAML | data | nothing |
| macOS | **`.keylayout`** | XML state machine in a bundle | data | nothing: no signing, no notarisation, no admin |
| macOS | **InputMethodKit** | Swift/Obj-C `.app` | code | Apple Developer account and notarisation |
| macOS | Keyman | `.kmp` | data | nothing |
| macOS | Squirrel (Rime) | Rime YAML | data | nothing |
| iOS | keyboard extension | Swift app | code | App Store review |
| iOS | Keyman app | `.kmp` | data | nothing |
| Android | InputMethodService | Kotlin app | code | Play Store |
| Android | Keyman app | `.kmp` | data | nothing |
| Web | KeymanWeb | `.kmn` compiled to JS | data | nothing, but only inside the page that embeds it |

### Reach, by format

No format is universal. In order of how far one file gets you:

1. **Keyman `.kmn`** — Windows, macOS, Linux, iOS, Android and web. The only
   one that spans desktop and mobile. Requires the Keyman host app on every
   platform, which is a second install for the user.
2. **m17n `.mim`** — one file, every Linux framework at once.
3. **Rime schema** — Windows, macOS and Linux desktop; no mobile.
4. **CLDR LDML keyboard XML** — the standards-track interchange format. Nothing
   consumes it directly, but it is the sensible thing to generate the others
   from, and the long-term route into the layouts operating system vendors ship
   themselves.

The fcitx5 rows, the `.mim` rule shape, the libime table options and the
existing `uz-kbd.mim` were checked against nixpkgs. The Windows, macOS and
mobile rows are not verified here.
