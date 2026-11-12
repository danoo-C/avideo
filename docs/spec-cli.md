# avideo — Specification (CLI)

This file specifies the command-line interface: commands, flags, terminal design, screens, non-interactive behavior, exit codes and configuration commands.

- Every analysis parameter is defined in [spec.md](spec.md). This file maps flags to those parameter keys and never redefines them.
- The visual reference is the **CLI** row of the drafts canvas (*avideo UI drafts*). Where the drafts and this spec differ, this spec wins.

---

## 1. Principles

1. **Modern, colorful and genuinely good-looking.** Color carries meaning (commands, flags, values, success, warnings), not decoration. Rounded panels, clear hierarchy, nothing noisy.
2. **Live and informative.** Long runs show what is happening: a live preview of the result, stats, activity and a precise progress bar.
3. **Friendly errors.** Every error says what went wrong, why, and what to do next, with "did you mean" suggestions.
4. **Scriptable.** No live UI when output is piped. `--json` gives machine-readable output; stdout and stderr are used consistently; exit codes are meaningful.
5. **Same results as the web app.** Flags map 1:1 to the shared settings, and `--config` accepts files exported from the web app.

Built with **Typer** (commands, parsing, completion) and **Rich** (all rendering).

---

## 2. Look and feel

### 2.1 Color tokens

Text uses the terminal's **default foreground**. avideo never paints large backgrounds; background colors appear only in small badges and chips.

| Token | Dark terminal | Light terminal | Used for |
|---|---|---|---|
| `brand.1`…`brand.6` | `#A78BFA` `#C084FC` `#F472B6` `#FB7185` `#FB923C` `#FACC15` | `#6D28D9` `#7E22CE` `#BE185D` `#BE123C` `#C2410C` `#A16207` | Wordmark letters, one color per letter |
| `accent` | `#A78BFA` | `#6D28D9` | Neutral panel titles, version badge, arrows |
| `command` | `#22D3EE` bold | `#0E7490` bold | Command names, paths, URLs |
| `flag` | `#FACC15` | `#A16207` | Option names |
| `dim` | `#7D8596` | `#6B7280` | Labels, metavars, hints, secondary text |
| `success` | `#4ADE80` | `#15803D` | ✓, completed progress, done states |
| `warning` | `#FACC15` | `#A16207` | `!` warnings (always with the `!` glyph, never color alone) |
| `error` | `#F87171` | `#B91C1C` | ✗ errors, error panel borders |
| `info` | `#60A5FA` | `#1D4ED8` | JSON keys, HTTP verbs in the serve log |
| `progress` | `#F472B6` | `#BE185D` | Progress bar fill while running |
| `track` | `#2A2F3A` | `#D1D5DB` | Unfilled progress bar |

**Command group colors** (panel borders in help, tool badges):

| Group | Color |
|---|---|
| Analyze | `brand.3` pink |
| Extract | `brand.5` orange |
| Inspect & output | `success` green |
| Manage | `dim` gray |

**Pipeline chips** cycle through violet, pink, orange, yellow, cyan and green text on a darkened tint of the same hue (truecolor only).

**Theme detection** (`--theme auto|dark|light`, env `AVIDEO_THEME`):

1. explicit flag or env var
2. `COLORFGBG`
3. an OSC 11 background query when the terminal answers within 50 ms
4. otherwise dark

### 2.2 Color depth

| Level | Detection | Behavior |
|---|---|---|
| Truecolor | `COLORTERM=truecolor`/`24bit`, or known terminals | Full palette, half-block previews in real colormap colors |
| 256 colors | `TERM` with `256color` | Palette mapped to the nearest 256-color entries; previews quantized |
| 16 colors | basic `TERM` | Named ANSI colors; previews use the ASCII ramp |
| None | `NO_COLOR`, `--color never`, or not a TTY (with `--color auto`) | No color at all; layout unchanged |

`--color auto|always|never` (default `auto`). `FORCE_COLOR` forces color.

### 2.3 Glyphs and ASCII fallback

Unicode glyphs are used when the output encoding is UTF-8; otherwise, or with `--ascii` (env `AVIDEO_ASCII=1`), the ASCII fallback is used.

