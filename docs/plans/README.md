# avideo — Milestones

This folder holds the build plans for avideo. The specification ([spec.md](../spec.md), [spec-cli.md](../spec-cli.md), [spec-web.md](../spec-web.md)) describes the complete product. These documents decide **what is built, in which order**.

---

## How planning works

- **This file is the roadmap.** It lists the milestones, their order and scope, and which milestone covers each part of the spec. It is the only document that looks further ahead than the current milestone.
- **One detailed plan per milestone**, in `mNN-<name>.md`, written **just in time**:
  - The plan for a milestone is written only after the previous milestone is finished. Detailed plans for later milestones are not written in advance.
  - Why: every milestone turns up problems and lessons, such as library quirks, performance findings, design changes and spec corrections. A plan written after that starts from the real code, not from guesses that have gone stale.
- **At the end of each milestone:**
  1. its plan's *Learnings* section is filled in
  2. this roadmap is updated (status, scope moved between milestones, new risks)
  3. the next milestone's plan is written
- **The spec stays the source of truth.** When implementation shows the spec is wrong or unclear, the spec is fixed in the same change and the plan lists it under *Spec updates*.

### Decision log

| Date | Decision |
|---|---|
| 2026-11-12 | Build order: the heatmap goes through every layer first (core → CLI → speed → web). The other tools follow. |
| 2026-11-12 | 10 milestones (M1–M10) after the environment setup (M0). |
| 2026-11-12 | Detailed plans are written just in time, one milestone at a time, after the previous one is done (see above). |

---

## Status

| # | Milestone | Status | Plan |
|---|---|---|---|
| M0 | Development environment | done | — (commit `3dec363`) |
| M1 | Foundations and `info` | planned | [m01-foundations.md](m01-foundations.md) |
| M2 | Heatmap engine | not started | written after M1 |
| M3 | CLI run experience | not started | written after M2 |
| M4 | Real-world footage and speed | not started | written after M3 |
| M5 | Web foundation | not started | written after M4 |
| M6 | Web heatmap tuning | not started | written after M5 |
| M7 | Sessions, export/import and app polish | not started | written after M6 |
| M8 | Tools I: timeline, scenes, background, stats, barcode, contact sheet | not started | written after M7 |
| M9 | Tools II: flow, flicker, compare | not started | written after M8 |
| M10 | Report and release | not started | written after M9 |

---

## Order and dependencies

```
M0 ─► M1 ─► M2 ─► M3 ─► M4 ─► M5 ─► M6 ─► M7 ─► M8 ─► M9 ─► M10
              │                        │
              └──── core parts of M8/M9 only need M2 ───┘ their web pages need M6
```

Why this order:

- **The heatmap is the backbone.** It uses most of the core: settings, source, pipeline stages, runner, events and outputs. Once it works in both interfaces, each remaining tool is mostly a core module plus its own views.
- **CLI before web.** The CLI is the cheapest way to settle the runner/event contract and the output formats. The web app then builds on something stable.
- **Speed before web.** The web app's full runs need parallel workers and the result cache. Doing them first means the server is written once.
- **Possible parallel work.** The core parts of M8/M9 only depend on M2. They could start earlier if work is ever run side by side.

---

## Milestones

### M1 — Foundations and `info`

**Goal:** the foundations everything else builds on, proven end to end by the first real feature, `avideo info`, in the CLI's final look.

- Core: error and warning types, value parsers, the **complete settings model for every tool**, TOML/JSON files, settings priority order, presets, user config, platform folders
- `VideoSource` with OpenCV and PyAV: metadata, time resolution, sampling, rotation, deinterlacing, resizing; quick hash
- `info` tool with all checks, including the noise estimate
- Output folder policy (for `info.json`)
- CLI: colors, theme and color-depth detection, ASCII fallback, width rules; command and flag framework; error panels and exit codes; main and command help screens; `info` screen; `config` and `presets` commands
- Synthetic test videos; snapshot testing for terminal screens

**Done when:** `avideo --help` and `avideo info` match the drafts; the spec's example settings file validates; every settings key in spec.md exists in the model with its default.

### M2 — Heatmap engine

**Goal:** the complete heatmap analysis in the core, checked against synthetic videos with known answers.

