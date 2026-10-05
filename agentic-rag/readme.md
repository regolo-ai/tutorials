# regolo agentic rag with hierarchical index retrieval

this repository provides a practical implementation of the hierarchical agentic retrieval architecture described in the tutorial using the `brick-complexity-pro` endpoint on regolo. the system runs entirely on top of a local open-source sqlite database, ensuring zero external database dependencies or recurring container hosting costs.

## quick start instructions

to initialize your local virtual environment and install all dependencies using the green regolo setup script, execute the following commands:

```bash
chmod +x setup.sh
./setup.sh
```

the script detects whether an existing `.venv` environment exists, creates one if missing, installs all required python dependencies, and initializes your local `.env` configuration file.

## execution modes

after completing setup, you can run the laboratory through two distinct interfaces:

### 1. interactive terminal interface

run the main script without parameters to display the guided terminal menu:

```bash
source .venv/bin/activate
python3 main.py
```

the menu enables developers to ingest custom documents from a designated path, run empirical comparisons between the baseline and hierarchical agentic pipelines, or run tests on the sample enterprise policies.

### 2. direct command-line execution

if you want to automate ingestion and evaluation directly from shell scripts, pass command line flags:

```bash
# ingest custom folder and compare on target inquiry
python3 main.py --path ./sample_data --query "compare the 2026 refund policy with 2025 and explain which exceptions changed."

# run the sample verification test
python3 main.py --sample-test
```

## local hierarchical index structure

the local database `rag_storage.sqlite3` maintains two complementary representations of the document corpus:

- `baseline_chunks`: a flat chunk table where documents are split into isolated chunks without parent-child relational links.
- `parent_summaries`: a parent table storing high-level thematic summaries used by the controller to discover candidate files.
- `child_chunks`: an analytical child table with relational foreign keys storing granular sections retrieved only when relevant.

this architectural decoupling allows `brick-complexity-pro` to call the typed tools `search_topic_index`, `read_chunk_details`, and `keyword_search` to gather factual proof without flooding the prompt context window.
