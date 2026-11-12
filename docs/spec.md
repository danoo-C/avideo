# avideo — Specification (core)

**avideo** is a video analysis toolkit written in Python. It has two interfaces on top of one shared core:

- a **command-line tool** (`avideo …`) — see [spec-cli.md](spec-cli.md)
- a **local web app** (`avideo serve`) — see [spec-web.md](spec-web.md)

This file is the **single source of truth** for everything both interfaces share: architecture, processing pipeline, every tool and **every parameter** (name, type, default, allowed values), the settings file format, output formats, sessions, live events, performance, errors and warnings. The CLI and web specs only describe how they expose these things; they never redefine a parameter.

This specification describes the complete feature set. It does not say what is built first; that is decided by separate plan documents.

---

## 1. Goals and non-goals

### Goals

1. **Pixel change heatmap** as the flagship feature: count how many times each pixel changes over a video, with optional thresholding (grayscale or per color channel) applied first.
2. A broad set of **additional analyses**: activity timeline, scene/cut detection, background extraction, per-pixel statistics, movie barcode, contact sheet, optical flow, flicker frequency, video comparison and an HTML report.
3. **Two interfaces, identical results.** The same settings produce the same output in the CLI and in the web app.
4. **Tune in the web app, batch in the CLI.** Settings exported from the web app run unchanged with `avideo … --config file.toml`.
5. **Streaming and bounded memory.** Videos of any length can be processed; memory depends on resolution, not on duration.
6. **Fast.** Parallel processing, downscaling and preview modes make tuning interactive.
7. **Local and private.** Nothing leaves the machine. No telemetry, no network calls.

### Non-goals (out of scope)

