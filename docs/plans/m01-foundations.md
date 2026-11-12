# M1 — Foundations and `info`

**Status:** planned · **Depends on:** M0 (development environment) · **Next:** the M2 plan is written when this milestone is done ([roadmap](README.md)).

---

## 1. Goal

Build the foundations every later milestone stands on: errors, value types, the complete settings system and video decoding. Prove them end to end with the first real feature, `avideo info`, shown in the CLI's final look and feel.

## 2. Demo

```bash
avideo                                  # main help: wordmark, command panels, common options
avideo info clip.mp4                    # info panel with checks, warnings and tips
avideo info videos/ --json              # one JSON line per video
avideo info clip.mp4 -o out/            # also writes out/clip/info.json
avideo info clpi.mp4                    # error panel: "Did you mean clip.mp4?", exit code 3
avideo info clip.mp4 --set heatmap.change.dleta=4   # error panel: did you mean heatmap.change.delta, exit 2
avideo config show heatmap              # every heatmap key with help text and allowed values
avideo config check street-cam.toml     # the spec §8.3 example passes
avideo presets list
NO_COLOR=1 avideo --help                # same layout, no color
avideo --ascii info clip.mp4            # ASCII fallback
```

## 3. Scope

| Spec section | What M1 builds |
|---|---|
| spec.md §4 | All value types: Time, Duration, Scale, ROI, ChannelList, Color, Choice |
| spec.md §5 | `start`, `end`, `step`, `max_frames`, `resize`, `rotate`, `deinterlace`, `backend` applied by the source; ROI parsed (masking is M2); `stabilize` and `normalize_exposure` exist in the settings only (M4) |
| spec.md §6.1 | `info` tool: every reported field and every check |
| spec.md §7.1 | `gray` conversion only |
| spec.md §7.5 | Noise σ estimate (steps 1–3); the `auto_delta` formula (step 4) |
| spec.md §8 | Complete settings model for **all** tools; settings priority order; TOML/JSON format; built-in and user presets; user config file |
| spec.md §9.1 | Output folder policy (`<root>/<stem>/`, `on_exists`) |
| spec.md §13.1–13.2 | Error classes and codes; warning registry and collector |
| spec.md §14 | No network access anywhere (nothing in M1 needs it) |
| spec.md §15 | Synthetic test videos; unit tests per parser |
| spec-cli.md §2 | Color tokens, theme detection, color depth, glyphs and ASCII fallback, typography and width rules |
| spec-cli.md §3 | Command structure, input expansion (files, globs, folders, `--recursive`), options before or after inputs |
| spec-cli.md §4 | Input flags; `-o`, `--on-exists`, `-c/--config`, `-p/--preset`, `--set`; interface flags (`--json`, `-q`, `-v/-vv`, `--color`, `--theme`, `--ascii`, `-r`, `--continue-on-error/--fail-fast`) |
| spec-cli.md §5.1 | `avideo info` |
| spec-cli.md §6.1–6.3, §6.7 | Main help, generic command help, info screen, error panels |
| spec-cli.md §7.1–7.3, §7.5 | Streams, non-TTY output, `--json` for `info`, logging |
| spec-cli.md §8.1–8.2, §9, §10 | `presets` and `config` commands, configuration sources, exit codes |

## 4. Not in this milestone

| Item | Where |
|---|---|
| Tool protocol, runner, live events, cancellation | M2 |
| ROI masks, `roi_crop`, W008 | M2 |
| Color spaces other than gray; auto delta used in a run | M2 |
| Run record, PNG writing, and reading PNG settings for `--config` | M2 |
| Validation that needs video metadata (`end > start`, `max_hz ≤ fps/2`, times inside the video) | M2 |
| `--save-config`, `--dry-run`, `--preview`, `--events`, `--no-live`; live view; batch `summary.csv` | M3 |
| Stabilization, exposure normalization, skipping corrupt frames (W013), seek verification for OpenCV | M4 |
| `--workers`, `--warmup`, `--cache`, `avideo cache` | M4 |
| `avideo serve` beyond the existing development stub | M5 |
| `--session`, `--video` | M7 |
| Shell completion beyond what Typer gives for free | M10 |

## 5. Design decisions

**D1 — The complete settings model is built now, for all 12 tools.**
- Settings are the contract between both interfaces. M1 features already need keys from tools that are not built yet:
  - presets set heatmap keys
  - `config check` must accept any section
  - `config show heatmap` must work
  - unknown sections must be errors
- The model is pure data plus validation, so building it early costs little.
- A spec-sync test (D9) keeps it identical to the spec.

**D2 — `avideo.core.settings` is a package, not a single module.** It holds about 120 parameters plus file I/O, layers and presets, which is too much for one file. The import path the spec names (`avideo.core.settings`) stays the same. The spec §3.1 tree is updated.

