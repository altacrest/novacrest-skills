---
name: long-form-video
description: "Make a narrated long-form YouTube video and its shorts for a Novacrest brand, in one of three formats: an iceberg, an answers video (real search questions) or an argument (the problem, possible futures, the verdict, the fix). Research, script, ElevenLabs narration, Blueprint-style stills from Gemini, Higgsfield clips, a rendered MP4, shorts, QA and the upload text."
---

# Long-form video and its shorts

This is how the Novacrest marketing team makes long YouTube videos with Claude. It started with the warehouse iceberg
(Nov 2026: 60 stories, about 55 minutes, cut into 60 shorts). A video is researched and written by Claude, read by an
ElevenLabs narrator, illustrated with stills in the brand's style, opened up with Higgsfield clips, rendered to one
MP4 with chapters, and cut into vertical shorts. Nothing is filmed.

Everything ships with this skill (paths are relative to this file):

- `formats/iceberg.md`, `formats/answers.md`, `formats/argument.md`: each format's shape, research method, script
  rules, cards and shorts. Read the format's file before Step 2.
- `brands/<brand>/`: the brand pack. `brand.json` (site, call to action, channel, narrator, music, card colors),
  `style.md` (how stills, clips and cards look), `prompt.json` (the still and clip prompt parts), `image-prompt.md`
  (the full picture style spec), `claims.json` and `pitch_lines.json` (the only things the video may say about the
  product), the logos. BinLogic is the first pack; a new brand is a new folder with the same files.
