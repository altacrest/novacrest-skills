---
name: motion-how-to-video
description: "Make a narrated how-to video of an app flow: real screens captured in Chrome, a Claude Motion film with one step per scene, English narration by ElevenLabs (Matilda) under each caption, mixed into one MP4. Use for how-to, tutorial, docs or QA videos of an app."
---

# Narrated how-to video with Claude Motion

This is how the Novacrest marketing team makes how-to and docs videos: the app's real screens, a gliding cursor, one short caption per step, an English voice reading each caption, one finished MP4. It started with the OmniOrders quick start films (Oct 2026). Jose wants QA docs videos made this way so Supademo can be cancelled.

Everything the film needs ships with this skill (paths are relative to this file):

- `engine/shared.js` and `engine/base.css`: the screenshot engine (`SS`) and its look. Never rebuild them from memory.
- `examples/how-to-film/`: every scene module of the reference film, "Make a how-to video with Claude Motion" (Oct 27 2026), with its `lines.json`, `scenes.json` and `shots.json`. Read them before writing scenes: they show each `SS.def` option in use.
- `scripts/voice.py`: the narration. ElevenLabs API, one MP3 per caption, checked with Whisper when it's installed. It runs in the user's own Terminal.
- `scripts/mix.py`: puts each clip under its caption and writes the finished MP4 (needs ffmpeg).

## Hard rules

- Real screens only, captured from the app. Never redraw the app's UI: Jose caught drawn screens in the first quick start films. A plain card showing a command is fine; a drawn copy of an app or a Terminal window is not.
- Use the test account. No real customer data, keys, tokens or passwords on screen: cover them with a patch or use the test account's dummy values. Never sign in for the user; ask them to sign in.
- The narration is English (US), and the captions are the script: one per step, plain words anyone's mom would follow, under about 12 words, no em dashes. The voice reads each caption word for word. When the voice says a word wrong, put a spoken respelling in `say.json`; the caption stays as written.
- Never stretch the video to fit the voice. Captions are timed to their clips (Step 4). A clip that still runs long is sped up a little (mix.py allows 1.15x at most), or its line gets shorter and is voiced again.
- Pilot first: voice the first scene's lines and check them before the rest, and again after any voice or script change.
- No LLM judges the voice. voice.py scores each clip with Whisper (word error rate) when faster-whisper is installed; otherwise the user listens.
- Never ask for, print or paste an API key in the chat. The ElevenLabs key lives only in a file on the user's computer.
- Ask before downloading files, naming them and where they come from.

Why the voice runs in the user's Terminal: Claude's workspace and Claude's shell on the user's computer can't reach ElevenLabs (the Novacrest network allowlist blocks api.elevenlabs.io and elevenlabsusercontent.com; checked Nov 12 2026), and keys never go through the chat. Claude prepares everything and the user pastes one command. The ElevenLabs connector (custom connector, `https://api.elevenlabs.io/v1/mcp`) makes speech without a key, but its audio comes back as elevenlabsusercontent.com links that the workspace can't download, so it isn't used here. If an admin allows those two domains, revisit this.

## Step 1: scope and captions

Get these, asking only what's missing in one round: the flow (for example "create a transfer in OmniOrders"), the app and its test account, where the video goes (a docs page, the quick start, YouTube) and the product's colors. Write the step list and one caption per step, plus a title line and an end line, as `lines.json` (`{"id": "caption"}`, in film order; ids like `open`, `ask-a`, `ask-b`, `end`). Add `say.json` (`{"id": "spoken text"}`) only for lines with a word the voice may say wrong (OmniOrders as "Omni Orders", a repo name with dashes). Show the user the captions in chat and carry on unless they change them.

## Step 2: start the narration

Start it as soon as the captions are settled; capture and build while it runs.

1. Make a film folder on the user's computer, `~/Downloads/<film-slug>/`, with `lines.json`, `say.json` (if any) and a copy of `scripts/voice.py`. With a linked folder, write them there with device_bash. Without one, send the files with SendUserFile and ask the user to put them in one folder.
2. The first time, the user needs an ElevenLabs API key with Text to Speech access (README, "ElevenLabs"). Check whether `~/.config/elevenlabs/env` exists (test for the file; never read it). If it doesn't, start the block below with the setup line.
3. Give the user one paste-ready block for Terminal:
   ```
   cd ~/Downloads/<film-slug>
   python3 voice.py setup        # first time only: paste the key when asked (typing is hidden)
   python3 voice.py check        # the key works, credits left
   python3 voice.py --only open,<first scene's ids>
   ```
   When the pilot sounds right (voice.json shows no flags, or the user listened), the rest is `python3 voice.py`.
4. The house voice: Matilda (`XrExE9yKIg1WjnnlVkGX`), `eleven_multilingual_v2`, stability 0.5, similarity 0.75, speed 1.0, MP3 44.1 kHz 128 kbps; each line is read with the captions before and after it as context, so the reading flows. Change the voice or speed only when the user asks. voice.py prints the characters to be used (about one credit each); if `check` shows fewer credits left, stop and ask.
5. Clips land in `voice/<id>.mp3`; `voice/voice.json` lists each clip's length and, with Whisper, what was heard and the word error rate. A line over 0.05 gets a listen, a respelling in `say.json` or new wording, then `python3 voice.py --only <id> --redo`.

