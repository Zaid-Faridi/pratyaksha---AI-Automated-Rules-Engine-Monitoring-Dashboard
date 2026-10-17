# Pratyaksha (प्रत्यक्ष) - Phase 3: Monitoring Dashboard
> **AI Video-Analytics Surveillance & Compliance Web Application**  
> *MSDE Problem Statement 26245*

The Phase 3 frontend is a responsive, government-grade React dashboard built for national and state-level skilling monitoring units. It visualizes automated attendance auditing, sanctioned infrastructure tracking, camera health telemetry, and compliance alert queues.

---

## Technology Stack

- **Framework**: React 18 + Vite + TypeScript
- **Styling**: Tailwind CSS with custom Government Blue & Teal palette (`gov-50` to `gov-900`) and dark/light mode toggle
- **Routing**: React Router v6
- **Server State & Caching**: TanStack Query (React Query) with 30s auto-refresh
- **Charts**: Recharts (Attendance BarCharts, Compliance AreaCharts, and Alerts-by-Type charts)
- **Geospatial**: Leaflet + React Leaflet with OpenStreetMap tiles and custom compliance-coded pins
- **Icons**: Lucide React
- **HTTP / API**: Native typed Fetch client with automatic Vite proxy (`/api` -> `http://localhost:8000`) and offline mock fallback

---

## Directory Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts             # Typed API client module (fetch + mock fallback)
│   │   └── mockData.ts           # Comprehensive local fixtures for offline demos
│   ├── components/
│   │   ├── common/
│   │   │   ├── KpiCard.tsx       # Reusable KPI metric card with icon & variant colors
│   │   │   ├── SeverityBadge.tsx # LOW, MEDIUM, HIGH, CRITICAL, INFO badges
│   │   │   ├── StatusBadge.tsx   # COMPLIANT, NEEDS_ATTENTION, NON_COMPLIANT badges
│   │   │   ├── ScoreRing.tsx     # Circular SVG compliance score gauge (0–100%)
│   │   │   ├── DataTable.tsx     # Searchable, sortable, paginated table
│   │   │   ├── LoadingSkeleton.tsx # Shimmer skeleton loading state
│   │   │   ├── EmptyState.tsx    # Clean empty state display
│   │   │   └── ErrorState.tsx    # Graceful error state with retry button
│   │   ├── layout/
│   │   │   ├── Header.tsx        # Top navbar with live sync status, theme toggle & privacy link
│   │   │   └── Sidebar.tsx       # Navigation sidebar with open alerts counter
│   │   ├── alerts/
│   │   │   └── AlertPanel.tsx    # Slide-over alert review panel with evidence thumbnail & actions
│   │   └── map/
│   │       └── CentresMap.tsx    # Interactive Leaflet map with compliance-coded pins
│   ├── pages/
│   │   ├── OverviewPage.tsx      # KPI cards, charts, and ranked least compliant centres table
│   │   ├── MapPage.tsx           # Full-screen national map view with state/district/scheme filters
│   │   ├── CentresListPage.tsx   # Searchable, sortable table of all monitored institutes
│   │   ├── CentreDetailPage.tsx  # Centre score breakdown, claimed vs detected chart, and zone equipment
│   │   ├── AlertQueuePage.tsx    # Full alert queue with filters, slide-over review, and optimistic update
│   │   └── PrivacyPage.tsx       # Government DPDP-compliant privacy charter
│   ├── context/
│   │   └── ThemeContext.tsx      # Dark / Light theme context with localStorage sync
│   ├── types/
│   │   └── index.ts              # TypeScript definitions matching backend schemas
│   ├── App.tsx                   # QueryClientProvider, BrowserRouter & Route layout
│   ├── index.css                 # Tailwind directives & custom Leaflet styling
│   ├── main.tsx                  # App DOM mount entrypoint
│   └── vite-env.d.ts             # Vite client environment types
├── package.json
├── vite.config.ts                # Vite config with /api proxy to http://localhost:8000
├── tailwind.config.js            # Tailwind configuration
├── tsconfig.json                 # TypeScript compiler configuration
├── .env                          # VITE_API_BASE_URL=/api & VITE_USE_MOCK=false
└── README.md
```

---

## Setup & Running the Application

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Running Frontend and Backend Together

**Terminal 1 (Backend):**
```bash
cd backend
source ../.venv/bin/activate
# Optional: re-seed fresh sample data
python scripts/seed.py
# Start FastAPI backend server on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. The Vite development proxy will route all `/api/*` calls to `http://localhost:8000/*`.

