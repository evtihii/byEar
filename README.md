# ByEar (наСлух)

A local tool for reviewing and fixing game voice-over by ear: original and translated takes side by side,
“OK” / “Fix” marks with comments, gain and normalization edits right on the waveform (with undo),
a fix queue handled by an AI coding agent, and per-folder “ready to embed” marks.

## An add-on over an AI coding agent

ByEar does not generate or edit voice-over itself. It is a review layer on top of an AI coding agent:
you listen, mark a line “Fix” and write what is wrong; ByEar queues the job and hands it to the agent
together with the files, the line text, your comment and the chosen reference original. The agent does
the actual work in your project (regenerating takes, aligning pauses, matching loudness) following a
per-project brief, and ByEar shows you the result for the next listen.

- **Claude Code** — supported now. ByEar keeps one persistent `claude` session per app run, shows its
  context size and lets you compact it.
- **Codex** — planned (see [ROADMAP.md](ROADMAP.md)).

## Running

- **macOS app:** `zsh mac/build.sh` builds `ByEar.app` next to `server.py`. The app starts the server
  itself and stops it (together with the agent) on ⌘Q. If a server is already running, it just attaches.
- **Without the app:** `python3 server.py` (or `ByEar.command`), then open http://localhost:8765.

Requirements: Python 3.10+, `ffmpeg` / `ffprobe`; for the fix queue — [Claude Code](https://claude.com/claude-code) (`claude`).

The interface is in Ukrainian for now.

## Projects

Projects are added in the UI (the “+” button) and stored in `projects.json` (not tracked; see
`projects.example.json`). A project is a folder of lines: a folder per line with `en.wav` / `ja.wav`
(originals) and `ua.wav` (translation), or flat files like `Name_en.wav` / `Name_ua.wav`.
Feedback is stored in `summary.json` inside the project folder.

Project fields:
- `agent_cwd`, `agent_brief` — the folder the agent works in and its brief (without them the queue is off);
- `default_ref` — the original language used as the agent's reference by default
  (can be changed per line with the “reference” buttons under the originals).

Audio, API keys and local data (queue, logs, edit history) never go into the repository — see `.gitignore`.

## After each agent job

ByEar keeps the version the agent overwrote (“▶ До правки” plays it, ⌘Z restores it) and measures pitch,
loudness and length of the new file against the reference and the previous version. Large differences
(e.g. a pitch-shifted voice or a much quieter take) are flagged next to the agent's reply, together with the
job's token count and cost. A job that goes over `max_job_tokens` is stopped.

## Settings (`settings.json`, created on first run)

- `model` — agent model; `timeout_min` — minutes per job; `max_job_tokens` — token limit per job;
- `auto_compact_at` — compact the agent's context above this size;
- `port` — server port (default 8765; the `PORT` environment variable wins). ByEar.app reads the same file.

## Security

The server listens on 127.0.0.1 only and refuses requests whose Host is not localhost, POSTs from other
origins and non-JSON POSTs, so a web page open in your browser cannot queue jobs for the agent.

## Tests

`python3 -m unittest discover -s tests` — starts real servers on free ports with a temporary project and a
fake agent (`tests/fake_agent.py`). Requires ffmpeg.
