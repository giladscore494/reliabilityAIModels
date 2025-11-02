# 🚗 Car Reliability Analyzer - Full Stack Application

A comprehensive car reliability analysis platform for the Israeli market, featuring AI-powered insights, caching, rate limiting, and user authentication.

## 📋 Architecture

### Client (React + Vite)
- **Vision-UI Dashboard** for elegant user interface
- **React Router** for navigation
- **Google OAuth** for authentication
- **Axios** for API communication
- Pages: Dashboard, Analyze, History, ROI Tool, Leads, Login

### Server (FastAPI + Python)
- **FastAPI** REST API with full CORS support
- **Google Gemini AI** for reliability analysis
- **Google Sheets** as primary database (source of truth)
- **Optional PostgreSQL** for rate limits/telemetry/leads
- **45-day caching** with similarity matching
- **Rate limiting**: 1000/day global, 5/day per user

## 🏗️ Repository Structure

```
/
├─ client/                          # React frontend
│  ├─ src/
│  │  ├─ api/http.js               # Axios with auth headers
│  │  ├─ pages/                    # App pages
│  │  │  ├─ Dashboard.jsx
│  │  │  ├─ Analyze.jsx
│  │  │  ├─ History.jsx
│  │  │  ├─ RoiTool.jsx
│  │  │  ├─ Leads.jsx
│  │  │  └─ Login.jsx
│  │  ├─ components/               # UI components
│  │  │  ├─ ReliabilityForm.jsx
│  │  │  ├─ ScoreBreakdownCard.jsx
│  │  │  ├─ IssuesCostsCard.jsx
│  │  │  ├─ ChecksCard.jsx
│  │  │  ├─ CompetitorsCard.jsx
│  │  │  └─ QuotaBadge.jsx
│  │  ├─ utils/
│  │  │  └─ modelsDictFallback.js
│  │  ├─ App.jsx
│  │  ├─ router.jsx
│  │  └─ main.jsx
│  ├─ package.json
│  └─ vite.config.js
│
├─ server/                          # FastAPI backend
│  ├─ app.py                       # Main FastAPI app with routes
│  ├─ models_logic.py              # AI model calling & prompts
│  ├─ sheets_layer.py              # Google Sheets integration
│  ├─ cache_lookup.py              # Cache search & similarity
│  ├─ rate_limits.py               # Quota checking
│  ├─ auth.py                      # Google OAuth verification
│  ├─ schemas.py                   # Pydantic models
│  ├─ leads.py                     # Lead handling
│  ├─ roi.py                       # ROI calculations
│  ├─ settings.py                  # Environment config
│  ├─ requirements.txt
│  └─ gunicorn_conf.py
│
├─ railway.json                    # Railway deployment config
├─ env.example                     # Environment variables template
├─ .gitignore
└─ README.md
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.9+
- Google Cloud project with:
  - Gemini API access
  - Service Account for Sheets API
  - OAuth 2.0 Client ID

### Local Development

#### 1. Clone the repository
```bash
git clone <your-repo-url>
cd reliabilityAIModels
```

#### 2. Set up environment variables
```bash
cp env.example .env
# Edit .env with your actual credentials
```

#### 3. Start the server
```bash
cd server
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

#### 4. Start the client (in a new terminal)
```bash
cd client
npm install
npm run dev
```

The app will be available at:
- Client: http://localhost:3000
- Server API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📊 Google Sheets Setup

### Headers (Row 1)
The sheet must have these exact headers (case-sensitive):
```
date, user_id, make, model, sub_model, year, fuel, transmission,
mileage_range, base_score_calculated, score_breakdown, avg_cost,
issues, search_performed, reliability_summary, issues_with_costs,
sources, recommended_checks, common_competitors_brief
```

### Service Account Permissions
1. Create a Service Account in Google Cloud Console
2. Enable Google Sheets API and Google Drive API
3. Download the JSON key file
4. Share your Google Sheet with the service account email
5. Set `GOOGLE_SERVICE_ACCOUNT_JSON` in env (entire JSON as one line)

## 🔐 Google OAuth Setup

1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Add authorized JavaScript origins:
   - http://localhost:3000 (development)
   - Your production client URL