| Element | Unicode | ASCII |
|---|---|---|
| Spinner | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | `\|/-\` |
| Progress bar | `━` fill, `╸` head | `=` fill, `>` head |
| Success / error / warning | `✓` `✗` `!` | `ok` `x` `!` |
| Arrow | `→` `➜` | `->` |
| Panels | rounded box (`╭╮╰╯─│`) | `+-\|` |
| Tree | `├─` `└─` | `\|-` `` `- `` |
| Sparkline | `▁▂▃▄▅▆▇█` | `_.-=*#` |
| Image preview | `▀` half-blocks, fg = top pixel, bg = bottom pixel | density ramp ` .:-=+*#%@` |
| Wordmark | 2-row block letters (see 6.1) | plain bold `avideo` |

### 2.4 Typography and layout

- **Bold** marks key values (counts, percentages, resolution). Italics, blinking and underline are not used, except that URLs and output paths are underlined when the terminal supports hyperlinks (OSC 8, clickable).
- **Width adaptation:**
  - minimum supported width: 60 columns
  - 60–99 columns: panels stack vertically
  - 100+ columns: two-column layouts (e.g. preview | stats)
  - maximum content width: 120 columns
- Numbers use thousands separators (`7,560`); times use `MM:SS.f` (`HH:MM:SS.f` over an hour); sizes use KB/MB/GB with one decimal.

---

## 3. Command structure

```
avideo <command> [options] <input…>
avideo --version | --help
```

### 3.1 Commands

| Group | Command | Inputs |
|---|---|---|
| Analyze | `heatmap`, `timeline`, `scenes`, `flow`, `flicker` | one or more videos |
| Analyze | `compare` | exactly two videos `A B` |
| Extract | `background`, `stats`, `barcode`, `contact-sheet` | one or more videos |
| Inspect & output | `info` | one or more videos |
| Inspect & output | `report` | one or more videos |
| Inspect & output | `serve` | optional folder, video, output folder or `.avideo` session |
| Manage | `presets`, `config`, `cache` | subcommands (section 8) |

### 3.2 Inputs and batch mode

- Inputs may be files, globs (quoted globs are expanded by avideo, so they work on every shell) or directories.
- Directories include video files directly inside them. Add `--recursive` to include subfolders. Video files are recognized by extension (`mp4 mov mkv avi webm m4v mts m2ts ts mpg mpeg wmv flv y4m`) and probed.
- With more than one input, the command runs once per input (**batch mode**):
  - inputs are processed one after another
  - each run may use parallel workers
  - `--fail-fast` stops at the first failure; the default `--continue-on-error` keeps going and reports failures at the end
  - a summary table is shown and `summary.csv` is written to the output root

### 3.3 Where options go

Options may come before or after inputs: `avideo heatmap cam.mp4 --resize 50%` and `avideo heatmap --resize 50% cam.mp4` are equivalent. Global options are accepted by every analysis command.

---

## 4. Global options

Accepted by every analysis command (`heatmap` … `report`, `info` where relevant).

### 4.1 Input — keys from spec.md §5

| Flag | Key |
|---|---|
| `--start TIME` | `input.start` |
| `--end TIME` | `input.end` |
| `--step N` | `input.step` |
| `--max-frames N` | `input.max_frames` |
| `--resize SCALE` | `input.resize` |
| `--roi ROI` | `input.roi` |
| `--roi-crop` | `input.roi_crop = true` |
| `--rotate auto\|0\|90\|180\|270` | `input.rotate` |
| `--deinterlace auto\|on\|off` | `input.deinterlace` |
| `--stabilize off\|translate\|affine\|homography` | `input.stabilize` |
| `--normalize-exposure off\|mean\|histogram` | `input.normalize_exposure` |
| `--backend auto\|opencv\|pyav` | `input.backend` |

### 4.2 Output, performance and settings

| Flag | Short | Key / effect |
|---|---|---|
| `--out DIR` | `-o` | `output.dir` |
| `--on-exists overwrite\|increment\|fail` | | `output.on_exists` |
| `--workers N\|auto` | `-w` | `parallel.workers` |
| `--warmup N\|auto` | | `parallel.warmup` |
| `--preview` | | Preview quality (spec.md §12.3) |
| `--cache` / `--no-cache` | | Use the result cache (default off in the CLI) |
| `--config FILE` | `-c` | Load a settings file: TOML, JSON or an avideo PNG. Repeatable; later files win. |
| `--preset NAME` | `-p` | Load a built-in or user preset |
| `--set KEY=VALUE` | | Set any parameter by key, e.g. `--set heatmap.output.vmax=p99.5`. Repeatable. Guarantees every key is reachable even without a dedicated flag. |
| `--save-config FILE` | | Write the resolved settings (non-default values) to FILE |
| `--dry-run` | | Validate, print the resolved settings and the plan (inputs, frames, outputs), then exit without processing |
| `--session FILE` | | Also write a `.avideo` session |
| `--video PATH` | | When loading a session via `--config`, the new location of its video |

