# Faster Space Station Landing
# Builds the FOMOD installer (10x + 5x + 2x) with the AMUMSS Linux port.
#
# What it does: the game flies your ship to a landing pad on its own when you
# enter a space station or the space anomaly. It ships that flight
# slow. This raises the speed, in the dock node data and in the ship globals.
#
# Every value this mod patches lives in src/patches.tsv. That table drives
# both the rendered script and the verify step, so a value can never be
# patched without also being checked.
#
# Usage:
#   make release      clean rebuild + verify + pack dist/ zip (default)
#   make verify       sanity-check the built outputs
#   make clean        remove build/ and dist/
#
# Override the AMUMSS install location if needed:
#   make AMUMSS_HOME=/path/to/AMUMSS release
#
# Game-update playbook (see README.md):
#   1. fetch latest MBINCompiler into AMUMSS_HOME
#   2. re-derive the bases in src/patches.tsv (see README.md)
#   3. bump VERSION below (the mod version, published on Nexus)
#   4. make release, import + deploy + test in game

AMUMSS_HOME ?= $(HOME)/AMUMSS
AMUMSS_LINUX ?= $(HOME)/Git/AMUMSS/linux

# The mod version, published as the version of the Nexus release. An
# unreleased build stays at 0.0.0; the first public release bumps this in the
# same commit that publishes it. The version is deliberately not part of the
# mod name: the artifact is named after the mod alone (see FOMOD_ZIP), because
# a mod manager names the installed mod after the archive file name and shows
# the version in a column of its own.
VERSION      := 0.1.0

MOD_SET      := Faster Space Station Landing

SRC_TEMPLATE := src/landing.lua.in
SRC_TABLE    := src/patches.tsv

BUILD := build
DIST  := dist
STAMP := $(BUILD)/.built

# Installer variants, fastest first. Each variant label names the rendered
# script, the CreatedMODS folder, the fomod source folder and the in-game
# MOD_FILENAME suffix, so it must match ModuleConfig.xml exactly.
#
# Every variant scales the steering forces and the approach speed together,
# which is what keeps the turn into alignment in step with the flight to
# the pad. The window the ship has to turn in is left alone, because
# cutting it as well leaves the ship landing upside down.
#
# FastTurn is a diagnostic: it gives the turn ten times the factor of the
# flight, for the case where the turn itself is the limit.
VARIANT := 10x 5x 2x

# The scopes each variant patches, each with the factor for that group.
# The manoeuvre is shortened by the same factor as the flight, so the
# ship still finishes lining up with the pad before it touches down.
#
# 10x is the ceiling. A 100x option was built and tested and the ship did
# not land right, so it is not offered. The floor on the shortened values
# is a 20x shortening, which is above the factor that is known to work and
# well below the one that does not.
SCOPES_10x := forces:10,approach:10,bounce:10,manoeuvre:10
SCOPES_5x  := forces:5,approach:5,bounce:5,manoeuvre:5
SCOPES_2x  := forces:2,approach:2,bounce:2,manoeuvre:2

DESC_10x := 10x faster station and anomaly landing
DESC_5x  := 5x faster station and anomaly landing
DESC_2x  := 2x faster station and anomaly landing

RENDERED := $(addprefix $(BUILD)/,$(addsuffix .lua,$(VARIANT)))
EXPECTED := $(addprefix $(BUILD)/,$(addsuffix .expected.tsv,$(VARIANT)))

# clean runs before build runs before verify, so release must not be parallel.
.NOTPARALLEL:

.PHONY: all release build verify clean assets video

all: release

# The artifact is named after the mod and nothing else, for the same reason
# the mod name carries no version: the file name is what a mod manager shows
# as the mod name.
FOMOD_ZIP := $(DIST)/$(MOD_SET).zip

release: clean build verify
	@rm -rf "$(BUILD)/fomodz" && mkdir -p "$(BUILD)/fomodz/fomod" $(addprefix "$(BUILD)/fomodz/",$(VARIANT))
	@set -e; for v in $(VARIANT); do cp -a "$(BUILD)/$(MOD_SET) - $$v/." "$(BUILD)/fomodz/$$v/"; done
	@cp ModuleConfig.xml "$(BUILD)/fomodz/fomod/"
	@mkdir -p "$(DIST)" && rm -f "$(FOMOD_ZIP)" && cd "$(BUILD)/fomodz" && zip -qr "$(shell pwd)/$(FOMOD_ZIP)" fomod $(VARIANT)
	@echo "packed: $(FOMOD_ZIP) (version $(VERSION))"
	@python3 -c "import xml.dom.minidom; xml.dom.minidom.parse('$(BUILD)/fomodz/fomod/ModuleConfig.xml'); print('ModuleConfig.xml: well-formed XML')"