4. Add authorized redirect URIs if needed
5. Copy the Client ID to:
   - `GOOGLE_OAUTH_CLIENT_ID` (server)
   - `VITE_GOOGLE_CLIENT_ID` (client)
   - `GOOGLE_OAUTH_AUDIENCE` (server, same as client ID)

## 🌐 API Endpoints

### Core Endpoints

#### `POST /v1/analyze`
Analyze car reliability
- **Body**: `{ make, model, sub_model, year, fuel_type, transmission, mileage_range }`
- **Headers**: `Authorization: Bearer <google_id_token>` (optional)
- **Response**: Analysis result with score, breakdown, issues, costs, checks, competitors

#### `GET /v1/history?limit=100&offset=0`
Get user's analysis history (requires auth)

#### `GET /v1/history/export.csv`
Export user history as CSV (requires auth)

#### `POST /v1/leads`
Submit a lead for insurance/financing/dealer
- **Body**: `{ type: "insurance|financing|dealer", payload: { name, phone, email, note } }`

#### `POST /v1/roi`
Calculate ROI and future value
- **Body**: `{ make, model, year, purchase_price, current_mileage, expected_annual_mileage }`

#### `GET /v1/quota`
Check remaining quota for user and global

#### `GET /health`
Health check

## 🚢 Deployment to Railway

### Using railway.json (Recommended)

1. Push code to GitHub
2. In Railway Dashboard:
   - New Project → Deploy from GitHub repo
   - Connect your repository
   - Railway will auto-detect `railway.json`
3. Set environment variables in Railway dashboard for both services
4. Deploy!

### Environment Variables (Set in Railway Dashboard)

**Server Service:**
- `ALLOWED_ORIGINS`: Your client URL (or "*" for all origins)
- `GOOGLE_SHEET_ID`: Your sheet ID
- `GOOGLE_SERVICE_ACCOUNT_JSON`: Service account JSON (one line)
- `GEMINI_API_KEY`: Your Gemini API key
- `GOOGLE_OAUTH_CLIENT_ID`: OAuth client ID
- `GOOGLE_OAUTH_AUDIENCE`: Same as client ID
- `PORT`: 8000 (Railway sets this automatically)

**Client Service:**
- `VITE_API_BASE_URL`: Your server URL (e.g., https://car-dashboard-server-production.up.railway.app)
- `VITE_GOOGLE_CLIENT_ID`: OAuth client ID

## 🧪 Testing

### Test Server
```bash
# Health check
curl https://your-server.up.railway.app/health

# Test analysis (anonymous)
curl -X POST https://your-server.up.railway.app/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "make": "Mazda",
    "model": "Mazda3 (2003-2025)",
    "sub_model": "האצ'\''בק",
    "year": 2015,
    "fuel_type": "בנזין",
    "transmission": "אוטומטית",
    "mileage_range": "100,000 - 150,000 ק\"מ"
  }'
```

### Test Client
Open the deployed client URL and:
1. Click "Analyze" to test reliability analysis
2. Try "Login" to test Google OAuth
3. Check "History" (requires login)
4. Test "ROI Calculator"
5. Test "Get Quote" (leads)

## 🔧 Troubleshooting

### Common Issues

**Server fails to start:**
- Check that all environment variables are set correctly
- Verify Google Sheets sharing with service account
- Check Gemini API key is valid

**Client can't connect to server:**
- Verify `VITE_API_BASE_URL` points to correct server URL
- Check CORS settings in `ALLOWED_ORIGINS`
- Ensure both services are deployed and running

**Authentication fails:**
- Verify OAuth Client ID matches in both client and server
- Check authorized origins in Google Cloud Console
- Ensure token is being sent in Authorization header

**Cache not working:**
- Check Google Sheet has correct headers
- Verify sheet is not empty
- Check `CACHE_MAX_DAYS` setting

**Rate limit issues:**
- Check quota endpoint: `/v1/quota`
- Verify date column in sheet is formatted correctly
- Consider increasing limits in environment variables

## 📝 License

[Your License Here]

## 👥 Contributors

[Your Name/Team]

## 🔗 Links

- [Google Gemini API](https://ai.google.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Railway Documentation](https://docs.railway.app/)
