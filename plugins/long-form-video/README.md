# Long-form video

Make a narrated long-form YouTube video and its shorts with Claude. You pick the brand, the format and the topic;
Claude researches, writes and checks the script, makes the pictures and clips in your Chrome, renders the video with
chapters, cuts every short, and writes the title, description and tags. The narrator is an ElevenLabs voice that
runs in your Terminal. Nothing is filmed.

Three formats (each one's rules are in `skills/long-form-video/formats/`):

| Format | What it is | Shorts |
| --- | --- | --- |
| Iceberg | Many short stories about one topic, from the best known to the most obscure, level by level | Every entry |
| Answers | One video answering 6 to 12 real questions people search for | Every answer |
| Argument | The problem, two to four possible futures, the verdict, then the fix | 3 to 6 marked passages |

The first brand pack is BinLogic (Blueprint Reality: photoreal heroes in a blue blueprint world, the binlogic.io blog
look). Another brand is another folder in `skills/long-form-video/brands/`.

## What you need

- The Claude desktop app with Claude in Chrome, and a folder connected (your Downloads).
- In Chrome, signed in: Gemini (gemini.google.com, for the stills), Higgsfield (the team account, for the clips),
  YouTube Studio for the brand's channel, and Instagram for Reels. Claude never signs in for you.
- Your own ElevenLabs API key, from an account on a paid plan (free accounts can't use Voice Library voices through
  the API), with the brand's narrator added to My Voices.
- The Mac's Terminal, for one command per video (the voice).

## Install (once)

1. In Claude open **Customize**, then **Plugins**. If the novacrest-skills marketplace isn't there yet: **+ Add**,
   **Add marketplace**, type `altacrest/novacrest-skills`, choose **Use "altacrest/novacrest-skills"**, **Sync**.
2. Find **Long-form video** and click **Install**.
3. The Higgsfield connector: Claude **Settings**, **Connectors**, **Add custom connector**. Name it Higgsfield, paste
   `https://mcp.higgsfield.ai/mcp`, then **Connect** and sign in with the Higgsfield account. It reads the credits and
   finds each finished clip; the clips themselves are made in the Higgsfield web app in Chrome.
4. ElevenLabs: in ElevenLabs open **Developers**, **API keys**, **Create API key**, leave **Restrict Key** on and set
   **Text to Speech** to **Access** (and **User** to **Read** to see credits). Then open **Voices**, **Voice Library**,
   find the brand's narrator (BinLogic's is David - The Movie Trailer) and add it to **My Voices**. The first time
   Claude gives you the voice command, run `python3 voice.py setup` first and paste the key (typing is hidden). Never
   paste a key into Claude.
5. Optional: `pip3 install faster-whisper` in Terminal, so every take is checked word by word.

In Claude Code: `/plugin install long-form-video --marketplace altacrest/novacrest-skills`.

## Make a video

Ask Claude, for example: "Make a BinLogic iceberg video about Black Friday", "Make an answers video from what people
are searching for on the BinLogic channel", or "Make an argument video: why one recall empties a whole aisle."

What you'll do along the way:

1. Read the outline Claude shows you and change anything you like.
2. Paste one block into Terminal for the pilot voice, listen to the pilot draft, then run `python3 voice.py` for the
   rest. A full 20-minute video uses about 20,000 ElevenLabs credits; Claude tells you before it starts.
3. Say yes to the picture downloads from Gemini, and to the Higgsfield clips (Claude tells you how many and what they
   cost: about 7.5 credits a 5-second clip on Kling 3.0 Turbo).
4. Look at the draft and the contact sheets; ask for changes.
5. In YouTube Studio, pick the finished MP4 in the upload dialog (Claude fills in everything else and saves it
   private or scheduled). Say when to publish.

## If something goes wrong

- **"couldn't reach ElevenLabs"**: run the voice command in your own Terminal, not inside Claude.
- **"the narrator voice isn't in this ElevenLabs account"**: add the voice named in the brand's `brand.json` from the
  Voice Library to My Voices.
- **"ElevenLabs doesn't let free accounts use those"**: the narrator is a Voice Library voice; the key has to come
  from an account on a paid plan.
- **Not enough credits**: voice the pilot now and the rest after the monthly reset.
- **A word sounds wrong**: tell Claude which one; it adds a spoken spelling and gives you a command to redo that part.
- **A still or clip looks off**: tell Claude which; it makes that one again.

## What's inside

- `skills/long-form-video/SKILL.md`: the steps Claude follows.
- `skills/long-form-video/formats/`: iceberg, answers and argument.
- `skills/long-form-video/brands/binlogic/`: the BinLogic look, prompts, claims and narrator.
- `skills/long-form-video/engine/`: the scripts (voice, stills, clips, render, shorts, checks, upload text).
- `skills/long-form-video/examples/`: a tiny video folder for each format.
