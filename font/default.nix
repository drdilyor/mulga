# default.nix -- patch a font package so that reformed Uzbek text draws in the
# old digraph spelling. See ../README.md, "Reading it the old way".
#
#   pkgs.callPackage ./font { } { font = pkgs.dejavu_fonts; }
#   pkgs.callPackage ./font { } { font = pkgs.ibm-plex; suffix = "UZ"; }
#
# Every .ttf and .otf the package installs under share/fonts is patched, so
# one call covers a whole family. They come out under share/fonts/truetype and
# share/fonts/opentype, which is where fontconfig looks and is all it cares
# about; the original layout below share/fonts is not preserved. Collections
# (.ttc) are left alone.
#
# The result is a derivative of the font it was made from and carries that
# font's licence, which is why `meta` is inherited rather than invented. Some
# licences reserve the family name and allow modification only under a
# different one -- the Bitstream Vera licence DejaVu uses reserves "Bitstream"
# and "Vera", the SIL OFL has Reserved Font Names -- so the rename that keeps
# fontconfig honest is often also the condition on which the patch is allowed
# at all. Check before redistributing something with a `suffix` you chose.
#
# The arguments come in two goes on purpose. callPackage fills in every
# argument it finds a package for, and it does that whether or not the
# argument has a default, so an option named after a package silently becomes
# that package: `apostrophe ? null` in the first set was quietly handed
# pkgs.apostrophe, the GNOME markdown editor, and the build spent a while
# fetching texlive before failing on it. Only the dependencies are in the
# first set, where being filled in is the point; the options are in the
# second, where nixpkgs cannot reach them.
{ lib
, runCommand
, python3
}:

{ font              # the font package to patch
, suffix ? "Mulga"  # appended to the family: DejaVu Sans -> DejaVu Sans Mulga
, apostrophe ? null # tutuq belgisi codepoint in hex, e.g. "2019"
, exclude ? [ ]     # faces to leave alone, as extended regular expressions
, doCheck ? true    # shape the corpus back through every patched face
}:

let
  python = python3.withPackages (ps: with ps; [ fonttools uharfbuzz ]);

  # What the patcher puts in a filename, which is how a patched face is found
  # again afterwards to check it against the one it came from.
  slug = lib.replaceStrings [ " " ] [ "" ] suffix;

  options = lib.escapeShellArgs (
    [ "--suffix" suffix ]
    ++ lib.optionals (apostrophe != null) [ "--apostrophe" apostrophe ]
  );

  filter =
    if exclude == [ ] then "cat"
    else "grep -Ev ${lib.escapeShellArg (lib.concatStringsSep "|" exclude)}";

  version = lib.getVersion font;
in
runCommand
  ("${lib.getName font}-${lib.toLower slug}"
    + lib.optionalString (version != "") "-${version}")
{
  inherit doCheck;
  nativeBuildInputs = [ python ];
  meta = (font.meta or { }) // {
    description =
      (font.meta.description or (lib.getName font))
      + ", drawing reformed Uzbek in the old digraph spelling";
  };
} ''
  base=${font}/share/fonts
  if [ ! -d "$base" ]; then
    echo "${font}: no share/fonts to patch" >&2
    exit 1
  fi

  # -L because a font package may well symlink a face in from another
  # derivation rather than hold it -- dejavu_fonts does exactly that with
  # DejaVuSans.ttf, the most used face it has -- and without following those,
  # -type f drops them without a word.
  #
  # -print0 would be tidier, but the exclude filter is a line-oriented grep.
  ttf=(); otf=()
  while IFS= read -r face; do
    case "$face" in
      *.otf|*.OTF) otf+=("$face") ;;
      *)           ttf+=("$face") ;;
    esac
  done < <(find -L "$base" -type f \( -iname '*.ttf' -o -iname '*.otf' \) |
           sort | ${filter})

  if [ ''${#ttf[@]} -eq 0 ] && [ ''${#otf[@]} -eq 0 ]; then
    echo "${font}: no .ttf or .otf under share/fonts" >&2
    exit 1
  fi

  # Pairs of patched face and the face it came from, for the checks below.
  pairs=()

  patch() {
    local dir=$1; shift
    if [ $# -eq 0 ]; then return 0; fi
    mkdir -p "$dir"
    python3 ${./mulga_font.py} ${options} "$@" -o "$dir"
    local face name patched
    for face in "$@"; do
      name=$(basename "$face")
      patched=$dir/''${name%.*}-${slug}.''${name##*.}
      # A face the patcher had to skip -- no ş, ç, ö or ǧ in it, which is
      # what a symbol font in the same package looks like -- has nothing
      # there to check.
      if [ -e "$patched" ]; then pairs+=("$patched=$face"); fi
    done
  }

  patch $out/share/fonts/truetype "''${ttf[@]}"
  patch $out/share/fonts/opentype "''${otf[@]}"

  if [ -n "$doCheck" ] && [ ''${#pairs[@]} -gt 0 ]; then
    python3 ${./test_font.py} -q "''${pairs[@]}"
  fi
''