- Live camera, webcam or network stream (RTSP) input.
- GPU/CUDA processing.
- Audio analysis.
- Video editing or transcoding (beyond writing the tool's own output videos).
- Hosting the web app for multiple remote users.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Source** | An opened video file plus its metadata. |
| **Frame** | One decoded image, `uint8`, RGB, shape `H×W×3`. |
| **Sampled frames** | The frames a run actually processes after applying `start`, `end`, `step` and `max_frames`. |
| **Tool** | One analysis, e.g. `heatmap`, `timeline`, `flow`. Each tool is a CLI command and a page in the web app. |
| **Stage** | One step inside a tool's pipeline whose intermediate image can be shown (e.g. *Thresholded*, *Change mask*). |
| **Settings** | The full set of parameter values for a run. Stored as TOML. |
| **Run** | One execution of a tool on one source with one settings set. Produces results and outputs. |
| **Result** | In-memory output of a run (arrays, tables, stats). |
| **Output** | A file written from a result (PNG, NPY, CSV, MP4, …). |
| **Session** | A saved bundle of video reference, settings and results (`.avideo` file). |
| **Preview quality** | Reduced-resolution processing used for interactive tuning. |
| **Comparison** | One frame compared against its reference. A run over N sampled frames with `reference = previous` has N−1 comparisons. |

---

## 3. Architecture

### 3.1 Package layout

The tree shows the target structure. Modules are created as they are implemented.

```
pyproject.toml          # package, dependencies, `avideo` entry point
src/avideo/
  core/                 # no UI code at all
    source.py           # VideoSource: backends, metadata, seeking, sampled frame iterator
    settings.py         # pydantic models for every parameter; TOML/JSON load, save, merge
    values.py           # parsers for Time, Duration, Scale, ROI, lists
    colorspaces.py      # gray/rgb/hsv/lab/rgbn conversions, all scaled to 0–255
    pipeline/           # reusable stages
      preprocess.py     # resize, rotate, deinterlace, blur, exposure normalization
      stabilize.py
      roi.py
      threshold.py      # fixed / otsu / adaptive / range, levels, hysteresis
      change.py         # reference handling, distance, delta, combine
      cleanup.py        # morphological opening, min-run
      accumulate.py
    tools/              # one module per tool, all implementing the Tool protocol
      info.py heatmap.py timeline.py scenes.py background.py stats.py
      barcode.py contact.py flow.py flicker.py compare.py report.py
    render.py           # colormaps, colorbars, overlays, plots, composites
    outputs.py          # writers, output folder policy, run.json, PNG metadata
    session.py          # .avideo bundles
    events.py           # live event types
    runner.py           # runs one or more tools over one decode pass; cancellation
    parallel.py         # chunked multi-process execution and merging
    cache.py            # result cache
    errors.py           # error and warning types and codes
  cli/                  # Typer + Rich; see spec-cli.md
  server/               # FastAPI; serves the built frontend from server/static/; see spec-web.md
frontend/               # React + TypeScript + Vite (Node project); see spec-web.md §3.2
tests/
docs/
```

### 3.2 Dependencies

| Package | Use |
|---|---|
| Python ≥ 3.11 | `tomllib` is built in |
| `numpy` | All array processing |
| `opencv-python-headless` | Decoding (default backend), image processing, optical flow, video writing fallback |
| `pydantic` v2 | Settings models and validation |
| `tomli-w` | Writing TOML |
| `Pillow` | PNG writing with metadata |
| `scikit-image` | Multi-level Otsu, SSIM |
| `matplotlib` | Plots (timeline, spectra, PSNR/SSIM, direction rose) |
| `typer`, `rich` | CLI |
| `fastapi`, `uvicorn` | Web server (installed by default so `avideo serve` always works) |
| `av` (PyAV) — optional extra `avideo[av]` | Frame-accurate seeking, VFR timestamps, H.264 output |

Development tools (extra `dev`): `pytest`, `httpx`, `ruff`, `mypy`.

**Packaging:**
- `pyproject.toml` with the `hatchling` build backend. The package installs one console entry point: `avideo`.
- Development uses a virtual environment in `.venv/`, created with `python -m venv .venv` and filled with `pip install -e ".[dev,av]"`.
- The frontend is a separate Node project (`frontend/`, Node ≥ 20) built with Vite. Its build output ships inside the Python package, so users never need Node ([spec-web.md](spec-web.md) §3.2).

### 3.3 Core concepts and data flow

```
VideoSource ──► sampled frames ──► per-tool pipeline (stages) ──► Result ──► outputs
                     │                     │
                     │                     └──► live events (progress, stage images, stats)
                     └── shared by several tools in one decode pass (runner)
```

- **VideoSource** opens a file through a backend (`opencv` or `pyav`), exposes metadata (section 6.1) and yields sampled frames with their index and timestamp. It applies the shared input settings that affect frames before any tool sees them: time range, step, rotation, deinterlacing, resize, stabilization, exposure normalization. ROI is passed to tools as a mask.
- **Tool protocol.** Every tool implements:
  - `settings_model` — its pydantic model
  - `begin(meta, settings)` → state
  - `process(frame, index, time)` → optional per-frame stats; updates state
  - `stages(frame)` → named intermediate images for the current frame (used by live views and the frame inspector)
  - `snapshot()` → current partial result (e.g. heatmap so far)
  - `merge(a, b)` → combines partial results from parallel chunks
  - `finish()` → final Result (arrays, tables, stats)
  - `write(result, out_dir)` → output files
- **Runner** drives one decode pass and feeds the same frames to one or more tools (used by `report` and by the web app's "run all"). It emits live events (section 11), honors a cancellation token and supports a *preview* mode (section 12.3).
- **Single-frame evaluation.** For the web app's frame inspector, any tool can compute its stages for an arbitrary frame (plus its reference frame) without running over the whole video.

### 3.4 Determinism

Given the same video, settings, avideo version and `workers = 1`, results are bit-identical. With parallel workers, results are identical for stateless settings and may differ very slightly for stateful ones (section 12.2). `run.json` records the worker count.

---

## 4. Value types

Parameters use these value types. The same syntax is accepted in TOML, on the command line and in the web app.

| Type | Syntax | Examples |
|---|---|---|
| **Time** (a point in the video) | seconds, `MM:SS(.f)`, `HH:MM:SS(.f)`, frame index `f<N>`, or percent of duration | `12.5`, `01:53.8`, `00:01:53.8`, `f3412`, `50%` |
| **Duration** | number with unit `s`, `ms` or `f` (frames); plain number = seconds | `0.5s`, `500ms`, `15f`, `2` |
| **Scale** | percent, factor, `WxH`, `Wx` (keep aspect), `xH` (keep aspect) | `50%`, `0.5`, `960x540`, `960x`, `x540` |
| **ROI** | `x,y,w,h` rectangle; polygon `x1,y1;x2,y2;…` (≥ 3 points); or path to a mask image (white = included) | `100,50,800,400`, `0,0;640,0;320,360`, `roi.png` |
| **ChannelList** | one integer for all channels or one per channel, comma-separated (TOML: array) | `128`, `128,140,96`, `[128, 140, 96]` |
| **Color** (for ranges) | ChannelList in the chosen color space | `[10, 120, 80]` |
| **Choice** | one of the listed words, lowercase | `majority` |

ROI and other pixel coordinates are always in **source** pixel coordinates (before resize); avideo scales them internally.

---

## 5. Common input parameters

These apply to every tool. TOML section `[input]`. A tool may override any of them in `[<tool>.input]` (e.g. `[flicker.input] resize = "25%"`).

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `input.start` | Time | start of video | within video | First frame to analyze. |
| `input.end` | Time | end of video | > start | Last frame to analyze (inclusive). |
| `input.step` | int | `1` | ≥ 1 | Use every Nth frame. |
| `input.max_frames` | int \| none | none | ≥ 2 | Stop after this many sampled frames. |
| `input.resize` | Scale | `100%` | 1%–100% (upscaling is allowed with warning W006) | Downscale frames before processing. |
| `input.roi` | ROI \| none | none | | Region of interest. Pixels outside are ignored by every analysis. |
| `input.roi_crop` | bool | `false` | | `true`: outputs are cropped to the ROI's bounding box. `false`: outputs keep full frame size; pixels outside the ROI are shown as excluded (transparent in PNG, NaN in float arrays, 0 in counts). |
| `input.rotate` | Choice | `auto` | `auto`, `0`, `90`, `180`, `270` | `auto` applies the rotation stored in the file's metadata. |
| `input.deinterlace` | Choice | `auto` | `auto`, `on`, `off` | `auto` deinterlaces only when the stream is flagged interlaced. Uses a simple blend (bob) filter. |
| `input.stabilize` | Choice | `off` | `off`, `translate`, `affine`, `homography` | Aligns each frame to the reference before comparison to cancel camera shake (section 7.4). |
| `input.normalize_exposure` | Choice | `off` | `off`, `mean`, `histogram` | Compensates global brightness changes (auto-exposure, clouds). `mean` scales each frame so its mean luma matches a running average; `histogram` matches each frame's luma histogram to the first frame's. |
| `input.backend` | Choice | `auto` | `auto`, `opencv`, `pyav` | `auto` uses PyAV when installed, otherwise OpenCV. |

**Order of frame operations** (fixed): decode → rotate → deinterlace → time sampling (`start`/`end`/`step`/`max_frames`) → resize → stabilize → exposure normalization → tool pipeline. ROI masking happens inside tools at the point where pixels are counted or measured.

**Variable frame rate.** Times are resolved using frame timestamps (PyAV) or by frame index ÷ average fps (OpenCV, with warning W001). `step` always counts frames, not time.

---

## 6. Tools

Each tool lists its purpose, parameters, algorithm, stages (images shown live and in the web app), results, statistics and outputs. Output file names are relative to the output folder (section 9.1).

### 6.1 `info` — video metadata

**Purpose:** show everything worth knowing about a video before analyzing it, and warn about properties that affect analysis.

| Key | Type | Default | Description |
|---|---|---|---|
| `info.exact` | bool | `false` | Count frames by decoding the whole video instead of trusting container metadata. |
| `info.all_streams` | bool | `false` | List every stream (default: first video stream plus a summary of others). |

**Reported fields:**

- **File:** path, size, container format, modification time, creation time tag
- **Video:**
  - duration; frame count, flagged *estimated* unless exact
  - average fps and nominal fps; VFR flag
  - codec, profile and level
  - width × height; sample and display aspect ratio
  - pixel format, bit depth, chroma subsampling
  - color space, primaries, transfer and range
  - scan type (progressive / interlaced, field order); rotation; average bitrate
  - keyframe interval (estimated from the first 30 s)
- **Audio:** codec, sample rate, channels per stream
- **Other streams:** subtitle and data stream counts

**Checks** (each shows ✓ or a warning with a tip):

- constant frame rate (W001)
- rotation (W002)
- chroma subsampling 4:2:0 / 4:2:2 (W003, shown as a tip only when color settings are relevant)
- interlacing (W005)
- frame-accurate seeking available (W007)
- estimated noise level (W004)

**Outputs:** none by default; `info.json` when written via the CLI `--json`/`-o` or the web export.

---

### 6.2 `heatmap` — per-pixel change heatmap

**Purpose:** count, for every pixel, how many times it changed over the video. Optionally threshold frames first (grayscale or per color channel), so only meaningful changes count.

#### 6.2.1 Pipeline

```
frame ─► preprocess ─► [threshold] ─► compare with reference ─► change mask(s) ─► cleanup ─► accumulate
                │            │                    │
              stage:       stage:               stage:                                    stage:
          Preprocessed  Thresholded          Change mask                                Heatmap
```

Stages available for live display: **Original**, **Preprocessed**, **Thresholded** (only when thresholding is enabled), **Change mask**, **Heatmap** (accumulated so far), and, when `combine = separate`, **Channels** (RGB composite of the per-channel heatmaps).

#### 6.2.2 Color space and preprocess — `[heatmap]`, `[heatmap.preprocess]`

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `heatmap.space` | Choice | `gray` | `gray`, `rgb`, `hsv`, `lab`, `rgbn` | Color space the heatmap works in (section 7.1). With thresholding on, its channels are thresholded; with thresholding off, differences are computed on its channels. `gray` has 1 channel, the others 3. |
| `heatmap.preprocess.blur` | float | `0` | 0–10 | Gaussian blur sigma in processing pixels. Reduces compression noise. `0` = off. |

#### 6.2.3 Threshold (optional) — `[heatmap.threshold]`

Converts each frame into discrete **levels** per channel before comparison. With 2 levels this is binarization. A pixel then counts as changed only when its level changes.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `heatmap.threshold.enabled` | bool | `false` | | Turns the threshold stage on. Channels come from `heatmap.space`. |
| `heatmap.threshold.method` | Choice | `fixed` | `fixed`, `otsu`, `adaptive`, `range` | How cut points are chosen (below). |
| `heatmap.threshold.values` | ChannelList | `128` | 0–255 | Cut point per channel for `fixed` with 2 levels. One value applies to all channels. |
| `heatmap.threshold.levels` | int | `2` | 2–16 | Levels per channel. `2` = binary (8 colors in a 3-channel space); `4` = 64 colors, etc. |
| `heatmap.threshold.hysteresis` | int | `0` | 0–64 | Dead band around each cut point (section 7.2). Stops pixels near a cut point from flickering. |
| `heatmap.threshold.otsu_scope` | Choice | `video` | `video`, `frame` | `video`: Otsu cut points computed once from up to 50 frames sampled evenly across the range (stable). `frame`: recomputed for every frame (follows lighting, may flicker). |
| `heatmap.threshold.adaptive_block` | int | `31` | odd, 3–255 | Neighborhood size in pixels for `adaptive`. |
| `heatmap.threshold.adaptive_offset` | int | `5` | −64–64 | Constant subtracted from the local mean for `adaptive`. |
| `heatmap.threshold.range_lower` | Color | `[0, 0, 0]` | 0–255 per channel | Lower bound (inclusive) for `range`. |
| `heatmap.threshold.range_upper` | Color | `[255, 255, 255]` | 0–255 per channel | Upper bound (inclusive) for `range`. If lower > upper on the hue channel of `hsv`, the range wraps around (for reds). |
| `heatmap.threshold.range_invert` | bool | `false` | | Select pixels **outside** the range. |

**Methods:**

- **`fixed`** — with 2 levels, a channel value `v` maps to level 1 if `v > T`, else 0, using `values`. With more levels, cut points are evenly spaced (`255·k/levels`, k = 1…levels−1) and `values` is ignored.
- **`otsu`** — cut points per channel from Otsu's method (2 levels) or multi-level Otsu (> 2 levels).
- **`adaptive`** — each pixel is compared with its local Gaussian-weighted mean minus `adaptive_offset` (2 levels only; `levels` must be 2).
- **`range`** — produces **one** binary channel: 1 where all channels are within `[range_lower, range_upper]` (or outside, with `range_invert`). Used to track a colored object. `levels` must be 2.

When thresholding is enabled, the **Thresholded** stage shows the leveled image mapped back to colors (binary RGB shows the 8 pure colors; `gray` shows black and white; `range` shows white for selected pixels).

#### 6.2.4 Change detection — `[heatmap.change]`

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `heatmap.change.reference` | Choice | `previous` | `previous`, `frame`, `background` | What each frame is compared against (section 7.3). |
| `heatmap.change.reference_frame` | Time | `input.start` | | The fixed reference frame for `frame`. |
| `heatmap.change.background_model` | Choice | `average` | `average`, `mog2` | Model for `background`. |
| `heatmap.change.background_rate` | float | `0.01` | 0.0001–1 | Learning rate α for `average`, and history length (≈ 1/α frames) for `mog2`. |
| `heatmap.change.distance` | Choice | `channel` | `channel`, `euclidean`, `deltae` | How differences are measured **when thresholding is off**. `channel`: one difference per channel of `heatmap.space`. `euclidean`: one combined distance over all channels. `deltae`: CIEDE2000 perceptual distance (requires `heatmap.space = lab`). The last two produce a single channel. |
| `heatmap.change.delta` | int \| `auto` | `12` | 0–255 | A channel counts as changed when its difference is greater than delta. `auto` estimates video noise and sets delta = ⌈3σ⌉ clamped to 2–64 (section 7.5). **Ignored when thresholding is on**, where any level change counts. |
| `heatmap.change.combine` | Choice | `any` | `any`, `all`, `majority`, `sum`, `separate` | How per-channel change masks become the count (section 7.6). |

#### 6.2.5 Cleanup — `[heatmap.cleanup]`

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `heatmap.cleanup.open` | int | `0` | 0–15 | Morphological opening of the change mask with an elliptical kernel of this diameter in processing pixels. Removes isolated speckles. `0` = off. |
| `heatmap.cleanup.min_run` | int | `1` | 1–300 | Minimum persistence in sampled frames (section 7.7). `1` = off. |

#### 6.2.6 Output — `[heatmap.output]`

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `heatmap.output.normalize` | Choice | `raw` | `raw`, `percent`, `log` | `raw`: counts. `percent`: count ÷ comparisons × 100 (÷ comparisons × channels for `sum`). `log`: log(1 + count) ÷ log(1 + vmax). |
| `heatmap.output.vmax` | `auto` \| number \| `pN` | `auto` | | Value mapped to the top of the colormap. `auto` = maximum; `p99.5` = 99.5th percentile (stops one hot spot from washing out the rest); a number is used as-is in the chosen normalization. |
| `heatmap.output.colormap` | Choice | `inferno` | `inferno`, `magma`, `plasma`, `viridis`, `cividis`, `turbo`, `gray` | Colormap for images. `cividis` and `viridis` are color-blind friendly. |
| `heatmap.output.colorbar` | bool | `true` | | Adds a colorbar strip with min / mid / max labels to `heatmap.png`. |
| `heatmap.output.files` | list | `["png", "npy", "settings"]` | see 6.2.9 | Which outputs to write. |
| `heatmap.output.image_size` | Choice | `source` | `source`, `processing` | Size of image outputs. `source` upscales to the original resolution (nearest-neighbor); `processing` keeps the processing resolution. Arrays always use processing resolution. |
| `heatmap.output.overlay_base` | Choice \| Time | `median` | `median`, `first`, `middle`, or a Time | Background image for the overlay. `median` = per-pixel median of up to 50 evenly sampled frames. |
| `heatmap.output.overlay_opacity` | float | `0.5` | 0–1 | Maximum opacity of the heatmap in the overlay. |
| `heatmap.output.overlay_mode` | Choice | `weighted` | `weighted`, `uniform` | `weighted`: opacity scales with the normalized value, so cold areas show the base image. `uniform`: same opacity everywhere. |
| `heatmap.output.composite_scale` | Choice | `joint` | `joint`, `independent` | For `combine = separate`: normalize the three channel heatmaps to one shared max or each to its own max. |
| `heatmap.output.timelapse_snapshots` | int | `300` | 10–10000 | Number of evenly spaced snapshots rendered into the time-lapse. Also used by the web app to scrub the heatmap's growth after a run. |
| `heatmap.output.timelapse_fps` | int | `30` | 1–120 | Frame rate of the time-lapse video. |
| `heatmap.output.timelapse_scale` | Choice | `final` | `final`, `running` | `final`: every snapshot uses the final vmax (shows growth). `running`: each snapshot uses its own vmax. |
| `heatmap.output.rolling_window` | Duration | `10s` | | Window length for the rolling heatmap video. |
| `heatmap.output.rolling_mode` | Choice | `decay` | `decay`, `exact` | `decay`: exponential decay with half-life = window ÷ 2 (low memory). `exact`: true sliding-window counts using bit-packed masks (memory H×W×window ÷ 8 bytes). |

#### 6.2.7 Results

- `counts`: `uint32` array, shape `H×W` (or `H×W×C` for `separate`), processing resolution.
- `comparisons`: number of frame comparisons.
- `per_frame`: table of frame index, time, percent of ROI pixels changed, mean absolute difference.
- `snapshots`: optional, `timelapse_snapshots` copies of `counts` stored as `uint16` scaled to the final max (kept for the time-lapse and for scrubbing in the web app; dropped after writing outputs in the CLI).

#### 6.2.8 Statistics

| Stat | Meaning |
|---|---|
| `frames` / `comparisons` | Sampled frames and comparisons made |
| `max_count`, `max_location` | Hottest pixel's count and its (x, y) in source coordinates |
| `mean`, `median`, `p99` | Over ROI pixels |
| `never_changed_pct` | Percent of ROI pixels with count 0 |
| `busiest_frame` | Index, time, percent changed |
| `quietest_segment` | Longest span (≥ 1 s) where < 1% of pixels changed per frame |
| `noise_sigma` | Estimated noise σ (always computed on the first 50 comparisons) |
| `delta_used` | The delta actually used (shows the result of `auto`) |

#### 6.2.9 Outputs

| `files` entry | File | Content |
|---|---|---|
| `png` | `heatmap.png` | Colormapped heatmap (+ colorbar unless disabled). Settings embedded as PNG text metadata (section 9.4). |
| `overlay` | `heatmap_overlay.png` | Heatmap over the base image. |
| `npy` | `heatmap_counts.npy` | Raw `counts` array. |
| `csv` | `heatmap_counts.csv` | `counts` as CSV, one row per pixel row (for `separate`: one file per channel, `heatmap_counts_c0.csv` …). |
| `composite` | `heatmap_channels.png` | RGB composite for `separate` (channel *i*'s heatmap drives color channel *i*). |
| `timelapse` | `heatmap_timelapse.mp4` | The heatmap building up over the video. |
| `rolling` | `heatmap_rolling.mp4` | Rolling-window heatmap, one output frame per sampled frame. |
| `timeline` | `timeline.csv` | The `per_frame` table (same format as the `timeline` tool). |
| `settings` | `heatmap_settings.toml` | Fully resolved settings. |
| — (always) | `heatmap_run.json` | Run record (section 9.3). |

---

### 6.3 `timeline` — activity over time

**Purpose:** show *when* things happen: how much of the frame changes in each frame, plus brightness.

Timeline uses the change-detection settings of the `heatmap` sections (`[heatmap]` space, `[heatmap.preprocess]`, `[heatmap.threshold]`, `[heatmap.change]`, `[heatmap.cleanup]`), so "percent changed" means exactly what it means in the heatmap.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `timeline.smooth` | Duration | `0f` | | Moving-average window applied to the curves for plots and peak detection (raw values are always kept in the CSV). |
| `timeline.active_above` | float | `1.0` | 0–100 | A frame is *active* when percent changed exceeds this. |
| `timeline.min_segment` | Duration | `1s` | | Active/quiet segments shorter than this merge into their neighbors. |
| `timeline.peak_prominence` | float | `2.0` | 0–100 | Minimum prominence (in percentage points) for a peak to be reported. |
| `timeline.max_peaks` | int | `20` | 1–1000 | Report at most this many peaks (highest first). |

**Per-frame metrics:** `pct_changed`, `mean_abs_diff` (luma, 0–255), `mean_luma` (0–255).

**Stages:** Original, Change mask (the frame being measured).

**Statistics:** active time and percentage, number of active segments, highest peak (time, value), mean percent changed.

**Outputs:**

- `timeline.csv` (columns `frame,time_s,pct_changed,mean_abs_diff,mean_luma`)
- `timeline.png` (plot: percent changed, with brightness on a second axis, active segments shaded and peaks marked)
- `timeline_segments.json` (segments and peaks)
- `timeline_settings.toml`, `timeline_run.json`

---

### 6.4 `scenes` — cuts, frozen frames and black frames

**Purpose:** find shot boundaries and problem segments.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `scenes.cut_threshold` | float | `30` | 1–255 | A cut is detected when the content score jumps above this. Content score = mean absolute difference between consecutive frames in HSV, averaged over the three channels (processing resolution, 0–255). |
| `scenes.cut_adaptive` | bool | `true` | | Also requires the score to be at least 3× the average of the surrounding ±1 s. Avoids false cuts during fast motion. |
| `scenes.min_scene` | Duration | `0.5s` | | Cuts closer together than this are merged. |
| `scenes.frozen_max_change` | float | `0.1` | 0–100 | A frame is *frozen* when less than this percent of pixels change (heatmap detection settings with `delta` at least 2). |
| `scenes.frozen_min` | Duration | `1s` | | Minimum length of a reported frozen segment. |
| `scenes.black_max_luma` | int | `16` | 0–255 | A pixel is black when its luma is at or below this. |
| `scenes.black_min_pixels` | float | `98` | 0–100 | A frame is black when at least this percent of pixels are black. |
| `scenes.black_min` | Duration | `0.2s` | | Minimum length of a reported black segment. |
| `scenes.thumbnails` | bool | `true` | | Save one thumbnail per scene (its middle frame). |
| `scenes.thumb_width` | int | `320` | 64–1920 | Thumbnail width in pixels. |

**Stages:** Original, Difference (absolute HSV difference to the previous frame).

**Statistics:** number of scenes, cuts, frozen and black segments; average and shortest scene length.

**Outputs:**

- `scenes.csv` (columns `index,type,start_frame,end_frame,start_s,end_s,duration_s,score`; type is `scene`, `frozen` or `black`)
- `scenes.json` (same data)
- `scenes/scene_###.jpg` thumbnails
- `scenes_settings.toml`, `scenes_run.json`

---

### 6.5 `background` — background extraction

**Purpose:** reconstruct the static scene by removing moving objects.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `background.method` | Choice | `median` | `median`, `mode`, `mean` | Per-pixel statistic over sampled frames. |
| `background.samples` | int | `50` | 3–500 | Number of frames sampled evenly across the range (bounds memory: samples × H × W × 3 bytes). |
| `background.foreground_frame` | Time \| none | none | | Also output the foreground mask of this frame (difference to the background > `heatmap.change.delta`). |

**Stages:** Original, Background (current estimate), Foreground (difference of the current frame to the current estimate).

**Outputs:**

- `background.png`
- `background_foreground.png` (if a foreground frame is set)
- `background_settings.toml`, `background_run.json`

---

### 6.6 `stats` — per-pixel statistics

**Purpose:** per-pixel temporal statistics, and detection of dead, stuck and hot pixels.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `stats.space` | Choice | `gray` | `gray`, `rgb` | Channels to measure. |
| `stats.measures` | list | `["mean", "std", "min", "max"]` | `mean`, `std`, `min`, `max`, `range` | Which statistic images to produce. |
| `stats.colormap` | Choice | `viridis` | same as heatmap | Colormap for statistic images. |
| `stats.stuck_max_std` | float | `0.5` | 0–255 | Pixels with temporal std at or below this are *stuck*. |
| `stats.hot_min_mean` | float | `250` | 0–255 | Pixels with mean at or above this are *hot*. |
| `stats.dead_max_mean` | float | `5` | 0–255 | Pixels with mean at or below this **and** stuck are *dead*. |

**Algorithm:** streaming mean and variance (Welford), running min/max, all in `float64`/`uint8`. Memory O(H×W).

**Stages:** Original, the selected statistic so far.

**Caveat:** stuck/dead/hot detection is meaningful for calibration footage (static, evenly lit scene) and lossless or high-bitrate video. On lossy video, warning W009 is shown.

**Outputs:**

- `stats_<measure>.png` (colormapped) and `stats_<measure>.npy` (`float32`) for each measure
- `stats_pixels.csv` (columns `x,y,kind,mean,std`)
- `stats_settings.toml`, `stats_run.json`

---

### 6.7 `barcode` — movie barcode

**Purpose:** a strip showing the color of the video over time.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `barcode.mode` | Choice | `mean` | `mean`, `dominant` | Column color: mean color of the frame, or its dominant color (k-means, k = 3, largest cluster). |
| `barcode.width` | int | `1920` | 16–20000 | Output width. Sampled frames are binned into this many columns. |
| `barcode.height` | int | `240` | 8–4000 | Output height. |
| `barcode.style` | Choice | `solid` | `solid`, `squeezed` | `solid`: one color per column. `squeezed`: each frame is resized to 1 px wide and stacked, keeping vertical structure. |

**Outputs:** `barcode.png`, `barcode.csv` (column, start_s, end_s, r, g, b), `barcode_settings.toml`, `barcode_run.json`.

---

### 6.8 `contact` — contact sheet

CLI command name: `contact-sheet`.

**Purpose:** a grid of thumbnails for a quick visual overview.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `contact.cols` | int | `5` | 1–20 | Columns. |
| `contact.rows` | int | `4` | 1–50 | Rows. Thumbnails = cols × rows. |
| `contact.pick` | Choice | `even` | `even`, `scenes` | `even`: evenly spaced times. `scenes`: middle frame of each detected scene (uses `[scenes]` settings), up to cols × rows. |
| `contact.thumb_width` | int | `320` | 64–1920 | Width of each thumbnail. |
| `contact.timestamps` | bool | `true` | | Print the timestamp on each thumbnail. |
| `contact.header` | bool | `true` | | Header with file name, duration, resolution, fps, codec and size. |
| `contact.format` | Choice | `png` | `png`, `jpg` | Output format. |

**Outputs:** `contact_sheet.png|jpg`, `contact_settings.toml`, `contact_run.json`.

---

### 6.9 `flow` — optical flow

**Purpose:** show where things move, in which direction and how fast.

Uses dense Farnebäck optical flow (OpenCV) between consecutive sampled frames on luma.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `flow.pyr_scale` | float | `0.5` | 0.1–0.9 | Pyramid scale between levels. |
| `flow.levels` | int | `3` | 1–8 | Pyramid levels. |
| `flow.winsize` | int | `15` | 3–99 | Averaging window size. |
| `flow.iterations` | int | `3` | 1–20 | Iterations per level. |
| `flow.poly_n` | int | `5` | 5 or 7 | Pixel neighborhood for polynomial expansion. |
| `flow.poly_sigma` | float | `1.2` | 0.5–3 | Gaussian sigma for polynomial expansion. |
| `flow.min_magnitude` | float | `0.5` | 0–50 | Vectors shorter than this (processing px per frame) count as no motion. |
| `flow.colormap` | Choice | `inferno` | same as heatmap | For the magnitude image. |
| `flow.arrow_spacing` | int | `24` | 8–200 | Grid spacing (px) of the arrow overlay. |

**Accumulated per pixel:** mean magnitude, mean flow vector (sum of vectors ÷ count), moving-frame count (magnitude ≥ min).

**Stages:** Original, Flow (current frame, HSV: hue = direction, value = speed), Magnitude (mean so far), Direction (mean direction so far), Arrows (mean vectors over the original).

**Statistics:** mean speed, dominant direction (degrees, 0° = right, counter-clockwise), percent of pixels with motion.

**Outputs:**

- `flow_magnitude.png`
- `flow_direction.png` (with color-wheel legend)
- `flow_arrows.png`
- `flow_rose.png` (polar histogram of motion directions weighted by magnitude)
- `flow_vectors.npy` (`float32` `H×W×2` mean vectors)
- `flow_magnitude.npy`
- `flow_per_frame.csv` (frame, time_s, mean_magnitude, dominant_direction_deg)
- `flow_settings.toml`, `flow_run.json`

---

### 6.10 `flicker` — per-pixel flicker frequency

**Purpose:** find flickering lights or screens and their frequency.

Per-pixel FFT of luma over time windows, averaged across windows (Welch-style).

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `flicker.window` | int | `256` | 16–4096, power of two | Frames per FFT window. |
| `flicker.overlap` | float | `0.5` | 0–0.9 | Window overlap. |
| `flicker.min_hz` | float | `0.5` | > 0 | Ignore frequencies below this. |
| `flicker.max_hz` | float \| `nyquist` | `nyquist` | ≤ fps ÷ 2 | Ignore frequencies above this. |
| `flicker.min_amplitude` | float | `2.0` | 0–255 | Pixels whose strongest peak is below this amplitude (luma units) are shown as no flicker. |
| `flicker.colormap` | Choice | `turbo` | same as heatmap | For the frequency map. |

**Memory:** window × H × W × 4 bytes at processing resolution. avideo warns (W010) when this exceeds 2 GB and suggests a smaller `resize` (e.g. `[flicker.input] resize = "25%"`).

**Aliasing:** frequencies above fps ÷ 2 fold back (100 Hz mains flicker at 30 fps appears at 10 Hz). Shown in the legend as a note.

**Stages:** Original, Frequency (map so far), Amplitude (map so far).

**Outputs:**

- `flicker_frequency.png` (with Hz legend)
- `flicker_amplitude.png`
- `flicker_frequency.npy`, `flicker_amplitude.npy`
- `flicker_peaks.npy` (`float32` `H×W×3×2`: the three strongest peaks per pixel as Hz and amplitude)
- `flicker_spectrum.png` and `flicker_spectrum.csv` (average spectrum over flickering pixels)
- `flicker_settings.toml`, `flicker_run.json`

---

### 6.11 `compare` — compare two videos

**Purpose:** where and when two videos differ (encoder tests, regressions, before/after).

Inputs: video **A** and video **B**. If resolutions differ, B is resized to A (warning W011). Comparison happens after the input settings, which apply to both.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `compare.align` | Choice | `none` | `none`, `offset`, `auto` | `offset`: shift B by `compare.offset`. `auto`: find the offset (±10 s) that best correlates the two activity timelines. |
| `compare.offset` | Duration | `0s` | may be negative | B's offset relative to A. |
| `compare.delta` | int | `12` | 0–255 | Per-pixel luma difference counted as *different*. |
| `compare.metrics` | list | `["psnr", "ssim", "mad"]` | `psnr`, `ssim`, `mad` | Per-frame metrics (MAD = mean absolute difference). SSIM on luma. |
| `compare.worst` | int | `5` | 0–100 | Save side-by-side images of the N most different frames. |
| `compare.colormap` | Choice | `inferno` | same as heatmap | For difference heatmaps. |

**Accumulated per pixel:** mean absolute difference; count of frames with difference > delta.

**Stages:** A, B, Difference (|A − B| current frame), Difference heatmap (mean so far).

**Statistics:** mean / min PSNR, mean / min SSIM, mean MAD, worst frame, percent of frames with any pixel above delta.

**Outputs:**

- `compare.csv` (frame, time_s, psnr, ssim, mad)
- `compare.png` (metric plot)
- `compare_diff_mean.png`, `compare_diff_count.png`, `compare_diff_mean.npy`
- `compare_worst/###_<time>.png`
- `compare_settings.toml`, `compare_run.json`

---

### 6.12 `report` — HTML report

**Purpose:** run several tools in one decode pass and write one HTML report.

| Key | Type | Default | Allowed | Description |
|---|---|---|---|---|
| `report.tools` | list | `["info", "heatmap", "timeline", "scenes", "background", "barcode", "contact"]` | any tools except `compare` and `report` | Tools to run and include. Each uses its own settings sections. |
| `report.self_contained` | bool | `true` | | `true`: one HTML file with images embedded. `false`: HTML plus an `report_assets/` folder. |
| `report.title` | string | file name | | Report title. |

**Content:**

- header (title, file, date, avideo version)
- info table with checks
- one section per tool: key stats, main images, plots
- settings appendix (the resolved TOML)

The page has a light/dark theme following the system, and works offline.

**Outputs:** `report.html` (+ `report_assets/`), plus every included tool's regular outputs, `report_settings.toml`, `report_run.json`.

---

## 7. Algorithms in detail

### 7.1 Color spaces

All channels are scaled to **0–255** so thresholds and deltas mean the same in every space.

| Space | Channels | Definition |
|---|---|---|
| `gray` | Y | Luma, Rec. 709 weights (0.2126 R + 0.7152 G + 0.0722 B) on gamma-encoded values. |
| `rgb` | R, G, B | As decoded. |
| `hsv` | H, S, V | OpenCV HSV with hue rescaled from 0–179 to 0–255. Hue wraps around. |
| `lab` | L, a, b | CIE L\*a\*b\* (D65): L 0–100 → 0–255; a, b −128…127 → 0–255 (offset +128). |
| `rgbn` | r, g, b | Normalized RGB (chromaticity): channel ÷ (R+G+B) × 255; black pixels map to 0. Ignores brightness, robust to shadows. |

Hue differences in `hsv` use the circular distance (min(|d|, 256 − |d|)).

### 7.2 Hysteresis

For each pixel and channel, the level `L(t)` is stateful. With cut point `T` and hysteresis `h`:

- the level goes **up** across `T` only if the value exceeds `T + h`;
- it goes **down** across `T` only if the value falls below `T − h`;
- otherwise it keeps its previous level.

At the first sampled frame, levels are assigned without hysteresis. With more than 2 levels, the same rule applies to every cut point. The reference frame/background in `frame`/`background` modes is leveled without hysteresis.

### 7.3 Reference modes

- **`previous`**: compare frame t with the previous *sampled* frame.
- **`frame`**: compare every frame with one fixed frame (`reference_frame`).
- **`background`**:
  - **`average`**: compare with a running-average background `B ← (1 − α)·B + α·F`. B is updated after comparing, and is initialized with the first frame.
  - **`mog2`**: OpenCV's MOG2 subtractor produces the change mask directly. `delta` and `distance` are ignored, and thresholding is not allowed with `mog2`.

### 7.4 Stabilization

Each frame is aligned to the reference frame (`previous` → previous aligned frame; `frame` → the reference; `background` → the first frame):

- ORB features + RANSAC estimate a transform of the chosen type (`translate`, `affine`, `homography`).
- The frame is warped.
- Pixels with no source data after warping are excluded from counting for that frame.

If fewer than 20 inliers are found, the frame is used unaligned and warning W012 is counted (reported once with the number of affected frames).

### 7.5 Automatic delta (noise estimation)

1. Take the first 50 comparisons (luma, after preprocessing).
2. Keep pixels whose local gradient is in the lowest 50% (flat areas).
3. σ = 1.4826 × median absolute deviation of the frame differences ÷ √2.
4. `delta = clamp(ceil(3σ), 2, 64)`.

σ is always reported (`noise_sigma`). Warning W004 is raised when σ > 6 (noisy or low-light video) with the tip to use blur or a higher delta.

### 7.6 Combining channels

Given per-channel change masks m₁…m_C:

| Mode | Count increment per pixel per comparison |
|---|---|
| `any` | 1 if any mᵢ |
| `all` | 1 if all mᵢ |
| `majority` | 1 if at least ⌈(C+1)/2⌉ of mᵢ (C = 3 → 2 or more) |
| `sum` | number of true mᵢ (0…C) |
| `separate` | each channel accumulates into its own counts plane |

With one channel (`gray`, `range`, `euclidean`, `deltae`), every mode behaves like `any` (and `separate` yields one plane).

### 7.7 Minimum run

- **Thresholding on:** a level change only takes effect (and is counted) after the new level has persisted for `min_run` consecutive sampled frames (debounce). Shorter excursions are ignored and do not change the stored level.
- **Thresholding off:** a changed comparison is counted only if it belongs to a run of at least `min_run` consecutive changed comparisons at that pixel. Counting is delayed by up to `min_run − 1` frames; the run is flushed at the end of the video.

### 7.8 Speckle removal

Opening (erosion then dilation) on each channel's change mask, before combining, with an elliptical kernel of diameter `open`.

### 7.9 ROI

Pixels outside the ROI never count, are excluded from all percentages and statistics, and are drawn as excluded in outputs (section 5, `roi_crop`).

---

## 8. Settings

### 8.1 Model

- All parameters are defined once as pydantic models in `avideo.core.settings`.
- Each parameter has a key (`heatmap.change.delta`), type, default, allowed range or values, a one-line help text and a longer explanation. Both interfaces generate their help texts and tooltips from these.
- Validation errors name the key, the bad value, the allowed values or range, and (for unknown keys or choices) the closest valid match.

### 8.2 Precedence

From lowest to highest:

1. built-in defaults
2. user config file (`~/.config/avideo/config.toml`; Windows `%APPDATA%\avideo\config.toml`; macOS `~/Library/Application Support/avideo/config.toml`)
3. preset (`--preset NAME` or chosen in the web app)
4. settings file (`--config FILE` or imported in the web app)
5. explicit CLI flags or web app edits

`[<tool>.input]` overrides `[input]` at the same level.

### 8.3 File format (TOML)

- UTF-8 TOML. The top level has `version = 1` (schema version).
- Sections are named after keys: `[input]`, `[heatmap.threshold]`, …
- A file may contain sections for several tools; each tool reads only its own sections plus `[input]`.
- Unknown keys or sections are errors (with a did-you-mean suggestion).
- JSON with the same structure is accepted everywhere TOML is.
- Exported files contain only values that differ from defaults, unless "include defaults" is chosen. The resolved settings written to `<tool>_settings.toml` always contain every value of that tool.

Example:

```toml
# avideo settings · exported 2026-11-12 21:14
version = 1

[input]
resize = "50%"
step = 1

[heatmap]
space = "rgb"

[heatmap.preprocess]
blur = 1.0

[heatmap.threshold]
enabled = true
method = "fixed"
values = [128, 140, 96]
hysteresis = 12

[heatmap.change]
delta = 12
combine = "majority"

[heatmap.cleanup]
open = 3
min_run = 2

[heatmap.output]
colormap = "inferno"
files = ["png", "overlay", "npy", "settings"]
```

### 8.4 Built-in presets

| Preset | Purpose | Values (others default) |
|---|---|---|
| `default` | Plain defaults | — |
| `static-camera` | Fixed camera, outdoor or lab | `blur = 1`, `delta = "auto"`, `open = 3`, `normalize_exposure = "mean"` |
| `screen-recording` | Screen captures, UI tests | `blur = 0`, `delta = 2`, `space = "rgb"`, `combine = "any"` |
| `handheld` | Moving camera | `stabilize = "affine"`, `blur = 1.5`, `delta = "auto"`, `open = 3` |
| `low-light` | Dark, noisy footage | `blur = 2`, `delta = "auto"`, `min_run = 2`, `open = 3` |
| `color-object` | Track one colored object | `threshold.enabled = true`, `method = "range"`, `space = "hsv"` |

User presets are TOML files in `<config dir>/presets/<name>.toml` and can be created from both interfaces.

---

## 9. Outputs

### 9.1 Output folder

- Root: `output.dir`
  - CLI default: `./avideo-out`
  - web default: `<served root>/avideo-out`
- Each video gets a folder named after its file stem: `<root>/<stem>/`. All tools write into the same folder; every file is prefixed by its tool name, so tools never collide.
- `output.on_exists`:
  - `overwrite` (default): replaces the files of the same tool in that folder. Other tools' files are untouched.
  - `increment`: writes into `<stem>_2/`, `<stem>_3/`, ….
  - `fail`: stops with an error.
- Batch runs also write `<root>/summary.csv` (one row per input with the key stats).

| Key | Type | Default | Description |
|---|---|---|---|
| `output.dir` | path | see above | Output root. |
| `output.on_exists` | Choice | `overwrite` | `overwrite`, `increment`, `fail`. |

### 9.2 File formats

| Kind | Format |
|---|---|
| Images | PNG (8-bit RGB or RGBA when ROI exclusion is shown); JPG only where stated |
| Arrays | NumPy `.npy` (little-endian); dtypes as stated per tool |
| Tables | CSV, UTF-8, comma-separated, header row, `.` decimal point, times in seconds with 3 decimals |
| Videos | MP4. H.264 via PyAV when available, otherwise OpenCV `mp4v`. Even dimensions (padded). |
| Structured data | JSON, UTF-8, 2-space indent |
| Settings | TOML (section 8.3) |

### 9.3 Run record — `<tool>_run.json`

```json
{
  "avideo_version": "0.1.0",
  "tool": "heatmap",
  "status": "complete",
  "started": "2026-11-12T21:14:31+01:00",
  "duration_s": 35.2,
  "workers": 7,
  "quality": "full",
  "input": {
    "path": "/home/user/videos/street-cam/street-cam_2026-11-03.mp4",
    "size": 432640000,
    "quick_hash": "sha256:…",
    "meta": { "width": 1920, "height": 1080, "fps": 29.97, "frames": 7560 }
  },
  "settings": { "...": "fully resolved, same structure as TOML" },
  "stats": { "...": "tool statistics" },
  "warnings": [ { "code": "W003", "message": "…" } ],
  "outputs": [ "heatmap.png", "heatmap_counts.npy", "heatmap_settings.toml" ]
}
```

- `status` is `complete` or `partial` (stopped early; section 13.3).
- `quick_hash` is the SHA-256 of the file size plus the first and last 4 MB. It identifies a video for caches and sessions without reading the whole file.

### 9.4 Settings embedded in images

Every PNG an avideo tool writes carries a PNG text chunk `avideo` with the run record's `tool`, `avideo_version` and resolved `settings` as JSON. Importing such a PNG (web app) or passing it to `--config` (CLI) recovers its settings.

---

## 10. Sessions — `.avideo`

A session is a ZIP file:

```
manifest.json        # format version, created, avideo version, video {path, size, quick_hash, meta}
settings.toml        # all tools' settings
results/<tool>/…     # result arrays and tables (npy, csv, json), snapshots for scrubbing
thumbs/…             # small JPG thumbnails for the web app's recent list
```

- The video itself is **not** included; it is referenced by absolute path, with the quick hash for verification.
- Opening a session whose video moved asks for its new location (web app) or accepts `--video PATH` (CLI). The quick hash must match; otherwise avideo warns and offers to open the session's settings only.
- Sessions are written by the web app's export and by the CLI's `--session FILE` option, and are opened by the web app and by `avideo serve FILE.avideo`.

---

## 11. Live events

The runner emits typed events. The CLI live view and the web app's WebSocket both consume these; neither computes anything themselves.

| Event | Fields | Rate |
|---|---|---|
| `RunStarted` | run_id, tool(s), total_frames, settings, quality, workers | once |
| `Progress` | frames_done, total_frames, fps, elapsed_s, eta_s | ≤ 10/s |
| `FrameStats` | batch of {frame, time_s, pct_changed, …tool-specific} | batched, ≤ 10/s |
| `StageImages` | frame, time_s, {stage name → image} | ≤ requested fps (default 12), only for subscribed stages |
| `Snapshot` | frames_done, partial result (e.g. counts as `uint16` scaled + max) | ≤ requested fps (default 4) |
| `Warning` | code, message, details | when raised (deduplicated per code) |
| `RunFinished` | stats, outputs, duration_s | once |
| `RunCancelled` | frames_done, partial stats, outputs written | once |
| `RunFailed` | error code, message, details | once |

Consumers declare what they want (stages, rates, image size) through a subscription. The runner never renders more than requested. Stage images are produced at the requested display size, not at processing size.

---

## 12. Performance

### 12.1 Streaming and memory

Frames are processed one at a time. Memory is O(H × W) at processing resolution for every tool except:

- `background` (samples × frame)
- `flicker` (window × frame)
- `rolling_mode = exact` (window bits per pixel)
- heatmap snapshots (snapshots × H × W × 2 bytes)

Each of these warns when it would exceed 2 GB.

### 12.2 Parallel processing

| Key | Type | Default | Description |
|---|---|---|---|
| `parallel.workers` | int \| `auto` | `auto` | Worker processes. `auto` = CPU cores − 1, at most 8. `1` = sequential. |
| `parallel.warmup` | int \| `auto` | `auto` | Extra frames each chunk processes before its start to rebuild state (not counted). `auto` = 0 for stateless settings; max(5 × min_run, 50) with hysteresis or min_run; ⌈5 ÷ α⌉ (at most 2000) for background models. |

- The sampled frame range is split into contiguous chunks, one per worker.
- Each worker opens its own source, seeks to `chunk_start − 1 − warmup` and processes its chunk.
- Results are merged with the tool's `merge` (counts and sums add; per-frame tables concatenate; min/max combine; Welford states merge).
- Each chunk starts one frame early so the first comparison of the chunk is made.
- Parallel runs need frame-accurate seeking. With the OpenCV backend, avideo verifies the position after seeking. If it is wrong, the run falls back to sequential with warning W007.
- Tools that need global order run sequentially: `scenes` (cut adaptivity window), `compare` with `align = auto`, and `report` (one shared pass).

### 12.3 Preview quality

Used by the web app while tuning and by `--preview` in the CLI:

- `quality = preview` processes at 25% scale (relative to `input.resize`) and uses one worker, so frames arrive in order.
- `quality = full` uses the configured settings and workers.

### 12.4 Result cache

- Results are cached in `<cache dir>/results/` (`~/.cache/avideo` on Linux), keyed by quick_hash + tool + resolved settings hash + avideo version.
- The cache is LRU, limited by `cache.max_size` (default `2GB`).
- The web app uses it to return instantly to settings it has already run.
- The CLI uses it only with `--cache`.

### 12.5 Targets

Reference machine: 8-core laptop, 1080p H.264, PyAV backend.

| Scenario | Target |
|---|---|
| `heatmap`, gray, resize 50%, 7 workers | ≥ 200 fps (decode-bound) |
| `heatmap`, preview quality, 1 worker | ≥ 120 fps |
| Single-frame stage evaluation at preview size | ≤ 50 ms |
| `info` (metadata only) | ≤ 300 ms |

---

## 13. Errors, warnings and cancellation

### 13.1 Errors

All errors derive from `AvideoError` and carry a code, a short title, a message and an optional suggestion.

| Code | Class | Example |
|---|---|---|
| `E100` | `InvalidSettings` | Out-of-range or unknown value; message names the key and allowed values |
| `E101` | `InvalidValue` | Unparseable Time/Scale/ROI |
| `E200` | `InputNotFound` | File does not exist (suggests close matches) |
| `E201` | `InputUnreadable` | Permission denied |
| `E202` | `UnsupportedFormat` | No video stream / unknown codec |
| `E203` | `DecodeError` | Corrupt data at frame N (skipped frames reported; fails only if > 1% are bad) |
| `E300` | `OutputError` | Cannot write output folder; disk full |
| `E301` | `OutputExists` | With `on_exists = fail` |
| `E400` | `IncompatibleOptions` | e.g. `method = adaptive` with `levels > 2`; `distance = deltae` without `heatmap.space = lab`; thresholding with `mog2` |
| `E500` | `InternalError` | Unexpected; includes a hint to rerun with `--verbose` |

### 13.2 Warnings

Warnings never stop a run. Each is reported once per run (with a count when it repeats).

| Code | When | Tip shown |
|---|---|---|
| `W001` | Variable frame rate | Times use timestamps (PyAV) or are approximate (OpenCV); install `avideo[av]` |
| `W002` | Rotation metadata applied | Use `--rotate 0` to ignore |
| `W003` | 4:2:0/4:2:2 chroma with color thresholding or color change detection | Add `blur = 1`; color edges are blocky |
| `W004` | Noise σ > 6 | Use `blur`, `delta = "auto"`, `min_run` |
| `W005` | Interlaced content | `deinterlace = "on"` |
| `W006` | `resize` upscales | No benefit; slower |
| `W007` | Seeking not frame-accurate | Running sequentially; install `avideo[av]` |
| `W008` | ROI partly outside the frame | Clipped |
| `W009` | Stuck/dead pixel detection on lossy video | Results unreliable |
| `W010` | Estimated memory > 2 GB | Lower resize / window / samples |
| `W011` | `compare` resolutions differ | B resized to A |
| `W012` | Stabilization failed on some frames | Count reported |
| `W013` | Frames skipped due to decode errors | Count reported |

### 13.3 Cancellation

- Runs accept a cancellation token. On cancel, the tool finishes the current frame and writes outputs from the partial result, unless the cancel was a hard cancel.
- The run record then has `"status": "partial"` and `stats.frames` is the number actually processed.

---

## 14. Privacy and security

- avideo makes **no network requests** and collects no telemetry.
- The web server binds to `127.0.0.1` by default; other measures (token, host checks, path sandboxing) are specified in [spec-web.md](spec-web.md).
- Tools only read the input files they are given and only write inside the output folder and avideo's own config, cache and data folders.

---

## 15. Testing

- **Synthetic videos** generated in tests with known ground truth (lossless FFV1 in MKV), such as:
  - a moving square on a static background (exact heatmap counts)
  - a blinking region at a known frequency (flicker)
  - inserted black, frozen and cut segments (scenes)
  - a known global shift (stabilization)
  - two videos with a known difference (compare)
- **Unit tests** per pipeline stage and per value parser.
- **Property tests:** parallel == sequential for stateless settings; chunk merging is associative; TOML ↔ model round-trip is lossless; percent normalization never exceeds 100.
- **Golden tests:** small real-world clips with stored expected stats (with tolerances).
- **Interface tests:** see the CLI and web specs (snapshot tests of terminal output, API and WebSocket tests).
- **Benchmarks** for the targets in 12.5, run on demand (not blocking).

---

## 16. Interface coverage

Every tool exists in both interfaces:

| Tool | CLI command | Web page |
|---|---|---|
| info | `avideo info` | Video info |
| heatmap | `avideo heatmap` | Heatmap |
| timeline | `avideo timeline` | Timeline |
| scenes | `avideo scenes` | Scenes |
| background | `avideo background` | Background |
| stats | `avideo stats` | Pixel stats |
| barcode | `avideo barcode` | Barcode |
| contact | `avideo contact-sheet` | Contact sheet |
| flow | `avideo flow` | Optical flow |
| flicker | `avideo flicker` | Flicker |
| compare | `avideo compare` | Compare |
| report | `avideo report` | Report |

- Every parameter in this file has a CLI flag ([spec-cli.md](spec-cli.md) §4–5, or the generic `--set KEY=VALUE`) and a web control ([spec-web.md](spec-web.md) §8, or an export option in §6.4).
- The only interface-specific settings are display concerns: terminal colors in the CLI; theme and view modes in the web app.
