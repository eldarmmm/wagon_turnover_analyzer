# Railcar Turnover Analyzer

Python desktop application for calculating railcar turnover cycles from operational movement data and exporting formatted Excel reports.

## What this project does

This tool analyzes wagon movement history and builds cycle-based turnover reports, including:

- loading and unloading events
- loaded and empty runs
- completed and incomplete turnover cycles
- double-load scenarios at the same station
- Excel export with formatted output
- batch report generation by date range

The application uses a PyQt desktop interface and a SQL-based data source.

## Tech stack

- Python
- pandas
- pyodbc
- PyQt5
- openpyxl

## Project structure

```
railcar-turnover-analyzer/
├─ app/
│  ├─ styles.py
│  ├─ utils.py
│  ├─ turnover_logic.py
│  ├─ workers.py
│  ├─ widgets.py
│  └─ ui.py
├─ config.example.json
├─ requirements.txt
└─ main.py
```

## Notes about the public version

This public version is sanitized for portfolio purposes:

- connection details were removed
- database object names were replaced with generic placeholders
- internal comments and organization-specific references were removed

To run this project against your own environment, update the SQL queries in `app/workers.py` and `app/ui.py` so they match your schema.

## Installation

```bash
pip install -r requirements.txt
python main.py
```

## Data source expectations

The app expects a SQL Server-style source with tables equivalent to:

- station reference
- distance reference
- cargo reference
- wagon ownership history
- wagon type history
- wagon client group history
- operations / movement history

The exact table names in this repository are placeholders meant to show the architecture of the solution rather than expose a production schema.

## Why I built it

I built this tool to automate a real-world transportation analytics task: turning raw wagon operation history into a structured turnover report that business users can review and export.

The focus of the project is not only code, but also business-rule logic, reporting workflow, and practical usability for operations teams.

## Portfolio context

This project is part of my analytics and automation portfolio. It reflects how I use Python and AI-assisted development to turn operational problems into working internal tools.

## License

MIT
