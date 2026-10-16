<!--
WordPress notes
1. Paste into a Markdown block. Links are raw HTML anchors with target="_blank" rel="noopener noreferrer".
2. Upload the four screenshots from docs/img/ (app-steps-start.png, app-overview.png, app-reply-studio.png, app-escalation.png) and replace the bare file names. Alt text and captions are written.
3. Put the JSON-LD block at the end of the post in a Custom HTML block.
4. All numbers were measured on October 14, 2026 with the code in this repository, on synthetic sample reviews.
5. Add the author name and a short bio under the title before publishing (author attribution helps the article get cited).
6. Keyword note: "AI review response generator" is dominated by vendor pages, so the focus keyphrase targets the narrower angle of guardrails and human approval. No search volumes were measured (no keyword tool was available), so check them in your SEO tool before locking the keyphrase.
-->

| SEO field | Value |
|---|---|
| SEO title (58 characters) | AI review responses with guardrails: Clef-Flash and an LLM |
| Meta description (154 characters) | Draft review replies in your client's voice: Clef-Flash labels and checks, an LLM writes, a person approves. Open source, with measured results on Regolo. |
| Slug | ai-review-responses-guardrails-clef-flash |
| Focus keyphrase | AI review responses with guardrails |
| Secondary keywords | AI review response generator, Clef-Flash, review reply automation, brand voice guardrails, human approval, Regolo API |
| Category and tags | Tutorials · Clef-Flash, Regolo, customer reviews, agencies, Python |
| Open Graph title | AI review responses with guardrails, and a person in charge |
| Open Graph description | An open source app where Clef-Flash labels and checks, an LLM writes, and you approve. Measured on Regolo, with code. |

# AI review responses with guardrails: Clef-Flash decides, an LLM writes, a person approves

*Last updated: October 14, 2026*

AI review responses work best when the work is split between two kinds of models: Clef-Flash decides (sentiment, topic, risk, language) and checks the draft, an LLM writes it, and a person approves. In our sample, labeling 37 reviews took about 3 to 5 seconds for roughly half a cent, and writing and checking one reply usually took 1 to 3 seconds.

This guide walks through the open source app that does it, a small FastAPI project with a web interface that you can run on your laptop. It is written for agencies and teams that answer reviews for e-commerce and SaaS clients, and every client gets a brand profile instead of a new prompt. You need a Regolo API key, and new users can <a href="https://regolo.ai/pricing" target="_blank" rel="noopener noreferrer">create an account and start with a 30 day free trial</a>.

## Why do review replies matter, and why do templates fail?

BrightLocal's <a href="https://www.brightlocal.com/research/local-consumer-review-survey/" target="_blank" rel="noopener noreferrer">Local Consumer Review Survey 2026</a> (published February 11, 2026, 1,002 US adults) found that 80% of consumers are likely to use a business that responds to all of its reviews, that 81% expect to hear back within a week, and that templated or generic responses make 50% of consumers unlikely to choose a business. Replies have to be fast, and they have to be specific to the review, which is hard to do by hand across several clients and easy to get wrong with a template.

Many review tools follow a similar pattern: they route risky reviews (legal language, safety, fraud) to a person and let a model draft the rest, as described in these guides from <a href="https://www.yext.com/knowledge-center/a-guide-to-scaling-brand-visibility-with-ai-review-responses-in-2026" target="_blank" rel="noopener noreferrer">Yext</a> and <a href="https://reviewshake.com/blog/how-to-automate-ai-review-responses-while-keeping-your-brand-voice" target="_blank" rel="noopener noreferrer">ReviewShake</a>. This app shows how to build that pattern yourself, with the rules written down per client.

## What is Clef-Flash?

Clef-Flash is a decision model available on Regolo: you send a text and a question with a few allowed answers, each defined in one sentence, and it returns one of them with a confidence value and the probability of every option. It does not write free text, which makes its answers easy to filter, log and check.

## Why split the work between Clef-Flash and an LLM?

Replying to a review is three different jobs. Deciding what the review is about, how urgent it is and whether a person must see it first is a classification job with a short list of answers. Writing the reply is a generation job. Checking that the reply respects the brand rules is a classification job again.

The <a href="https://huggingface.co/Cloudflare/clef-flash" target="_blank" rel="noopener noreferrer">Clef-Flash model card</a> describes the model. Here it handles the two classification jobs through the Regolo API, and a chat model handles the writing. Each model does the work it is good at, and a person stays in charge of what gets posted.

