#!/usr/bin/env python3
"""
X6200 band-scope display patch: recolors each band's row0 to show a real
CW / DATA / BAKEN / Voice sub-band breakdown (IARU Region 1 style band plan)
instead of one flat "in-band" color, WITHOUT inserting any new code.

This is a superset of, and a drop-in replacement for, the "Bandplan Display
Patch" one directory up: it patches the same global NOP/color-table
groundwork from scratch (against the clean stock binary), so apply ONE of
the two scripts, not both.

How it works, in one sentence: every band's XBandMapItem already carries up
to 4 separate region-map lists (one per row of the original US-license-class
overlay this device ships with -- see the "Bandplan Display Patch" writeup
for that mechanism). Rows 1-3 are normally hidden; this script re-enables
them and repurposes their entries as extra, independently-colored/edged
segments merged into row0, instead of leaving them hidden or letting them
resurrect the old US-license colors. Every literal this script touches is
either a plain literal-pool word or one hop in a short chain of `add`/`sub`
immediates the compiler emits for a handful of bands -- no new instructions
are inserted anywhere.

Targets exactly: x6200_ui_v100, UI app version 1.0.7,
MD5 (unmodified) = a08ab13189bececa9995d3d19bc14c94

Full background, methodology, per-band literal maps and the reasoning
behind every patch below: see README.md in this directory.

This script ONLY changes the band-scope bar. It does not touch
isTxEnable()/isHamBand() or the fullband-tx setting in
/etc/xgradio/xgradio.conf -- TX behavior is unaffected.

Usage:
    python3 apply_bandplan_subdivision_patch.py <input_file> <output_file>

Example:
    python3 apply_bandplan_subdivision_patch.py x6200_ui_v100 x6200_ui_v100.patched

The script verifies the input file's MD5 before writing anything, and
verifies every patch's expected "old" value at its offset before changing
it. Any mismatch aborts immediately without touching the output file.

-------------------------------------------------------------------------
Adapting this to a different national band plan
-------------------------------------------------------------------------
The values below implement the Austrian (OeVSV) band plan, which follows
IARU Region 1 recommendations closely for every HF band except 60 m (60 m
allocations vary enormously by country -- narrow-band-only in some,
full-privilege in others). If your administration's edges differ:

  - Bands patched via a *plain literal swap* (60m's edges, and every
    "-> index N" color-only change) are trivial to retarget: just change
    the target Hz value or color index in the tuple below.
  - Bands patched via a *chain* (marked "chain" in the section header --
    20m, 15m, 6m) require re-deriving the chain's immediates for your
    target boundaries. See README.md's "Methodology" section for the
    register-tracing technique and the ARM-modified-immediate constraints
    that make this non-trivial (not every 32-bit delta is a legal ARM
    immediate in 1-2 instructions). Get this wrong and the script's own
    "expected old value" check will simply refuse to apply your patch
    against a clean binary, so there's no risk of silently corrupting
    something -- but a wrong *chain* value can silently produce the wrong
    boundary on-screen (right MD5, wrong Hz), so re-verify with a re-
    emulation pass (or at minimum a real device screenshot) before trusting
    a modified chain patch.
"""
import struct
import sys
import hashlib

EXPECTED_MD5 = "a08ab13189bececa9995d3d19bc14c94"
LOAD_BASE_VADDR = 0x10000  # single PT_LOAD segment: file_offset = vaddr - 0x10000

