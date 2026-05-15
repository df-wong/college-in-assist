# College-In Research Assistant

A Telegram bot that helps researchers, students, and academics analyze academic papers and accelerate their research workflow through natural-language conversation.
 
## Features

| Command | What it does |
|---|---|
| `/summarize` | Send a PDF, paste a paper URL, or paste raw text → structured summary (question, methodology, findings, limitations, conclusions). |
| `/gaps` | Identify research gaps in your last uploaded paper and propose concrete follow-up studies. |
| `/review <topic>` | Search arXiv + PubMed and produce a synthesized literature review with citations and source list. |
| `/cite <text>` | Generate a citation in your preferred style. |
| `/style <APA\|IEEE\|MLA\|Chicago\|BibTeX>` | Set your default citation style (persisted). |
| `/proposal <topic>` | Generate a structured research proposal (abstract, RQs, methodology, timeline, references). |
| `/interpret <stats text>` | Explain p-values, confidence intervals, regression tables, etc. in plain language. |

You can also just **upload a PDF** and the bot will auto-summarize it and remember it for follow-up commands.

## Architecture

```
college-in-assist/
├── bot/                # Telegram entrypoint + handlers + service container
├── core/               # LLM client, PDF extraction, prompt templates
├── sources/            # arXiv + PubMed clients (shared Paper dataclass)
├── features/           # One module per capability
├── storage/            # SQLite (users, sessions, search cache)
├── config.py           # Env-driven settings
└── requirements.txt
```

**Stack**: Python 3.11+, `python-telegram-bot` v21 (long polling), OpenAI Chat Completions, `pypdf`, `arxiv`, `pymed`, SQLite.

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
Bot:    [synthesized review with [n] citations]
        Sources:
        [1] ... arxiv:2401.12345
        [2] ... pubmed:38123456
        ...

You:    /style IEEE
You:    /cite Smith J. 2023 Deep learning in healthcare. Nature.
Bot:    (IEEE) J. Smith, "Deep learning in healthcare," Nature, 2023.

You:    /interpret t(48) = 2.31, p = 0.025, d = 0.42
Bot:    [plain-language explanation]
```

## Notes & limits

- **PDF size cap**: 25 MB, and very long papers are head+tail truncated when sent to the LLM.
- **Scanned PDFs**: text extraction will be empty; OCR is out of scope for v1.
- **Google Scholar**: intentionally not included — no official API and `scholarly` gets rate-limited / blocked. arXiv + PubMed cover most disciplines; SerpAPI Scholar can be added later behind a flag.
- **Citations**: the LLM never invents missing fields — unknown values are marked `[n.d.]` or `[Unknown]`.
- **State**: `last_paper` is per-user in SQLite, so `/gaps` and follow-ups work across reconnects. Search results are cached for 6 hours.

## Roadmap

- Vector store + RAG over user's uploaded papers (multi-paper Q&A).
- Async parallel source queries.
- Webhook deployment (FastAPI + ASGI) for serverless.
- Optional Scholar via SerpAPI.
- OCR fallback (`ocrmypdf`) for scanned PDFs.
