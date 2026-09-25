# Independent review rubric

Hand this file to a reviewer that did not build the film, with: the three finished files (`out/master.mp4`, `out/vertical.mp4`, `out/teaser.mp4`), their contact sheets (`npm run frames -- <file>`), `film/brief.md` and `film/claims.md`. Do not hand over the builder's opinion of the film; the reviewer forms its own.

The reviewer scores each criterion 1 to 5 with the evidence (a timestamp, a frame, a line), then gives a verdict: SHIP, or FIX with a list ordered by severity. A 1 or 2 on any criterion blocks shipping.

| # | Criterion | What a 5 looks like |
|---|-----------|---------------------|
| 1 | Hook | Frame 0 and the first 2 s state a problem or show something that makes a stranger keep watching, with the sound off. No logo first. |
| 2 | One story | One chain of consequences; no shot that moves nothing forward; the turn lands between 20 and 45 percent of the running time. |
| 3 | Product truth | Every capability on screen or in the voice has a sourced row in `film/claims.md` with status OK. No invented numbers. |
| 4 | Readability | One idea per card, six words or fewer, readable at phone size; no text on screen too briefly to read; voice and text agree. |
| 5 | Captions (vertical and teaser) | Every spoken word captioned, lit when it is heard (not before), one or two balanced lines, no lonely one word page. |
| 6 | Safe zones | On the 9:16 cuts nothing important under the top bar, the bottom rail or the right hand buttons. `npm run check:safe -- vertical` passes. |
| 7 | Look | One visual system; the product's colours and type; no generic gradients or glow; no bounce; UI in space, not a screen recording. |
| 8 | Sound | Every line intelligible over the music (transcribe the mix back to check); effects sparse; the music turns with the picture; the end resolves. |
| 9 | Delivery | `npm run check:final -- --publish` passes: loudness, true peak, format, faststart, no placeholder assets. |
| 10 | Cuts | The vertical is recomposed (not a crop) and loops back to frame 0 cleanly; the teaser stands alone and every cut lands between words. |

Checks a reviewer can run itself:

```bash
npm run check:timeline && npm run check:captions && npm run check:claims
npm run check:safe -- vertical && npm run check:safe -- master
npm run check:final -- --publish
npm run frames -- out/vertical.mp4 --at 0,17.9     # first and last frame: the loop
```

To hear the mix without ears, transcribe the finished file and compare it to the script, for example with whisper.cpp:

```bash
ffmpeg -i out/master.mp4 -ar 16000 -ac 1 /tmp/master16.wav
whisper-cli -m models/ggml-base.en.bin -f /tmp/master16.wav
```

A line that does not come back word for word is buried under the music or effects.