# Each entry: (vaddr, expected_old_value, new_value, description)
PATCHES = [
    # =========================================================================
    # Global setup
    # =========================================================================

    # XBandScope::paintEvent() calls drawRegionMap() 4x per band (rows 0-3,
    # list offsets +0x60/+0x68/+0x64/+0x6c). Row 2 (+0x64) is the only one
    # NOP'd here -- rows 0, 1 and 3 are all left drawing (row 1 and row 3
    # carry real per-band detail once repurposed below; every band's native
    # row 1/row 3 entries that AREN'T repurposed are individually neutralized
    # to color index 6 instead, so re-enabling the row doesn't resurrect the
    # old US-license-class colors anywhere).
    (0xee53c, 0xebfff94d, 0xe1a00000, "paintEvent: drawRegionMap call (row 2) -> NOP"),

    # Color table: XBandPlan::regionMapColor(), a 7-entry uint32 ARGB array.
    # displayed(R,G,B) = (table.Alpha, table.Red, table.Green) due to a
    # channel-mixup bug in the caller -- see the "Bandplan Display Patch"
    # writeup one directory up for the full analysis of this bug. Final
    # convention used throughout this script:
    #   0 = Yellow       -> Voice/Phone
    #   1 = mint green   -> "everything else" (6m's R&D allocation only)
    #   2 = light blue   -> CW
    #   3 = Red          -> BAKEN (beacons)
    #   4 = Gray         -> merged/mixed zone, not a single mode
    #   5 = Green        -> DATA
    #   6 = black         -> blank / out-of-band (blends into background)
    (0x111254, 0xffffff00, 0x00000000, "color table index 6 -> displays black (blends into background)"),
    (0x111244, 0x0000ff00, 0x64c8ff00, "color table index 2 -> displays light blue (was dark blue; better contrast against the black background)"),
    (0x11124c, 0xff00ff00, 0xa0a0a000, "color table index 4 -> displays gray (was Magenta, previously unused)"),
    # Index 1 (stock Orange) is repainted to a distinct mint/spring green
    # (0,255,170) rather than left Orange: DATA (index 5) is already
    # maximum-saturation pure green (0,255,0), so 6m's R&D allocation --
    # the only band that still uses index 1 after every other native index-1
    # entry below is either neutralized or moved to index 0 -- needed a
    # different hue, not just a brighter shade of the same color, to read as
    # visually distinct from both DATA and from Voice/AllMode next to it.
    (0x111240, 0xff7f0000, 0x00ffaa00, "color table index 1 -> displays mint/spring green (was Orange)"),

    # =========================================================================
    # 40m: 3 segments -- CW 7.000-7.040, DATA 7.040-7.053, Voice 7.053-7.200.
    # Plain literals throughout, no chains. 7.200-7.300 (outside the IARU-R1
    # 40m allocation) is left with NO region-map entry covering it at all:
    # paintEvent() fills the whole band-scope bar with plain black before
    # drawing any segments, so an uncovered range simply shows the
    # background -- no explicit "blank" entry needed, just make sure nothing
    # else still claims that territory (the 0x91744 patch below).
    # =========================================================================
    (0x9173c, 7124999, 7039999,
     "40m: CW high edge -> 7.039999 (DATA's low is a native +1-off-the-same-literal "
     "chain, so it follows automatically to 7.040000)"),
    (0x91750, 0xe3a02003, 0xe3a02002, "40m: CW segment color -> index 2 (light blue)"),
    (0x91c00, 7174999, 7052999, "40m: DATA high edge -> 7.052999"),
    (0x919cc, 0xe3a02006, 0xe3a02005, "40m: DATA segment color -> index 5 (Green)"),
    (0x919d8, 0xe2840038, 0xe2840034, "40m: DATA entry append target row2(+0x38) -> row0(+0x34) redirect"),
    (0x91c08, 7175000, 7053000, "40m: Voice low edge -> 7.053000"),
    (0x91a00, 0xe3a02002, 0xe3a02000, "40m: Voice segment color -> index 0 (Yellow)"),
    (0x91a1c, 0xe2840038, 0xe2840034, "40m: Voice entry append target row2(+0x38) -> row0(+0x34) redirect"),
    # This literal (native 7.300, the band's physical/display end) is shared
    # by 3 entries -- Voice plus two others that are already harmless (a
    # row0-native leftover drawn *before*, and fully overpainted by, Voice/
    # DATA; and a row1 entry that stays invisible since row1's other 40m
    # entries are neutralized below). All 3 simply shrink together.
    (0x91744, 7300000, 7199999, "40m: Voice high edge -> 7.199999 (true 40m allocation limit)"),
    (0x918b0, 0xe3a02003, 0xe3a02006, "40m row1: neutralize color -> index 6 (blank)"),
    (0x918ec, 0xe3a02001, 0xe3a02006, "40m row1: neutralize color -> index 6 (blank)"),
    (0x91a44, 0xe3a02005, 0xe3a02006, "40m row3: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 80m: CW 3.500-3.570, DATA 3.570-3.620, Voice 3.620-3.800, blank
    # 3.800-4.000 (the non-ham 75m broadcast portion). Plain literals; the
    # original row0-native "CW+DATA merged" entry is neutralized since CW and
    # DATA both get independent entries redirected from row1 instead.
    # =========================================================================
    (0x91258, 3599999, 3619999, "80m: CW+DATA-merged native entry high -> 3.620000 (still feeds DATA's high below)"),
    (0x91024, 0xe3a02003, 0xe3a02006, "80m: CW+DATA-merged native entry -> neutralized, index 6 (superseded by the independent CW+DATA entries below)"),
    (0x91260, 3600000, 3620000, "80m: Voice low edge -> 3.620000"),
    (0x91070, 0xe1a02008, 0xe3a02000,
     "80m: Voice segment color -> index 0 (Yellow) -- was a register copy "
     "(mov r2,r8), replaced with a direct immediate"),
    (0x910b0, 0xe3a02001, 0xe3a02006, "80m: blank (75m broadcast) segment color -> index 6"),
    (0x91274, 3524999, 3569999, "80m: CW high edge -> 3.569999 (row1 entry, independent literal, redirected into row0)"),
    (0x91198, 0xe3a02006, 0xe3a02002, "80m: CW segment color -> index 2 (light blue)"),
    (0x911b8, 0xe288003c, 0xe2880034, "80m: CW entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    # DATA's high is the SAME literal already patched above (0x91258) --
    # inherits 3.620000 automatically, landing exactly on the Voice boundary
    # with zero gap or overlap; no separate patch needed for DATA's high.
    (0x91278, 3525000, 3570000, "80m: DATA low edge -> 3.570000 (row1 entry, independent literal, redirected into row0)"),
    (0x9128c, 0xe3a02003, 0xe3a02005, "80m: DATA segment color -> index 5 (Green)"),
    (0x912b8, 0xe283003c, 0xe2830034, "80m: DATA entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    (0x91330, 0xe3a02001, 0xe3a02006, "80m row1: neutralize color -> index 6 (blank)"),
    (0x91490, 0xe3a02005, 0xe3a02006, "80m row3: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 160m: infeasible for a boundary split -- all 3 native region-map
    # entries (row0/row1/row2) share not just a literal *address* but the
    # same runtime *register value* for their edges, so no independent
    # second boundary can exist without inserting new code. Recolored from
    # the misleading native Yellow (would mean "Voice" in this convention)
    # to Gray, "merged/mixed, not a single mode".
    # =========================================================================
    (0x90e60, 0xe1a02005, 0xe3a02004,
     "160m: row0 (only visible entry) color -> index 4 (Gray) -- was a "
     "register copy (mov r2,r5), replaced with a direct immediate"),
    (0x90f18, 0xe3a02001, 0xe3a02006, "160m row1: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 20m: full CW/DATA/BAKEN/Voice breakdown, all 4 segments in row0.
    # (chain) CW's high is computed at runtime via 2 chained `sub`
    # immediates off the same literal BAKEN's low is patched from below, not
    # an independent literal -- see README.md's "Methodology" section for
    # how this was traced and how the replacement immediate was derived
    # (0x1e800 -> 0x7100, combined with the untouched second sub's 0x49
    # gives a total subtraction of 29,001: 14,099,000 - 29,001 = 14,069,999).
    # All 4 entries are built into a temp list and bulk-copied via a single
    # QList<XBandRegionMap>::operator=() call (20m's construction pattern
    # differs from every other band here, which append per-entry) -- the
    # bulk copy's target-offset instruction is flipped from row1(+0x3c) to
    # row0(+0x34) in ONE patch, moving all 4 entries together.
    #
    # Literal map (each loaded exactly once in the whole constructor):
    #   0x920a0 = 14,000,000  band start (anchor, untouched) -- CW low
    #   0x920a4 = 14,149,999  DATA high (shared with row0-native entry1, now neutralized)
    #   0x920a8 = 14,150,000  BAKEN low (shared with row0-native entry2, now neutralized) -- also the root of CW-high's sub-chain
    #   0x920ac = 14,350,000  band top (anchor, untouched) -- Voice high
    #   0x920b4 = 14,025,000  DATA low (independent)
    #   0x92068 = 14,174,999  BAKEN high (independent)
    #   0x92070 = 14,175,000  Voice low (independent)
    # =========================================================================
    (0x920a4, 14149999, 14098999, "20m: DATA high edge -> 14.098999"),
    (0x920a8, 14150000, 14099000, "20m: BAKEN low edge -> 14.099000 (also feeds the CW-high sub-chain)"),
    (0x920b4, 14025000, 14070000, "20m: DATA low edge -> 14.070000"),
    (0x92068, 14174999, 14111999, "20m: BAKEN high edge -> 14.111999"),
    (0x92070, 14175000, 14112000, "20m: Voice low edge -> 14.112000"),
    (0x91cf8, 0xe3a02003, 0xe3a02006, "20m: row0 native entry1 -> neutralized, index 6"),
    (0x91d3c, 0xe1a02008, 0xe3a02006,
     "20m: row0 native entry2 -> neutralized, index 6 -- was a register copy "
     "(mov r2,r8), replaced with a direct immediate"),
    (0x91e18, 0xe3a02006, 0xe3a02002, "20m: CW segment color -> index 2 (light blue)"),
    (0x91e54, 0xe3a02003, 0xe3a02005, "20m: DATA segment color -> index 5 (Green)"),
    (0x91ea8, 0xe3a02006, 0xe3a02003, "20m: BAKEN segment color -> index 3 (Red)"),
    (0x91ed4, 0xe3a02001, 0xe3a02000, "20m: Voice segment color -> index 0 (Yellow)"),
    (0x91df0, 0xe24aab7a, 0xe24aac71,
     "20m: CW-high sub-chain, 1st immediate 0x1e800 -> 0x7100 (combined with "
     "the unchanged 2nd sub's 0x49: 14,099,000 - 29,001 = 14,069,999)"),
    (0x91f04, 0xe280003c, 0xe2800034,
     "20m: bulk row1->row0 redirect (QList<XBandRegionMap>::operator=() "
     "target-offset instruction, moves all 4 entries into row0 at once)"),

    # =========================================================================
    # 17m: only ONE internal boundary exists anywhere in this band -- row0,
    # row1 and row2 all read the same 2 literals. A full CW/DATA/BAKEN/Voice
    # split isn't achievable without inserting new code. The one available
    # boundary is moved to the band's true CW+DATA+BAKEN/Voice split (18.120)
    # instead of the wrong native US-license boundary (18.100). entry2's low
    # is a native +1-off-entry1's-high chain, follows automatically.
    # Colored Gray (not light blue) since this is CW+DATA+BAKEN merged, not
    # pure CW -- coloring it the same as a real independent-CW band would be
    # misleading.
    # =========================================================================
    (0x920bc, 18099999, 18119999, "17m: merged-segment (CW+DATA+BAKEN) high -> 18.119999 (Voice low follows via native +1 chain to 18.120000)"),
    (0x9215c, 0xe3a02003, 0xe3a02004, "17m: merged-segment color -> index 4 (Gray)"),
    (0x92250, 0xe3a02003, 0xe3a02006, "17m row1: neutralize color -> index 6 (blank)"),
    (0x92290, 0xe3a02001, 0xe3a02006, "17m row1: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 15m: full CW/DATA/BAKEN/Voice breakdown, all in row0 -- same technique
    # as 20m, but per-entry row1->row0 redirects (15m appends each entry
    # individually rather than using 20m's bulk-copy construction).
    # (chain) DATA's low is computed via 2 chained `sub` immediates off the
    # same literal BAKEN's low is patched from below (0x2a800 -> 0x13400,
    # combined with the 2nd sub's 0x398 -> 0x98: total subtraction 79,000,
    # 21,149,000 - 79,000 = 21,070,000).
    #
    # Literal map (each independent unless noted):
    #   0x9277c = 21,024,999  CW high
    #   0x9276c = 21,199,999  DATA high (shared with row0-native entry1, now neutralized)
    #   0x92770 = 21,200,000  BAKEN low (shared with row0-native entry2, now neutralized) -- also the root of DATA-low's sub-chain
    #   0x92748 = 21,224,999  BAKEN high
    #   0x92750 = 21,225,000  Voice low
    # =========================================================================
    (0x9277c, 21024999, 21069999, "15m: CW high edge -> 21.069999"),
    (0x9276c, 21199999, 21148999, "15m: DATA high edge -> 21.148999"),
    (0x92770, 21200000, 21149000, "15m: BAKEN low edge -> 21.149000 (also feeds the DATA-low sub-chain)"),
    (0x92748, 21224999, 21150999, "15m: BAKEN high edge -> 21.150999"),
    (0x92750, 21225000, 21151000, "15m: Voice low edge -> 21.151000"),
    (0x92534, 0xe24bbbaa, 0xe24bbb4d, "15m: DATA-low sub-chain, 1st immediate 0x2a800 -> 0x13400"),
    (0x9254c, 0xe24bbfe6, 0xe24bb098, "15m: DATA-low sub-chain, 2nd immediate 0x398 -> 0x98 (combined total 79,000: 21,149,000 - 79,000 = 21,070,000)"),
    (0x923f8, 0xe3a02003, 0xe3a02006, "15m: row0 native entry1 -> neutralized, index 6"),
    (0x9242c, 0xe1a02005, 0xe3a02006,
     "15m: row0 native entry2 -> neutralized, index 6 -- was a register copy "
     "(mov r2,r5), replaced with a direct immediate"),
    (0x92508, 0xe3a02006, 0xe3a02002, "15m: CW segment color -> index 2 (light blue)"),
    (0x92554, 0xe3a02003, 0xe3a02005, "15m: DATA segment color -> index 5 (Green)"),
    (0x925a0, 0xe3a02006, 0xe3a02003, "15m: BAKEN segment color -> index 3 (Red)"),
    (0x925c8, 0xe3a02001, 0xe3a02000, "15m: Voice segment color -> index 0 (Yellow)"),
    (0x92520, 0xe287003c, 0xe2870034, "15m: CW entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    (0x92568, 0xe287003c, 0xe2870034, "15m: DATA entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    (0x925ac, 0xe287003c, 0xe2870034, "15m: BAKEN entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    (0x925f8, 0xe283003c, 0xe2830034, "15m: Voice entry append target row1(+0x3c) -> row0(+0x34) redirect"),
    (0x92790, 0xe3a02005, 0xe3a02006, "15m row3: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 12m: same situation as 17m -- only ONE internal boundary exists across
    # all 3 rows. Moved to the true split (24.940) instead of the wrong
    # native US-license boundary (24.930). Colored Gray, same reasoning.
    # =========================================================================
    (0x92bec, 24929999, 24939999, "12m: merged-segment (CW+DATA+BAKEN) high -> 24.939999"),
    (0x92bf0, 24930000, 24940000, "12m: Voice low edge -> 24.940000"),
    (0x9287c, 0xe3a02003, 0xe3a02004, "12m: merged-segment color -> index 4 (Gray)"),
    (0x9298c, 0xe3a02003, 0xe3a02006, "12m row1: neutralize color -> index 6 (blank)"),
    (0x929d0, 0xe3a02001, 0xe3a02006, "12m row1: neutralize color -> index 6 (blank)"),

    # =========================================================================
    # 10m: partial fix, same technique as 17m/12m -- only 1 independent
    # internal boundary across row0/row1/row2 (target needs 6 for the full
    # 7-segment CW/DATA/BAKEN/Voice/SAT/transition/FM breakdown). Moved to
    # the true Voice start (28.225) instead of the wrong native 28.300.
    # A 3rd real segment is recovered from row3 (see below), which only has
    # native entries in 4 bands total (80m, 40m, 15m, 10m) -- a much smaller
    # audit surface than row1.
    # =========================================================================
    (0x92c08, 28299999, 28224999, "10m: merged-segment (CW+DATA+BAKEN) high -> 28.224999 (Voice low follows via native +1 chain to 28.225000)"),
    (0x92b38, 0xe3a02003, 0xe3a02004, "10m: merged-segment color -> index 4 (Gray)"),
    (0x92ca0, 0xe3a02003, 0xe3a02006, "10m row1: neutralize color -> index 6 (blank)"),
    (0x92ce0, 0xe3a02001, 0xe3a02006, "10m row1: neutralize color -> index 6 (blank)"),
    # row3 entry1 duplicates the native entry1's literals exactly -- neutralized.
    # row3 entry2's low is the same native +1-chain value as entry2's low
    # above, so it already follows the merged-segment fix to 28,225,000;
    # only its high needs patching to carve out a standalone Voice segment.
    (0x92d9c, 0xe3a02003, 0xe3a02006, "10m row3: neutralize color -> index 6 (blank) (redundant duplicate of native entry1)"),
    (0x92b74, 0xe1a0200a, 0xe3a02004,
     "10m: native entry2 -> index 4 (Gray, SAT+transition+FM merged) -- was "
     "a register copy (mov r2,sl), replaced with a direct immediate"),
    (0x92c18, 28500000, 28999999, "10m: row3 entry2 high edge -> 28.999999 (Voice high)"),
    (0x92de0, 0xe3a02002, 0xe3a02000, "10m: row3 entry2 color -> index 0 (Yellow, Voice)"),
    (0x92df8, 0xe2840040, 0xe2840034, "10m: row3 entry2 append target row3(+0x40) -> row0(+0x34) redirect"),

    # =========================================================================
    # 30m: exactly ONE region-map entry in the entire band -- no row1, row2,
    # or row3 data at all. A CW/DATA split (10.100-10.130 / 10.130-10.150)
    # is not achievable without inserting new code. Color-only fix: the
    # stock Red (would mean "BAKEN" in this convention) is doubly
    # misleading since 30m has none -- recolored to Gray.
    # =========================================================================
    (0x91b34, 0xe3a02003, 0xe3a02004, "30m: single entry (CW+DATA merged) color -> index 4 (Gray)"),

    # =========================================================================
    # 60m: same root limitation as 30m -- exactly ONE region-map entry in
    # the entire band, no row1/2/3 data at all. A 3-segment split (CW / all
    # modes / narrow weak-signal, per most national IARU-R1-based charts) is
    # not achievable without inserting new code.
    #
    # *** CHECK YOUR OWN ADMINISTRATION'S 60m ALLOCATION BEFORE USING THESE
    # *** EDGES -- 60m privileges vary enormously by country (some are
    # *** narrow-band-only, some full-privilege, some don't have the band at
    # *** all). The values below are the Austrian/OeVSV edges (5,351,500 -
    # *** 5,366,500 Hz); the native stock edges (5,332,000-5,405,000 Hz) are
    # *** neither -- they don't correspond to any real 60m allocation we
    # *** could identify and were simply wrong (caught by comparing an
    # *** on-device screenshot against the real chart).
    #
    # Color-only would not have been enough here -- fixed both the color
    # (stock Blue reads as "pure CW", misleading since most of the band's
    # width is actually "all modes") and the edges.
    # =========================================================================
    (0x9172c, 5332000, 5351500, "60m: low literal -> true legal edge 5.3515 MHz (CHECK for your country)"),
    (0x91730, 5405000, 5366500, "60m: high literal -> true legal edge 5.3665 MHz (CHECK for your country)"),
    (0x91574, 0xe3a02002, 0xe3a02004, "60m: single entry (CW+all-modes+weak-signal merged) color -> index 4 (Gray)"),

    # =========================================================================
    # 6m: full BAKEN/CW/Voice/DATA/BAKEN/VoiceAM/R&D breakdown, 7 segments,
    # using all 8 native row0 slots. Voice/AllMode (50.500-52.000) is
    # deliberately split across 2 contiguous, identically-colored segments
    # (N6+N7, rendering as one seamless block) rather than 1 -- see
    # README.md's "Methodology" section for why (short version: two of the
    # required jumps are exactly 1,500,000 Hz, which has no valid
    # 2-instruction ARM-modified-immediate decomposition; splitting the
    # segment turns each into a 4-instruction hop with a decomposition that
    # does exist).
    #
    # 8 native row0 segments and what feeds each field (chain):
    #   N1 low=fp (literal, unchanged)   high=sb (literal)
    #   N2 low=sl (literal, reload)      high=r8 (literal, reload)
    #   N3 low=sl (literal, 2nd reload)  high=r8 (chain hop1 from N2)
    #   N4 low=fp (chain hopFP from N1)  high=r8 (chain hop2 from N3, untouched -- already correct)
    #   N5 low=sl (chain hopA from N3)   high=r8 (chain hop3 from N4)
    #   N6 low=sl (chain hopB from N5)   high=r8 (chain hop4 from N5)
    #   N7 low=sl (chain hopC from N6)   high=r8 (chain hop5 from N6)
    #   N8 low=sl (chain hopD from N7)   high=r8 (literal, unchanged)
    # N1's low (0x93220=50,000,000) and N8's high (0x93234=54,000,000)
    # already match the target exactly -- no patch needed for either.
    # =========================================================================
    (0x93224, 0x02fc771f, 0x02fb65af, "6m N1 high literal: 50.099999 -> 50.029999 (BAKEN/CW split)"),
    (0x93228, 0x02fc7720, 0x02fb65b0, "6m N2 low literal: 50.100000 -> 50.030000 (BAKEN/CW split)"),
    (0x9322c, 0x0304183f, 0x02fc771f, "6m N2 high literal: 50.599999 -> 50.099999 (CW/Voice boundary)"),
    (0x93230, 0x03041840, 0x02fc7720, "6m N3 low literal: 50.600000 -> 50.100000 (CW/Voice boundary)"),
    (0x92f44, 0xe2888a61, 0xe2888d05, "6m hop1a (r8, N2high->N3high): +320"),
    (0x92f4c, 0xe2888d2a, 0xe2888bc3, "6m hop1b (r8, N2high->N3high): +199680 [total +200000 -> 50.299999]"),
    # hop2 (0x92f94/0x92f98, N3high->N4high) already needs +100000, same as
    # native -- untouched.
    (0x92fdc, 0xe2888a61, 0xe2888e2a, "6m hop3a (r8, N4high->N5high): +672"),
    (0x92fe4, 0xe2888d2a, 0xe2888b61, "6m hop3b (r8, N4high->N5high): +99328 [total +100000 -> 50.499999]"),
    (0x93028, 0xe2888b61, 0xe2888e1b, "6m hop4a (r8, N5high->N6high): +432"),
    (0x93030, 0xe2888e2a, 0xe2888ab7, "6m hop4b (r8, N5high->N6high): +749568 [N6 high, internal VoiceAM split point]"),
    (0x93074, 0xe2888a61, 0xe2888e1b, "6m hop5a (r8, N6high->N7high): +432"),
    (0x9307c, 0xe2888d2a, 0xe2888ab7, "6m hop5b (r8, N6high->N7high): +749568 [total N5->N7 +1500000 -> 51.999999]"),
    (0x92f8c, 0xe28bb93d, 0xe28bbe3e, "6m hopFPa (fp, N1low->N4low): +992"),
    (0x92fa4, 0xe28bbd09, 0xe28bba49, "6m hopFPb (fp, N1low->N4low): +299008 [total +300000 -> 50.300000]"),
    (0x92fd4, 0xe28aaa7a, 0xe28aae3e, "6m hopAa (sl, N3low->N5low): +992"),
    (0x92fe0, 0xe28aae12, 0xe28aaa49, "6m hopAb (sl, N3low->N5low): +299008 [total +300000 -> 50.400000]"),
    (0x93020, 0xe28aaa61, 0xe28aae2a, "6m hopBa (sl, N5low->N6low): +672"),
    (0x9302c, 0xe28aad2a, 0xe28aab61, "6m hopBb (sl, N5low->N6low): +99328 [total +100000 -> 50.500000, VoiceAM start]"),
    (0x9306c, 0xe28aab61, 0xe28aae1b, "6m hopCa (sl, N6low->N7low): +432"),
    (0x93078, 0xe28aae2a, 0xe28aaab7, "6m hopCb (sl, N6low->N7low): +749568 [N7 low, internal VoiceAM split point]"),
    (0x930b8, 0xe28aaa61, 0xe28aae1b, "6m hopDa (sl, N7low->N8low): +432"),
    (0x930c8, 0xe28aad2a, 0xe28aaab7, "6m hopDb (sl, N7low->N8low): +749568 [total N6->N8 +1500000 -> 52.000000]"),
    # Colors: N1(BAKEN=3), N3(Voice=0), N4(DATA=5) already carry the right
    # native color -- untouched. Voice/AllMode uses the same Yellow as every
    # other Voice segment (it reads as Voice-family on the chart); only R&D
    # (a genuinely different allocation) gets the distinct mint-green color.
    (0x92f0c, 0xe3a02005, 0xe3a02002, "6m N2 color: Green -> Blue (CW)"),
    (0x92ff4, 0xe1a02009, 0xe3a02003,
     "6m N5 color: mov r2,sb(=0) -> mov r2,3 (Red/BAKEN), register copy replaced with direct immediate"),
    (0x93040, 0xe3a02004, 0xe3a02000, "6m N6 color: Gray -> Yellow (VoiceAM part 1)"),
    (0x9308c, 0xe1a02009, 0xe3a02000,
     "6m N7 color: mov r2,sb(=0) -> mov r2,0 (Yellow), register copy replaced with direct immediate (VoiceAM part 2)"),
    (0x930d0, 0xe3a02004, 0xe3a02001, "6m N8 color: Gray -> mint green (R&D)"),
    (0x93188, 0xe3a02003, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x931d0, 0xe3a02005, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x93254, 0xe1a02009, 0xe3a02006,
     "6m row1: neutralize color -> index 6 (blank) -- was a register copy (mov r2,sb/r9), replaced with a direct immediate"),
    (0x932a4, 0xe3a02005, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x932e0, 0xe3a02001, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x93328, 0xe3a02004, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x93370, 0xe3a02001, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
    (0x933c0, 0xe3a02001, 0xe3a02006, "6m row1: neutralize color -> index 6 (blank)"),
]


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    infile, outfile = sys.argv[1], sys.argv[2]

    with open(infile, "rb") as f:
        data = bytearray(f.read())

    actual_md5 = hashlib.md5(data).hexdigest()
    if actual_md5 != EXPECTED_MD5:
        print("ABORTED: input file MD5 does not match.")
        print(f"  expected: {EXPECTED_MD5}")
        print(f"  found:    {actual_md5}")
        print("This script's byte offsets were verified only against UI app")
        print("version 1.0.7 with the exact hash above. Applying it to a")
        print("different build could crash the app or corrupt unrelated code.")
        print("Do not proceed unless you have redone the analysis for your")
        print("exact binary (see README.md's methodology section).")
        sys.exit(2)

    print(f"MD5 verified: {actual_md5}")
    print(f"Applying {len(PATCHES)} patches...\n")

    for vaddr, expect_old, new, label in PATCHES:
        off = vaddr - LOAD_BASE_VADDR
        old = struct.unpack_from("<I", data, off)[0]
        if old != expect_old:
            print(f"ABORTED at '{label}': offset {hex(off)} expected "
                  f"{hex(expect_old)}, found {hex(old)}.")
            sys.exit(3)
        struct.pack_into("<I", data, off, new)
        print(f"  OK  {label}")

    with open(outfile, "wb") as f:
        f.write(data)

    print(f"\nDone. Patched file written to: {outfile}")
    print(f"MD5 of patched file: {hashlib.md5(data).hexdigest()}")


if __name__ == "__main__":
    main()