### 4.3 Interface

| Flag | Short | Effect |
|---|---|---|
| `--json` | | Machine-readable output (section 7.3); implies no live view |
| `--events` | | Stream live events (spec.md §11, without images) as JSON Lines to stdout |
| `--quiet` | `-q` | No live view and no summary; only errors (stderr) |
| `--no-live` | | Plain progress lines instead of the live view |
| `--verbose` | `-v` | More detail; `-vv` adds debug logs and tracebacks |
| `--color auto\|always\|never` | | Section 2.2 |
| `--theme auto\|dark\|light` | | Section 2.1 |
| `--ascii` | | Section 2.3 |
| `--recursive` | `-r` | Section 3.2 |
| `--continue-on-error` / `--fail-fast` | | Section 3.2 |
| `--help` | `-h` | Command help |

Top level only: `--version`, `--install-completion`, `--show-completion`.

---

## 5. Command reference

Each table maps flags to parameter keys in [spec.md](spec.md). Boolean keys whose default is `true` get a `--no-…` flag; those whose default is `false` get a plain flag. List values are comma-separated (`--outputs png,overlay,npy`). Choice values are validated with did-you-mean suggestions.

### 5.1 `avideo info`

| Flag | Key |
|---|---|
| `--exact` | `info.exact` |
| `--all-streams` | `info.all_streams` |

Prints the info panel (section 6.3). With `-o DIR` it also writes `info.json` into the video's output folder.

### 5.2 `avideo heatmap`

**Color space and preprocess**

| Flag | Key |
|---|---|
| `--space gray\|rgb\|hsv\|lab\|rgbn` | `heatmap.space` |
| `--blur SIGMA` | `heatmap.preprocess.blur` |

**Threshold**

| Flag | Key |
|---|---|
| `--thresh VALUES` | `heatmap.threshold.enabled = true`, `method = fixed`, `values = VALUES` (e.g. `128` or `128,140,96`) |
| `--thresh otsu\|adaptive\|range` | `heatmap.threshold.enabled = true`, `method = …` |
| `--no-thresh` | `heatmap.threshold.enabled = false` (overrides a config file) |
| `--levels N` | `heatmap.threshold.levels` |
| `--hysteresis N` | `heatmap.threshold.hysteresis` |
| `--otsu-scope video\|frame` | `heatmap.threshold.otsu_scope` |
| `--adaptive-block N` | `heatmap.threshold.adaptive_block` |
| `--adaptive-offset N` | `heatmap.threshold.adaptive_offset` |
| `--range-lower COLOR` | `heatmap.threshold.range_lower` |
| `--range-upper COLOR` | `heatmap.threshold.range_upper` |
| `--range-invert` | `heatmap.threshold.range_invert` |

**Change detection**

| Flag | Key |
|---|---|
| `--reference previous\|frame\|background` | `heatmap.change.reference` |
| `--reference-frame TIME` | `heatmap.change.reference_frame` |
| `--bg-model average\|mog2` | `heatmap.change.background_model` |
| `--bg-rate RATE` | `heatmap.change.background_rate` |
| `--distance channel\|euclidean\|deltae` | `heatmap.change.distance` |
| `--delta N\|auto` | `heatmap.change.delta` |
| `--combine any\|all\|majority\|sum\|separate` | `heatmap.change.combine` |

**Cleanup**

| Flag | Key |
|---|---|
| `--open N` | `heatmap.cleanup.open` |
| `--min-run N` | `heatmap.cleanup.min_run` |

**Output**

| Flag | Key |
|---|---|
| `--norm raw\|percent\|log` | `heatmap.output.normalize` |
| `--vmax auto\|N\|pN` | `heatmap.output.vmax` |
| `--colormap NAME` | `heatmap.output.colormap` |
| `--no-colorbar` | `heatmap.output.colorbar = false` |
| `--outputs LIST\|all` | `heatmap.output.files` (`all` = every output that applies) |
| `--image-size source\|processing` | `heatmap.output.image_size` |
| `--overlay-base median\|first\|middle\|TIME` | `heatmap.output.overlay_base` |
| `--overlay-opacity F` | `heatmap.output.overlay_opacity` |
| `--overlay-mode weighted\|uniform` | `heatmap.output.overlay_mode` |
| `--composite-scale joint\|independent` | `heatmap.output.composite_scale` |
| `--timelapse-snapshots N` | `heatmap.output.timelapse_snapshots` |
| `--timelapse-fps N` | `heatmap.output.timelapse_fps` |
| `--timelapse-scale final\|running` | `heatmap.output.timelapse_scale` |
| `--rolling-window DURATION` | `heatmap.output.rolling_window` |
| `--rolling-mode decay\|exact` | `heatmap.output.rolling_mode` |

