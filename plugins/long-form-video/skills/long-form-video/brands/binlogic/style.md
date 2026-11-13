# BinLogic video style: Blueprint Reality

Every still, clip, card and overlay in a BinLogic video uses the look of the binlogic.io blog heroes, so the videos
and their shorts sit well next to the blog posts on the BinLogic profiles. The card and overlay colors live in
brand.json (`look`); the still and clip prompt parts live in prompt.json. image-prompt.md is the full spec.

## The look in one line

A photoreal hero in a hand-drawn blue blueprint world on pale-blue grid paper (#EAF2FB): sky-blue (#7CB6F2) flat fills,
mid-blue (#1F6FD0) loose ink lines, and at most one deep cyan-blue (#0B3D91) marker.

## Stills, one per look

1. Write a 3-line concept brief before the prompt:
   - **Core idea**: the one thing this look must show, from what the narration says over it.
   - **Archetype**: one from the table below, and why it fits.
   - **Literal scene**: the subject, the setting, the camera, the one marker, and the photoreal hero named outright.
2. Rotate archetypes. Neighboring looks never share one, and none covers more than a quarter of the video. Prefer
   heroes that aren't people: a macro object, a map, an isometric plan, a diagram, split panels.
3. Real events, people and places: the hero is an object or a diagram, never a staged scene of the event and never a
   person who could pass for someone real. A rubber duck on a blueprint map of the Pacific, not a ship losing its
   containers. No real faces, no logos, no brand names, no readable text.
4. Fill prompt.json's `opening_template` (the brackets) and keep the rest of its wording. The engine adds the `pre`
   and the `tail` (style, format and negative list) itself. 16:9, edge to edge, no halo border or rounded corners,
   the hero in the central third (shorts pan a 9:16 window across the picture).
5. The opening plus the pre and the tail must fit in 2,000 characters; `stills.py queue` refuses a longer one.
6. Make the stills in the Gemini web app (gemini.google.com, the image tool at 16:9) with `stills.py`, in the user's
   signed-in Chrome.
7. `stills.py check` runs style_check.py: it fails a still with a black corner or with edges that aren't pale blueprint
   paper (a full photo, white paper, a dark or sepia render). Make a failing still again, at most twice, then keep the
   best one and say which.

| # | Archetype | Best for | Example scene |
|---|---|---|---|
| 1 | System diagram | how things connect, a relationship | Two or three blueprint nodes linked by a dotted data line; one photoreal device at a node |
| 2 | Split comparison | "X vs Y", before and after | The frame split into two blueprint halves, each with its own photoreal subject |
| 3 | Dashboard | numbers, accuracy, reports | A photoreal tablet on a desk of blueprint gauges and charts; a focus ring on the key number |
| 4 | Isometric plan or cutaway | layout, zones, a building | A 3/4 isometric blueprint warehouse; one photoreal pallet or worker for scale |
| 5 | Process flow | steps, a sequence | Left-to-right blueprint stages with a photoreal object at the active stage |
| 6 | Macro hero object | a thing: a barcode, a label, a pallet, a bin | One photoreal object large in frame with ink callouts |
| 7 | Action in context | when the task itself is the story | A photoreal hand doing the specific task; never the default worker scanning a box |
| 8 | Map or route | places, shipping, many sites | A blueprint map with route traces and pins; a photoreal truck or crate |
| 9 | Conceptual metaphor | an abstract idea | A photoreal subject plus one strong blueprint metaphor |

The worker in a safety vest scanning a box in an aisle is banned as a default: it is the most overused cover.

## Clips

A clip animates its look's own still without redrawing it. prompt.json's `clip_prompt` keeps the drawing still and
moves only the hero, a little: write the *(clip: ...)* direction as that motion ("the pallet glides a short way along
the dotted path"). A clip that turns the drawing into a photo or a 3D scene, warps the lines, adds objects or text,
or changes colors is deleted, and that look keeps its still.

## Cards, overlays and shorts

- Title, section and end cards, fact cards, lower thirds, source tags, badges and the brand card all sit on the same
  pale-blue grid paper: #EAF2FB with a faint light-blue grid, deep blue (#0B3D91) titles, mid-blue (#1F6FD0) rules and
  labels, sky-blue (#7CB6F2) fills. Inter for titles and text, JetBrains Mono for small labels (bundled in engine/gfx).
- The real logo files (logo.svg, logo-reversed.svg) may go on cards. Never a generated logo.
- No old-film look: no sepia, grain, flicker, dust, deco frames, glows or neon.
- Shorts open on the look's clip or still, never on a card. Captions are white with a black outline; the word being
  spoken turns sky blue.
