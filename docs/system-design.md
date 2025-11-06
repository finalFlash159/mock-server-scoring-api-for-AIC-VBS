# System Design - AIC 2025 Scoring Server

## Architecture Overview

```mermaid
graph TB
    Client[Client Team] -->|HTTP POST| API[FastAPI Server]
    API -->|Load Config| Config[current_task.yaml]
    API -->|Load GT| CSV[groundtruth.csv]
    API -->|Normalize| Normalizer[Normalizer]
    Normalizer -->|KIS/QA/TR| Submission[NormalizedSubmission]
    Submission -->|Score| Scorer[Scoring Engine]
    CSV -->|Ground Truth| Scorer
    Config -->|Parameters| Scorer
    Scorer -->|Results| Response[JSON Response]
    Response -->|HTTP 200| Client
    
    style API fill:#4CAF50
    style Scorer fill:#FF9800
    style Response fill:#2196F3
```

## Component Architecture

### 1. FastAPI Server (`app/main.py`)

Main application server with 4 endpoints:

```mermaid
graph LR
    A[FastAPI App] --> B[GET /]
    A --> C[GET /config]
    A --> D[GET /questions]
    A --> E[POST /submit]
    
    B --> F[Health Check]
    C --> G[Current Config]
    D --> H[List Questions]
    E --> I[Score Submission]
```

**Responsibilities:**
- Handle HTTP requests/responses
- CORS middleware for development
- Load groundtruth on startup
- Route requests to appropriate handlers

### 2. Data Models (`app/models.py`)

```mermaid
classDiagram
    class GroundTruth {
        +int stt
        +str type
        +str scene_id
        +str video_id
        +List~int~ points
    }
    
    class NormalizedSubmission {
        +int question_id
        +str qtype
        +str video_id
        +List~int~ values
    }
    
    class Config {
        +int active_question_id
        +float fps
        +float max_score
        +float frame_tolerance
        +float decay_per_frame
        +str aggregation
    }
```

**GroundTruth:**
- Represents one question from CSV
- `points`: Even-length list, each pair = 1 event

**NormalizedSubmission:**
- Unified format after normalization
- `values`: User submitted values (ms or frame_id)

**Config:**
- Scoring parameters
- `aggregation`: "mean" | "min" | "sum"

### 3. Groundtruth Loader (`app/groundtruth_loader.py`)

```mermaid
flowchart TD
    A[Load CSV] --> B{Validate Format}
    B -->|Invalid| C[Raise Error]
    B -->|Valid| D[Parse Points]
    D --> E{Even Count?}
    E -->|No| C
    E -->|Yes| F{Sorted?}
    F -->|No| C
    F -->|Yes| G[Create GroundTruth]
    G --> H[Add to Table]
    H --> I[Return Dict]
```

**Validations:**
- Points count must be even
- Points must be sorted ascending
- All required fields present

### 4. Normalizer (`app/normalizer.py`)

Converts different body formats to unified `NormalizedSubmission`:

```mermaid
flowchart LR
    A[Request Body] --> B{Task Type?}
    B -->|KIS| C[normalize_kis]
    B -->|QA| D[normalize_qa]
    B -->|TR| E[normalize_tr]
    C --> F[NormalizedSubmission]
    D --> F
    E --> F
    F --> G[Scoring Engine]
```

**KIS Format:**
- Multiple `answers` with `mediaItemName`, `start`, `end`
- Each answer = 1 event

**QA Format:**
- Single `text` with pattern: `QA-<ANSWER>-<VIDEO_ID>-<MS1>,<MS2>,...`
- Comma-separated times in one text

**TR Format:**
- Single `text` with pattern: `TR-<VIDEO_ID>-<FRAME_ID1>,<FRAME_ID2>,...`
- Comma-separated frame IDs in one text

### 5. Scoring Engine (`app/scoring.py`)

```mermaid
flowchart TD
    A[Start Scoring] --> B[Parse GT Points to Events]
    B --> C[Loop Each Event]
    C --> D{User Has Value?}
    D -->|No| E[Score = 0]
    D -->|Yes| F{Task Type?}
    F -->|KIS/QA| G[score_event_ms]
    F -->|TR| H[score_event_frame]
    G --> I[Event Score]
    H --> I
    E --> I
    I --> J{More Events?}
    J -->|Yes| C
    J -->|No| K[Aggregate Scores]
    K --> L{Aggregation?}
    L -->|mean| M[Average]
    L -->|min| N[Minimum]
    L -->|sum| O[Sum]
    M --> P[Final Score]
    N --> P
    O --> P
```

**Key Functions:**

- `points_to_events()`: Converts `[p1,p2,p3,p4]` → `[(p1,p2), (p3,p4)]`
- `score_event_ms()`: Score for KIS/QA (milliseconds)
- `score_event_frame()`: Score for TR (frame_id)
- `score_submission()`: Main scoring orchestrator

## Data Flow

### Complete Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI
    participant CFG as Config Loader
    participant GT as GT Loader
    participant N as Normalizer
    participant S as Scorer
    
    C->>API: POST /submit
    API->>CFG: Load config
    CFG-->>API: Config object
    API->>GT: Get question GT
    GT-->>API: GroundTruth object
    API->>N: Normalize body
    N-->>API: NormalizedSubmission
    API->>S: Score submission
    S->>S: Parse events
    S->>S: Score each event
    S->>S: Aggregate scores
    S-->>API: Final score + details
    API-->>C: JSON response