### 5.3 `avideo timeline`

Accepts all **color space, preprocess, threshold, change detection and cleanup** flags of `heatmap` (they set the same `heatmap.*` keys), plus:

| Flag | Key |
|---|---|
| `--smooth DURATION` | `timeline.smooth` |
| `--active-above PCT` | `timeline.active_above` |
| `--min-segment DURATION` | `timeline.min_segment` |
| `--peak-prominence PCT` | `timeline.peak_prominence` |
| `--max-peaks N` | `timeline.max_peaks` |

### 5.4 `avideo scenes`

| Flag | Key |
|---|---|
| `--cut-threshold F` | `scenes.cut_threshold` |
| `--no-cut-adaptive` | `scenes.cut_adaptive = false` |
| `--min-scene DURATION` | `scenes.min_scene` |
| `--frozen-max-change PCT` | `scenes.frozen_max_change` |
| `--frozen-min DURATION` | `scenes.frozen_min` |
| `--black-max-luma N` | `scenes.black_max_luma` |
| `--black-min-pixels PCT` | `scenes.black_min_pixels` |
| `--black-min DURATION` | `scenes.black_min` |
| `--no-thumbnails` | `scenes.thumbnails = false` |
| `--thumb-width N` | `scenes.thumb_width` |

### 5.5 `avideo background`

| Flag | Key |
|---|---|
| `--method median\|mode\|mean` | `background.method` |
| `--samples N` | `background.samples` |
| `--foreground-frame TIME` | `background.foreground_frame` |

### 5.6 `avideo stats`

| Flag | Key |
|---|---|
| `--space gray\|rgb` | `stats.space` |
| `--measures LIST` | `stats.measures` |
| `--colormap NAME` | `stats.colormap` |
| `--stuck-max-std F` | `stats.stuck_max_std` |
| `--hot-min-mean F` | `stats.hot_min_mean` |
| `--dead-max-mean F` | `stats.dead_max_mean` |

### 5.7 `avideo barcode`

| Flag | Key |
|---|---|
| `--mode mean\|dominant` | `barcode.mode` |
| `--width N` | `barcode.width` |
| `--height N` | `barcode.height` |
| `--style solid\|squeezed` | `barcode.style` |

### 5.8 `avideo contact-sheet`

| Flag | Key |
|---|---|
| `--cols N` | `contact.cols` |
| `--rows N` | `contact.rows` |
| `--pick even\|scenes` | `contact.pick` |
| `--thumb-width N` | `contact.thumb_width` |
| `--no-timestamps` | `contact.timestamps = false` |
| `--no-header` | `contact.header = false` |
| `--format png\|jpg` | `contact.format` |

### 5.9 `avideo flow`

| Flag | Key |
|---|---|
| `--pyr-scale F` | `flow.pyr_scale` |
| `--levels N` | `flow.levels` |
| `--winsize N` | `flow.winsize` |
| `--iterations N` | `flow.iterations` |
| `--poly-n 5\|7` | `flow.poly_n` |
| `--poly-sigma F` | `flow.poly_sigma` |
| `--min-magnitude F` | `flow.min_magnitude` |
| `--colormap NAME` | `flow.colormap` |
| `--arrow-spacing N` | `flow.arrow_spacing` |

### 5.10 `avideo flicker`

| Flag | Key |
|---|---|
| `--window N` | `flicker.window` |
| `--overlap F` | `flicker.overlap` |
| `--min-hz F` | `flicker.min_hz` |
| `--max-hz F\|nyquist` | `flicker.max_hz` |
| `--min-amplitude F` | `flicker.min_amplitude` |
| `--colormap NAME` | `flicker.colormap` |

### 5.11 `avideo compare A B`

| Flag | Key |
|---|---|
| `--align none\|offset\|auto` | `compare.align` |
| `--offset DURATION` | `compare.offset` |
| `--delta N` | `compare.delta` |
| `--metrics LIST` | `compare.metrics` |
| `--worst N` | `compare.worst` |
| `--colormap NAME` | `compare.colormap` |

