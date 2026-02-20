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

## Installation

1. Clone the repository.
2. Install the required dependencies:
   ```bash
   uv sync
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

## Database Models

- **Ring**: Physical location for matches.
- **Division**: Category of competition.
- **Competitor**: Athlete information.
- **Match**: Links competitors, tracks winners, and maintains the bracket tree structure (`next_match_id`).