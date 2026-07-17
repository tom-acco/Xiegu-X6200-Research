# Using Claude Code for hands-on radio hacking (a working method, not a specific finding)

## Overview

- This writeup is different from the others in this folder: it's not a specific X6200 finding,
  it's the **method** behind them. Both the [base display patch](./README.md) (merged as
  [#3](https://github.com/tom-acco/Xiegu-X6200-Research/pull/3)) and the
  [CW/DATA/BAKEN/Voice subdivision](./SUBDIVISION.md) follow-up
  ([#4](https://github.com/tom-acco/Xiegu-X6200-Research/pull/4)) — were produced end-to-end
  using [Claude Code](https://claude.com/product/claude-code), Anthropic's agentic coding CLI,
  driving the actual reverse-engineering, patching, and on-device verification, not just
  writing code from a spec someone else already worked out.
- The barrier to entry is lower than it sounds. You need: root SSH access to your device (for
  the X6200, see [Get Rooted](../Get%20Rooted/README.md)), and a computer with Claude Code
  installed. Almost none of the specialist tooling — `radare2`, its Python bindings, image
  libraries for decoding raw framebuffer dumps, whatever a given task needs — has to be
  installed up front. The agent installs it on demand, the first time a task actually needs
  it, and asks before doing so.
- No jailbreak or novel exploit was involved anywhere in this project. Root SSH was already
  open by the vendor. The interesting part isn't the access — it's what becomes *possible*
  once you pair that access with an agent that can read a disassembly dump, write a throwaway
  emulation script, run a shell command against the device, and keep a written trail so the
  next session doesn't start from zero.
- **Goal of this document:** lower the barrier for other hams to point Claude Code at their
  own device or their own idea — this radio or a completely different one — instead of
  assuming this kind of work requires a dedicated embedded-reverse-engineering background.

---

## Why this approach fits this kind of problem

The X6200's UI — driven by physical buttons and a rotary encoder, not a touchscreen — is one
large, statically linked, unstripped-enough-to-be-readable
ARM32 Qt binary (`/usr/app_qt/x6200_ui_v100`), running on a closed embedded Linux system with
no vendor SDK, no source, and no public documentation of its internals. The only way to change
how it behaves is: disassemble it, form a hypothesis about what a given piece of code does,
test that hypothesis, and if it holds, patch it — carefully, with a way back if you're wrong.

That loop is exactly what an agentic coding tool is good at automating the *drudgery* of,
while leaving the judgment calls to you:

- Searching and cross-referencing a multi-thousand-instruction disassembly dump for the one
  function that matters is tedious by hand and fast for an agent with a terminal.
- Writing a one-off Python script to emulate a function in isolation (rather than reasoning
  about ARM assembly by eye) and checking its output against a hypothesis is cheap to do
  *and cheap to throw away* when the hypothesis was wrong — which happened repeatedly in this
  project (see the "channel-mixup bug" in the
  [Bandplan Display Patch README](./README.md#the-channel-mixup-bug)
  for an example that only came to light because a measured on-screen color didn't match what
  the raw table bytes implied).
- Keeping a running, precise log of "what's confirmed, what's still open, what MD5 the device
  is currently running" across many separate sessions (see below) is exactly the kind of
  bookkeeping that's easy to skip when you're doing it manually under deadline pressure, and
  that an agent can be told to just always do.

None of this replaces understanding what you're doing — every patch in this repo was designed
by working out *why* a piece of code behaves the way it does, not by asking the agent to guess.
What changes is how fast you can go from "I wonder if..." to a verified answer.

---

## Prerequisites

### On the device

- Root SSH access. For the X6200, that's [Get Rooted](../Get%20Rooted/README.md) in this
  repo — out of scope here, and device-specific for anything other than an X6200.
- A stable address to reach it at (a DHCP reservation on your router is enough; no need for
  anything fancier).

### On your computer

- [Claude Code](https://claude.com/product/claude-code) installed.
- A normal SSH client (already on macOS/Linux).
- That's genuinely it to get started. Everything below — `git`, `python3` plus a couple of
  pip packages, `radare2`, `sshfs`, `sqlite3` — got pulled in over the course of the project
  *as the work required it*, not as a prerequisite checklist:
  - `radare2` (`brew install radare2`) — only needed once static disassembly of the binary
    started (`aa`, `pdf`, `pdc` commands, or scripted via its `r2pipe` Python bindings).
  - `r2pipe` (`pip3 install r2pipe`) — once analysis moved from manually reading disassembly
    to scripted emulation (ESIL) and literal-tracing.
  - `Pillow` (`pip3 install pillow`) — once raw on-device framebuffer dumps needed decoding
    into viewable images.
  - `sshfs` (`brew install sshfs`, plus a FUSE implementation on macOS) — once editing files
    directly on the device's filesystem (NetworkManager profiles, SQLite settings DB) got
    tedious to do one `scp` at a time.
  - `git` and `sqlite3` — standard tools, already present or trivial to install.

  You don't need to pre-install any of this. When Claude Code hits a task that needs a tool
  it doesn't have, it tells you what it wants to install and why, and you approve it (or it's
  already covered by your permission settings) — same as it would for any other missing
  dependency in a normal coding session.

---

## Setting up device access

### SSH alias + key auth

Worth setting up once, in `~/.ssh/config`, so every command Claude Code runs against the
device is a plain `ssh <alias> "<command>"` instead of a long-hand invocation with an
IP address and key path repeated everywhere:

```
Host x6200
    HostName 192.168.x.x
    User root
    IdentityFile ~/.ssh/id_x6200
    ControlMaster auto
    ControlPersist 10m
```

- `IdentityFile` + a passphrase-protected key (kept in your OS keychain, e.g.
  `ssh-add --apple-use-keychain` on macOS) beats leaving a plaintext password lying around
  anywhere reachable by tooling.
- `ControlMaster`/`ControlPersist` reuse a single authenticated connection for follow-up
  commands in the same session instead of renegotiating SSH for every single `ssh x6200 "..."`
  call — this matters a lot when an agent is running many short commands back-to-back.

### SSHFS mount for direct file editing

```
sshfs x6200:/ ~/x6200-mnt -o reconnect,ServerAliveInterval=15,volname=X6200
```

Once mounted, the device's root filesystem behaves like a local directory. This is genuinely
useful for anything that's a normal text/config edit — NetworkManager connection profiles,
poking at the SQLite settings DB — because it lets Claude Code use its ordinary file-editing
tools directly against the live device instead of you shuttling files back and forth by hand.

It is **not** how binary patches to the UI app were made — those go through a Python script
that patches a local copy, gets re-verified offline, and only then gets deployed with explicit
backup + checksum steps (see below). Direct edits are fine for config; a running app's own
binary deserves a slower, more deliberate path.

---

## Give the agent a persistent project memory

An agent session doesn't remember a previous one on its own. What made this project work
across many separate sessions, spread over multiple days, was writing two files down as we
went and having Claude Code read them at the start of every session:

- **`CLAUDE.md`** (repo root) — the project's standing context: how to reach the device, what
  tools exist, what's been finished and confirmed, what's still open, and non-negotiable
  safety rules (always back up before writing to the device, always verify an MD5 before and
  after copying a binary over, don't touch git without asking first, etc.). Claude Code loads
  this automatically at the start of every session in this directory. See
  <https://docs.claude.com/en/docs/claude-code/memory> for how the mechanism works in general.
  This project's own `CLAUDE.md` is kept in German day-to-day, since that's the language the
  work actually happens in — here's an English excerpt of the parts that matter for the
  pattern itself, translated just for this writeup:

  ```markdown
  ## Device access

  The X6200 sits on Wi-Fi on the home network (DHCP reservation set, fixed IP). Root SSH
  login is enabled.

  SSH (for commands):    ssh x6200 "<command>"
  SSHFS mount (for file editing):
      sshfs x6200:/ ~/x6200-mnt -o reconnect,ServerAliveInterval=15,volname=X6200

  ## Working method

  - Edit config files directly through the SSHFS mount and test them there, instead of
    juggling individual commands over SSH.
  - Document larger findings (table dumps, binary strings, patches) in this repo as you go,
    so progress stays traceable — even without git history, the full context must be
    reconstructable from the files alone.
  - Before any destructive action (writing to /usr/app_qt/, binary patches): back up the
    original file first (`cp file file.bak.<timestamp>` on the device).
  - Before every deployment: rebuild the patch script against the clean original, verify via
    re-emulation, compare MD5 before and after copying to the device.
  - Don't forget `chmod 700` after copying the binary to the device (otherwise the app
    silently fails to start).
  ```

- **A running lab notebook** (this project's is `analysis/NOTES.md`) — a chronological log of
  what was tried, what worked, what didn't, and why, with concrete addresses/values/checksums
  rather than vague summaries. This is what let a session days later pick up a half-finished
  thread instead of re-discovering the same dead end from scratch. Same story as `CLAUDE.md`:
  kept in German for daily use, English excerpt for this writeup —

  ```markdown
  # Analysis reference (app v1.0.7)

  Quick reference for continuing the work. Full narrative writeup (already merged
  upstream): <link to the finished PR>.

  ## Files in this directory

  - `x6200_ui_v100_orig_v1.0.7` — unmodified original binary, MD5 `<hash>`. Use this as
    the base for any new patch/disassembly work.
  - `some_function_disasm.txt` — full disassembly of the relevant function, vaddr range
    noted, one-line summary of what it builds.
  - `grab_frame.py` — run on the device to grab a pixel-exact screenshot of the current
    display for verification. Output format and required rotation noted.

  ## Device state as of this entry (updated <date>)

  The live binary is running MD5 `<hash>`, built from `<n>` patches. Always `md5sum` the
  live file rather than trusting a status note — this has gone stale mid-session more than
  once. Known-good backups on the device: `<filename>` (MD5 `<hash>`, the true clean
  original), `<filename>` (leftover proof-of-concept build)...
  ```

  The literal values above are placeholders for this excerpt; the real file carries the
  project's actual hashes, filenames, and a much longer chronological log.

The discipline this buys you is worth more than it sounds: writing a finding down at the
moment you confirm it is cheap; re-deriving it two sessions later because nobody wrote it down
is not. This project even used a small extra trick for handing off directly to a next session:
a standalone `NEXT_SESSION_PROMPT.md`, written at the *end* of a session rather than trying to
reconstruct context at the start of the next one, containing exactly the prompt to paste in to
resume the specific in-progress task — something like:

```markdown
Continue the <specific patch/analysis> for <specific component> (project context is in
CLAUDE.md, read that first).

Goal: <precise target state, with the concrete values/edges/behavior expected>.

Entry point: <file>, section "<heading>" — the groundwork already done is documented
there, this isn't a blank-slate start. <tool/script> is what mapped the relevant
data/behavior last time; apply the same technique here.

Approach (proven to work, see CLAUDE.md's "Working method"):
1. ...
2. ...

Important: don't touch git (no init, no commit, no fork) without asking first.
```

That's a generic shape, not a verbatim copy of any specific one this project used — the
point is the pattern: a session ends by writing down exactly what the next one needs, instead
of counting on the next session (or the next person) to reconstruct it.

---

## The workflow that worked

Distilled from `CLAUDE.md`'s working method (which itself came out of trial and error — the
first few patch attempts skipped straight to writing to the device and cost real time and
device reboots when a hypothesis turned out wrong):

1. **Understand before you touch.** Establish *where* the relevant data or logic actually
   lives (a disassembled function, a config file, a database table) before changing anything.
   Guessing-then-checking-on-hardware is far slower than working out the mechanism first.
2. **Prototype in a scratch copy, never on the live device.** Every binary patch in this
   project started as a modification to a local file copy, not the file on the radio.
3. **Verify offline before deploying.** Re-run the modified logic (in this project's case, an
   ARM emulator) and diff the result against the unmodified baseline — including a check that
   *nothing outside the intended scope* changed. This caught several would-be regressions
   before they ever reached the device.
4. **Back up, then deploy, then check.** Before writing anything to the device: copy the
   current file aside with a timestamped name. After copying the new file: compare MD5 sums
   before and after the transfer, not just "trust the `scp` exit code." On this specific
   device, also don't forget `chmod 700` after copying the UI binary back — get that wrong and
   the app fails to start with no error message anywhere obvious.
5. **Get real confirmation, not "should work."** For a screen you're changing the appearance
   of, that means an actual on-device screenshot compared against the intent — not a phone
   photo of the LCD (viewing-angle color shifts on this display genuinely produced wrong
   conclusions early in this project) and not just "the emulator agrees," since the emulator
   is itself a model of the real thing.
6. **Document in the same step you confirm something, not "later."** A decision, a discarded
   dead end, or a gotcha that isn't written down gets rediscovered the hard way — usually by a
   future session that has no memory of having already ruled it out once.

---

## Worked example, in brief

The [Bandplan Display Patch](./README.md) is the clean end-to-end
illustration: the colored bar on the spectrum display turned out to be hardcoding the *US*
amateur-license-class system (Extra/Advanced/General/Novice-Technician), meaningless outside
the US, plus an unrelated red/green/blue channel mixup bug in the color-lookup code that made
the raw table bytes actively misleading to read by eye. Both were found by disassembling the
relevant `XBandPlan`/`XBandScope` code, confirmed by an iterative patch → deploy → pixel-exact
screenshot → compare loop, turned into a small, reviewable binary patch script, and shipped
upstream as a PR others could apply to their own X6200. The full writeup — background,
methodology, the exact patch, and how to apply it yourself — is in that file; this document is
just the "how the work itself got done" companion to it. The
[CW/DATA/BAKEN/Voice subdivision](./SUBDIVISION.md) follow-up used the
exact same loop, just applied to a harder problem (per-band CW/DATA/BAKEN/Voice sub-segments
instead of one flat color).

---

## Safety notes specific to touching a live radio over SSH

- **Always keep a tested rollback path.** A backup file sitting on the device is only useful
  if you also know the exact restore command, and ideally have exercised it once.
- **Gate any patch script against the exact firmware build it was written for** (this
  project's scripts refuse to run if the target file's MD5 doesn't match what they expect).
  A patch computed against one build silently corrupting a different build is a much worse
  failure mode than the script just refusing to run.
- **Know your recovery story before you need it.** On the X6200: no `dm-verity`/secure boot
  was found, no code signing, the UI process is supervised by `monit` and gets auto-restarted
  if it crashes, and SSH is a separate service unaffected by a broken UI binary — so a bad
  binary here is "annoying, not fatal." That is a property of *this* device, not a given;
  confirm the equivalent for whatever you're working on before you start relying on it.
- Claude Code itself asks for confirmation before genuinely destructive or hard-to-reverse
  actions as a matter of how it operates — but the *domain-specific* safety net (backups, MD5
  checks, the `chmod 700` gotcha, "don't touch git without asking") has to come from you,
  written down in `CLAUDE.md`, because the agent has no way to know those rules exist
  otherwise.

---

## Try it on your own idea

None of the above is specific to this radio. The pattern is: get a shell (or equivalent
access) on a device you own, point Claude Code at it with a `CLAUDE.md` describing how to
reach it and what the ground rules are, and use the same understand → prototype → verify →
deploy-carefully → document loop for whatever you're curious about. It doesn't have to be
binary patching — the same approach applies just as well to a misbehaving config, an
undocumented API, or a completely different piece of gear.

If it *is* an X6200 idea, [tom-acco/Xiegu-X6200-Research](https://github.com/tom-acco/Xiegu-X6200-Research)
is where X6200-specific findings are being collected — which is exactly where this document
itself lives now, as its own contribution alongside the patches it describes.