Output folder: `<out>/<stemA>__vs__<stemB>/`.

### 5.12 `avideo report`

| Flag | Key |
|---|---|
| `--tools LIST` | `report.tools` |
| `--no-self-contained` | `report.self_contained = false` |
| `--title TEXT` | `report.title` |
| `--open` | Open the report in the default browser when done |

Per-tool parameters come from `--config`, `--preset` and `--set` (tool flags like `--delta` are not accepted, because they would be ambiguous across tools).

### 5.13 `avideo serve`

Starts the local web app. Its options and behavior are specified in [spec-web.md](spec-web.md) §2. The terminal side (banner and request log) is specified in section 6.8 below.

---

## 6. Screens

All screens follow the drafts. Examples use the 100-column layout.

### 6.1 Main help — `avideo --help` / `avideo`

1. Prompt echo is the shell's; avideo prints from the next line.
2. **Wordmark:** 2-row block letters, one color per letter (`brand.1`…`brand.6`):
   ```
   ▄▀█ █ █ █ █▀▄ █▀▀ █▀█
   █▀█ ▀▄▀ █ █▄▀ ██▄ █▄█
   ```
   To the right: version badge (`accent` on a dark violet tint) and the tagline in `dim`: *Video analysis toolkit · heatmaps, motion, scenes and more*.
3. **Usage line:** `USAGE` badge, then `avideo <command> [options] <video…>`, with `<command>` in `command` color, `[options]` in `flag` color and `<video…>` dim.
4. **Command panels:** one rounded panel per group (title in the border, border in the group color). Two-column grid: command name (`command`, bold) and a one-line description. Analyze is full width; Extract and Inspect & output sit side by side at ≥ 100 columns; Manage is a compact last row.
5. **Common options panel:** neutral border; flags in `flag` color, metavars dim, descriptions plain, defaults dim in brackets.
6. **Examples:** three examples with a green `$`.
7. Footer hint: `Run avideo <command> --help to see every option of a command.`

### 6.2 Command help — `avideo heatmap --help`

- Header line: tool badge (group color background), the command's one-line description, and a 2–3 line explanation.
- Usage line as above.
- Option panels by section, in pipeline order:
  - Input (global input flags, collapsed into one line: `--start --end --step --max-frames --resize --roi … (see avideo --help)`)
  - Color space & preprocess
  - Threshold
  - Change detection
  - Cleanup
  - Output
  - Run (workers, preview, config, preset, set, save-config, dry-run)
  - Interface
- Each option shows flag, metavar, description, allowed values (dim) and default (dim, in brackets). Texts come from the settings model's help strings.
- Examples panel: 3–5 realistic examples for that command.
- Footer: link to the settings key reference (`avideo config show heatmap`).

### 6.3 `avideo info`

- Panel titled with the file name (`accent` border) holding a two-column key/value grid:
  - File
  - Duration (bold yellow)
  - Video (resolution and fps bold cyan)
  - Pixels
  - Color
  - Scan
  - Bitrate
  - Audio
  - Other streams (only when present)
- **Checks row:** green `✓` items that passed (constant frame rate, no rotation, fast seeking).
- **Warnings:** one line each, yellow `!`, a short title in yellow, a plain-language explanation and a dim `Tip:` with the flag to use.
- Several inputs: one panel per file, then a compact comparison table (name, duration, resolution, fps, codec, size, warnings count).

### 6.4 Live view (running analysis)

Rendered with Rich Live at 10 Hz. It never takes more than 5% of runtime: snapshots for the preview are requested at 4 Hz.

```
⠹ HEATMAP  street-cam_2026-11-03.mp4   1920×1080 → 960×540 · 7,560 frames · step 1
resize 50% → blur 1 → binarize RGB 128·140·96 ±12 → Δ>12 vs previous → majority → open 3px

╭ Live preview  60×34 ─────────────────────────╮ ╭ Now ─────────────────────────╮
│ (half-block image of the current result)     │ │ frame    3,412 / 7,560       │
│                                              │ │ time     01:53.8 / 04:12.2   │
│                                              │ │ speed    214 fps             │
│ inferno 0 ████████████ 412 changes           │ │ changed  3.8% this frame     │
╰──────────────────────────────────────────────╯ │ hottest  412 changes         │
                                                 │ static   61.2% of pixels     │
                                                 │ activity ▂▃▅▇▅▃▂▁▂▅█▇▅▃      │
                                                 ╰──────────────────────────────╯
━━━━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━━━━━━━━━  45%  elapsed 0:16  ETA 0:19
ctrl+c stops and keeps partial results · --quiet hides this live view
```

