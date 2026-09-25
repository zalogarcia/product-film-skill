---
name: product-film
description: Make a short motion-graphics product film (16:9 master, 9:16 vertical, and a teaser, all with burned-in captions) from a product brief, with Remotion, a timeline that drives picture, captions and the audio mix, and quality gates. Use when the user asks for a product film, a launch video, a SaaS explainer, or a promo video for their product. Not for editing footage they filmed, and not for AI-generated live action clips.
---

Take "make a product film for my product" to three finished cuts: a 16:9 master, a 9:16 vertical that loops seamlessly, and a short teaser, each with karaoke captions burned in for sound off viewing. Everything is driven by ONE timeline file, every on-screen promise is sourced, and nothing ships without passing the gates.

## When to invoke

- "Make a product film / launch video / promo for my app."
- "Turn this product into a 20 second motion graphics video for Reels and YouTube."
- A product page, docs or a demo is handed over with a request for a video.

Skip for: editing a video the user recorded, generating live action footage, a single animated logo, a slide deck.

## The starter

The starter project is the `template/` folder next to this file (the repo's `install.sh` puts it there). If it is missing, the user copied only this folder: ask where they cloned the repo and use its `template/` folder.

```bash
cp -R <this skill's folder>/template <film folder>
cd <film folder>
npm ci
npm run whisper-model      # whisper.cpp users: fetches models/ggml-base.en.bin
npm run example            # proves the machine: renders the example film with no API keys
```

`npm run example` must finish before real work starts; it takes a few minutes at half resolution. Read its output and look at the contact sheets it writes to `build/frames/`.

What lives where:

| Path | What it is |
|------|------------|
| `film/brief.md`, `film/concepts.md`, `film/claims.md`, `film/script.md` | The thinking, in writing. Replace the example's. |
| `src/timeline.ts` | THE timeline: lines, events, cuts and acts, every on-screen string (COPY), sound cues, the music plan, the teaser segments. |
| `src/scenes/`, `src/ui/` | The picture. One component renders every cut; `useFilm().isV` switches the layout. |
| `src/tokens.ts`, `public/fonts/` | Colours and fonts. Use the product's own. Fonts are bundled files, never fetched at render time. |
| `film.config.json` | Voices, EQ chains, effects prompts, stills prompts, loudness target, safe zones, caption speed, banned words. |
| `pipeline/` | Every step below, one script each, all run through `npm run`. |
| `build/SOURCES.txt` | Where every asset came from. Placeholders say PLACEHOLDER. |

## Configuration

Keys come from the environment only, never from files in the project:

- `ELEVENLABS_API_KEY`: voice, music and sound effects. Without it every audio step makes a labelled placeholder.
- One voice id variable per speaker, named in `film.config.json` (`voices.<speaker>.elevenlabsVoiceEnv`, for the example `ELEVENLABS_VOICE_NARRATOR`). The user brings their own voice.
- `OPENAI_API_KEY` (optional): photographic background plates. `OPENAI_IMAGE_MODEL` picks the model (default `gpt-image-1`). Needs `pip install openai`.
- `PF_NO_KEYS=1`: force placeholders even when keys are set.
- Whisper: `whisper-cli` on PATH with `models/ggml-base.en.bin` (or `WHISPER_CPP_BIN`, `WHISPER_MODEL`), else the `whisper` command from openai-whisper (`WHISPER_PY_MODEL`, default `base.en`).

## The process

Work the steps in order. Each writes a file, so the work survives a restart and the user can review it.

### 1. Brief and product truth

Write `film/brief.md`: the product in one sentence, what it does (numbered facts only), who it is for, the ONE thing the viewer should leave with, the call to action, the cuts and their lengths. Get the facts from the product itself (its site, docs, app, code), not from marketing adjectives. Ask the user only for what the product cannot tell you: audience, call to action, voice, brand colours.

### 2. Concept, then a critic pass that kills weak hooks

Write three different concepts to `film/concepts.md`, each one paragraph with its first 2 seconds described exactly. Then run a critic pass: hand the brief and the three concepts to a reviewer that did not write them (a fresh subagent, or the user) and ask it to attack each hook for the audience and for the feed. Kill feature tours, logo openings, moods without a problem, and any hook that needs a number the brief cannot back. Record which concept survives, what the critic changed, and why.

### 3. Claims ledger

Write `film/claims.md`: one row per capability the film shows or says, with its source (a docs URL, a file and line, a screen you opened) and a status. A claim without a source gets rewritten until it is true, or cut. Invented statistics are never allowed. `npm run check:claims` enforces the ledger against the timeline.

### 4. Script, then the timeline

Write the beat sheet to `film/script.md` (time, act, picture, voice line, sound), then put it in `src/timeline.ts`:

- `LINES`: every spoken line with its id, speaker, caption text, optional `tts` spelling, start time and claim id.
- `EV`: named moments that scenes and sound cues both read.
- `CUTS`: the master and the vertical, each with its size, length and acts. The vertical is a recomposition with its own act timing, not a crop. `captions: false` on a cut renders it without burned-in captions.
- `COPY`: every string the picture shows, each with a claim id or a reserved kind (`story`, `brand`, `label`, `legal`). Scenes read text only through `T("key")`.
- `sfxFor`, `MUSIC` (global styles, one section per act, gain keyframes, the duck under speech) and `TEASER` (segments on the vertical's clock).

Retime in this file and nowhere else; picture, captions and mix all follow it.

### 5. Audio

```bash
npm run voice              # ElevenLabs TTS per line (placeholder without a key); trims silence
npm run words              # whisper word timings for the captions, with the onset correction
npm run check:timeline     # the lines as MEASURED still fit the acts, the cuts and the teaser
npm run music              # ElevenLabs music from the plan, one section per act
npm run music -- --takes 2 # two takes to choose from; then: npm run music -- --use 2
npm run sfx                # ElevenLabs sound effects from the config prompts
npm run stills             # optional OpenAI plates (skipped without a key)
```

After ANY voice change: `npm run words`, then `npm run check:timeline`, then fix `src/timeline.ts` until it passes. A regenerated line always comes back a different length. A voice that reads a line faster than its caption can be read fails `check:captions`: shorten the line, or slow just that line with `speed` on it in `src/timeline.ts` (0.7 to 1.2), then `npm run voice -- --only <line id>`. The speaker's `settings.speed` in `film.config.json` changes every line of that speaker, so the next `npm run voice` re-voices all of them.

### 6. Picture

Build the scenes in `src/scenes/` from the product's real UI and tokens. `npm run studio` to scrub; `npm run render -- master --still 4.5` to write one frame to `build/stills/`. Wrap anything decorative (background glows, plates, shapes bleeding off frame) in `<Decor>`; everything else is content and must sit inside the safe zone. `npm run typecheck` after every change.

### 7. Gates, then the cuts

```bash
npm run typecheck
npm run check:timeline
npm run check:captions               # words light when heard; readable speed; not stale
npm run check:claims                 # every promise sourced; no banned words; no text outside COPY
npm run check:safe -- vertical       # renders a content only probe; fails content outside the box
npm run check:safe -- master
npm run cuts -- --scale 0.5          # fast preview of all three cuts
npm run frames -- out/vertical.mp4   # contact sheet in build/frames/: LOOK at it
npm run cuts                         # full resolution: render, mix, teaser, finish, check:final
npm run check:final -- --publish     # fails if any asset is still a placeholder
```

The frame check is a person's (or your own) eyes on `build/frames/*-sheet.jpg` and on single frames (`npm run frames -- out/master.mp4 --at 0,4.3,13.5`): frame 0, every act turn, every caption page, the end card hold, and the vertical's last frame against its first.

For 4K: `npm run render -- master --scale 2` renders the 1080p composition at twice the size, then `npm run mix -- master` and `npm run finish -- master`.

### 8. Independent review, then deliver

Before calling it done, hand `references/review.md`, the three finished files, the contact sheets, `film/brief.md` and `film/claims.md` to a reviewer that did not build the film (a fresh subagent, or a person). Give it the rubric, not your opinion of the film. Fix what it finds, re-run the gates, and review once more.

Deliver: `out/master.mp4`, `out/vertical.mp4`, `out/teaser.mp4`, plus what `npm run check:final` printed (sizes, loudness, sources). Say plainly what was measured and what nobody has heard yet: an agent can measure loudness and transcribe the mix back, but a person should listen once on headphones and once on a phone speaker before posting.

## Craft rules

The short list; `references/craft.md` has the reasoning and numbers.

- Frame 0 is the problem, never a logo. The first 2 seconds must be understood with the sound off.
- One story told through consequences, not a feature list. Every shot advances the story or goes.
- One idea per card, six words or fewer, at most 20 characters per second of reading.
- The product's own colours and type. Tinted near black and near white, no purple gradients, no glow on everything, no bounce easing.
- UI lives in space: isolated, scaled up, cropped hard, moved by a camera. Never a flat screen recording.
- Sparse sound: a cue only where the viewer should notice something, silence before the turn, the music ducked under every line.
- The vertical is recomposed for 9:16, captions inside the safe box, and ends on frame 0 so the loop is seamless.
- Only numbers the product can back. The scenario's own specifics beat industry statistics.

## Traps (each one has cost a real film time)

- **Music API limits.** ElevenLabs music refuses sections shorter than 3 s and runs at most 2 requests per account at a time. Plan sections per act of 3 s or more (`check:timeline` fails shorter ones), and generate takes 2 at a time (`music.py` does).
- **Image generation timeouts.** A high quality image can take over a minute before the first byte; a plain blocking HTTP call gets cut off. Use the SDK's streamed call (`stills.py` does).
- **Whisper hands pauses to the next word.** The word after a pause often starts on the tail of the previous word, so its caption lights a third of a second before it is heard. `words.py` moves any word that starts in silence, or on a tail right before a pause of 100 ms or more, to where the voice's energy returns; `check:captions` runs the same tests and fails what is left.
- **Whisper word times drift.** Models disagree by 0.1 to 0.3 s on the same file, and a small model can stretch a line so its last word "ends" after the audio does. `words.py` maps a stretched transcript back onto the audible speech; for a real film fetch a bigger model (`npm run whisper-model -- small.en`, then `WHISPER_MODEL=models/ggml-small.en.bin npm run words`) and watch the vertical once with the sound on.
- **A regenerated voice line changes length.** Every timing after it is now a guess. Re-run `words` and `check:timeline` after every voice change, and never trust durations from an earlier take.
- **The placeholder voice moves its rate in coarse steps.** macOS `say` gives identical audio at 157 and 175 words per minute, so a `speed` of 0.9 can leave a placeholder line exactly as long as before. Judge a speed change on the real voice (ElevenLabs and `espeak-ng` scale smoothly).
- **The Remotion CLI can crash on long or large renders.** A slow font load makes Remotion retry the frame; the CLI's progress bar counts the retries again and can crash at 4K. Render through `npm run render` (the Node API, no progress bar, 120 s page timeout). Under heavy machine load a font load can stall a batch of frames for about a minute before the retry succeeds; the render still finishes.
- **The encode moves the true peak.** AAC overshoots the WAV's true peak by a dB or more, so the mix limits to about -3 dBFS and `check:final` measures the encoded file, never the WAV.
- **Full range video.** Remotion writes full range H.264; players expect limited range. `finish` converts it (a relabel alone shifts every colour).
- **Teaser cuts inside words.** A segment edge chosen by eye lands mid word after any retime. `check:timeline` fails any edge inside a spoken word; re-run it after every voice change.
- **Case insensitive file systems.** `film.tsx` and `Film.tsx` are the same file on macOS and Windows; one silently overwrites the other. Keep module names distinct beyond case.

## Output shape

Report: the three files with duration, resolution, size and loudness (from `check:final`), which gates ran and passed, what the independent review found and what changed, the sources list with any placeholder called out, and what still needs a human ear or eye.

## Anti-patterns

- Retiming a scene by editing numbers inside a scene file: the captions and the mix no longer match the picture. Retime in `src/timeline.ts`.
- Typing a claim straight into a scene: it escapes the claims check. Put every string in `COPY`.
- Judging captions from the plan instead of the measured words: run `npm run words` after every voice change.
- Publishing a cut while `build/SOURCES.txt` lists a placeholder: `npm run check:final -- --publish` fails it.
- Grading your own film: the review goes to a reviewer that did not build it.
