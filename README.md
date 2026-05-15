# College-In Research Assistant

A Telegram bot that helps researchers, students, and academics analyze academic papers and accelerate their research workflow through natural-language conversation.

## Features

| Command | What it does |
|---|---|
| `/summarize` | Send a PDF, paste a paper URL, or paste raw text → structured summary (question, methodology, findings, limitations, conclusions). |
| `/gaps` | Identify research gaps in your last uploaded paper and propose concrete follow-up studies. |
| `/review <topic>` | Search arXiv + PubMed + Google Scholar and produce a synthesized literature review with citations, contradiction detection, and source list. |
| `/cite <text>` | Generate a citation in your preferred style. |
| `/style <APA\|IEEE\|MLA\|Chicago\|BibTeX>` | Set your default citation style (persisted). |
| `/proposal <topic>` | Generate a structured research proposal (abstract, RQs, methodology, timeline, references). |
| `/interpret <stats text>` | Explain p-values, confidence intervals, regression tables, etc. in plain language. |
| `/convert` | Convert files between formats (see below). |

### File Conversion (`/convert`)

Upload a file after running `/convert` and the bot will offer available conversions:

| Input | Output options |
|---|---|
| PDF | Word (.docx), PNG images |
| Word (.docx) | PDF, PNG images, Plain text (.txt) |
| TXT | Word (.docx), PDF |
| Image (PNG/JPG) | PDF |

The bot auto-detects the file type and shows inline buttons when multiple conversions are possible.

### Auto-summarize

You can also just **upload a PDF** (without `/convert`) and the bot will auto-summarize it and remember it for follow-up commands like `/gaps` and `/interpret`.

## Architecture

```
college-in-assist/
├── bot/                # Telegram entrypoint + handlers + service container
├── core/               # LLM client, PDF extraction, prompt templates
├── sources/            # arXiv + PubMed + Google Scholar clients (shared Paper dataclass)
├── features/           # One module per capability (summarize, gaps, review, cite, proposal, interpret, convert)
├── storage/            # SQLite (users, sessions, search cache)
├── config.py           # Env-driven settings
└── requirements.txt
```

**Stack**: Python 3.11+, `python-telegram-bot` v21 (long polling), OpenAI Chat Completions, `pypdf`, `PyMuPDF`, `python-docx`, `Pillow`, `arxiv`, `pymed`, `scholarly`, SQLite.

## Setup

```bash
# 1. Clone and enter
cd college-in-assist

# 2. Create virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env and fill in:
#   TELEGRAM_BOT_TOKEN  (from @BotFather)
#   OPENAI_API_KEY
#   PUBMED_EMAIL        (any contact address; NCBI requests one)

# 5. Run
python -m bot.main
```

The bot uses long polling, so no public URL or webhook is required.

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Required. From [@BotFather](https://t.me/BotFather). |
| `OPENAI_API_KEY` | — | Required. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Any chat-completions-capable model. |
| `PUBMED_EMAIL` | `research@example.com` | NCBI E-utilities expects a contact email. |
| `DB_PATH` | `./data/assistant.db` | SQLite location. |
| `LOG_LEVEL` | `INFO` | Standard Python logging levels. |

## Usage walkthrough

```
You:    /start
Bot:    [welcome + command list]

You:    [uploads paper.pdf]
Bot:    [structured summary]
        Stored. Try /gaps for research-gap analysis or /interpret for stats explanations.

You:    /gaps
Bot:    [acknowledged limitations, unaddressed gaps, follow-up studies]

You:    /review graph neural networks for drug discovery
Bot:    [synthesized review with [n] citations from arXiv, PubMed, Scholar]
        Sources:
        [1] ... arxiv:2401.12345
        [2] ... pubmed:38123456
        [3] ... scholar:...
        ...

You:    /style IEEE
You:    /cite Smith J. 2023 Deep learning in healthcare. Nature.
Bot:    (IEEE) J. Smith, "Deep learning in healthcare," Nature, 2023.

You:    /interpret t(48) = 2.31, p = 0.025, d = 0.42
Bot:    [plain-language explanation]

You:    /convert
Bot:    Send me a file to convert...
You:    [uploads thesis.pdf]
Bot:    Choose a conversion format:
        [PDF → Word (.docx)]  [PDF → PNG images]
You:    [taps PDF → Word]
Bot:    [sends thesis.docx]
```

## Notes & limits

- **PDF size cap**: 25 MB, and very long papers are head+tail truncated when sent to the LLM.
- **Scanned PDFs**: text extraction will be empty; OCR is out of scope for v1.
- **Google Scholar**: uses the `scholarly` library which scrapes Scholar. May be rate-limited under heavy use; arXiv and PubMed serve as reliable fallbacks.
- **Citations**: the LLM never invents missing fields — unknown values are marked `[n.d.]` or `[Unknown]`.
- **State**: `last_paper` is per-user in SQLite, so `/gaps` and follow-ups work across reconnects. Search results are cached for 6 hours.
- **Conversion quality**: Word→PDF and PDF→Word are text-based conversions (layout/formatting is best-effort, not pixel-perfect).
- **PNG output**: capped at 20 pages per conversion to avoid flooding the chat.

## Roadmap

- Vector store + RAG over user's uploaded papers (multi-paper Q&A).
- Async parallel source queries.
- Webhook deployment (FastAPI + ASGI) for serverless.
- OCR fallback (`ocrmypdf`) for scanned PDFs.
- Batch conversion (multiple files at once).
- Image-to-text (OCR) before summarization.
