# Taekwondo Competition Manager

A lightweight, web-based tournament management system built with Python (Flask) and HTMX. Designed to handle Taekwondo competitions, including bracket generation, ring management, and live scoring.

## Features

- **Division Management**: Create and manage competition divisions (e.g., Weight class, Belt rank).
- **Competitor Management**: Add competitors to specific divisions.
- **Automatic Bracket Generation**: Generates single-elimination brackets, automatically handling byes for uneven numbers of competitors.
- **Ring Management**: Create and monitor multiple competition rings.
- **Match Scheduling**: Assign matches to specific rings and order them.
- **Live Scorekeeping**: Dedicated interface for scorekeepers to record results and advance winners through the bracket automatically.
- **Public Display**: Live view of upcoming matches and ring status.

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy
- **Database**: SQLite (Auto-generated)
- **Frontend**: HTML, HTMX (for dynamic interactions)

## Prerequisites

- Python 3.13
- uv (installation instructions [here](https://docs.astral.sh/uv/getting-started/installation/))
- A [Supabase](https://supabase.com) project for authentication

## Installation

1. Clone the repository.
2. Install the required dependencies:
   ```bash
   uv sync
   ```
3. Create a `.env` file with the required environment variables:
   ```
   # PostgreSQL database connection
   user=<db_user>
   password=<db_password>
   host=<db_host>
   port=<db_port>
   dbname=<db_name>

   # Supabase authentication
   SUPABASE_URL=https://<your-project>.supabase.co
   SUPABASE_KEY=<your-supabase-anon-key>

   # Flask session secret key (generate a strong random value)
   SECRET_KEY=<your-secret-key>
   ```

## Running the Application

1. Run the application:
   ```bash
   uv run flask run
   ```
   >*Notes:*
   >
   >*On the first run, this will automatically create the `tournament.db` SQLite database.*
   >
   >*You can specify a different port with `--port <port_number>`.*
   >*Be sure to update the URLs below accordingly.*

## URLs

2. Open your browser and navigate to:
   - **Public Home**: `http://localhost:5000/`
   - **Admin Dashboard**: `http://localhost:5000/admin`

## Usage Guide

### 1. Setup
- Navigate to the **Admin Dashboard**.
- **Create Rings**: Add the rings available for the tournament (e.g., "Ring 1", "Ring 2").
- **Create Divisions**: Define the categories for competition.

### 2. Manage Competitors & Brackets
- Click "Manage" on a Division.
- Add competitors by name (supports bulk add via newlines).
- Click **Generate Bracket**. This will create the match tree based on the number of competitors.
- Click **Manage & Schedule Bracket** to view the tree.

### 3. Scheduling
- In the Bracket Manager, you can assign specific matches to a Ring and give them a sequence number (e.g., Match 101).

### 4. Running the Tournament
- **Scorekeepers**: Navigate to `/ring/<ring_id>/scorekeeper`. They will see a list of scheduled matches for their ring.
- **Recording Results**: Scorekeepers select the winner. The system automatically updates the bracket, moving the winner to the next round.

## Project Structure

- `app.py`: Main application logic, database models, and routes.
- `templates/`: Contains HTML templates (e.g., `index.html`, `admin.html`, `bracket_view.html`).
- `scripts/`: Management utilities and migrations.

## Management Scripts

Run scripts from the repository root:

```bash
uv run scripts/init_db.py
uv run scripts/reset_db.py
uv run scripts/test_db.py
uv run scripts/update_secrets.py --env dev
```

## Database Models

- **Ring**: Physical location for matches.
- **Division**: Category of competition.
- **Competitor**: Athlete information.
- **Match**: Links competitors, tracks winners, and maintains the bracket tree structure (`next_match_id`).

---

## REST API — `/api/v1`

The `/api/v1` prefix provides a stable, versioned JSON REST API for all tournament data.
All endpoints require Bearer-token authentication.

### Authentication

Every `/api/v1` request must include an `Authorization` header with a valid API token:

```
Authorization: Bearer <your-api-token>
```

Tokens are created and revoked via the **Admin → API Tokens** page
(`/admin/api-tokens`).  Each token is shown **only once** at creation time;
store it securely.

```bash
# Example: obtain token via the admin UI, then export it
export TKD_TOKEN="<paste-your-token-here>"
BASE="http://localhost:5000"
```

Requests with a missing or invalid token receive:

```json
HTTP/1.1 401 Unauthorized
{
  "data": null,
  "error": { "code": "UNAUTHORIZED", "message": "Invalid or revoked token.", "details": {} }
}
```

### Response Envelope

Every response is wrapped in a consistent JSON envelope:

**Success**
```json
{ "data": <payload>, "error": null }
```

**Error**
```json
{
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Human-readable description.",
    "details": { "field": "name" }
  }
}
```

`error.details` always contains at least `{}`.  When the error is field-specific
it includes a `"field"` key identifying the offending input field, plus any
additional actionable context (e.g., `"valid_values"`, `"valid_winner_ids"`).

### Status Codes

| Code | Meaning |
|------|---------|
| 200  | OK — read or update succeeded |
| 201  | Created — new resource created |
| 400  | Bad Request — invalid input; see `error.details` |
| 401  | Unauthorized — missing or invalid Bearer token |
| 404  | Not Found — resource does not exist |
| 409  | Conflict |
| 415  | Unsupported Media Type — POST/PUT/PATCH body must be `application/json` |
| 422  | Unprocessable Entity |
| 500  | Internal Server Error |

### Content-Type

POST, PUT, and PATCH requests that include a body **must** send
`Content-Type: application/json`.  Body-less POSTs (e.g., `generate_bracket`)
are accepted without a Content-Type header.

---

### Rings

#### `GET /api/v1/rings`

List all rings.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/rings
```

```json
{ "data": [{ "id": 1, "name": "Ring 1" }], "error": null }
```

#### `POST /api/v1/rings`

Create a ring.

| Field  | Type   | Required | Description |
|--------|--------|----------|-------------|
| `name` | string | ✓        | Ring name   |

```bash
curl -X POST $BASE/api/v1/rings \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ring 1"}'
```

```json
HTTP/1.1 201 Created
{ "data": { "id": 1, "name": "Ring 1" }, "error": null }
```

#### `GET /api/v1/rings/<id>`

Fetch a single ring.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/rings/1
```

#### `PATCH /api/v1/rings/<id>`

Update a ring's name.

```bash
curl -X PATCH $BASE/api/v1/rings/1 \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ring A"}'
```

#### `DELETE /api/v1/rings/<id>`

Delete a ring.

```bash
curl -X DELETE -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/rings/1
```

```json
{ "data": { "id": 1, "deleted": true }, "error": null }
```

---

### Divisions

#### `GET /api/v1/divisions`

List all divisions.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/divisions
```

```json
{ "data": [{ "id": 1, "name": "Male Under 80kg", "event_type": "kyorugi" }], "error": null }
```

#### `POST /api/v1/divisions`

Create a division.

| Field        | Type   | Required | Description                           |
|--------------|--------|----------|---------------------------------------|
| `name`       | string | ✓        | Division name                         |
| `event_type` | string |          | `"kyorugi"` (default) or `"poomsae"` |

```bash
curl -X POST $BASE/api/v1/divisions \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Male Under 80kg", "event_type": "kyorugi"}'
```

```json
HTTP/1.1 201 Created
{ "data": { "id": 1, "name": "Male Under 80kg", "event_type": "kyorugi" }, "error": null }
```

Validation error example (invalid `event_type`):

```json
HTTP/1.1 400 Bad Request
{
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Invalid event type.",
    "details": { "field": "event_type", "valid_values": ["kyorugi", "poomsae"] }
  }
}
```

#### `GET /api/v1/divisions/<id>`

Fetch a single division.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/divisions/1
```

#### `PUT /api/v1/divisions/<id>` · `PATCH /api/v1/divisions/<id>`

Rename a division.

```bash
curl -X PATCH $BASE/api/v1/divisions/1 \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Female Under 57kg"}'
```

#### `DELETE /api/v1/divisions/<id>`

Delete a division and all its competitors and matches.

```bash
curl -X DELETE -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/divisions/1
```

---

### Competitors

#### `GET /api/v1/competitors[?division_id=<id>]`

List all competitors, optionally filtered by division.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" "$BASE/api/v1/competitors?division_id=1"
```

#### `POST /api/v1/competitors`

Add a competitor to a division.

| Field         | Type    | Required | Description                       |
|---------------|---------|----------|-----------------------------------|
| `name`        | string  | ✓        | Competitor name                   |
| `division_id` | integer | ✓        | ID of the division                |
| `position`    | integer |          | Seed/roster order (default: null) |

```bash
curl -X POST $BASE/api/v1/competitors \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Smith", "division_id": 1}'
```

```json
HTTP/1.1 201 Created
{ "data": { "id": 1, "name": "Alice Smith", "division_id": 1, "position": null }, "error": null }
```

#### `GET /api/v1/competitors/<id>`

Fetch a single competitor.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/competitors/1
```

#### `PATCH /api/v1/competitors/<id>`

Update a competitor's name, division, or position.

```bash
curl -X PATCH $BASE/api/v1/competitors/1 \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Johnson", "position": 2}'
```

#### `DELETE /api/v1/competitors/<id>`

Remove a competitor.

```bash
curl -X DELETE -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/competitors/1
```

---

### Bracket

#### `POST /api/v1/divisions/<id>/generate_bracket`

Generate (or regenerate) a single-elimination bracket for a division.  At least
2 competitors must exist.  The request body is optional.

```bash
curl -X POST -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/divisions/1/generate_bracket
```

```json
HTTP/1.1 201 Created
{ "data": { "division_id": 1, "competitors": 4, "matches_created": 3 }, "error": null }
```

Error when fewer than 2 competitors exist:

```json
HTTP/1.1 400 Bad Request
{
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "At least 2 competitors are required to generate a bracket.",
    "details": {}
  }
}
```

#### `GET /api/v1/divisions/<id>/bracket`

Retrieve all matches in the bracket for a division.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/divisions/1/bracket
```

```json
{
  "data": [
    {
      "match_id": 1, "round_name": "Semi-Final", "status": "Pending",
      "ring_id": null, "next_match_id": 3,
      "competitor1": { "id": 1, "name": "Alice Smith" },
      "competitor2": { "id": 2, "name": "Bob Jones" },
      "winner_id": null
    }
  ],
  "error": null
}
```

---

### Matches

#### `GET /api/v1/matches[?division_id=<id>]`

List matches, optionally filtered by division.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" "$BASE/api/v1/matches?division_id=1"
```

#### `POST /api/v1/matches`

Create a match manually.

| Field           | Type    | Required | Description                              |
|-----------------|---------|----------|------------------------------------------|
| `division_id`   | integer | ✓        | Division this match belongs to           |
| `ring_id`       | integer |          | Ring the match is assigned to            |
| `competitor1_id`| integer |          | First competitor                         |
| `competitor2_id`| integer |          | Second competitor                        |
| `next_match_id` | integer |          | ID of the next bracket match             |
| `round_name`    | string  |          | e.g., `"Semi-Final"`, `"Final"`          |
| `match_number`  | integer |          | Scheduling number (e.g., `101`)          |

```bash
curl -X POST $BASE/api/v1/matches \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"division_id": 1, "round_name": "Final"}'
```

#### `GET /api/v1/matches/<id>`

Fetch a single match.

```bash
curl -H "Authorization: Bearer $TKD_TOKEN" $BASE/api/v1/matches/1
```

#### `PATCH /api/v1/matches/<id>`

Update non-terminal match fields.  To complete a match use the `/result` endpoint.

Allowed `status` values via PATCH: `Pending`, `In Progress`.
Terminal statuses (`Completed`, `Disqualification`, `Completed (Bye)`) must be
set via `POST /api/v1/matches/<id>/result`.

```bash
curl -X PATCH $BASE/api/v1/matches/1 \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ring_id": 2, "status": "In Progress"}'
```

Validation error when setting a terminal status via PATCH:

```json
HTTP/1.1 400 Bad Request
{
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Cannot set a terminal status via PATCH. Use the /matches/<id>/result endpoint to complete a match.",
    "details": { "field": "status", "allowed_statuses": ["In Progress", "Pending"] }
  }
}
```

#### `POST /api/v1/matches/<id>/result`

Record the outcome of a match and automatically advance the winner to the next
bracket match.

| Field       | Type    | Required | Description                                    |
|-------------|---------|----------|------------------------------------------------|
| `status`    | string  | ✓        | `"Completed"` or `"Disqualification"`          |
| `winner_id` | integer | ✓        | Competitor ID of the winner (must be a participant) |

```bash
curl -X POST $BASE/api/v1/matches/1/result \
  -H "Authorization: Bearer $TKD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "Completed", "winner_id": 42}'
```

```json
{ "data": { "match_id": 1, "status": "Completed", "winner_id": 42 }, "error": null }
```

Validation error when `winner_id` is not a participant:

```json
HTTP/1.1 400 Bad Request
{
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "winner_id must be a participant in this match.",
    "details": { "field": "winner_id", "valid_winner_ids": [42, 43] }
  }
}
```

---

### Legacy Endpoints (Deprecated)

The following routes pre-date the `/api/v1` API.  They remain functional but
are **deprecated** and will be removed in a future release once all clients
have migrated.  Every response from these routes includes:

```
Deprecation: true
Link: </api/v1>; rel="successor-version"
```

| Legacy endpoint | Replacement |
|---|---|
| `GET /rings` | `GET /api/v1/rings` |
| `POST /rings` | `POST /api/v1/rings` |
| `GET /divisions` | `GET /api/v1/divisions` |
| `POST /divisions` | `POST /api/v1/divisions` |
| `PUT /divisions/<id>` | `PATCH /api/v1/divisions/<id>` |
| `DELETE /divisions/<id>` | `DELETE /api/v1/divisions/<id>` |
| `POST /matches/<id>/result` | `POST /api/v1/matches/<id>/result` |
| `POST /divisions/<id>/generate_bracket` | `POST /api/v1/divisions/<id>/generate_bracket` |
| `GET /divisions/<id>/bracket` | `GET /api/v1/divisions/<id>/bracket` |
| `GET /divisions/<id>/bracket_ui` | `GET /ui/divisions/<id>/bracket` (HTMX fragment) |
| `PUT /matches/<id>/schedule` | `PATCH /api/v1/matches/<id>` |