![The app with three completed steps, each closed with a check mark and a summary, above the list of labeled reviews](app-overview.png)
*Image 1. The three steps close with a check mark and a one line summary when they are done, and the reviews appear only after the analysis.*

## What does the app do, step by step?

The interface has three steps. Each one closes when it is complete, shows a check mark with a short summary on its bar, and opens again with one click.

![Step 1 completed with a saved key and step 2 open with the sample reviews and the CSV import](app-steps-start.png)
*Image 2. Step 1 is done (key saved) and step 2 is open, with the two sources and what each one expects.*

### Step 1: connect your Regolo account

Paste your API key in the form and choose **Save and verify key**. The app checks it against Regolo's catalog, which runs no inference, and stores it in a local `.env` file. The key never goes back to the browser, only its last four characters. If you do not have a key yet, the left side of the step links to the account creation page with the 30 day free trial for new users.

### Step 2: bring in the reviews

Choose between the sample reviews, which are synthetic and written for the demo in five languages, and a CSV file. The sample card lets you pick one of two clients, an outdoor gear shop and a SaaS company, and a CSV import goes to the client selected there. The CSV card says what it expects: a UTF-8 file with a header row and one review per row, a required `text` column and optional `rating`, `title`, `author` and `date` columns. A template is one click away. The app does not scrape review sites, so you take the export from the review tool your client uses, and many tools offer one in their settings.

### Step 3: analyze with Clef-Flash

Each review gets five questions in one request to the `/v1/systemone` endpoint: sentiment, topic, whether a person must handle it first, whether a reply is needed, and the language. A progress bar shows how many reviews are done, and the list of reviews appears only when the analysis finishes.

## How do you set up a client with a brand profile?

A brand profile is a small JSON file with the voice, the topics Clef-Flash chooses from, the only facts the reply may state, the things it must never do and the forbidden phrases.

```json
{
  "id": "acme-outdoor", "type": "ecommerce",
  "topics": {"shipping_delivery": "The customer talks about delivery time, tracking or a damaged parcel.", "billing_refund": "..."},
  "facts": ["Returns are accepted within 30 days of delivery for unused items."],
  "never": ["promise a refund, replacement, discount or any compensation in a public reply"],
  "forbidden_phrases": ["we apologize for any inconvenience"],
  "support_contact": "support@acme-outdoor.example", "signature": "Marta, Acme Outdoor support"
}
```

Because the topics are plain sentences, an e-commerce client and a SaaS client get different categories with no code change, and a new client is a new file.

## How do you label every review with Clef-Flash?

```python
body = {"model": "clef-flash",
        "state": {"sentences": [{"id": 0, "text": review_text}]},
        "questions": {
            "sentiment": {"type": "choice", "criteria": SENTIMENT, "instructions": "In sentence [0], what is the overall sentiment of the customer review? Choose exactly one."},
            "topic": {"type": "choice", "criteria": brand["topics"], "instructions": "In sentence [0], which topic is the main reason for the review? Choose exactly one."},
            "escalation": {"type": "choice", "criteria": ESCALATION, "instructions": "In sentence [0], must a person handle this review before any public reply? Choose exactly one."},
            # priority and language follow the same pattern
        }}
```

Two practices made a visible difference in our tests.

**Keep subtle decisions in small requests.** Clef-Flash accepts up to 64 questions per request, and our first version sent 12 reviews at once (60 questions). The escalation question flagged 12 of 37 reviews when about 5 deserved it. With 4 reviews per request the flags improved but false alarms remained in the SaaS file, and with one review per request the flags matched what we expected, at lower token cost and about the same wall time, because the requests run in parallel. The limit of 64 is a ceiling and not a target.

**Write what does not count.** Our first definition of "escalate" listed legal threats, safety problems and fraud accusations, and Clef-Flash also flagged angry but ordinary reviews. Adding one sentence to the "none" category ("complaints about delivery, price, discount codes, refunds, bugs or support speed belong here, even when the customer is angry") fixed most of it.

Every answer carries a confidence value, and the app marks reviews with a label below 80% as "check labels" so a person reads them first.

## How does the LLM write the reply?

