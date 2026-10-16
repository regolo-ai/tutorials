# Video script: reply to reviews with Clef-Flash and an LLM (about 9 minutes)

Screen: the app at http://127.0.0.1:8100 (Chrome, 1440 px wide, light theme). Terminal: the project folder. Voice: first person plural, calm and specific.

## 0:00 Hook (20 s)
On screen: the app with 37 reviews already labeled.
"This is how an agency can answer customer reviews for several clients without losing control of what gets posted. Clef-Flash decides, an LLM writes, Clef-Flash checks, and a person approves."

## 0:20 Why two kinds of models (45 s)
On screen: the line "Decide with Clef-Flash, write with an LLM, check with Clef-Flash" in the header.
"Replying to a review is three jobs. Deciding what it is about and how risky it is, writing the reply, and checking that the reply respects the brand. The first and the last are choices from a short list, which is what Clef-Flash does through the Regolo API. The writing is a job for a chat model."

## 1:05 Start the app (40 s)
On screen: terminal, then the browser.
```
cp .env.example .env     # add the Regolo key
./run.sh
```
"You need a Regolo key and Python. The app runs on your computer and keeps the reviews in a local database."

## 1:45 Connect your Regolo account (30 s)
Actions: show the two columns of step 1, paste the key into the form and click **Save and verify key**.
"New to Regolo? There are 30 days of free trial for new users, and the link takes you to the pricing page to create an account. Paste your API key here: it is checked with Regolo's catalog, saved on this computer, and never sent back to the browser."

## 2:15 Bring in reviews (35 s)
Actions: show the two cards (sample reviews, CSV with the list of columns and the template). Click **Download the template** and open it for a second.
"Reviews come from the sample data or from a CSV file. The card says exactly what it expects: a header row, one review per row, and a required text column. The template is one click away. The app does not scrape review sites, so you take the export from the review tool your client uses."

## 2:50 Load and analyze (60 s)
Actions: click **Load sample reviews** (the reviews stay hidden), then **Analyze with Clef-Flash**. Point at the progress bar while it fills, and show how each finished step closes with a check mark and a summary, and how the list appears only after the analysis.
"We load 37 sample reviews. They are synthetic, written for this demo, in five languages. One click and Clef-Flash labels every review: sentiment, topic, whether a person must handle it first, whether a reply is needed and the language. The tile shows the real time of the run and the estimated cost, a few seconds and about half a cent."

## 3:50 Read the labels (50 s)
Actions: filter **Needs a person**, open the review from "Anonymous" (scam and lawyer) and the one from "Ivan P." (injury).
"Reviews with a legal threat, a safety problem, a fraud accusation, a privacy request or the press are flagged for a person. Every label has a confidence value, and low confidence ones are marked 'check labels' so a person reads them first."

## 4:40 Brand profile (45 s)
On screen: in step 2, switch the sample client from Acme Outdoor to Northwind Cloud, then show `brands/acme-outdoor.json` in the editor.
"Each client is one JSON file: the voice, the topics Clef-Flash chooses from, the only facts a reply may state, the things it must never do and the forbidden phrases. An e-commerce client and a SaaS client get different topics with no code change."

## 5:25 Write and check a reply (90 s)
Actions: select "Hannah K." (late delivery), click **Write a draft**, scroll through the checks. Then select "Tom R." (broken tent) and show a blocked draft if it appears, or add the instruction "mention the refund" to force one.
"The writing model gets the brand profile, the review and the labels, and replies in the language of the review. The draft is checked by plain rules and by Clef-Flash: no promise of compensation, no blame, no defensive tone, no competitors, same language, only facts from the profile. If a blocking check fails, the writer tries once more, and if it still fails the Approve button stays disabled."

## 6:55 Escalation and approval (45 s)
Actions: open an escalated review and write a draft, then approve a ready draft.
"For an escalated review the draft is a neutral holding reply and cannot be marked ready. When a person approves a draft, the app copies the text so it is posted from the platform's own console. Nothing is posted from here."

## 7:40 What we learned and the limits (50 s)
On screen: README section "What we measured".
"Two things changed the code. Subtle decisions need small requests: with twelve reviews in one request the escalation question flagged more than twice as many reviews as it should, and one review per request fixed it. And turning reasoning off for the writing model took a draft from tens of seconds to a few. The sample is synthetic, the checks are a filter and not a guarantee, and a person approves every reply."

## 8:30 Close (15 s)
"The code and the tutorial are in the Regolo tutorials repository. Try it with one of your own clients."

## Before you record
- Run the app once so the font and data are warm, and use a clean database (**Clear this client**).
- Check the numbers on the tiles against what you say, since each run differs a little.
- Keep the Regolo key out of the frame (the `.env` file stays closed).
