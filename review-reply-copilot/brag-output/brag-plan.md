# Review Reply Copilot: YouTube tutorial plan

Made with /brag on October 15, 2026, adapted from a short launch video to a narrated screen tutorial at the user's request (at least 2:30, 16:9, 2560x1440).

## Angle

A calm, practical walkthrough of the real app on first launch. The viewer sees the cursor move through the overview and then every step, with live Regolo calls, and ends on the numbers the app measured during the recording.

- **What it is:** an open source app that drafts replies to customer reviews in a client's voice.
- **Who it is for:** agencies and teams that answer reviews for e-commerce and SaaS clients.
- **What sets it apart:** Clef-Flash decides and checks, a chat model writes, and a person approves. Risky reviews get a holding reply only.
- **Hook:** "a templated reply can do more harm than no reply at all".
- **Real UI shown:** all of it, recorded live from `http://localhost:8100`.
- **Tone:** polished, friendly, no jokes.

## Format

- Output: `review-reply-copilot-tutorial.mp4`, 2560x1440, 30 fps, H.264 (CRF 16) with AAC 192 kbps, 4:01.
- Capture: headless Chromium at 2560x1440 with the page zoomed 2x, so the text is rendered at full 2K resolution rather than upscaled. A drawn cursor with a click ring follows every mouse move.
- Voice: Kokoro (`am_puck`, chosen by the user), speed 1.1, sentence ends spoken as exclamations for a livelier read (subtitles keep the written punctuation), brighter EQ and light compression, one clip per segment, loudness normalized to -16 LUFS.
- Music: none. The bundled tracks have unverified license terms, which is a Content ID risk on YouTube.
- Subtitles: `review-reply-copilot-tutorial.srt`, generated from the script with timing estimated from each segment's length.

## How the API key stays hidden

The real key is never typed on screen and never placed in the page. The backend reads it from `.env`. In the video, the masked field receives a decoy string that shows only as dots, and the browser's save request is answered locally with the real account status, which contains only the hint (····7VcQ). The Show button is never pressed.

## Storyboard

| Time | Segment | On screen |
|---|---|---|
| 0:00 | Intro | Title card: Review Reply Copilot, "Clef-Flash decides, an LLM writes, Clef-Flash checks" |
| 0:18 | Welcome | App at first launch with a slow push in; a subscribe button pops in, a hand clicks it and it turns into SUBSCRIBED |
| 0:29 | Overview | Headline, the four tiles, scroll through the three steps |
| 0:45 | Step 1 | Free trial card, key typed into the masked field, save, step closes with "Key saved" |
| 1:05 | Step 1 done | Cursor on the check mark and summary |
| 1:11 | Step 2, client | Sample client menu switches to Northwind Cloud, then back to Acme Outdoor |
| 1:28 | Step 2, CSV | Expected columns, template button, then "Load sample reviews" |
| 1:41 | Step 3 | "Analyze with Clef-Flash", live progress bar, 37 reviews in 3.0 s |
| 2:00 | Result tile | Analysis tile: 3.0 s, 37 requests, $0.0047 |
| 2:09 | Filters | Negative chip, topic menu, "Needs a person", open "Late and no updates" |
| 2:21 | Reply studio | Labels with confidence bars, "Write a draft" |
| 2:36 | Checks | Draft, 5 rule checks and 8 Clef-Flash checks, all passed |
| 2:58 | Approve | "Check again", then "Approve and copy" |
| 3:11 | Escalation | "Needs a person", the injured child review, holding reply banner and draft |
| 3:27 | Results | Tiles: 37 analyzed, 2 replies, 1 approved, 1.7 s per reply |
| 3:36 | Reminder | Last app frame with the same subscribe animation |
| 3:45 | Outro | Card with the code link, the free trial and the models |

## Voiceover script

**Intro.** Replying to every customer review takes time, and a templated reply can do more harm than no reply at all. In this video, we walk through Review Reply Copilot, an open source app that drafts replies in your client's voice and keeps a person in charge.

**Welcome.** Hi everyone, and welcome. If you find this tutorial useful, leave a like and subscribe to the channel, so you stay up to date on every new guide we publish.

**Overview.** This is the app on first launch. At the top, four tiles track your reviews, your replies, and the time and cost of every step. Below them, three steps take you from an empty project to labeled reviews, so let's go through them in order.

**Step 1.** Step one connects your Regolo account, and new users can start with a thirty day free trial. Paste your API key in the field, where it stays masked. The app checks it against Regolo's model catalog without running any inference, then saves it in a local dot env file, and the key never travels back to the browser.

The step closes with a check mark and a short summary, and you can reopen it at any time.

**Step 2.** Step two brings in the reviews. Each client has a brand profile with its voice, its topics, and the only facts a reply may state. The sample data covers two clients, a software company and an outdoor gear shop, and we'll use the shop, Acme Outdoor.

For your real clients, you import a CSV export from their review tool. The card lists the columns it expects, and the template is one click away. For now, we load the sample reviews.

**Step 3.** Step three sends every review to Clef-Flash, Regolo's decision model. It answers five questions for each one: the sentiment, the topic, whether a person must handle it first, how urgent a reply is, and the language. Eight requests run in parallel, and the bar shows the real progress.

All thirty seven reviews are labeled. The analysis tile shows how long the run took and what it cost, which for this sample is well under one cent.

**Filters.** The reviews now appear with their labels. You can filter by sentiment or topic, or show only the reviews that need a person. Let's open a negative one about a late delivery.

**Reply studio.** The reply studio shows each label with a confidence bar, and low confidence cases are flagged for a second look. When we click write a draft, a chat model writes the reply with the client's brand rules, and Clef-Flash checks it right away.

**Checks.** Here is the draft, followed by every check. Rule checks cover length, contact details and forbidden phrases. Clef-Flash answers yes or no questions about the text: does it promise compensation, blame the customer, or state something the brand profile doesn't support? If a blocking check fails, the app tries once more, and then asks you to edit.

**Approve.** You can edit the text and run the checks again. When the reply reads well, approve it. The text is copied to your clipboard, and you post it from the review platform yourself, because nothing is published from the app.

**Escalation.** Some reviews should never get an automatic answer. This customer reports that their son was burned by a camping stove, so Clef-Flash marks the review for a person. The draft becomes a neutral holding reply, and it can't be marked as ready.

**Results.** Back at the top, the tiles sum up the session: the reviews analyzed, the replies drafted and approved, and the average time to write a reply.

**Reminder.** Before we wrap up: if this was useful, give the video a like and subscribe to the channel, so you don't miss the next tutorials.

**Outro.** That's the whole workflow: Clef-Flash decides and checks, a chat model writes, and a person approves. The code is open source, and new Regolo users get a thirty day free trial, so you can try it on your own reviews today.

## Measured during the recording

October 15, 2026, 37 synthetic Acme Outdoor reviews, one run: labeling took 3.0 s with 37 requests for $0.0047. Two drafts were written and checked in 1.7 s on average, with $0.0007 spent on writing. The first draft passed all 13 checks on the first attempt.