## Step 3: capture the screens

1. Load the claude-in-chrome skill. Open the app in a new tab in the user's signed-in Chrome. Resize the window until the page viewport is 1512 x 745 (check `innerWidth` and `innerHeight`): that is the engine's world size, and screenshots then come back at 2x, 3024 x 1490.
2. Walk the flow in the test account. Capture each state the film needs with a `computer` screenshot and `save_to_disk: true`: before and after each click; for typing, the empty field and the filled field (the film reveals typed lines as patches cut from the filled shot).
3. In the workspace, convert to webp (quality about 90), named `<flow>_<step>.webp`, plus 2x crops of each typed line. Record each shot's URL path in `shots.json` and each patch's rect in view pixels (the 1512 x 745 space).
4. Don't submit anything that changes data outside the test account. Stop and ask if a step would.

## Step 4: build the film

1. Create the film from the Motion artifact type (find it in the Artifact tool's types listing; Novacrest's is https://claude.ai/artifact/S4skLPbN9WeoFmuiTfaEFy), `title` = the video's name, and read the type's instructions that come back: they govern the film. Settle its questions in the request so no form is needed. Style: guided cursor over real screenshots, the reference film's look. Colors: the product's palette (OmniOrders: #16213E, #11ACE4, #F4F7FB, #2FD193). Length: set by the voice (below), plus a 5-second title card and a 7-second end card.
2. Write `engine/shared.js` into the film as `modules/shared.js` unchanged, and `engine/base.css` as `modules/base.css`, changing only the four colors on its first line. Upload this film's own screenshots and crops as its assets; never copy another film's `_blob` refs.
3. Write `lines.json` (the Step 1 file), `shots.json` (each shot's URL path; `"host"` is the domain the browser bar shows before a path that starts with `/`), one scene module per step built with `SS.def` (the title card uses `SS.open`; `SS.end` takes `mark`, `next` and `url`), and `scenes.json` with each scene's `dur` and `desc`. Declare captions as `caps: [['<id>', tin, tout], ...]` so mix.py can find them; a line voiced without a caption (the title card's) is declared the same way in its module, for example `const voiceOnly = [['open', 0.4, 4.6]];`. Follow the examples: the cursor glides to the control, a ring and a click ripple mark it, the camera eases in, the caption sits on the dark plate.
4. Time the captions to the clips in `voice/voice.json`: in each scene the first caption comes in at 0.3 s, each caption stays up for its clip's length plus 0.45 s, and the next comes in 0.35 s after that. A scene's `dur` is its last caption's out time plus about 0.4 s, or longer when the on-screen action needs it. Fit the cursor, rings and camera inside those windows. If the voice isn't back yet, give each caption about 5 s and retime when it is.
5. Keep the score quiet and modern: the first quick start scores got called "80s church organ".
6. The user plays the film and asks for changes; apply them (a changed caption gets voiced again). When they're happy, the MP4 is exported with the download arrow under the player on the film page: the user clicks it, or Claude in Chrome does once they say yes. It lands in their Downloads folder.

## Step 5: mix

1. Put the exported MP4, the `voice/` folder, `scenes.json` and the scene modules in one place: the film folder on the user's computer (run mix.py there with device_bash when ffmpeg is installed), or the cloud workspace (stage them). Store documents saved from the film with ArtifactData (`out_dir`) work as they are.
2. `python3 mix.py cues --scenes scenes.json --modules <folder with scene-*.js> --lines lines.json` writes `cues.json`: each caption's start and end in the film (the scene's start, the sum of the earlier scenes' `dur`, plus the caption's times).
3. `python3 mix.py mix --film <exported>.mp4 --voice voice --cues cues.json --out <product>-<flow>.mp4 --web` starts each clip at its caption, keeps the film's score at 25% under the voice when the export has sound, levels the voice to -16 LUFS and copies the picture. It stops on a clip that needs more than 1.15x; shorten that line, voice it again and mix again.
4. `python3 mix.py frames --film <product>-<flow>.mp4 --cues cues.json --out frames` saves a frame at each caption's midpoint. Look at every one: caption visible, the right screen, nothing private. Then play the opening seconds: the voice starts with its caption. Follow the video-making skill's ffmpeg rules for anything else.

## Step 6: deliver

- Send the finished MP4 with SendUserFile and save it in the user's connected folder as `<product>-<flow>.mp4`.
- For a website: the `-web.mp4` copy goes in a PR to the site repo. Give the user the link; they merge it.
- End with a short list of what the user still has to do: the Terminal command, the export, merging the PR.

## Setup, once per person (the plugin's README has the details)

1. Install from GitHub: Claude > Customize > Plugins > Add > Add marketplace > `altacrest/novacrest-skills` > Sync, then install How-to video.
2. ElevenLabs: an API key with Text to Speech access, saved with `python3 voice.py setup` in any film folder.
3. Claude in Chrome, signed in to the app's test account.
