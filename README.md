# AIC 2025 - Scoring Server

Mock scoring server for AIC 2025 supporting 3 task types: **KIS**, **QA**, **TR** with multiple events per question.

## Table of Contents

- [Setup and Run](#setup-and-run)
- [Groundtruth CSV Format](#groundtruth-csv-format)
- [Switching Questions](#switching-questions)
- [API Request Format](#api-request-format)
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

## Groundtruth CSV Format

File `data/groundtruth.csv`:

```csv
id,type,scene_id,video_id,points
1,TR,L26,V017,"4890,5000,5001,5020"
2,KIS,L26,V017,"4890,5000,5001,5020"
3,QA,K01,V021,"12000,12345"
```

**Rules:**
- `points`: Comma-separated integers, **count must be even**
- Each pair of numbers = 1 event: `[start, end]`
- KIS/QA: points = milliseconds (ms)
- TR: points = frame_id
- Points must be sorted in **ascending order**

**Example:**
- `4890,5000,5001,5020` → 2 events: [4890,5000] and [5001,5020]

## Switching Questions

Edit `config/current_task.yaml`:

```yaml
active_question_id: 2  # Switch to question 2
```

Server automatically loads new config for each request, no restart needed.

## API Request Format

### KIS (Known-Item Search)

Each event = separate answer

```json
{
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

All times in **one text**, comma-separated

```json
{
  "answerSets": [{
    "answers": [
      { "text": "QA-MyAnswer-V021-12172,12500" }
    ]
  }]
}
```

**Format:** `QA-<ANSWER>-<VIDEO_ID>-<MS1>,<MS2>,...`

### TR (Temporal Retrieval)

All frame IDs in **one text**, comma-separated

```json
{
  "answerSets": [{
    "answers": [
      { "text": "TR-V017-4945,5010" }
    ]
  }]
}
```

**Format:** `TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,...`

### Submit via API

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d @your_submission.json
```

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