**Header line:** spinner (`progress` color), tool badge, file name (bold), dim summary of resolution change, frame count and step.

**Pipeline chips:** the active pipeline, built from the resolved settings, only listing steps that are on. Examples:
- `resize 50%`
- `stabilize affine`
- `blur 1`
- `binarize RGB 128·140·96 ±12` or `otsu HSV` or `range HSV`
- `Δ>12 vs previous` or `Δ auto (9)` or `vs background`
- `majority`
- `open 3px`
- `min run 2`

**Preview panel:**
- Size: width = min(available width of the left column, 80) cells; height = width × (H ÷ W) ÷ 2 rows (each cell shows 2 pixels vertically), at most 24 rows.
- The image is downsampled with area averaging. Colors come from the tool's colormap, or are true colors for image previews.
- Below the image: a colormap legend (min, 24 color cells, max with unit).

**What the preview shows per tool:**

| Tool | Preview panel | Stats panel |
|---|---|---|
| heatmap | Accumulated heatmap | frame, time, speed, changed, hottest, static, activity sparkline |
| timeline | Full-width bar chart of % changed so far (`▁…█`) with active segments in `success` | current %, active time, peaks found |
| scenes | Last 6 detected events (time, type badge, score) | scenes, cuts, frozen, black counts |
| background | Current background estimate (true color) | samples taken |
| stats | First selected measure | mean std so far, stuck/hot so far |
| barcode | The barcode so far, one row of colored blocks across the width | columns filled |
| contact-sheet | Timestamps captured (as a list) | thumbnails done |
| flow | Mean direction map (HSV) | mean speed, dominant direction with arrow glyph `→↗↑↖←↙↓↘` |
| flicker | Frequency map after the first window; before that a window progress bar | windows done, flickering pixels, strongest Hz |
| compare | PSNR and SSIM sparklines | current and min PSNR / SSIM |
| report | One row per tool with its own progress bar and status | — |

**Progress line:**
- Bar width adapts to the terminal (≥ 20 cells). The fill is `progress` while running, `success` when done and `warning` when stopped.
- After the bar: percent (bold), elapsed time and ETA (`command` color). In batch mode it also shows `file 2/4`.

**Hint line:** dim, one line, contextual.

**Warnings during a run** print above the live area, so they stay in scrollback: `! W004 noisy video (σ ≈ 7.2) — try --delta auto or --blur 1`.

### 6.5 Finished summary

1. Final progress line (full bar in `success`, `100%`, frames, total time).
2. Success line: green bold `✓ Heatmap done`, then dim `7,560 frames in 0:35 · 216 fps`.
3. **Result panel** (`success` border): a key/value grid of the tool's statistics (spec.md §6), with the most important value per row in bold color. For heatmap: hottest pixel (+ location), mean, never changed, busiest frame, quietest segment, and `delta auto → 9` when used.
4. **Thumbnail panel** beside the result (≥ 100 columns): a half-block rendering of the main output image (e.g. `heatmap.png`).
5. **Saved files:** `Saved to <path>` (underlined, clickable), then a tree with one row per file: name (colored by kind: images pink, data orange, settings violet), a dim description and a right-aligned size.
6. **Warnings recap** (if any): one line per warning code with its count.
7. **Next step** (one line, `accent` arrow), e.g. `→ Explore it in the web app: avideo serve ./avideo-out/street-cam_2026-11-03`.

### 6.6 Batch

- **While running:** a compact table of all inputs (status column: `queued` dim, a spinner while running, `✓ done` green, `✗ failed` red, `! warnings` yellow) above the live view of the current file. The progress line shows file progress and overall progress (`file 2/4 · overall 38%`).
- **When finished:** a rounded table with columns `video`, `frames`, `time`, then 2–3 key stats of the tool (heatmap: `hottest`, `static`), then `status`. Header in `accent` bold.
- Below: `✓ 4 videos · 44,310 frames · 3:26 total · summary.csv written` (or `✗ 1 of 4 failed`, followed by the error panels of the failed inputs).

### 6.7 Errors

Every error is a rounded panel with an `error` border, titled `✗ <short title>`. Body:

