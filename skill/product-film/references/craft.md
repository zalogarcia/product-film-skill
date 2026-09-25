# Craft notes for short product films

Starting values, not laws. Each comes from studying product films and short form product videos that travelled, and from building one end to end. Break a rule on purpose, never by accident.

## The hook (0 to 2 s)

- Open on the problem, the product in action, or something odd. Never a logo, a title card or a "meet X" preamble.
- Frame 0 is also the thumbnail and the frame a feed shows before it plays: readable at a quarter size, nothing important near the edges.
- On the vertical, sound starts at frame 0. On the master a 0.3 to 0.5 s silence before the first hit is fine.
- Hook patterns that work: the problem stated by an object ("last watered Tuesday"), a question the viewer is already asking, a before and after in one frame, a moment the viewer recognises from their own day, a number the product can back.

## Structure and pacing

- One story, told as a chain of consequences: the problem, the product's move, what it changes, the end card.
- Put the turn (the moment the product shows up and changes things) between 20 and 45 percent of the running time.
- Every shot advances the story or goes. Count the axes the story moves on (the user is helped, the job gets done, time or money comes back) and delete any shot that moves none.
- Hard cuts between worlds (the user's world, the product), continuous camera moves inside the product.
- End: a tagline of 2 to 5 words only this product could say, the logo, one call to action, then a 1.5 to 3 s quiet hold with the music resolved.

## Type

- Three sizes, one family, two weights. Emphasis by weight or colour, never by gradient.
- One claim per card, six words or fewer.
- At most 20 characters per second of reading; a statement holds at least 1.5 times its read aloud time; nothing readable stays under 0.8 s.
- Voice and on-screen text never say different things at the same moment.

## UI and camera

- Rebuild the product's real screens from its real tokens. No lorem ipsum, no placeholder names, no numbers that disagree between screens.
- Isolate components at 1.5 to 4 times scale on a clean canvas, or tilt a panel in 3D; crop hard; let screens bleed off frame. Never a flat full screen recording with browser chrome.
- The product's own actions happen with no cursor; the absence of a hand reads as automation. Use a cursor only when a person acts, on an eased arc, arriving a few frames before the click.
- One motion language for the whole film: entrances and camera on a strong ease out (for example cubic bezier 0.2, 0, 0, 1), exits on an ease in, springs heavily damped. No overshoot, no elastic, no bounce.
- Timing scale at 30 fps: UI state changes 8 to 15 frames, camera moves 0.8 to 1.6 s, every hold drifts 2 to 6 percent so nothing is ever fully still.
- One ownable visual device reused through the film beats a new effect per beat.
- Motion blur on fast moves only (the starter's `<MotionBlur>` supersamples sub frames; it multiplies render cost while active).

## Sound

- Voice intelligibility first. Duck the music 8 to 15 dB under every line.
- Sparse effects: a cue only where the viewer should notice something (a message lands, a job is done). One hit per section boundary at most, one riser at most, silence just before the turn.
- Music changes where the picture changes: one section per act (the composition plan does this).
- Deliver around -14 LUFS integrated with true peak at or under -1 dBTP, measured on the encoded file.
- If a voice in the film is supposed to be a person, it has to sound like one; a robotic line anywhere sinks the whole film.

## The vertical (1080 x 1920)

- A recomposition, not a crop: bigger type, stacked layout, the product larger in frame.
- Content inside x 60 to 930 and y 250 to 1520 (the starter's default box): the top bar, the caption and button rail at the bottom, and the like and share column on the right cover the rest.
- Burned in captions for sound off viewing, one or two lines, the spoken word lit.
- End on the first frame so the platform's loop reads as continuous.

## What makes a product film look cheap

1. A logo or title first.
2. A screen recording look: static camera, tiny text, a wandering cursor.
3. Fake or inconsistent UI and invented statistics.
4. The generic palette: purple to blue gradients, floating orbs, glass as decoration, neon glow, pure black and pure white.
5. Bouncy easing and the same fade up on every element.
6. Too much text, or voice and text saying different things.
7. A feature list instead of a story.
8. Wall to wall music and a whoosh on every move.
9. A new effect in every shot.
10. The vertical as a crop of the master.
