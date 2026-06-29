# EduAgent — AI Academic Assistant

A full-stack AI study assistant: AI Chat (with RAG over your own documents), Notes
Generator, Summarizer, Quiz Generator, Flashcards, and Assignment Helper — all
running on a **local LLM via Ollama**, with a pluggable agent layer that mirrors
Google's Agent Development Kit (ADK) pattern so you can swap to Gemini later if
you want.

Stack: **FastAPI** + **Jinja2** (server-rendered HTML, no separate frontend build
step) + **SQLite** (via SQLAlchemy) + **ChromaDB** (vector store for RAG) +
**Ollama** (local LLM + embeddings).

---

## 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (`ollama serve`, or it
  auto-starts on macOS/Windows after install)
- At least one chat model and one embedding model pulled:

```bash
ollama pull llama3              # chat model (swap for any model you like)
ollama pull nomic-embed-text    # embedding model, used for RAG
```

Verify Ollama is up:

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON list including the models you pulled.

---

## 2. Install & Run

```bash
# 1. Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy the env file (defaults already point at a local Ollama on :11434)
cp .env.example .env

# 4. Run the app
uvicorn app.main:app --reload
```

Open **http://localhost:8000** — you'll land on the login screen. Click
**Sign up** to create your first account (this all runs locally — no email
verification, no external services).

---

## 3. Project Structure

```
eduagent/
├── app/
│   ├── main.py                 # FastAPI app entrypoint, mounts routers
│   ├── config.py                # Settings loaded from .env
│   ├── database.py              # SQLAlchemy engine/session
│   ├── models.py                # ORM models (User, Note, Quiz, etc.)
│   ├── auth.py                  # Password hashing + session helpers
│   ├── routers/                 # One router per feature/page
│   │   ├── auth_router.py       # /login /signup /logout
│   │   ├── dashboard_router.py  # /dashboard
│   │   ├── chat_router.py       # /chat, RAG document upload
│   │   ├── notes_router.py      # /notes
│   │   ├── summarizer_router.py # /summarizer
│   │   ├── quiz_router.py       # /quiz
│   │   ├── flashcards_router.py # /flashcards
│   │   ├── assignment_router.py # /assignment-helper
│   │   ├── planner_router.py    # /planner
│   │   └── misc_router.py       # /analytics /history /bookmarks /settings
│   ├── services/
│   │   ├── agent_service.py     # Agent abstraction: LocalOllamaAgent / GoogleADKAgent
│   │   ├── academic_service.py  # Prompt templates for each feature
│   │   ├── rag_service.py       # Chunking, embeddings, ChromaDB retrieval
│   │   └── activity_logger.py   # Records dashboard activity feed
│   ├── templates/                # Jinja2 HTML templates (one per page)
│   └── static/
│       ├── css/style.css         # Design system (matches the EduAgent red/black theme)
│       └── js/app.js             # Chat, quiz, flashcard interactivity
├── data/
│   ├── db/eduagent.db            # SQLite database (created on first run)
│   ├── chroma/                   # ChromaDB vector store (created on first run)
│   └── uploads/                  # User-uploaded documents
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. How the AI features work

### AI Chat + RAG
1. Upload a `.pdf`, `.txt`, or `.md` file in the AI Chat sidebar.
2. The file is split into overlapping text chunks (`app/services/rag_service.py`).
3. Each chunk is embedded with Ollama's `nomic-embed-text` model and stored in a
   per-user ChromaDB collection (`data/chroma/`).
4. When you ask a question with **"Use my documents"** toggled on, your query is
   embedded too, the most similar chunks are retrieved, and they're injected into
   the LLM prompt as context — this is Retrieval-Augmented Generation.

### Notes / Summarizer / Quiz / Flashcards / Assignment Helper
Each feature builds a tailored prompt (see `app/services/academic_service.py`)
and sends it to the active agent. Quiz and Flashcards ask the model to return
structured JSON, which is parsed and rendered as interactive UI (clickable quiz
options with instant grading, flip-to-reveal flashcards).

### The Agent layer (Ollama by default, Google ADK optional)
`app/services/agent_service.py` defines a small `BaseAgent` interface with a
`.run(system_prompt, user_prompt, history)` method, modeled after how Google's
ADK structures an Agent. Two implementations exist:

- **`LocalOllamaAgent`** (default) — talks to your local Ollama server. No API
  key, no internet required after the model is pulled.
- **`GoogleADKAgent`** (optional) — a thin wrapper around the real `google-adk`
  package + Gemini. To use it:
  1. `pip install google-adk`
  2. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
  3. In `.env`, set `AGENT_BACKEND=adk` and `GOOGLE_API_KEY=your-key-here`
  4. Restart the app

  Note: the ADK ecosystem moves fast — check the
  [official ADK docs](https://google.github.io/adk-docs/) if the SDK's
  session/runner API has changed since this was written, and adjust
  `GoogleADKAgent.run()` accordingly.

Every router calls `academic_service`, which calls `get_agent()` — so switching
backends doesn't require touching any route or template code.

---

## 5. Customizing

- **Change the chat/embedding model**: edit `OLLAMA_CHAT_MODEL` /
  `OLLAMA_EMBED_MODEL` in `.env` to any model you've pulled (e.g. `mistral`,
  `phi3`, `qwen2.5`).
- **Change the branding**: edit `app/templates/base.html` (sidebar/topbar) and
  `app/static/css/style.css` (`:root` CSS variables — palette, fonts).
- **Add a new AI feature**: add a prompt builder in `academic_service.py`, a new
  router in `app/routers/`, a template in `app/templates/`, and register the
  router in `app/main.py`.
- **Swap SQLite for Postgres**: change `DATABASE_URL` in `.env` to a Postgres
  connection string and `pip install psycopg2-binary`.

---

## 6. Notes & limitations

- This uses FastAPI's `create_all()` for simplicity — for schema changes after
  you have real data, add [Alembic](https://alembic.sqlalchemy.org/) migrations.
- Sessions are cookie-based via `SessionMiddleware`; **change `SECRET_KEY` in
  `.env`** before deploying anywhere beyond your own machine.
- Quiz/Flashcard generation asks the LLM to emit JSON. Most local models do
  this reliably, but if a model returns malformed JSON, the app falls back to a
  clearly-labeled placeholder so the UI never crashes — just regenerate.
- This is a local-first, single-machine learning tool, not a hardened
  multi-tenant production system (e.g. no rate limiting, no email verification).
  Add those if you plan to deploy it publicly.

---

## 7. Quick troubleshooting

| Symptom | Likely cause |
|---|---|
| Chat replies with a connection error | Ollama isn't running — run `ollama serve` |
| RAG upload fails / no chunks | Check the embedding model is pulled: `ollama pull nomic-embed-text` |
| Quiz/Flashcards show a "could not parse" card | The chat model returned non-JSON text — try regenerating, or switch to a more instruction-following model |
| `pip install` fails on `google-adk` | It's optional — only needed if `AGENT_BACKEND=adk`. Leave it out and stay on `local` |