```

### Config Loading Strategy

```mermaid
flowchart LR
    A[Request Arrives] --> B[Load YAML]
    B --> C[Parse Config]
    C --> D[Get active_question_id]
    D --> E[Fetch from GT_TABLE]
    E --> F[Validate Match]
    F --> G[Proceed to Score]
```

**Benefits:**
- No server restart needed
- Dynamic question switching
- Easy testing

## File Structure

```
scoring-server/
├── app/
│   ├── __init__.py           # Package marker
│   ├── main.py               # FastAPI app, endpoints, CORS
│   ├── models.py             # Pydantic data models
│   ├── config.py             # YAML config loader
│   ├── groundtruth_loader.py # CSV parser with validation
│   ├── normalizer.py         # Body format normalizers (KIS/QA/TR)
│   ├── scoring.py            # Core scoring algorithms
│   └── utils.py              # Helper functions
├── config/
│   └── current_task.yaml     # Active question config
├── data/
│   └── groundtruth.csv       # Question groundtruth data
├── tests/
│   ├── __init__.py
│   └── test_scoring.py       # Unit tests
├── docs/
│   ├── system-design.md      # This file
│   └── scoring-logic.md      # Scoring algorithm details
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build
└── README.md                 # Quick start guide
```

## API Endpoints Detail

### GET `/`

**Purpose:** Health check

**Response:**
```json
{
  "status": "ok",
  "message": "AIC 2025 Scoring Server",
  "version": "1.0.0",
  "total_questions": 5
}
```

### GET `/config`

**Purpose:** View current active question configuration

**Response:**
```json
{
  "active_question_id": 1,
  "type": "TR",
  "video_id": "V017",
  "scene_id": "L26",
  "num_events": 2,
  "fps": 25.0,
  "max_score": 100.0,
  "frame_tolerance": 12.0,
  "aggregation": "mean"
}
```

### GET `/questions`

**Purpose:** List all available questions

**Response:**
```json
{
  "questions": [
    {
      "id": 1,
      "type": "TR",
      "video_id": "V017",
      "scene_id": "L26",
      "num_events": 2
    }
  ]
}
```

### POST `/submit`

**Purpose:** Submit answer and get score

**Request:** See README.md for format details

**Response:**
```json
{
  "success": true,
  "question_id": 1,
  "type": "TR",
  "video_id": "V017",
  "score": 23.0,
  "detail": {
    "per_event_scores": [46.0, 0.0],
    "gt_events": [[4890, 5000], [5001, 5020]],
    "user_values": [4999, 5049],
    "aggregation_method": "mean",
    "num_gt_events": 2,
    "num_user_events": 2
  }
}
```

## Error Handling

```mermaid
flowchart TD
    A[Request] --> B{Valid JSON?}
    B -->|No| C[400 Bad Request]
    B -->|Yes| D{Question Exists?}
    D -->|No| E[400 Question Not Found]
    D -->|Yes| F{Valid Format?}
    F -->|No| G[400 Invalid Format]
    F -->|Yes| H{Video Match?}
    H -->|No| I[400 Video Mismatch]
    H -->|Yes| J[Score Submission]
    J --> K{Success?}
    K -->|No| L[500 Internal Error]
    K -->|Yes| M[200 OK]
```

**Error Response Format:**
```json
{
  "detail": "Error message here"
}
```

## Deployment Options

### Local Development
```bash
uvicorn app.main:app --reload
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker
```bash
docker build -t scoring-server .
docker run -p 8000:8000 scoring-server
```

### With Gunicorn
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Performance Considerations

- **CSV Loading:** Done once at startup, cached in memory
- **Config Loading:** Per-request (lightweight YAML parse)
- **Scoring:** O(n) where n = number of events
- **No Database:** All in-memory for speed

## Configuration Options

### `config/current_task.yaml`

```yaml
active_question_id: 1      # Which question is active
fps: 25.0                  # Video FPS for ms→frame conversion
max_score: 100.0           # Maximum score per event
frame_tolerance: 12.0      # Tolerance in frames (±from event boundaries)
decay_per_frame: 1.0       # Score decay rate per frame
aggregation: "mean"        # How to combine event scores: mean/min/sum
```

**Aggregation Strategies:**

- `mean`: Average score across all events (default)
- `min`: Take lowest score (strict, all events must be good)
- `sum`: Sum all scores (rewards multiple correct events)

## Testing Strategy

### Unit Tests (`tests/test_scoring.py`)

- Test `points_to_events()` conversion
- Test scoring functions with various distances
- Test aggregation methods (mean/min/sum)
- Test edge cases (missing events, out of range)

### Integration Testing

Manual testing with curl:
```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d @test_submission.json
```

## Future Enhancements

- Database backend for persistent storage
- User authentication and session management
- Leaderboard functionality
- Detailed analytics and reporting
- WebSocket for real-time updates
- Admin UI for managing questions

---

**Last Updated:** 2025-11-07
