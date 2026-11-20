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
  (can be changed per line with the “reference” buttons under the originals);
- `usage_cmd`, `usage_label` — optional command that prints the generation service's credit counter as JSON
  `{"used": …, "limit": …, "reset": <unix time>}` (e.g. a small script that asks ElevenLabs with the
  project's own key). ByEar runs it before and after each agent job and shows the difference as the
  generation cost; the remaining credits appear on the left rail. API keys stay in the project — ByEar
  never reads them.

The left rail also shows the **Claude plan limits**: how much of the 5-hour window is used (big number) and of
the week (below), with reset times in the tooltip. ByEar takes them from Claude Code's own stream
(`rate_limit_event`), so it never touches your login; click the block to refresh. Before a job is sent at
≥ 90 % (or when a limit is reached) ByEar asks first.

Audio, API keys and local data (queue, logs, edit history) never go into the repository — see `.gitignore`.

## Tempo without pitch change

Under the volume row: “Довжина ±%” changes the tempo of the whole file or of the selected region, and
“Довжина як EN/JA” stretches or squeezes the whole file to the reference length; quick “−5% / +5%” buttons
appear on a selection. The pitch stays the same (ffmpeg `atempo`, clean for speech within about ±25 %);
⌘Z undoes. The same is available from the command line for agents and scripts:

```
python3 tempo.py in.wav out.wav --speed 1.1                     # 10 % faster (shorter)
python3 tempo.py in.wav out.wav --length 3.2                    # whole file 3.2 s long
python3 tempo.py in.wav out.wav --speed 0.9 --start 1 --end 2.5 # only that region, slower
```

## Dictation

The “Диктувати” button next to the comment (or the D key) records your voice and a **local Whisper**
(whisper.cpp `whisper-cli` + a multilingual ggml model in `~/.cache/whisper/`) turns it into text at the cursor.
Nothing leaves the machine. Without Whisper the button is disabled; hovering it explains why and links to the
install guide at `/docs/whisper.html` (`static/docs/`). Settings: `dictation_lang` (default `uk`),
`whisper_model`, `dictation_prompt` (names Whisper should spell right).

## Echo

“Луна” row: amount (%) and tail (seconds until it dies out), for the whole file or the selected region (a
quick “Луна” button appears on a selection). The loudness of the words stays the same; ⌘Z removes it.
10 % is barely audible, 30 % a room, 70 % a large hall. From the command line:

```
python3 echo.py in.wav out.wav --amount 30 --tail 1.0
python3 echo.py in.wav out.wav --amount 50 --tail 2 --start 1 --end 2.4
```

## After each agent job

ByEar keeps the version the agent overwrote (“▶ До правки” plays it, ⌘Z restores it) and measures pitch,
loudness and length of the new file, the previous version and the reference. Pitch is compared with the
previous version (same voice; the reference is usually another actor in another language, shown greyed for
information), loudness and length with the reference. Large differences (e.g. a pitch-shifted voice or a much
quieter take) are flagged next to the agent's reply, together with the job's token count and cost. A job that
goes over `max_job_tokens` is stopped.

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