The writing model receives the brand profile as its instructions, the review, and the labels from Clef-Flash. For a three sentence reply we turned reasoning off (`reasoning_effort: "none"` on Regolo), which took a draft from 14 to 74 seconds in our first test to usually 1 to 3 seconds, with replies that read just as well. One of nine drafts still took 17 seconds, so keep a spinner in the interface.

Reviews that Clef-Flash marks for escalation get a different instruction: a short, neutral holding reply that thanks the customer, says the team is looking into it and points to the support contact, without admitting fault or discussing legal, safety or privacy details.

## How do you check the draft before a person sees it?

Every draft goes through two kinds of checks. Plain code checks the length, the forbidden phrases and any contact detail that is not the brand's own. Clef-Flash answers yes or no questions about meaning, in a single request.

```python
questions = {
  "compensation": yes_no("Does the reply in sentence [1] promise or offer a refund, replacement, discount, credit or other compensation?"),
  "blame":        yes_no("Does the reply in sentence [1] blame, criticise or argue with the customer?"),
  "tone":         yes_no("Is the tone of the reply in sentence [1] defensive, dismissive, sarcastic or cold?"),
  "language":     yes_no("Is the reply in sentence [1] written in the same language as the review in sentence [0]?"),
}
```

If a blocking check fails, the writer receives the list of problems and tries once more. If it still fails, the draft stays "needs edit" and the Approve button is disabled. In one of our runs, a reply to a broken tent that quoted the refund policy was blocked by the compensation check, which is the behavior you want from a brand guardrail.

![A draft reply with its labels and the list of checks, each marked as rule or Clef-Flash](app-reply-studio.png)
*Image 3. The reply studio: labels with confidence, the editable draft, and the checks that ran on it.*

![An escalated review with a neutral holding reply and a warning that a person should handle it first](app-escalation.png)
*Image 4. A review with a legal threat gets a holding reply and cannot be marked ready.*

## Who approves, and what gets posted?

A person approves every reply, and nothing is posted from the app. Approving copies the text so you post it from the review platform's own console. This is deliberate: the checks are a filter and not a guarantee, and a public reply is the client's voice.

## Which approach fits: templates, an LLM alone, or decide, write and check?

| | Template replies | An LLM alone | Clef-Flash, LLM and a person (this app) |
|---|---|---|---|
| Speed per reply | instant | seconds | about 1 to 3 seconds for the draft and the checks in our sample |
| Matches what the review says | no, generic by design | yes | yes, with the review and its labels in the prompt |
| Handles risky reviews (legal, safety, fraud) | only with manual triage | depends on the prompt | flagged before writing, holding reply, cannot be marked ready |
| Enforces brand rules | by wording | by prompt only | by prompt and by checks on every draft |
| Person in the loop | by hand | optional | always, before anything is posted |

Only the last column and the time figures come from our own tests. The other columns describe how these approaches usually work, and templates are the ones the BrightLocal survey above associates with lower customer trust.

## What did we measure?

On 37 and 35 synthetic reviews (written for the demo, in English, Italian, German, French and Spanish), from one machine, on October 14, 2026:

| Step | Result |
|---|---|
| Label 37 reviews with Clef-Flash | about 3 to 5 seconds, estimated 0.005 US dollars (about 0.13 US dollars per 1,000 reviews) |
| Write and check one reply, reasoning off | usually 1 to 3 seconds, about 0.0004 US dollars for the writing step |
| The same reply with the reasoning model left on | 14 to 74 seconds in our first test |

Costs are estimates from the tokens reported by the API and the Regolo catalog rates, not an invoice.

## Which practices would we keep?

1. Give every client a profile with the facts the reply may state, and forbid everything else.
2. Let Clef-Flash decide before the LLM writes, and pass the labels to the writer.
3. Keep subtle classifications in small requests and measure on your own reviews.
4. Describe what does not belong in a category as carefully as what does.
5. Use the confidence value to decide which labels a person reads first.
6. Check every draft twice, with plain rules and with yes or no questions, and cap the retries.
7. Never post automatically. A person approves and posts.

## What are the limits?

- The sample reviews are synthetic, and we have not measured the labels against a set of real, hand-labeled reviews, so treat them as a first pass.
- Clef-Flash can be confidently wrong, and the draft checks do not replace a person.
- The app reads reviews from a CSV file and does not collect them from review sites. Take the export from the review tool your client uses, within its terms.
- Reviews contain personal data. In this app they stay in a local database on your computer, and inference on Regolo keeps no data after each request. Whether your setup is compliant with data protection law still depends on how you build and operate it.

