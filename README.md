# AIC 2025 - Scoring Server (Competition Mode)

Mock scoring server for AIC 2025 supporting 3 task types: **KIS**, **QA**, **TR** with **server-controlled timing**, **penalty system**, and **exact match scoring**.

## Table of Contents

- [Setup and Run](#setup-and-run)
- [Competition Mode Overview](#competition-mode-overview)
- [Groundtruth CSV Format](#groundtruth-csv-format)
- [Admin Controls](#admin-controls)
- [API Request Format](#api-request-format)
- [Scoring System](#scoring-system)
- [Expose API](#expose-api-to-team)
- [Detailed Documentation](docs/)

## Setup and Run

### 1. Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Start Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server runs at: `http://localhost:8000`

### 3. Test

```bash
# Health check
curl http://localhost:8000/

# View current config
curl http://localhost:8000/config
```

## Competition Mode Overview

**Server-Controlled Timing:** Admin starts questions, teams submit within time limits.

**Key Features:**
- ⏱️ **Time-based scoring:** Earlier submissions get higher scores
- 🚫 **Penalty system:** Wrong submissions reduce final score
- ✅ **Exact match:** No tolerance, must match groundtruth exactly
- 🏆 **Leaderboard:** Real-time rankings by score and time
- 🔒 **One completion per team:** Can't submit after correct answer

**Workflow:**
1. Admin starts question with timer
2. Teams submit answers (tracked by `team_id`)
3. System calculates score based on time and penalties
4. Leaderboard updates automatically
5. Admin stops question when time expires

## Groundtruth CSV Format

File `data/groundtruth.csv`:

```csv
id,type,scene_id,video_id,points
1,TR,L26,V017,"4890-5000-5001-5020"
2,KIS,L26,V017,"4890-5000-5001-5020"
3,QA,K01,V021,"12000-12345"
```

**Rules:**
- `points`: Dash-separated integers (`-`), **count must be even**
- Each pair of numbers = 1 event: `[start, end]`
- KIS/QA: points = milliseconds (ms)
- TR: points = frame_id
- Points must be sorted in **ascending order**

**Example:**
- `4890-5000-5001-5020` → 2 events: [4890,5000] and [5001,5020]

## Admin Controls

Admin endpoints control question timing and sessions.

### Start Question

```bash
curl -X POST http://localhost:8000/admin/start-question \
  -H "Content-Type: application/json" \
  -d '{
    "question_id": 1,
    "time_limit": 300,
    "buffer_time": 10
  }'
```

**Response:**
```json
{
  "success": true,
  "question_id": 1,
  "start_time": 1762492824.777456,
  "time_limit": 300,
  "buffer_time": 10,
  "message": "Question 1 started. Teams can now submit."
}
```

### Stop Question

```bash
curl -X POST http://localhost:8000/admin/stop-question \
  -H "Content-Type: application/json" \
  -d '{"question_id": 1}'
```

### Reset All Sessions (Testing Only)

```bash
curl -X POST http://localhost:8000/admin/reset-all
```

### List Active Sessions

```bash
curl http://localhost:8000/admin/sessions
```

### Check Question Status

```bash
curl http://localhost:8000/question/1/status
```

**Response:**
```json
{
  "question_id": 1,
  "is_active": true,
  "elapsed_time": 29.36,
  "remaining_time": 270.64,
  "time_limit": 300,
  "buffer_time": 10,
  "total_teams_submitted": 2,
  "completed_teams": 2
}
```

### View Leaderboard

```bash
curl http://localhost:8000/leaderboard?question_id=1
```

**Response:**
```json
{
  "question_id": 1,
  "total_ranked": 2,
  "rankings": [
    {
      "rank": 1,
      "team_id": "team_02",
      "score": 95.5,
      "submit_time": 5.23,
      "wrong_attempts": 0
    },
    {
      "rank": 2,
      "team_id": "team_01",
      "score": 85.5,
      "submit_time": 12.45,
      "wrong_attempts": 1
    }
  ]
}
```

## API Request Format

**All submissions require `team_id`** for tracking. Question timing is controlled by admin.

### KIS (Known-Item Search)

Each event = separate answer. Must match **ALL** groundtruth events exactly (100% or 0 score).

```json
{
  "team_id": "team_01",
  "question_id": 1,
  "answerSets": [{
    "answers": [
      {
        "mediaItemName": "V017",
        "start": "4945",
        "end": "4945"
      },
      {
        "mediaItemName": "V017",
        "start": "5010",
        "end": "5010"
      }
    ]
  }]
}
```

### QA (Query Answer)

All times in **one text**, comma-separated. Must match **ALL** groundtruth events exactly (100% or 0 score).

```json
{
  "team_id": "team_01",
  "question_id": 3,
  "answerSets": [{
    "answers": [
      { "text": "QA-MyAnswer-V021-12000,12345" }
    ]
  }]
}
```

**Format:** `QA-<ANSWER>-<VIDEO_ID>-<MS1>,<MS2>,...`

### TR (Temporal Retrieval / TRAKE)

All frame IDs in **one text**, comma-separated. Supports **partial scoring**:
- **100% match:** Full score (correctness = 1.0)
- **50-99% match:** Half score (correctness = 0.5)
- **<50% match:** Zero score (correctness = 0.0)

```json
{
  "team_id": "team_01",
  "question_id": 1,
  "answerSets": [{
    "answers": [
      { "text": "TR-V017-4890,5000,5001,5020" }
    ]
  }]
}
```

**Format:** `TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,...`

### Submit via API

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "your_team_id",
    "question_id": 1,
    "answerSets": [...]
  }'
```

**Success Response (Correct):**
```json
{
  "success": true,
  "correctness": "full",
  "score": 85.5,
  "detail": {
    "matched_events": 2,
    "total_events": 2,
    "wrong_attempts": 1,
    "elapsed_time": 12.45,
    "time_factor": 0.9585
  }
}
```

**Failure Response (Incorrect):**
```json
{
  "success": false,
  "correctness": "incorrect",
  "score": 0,
  "detail": {
    "matched_events": 1,
    "total_events": 2,
    "wrong_attempts": 2,
    "message": "Wrong answer. Try again with penalty."
  }
}
```

**Already Completed:**
```json
{
  "success": false,
  "error": "already_completed",
  "detail": {
    "score": 95.5,
    "completed_at": 5.23
  },
  "message": "You already completed this question with score 95.5"
}
```

## Scoring System

### Formula

```
Score = max(0, P_base + (P_max - P_base) × fT(t) - k × P_penalty) × correctness_factor
```

Where:
- **fT(t)** = Time factor = `1 - (t_submit / T_task)`
- **P_max** = Maximum score = 100
- **P_base** = Base score = 50
- **P_penalty** = Penalty per wrong submission = 10
- **k** = Number of wrong submissions before correct answer
- **T_task** = Time limit (default 300s)
- **t_submit** = Time elapsed when submitting correct answer

### Correctness Factor

**KIS / QA:**
- 100% match: `correctness_factor = 1.0`
- <100% match: `correctness_factor = 0.0`

**TR (TRAKE):**
- 100% match: `correctness_factor = 1.0`
- 50-99% match: `correctness_factor = 0.5`
- <50% match: `correctness_factor = 0.0`

### Example Calculation

**Scenario:** Team submits correct answer after 30s with 1 wrong attempt

```
fT(30) = 1 - (30 / 300) = 0.9
Score = max(0, 50 + (100 - 50) × 0.9 - 1 × 10) × 1.0
      = max(0, 50 + 45 - 10) × 1.0
      = 85.0
```

### Leaderboard Ranking

Teams are ranked by:
1. **Score** (descending)
2. **Time** (ascending) - for tiebreakers

## Expose API to Team

### Within LAN

```bash
# Get your machine's IP
ipconfig getifaddr en0  # macOS
# ifconfig              # Linux
# ipconfig              # Windows

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Team members access: `http://<YOUR_IP>:8000/submit`

### Docker

```bash
docker build -t scoring-server .
docker run -p 8000:8000 scoring-server
```

### Production with Nginx

```nginx
server {
    listen 80;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Documentation

Detailed documentation about system design, scoring logic, and architecture:

- **[System Design](docs/system-design.md)** - Architecture, components, data flow
- **[Scoring Logic](docs/scoring-logic.md)** - Detailed scoring algorithm

## Testing

```bash
pytest tests/test_scoring.py -v
```