---

## Offline Mock Mode (Demoing without Backend)

If you need to demonstrate the web application offline without running the FastAPI server or Python environment:

1. Open `frontend/.env`
2. Set `VITE_USE_MOCK=true`
3. Run `npm run dev`

The application will serve rich local JSON fixtures (`src/api/mockData.ts`) covering all 5 state centres, alerts, attendance comparisons, and compliance breakdowns.

---

## Application Pages & Capabilities

1. **Overview Dashboard (`/`)**:
   - 5 KPI metric cards: Total Centres, Average Compliance, Open Alerts, Attendance Mismatches Today, and Offline Cameras.
   - Bar chart of active violations grouped by violation type.
   - Area chart showing the 7-day weighted compliance score trend.
   - Ranked table of the least compliant centres requiring immediate audit.

2. **National Map View (`/map`)**:
   - Interactive Leaflet OpenStreetMap view of India.
   - Custom SVG pin markers colored dynamically by compliance:
     - 🟢 **Green** ($\ge 85\%$): Compliant
     - 🟡 **Amber** ($65-84\%$): Needs Attention
     - 🔴 **Red** ($< 65\%$): Severe Non-Compliance
   - Popups showing instant score, open alert count, and direct link to audit.
   - Filters by State, District, Scheme (PMKVY 4.0, DDU-GKY, STRIVE, etc.), and Status.

3. **Centres Directory (`/centres`)**:
   - Searchable, sortable table across name, location, and scheme.
   - Real-time circular score rings, camera online/offline statuses, and heartbeat timestamps.
   - Filter pills for quick status toggling.

4. **Centre Detail Audit (`/centres/:id`)**:
   - Comprehensive header showing score and weighted components (Attendance 45%, Infrastructure 35%, Camera 20%).
   - Recharts BarChart comparing claimed vs detected attendance per batch/day with mismatch warning indicators.
   - Zone-by-zone sanctioned equipment inventory table (`MATCH`, `DEFICIT`, `SURPLUS`).
   - Camera feeds panel with live status, RTSP addresses, and zone assignments.
   - Incident alert log with one-click review panel trigger.

5. **Alert Review Queue (`/alerts`)**:
   - Multi-dimensional filtering by Centre, Violation Type, Severity, and Resolution Status.
   - Slide-over detail panel with discrepancy explanation, timeline, and privacy-anonymized thumbnail.
   - **Verify** and **Dismiss** actions with reviewer name and audit memo input, wired to `PATCH /alerts/{id}` with optimistic UI updates and toast feedback.

6. **Privacy Charter (`/privacy`)**:
   - Public-facing statement confirming zero facial identification, aggregated headcount only, edge-side Gaussian blurring, and 90-day automated data retention.

---

## Backend Changes Made for Phase 3

To support optimal dashboard UX without modifying core business rules, the following non-breaking enhancements were made to the backend:

1. **`GET /dashboard/summary` additions**:
   - Added `average_compliance_score` (computed across all centres).
   - Added `attendance_mismatches_today` (open attendance shortfall alerts).
   - Added `compliance_trend` (7-day daily compliance index points).
   - Expanded `top_non_compliant_centres` to return up to 10 centres.

2. **`GET /centres/{id}/attendance-history` (New Helper Endpoint)**:
   - Returns claimed attendance records paired with observed detection counts per batch and date to power the Recharts verification chart.

3. **`GET /centres/{id}/infrastructure-status` (New Helper Endpoint)**:
   - Returns zone-by-zone detected vs expected equipment inventory (`MATCH`, `DEFICIT`, `SURPLUS`) for the centre detail table.

4. **Pydantic Schemas Updated**:
   - Modernized schema definitions with `ConfigDict(from_attributes=True)` and defined `CentreAttendanceHistory` and `ZoneInfrastructureStatus` response models.