## Frequently asked questions

### Can an LLM reply to reviews automatically?

It can draft them, and in this app a person approves every reply. The labels and the checks reduce the work and the risk, but a public reply is the client's voice, so we do not post automatically.

### What does Clef-Flash add compared with asking the LLM to do everything?

Clef-Flash returns a choice from your own list with a confidence value, which is easy to filter, log and check, and it does the decisions before and after the writing step. In this app, a review is labeled in about 0.6 seconds per request on average (requests run in parallel) and a draft is checked in a single request.

### How do I keep replies on brand for several clients?

With one profile per client: voice, topics, the facts the reply may state, things it must never do and forbidden phrases. The checks use the same profile, so a rule you add is both an instruction for the writer and a test for the draft.

### How fast should you reply to a review?

In BrightLocal's 2026 survey of 1,002 US adults, 81% expect to hear back within a week. This app drafts and checks a reply in about 1 to 3 seconds, so the wait is for the person who approves it.

### Where do the reviews come from?

From the sample data or from a CSV file. Most review tools can export their reviews, so check the export options of the tool your client uses, and use the template the app provides for the columns it expects.

### Does it work with reviews in other languages?

The sample includes Italian, German, French and Spanish reviews. Clef-Flash labels the language, the writer replies in it, and one check confirms that the reply is in the same language as the review.

### Is there a free way to try it?

New Regolo users get a 30 day free trial, and the pricing page has the current terms. The app saves your key locally after verifying it.

## Next steps

Clone the <a href="https://github.com/regolo-ai/tutorials/tree/main/review-reply-copilot" target="_blank" rel="noopener noreferrer">review-reply-copilot project</a>, add your Regolo key in step 1, load the sample reviews and try one of your own client's brand profiles. The <a href="https://docs.regolo.ai" target="_blank" rel="noopener noreferrer">Regolo documentation</a> lists the current endpoints and models.

FAQ and Article JSON-LD for the Custom HTML block at the end of the post:

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "Article", "headline": "AI review responses with guardrails: Clef-Flash decides, an LLM writes, a person approves",
     "description": "Draft review replies in your client's voice: Clef-Flash labels and checks, an LLM writes, a person approves. Open source, with measured results on Regolo.",
     "dateModified": "2026-10-14", "inLanguage": "en", "publisher": {"@type": "Organization", "name": "Regolo", "url": "https://regolo.ai"}},
    {"@type": "FAQPage", "mainEntity": [
      {"@type": "Question", "name": "Can an LLM reply to reviews automatically?", "acceptedAnswer": {"@type": "Answer", "text": "It can draft them, and in this app a person approves every reply. The labels and the checks reduce the work and the risk, but a public reply is the client's voice, so we do not post automatically."}},
      {"@type": "Question", "name": "What does Clef-Flash add compared with asking the LLM to do everything?", "acceptedAnswer": {"@type": "Answer", "text": "Clef-Flash returns a choice from your own list with a confidence value, which is easy to filter, log and check, and it does the decisions before and after the writing step."}},
      {"@type": "Question", "name": "How do I keep replies on brand for several clients?", "acceptedAnswer": {"@type": "Answer", "text": "With one profile per client: voice, topics, the facts the reply may state, things it must never do and forbidden phrases. The checks use the same profile."}},
      {"@type": "Question", "name": "How fast should you reply to a review?", "acceptedAnswer": {"@type": "Answer", "text": "In BrightLocal's 2026 survey of 1,002 US adults, 81% expect to hear back within a week. This app drafts and checks a reply in about 1 to 3 seconds, so the wait is for the person who approves it."}},
      {"@type": "Question", "name": "Where do the reviews come from?", "acceptedAnswer": {"@type": "Answer", "text": "From the sample data or from a CSV file. Most review tools can export their reviews, so check the export options of the tool your client uses."}},
      {"@type": "Question", "name": "Does it work with reviews in other languages?", "acceptedAnswer": {"@type": "Answer", "text": "The sample includes Italian, German, French and Spanish reviews. Clef-Flash labels the language, the writer replies in it, and one check confirms that the reply is in the same language as the review."}},
      {"@type": "Question", "name": "Is there a free way to try it?", "acceptedAnswer": {"@type": "Answer", "text": "New Regolo users get a 30 day free trial, and the pricing page has the current terms."}}
    ]}
  ]
}
</script>
```