**D3 — Settings are combined as sparse layers.**
- Each source (defaults, user config, environment, preset, each `--config` file, `--set`, flags) is a `Layer`: a nested dict of only the values that source set explicitly, plus a label for error messages.
- Layers are merged from lowest to highest priority and validated once.
- Keeping layers sparse gives several features for free: "non-default values only" exports, `--save-config`, presets, the CLI command box, and the web app's "changed from preset" marks.
- **Tool input overrides** (spec §8.2, "at the same level"):
  - within one layer, `[<tool>.input]` beats `[input]`
  - a higher layer's `input.X` clears `<tool>.input.X` set by lower layers
  - so `--resize 50%` on the command line beats `[flicker.input] resize = "25%"` from a config file, while the same file's `[input] resize` would not

**D4 — Commands come from a declarative flag table.**
- Each analysis command is built from `FlagSpec` rows (flag names → settings key, metavar, help section) into a Click command, and added to the Typer app's group.
- Typer stays the app shell: the root callback, the manage subcommands, `--version` and completion.
- Why: about 150 flags map one-to-one to settings keys. Three things then read the same table:
  - the help screens
  - the flag-coverage test (spec-cli §12)
  - the flags → settings conversion
- Writing 150 Typer function parameters by hand would duplicate all of that.
- Step 12 starts with a spike to confirm this works with the installed Typer/Click.

**D5 — Metadata comes from the chosen backend.**
- PyAV gives every field in spec §6.1.
- OpenCV gives fewer: size, fps, frame count, codec FourCC and rotation where exposed.
- Missing values are `None` and shown as `—`. No backend mixing.

**D6 — Frame operations run in an equivalent, cheaper order.**
- The spec's order is decode → rotate → deinterlace → sample → resize. Rotation and deinterlacing are per-frame and stateless, so the source samples first and only rotates, deinterlaces and resizes the frames it keeps.
- The result is identical. Tests compare against the spec's order on a fixture.

**D7 — Deinterlacing is a vertical [1, 2, 1] / 4 blend.** Each output line mixes itself with its neighbors from the other field. That is the "simple blend" the spec names. The spec is updated with the exact filter.

**D8 — Synthetic test videos are written with PyAV as lossless FFV1 in MKV.**
- They use an RGB pixel format (`bgr0`/`gbrp`), so both backends decode exactly the same pixels with no YUV conversion differences.
- Frames encode their own index as a block pattern, so tests can read back exactly which source frame they received.
- One lossy H.264 4:2:0 clip covers W003 and "normal" files.

**D9 — Spec-sync tests.**
- A test parses the parameter tables in `docs/spec.md` and checks:
  - every key there exists in the model, and the other way round
  - defaults match wherever the spec default is a literal
  - non-literal defaults (`start of video`, `file name`, `see above`) are in an explicit allowlist with a reason
- A second test checks behavior classes against the spec-web §8.1 table.

**D10 — Help lists only commands that exist.** The main help is generated from the command registry, so it grows as milestones add commands. Snapshot files are updated with each new command.

**D11 — `info` does not implement the Tool protocol yet.** The protocol is designed in M2. `info` is a plain function returning an `InfoResult`. M2 decides whether to wrap it.

**D12 — Relative paths inside a settings file resolve against that file's folder** (for example `input.roi = "roi.png"`). On the command line they resolve against the current folder.

**D13 — Where small helpers live.**
- Luma conversion goes in `core/colorspaces.py`.
- Noise estimation goes in `core/pipeline/change.py`, where spec §7.5 belongs.
- Each module starts with only what M1 needs; M2 fills them.

**D14 — Units for the Size type.** `cache.max_size` is parsed by a new Size type: `2GB`, `500MB`, or plain bytes. KB/MB/GB are 1024-based, the same as the CLI's size display. Spec §4 is updated.

## 6. Module map

Created (or rewritten) in this milestone. Nothing else is scaffolded.

