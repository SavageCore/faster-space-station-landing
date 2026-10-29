# Faster Space Station Landing

Speeds up the scripted flight that carries your ship to the landing pad when
you enter a space station or the space anomaly. Built natively on
Linux with the
[AMUMSS Linux port](https://github.com/SavageCore/AMUMSS/tree/feat/linux-support).

## Usage

Install it and pick how much faster the landing is.

| Option | Factor | Patches |
| --- | --- | --- |
| `10x` | 10x | every value below |
| `5x` | 5x | every value below |
| `2x` | 2x | every value below |

The factor is applied to every base value in `src/patches.tsv`, so one number
scales the whole mod. 10x is the ceiling: past that the ship no longer
lands right.

It cannot remove the sequence itself, only compress it. The docking camera
cut and the "INITIATING DOCKING PROCEDURE" banner still fire.

## What it patches

The game hands your ship to a dock node when you enter a station or the
anomaly, and flies it to a landing pad on its own. The flight
has several parts, and the game ships them all slow.

| Part | Where | What it governs |
| --- | --- | --- |
| the flight | `GcOutpostComponentData.ApproachSpeed` in each dock node | how fast the ship flies along the approach to the pad |
| the turn | `OutpostDock*Force` in `GCAISPACESHIPGLOBALS` | how fast the ship turns into alignment on the way in |
| the manoeuvre | the `DockingLandingTime`, `DockingRotateStartTime` and `LandingManuevre*` values | how long the ship spends lining up with the pad |
| the touchdown | the `DockingSpringTime` and `DockingLandingBounce*` values | how long the ship takes to settle onto the pad |

The factor scales all of it together, which is what keeps the parts in
step. The ship lines up with the pad in a manoeuvre of fixed length, so a
faster flight only stays upright if the manoeuvre is shortened by the same
factor. Speeding up the flight alone leaves the ship arriving at the pad
while it is still turning, and it lands upside down.

Two things are left alone on purpose. The descent speed, because a faster
descent shortens the same window the manoeuvre has to fit in. And the tip
geometry, because raising the length of the tip or the angle the ship may
tip up to makes it fly on past the pad and over rotate.

Every value lives in `src/patches.tsv`, which is also what `make verify`
checks the build against. A value cannot be patched without also being
checked, and the two cannot drift apart.

## Compatibility

Modifies `GCAISPACESHIPGLOBALS.GLOBAL.MBIN` and the six dock entity files of
the space stations and the anomaly. Nothing else.

It does not touch `GCSPACESHIPGLOBALS.GLOBAL.MBIN` at all, so it has no
file in common with
[Faster Spaceship Docking Rotation Reloaded](https://www.nexusmods.com/nomanssky/mods/4569)
and the two cannot fight over it. The docking rotation is a different phase
again, where the ship turns to line up with the pad, and that knob belongs
to the rotation mod.

[Auto Eject on Landing](https://www.nexusmods.com/nomanssky/mods/3689) is
not needed by this mod, but the demo video shows the landing with it.

The entity files live in `NMSARC.Precache.pak`, the globals file in
`NMSARC.globals.pak`.

The dock node and shared ship settings changes also apply to NPC ships
docking, so station traffic moves faster too.

## Build (on Linux)

Requires a full AMUMSS install at `~/AMUMSS` (override with
`AMUMSS_HOME=...`) with `MBINCompiler-linux` fetched
(`linux/scripts/fetch_mbincompiler.sh` in the AMUMSS repo).

```sh
make release      # clean rebuild + verify + pack dist/ zip (default)
make verify       # sanity-check the built outputs
make clean        # remove build/ and dist/

make assets                  # regenerate the Nexus page images
```

`make build` clears this mod's folders out of
`$(AMUMSS_HOME)/CreatedMODS`, temporarily stages the variant scripts into
`$(AMUMSS_HOME)/ModScript` (existing content moved aside and restored), runs one
`buildmod.sh --run-pipeline`, and collects the outputs.

`make assets` rebuilds the two Nexus page images from the source screenshot
in `assets/src`. The generated images are build artifacts and are not
tracked; the screenshot and the typeface are.

### The demo video

`assets/combine.py` joins the six landing recordings into one video with
the speed and the case labelled on every segment, and a timer that starts
when the game takes the ship over and ends when the ship is down.

```sh
python3 assets/combine.py            # lossless master, 2560x1440, a couple of GB, for upload
```

Both ends of the timer are found in the footage rather than by hand. The
start is the frame the game prints "Initiating landing sequence" across the
screen. It is told apart from the scene behind it by the number of bright
runs in the band it sits in: a line of glyphs makes hundreds of runs, a lit
wall makes a few. The message fades in, so the timer starts once the text
has faded halfway in, which is the same point in every recording. The end
is the cut to black that the game plays once the ship is down and the pilot
is put out.

The video is re-encoded losslessly by default, so it is bit identical to the
recordings apart from the overlay. The audio is re-encoded, because the
segments have to be joined and the sources are AAC.

### `make verify` is the load-bearing step

For every variant and every patched file it asserts that the EXML was
produced by *this* run, that each expected property carries the expected
value, that the patch touches nothing else, and that there are no marker
tags.

The freshness check exists because of how AMUMSS fails: a change that stops
matching does not error, it silently applies nothing, creates no file, and
leaves the previous build's file sitting in `CreatedMODS`. The copy then
succeeds and every other check happily validates last week's output.

## Release

`make release` creates `dist/Faster Space Station Landing.zip`. It is a FOMOD
installer: `fomod/` sits at the zip root, which is how mod managers detect an
installer, and each option is a folder beside it. Import it into
[Amethyst](https://github.com/ChrisDKN/Amethyst-Mod-Manager)/[Vortex](https://github.com/Nexus-Mods/Vortex)
or upload it to Nexus. For a manual install, copy the folder for the option you want into `GAMEDATA/MODS`.

The zip is named after the mod and carries no version, because a mod manager
names the installed mod after the archive file name and shows the version in a
column of its own. The version travels as the version of the Nexus release
instead.

## Game updates / versioning

The mod version is `VERSION` in the `Makefile`. The game version the script
targets is `GameVersion` in `src/landing.lua.in`.

When No Man's Sky updates:

1. Fetch the new matching compiler from the AMUMSS repo (use
   `MBINCOMPILER_TAG=vX` to pin):
   `AMUMSS_HOME=~/AMUMSS linux/scripts/fetch_mbincompiler.sh`
   If the AMUMSS core itself changed, re-run the pipeline once so the
   linux patches re-verify (`apply_linux_patches.sh --verify`).
2. Re-derive the bases in `src/patches.tsv` (see below).
3. Bump `GameVersion` in `src/landing.lua.in` and `VERSION` in the `Makefile`.
4. `make release`, install, test.

### Re-deriving the bases

The base values are game data, not constants this mod owns. To re-derive them:

```sh
PAK=~/.local/share/Steam/steamapps/common/"No Man's Sky"/GAMEDATA/PCBANKS/NMSARC.Precache.pak
hgpaktool -O /tmp/probe -f "*spacestation/modularparts/entities/*" -f "*spacestation/spacestation/entities/*" \
  -f "*spacestation/spacestationtypeb/entities/*" -f "*nexus/nexus/entities/*" \
  -f "*nexus/nexusexterior/entities/*" "$PAK"

GLOBALS=~/.local/share/Steam/steamapps/common/"No Man's Sky"/GAMEDATA/PCBANKS/NMSARC.globals.pak
hgpaktool -O /tmp/probe -f "GCSPACESHIPGLOBALS.GLOBAL.MBIN" -f "GCAISPACESHIPGLOBALS.GLOBAL.MBIN" "$GLOBALS"
```

Then decompile each MBIN with `MBINCompiler-linux` and read the values in
`GcOutpostComponentData` (`ApproachSpeed`) and in the shared ship globals
(the `OutpostDock*Force`, `Docking*` and `LandingManuevre*` values). Update
the `BASE` column in `src/patches.tsv` to match. If a property is renamed,
`make verify` fails on the missing property rather than shipping a patch
that does nothing.
