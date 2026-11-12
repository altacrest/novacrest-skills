# How-to video

Make a narrated how-to video of any app flow with Claude. Claude walks the app's real screens, builds the film in Claude Motion, and an ElevenLabs voice (Matilda) reads each caption in English. You get one MP4, ready for a docs page, the quick start or YouTube.

## What you need

- The Claude desktop app with Claude in Chrome.
- The app's test account, signed in in Chrome. Never film real customer data.
- An ElevenLabs API key. Novacrest has one ElevenLabs account; ask Sean for access.
- The Mac's Terminal app, for one command per video.

## Install (once)

In the Claude app:

1. Open **Customize**, then **Plugins**.
2. Click **+ Add**, then **Add marketplace**.
3. Pick **novacrest-skills** (or paste `altacrest/novacrest-skills`) and click **Sync**.
4. Find **How-to video** and click **Install**.

In Claude Code: `/plugin install motion-how-to-video --marketplace altacrest/novacrest-skills`. A ZIP upload works too; see the [main README](../../README.md).

## ElevenLabs (once)

1. Sign in at [elevenlabs.io](https://elevenlabs.io). Open **Developers**, then **API keys**, and click **Create API key**.
2. Name it "How-to videos". Leave **Restrict Key** on and set **Text to Speech** to **Access**. To see your credits with `check`, also set **User** to **Read**; to pick a voice by name other than the defaults, set **Voices** to **Read**. Everything else can stay off.
3. Copy the key. In Terminal, inside any film folder Claude made, run `python3 voice.py setup`, paste the key and press Enter. Typing is hidden. The key is saved in `~/.config/elevenlabs/env`, a file only you can read.

Never paste the key into a Claude chat. Claude doesn't need it: the voice runs in your Terminal, because Claude can't reach ElevenLabs from its side.

## Make a video

1. Open the app's test account in Chrome. In Claude, ask for it, for example: "Make a narrated how-to video of creating a transfer in the OmniOrders test account."
2. Claude shows the captions, one per step. Change any you like.
3. Claude makes a film folder in your Downloads and gives you one command. Paste it into Terminal: it makes an English voice clip for each caption.
4. Meanwhile Claude captures the real screens and builds the film in Claude Motion. Play it and ask for any changes.
5. When it looks right, click the download arrow under the film to export the MP4.
6. Claude puts each voice clip under its caption and gives you the finished MP4 (and a smaller copy for the web).

## If something goes wrong

- **"the key was refused"**: make a new key with Text to Speech access, then run `python3 voice.py setup` again.
- **Out of credits**: `python3 voice.py check` shows what's left. Ask Sean before topping up.
- **A word sounds wrong**: tell Claude which one. It adds a spoken spelling for that line and gives you a command to make just that clip again.
- **"couldn't reach ElevenLabs"**: run the command in your own Terminal, not inside Claude.

## What's inside

- `skills/motion-how-to-video/SKILL.md`: the steps Claude follows.
- `skills/motion-how-to-video/engine/`: the screenshot engine every film uses.
- `skills/motion-how-to-video/scripts/voice.py`: makes the English narration with ElevenLabs.
- `skills/motion-how-to-video/scripts/mix.py`: lays each clip under its caption and writes the MP4.
- `skills/motion-how-to-video/examples/how-to-film/`: the scenes of the first how-to film, as examples.
