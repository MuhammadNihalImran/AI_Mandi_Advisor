# AI Mandi Advisor

An AI-powered mandi (market) advisor that provides crop price insights and recommendations for farmers.

## Project Structure

```
AI_Mandi_Advisor/
├── server/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # FastAPI app entrypoint
│   │   ├── config.py       # Environment variables (pydantic-settings)
│   │   ├── routers/        # API endpoint definitions
│   │   ├── services/       # Business logic (predictor, RAG, AI advisor, weather)
│   │   ├── models/         # Pydantic schemas
│   │   └── db/             # SQLAlchemy database code
│   ├── tests/              # pytest test suite (60 tests, 92% coverage)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── client/                 # React + Vite frontend
│   ├── src/
│   │   ├── components/     # WeatherInputs, PricePrediction, AIAdvice
│   │   ├── api.js          # API client (fetch wrapper)
│   │   ├── App.jsx         # Main app component
│   │   └── index.css       # Design tokens + global styles
│   └── .env                # VITE_API_BASE_URL
├── docker-compose.yml
└── reference/              # Reference datasets and files
```

## Local Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd AI_Mandi_Advisor
```

### 2. Create a virtual environment

```bash
cd server
python -m venv venv
```

### 3. Activate the virtual environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

**Production (deploying on Railway/Render):**
```bash
pip install -r requirements.txt
```

**Development (running tests locally):**
```bash
pip install -r requirements-dev.txt
```

All versions are pinned in both files to avoid deployment surprises.

### 5. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` and add your `GROQ_API_KEY`:
```
GROQ_API_KEY=your_groq_api_key_here
DATABASE_URL=sqlite:///./mandi.db
CORS_ORIGINS=["*"]
```

Get your free Groq API key from [console.groq.com](https://console.groq.com/keys).

### 6. Seed the database (one-time)

```bash
python -m app.db.seed
```

### 7. Run the server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

- **Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

### 8. Run tests

```bash
python -m pytest tests/
```

## Frontend (React + Vite)

### 1. Install dependencies

```bash
cd client
npm install
```

### 2. Configure API base URL

The `.env` file in `client/` already has:
```
VITE_API_BASE_URL=http://localhost:8000
```

### 3. CORS reminder

> **Important:** The backend must allow requests from the Vite dev server.  
> In `server/.env`, set `CORS_ORIGINS` to include `http://localhost:5173`:
> ```
> CORS_ORIGINS=["http://localhost:5173"]
> ```
> Or use `["*"]` for development (allows all origins).

### 4. Run the dev server

```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`.

### Components

| Component | Description |
|---|---|
| `<WeatherInputs />` | Temperature/rainfall/humidity sliders + "Live weather fetch" button |
| `<PricePrediction />` | Chalkboard-style ticket showing predicted price + delta % |
| `<AIAdvice />` | "Farmer advice lein" button → AI advice text + RAG history |

## Docker (Local)

### Build and run with Docker Compose

From the project root:

```bash
# Create .env in the root directory (same level as docker-compose.yml)
cp server/.env.example .env
# Edit .env and add your GROQ_API_KEY

# Build and start
docker compose up --build

# Run in background
docker compose up --build -d
```

The API will be available at `http://localhost:8000`.

### Build and run manually

```bash
cd server
docker build -t mandi-advisor .
docker run -p 8000:8000 --env-file ../.env mandi-advisor
```

## Deployment

Both Railway and Render offer free tiers that work well with FastAPI + Docker.

### Option A: Railway (Recommended)

Railway auto-detects the Dockerfile and makes deployment trivial.

1. **Create a project** at [railway.app](https://railway.app) and connect your GitHub repo.

2. **Set the root directory** to `server` in Railway's deploy settings (since the Dockerfile lives there).

3. **Add environment variables** in Railway's "Variables" tab:

   | Variable | Value |
   |---|---|
   | `GROQ_API_KEY` | `gsk_your_actual_key_here` |
   | `DATABASE_URL` | `sqlite:///./data/mandi.db` |
   | `CORS_ORIGINS` | `["https://your-frontend-domain.com"]` |

4. **Deploy** -- Railway will automatically build the Dockerfile and start the container.

5. **Generate a domain** in Railway's settings to get a public URL like `mandi-advisor.up.railway.app`.

6. **Seed the database** (one-time) via Railway's shell:
   ```bash
   railway run python -m app.db.seed
   ```

**Free tier:** $5 credit/month (no card required), enough for ~500 hours of a small service.

### Option B: Render

Render supports Docker-based services with automatic deploys from GitHub.

1. **Create a new Web Service** at [render.com](https://render.com) and connect your GitHub repo.

2. **Configure the service:**

   | Setting | Value |
   |---|---|
   | **Root Directory** | `server` |
   | **Environment** | `Docker` |
   | **Build Command** | *(leave empty -- Dockerfile handles it)* |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |

3. **Add environment variables** in Render's "Environment" section:

   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | `gsk_your_actual_key_here` |
   | `DATABASE_URL` | `sqlite:///./data/mandi.db` |
   | `CORS_ORIGINS` | `["https://your-frontend.onrender.com"]` |

4. **Deploy** -- Render builds the Dockerfile and starts the service.

5. Your API will be live at `https://mandi-advisor.onrender.com`.

**Free tier:** 750 hours/month for web services (spins down after 15 min inactivity, cold start ~30s).

### Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | **Yes** | — | Groq API key for AI advice generation |
| `DATABASE_URL` | No | `sqlite:///./mandi.db` | SQLAlchemy database URL |
| `CORS_ORIGINS` | No | `["*"]` | Allowed CORS origins (JSON list) |
| `DEBUG` | No | `false` | Enable debug mode (exposes stack traces) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | App info |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/history?limit=N` | Historical mandi prices from DB |
| `POST` | `/api/predict` | ML price prediction (rate-limited: 60/15min) |
| `POST` | `/api/advice` | Full pipeline: predict + RAG + AI advice (rate-limited: 20/15min) |
| `GET` | `/api/weather/live` | Live Faisalabad weather from Open-Meteo |