1. What happened, with the offending value in bold `error` color.
2. Why or what is allowed (dim lead-in, e.g. `Thresholds go from 0 to 255.`).
3. A suggestion: `Did you mean street-cam/street-cam_2026-11-03.mp4?` (file suggestions from fuzzy matching in the input's folder and one level below; option and choice suggestions from fuzzy matching). Or `Try:` with a corrected example command.
4. With `-v`: the error code and the traceback below the panel.

Usage errors (unknown flag, missing argument) use the same panel and include the command's usage line. Error panels go to stderr.

### 6.8 `avideo serve`

```
╭───────────────────────────────────────────────────────╮
│ avideo web  running locally · v0.1.0                  │
│                                                       │
│ ➜  Local   http://127.0.0.1:8765/?t=…                 │
│ ➜  Folder  ~/videos (read-only, nothing leaves this machine) │
│                                                       │
│ press o to open the browser · q to quit               │
╰───────────────────────────────────────────────────────╯
21:14:02  GET   /                                   200 · 3 ms
21:14:03  WS    /api/ws                             connected
21:14:09  RUN   heatmap street-cam_2026-11-03.mp4   preview 25%
21:15:06  DONE  heatmap · 7,560 frames              0:35
21:15:20  SAVE  settings → street-cam.toml          1 KB
```

- Banner with an `accent` border: `avideo web` badge, the local URL (underlined, clickable, includes the session token) and the served folder.
- Key hints: `o` opens the browser; `q` or ctrl+c quits. These are read only while the terminal is in focus; there is no global hook.
- **Request log** (one line per event): time (dim) and verb, colored by kind:
  - `GET`/`POST`/`WS` in `info`
  - `RUN` in `progress`
  - `DONE` in `success`
  - `SAVE`/`EXPORT` in `warning`
  - `ERROR` in `error`
- Static file requests are hidden unless `-v`.

### 6.9 Interrupt

- **First ctrl+c:** the live view's hint line changes to `Stopping… saving partial results (press ctrl+c again to quit immediately)`. The run finishes the current frame and writes outputs. The summary then starts with `■ Stopped at frame 3,412 / 7,560 — partial results saved` in `warning` color, and the bar is drawn in `warning`.
- **Second ctrl+c:** exits immediately without writing.

Exit code 130 in both cases.

---

## 7. Non-interactive behavior

### 7.1 Streams

| Content | Stream |
|---|---|
| Summaries, tables, info panels, JSON | stdout |
| Live view, progress lines, warnings, errors, logs | stderr |

### 7.2 Not a TTY

When stderr is not a TTY, or `CI` is set:

- there is no live view
- colors are off (unless `--color always`)
- progress is printed as plain lines to stderr at every 10%:
  ```
  heatmap street-cam_2026-11-03.mp4  40%  3,024/7,560  214 fps  ETA 0:21
  ```
- the final summary is printed to stdout as plain text without panels, but with the same content.

`--no-live` forces this mode on a TTY.

### 7.3 `--json`

stdout contains **only JSON Lines**: one JSON object per input, written when that input finishes.

- **Analysis commands:** the run record (spec.md §9.3), with `outputs` as absolute paths.
- **`info`:** `{"path", "meta", "checks", "warnings"}`.
- **Failure:** `{"path", "error": {"code", "title", "message", "suggestion"}}`.
- **`--dry-run --json`:** `{"path", "settings", "plan": {"frames", "outputs", "workers"}}`.

Progress still goes to stderr unless `--quiet`.

### 7.4 `--events`

Streams the live events of spec.md §11 to stdout as JSON Lines (`{"event": "Progress", …}`), without image payloads. It is meant for wrapping avideo in other tools. It cannot be combined with `--json`.

### 7.5 Logging

- `-v`: info logs (decoder chosen, workers, chunk plan, cache hits) to stderr.
- `-vv`: debug logs and full tracebacks.
- Logs never go to stdout.

---

## 8. Manage commands

### 8.1 `avideo presets`

| Command | Effect |
|---|---|
| `avideo presets list` | Table of built-in and user presets: name, source (built-in/user), tools they cover, description |
| `avideo presets show NAME` | Print the preset as highlighted TOML |
| `avideo presets save NAME [--from FILE] [flags…]` | Save a user preset from a settings file and/or flags (non-default values only) |
| `avideo presets delete NAME` | Delete a user preset (asks for confirmation unless `--yes`) |

### 8.2 `avideo config`

| Command | Effect |
|---|---|
| `avideo config show [TOOL]` | Print the effective settings (defaults + user config + env) as TOML with a dim comment per key (help text, allowed values). Without TOOL: `[input]`, `[output]`, `[parallel]`. |
| `avideo config path` | Print the locations of the user config, presets, cache and data folders |
| `avideo config edit` | Open the user config file in `$EDITOR` (creates it with commented defaults if missing) |
| `avideo config check FILE` | Validate a settings file and report problems (same messages as runs) |

### 8.3 `avideo cache`

| Command | Effect |
|---|---|
| `avideo cache info` | Location, size, entry count, limit |
| `avideo cache clear` | Delete all cached results (asks unless `--yes`) |

---

## 9. Configuration sources

The CLI adds environment variables to the precedence in spec.md §8.2. They sit **between the user config file and presets**:

defaults < user config < **environment** < preset < `--config` files < `--set` < dedicated flags

| Variable | Effect |
|---|---|
| `AVIDEO_CONFIG` | Path of the user config file |
| `AVIDEO_OUT` | `output.dir` |
| `AVIDEO_WORKERS` | `parallel.workers` |
| `AVIDEO_BACKEND` | `input.backend` |
| `AVIDEO_CACHE_DIR` | Cache folder |
| `AVIDEO_THEME` | `--theme` |
| `AVIDEO_ASCII` | `--ascii` when `1` |
| `NO_COLOR`, `FORCE_COLOR` | Standard color switches |
| `COLUMNS` | Overrides the detected terminal width |

---

## 10. Exit codes

| Code | Meaning | Error codes (spec.md §13) |
|---|---|---|
| `0` | Success (warnings allowed) | — |
| `1` | Internal error | `E500` |
| `2` | Usage or settings error | `E100`, `E101`, `E400`, unknown flags |
| `3` | Input error | `E200`, `E201`, `E202` |
| `4` | Decode error | `E203` |
| `5` | Output error | `E300`, `E301` |
| `6` | Batch finished with some inputs failed | — |
| `130` | Interrupted (ctrl+c) | — |

---

## 11. Shell completion

`avideo --install-completion` sets up completion for bash, zsh, fish and PowerShell. It completes:

- commands and subcommands
- flags, and choice values (`--combine m<TAB>` → `majority`)
- colormap and preset names
- `--set` keys (`--set heatmap.ch<TAB>`)
- input paths, filtered to video files and folders

---

## 12. Testing (CLI)

- **Flag coverage:** a test walks every settings key in the core model and asserts it is reachable by a dedicated flag or `--set`, and that every flag maps to an existing key.
- **Parsing:** each value type (Time, Duration, Scale, ROI, ChannelList, Choice) with valid and invalid inputs; error messages snapshot-tested.
- **Screens:** snapshot tests of every screen in section 6, rendered by Rich at widths 60, 100 and 140, in truecolor, 16-color, no-color and ASCII modes (compared as text and SVG).
- **Behavior:** non-TTY output, `--json` lines validated against JSON schemas, `--events` stream order, exit codes for each error class, ctrl+c handling (partial outputs and the `partial` status), batch with mixed failures.
- **Round-trip:** `--save-config` then `--config` reproduces identical resolved settings; a web-exported TOML runs unchanged.

---

## 13. Examples

```bash
# What is in this video?
avideo info cam.mp4

# Default heatmap
avideo heatmap cam.mp4

# Grayscale binarization at 120, ignore small noise, log scale
avideo heatmap cam.mp4 --thresh 120 --hysteresis 8 --open 3 --norm log

# Color thresholding per channel, count a change when 2 of 3 channels flip
avideo heatmap cam.mp4 --space rgb --thresh 128,140,96 --combine majority

# Track a red object (hue wraps around)
avideo heatmap cam.mp4 --space hsv --thresh range --range-lower 240,120,80 --range-upper 10,255,255

# Handheld footage, automatic noise threshold, every output
avideo heatmap walk.mov --stabilize affine --delta auto --outputs all

# Settings tuned in the web app, run on a whole folder
avideo heatmap street-cam/ --config street-cam.toml -o results/

# Only minutes 1–3, every 2nd frame, half size, machine-readable
avideo heatmap cam.mp4 --start 1:00 --end 3:00 --step 2 --resize 50% --json

# When is there activity?
avideo timeline cam.mp4 --active-above 2 --smooth 0.5s

# Find cuts and black frames
avideo scenes film.mkv --min-scene 1s

# Compare two encodes, auto-align, save the 10 worst frames
avideo compare original.mp4 encoded.mp4 --align auto --worst 10

# One report with everything
avideo report cam.mp4 --open

# Open the web app on a folder
avideo serve ~/videos
```
