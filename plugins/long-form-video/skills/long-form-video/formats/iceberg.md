# Format: iceberg

Many short stories, all about one topic, ordered from the best known to the most obscure across levels. The point
of an iceberg is many sub-stories at every level, every one about the full topic: an event, a person, a place, a
number or a thing that belongs to the topic. Never a general explainer.

- **Shape**: a cold open, then `## LEVEL n: Name` sections (6 levels of 6 entries is the default, about 20 to 25
  minutes; video.json `levels`, `entries`), each with a short spoken intro and its numbered entries, then `## OUTRO`.
- **Entry**: about 90 words (45 seconds at the house pace), one story, one look. Every entry is a short on its own.
- **Cards**: each level gets the berg card, its level filled in. Chapters are the levels.
- **Topic**: interesting enough that people who will never buy the product still click (the reason the best
  icebergs work), where current events in the niche, lasting curiosity, the brand's buyers and the product meet.

## Find the entries

Don't ask a model to be obscure; change where it looks. The question isn't "what obscure things happened in
<topic>?" It's "what unusual stories turn out to be <topic> stories when you investigate them?" Many of the best are
filed under another subject (a court case, a spy operation, a war, a fraud) even though the topic was central.

Run each pass on its own, with its own fresh list, before reading the others. Up to 15 candidates each, about 100 in
all before checking. Each candidate's `lens` in candidates.json is the pass that found it.

1. **first-pass**: the well-known stories most people link to the topic. They fill the top of the iceberg.
2. **crime**: heists, theft, fraud, smuggling, and cases solved or exposed through the paper trail.
3. **intelligence**: espionage, Cold War operations, covert supply chains, industrial espionage, government secrecy.
4. **breakdown**: things going wrong where nobody gets hurt: crashed systems, delivery meltdowns, oversold or
   missing stock, supply crunches, recalls, bizarre chains of events.
5. **economics**: financial scandals, market manipulation, shortages, monopolies, commodity speculation.
6. **strange**: bizarre legal cases, forgotten inventions, odd experiments, stories that sound made up but are documented.
7. **outsider**: what would a criminologist, a military historian, an insurance investigator, an archivist, a food
   scientist or a judge know about this topic that people in the trade wouldn't?
8. **library**: work from what you know from books before you search: company and trade histories, memoirs,
   biographies, court records, old newspapers and magazines. Web search favors whatever ranks online today; the
   deepest stories tend to live in books. Name the book or record each story comes from.

**Breakdowns yes, tragedies no.** Where things go wrong and nobody gets hurt has its own pass. A tragedy, where
people die or get hurt and the loss is the story (crowd crushes, shootings, fatal accidents), stays out of every pass
unless the story is strange in its own right, like the Boston molasses flood. Its aftermath stays out with it (the
fine, the lawsuit, the tally of the dead). The test: if the entry is about who got hurt, it's a tragedy; if it's
about how something worked or broke, or how a paper trail cracked a case, it isn't.

The prompt for each pass (fill in the topic and the lens):

> You are researching candidates for a documentary iceberg about <topic>. Lens for this pass: <lens>.
> Don't produce a conventional list of <topic> history. Look for documented events, often filed under another
> subject, where <topic> was an important part of the story. A candidate must have a genuine connection to <topic>;
> a passing mention is not enough. Don't invent connections to make a story fit. Leave out tragedies unless the story
> is strange in its own right. Prioritize documented incidents with identifiable people, organizations and dates,
> surprising details, subjects rarely covered in videos, and material backed by primary sources or reputable
> reporting. For every candidate give: name, date and place, what happened, the exact connection to <topic>, why
> it's interesting, the source (a book with chapter or page, a record, or reputable reporting), and any video that
> already covered it.

## Check, score and pick

1. **Check**: open a source for every candidate. For a library-pass story, find the book, record or old newspaper
   online (Internet Archive, Google Books, HathiTrust, Chronicling America, court records) or reputable reporting
   that cites it. Drop what you can't confirm, passing mentions and tragedies. Set `sourced` only for what you confirmed.
2. **Compare**: search for existing iceberg videos and charts on the topic and set `covered` on candidates they used.
3. **Score** each survivor 0 to 2 with a one-line reason each: `on_topic` (2 when the story is about the topic itself),
   `story` (a concrete person, number or twist that works as its own short) and `surprise` (would someone who knows
   the topic be surprised?).
4. **Pick** with `engine/pick.py views` then `engine/pick.py pick` on <video folder>/candidates.json. It measures how
   well known each candidate is (Wikipedia page views over the last year; languages when that service is blocked)
   and makes the pick the same way every time: levels from best known to most obscure, current events held to
   video.json's `max_current_share` (about a third, every one on topic). The script picks, not you. Keep its per-lens
   summary for the report.

## Script notes

- The cold open names the topic and the promise in its first seconds ("Thirty-six stories. Six levels.").
- Each level's intro is two to four short lines.
- Order entries inside a level the way pick.py ranks them; numbering runs through the whole video.
- Brand reads (the self-sponsor lines) go in three to five entries where the story naturally touches what the brand
  does, each marked with a *(card: ...)* direction.
