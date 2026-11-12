# Novacrest skills

Claude plugins the Novacrest marketing team shares. Add this repository to Claude once, as a marketplace, and every plugin in it is ready to install. When the repository changes, Claude picks up the new version the next time the marketplace syncs.

| Plugin | What it does |
| --- | --- |
| [How-to video](plugins/motion-how-to-video) | A narrated how-to video of any app flow: real screens, a Claude Motion film, an English voice under each caption, one MP4. [Watch how it works](https://github.com/altacrest/novacrest-skills/releases/download/v2.0.0/how-to-video.mp4). |

## Install in the Claude app

1. In Claude, open **Customize**, then **Plugins**.
2. Click **+ Add**, then **Add marketplace**.
3. Type `altacrest/novacrest-skills` in the box and choose **Use "altacrest/novacrest-skills"** (the list may not show the repo yet). Leave **Sync automatically** on, so updates arrive by themselves, and click **Sync**.
4. Find the plugin you want and click **Install**.

You need GitHub connected to Claude and access to this repository. No access yet? Ask Sean. An organization admin can also add the marketplace for everyone in the organization.

## Install in Claude Code

Inside Claude Code (version 2.1.275 or later), one line:

```
/plugin install motion-how-to-video --marketplace altacrest/novacrest-skills
```

Or from a terminal:

```
claude plugin marketplace add altacrest/novacrest-skills
claude plugin install motion-how-to-video@novacrest-skills
```

## Without the marketplace

Each release has the skill as a ZIP file (for example `motion-how-to-video.zip`). In Claude, open **Customize**, then **Skills**, click **+ Add**, then **Upload skill**, and pick the ZIP. An uploaded skill doesn't update itself: upload the new ZIP when there's a new release.

## Add a plugin to this repository

1. Make `plugins/<name>/` with `.claude-plugin/plugin.json` and `skills/<name>/SKILL.md` (scripts and other files go next to `SKILL.md`).
2. Add an entry for it to `.claude-plugin/marketplace.json`.
3. Check both: `claude plugin validate .` and `claude plugin validate plugins/<name>`.
4. No keys, passwords or customer data in the repository. Keys stay in each person's own files (`.env` files are ignored by git).