- `engine/`: the scripts, run in Claude's workspace unless noted.
  - `compile.py` (script.md to manifest.json, with the format's checks), `lint.py` (the humanizer and claims check),
    `memes.py` (the meme pass), `pick.py` (the iceberg's entry pick)
  - `voice.py` (the narration; runs in the user's own Terminal)
  - `stills.py` (stills in the Gemini web app), `clips.py` (Higgsfield clips), `style_check.py`
  - `assemble.py` (the long video), `shorts.py` (the shorts), `qa.py` (the checks), `meta.py` (title, description,
    chapters, tags, sources, shorts text, thumbnail)
  - `render.mjs` with `gfx/` (the cards and overlays, drawn in HTML), `upload/` (YouTube Studio and Instagram page
    helpers), `shrink_short.sh`
- `examples/`: a small video folder for each format (video.json and script.md), the grammar in use.

## Hard rules

- Real facts only, each with its source in the script. A red-team pass before voicing. Nothing about the product
  outside the brand's claims files: never name a customer or claim case studies, customer counts, customer
  logos or testimonials.
- No model judges the voice, the pictures or the pick. The checks are the scripts: lint, compile, style_check, pick,
  qa. A person looks at the contact sheets.
- Never a realistic AI picture of a real event, a real person's face, or a logo. Every AI still carries the AI IMAGE
  badge and every clip the AI VIDEO badge (the engine burns them in). YouTube's "altered or synthetic content" is Yes.
- Plain words anyone's mom would follow. No dashes, brackets, semicolons or slashes in narration (lint fails them),
  no AI tells, no em dashes anywhere in the user's voice.
- The voice starts in the first few seconds: the title card sits under the cold open's first words.
- Pilot first: voice the cold open and the first section, render a draft, and get the user's ear on it before voicing
  the rest; again after any voice or script change.
- Never ask for, print or paste an API key. Never sign in for the user; ask them to sign in.
- Ask first, with the numbers: before spending Higgsfield credits (how many clips, what they cost), before
  downloading files (how many, from where, into Downloads), before uploading or publishing anything. Uploads go up
  private or scheduled; public only on the user's yes.

## Where each part runs, and why

Claude's workspace and Claude's shell on the user's computer can't reach ElevenLabs, Higgsfield's API, Mistral or
Google's APIs (the Novacrest network allowlist; measured Nov 13 2026). So:

- **The voice** runs in the user's own Terminal (`voice.py`, one paste-ready command).
- **Stills, clips and uploads** happen in the user's signed-in Chrome through Claude in Chrome: Gemini
  (gemini.google.com) for stills, the Higgsfield web app for clips, YouTube Studio and instagram.com for uploads.
- **The Higgsfield connector** (custom connector `https://mcp.higgsfield.ai/mcp`) can't make media. It reads the
  credits (`balance`), the models and their settings (`models_list`, `models_get`) and every finished generation with
  its link (`show_generations`). Use it to price the clips and to find each new clip.
- **Everything else** (research, writing, checks, cards, renders) runs in Claude's workspace, which has Chromium,
  Playwright, ffmpeg and scikit-learn. Work on a copy of the video folder there.

## The video folder

It lives on the user's computer, `~/Downloads/<slug>/`, and Claude keeps a working copy in its workspace
(`/mnt/user-data/outputs/videos/<slug>/`, so files can be copied back with device_commit_files):

    video.json      title, slug, brand, format and settings (Step 1)
    script.md       the script (Step 3)
    manifest.json   compile.py's output; voice.py reads it
    say.json        optional spoken respellings, {"seg-004": "how the voice should say it"}
    voice.py        a copy of engine/voice.py, for the Terminal
    voice/          the takes and voice/report.json (word times)
    images/         one still per look, <look id>.jpg (look ids are <segment id>-<k>)
    clips/          Higgsfield clips, <look id>.mp4, and clips/plan.json
    music/          the brand's music bed (brand.json says which file; it isn't in the repo)
    out/            the video, its timeline, the shorts, youtube.txt, sources.md, the thumbnail, qa/

On the user's computer the folder is `~/Downloads/<slug>/` in their own Terminal and `$HOME/mnt/Downloads/<slug>/` in
device_bash (the connected Downloads folder); device_stage_files and device_commit_files take its path on the
computer, under the folder get_device_info lists.

Copy text files Claude writes to the user's folder with device_commit_files. Copy what the user's computer makes
(voice/, downloaded stills and clips, music/) into the working copy with device_stage_files, at most 50 files a call.

## Step 1: scope

Get these, asking only what's missing, in one round: the brand (the brand pack must exist), the format, the topic
(or where topics come from: the format file says), the length, and the channel. Write `video.json`:

    {"title": "...", "slug": "black-friday-iceberg", "brand": "binlogic", "format": "iceberg",
     "target_minutes": 22, "levels": 6, "entries": 36, "clips": 16,
     "youtube_title": "...", "hook": "...", "tags": ["..."], "thumbnail_look": "seg-007-1"}

`levels`, `entries` and `max_current_share` are the iceberg's. `clips` caps the Higgsfield clips (each costs credits).
`hook` (two sentences for the top of the description) and `youtube_title` come from the finished script; `kicker`
overrides the small line on the title card. Make `~/Downloads/<slug>/` with `video.json` and a copy of
`engine/voice.py`. Ask the user for the brand's music file if `music/` doesn't have it.

## Step 2: research

Follow the format's file: the discovery passes and `pick.py` for an iceberg, the YouTube Studio research page and
search demand for answers, documented failures and real drivers for an argument. Every story keeps its sources.

## Step 3: script

1. Write `script.md` in the grammar `engine/compile.py` describes: a cold open, `## SECTION: Name` sections, numbered
   segments `**N. Title.**` with their narration, stage directions `*(sources: ...)*`, `*(look: ...)*`,
   `*(clip: ...)*`, `*(stat: "BIG" "line")*`, `*(card: "first words" "last words")*`, `*(short: ...)*`, and
   `## OUTRO`. A direction belongs to the paragraph above it (or below it, when it opens the block). The examples
   show each one. Write for the ear: short sentences, numbers as words, no symbols.
2. `python3 engine/lint.py <folder>`: rewrite only the flagged sentences until it reports 0 FAIL.
3. The meme pass, iceberg and answers only: stage the Know Your Meme sitemaps the user saved in ~/Downloads/memes into
   the workspace, then `python3 engine/memes.py suggest <folder>/script.md --memes <that folder>`, pick at most one per
   segment, then `memes.py check` with the same `--memes`. Skip it when there are no sitemaps.
4. Red team: a second pass whose only job is finding what's wrong: dates, numbers, names, quotes, claims a source
   doesn't support, anything that reads as a product claim the claims files don't hold. Fix or cut every finding.
5. `python3 engine/compile.py <folder>` until it reports no FAIL. Show the user the outline (sections, segment titles,
   words, minutes) and carry on unless they change it. Copy manifest.json (and say.json) to the user's folder.

## Step 4: the narration (the user's Terminal)

Give one paste-ready block:

    cd ~/Downloads/<slug>
    python3 voice.py setup        # first time only: paste the ElevenLabs key when asked (typing is hidden)
    python3 voice.py check        # the key works, credits left, what this video needs
    python3 voice.py --only open-01,open-02,sec-01,seg-001,seg-002

`check` prints the credits the video needs (about one per character; a 36-entry iceberg is about 20,000). When
they're short, voice the pilot and wait for the monthly reset rather than buy more, unless the user says so. With
faster-whisper installed (`pip3 install faster-whisper`) every take is checked against the script and a misread take
is made again. Copy voice/ into the working copy, then render the pilot (`assemble.py <folder> --sections 1 --draft
--tag _pilot`) and send it for a listen. A word said wrong gets a respelling in say.json and
`python3 voice.py --only <id> --redo`. Then the rest: `python3 voice.py`.

## Step 5: stills (Gemini in Chrome)

1. `python3 engine/stills.py prompts <folder>`, then fill each look's `opening` in images/prompts.json from the
   brand's `prompt.json` template and `style.md` (the 3-line brief, the archetype rotation, no real faces or events).
2. `python3 engine/stills.py queue <folder>`, then run the two page scripts in a Gemini tab exactly as the header of
   `stills.py` says. The downloads need the user's yes first (one yes for the batch).
3. Collect them on the user's computer: copy `engine/stills.py` into the folder once, then (device_bash)
   `python3 stills.py collect --clicks clicks.json --out images`. Copy images/ into the working copy.
4. `python3 engine/stills.py check <folder>`: make a failing still again, at most twice, then keep the best.

## Step 6: clips (the Higgsfield web app)

1. `python3 engine/clips.py plan <folder>`. Read the balance with the Higgsfield connector and tell the user the count
   and the cost (Kling 3.0 Turbo, 720p, 5 s: 7.5 credits a clip, about 4 minutes each, measured Nov 2026). Get a yes.
2. Make them in higgsfield.ai's video tool as the header of `clips.py` says: the still as the start frame, plan.json's
   prompt, 5 s. Find each finished clip with the connector's `show_generations`, look at its first, middle and last
   frames, and drop any clip that turns the drawing into a photo or 3D, warps it, or adds text.
3. Download the kept clips one at a time, as the header of `clips.py` says (the user's yes first). After each one, in
   the video folder on the user's computer (device_bash; copy `engine/clips.py` there once):
   `python3 clips.py collect --as <look id> --out clips`. Then copy clips/ into the working copy and run
   `python3 engine/clips.py check <folder>`.

A look without a clip simply holds its still; the video never waits on clips.

## Step 7: render and check (Claude's workspace)

1. `python3 engine/assemble.py <folder> --draft` (fast), then `python3 engine/qa.py render <folder>` and look at every
   contact sheet in out/qa: the title, each section card, each look (the lower third and badge 3 seconds in), each
   brand card, the end card. Fix and render again; unchanged parts are reused.
2. The final render takes a while (about 12 to 20 minutes for 25 minutes of video): run it in the background,
   `nohup python3 engine/assemble.py <folder> > <folder>/build/assemble.log 2>&1 &`, and check the log. Then
   `qa.py render` again: it must exit 0.
3. `python3 engine/shorts.py <folder>`, then `python3 engine/qa.py shorts <folder>` (exit 0) and look at
   out/qa/shorts_all.jpg.
4. `python3 engine/meta.py <folder>`: out/youtube.txt (title, description with chapters and sources, tags, settings),
   out/sources.md, out/shorts/shorts_upload.csv, out/thumbnail.png. If a YouTube SEO skill is installed, run it over
   youtube.txt and the shorts text.

## Step 8: deliver and upload

1. Copy out/ to the user's folder with device_commit_files. A file over 380 MB goes in parts:
   `ffmpeg -i out/<slug>.mp4 -c copy -f segment -segment_time 600 -reset_timestamps 1 out/part%02d.mp4`, commit the
   parts, then on the user's computer (device_bash) `printf "file '%s'\n" part*.mp4 > parts.txt && ffmpeg -f concat
   -safe 0 -i parts.txt -c copy <slug>.mp4` and delete nothing until the user has checked it plays.
2. The long video: in YouTube Studio (the brand channel, signed in by the user) the user picks the MP4 in the upload
   dialog (Claude in Chrome can't pass a file over 10 MB). Claude fills the title, description and tags from
   youtube.txt (`upload/youtube_studio.js`, `__fill` with a `__ROWS` row for it), sets not made for kids, altered
   content Yes, uploads out/thumbnail.png, and saves it private or scheduled.
3. The shorts: `upload/youtube_studio.js` (YouTube) and `upload/instagram_web.js` (Reels), each header says how;
   `shrink_short.sh` for any short over 9.6 MB. Private first; public on the user's yes.

## Step 9: report

What was made and where (the folder, the files), the narrator and credits used, the Higgsfield credits spent, the QA
results, and the list of what the user still has to do: the Terminal command, sign-ins, yeses for downloads or
credits, picking the MP4 in YouTube Studio, publishing.

## Setup, once per person (the plugin's README has the details)

1. Install the plugin from the novacrest-skills marketplace (Claude > Customize > Plugins).
2. ElevenLabs: an API key with Text to Speech access, saved with `python3 voice.py setup`; the brand's narrator voice
   in the account's My Voices.
3. Claude in Chrome, with Gemini, Higgsfield, YouTube Studio (the brand channel) and Instagram signed in.
4. The Higgsfield connector: Claude > Settings > Connectors > Add custom connector, `https://mcp.higgsfield.ai/mcp`.
5. Optional: `pip3 install faster-whisper` (the word check); Know Your Meme sitemaps in ~/Downloads/memes.
