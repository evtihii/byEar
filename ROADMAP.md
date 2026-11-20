# ByEar — roadmap

Ideas for later: planned ahead, not implemented yet unless checked.

## 1. Project setup agent (first: it is where a project starts)
Today the listening folders (`en.wav`, `ua.wav`, `текст.txt`) and the game pak are made by hand in a separate
Claude chat. ByEar should do both ends itself.
- [x] **“New project” window** (2026-11-20), opened when a project is created/opened — not the review window. Pick the game
  folder, or a folder that already has the audio.
- [x] **Setup agent** (2026-11-20, `setup_agent.py`), separate from the fix agent (stronger model, its own token limit). It:
  - finds the engine and audio middleware (Unreal / Unity, Wwise / FMOD …) and shows a plan before extracting
    anything: how many lines per language, a few samples to listen to;
  - after “yes”, extracts the lines into the listening structure (one folder per line, originals in every
    language the game has, transcript);
  - writes the project's own `extract` and `pack` scripts and its `projects.json` entry.
- [x] **Recipes** (`recipes/`). The SILENT HILL f path (UE5 pak → Wwise event `.bnk` → media id → `.wem` → wav, Japanese in
  its own folder, `.bnk` size fields patched on pack) becomes the first recipe; the agent starts from a known
  recipe instead of from zero. New engines become new recipes once someone has gone through them.
- [x] **Back to projects** (2026-11-20): “← Проєкти” in the setup window and above the phrase list.
- [ ] **“Embed” button** that runs the project's `pack` with the checks done by hand today: diff against the
  previous build, decode every changed file, refuse while the game is running, old pak to the Trash.
- Limits: the user's own copy of the game, mods for personal use. The agent does not look for encryption keys
  or bypass protection — if the paks are encrypted it says so and stops.
- Not in this step: generating the translated voice (TTS, voice casting) — a separate step later.

## Agents
- [x] **Claude Code** as the fix agent: one persistent `claude` session per app run, context meter, compact. (2026-11-19)
- [ ] **Codex** as an alternative agent. Make the agent layer pluggable (start / send job / interrupt /
  compact / context size), pick the agent per project in `projects.json`.
- [x] **Claude plan limits on the rail** (2026-11-20): how much of the 5-hour and the weekly window is used and
  when each resets (tooltip), a warning before sending a job at ≥ 90 % or when the limit is reached. Taken from
  Claude Code's own `rate_limit_event` in the agent stream and kept in `limits.json`; on start (if older than an
  hour) or on click ByEar asks a tiny Haiku “ok” to refresh. No account login or token handling.
- [ ] **Codex plan limits** the same way, once Codex is an agent.

## Originals in several languages
- [x] Several original tracks per line (`en.wav`, `ja.wav` …), an “Original” group separate from
  “Translation · UA”. (2026-11-19)
- [x] “Reference for the agent” toggle buttons under the originals: one language or none; the choice is
  remembered in `summary.json` (`items[id].ref`, `"none"` = no reference), the default is the project's
  `default_ref` in `projects.json`. Sent to the agent as job fields (`ref`, `ref_file`), not as comment text. (2026-11-19)
- [ ] **Japanese transcript in `текст.txt`.** Today it holds an “English (audio): …” line. Add the same line
  for Japanese (Scribe, `language_code='ja'`) and maybe a literal translation for the reviewer.
- [ ] **Japanese originals for SILENT HILL f.** Extract the Japanese voice-over from the game pak
  (`WwiseAudio/…/Japanese`) and put `ja.wav` next to `en.wav` in the listening folders. Without it the JA
  button does not appear.

## App
- [x] **ByEar.app for macOS** (2026-11-19): a Swift shell around WKWebView (`mac/main.swift`, build with
  `zsh mac/build.sh`). Starts `server.py --no-open` itself, ⌘Q stops the server and the agent; if a server
  is already running it only attaches and leaves it alone.
- [ ] **Windows** (not now). Plan: the same thin shell in C# + WebView2. Before that, move the three
  macOS-specific spots in the server into a separate module — folder picker (`osascript`), Trash (`~/.Trash`),
  “Reveal in Finder” (`open -R`) — and add Windows versions (Recycle Bin, Explorer). Ship Python and ffmpeg
  alongside or inside the installer. Build on a Windows machine or in CI.
- [ ] English UI (the interface is Ukrainian for now).

## Quality and safety (found 2026-11-19)
- [x] **Reject cross-site requests.** Host must be localhost/127.0.0.1/[::1] with our port; POSTs must come
  from the ByEar page (Origin) and carry `application/json` — blocks CSRF and DNS rebinding.
- [x] **Verify agent results automatically.** After each job ByEar measures pitch (f0), loudness (LUFS) and
  length of the new file, the version before the edit and the reference (`analysis.py`, no numpy), and flags
  large differences next to the agent's reply.
- [x] **Previous version A/B.** The version an agent overwrote is kept (`before/`, pushed to undo history):
  “▶ До правки” plays it, ⌘Z restores it.
- [x] **Cost visible and capped.** Tokens/cost in the agent reply card; `max_job_tokens` in `settings.json`
  (default 1 000 000) stops a job that goes over.
- [x] `index.html` split into `static/app.css` + `static/js/*.js`; server tests in `tests/`.
- [x] Port from `settings.json` (`port`) or `PORT` (server and ByEar.app); old logs and “before” copies rotate
  to the Trash; language tags and names come from the server (`/api/config`), a project can add `lang_names`.
- [x] **Generation cost per job** (2026-11-20): credits spent on the generation service (ElevenLabs) via the
  project's `usage_cmd`, shown in orange next to the Claude cost; remaining credits on the left rail.
- [x] **Tempo without pitch change** (2026-11-20): whole file, a region, or fit to the reference length;
  `tempo.py` also works from the command line. Higher quality (rubberband) if ffmpeg is built with it.
- [x] **Echo with two knobs** (2026-11-20): amount and tail, whole file or region, loudness kept; `echo.py` CLI.
- [ ] Estimate the echo of the reference (tail length/level after speech) and offer “echo like EN”.
- [x] **Dictation with local Whisper** (2026-11-20): record in the page, whisper.cpp on the server, text into the
  comment; disabled with a tooltip + install guide (`/docs/whisper.html`) when Whisper is missing.
- [ ] Detect original audio pasted into the translation (e.g. English breaths) — needs audio fingerprinting.

## Settings page
- [ ] **Settings page in the app** instead of editing `settings.json` / `projects.json` by hand: agent model,
  token limit per job, auto-compact threshold, port, per-project reference language.
- [ ] **Integrations with services** (ElevenLabs first; later other TTS / speech-to-text / LLM providers):
  the reviewer just pastes an API key. ByEar then shows the credits left and the cost per job without a
  per-project `usage_cmd` script.
  - Keys are stored only on this machine, in the macOS Keychain (not in the repo, not in project folders);
    the page never reads a key back, it only shows “connected” with the last 4 characters.
  - “Check connection” button; per-project choice of which integration counts the generation cost.
  - The agent keeps using the project's own key file; the integration is for ByEar's own counters.

## Other
- [x] Documentation link on the home page: `/docs/` served from `static/docs/` (2026-11-20).
- [ ] Paths to sound banks per project (postponed).
