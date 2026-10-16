# Importing reviews

The app takes reviews from two sources. Each one is a card in step 2 of the interface.

## 1. Sample reviews

Expects nothing. It loads synthetic reviews written for the demo (37 for Acme Outdoor, 35 for Northwind Cloud, in English, Italian, German, French and Spanish) so you can try the whole flow.

## 2. CSV file

Expects a UTF-8 CSV with a header row and one review per row. A ready template is in [`data/reviews-template.csv`](../data/reviews-template.csv), and the interface has a **Download the template** button.

```csv
author,rating,title,text,date
Jane D.,5,"Fast delivery","The boots arrived in three days and fit perfectly. Will order again.",2026-09-28
Marco R.,2,"Late and no updates","Order took 14 days and nobody answered my email.",2026-09-27
Sam K.,,"","Great customer service, they fixed the issue the same day.",2026-09-26
```

| Column | Required | Notes |
|---|---|---|
| `text` | yes | the review itself. Also understood: `review`, `body`, `content`, `comment`, `review text`, `review content` |
| `rating` | no | 1 to 5. Also understood: `stars`, `score`, `review rating`. Empty is fine |
| `title` | no | also `headline`, `subject`, `review title` |
| `author` | no | also `name`, `user`, `reviewer`, `reviewer name`, `consumer`. Use initials, not full names, when you can |
| `date` | no | any format, kept as text. Also `created`, `published`, `review date`, `date of experience` |

Rows without text are skipped, and a row that is already in the database for the same client is not added twice.

## Where do the reviews come from?

Most review tools can export a CSV, so check the export options of the one your client uses. If the tool offers an official API, you can pull the reviews with the client's own credentials and save them as a CSV in this format. The app does not scrape review sites, and it does not collect from any site on its own.
