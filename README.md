# ShopSphere — Next.js + FastAPI + PostgreSQL

## Stack
- Next.js + TypeScript + Tailwind CSS
- FastAPI + Pydantic
- PostgreSQL
- SQLAlchemy 2 ORM (database mapping)
- Alembic migrations
- JWT authentication
- Docker Compose for PostgreSQL

## Structure
```text
ShopSphere/
├── frontend/
│   ├── app/
│   │   ├── cart/page.tsx
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   ├── products/[id]/page.tsx
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   ├── lib/
│   └── types/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── chatbot.py
│   │   ├── models/
│   │   ├── schemas/
│   │   └── main.py
│   ├── alembic/versions/
│   ├── requirements.txt
│   └── .env.example
└── docker-compose.yml
```

## Database mapping
SQLAlchemy maps:
- Category 1 -> many Products
- User 1 -> 1 Cart
- Cart 1 -> many CartItems
- Product 1 -> many CartItems
- User 1 -> many Orders
- Order 1 -> many OrderItems
- Product 1 -> many OrderItems

## Run PostgreSQL
```bash
docker compose up -d db
```

## Run backend

For first-time setup, run this from the repository root (`E:\ShopSphere`). If your
terminal is already in `backend`, skip `cd backend`. The virtual environment only
needs to be created once; do not recreate it if `.venv` already exists.

```powershell
cd backend
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv .venv }
requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.db.seed
```

The seed command imports Fake Store API products and explicitly identified LED
products from DummyJSON into the local database. It needs an internet connection
and can be rerun safely; imported products are matched by their source IDs.
Rerun it to apply.venv\Scripts\python.exe -m pip install -r  category updates: men's and women's clothing are kept
separate (including jackets, tops, and footwear), and recognizable types such
as storage, LED lighting, computer accessories, jewelry, and monitors get
specific recommendation groups. Recommendations prefer the exact product group,
then consider only products in the same department that share meaningful words
in their names. Price proximity and stock availability help rank close matches;
unrelated products are not used just to fill the list.

### Product chatbot

The floating Messages chat is available across shop and product pages for
authenticated users. Each time the chat is opened it creates a new, separate
conversation; closing and opening it again starts fresh. Users can browse and
reopen previous conversations from the chat history. The `/chat` page also
starts a new conversation whenever it is opened. Conversations are stored
separately in PostgreSQL; public product details are
embedded with the configured Hugging Face embedding model locally on CPU and
indexed in ChromaDB at `backend/chroma_db`. The embedding model is downloaded on first
use and may use `HF_TOKEN` for authenticated downloads. Groq generates answers
using the retrieved catalog details and the signed-in user's recent conversation.

Set `GROQ_API_KEY` in `backend/.env` to a Groq API key. `HF_TOKEN` is only
needed if Hugging Face requires authentication to download the embedding
model. `HF_EMBEDDING_MODEL`, `GROQ_CHAT_MODEL`, and `CHROMA_PATH` can be
overridden there; defaults are documented in `backend/.env.example`. Apply the
database migrations with `alembic upgrade head` from `backend` before using
the chatbot. Groq receives the user's question and context from the current
chat only; do not send sensitive personal information through chat. Retrieved
catalog matches are returned as structured product data and displayed as
product cards in chat.

To start or restart the backend later, run this from `backend`. Calling Uvicorn
through the venv's Python explicitly prevents accidentally using Anaconda or a
different system Python:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Run frontend
From the repository root, you can start the frontend with:

```powershell
npm run dev
```

Or run the frontend commands directly from its folder:

```powershell
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000

## Demo admin
```text
email: admin@shopsphere.local
password: Admin123!
```

The UI is intentionally clean and easy to extend. For production, add payment integration, image storage, refresh tokens/secure cookies, rate limiting, email verification, admin dashboard, and deployment secrets.