- Tool protocol and runner: events, cancellation, preview quality. The protocol is designed for every tool shape, not just the heatmap:
  - tools that read selected frames up front (background, contact sheet, Otsu `video` scope, overlay median)
  - tools that look ahead (scenes)
  - tools with two sources (compare)
- The runner runs one tool now; it is shaped so that several tools can share one decode pass in M10.
- Color spaces; pipeline stages:
  - preprocess
  - threshold (fixed, Otsu, adaptive, range; levels; hysteresis)
  - change detection (previous, frame, background average and MOG2; channel, euclidean and ΔE distances; delta and auto delta)
  - combine, cleanup (opening, minimum run), accumulate
- ROI masks and `roi_crop` (W008)
- Heatmap results, statistics and snapshots
- Rendering: colormaps, colorbar, overlay, channel composite
- Outputs:
  - run record (`<tool>_run.json`)
  - settings embedded in PNGs, and reading them back for `--config`
  - png, npy, csv, timeline.csv and settings files
  - time-lapse and rolling videos
  - replacing a tool's old files under `on_exists = overwrite`
- Validation that needs video metadata, at run start
- Single-frame stage evaluation (for the web frame inspector)
- A plain `avideo heatmap` command (generic flags, `--set`/`--config`, plain progress) to run all of this

**Done when:** exact counts on synthetic videos for every reference mode and combine mode; outputs as in spec §6.2.9; bit-identical results with `workers = 1`.

### M3 — CLI run experience

**Goal:** running an analysis in the terminal looks and behaves like the CLI drafts.

- Every heatmap flag, including the `--thresh` forms and `--outputs all`; heatmap command help
- `--save-config`, `--dry-run` (also with `--json`), `--preview`
- Live view: header, pipeline chips, half-block preview with legend, stats panel with sparkline, progress line, hint line, warnings kept in scrollback
- Finished summary: result panel, thumbnail, saved-files tree, warnings recap, next step
- Interrupt: the first ctrl+c saves partial results, the second quits immediately; exit code 130
- Non-TTY progress lines, `--no-live`, `--quiet`, `--json` run records, `--events` JSON Lines
- Batch mode: table while running, final table, `summary.csv`, exit code 6
- Tests: flag coverage, screen snapshots, `--save-config` → `--config` round trip

**Done when:** the live view, summary and batch screens match the drafts; every heatmap key is reachable from the CLI.

### M4 — Real-world footage and speed

**Goal:** handles shaky, flickering-exposure and damaged footage, and reaches the speed targets.

- Parallel chunked processing:
  - chunk plan, warmup rules, merge
  - seek verification, with fallback to sequential and W007
  - the rule that some tools always run sequentially
  - `--workers`, `--warmup`
- Result cache (LRU, `cache.max_size`), `--cache`, `avideo cache info|clear`
- Stabilization: ORB + RANSAC, translate/affine/homography, excluded border pixels, W012
- Exposure normalization (`mean`, `histogram`)
- Decode errors: skip corrupt frames, W013, E203 above 1% bad frames
- Memory estimates and W010
- Benchmarks for spec §12.5 (on demand); property tests: parallel equals sequential, chunk merging is associative

**Done when:** the heatmap meets the §12.5 speed targets (or the gap is measured and documented); the `handheld` preset works on the stabilization test video.

### M5 — Web foundation

**Goal:** open a video in the browser and watch an analysis stream live.

- Server:
  - `avideo serve`: options, PATH modes (none, folder, video), port fallback, `--allow-remote`
  - terminal banner, request log, `o`/`q` keys
- Security: token exchanged for a cookie, Host/Origin checks, file access limited to the root folder, CSP
- REST API: version, schema, preferences, file browser (list, meta, thumbnails, reveal), recent videos, workspaces, runs, frame images
- Workspaces; job manager with a process pool (one preview run and one full run per workspace)
- WebSocket: binary framing, hello/subscribe, throttling where the latest frame wins, stage images and snapshots, reconnect with `resume_seq`
- TypeScript types generated from the OpenAPI schema
- Frontend:
  - design tokens (both themes), bundled fonts, the components of spec-web §4.5
  - layout at ≥ 1280 px
  - Open screen (file browser, recent videos); workspace shell (top bar, tools sidebar, viewer column)