```
src/avideo/core/
  errors.py              error classes, warning registry, collector, did-you-mean
  values.py              Time, Duration, Scale, ROI, ChannelList, Color, Size
  paths.py               config / data / cache folders per platform (new; spec tree updated)
  settings/
    __init__.py          public API
    base.py              param() helper, value-type annotations, introspection
    models.py            every section of every tool
    layers.py            Layer, merge, resolve, --set parsing, diff from defaults
    io.py                TOML/JSON load and dump
    presets.py           built-in and user presets, user config file
  colorspaces.py         gray only (rest in M2)
  pipeline/
    __init__.py
    change.py            noise estimate and auto delta only (rest in M2)
  source.py              VideoMeta, backends, sampling, quick hash
  outputs.py             output folder policy, JSON writer (rest in M2)
  tools/
    __init__.py
    info.py
src/avideo/cli/
  app.py                 rewritten: root app, registration, error boundary
  console.py             tokens, theme, color depth, glyphs, width, the UI context
  format.py              numbers, times, sizes
  commands.py            CommandSpec registry, Click command builder
  flags.py               FlagSpec table, flags → settings layers
  inputs.py              input expansion, file suggestions
  errors.py              error panels, exit codes
  help.py                main help, command help
  info.py                `avideo info`
  manage.py              `avideo config …`, `avideo presets …`
tests/
  conftest.py            fixtures, --update-snapshots option
  synth.py               synthetic video writer and frame patterns
  snapshots.py           terminal snapshot helper
  snapshots/             stored .txt / .svg snapshots
  core/test_*.py
  cli/test_*.py
```

`pyproject.toml` changes: the `pydantic.mypy` plugin, pytest `pythonpath = ["tests"]` (so tests can import `synth` and `snapshots`), and a `slow` marker.

---

## 7. Steps

