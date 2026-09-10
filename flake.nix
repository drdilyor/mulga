{
  description = "Input methods for the reformed Uzbek Latin alphabet";
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
  };
  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = nixpkgs.legacyPackages.${system};
  in
  {
    devShells.${system}.default = pkgs.mkShell {
      inputsFrom = [ self.packages.${system}.mulga ];
      nativeBuildInputs = with pkgs; [
        clang-tools
        cmake
        # For font/: fontTools patches the fonts, uharfbuzz shapes text back
        # through them to check what a reader would see.
        (python3.withPackages (ps: with ps; [ fonttools uharfbuzz ]))
      ];
    };

    # `mulga.lib.patchFont pkgs { font = pkgs.iosevka; }` -- the font patcher
    # against the caller's nixpkgs rather than the one this flake pins. What
    # it takes is documented at the top of font/default.nix.
    lib.patchFont = pkgs: pkgs.callPackage ./font { };

    apps.${system} = {
      e2e = {
        type = "app";
        program = "${self.packages.${system}.e2e}/bin/mulga-e2e";
      };
      keylayout = {
        type = "app";
        program = "${self.packages.${system}.keylayout-check}/bin/mulga-keylayout-check";
      };
    };

    packages.${system} = rec {
      default = mulga;

      # The fcitx5 engine, written in C++.
      # extra-cmake-modules only exists under kdePackages now that KDE Gear 5
      # has been dropped from nixpkgs.
      mulga = pkgs.callPackage (
        { stdenv
        , cmake
        , extra-cmake-modules
        , pkg-config
        , gettext
        , zstd
        , fcitx5
        }:
          stdenv.mkDerivation {
            pname = "fcitx5-mulga";
            version = "0.1.0";
            src = ./fcitx5-addon;
            nativeBuildInputs = [
              cmake
              extra-cmake-modules
              pkg-config
              gettext
              zstd
            ];
            buildInputs = [
              fcitx5
            ];
            doCheck = true;
          }
        ) {
          inherit (pkgs.kdePackages) extra-cmake-modules;
        };

      # The same alphabet as an m17n input method. Needs no compilation: point
      # M17NDIR at this directory, or copy the file into ~/.m17n.d.
      mim = pkgs.runCommand "mulga-m17n" { } ''
        mkdir -p $out/share/m17n
        cp ${./m17n/uz-Mulga.mim} $out/share/m17n/uz-Mulga.mim
      '';

      # Fonts that draw the reformed alphabet in the old digraph spelling --
      # the opposite of what the input methods do, and at the opposite end.
      # The text stays reformed; only the picture of it says sh, ch, oʻ, gʻ.
      #
      # `font/default.nix` will do this to any font package; DejaVu is the
      # one built here because it carries all four letters across every text
      # face. Building it runs the shaping tests over every face that comes
      # out.
      font = pkgs.callPackage ./font { } {
        font = pkgs.dejavu_fonts;
        # A maths font, not a text one: nothing to read in it.
        exclude = [ "MathTeXGyre" ];
      };

      # A fcitx5 carrying both routes -- the C++ addon and fcitx5-m17n -- for
      # trying them without touching the system profile.
      fcitx5-with-mulga = pkgs.kdePackages.fcitx5-with-addons.override {
        addons = [ mulga pkgs.fcitx5-m17n ];
      };

      # The macOS layout, and the checker that stands in for a Mac: it
      # implements the .keylayout state machine and runs the same corpus
      # through it. `nix run .#keylayout`.
      keylayout-check =
        let
          # Staged with the same shape as the checkout, because the checker
          # locates the layout, the CLDR data and the corpus relative to itself.
          files = pkgs.runCommand "mulga-keylayout-files" { } ''
            mkdir -p $out/macos $out/spec $out/test/keylayout
            cp ${./macos/UzbekMulga.keylayout} $out/macos/UzbekMulga.keylayout
            # Copied as a directory: a nix store path may not be named with a
            # leading underscore, which _platform.xml would need.
            cp -r ${./macos/cldr} $out/macos/cldr
            cp ${./spec/corpus.tsv} $out/spec/corpus.tsv
            cp ${./test/keylayout/simulate.py} $out/test/keylayout/simulate.py
          '';
        in
        pkgs.writeShellApplication {
          name = "mulga-keylayout-check";
          runtimeInputs = [ pkgs.python3 ];
          text = ''exec python3 ${files}/test/keylayout/simulate.py'';
        };

      # `nix run .#e2e` -- starts that fcitx5 on a throwaway D-Bus session and
      # types at it over the D-Bus frontend, once per input method, so both
      # routes are exercised for real without a display or a GUI app.
      e2e =
        let
          files = pkgs.runCommand "mulga-e2e-files" { } ''
            mkdir -p $out/m17n
            cp ${./test/e2e/run.sh} $out/run.sh
            cp ${./test/e2e/drive.py} $out/drive.py
            cp ${./m17n/uz-Mulga.mim} $out/m17n/uz-Mulga.mim
            cp ${./spec/corpus.tsv} $out/corpus.tsv
            chmod +x $out/run.sh
          '';
          python = pkgs.python3.withPackages (ps: [ ps.dbus-python ps.pygobject3 ]);
        in
        pkgs.writeShellApplication {
          name = "mulga-e2e";
          runtimeInputs = [ pkgs.dbus python fcitx5-with-mulga ];
          text = ''
            status=0
            echo "== fcitx5 addon (C++) =="
            sh ${files}/run.sh mulga || status=1
            echo
            echo "== m17n .mim =="
            sh ${files}/run.sh m17n_uz_Mulga || status=1
            exit "$status"
          '';
        };
    };
  };
}