- WebGL2 viewer:
  - layers and colormap lookup tables
  - single, side by side, blend and wipe views; zoom and pan
  - Canvas 2D fallback
  - overlays: LIVE chip, legend, label chips
- Stage selector, transport, activity scrubber, following a run live

**Done when:** from the browser, open a synthetic video, watch a heatmap preview stream live, and switch stages and view modes; API, WebSocket and security tests pass.

### M6 — Web heatmap tuning

**Goal:** the Heatmap workspace from the drafts. You can tune settings with instant feedback, and the CLI reproduces the result exactly.

- Settings panels generated from the schema: sections, rows, control types, visibility rules, summaries, "changed from preset" dots
- Behavior classes:
  - display: in the browser, done by the shader
  - pipeline: frame inspector, or a preview restart after a short pause
  - input: also resets the scrubber
  - export: stored for exports
- Common rows: preset row (Save / Save as), Input section with ROI drawing (rectangle, polygon) and loading a mask
- The full heatmap panel (spec-web §8.3), with the color picker for the range method
- Frame inspector (while paused; the latest request wins); pixel inspector
- Validation states; reset of a control, a section or back to the preset; undo/redo kept on the server; `settings.changed` across tabs
- CLI command box: the command, Copy as `--config`, Copy TOML
- Runs and results:
  - full run, stop (graceful and hard)
  - result badges, outdated marks, cache hits
  - stat tiles
  - scrubbing through snapshots after a run, with the "Final" toggle
  - last settings remembered per video
- Frontend unit tests (Vitest): store, undo, panel generation; normalization and colormap test vectors shared with Python

**Done when:** the Heatmap workspace draft works end to end; the copied CLI command reproduces the web result bit for bit.

### M7 — Sessions, export/import and app polish

**Goal:** everything around the analysis: saving, sharing, preferences and every screen size.

- `.avideo` sessions in the core; CLI `--session` and `--video`; `avideo serve FILE.avideo` and the output-folder mode
- Export dialog: scope, items with their options, destination picker, size estimates, "Run full analysis & export", progress, reveal in file manager
- Import:
  - settings files (TOML/JSON) and avideo PNGs
  - `.npy` counts, including the result-only workspace
  - sessions, with the dialog to locate a moved video
  - the Open screen's drop zone and uploads
- Video info page with Apply buttons
- Preferences dialog, command palette, every shortcut and the `?` overlay
- Responsive layouts (960, 720 and < 720 px), light theme pass, accessibility audit (spec-web §15), all remaining states (spec-web §14)

**Done when:** the Export & import draft works; a web export run with `avideo … --config` gives identical results; sessions round-trip.

### M8 — Tools I: timeline, scenes, background, stats, barcode, contact sheet

**Goal:** the simpler tools, complete in both interfaces.

- Each tool gets:
  - its core module
  - a CLI command: flags, help, its live preview (spec-cli §6.4), its summary
  - a web page: stages, panel sections, its charts, strips and tables
- Shared pieces: canvas chart helpers, cut and peak ticks on the scrubber, matplotlib plots

**Done when:** each tool runs in both interfaces with the outputs of spec §6; tests on synthetic videos with known answers pass (cuts, black and frozen segments, background).

### M9 — Tools II: flow, flicker, compare

**Goal:** the heavy tools, complete in both interfaces.

- flow: Farnebäck, per-pixel accumulation, color-wheel legend, direction rose
- flicker: Welch FFT, memory planning (W010), per-pixel peaks, spectrum, aliasing note, pixel peak chart
- compare:
  - two sources, alignment (offset, auto)
  - PSNR, SSIM and MAD; worst frames
  - A/B view modes and the Video B picker; W011

**Done when:** synthetic tests with known answers (known motion, known blink frequency, known difference) pass in both interfaces.

### M10 — Report and release

**Goal:** the last tool, the final test layers, and a package anyone can install.

- Runner: several tools in one decode pass
- Report:
  - HTML (self-contained or with an assets folder, light/dark, works offline)
  - CLI `report` and `--open`
  - web Report page (tools checklist, iframe preview)
- Shell completion: choices, colormaps, presets, `--set` keys, video paths
- Testing:
  - Playwright end-to-end and visual regression tests
  - golden tests on real clips
  - every example in spec-cli §13 runs