# Render one variant: the script and the expected values that verify checks
# the built EXML against. The guard turns a typo in VARIANT into a loud
# failure rather than a script with a blank factor.
$(BUILD)/%.lua $(BUILD)/%.expected.tsv: $(SRC_TEMPLATE) $(SRC_TABLE) src/render_mod.py
	@mkdir -p "$(BUILD)"
	@test -n "$(SCOPES_$*)" -a -n "$(DESC_$*)" || { echo "ERROR: unknown variant '$*' - add SCOPES_$* and DESC_$* to the Makefile" >&2; exit 1; }
	@python3 src/render_mod.py --variant "$*" --factor 1 --desc "$(DESC_$*)" --scopes "$(SCOPES_$*)" \
		--template "$(SRC_TEMPLATE)" --table "$(SRC_TABLE)" \
		--out-script "$(BUILD)/$*.lua" --out-expected "$(BUILD)/$*.expected.tsv"

# One pipeline run builds every variant as an individual mod.
build: $(RENDERED)
	@test -d "$(AMUMSS_HOME)/MODBUILDER" || (echo "ERROR: no AMUMSS install at $(AMUMSS_HOME) (set AMUMSS_HOME=...)" >&2; exit 1)
	@test -x "$(AMUMSS_HOME)/MODBUILDER/MBINCompiler-linux" || (echo "ERROR: run $(AMUMSS_LINUX)/scripts/fetch_mbincompiler.sh with AMUMSS_HOME=$(AMUMSS_HOME) first" >&2; exit 1)
	@mkdir -p "$(BUILD)"
	@set -e; \
	if [ -d "$(AMUMSS_HOME)/ModScript" ]; then mv "$(AMUMSS_HOME)/ModScript" "$(AMUMSS_HOME)/ModScript.makebak"; trap 'rm -rf "$(AMUMSS_HOME)/ModScript"; mv "$(AMUMSS_HOME)/ModScript.makebak" "$(AMUMSS_HOME)/ModScript"' EXIT; fi; \
	mkdir -p "$(AMUMSS_HOME)/ModScript"; \
	cp $(RENDERED) "$(AMUMSS_HOME)/ModScript/"; \
	for v in $(VARIANT); do rm -rf "$(AMUMSS_HOME)/CreatedMODS/$(MOD_SET) - $$v"; done; \
	AMUMSS_HOME="$(AMUMSS_HOME)" "$(AMUMSS_LINUX)/buildmod.sh" --run-pipeline; \
	rm -rf "$(AMUMSS_HOME)/ModScript"; \
	if [ -d "$(AMUMSS_HOME)/ModScript.makebak" ]; then mv "$(AMUMSS_HOME)/ModScript.makebak" "$(AMUMSS_HOME)/ModScript"; fi; \
	trap - EXIT
	@set -e; for v in $(VARIANT); do \
		rm -rf "$(BUILD)/$(MOD_SET) - $$v"; \
		mkdir -p "$(BUILD)/$(MOD_SET) - $$v"; \
		cp -a "$(AMUMSS_HOME)/CreatedMODS/$(MOD_SET) - $$v"/* "$(BUILD)/$(MOD_SET) - $$v/"; \
	done
	@touch "$(STAMP)"
	@echo "built: $(foreach v,$(VARIANT),$(BUILD)/$(MOD_SET) - $(v) )"

verify: build
	@for n in "$$(sed -n 's:.*<moduleName>\(.*\)</moduleName>.*:\1:p' ModuleConfig.xml)" "$(MOD_SET)"; do \
		if printf '%s' "$$n" | grep -qE '[vV]?[0-9]+(\.[0-9]+)+'; then \
			echo "ERROR: the mod name must not carry a version: '$$n'" >&2; exit 1; \
		fi; \
	done
	@python3 src/verify_build.py --build "$(BUILD)" --mod-set "$(MOD_SET)" --variants "$(VARIANT)"

# Nexus page images from the source screenshot. The generated images are
# build artifacts and are not tracked; the source screenshot and the
# typeface are.
assets: assets/src/gallery-landing.jpg assets/generate.py
	python3 assets/generate.py

# The demo video, joined from the recordings in assets/. The generated videos
# are build artifacts and are not tracked.
video:
	python3 assets/combine.py
	python3 assets/combine.py --web

clean:
	rm -rf "$(BUILD)" "$(DIST)"