Each step is one reviewable change with its tests (see the [definition of done](README.md#definition-of-done)).

### Part A — Core

#### Step 1 — Errors and warnings

- `core/errors.py`:
  - `AvideoError(Exception)` with `code`, `title`, `message`, `suggestion` and `details` (a dict such as `key`, `value`, `allowed`).
  - One subclass per spec §13.1 row with a fixed code: `InvalidSettings` E100, `InvalidValue` E101, `InputNotFound` E200, `InputUnreadable` E201, `UnsupportedFormat` E202, `DecodeError` E203, `OutputError` E300, `OutputExists` E301, `IncompatibleOptions` E400, `InternalError` E500.
  - `InvalidSettings` carries a list of issues (`key`, `value`, `message`, `allowed`, `suggestion`, `source`), so one run reports every bad key at once.
  - `WARNINGS`: the registry of W001–W013, each with code, title and tip text exactly as spec §13.2.
  - `AvideoWarning(code, message, details, count)`. `WarningCollector.add(code, message, **details)` deduplicates by code, counts repeats, keeps the first message, and iterates in the order warnings were first raised.
  - `suggest(word, candidates)`: the shared did-you-mean helper (difflib, cutoff ≈ 0.6).
- **Tests:** codes unique and matching the spec, collector dedup and counts, suggestions.

#### Step 2 — Value types

- `core/values.py`: frozen dataclasses.
  - Each has `parse(raw)` (accepts strings and numbers, and arrays where lists are allowed).
  - `__str__` returns canonical text that parses back to an equal value. TOML stores this text, which makes round-trips lossless.
  - **Time:**
    - kinds `seconds`, `timecode`, `frame`, `percent`
    - `MM:SS(.f)` and `HH:MM:SS(.f)`, with minutes and seconds below 60; `f<N>`; `N%` (0–100)
    - `seconds(fps, duration)` and `frame(fps, duration)` resolve it. Timestamp-based resolution for VFR lives in the source.
  - **Duration:**
    - units `s`, `ms`, `f`; a plain number means seconds
    - a sign is allowed; field constraints decide where negatives are valid (`compare.offset`)
    - `seconds(fps)` and `frames(fps)`
  - **Scale:**
    - forms: percent, factor, `WxH`, `Wx`, `xH`
    - `apply(w, h)` rounds to whole pixels (at least 1); `upscales(w, h)` reports upscaling
  - **ROI:**
    - `Rect(x, y, w, h)`, `Polygon(points ≥ 3)` or `MaskPath(path)`
    - text that is neither rectangle nor polygon syntax is a mask path
    - geometry only; masks are built in M2
  - **ChannelList:** 1 or 3 integers, from `128`, `"128"`, `"128,140,96"` or `[128, 140, 96]`. **Color** is a ChannelList. Its length is checked against the color space in step 3.
  - **Size:** `2GB`, `500MB`, `64KB` or plain bytes, 1024-based (D14).
  - Parse failures raise `InvalidValue` (E101). The message lists the accepted syntaxes with examples, for example: `"1:75" is not a valid time. Use seconds (12.5), MM:SS (01:53.8), HH:MM:SS (00:01:53.8), a frame (f3412) or a percent (50%).`
- **Tests:** table-driven valid and invalid inputs per type, `parse(str(v)) == v` for every valid example, resolution math (timecodes, percent of duration, frames at fractional fps).

#### Step 3 — Settings model

- `settings/base.py`:
  - `param(default, help, *, long="", behavior, ge=None, le=None, …)` returns a pydantic `Field`. It records the one-line help, the long explanation and the behavior class (`display`, `pipeline`, `input`, `export`; spec-web §8.1).
  - Annotated types wrap the value types (`TimeT`, `DurationT`, `ScaleT`, `RoiT`, `ChannelListT`, `ColorT`, `SizeT`). They parse on input and serialize to canonical text.
  - Unions: `int | "auto"`, `float | "nyquist"`, `vmax` (`auto`, a number or `pN`), `overlay_base` (a choice or a Time), `int | None`.
  - `Section` base model: `extra="forbid"` and `validate_assignment=True`.
  - `iter_params(model)` yields `ParamInfo` for every parameter: key, type label as the spec names it, default, allowed range or choices, help, long help and behavior. The CLI help, `config show`, the M5 `/api/schema` and the tests all use it.
- `settings/models.py`: one model per section, with keys, types, defaults, ranges and help exactly as in spec §5, §6, §9.1, §12.2 and §12.4.
  - `InputSettings`, `OutputSettings`, `ParallelSettings`, `CacheSettings`
  - `InfoSettings`
  - `HeatmapSettings` with `preprocess`, `threshold`, `change`, `cleanup` and `output`
  - `TimelineSettings`, `ScenesSettings`, `BackgroundSettings`, `StatsSettings`, `BarcodeSettings`, `ContactSettings`, `FlowSettings`, `FlickerSettings`, `CompareSettings`, `ReportSettings`
  - Every tool section has `input: InputOverride` (all fields optional) for `[<tool>.input]`.
  - The root `Settings` has `version = 1` plus every section.
  - Rules on single fields become field constraints:
    - odd `adaptive_block`; power-of-two `flicker.window`; `poly_n` ∈ {5, 7}; `max_frames ≥ 2`
    - `report.tools` excludes `compare` and `report`
    - list-of-choice fields have no duplicates
  - Rules across fields raise `IncompatibleOptions` (E400):
    - `adaptive` or `range` with `levels > 2`
    - `deltae` without `space = lab`
    - thresholding with `mog2`
    - `values`, `range_lower` or `range_upper` whose length is neither 1 nor the space's channel count
  - Defaults that depend on context are `None`: `input.start`/`end` (whole video), `reference_frame` (= `input.start`), `report.title` (file name), `output.dir` (set by each interface).
- `pyproject.toml`: add the `pydantic.mypy` plugin.
- **Tests:**
  - the spec-sync test (D9)
  - the behavior-class test (D9)
  - every parameter has help text
  - each E400 rule
  - constraint error messages

#### Step 4 — Settings files and layers

- `settings/layers.py`:
  - `Layer(source, data)`: sparse nested dict plus a label such as `--config street-cam.toml`, `preset static-camera`, `--set` or `AVIDEO_WORKERS`.
  - `merge(layers)`: lowest to highest priority, with the tool-input rule from D3.
  - `resolve(layers) -> Settings`: merge, then validate once. Pydantic errors become one `InvalidSettings` listing each issue with:
    - key and bad value
    - allowed values or range
    - did-you-mean
    - which layer set it
  - `effective_input(settings, tool) -> InputSettings`: `[input]` with `[<tool>.input]` applied on top.
  - `diff_from_defaults(settings) -> dict`: only non-default values.
  - `parse_assignment("key=value") -> Layer` for `--set`:
    - the value is converted according to the key's type: comma lists; booleans `true/false/yes/no/on/off/1/0`; `none`; value types
    - an unknown key gets a did-you-mean over all keys
- `settings/io.py`:
  - `load_file(path) -> Layer`:
    - TOML or JSON, chosen by extension, with a content check as fallback
    - `version` is optional (default 1); any other version is E100
    - unknown sections or keys are E100 with did-you-mean, reported against the file
    - relative paths resolve against the file's folder (D12)
  - `dumps_toml(data)`:
    - works for sparse or full data
    - optional header `# avideo settings · exported YYYY-MM-DD HH:MM`
    - value types written as canonical text; sections in model order
  - `tool_settings_toml(settings, tool)`: every value of one tool plus its effective `[input]`. This becomes `<tool>_settings.toml` in M2.
- **Tests:**
  - the spec §8.3 example loads
  - TOML ↔ model round trip is lossless for the defaults and for non-default values of every type
  - JSON gives the same result as TOML
  - the priority order
  - a table of cases for the tool-input rule
  - `--set` conversion per type
  - error message text

#### Step 5 — Paths, user config and presets

- `core/paths.py`:
  - `config_dir()`, `data_dir()`, `cache_dir()`, `user_config_file()`, `presets_dir()`
  - Linux: `~/.config/avideo`, `~/.local/share/avideo`, `~/.cache/avideo` (XDG variables respected)
  - macOS: `~/Library/Application Support/avideo` (config and data), `~/Library/Caches/avideo`
  - Windows: `%APPDATA%\avideo` (config and data), `%LOCALAPPDATA%\avideo\cache`
  - Overrides: `AVIDEO_CONFIG` (user config file) and `AVIDEO_CACHE_DIR`
- `settings/presets.py`:
  - built-in presets from spec §8.4, as layers with descriptions
  - user presets in `<config>/presets/<name>.toml`; the description is the file's first comment line
  - `list_presets()` returns name, source, tools covered and description
  - `load_preset(name)`, with did-you-mean for unknown names
  - `save_preset(name, layer)` writes non-default values only and refuses built-in names
  - `delete_preset(name)`
  - `load_user_config() -> Layer | None`
- **Tests:** temporary folders with mocked environment and platform; every built-in preset resolves without errors.

#### Step 6 — Synthetic test videos

- `pyproject.toml`: pytest `pythonpath = ["tests"]` and the `slow` marker.
- `tests/synth.py`:
  - `write_video(path, frames, *, fps, codec="ffv1", pix_fmt="bgr0", container="mkv", pts=None, rotation=None, interlaced=False, audio=False, subtitles=False)` using PyAV.
  - Frame generators: `index_pattern` (each frame encodes its index; `read_index(image)` decodes it), `moving_square`, `static`, `noisy(sigma)`, `combed` (alternating field content, for deinterlacing).
- `tests/conftest.py`: session-scoped fixtures. They write small clips (≤ 128×72, ≤ 120 frames) once per test run:
  - `clip_index`, `clip_vfr`, `clip_rotated` (90°), `clip_interlaced`
  - `clip_noisy` (known σ), `clip_streams` (with audio and subtitles), `clip_h264` (lossy 4:2:0)
- If PyAV cannot write a container flag (display-matrix rotation, interlaced field order), the fixture uses the `ffmpeg` command when available. Otherwise the dependent tests are skipped with a clear reason. Which way worked goes into Learnings.
- **Tests:** `read_index(index_pattern(...)[k]) == k`; every fixture opens and has the expected basic properties.

#### Step 7 — Video source: probing

- `core/source.py`, part 1:
  - `VideoMeta` (pydantic, JSON-serializable), every field of spec §6.1:
    - **file:** path, size, container, mtime, creation time
    - **video:** duration, frames and whether the count is estimated, average and nominal fps, VFR flag, codec, profile and level, size, SAR and DAR, pixel format, bit depth, chroma subsampling, color space/primaries/transfer/range, scan and field order, rotation, bitrate, keyframe interval
    - **streams:** audio streams, subtitle and data stream counts, all streams (when requested)
    - **backend:** `backend`, `seek_accurate`
  - Backend interface: `probe(path, *, all_streams)`, `frames(start_index)` (yields index, time in seconds, RGB array), `close()`.
  - `PyAVBackend`:
    - metadata from the container, stream and codec context
    - rotation from the display matrix
    - interlacing from the first decoded frame
    - VFR from packet timestamps over the first seconds
    - keyframe interval from demuxing the first 30 s without decoding
    - `seek_accurate = True`
  - `OpenCVBackend`:
    - opened with `CAP_FFMPEG`
    - **automatic orientation turned off**, so rotation is applied by avideo in the same way for both backends
    - reduced metadata (D5)
    - `seek_accurate = False` until M4 adds seek verification
  - `select_backend(choice)`: `auto` picks PyAV when installed. `pyav` without PyAV installed is E100, with the suggestion to install `avideo[av]`.
  - Errors: missing file E200, permission E201, no video stream or unknown codec E202.
  - `quick_hash(path)`: SHA-256 of the file size plus the first and last 4 MB, as `sha256:<hex>`.
- **Tests:** metadata of each fixture with both backends (fields OpenCV cannot give are `None`); each error; quick hash (stable, changes with content, works on files under 8 MB).

#### Step 8 — Video source: sampled frames

- `core/source.py`, part 2:
  - `VideoSource.open(path, input_settings, warnings)`:
    - picks the backend and probes
    - builds the sampling plan: `start`/`end` (inclusive), resolved to frame indices from timestamps (PyAV) or index ÷ average fps (OpenCV; W001 when the stream is VFR); then `step` and `max_frames`
    - `plan.count` is the expected sampled frame count (estimated unless exact); also the processing size
  - `iter_frames()` yields `SampledFrame(index, time_s, image)`:
    1. seeks to `start` (frame-accurate with PyAV; OpenCV reads forward until M4)
    2. rotates: `auto` uses the metadata; W002 when applied
    3. deinterlaces: `auto` only when the stream is flagged interlaced; filter as in D7
    4. resizes: `Scale.apply` on the rotated size; area interpolation down, linear up; W006 when upscaling
  - Skipped frames are decoded but never transformed (D6).
  - `stabilize` and `normalize_exposure` are accepted but not applied until M4.
- **Tests:**
  - exact sampled indices (via `read_index`) for combinations of `start`/`end`/`step`/`max_frames` and every Time kind
  - VFR timestamps
  - rotation 90/180/270 and `rotate = 0`
  - deinterlacing on the combed clip
  - every Scale form
  - **PyAV and OpenCV yield identical frames** on the lossless clips
  - D6 order equals the spec order

#### Step 9 — `info` tool

- `core/colorspaces.py`: `to_gray(rgb)`, Rec. 709 luma on gamma-encoded values.
- `core/pipeline/change.py`:
  - `estimate_noise_sigma(pairs)` implements spec §7.5 steps 1–3: keep flat areas (local gradient in the lowest 50%), then σ = 1.4826 × MAD of the differences ÷ √2.
  - `auto_delta(sigma)` implements step 4.
- `core/tools/info.py`:
  - `run_info(path, settings, *, progress=None) -> InfoResult(meta, checks, warnings)`.
  - `info.exact` decodes every frame to count them, reporting progress through the callback.
  - `info.all_streams` lists every stream.
  - Checks, in spec order:
    - constant frame rate (W001)
    - rotation (W002)
    - chroma subsampling (W003, only when the resolved settings use color, that is `heatmap.space != gray`)
    - interlacing (W005)
    - frame-accurate seeking (W007)
    - noise level (W004: σ over the first 50 comparisons, warns above 6)
  - Each check is a `Check(id, ok, code, title, message, tip)`.
  - `InfoResult.to_json()` returns `{"path", "meta", "checks", "warnings"}` (spec-cli §7.3).
- **Tests:**
  - each check on its fixture: VFR → W001; rotated → W002; H.264 4:2:0 with `space = rgb` → W003, and no W003 with `gray`; interlaced → W005; OpenCV → W007; noisy → W004
  - σ within 15% of the generated noise
  - exact counting; all streams

#### Step 10 — Output folder basics

- `core/outputs.py`:
  - `video_out_dir(root, stem, tool, on_exists)` returns `<root>/<stem>/`, depending on `on_exists`:
    - `overwrite`: reuses the folder
    - `increment`: `<stem>_2/`, `<stem>_3/`, …
    - `fail`: E301 when the folder already holds files of that tool
  - `write_json(path, data)`: UTF-8, 2-space indent, written atomically (temporary file, then rename).
  - Write failures (permission, full disk) become E300.
- **Tests:** each policy; atomic write; E300 on a read-only folder.

### Part B — CLI

#### Step 11 — Console and formatting

- `cli/console.py`:
  - Color tokens for dark and light terminals (spec-cli §2.1) as Rich themes, plus explicit 16-color fallbacks. Command group colors.
  - Theme detection, in order:
    1. `--theme` or `AVIDEO_THEME`
    2. `COLORFGBG`
    3. an OSC 11 query (POSIX TTY only; 50 ms timeout; terminal state always restored)
    4. otherwise dark
  - Color depth: `--color auto|always|never`, `NO_COLOR`, `FORCE_COLOR`, TTY and `CI` checks → truecolor, 256, 16 or none.
  - Glyph sets, Unicode or ASCII (spec-cli §2.3), chosen by the output encoding, `--ascii` or `AVIDEO_ASCII=1`.
  - Width: `COLUMNS` override, minimum 60, maximum content 120, two-column layouts from 100.
  - Two consoles: stdout for results, stderr for progress, warnings, errors and logs (spec-cli §7.1). Clickable links (OSC 8) where supported.
  - A `UI` context object (consoles, theme, glyphs, width, verbosity) passed to every screen.
- `cli/format.py`:
  - `num(7560)` → `7,560`
  - `timecode(113.8)` → `01:53.8` (`HH:MM:SS.f` over an hour)
  - `size(432640000)` → `412.6 MB`
  - percentages
- `tests/snapshots.py` and the `--update-snapshots` pytest option:
  - render a screen with a recording Rich console at a given width and mode
  - compare plain text and SVG with the files in `tests/snapshots/`
  - mask values that change (temporary paths, dates, version)
- **Tests:** a detection matrix (environment and TTY combinations); formatting.

#### Step 12 — Command framework

- **Spike first** (result recorded in Learnings). With the installed Typer (0.29) and Click, confirm three things:
  1. programmatically built Click commands can be added to the Typer app's group
  2. root and command help can be replaced by our own renderer
  3. `--install-completion` still covers those commands
- `cli/commands.py`:
  - `CommandSpec(name, group, summary, explanation, examples, inputs, flags)`, where inputs is videos, two videos or none.
  - The registry; groups Analyze, Extract, Inspect & output and Manage, with their colors.
  - The builder turns a `CommandSpec` into a Click command. Options may come before or after inputs (spec-cli §3.3), and `-h/--help` is supported.
- `cli/flags.py`:
  - `FlagSpec(names, key or effect, metavar, section, kind)`. Kinds:
    - a value
    - an on/off switch (`--no-…` for keys whose default is `true`)
    - a comma list
    - a custom mapper (used by `--thresh` in M3)
  - Global flag sets:
    - input flags (spec-cli §4.1)
    - `-o/--out`, `--on-exists`, `-c/--config` (repeatable), `-p/--preset`, `--set` (repeatable)
    - interface flags (spec-cli §4.3, the M1 subset)
  - Flag values are parsed with the core value types; invalid choices get did-you-mean.
  - `build_layers(parsed)` produces, from lowest to highest priority (spec-cli §9): defaults, user config, environment (`AVIDEO_OUT`, `AVIDEO_WORKERS`, `AVIDEO_BACKEND`), preset, `--config` files in order, `--set` in order, dedicated flags.
- `cli/inputs.py`:
  - expands files, quoted globs and folders (video extensions from spec-cli §3.2; `--recursive`)
  - a missing input raises `InputNotFound`, with fuzzy suggestions from its folder and one level below
- `cli/app.py`, rewritten:
  - the root Typer app (`--version`, completion options) and command registration
  - one error boundary that maps errors to panels and exit codes (spec-cli §10):
    - `AvideoError` by its code
    - Click usage errors → 2
    - ctrl+c → 130
    - anything unexpected → E500 → 1
  - The existing `serve` stub stays until M5.
- **Tests:** options before and after inputs; the priority order through the CLI (user config + environment + preset + config + set + flag); input expansion; each exit code.

#### Step 13 — Error panels

- `cli/errors.py`: the panel of spec-cli §6.7, always on stderr.
  - Title `✗ <title>`.
  - What happened, with the offending value in bold error color.
  - A dim lead-in with why, or what is allowed.
  - `Did you mean …?`, or `Try:` with a corrected command.
  - With `-v`: the error code and traceback below the panel.
  - Usage errors include the command's usage line.
  - `InvalidSettings` with several issues is one panel listing all of them.
- **Tests:** snapshots per error kind at 100 columns, truecolor and no-color: E100 with did-you-mean, E101, E200 with a file suggestion, E202, E300, E400, a usage error.

#### Step 14 — Help screens

- `cli/help.py`:
  - **Main help** (spec-cli §6.1):
    - wordmark with per-letter brand colors (plain bold `avideo` in ASCII mode), version badge and tagline
    - the USAGE line
    - one command panel per group, laid out by width: Analyze full width; Extract and Inspect & output side by side at ≥ 100 columns; Manage as a compact last row
    - the common options panel, built from the global flags with help text and defaults from the settings model
    - three examples and the footer hint
    - only registered commands are listed (D10)
  - **Command help** (spec-cli §6.2), generic:
    - tool badge in the group color, summary and explanation, usage line
    - option panels by section, in pipeline order; analysis commands collapse the global input flags into one line
    - each option shows metavar, help from the settings model, allowed values and default
    - examples panel; footer pointing to `avideo config show <tool>`
    - used now by `info`, `config …` and `presets …`
  - `avideo` with no arguments shows the main help.
- **Tests:** snapshots of the main help and `info --help` at 60, 100 and 140 columns, in truecolor, 256-color, 16-color, no-color and ASCII (text and SVG). They are compared once by eye with the drafts canvas's CLI row; any differences found are recorded in Learnings.

#### Step 15 — `avideo info`

- `cli/info.py`:
  - **Flags:** `--exact`, `--all-streams`, `--backend`, `--rotate`, `-o`, `--on-exists`, `--config`, `--preset`, `--set`, and the interface flags.
  - **Screen** (spec-cli §6.3):
    - a panel with an accent border, titled with the file name
    - a key/value grid: File; Duration (bold yellow); Video (resolution and fps bold cyan); Pixels; Color; Scan; Bitrate; Audio; Other streams (only when present)
    - the checks row (green ✓ items)
    - warnings: yellow `!`, title, plain explanation, and a dim `Tip:` with the flag to use
  - **Several inputs:** one panel per file, then a comparison table (name, duration, resolution, fps, codec, size, warnings).
  - **`--exact`:** a simple progress display on stderr while counting. The full live view comes in M3.
  - **`--json`:** one JSON line per input on stdout. Failures appear as `{"path", "error": {…}}`.
  - **`-o DIR`:** writes `info.json` into `<out>/<stem>/`, following `on_exists`.
  - **Not a TTY, or `CI` set:** no color, plain text with the same content (spec-cli §7.2).
  - **Failures across inputs:** continue on error by default; `--fail-fast`; exit code 6 when some inputs failed.
- **Tests:**
  - snapshots: one file, several files, warnings, the OpenCV backend with missing fields
  - JSON lines validated against a schema
  - non-TTY output; exit codes; `info.json` content

#### Step 16 — Manage commands

- `cli/manage.py`:
  - `config show [TOOL]`:
    - prints the effective settings (defaults + user config + environment) as highlighted TOML
    - every key has a dim comment with its help text and allowed values
    - without TOOL it shows `[input]`, `[output]` and `[parallel]`
  - `config path`: user config, presets, cache and data folders.
  - `config edit`: opens `$EDITOR` (fallbacks: `nano`, `vi`; Windows: `notepad`). If the file is missing, it is created with commented-out defaults.
  - `config check FILE`: prints ✓, or the same error panel as a run (exit code 2).
  - `presets list`: table with name, source, tools and description.
  - `presets show NAME`: highlighted TOML.
  - `presets save NAME [--from FILE] [--set …]`: tool flags join when their commands exist.
  - `presets delete NAME [--yes]`.
- **Tests:** every subcommand; snapshots of `presets list`, `presets show` and `config show heatmap` at 100 columns; `config edit` with a fake `$EDITOR`.

#### Step 17 — Logging and wrap-up

- `-v` writes info logs (chosen backend, probe timings) to stderr. `-vv` adds debug logs and full tracebacks (spec-cli §7.5). Logs never go to stdout.
- Time `info` on a 1080p H.264 file against spec §12.5 (≤ 300 ms for metadata), separately from the noise check. Record the numbers in Learnings.
- Update `README.md` (available commands), the spec (section 9 below) and the [roadmap](README.md) status. Fill in Learnings.

---

## 8. Acceptance criteria

- [ ] `avideo` and `avideo --help` render spec-cli §6.1 at 60, 100 and 140 columns in every color mode and in ASCII; checked by eye with the drafts once.
- [ ] `avideo info` renders spec-cli §6.3 for one and for several files, with every check and warning tip; `--json`, `-o`, `--exact` and `--all-streams` work.
- [ ] Both backends decode identical frames on the lossless fixtures. The OpenCV backend shows `—` for fields it cannot provide.
- [ ] Sampling (`start`, `end`, `step`, `max_frames`, every Time kind), rotation, deinterlacing and resizing give exactly the expected frames.
- [ ] The spec-sync tests pass: every key in spec.md exists in the model with the spec's default, and behavior classes match spec-web §8.1.
- [ ] The spec §8.3 example file passes `avideo config check`. Typos in keys or choices get did-you-mean suggestions. The tool-input rule (D3) is covered by tests.
- [ ] Error panels and exit codes for E100, E101, E200 (with a file suggestion), E202, E300, E400 and usage errors; ctrl+c exits with 130.
- [ ] `config show|path|edit|check` and `presets list|show|save|delete` work.
- [ ] Output is correct when piped: no color, no panels, same content; stdout holds only results.
- [ ] `pytest`, `ruff check .`, `ruff format --check .` and `mypy` pass.

## 9. Spec updates

- spec.md §3.1: `settings.py` becomes the `settings/` package (same import path); add `paths.py`.
- spec.md §4: add the Size type (`2GB`; KB/MB/GB are 1024-based), used by `cache.max_size`.
- spec.md §5 (`input.deinterlace`): name the filter exactly (vertical [1, 2, 1] / 4 blend).
- spec.md §8.2 / spec-web.md §3.1: cache folder locations on macOS and Windows (only Linux is given now).
- spec.md §9.1: say exactly when `on_exists = fail` triggers (the video's folder already holds files of that tool).
- spec.md §12.4: add a parameter table row for `cache.max_size` (it is only mentioned in prose, so the spec-sync test would not see it).
- Anything else found during the work is added here.

## 10. Risks and open questions

- **PyAV 19 API** for display-matrix rotation, field order and color properties. Verify at the start of step 7. If something is missing, read the stream's side data directly.
- **OpenCV 5.0** (installed: 5.0.0.93): video I/O properties such as automatic orientation may differ from 4.x. Verify in step 7.
- **Writing fixtures with rotation or interlace flags** may not be possible through PyAV. Fallback: the `ffmpeg` command, otherwise skip (step 6).
- **Typer/Click integration** for generated commands and custom help. The spike at the start of step 12 decides; the fallback is a thin Click-only root group.
- **`info` speed:** the noise check decodes 51 frames, which may exceed 300 ms on 4K. The spec's target covers metadata only. If it is too slow, the screen shows metadata first and the noise check after it.
- **Snapshot stability:** Rich's SVG export must be deterministic across runs. If not, compare text only and keep SVG for manual review.

## 11. Learnings

*(Filled in when the milestone ends.)*