- Performance checks for spec-web §13 and spec §12.5; JavaScript bundle budget
- Packaging: the wheel ships the built frontend; smoke test that installs from the wheel; README

**Done when:** a clean `pip install` of the built wheel runs every CLI example and the web app, with no Node installed.

---

## Spec coverage

Every section of the spec maps to the milestone(s) that build it. When scope moves, this table moves with it.

### spec.md (core)

| Section | Milestone |
|---|---|
| §1 Goals, §2 Glossary | all (guiding) |
| §3.1 Package layout | grows with each milestone |
| §3.2 Dependencies and packaging | M0; wheel with built frontend M10 |
| §3.3 VideoSource | M1 (stabilization and exposure M4) |
| §3.3 Tool protocol, runner, single-frame evaluation | M2; multi-tool pass M10 |
| §3.4 Determinism | M2 (sequential), M4 (parallel) |
| §4 Value types | M1 |
| §5 Common input parameters | M1 (sampling, resize, rotate, deinterlace, backend, ROI parsing); M2 (ROI masking, `roi_crop`); M4 (`stabilize`, `normalize_exposure`) |
| §6.1 info | M1 |
| §6.2 heatmap | M2 |
| §6.3–6.8 timeline, scenes, background, stats, barcode, contact | M8 |
| §6.9–6.11 flow, flicker, compare | M9 |
| §6.12 report | M10 |
| §7.1 Color spaces | M1 (gray), M2 (all) |
| §7.2–7.3, §7.6–7.9 | M2 |
| §7.4 Stabilization | M4 |
| §7.5 Automatic delta | M1 (noise σ), M2 (auto delta) |
| §8 Settings (model, priority order, file format, presets) | M1; user presets from the web M6 |
| §9.1 Output folder | M1 (folder policy), M2 (replacing a tool's files), M3 (batch `summary.csv`) |
| §9.2–9.4 File formats, run record, settings in PNGs | M2 |
| §10 Sessions | M7 |
| §11 Live events | M2 (core), M3 (CLI, `--events`), M5 (WebSocket) |
| §12.1 Streaming and memory | M2; memory warnings M4 and per tool in M8/M9 |
| §12.2 Parallel processing | M4 |
| §12.3 Preview quality | M2 (runner), M3 (`--preview`), M5 (web) |
| §12.4 Result cache | M4 |
| §12.5 Targets | M4 (benchmarks), M10 (final check) |
| §13.1 Errors | M1 (types); raised where each feature lands |
| §13.2 Warnings | M1 (registry); each raised where its feature lands |
| §13.3 Cancellation | M2 (core), M3 (CLI ctrl+c), M6 (web Stop) |
| §14 Privacy and security | M1 (no network); M5 (server) |
| §15 Testing | M1 (synthetic videos, unit tests); M2/M4 (property tests); M10 (golden tests) |
| §16 Interface coverage | M3 (heatmap), M8–M10 (other tools) |

### spec-cli.md

| Section | Milestone |
|---|---|
| §1 Principles | all |
| §2 Look and feel | M1 |
| §3.1 Commands | grows with each tool |
| §3.2 Inputs and batch mode | M1 (input expansion, several `info` inputs); M3 (batch runs, tables, `summary.csv`) |
| §3.3 Where options go | M1 |
| §4.1 Input flags | M1 |
| §4.2 Output, performance and settings flags | M1 (`-o`, `--on-exists`, `--config`, `--preset`, `--set`); M2 (`--config` with PNG); M3 (`--save-config`, `--dry-run`, `--preview`); M4 (`--workers`, `--warmup`, `--cache`); M7 (`--session`, `--video`) |
| §4.3 Interface flags | M1 (`--json`, `-q`, `-v`, `--color`, `--theme`, `--ascii`, `-r`, `--fail-fast`); M3 (`--events`, `--no-live`) |
| §5.1 info | M1 |
| §5.2 heatmap | M3 |
| §5.3–5.11 other tools | M8, M9 |
| §5.12 report | M10 |
| §5.13 serve | M5 |
| §6.1 Main help | M1 |
| §6.2 Command help | M1 (generic renderer), M3 (heatmap), M8–M10 (other tools) |
| §6.3 info screen | M1 |
| §6.4 Live view | M3; per-tool previews M8/M9; report rows M10 |
| §6.5 Finished summary, §6.6 Batch, §6.9 Interrupt | M3 |
| §6.7 Errors | M1 |
| §6.8 serve screen | M5 |
| §7.1 Streams, §7.5 Logging | M1 |
| §7.2 Not a TTY | M1 (`info`), M3 (progress lines) |
| §7.3 `--json` | M1 (`info`), M3 (runs, dry run) |
| §7.4 `--events` | M3 |
| §8.1 presets, §8.2 config | M1 |
| §8.3 cache | M4 |
| §9 Configuration sources | M1 |
| §10 Exit codes | M1 (130 for runs in M3, 6 for runs in M3) |
| §11 Shell completion | M10 |
| §12 Testing | M1 (parsing, screens); M3 (flag coverage, behavior, round trip) |
| §13 Examples | M10 (all run) |

### spec-web.md

| Section | Milestone |
|---|---|
| §1 Principles | all |
| §2 Launch | M5 (none, folder, video); M7 (output folder, `.avideo`) |
| §3.1 Server | M5 (workspaces, jobs, recent, preferences); M6 (last settings per video, presets) |
| §3.2 Frontend | M5 |
| §4 Visual design | M5; M7 (light theme pass) |
| §5 Layout | M5 (≥ 1280 px); M7 (responsive) |
| §6.1 Open screen | M5 (browser, recent); M7 (drop zone, uploads) |
| §6.2 Workspace | M5 (viewer, transport); M6 (settings panel, result badges) |
| §6.3 Tool pages | M6 (Heatmap), M7 (Video info), M8–M9 (others), M10 (Report) |
| §6.4 Export & import dialog | M7 |
| §6.5 Preferences, §6.6 Shortcuts overlay, §6.7 Command palette | M7 |
| §7.1–7.5 Viewer, view modes, overlays | M5; ROI outline and warnings banner M6 |
| §7.6 Pixel inspector | M6 |
| §7.7 Transport and scrubber | M5; ticks M8 |
| §7.8 Playback and live following | M5 (follow live); M6 (frame inspector, playback after a run) |
| §8.1–8.3, §8.5–8.6 Settings panel, heatmap controls, undo, CLI box | M6 |
| §8.4 Other tools' controls | M7 (Video info), M8–M9, M10 (Report) |
| §9 Runs and live updates | M5 (preview runs); M6 (full runs, stop, cache) |
| §10 Export and import (server) | M7 |
| §11 Keyboard shortcuts | M5 (viewer keys), M7 (all) |
| §12 API | M5 (core endpoints, WebSocket); M6 (settings, undo, cli, runs); M7 (export, import, presets); M10 (report) |
| §13 Performance budgets | M5/M6 (checked as built), M10 (final) |
| §14 States | M5 (loading, connection lost); M6 (running, outdated, partial, invalid, failed); M7 (rest) |
| §15 Accessibility | built into each milestone; M7 audit |
| §16 Security | M5 |
| §17 Testing | M5 (API, WebSocket); M6 (Vitest); M10 (Playwright, visual regression) |

---

## Definition of done

**Each step** of a plan:

- is one reviewable change with its tests
- passes `pytest`, `ruff check .`, `ruff format --check .` and `mypy`
- passes `npm run typecheck` and `npm run build` when it touches `frontend/`

**Each milestone:**

- every acceptance criterion in its plan is checked and the demo has been run
- the spec has been updated wherever the implementation changed it
- the plan's *Learnings* section is filled in
- this roadmap is updated, and the next plan is written

---

## Plan template

Every `mNN-<name>.md` has these sections:

1. **Header:** status, dependencies
2. **Goal:** one or two sentences
3. **Demo:** what can be shown at the end
4. **Scope:** spec sections covered, and what each contributes
5. **Not in this milestone:** with the milestone that does it
6. **Design decisions:** choices made up front, with reasons
7. **Module map:** files created or changed
8. **Steps:** ordered; each with what, files and tests
9. **Acceptance criteria:** a checklist
10. **Spec updates:** changes to the spec this milestone makes
11. **Risks and open questions**
12. **Learnings:** filled in when the milestone ends
