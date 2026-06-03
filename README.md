# Railcar Turnover Analyzer

> Python desktop application that calculates railcar turnover cycles from raw wagon movement data and generates structured Excel reports for operations teams.

---

## Background

In rail freight operations, **turnover** is the full cycle a wagon completes:

```
Arrival at loading station → Loaded run → Unloading → Empty run → Next loading
```

Calculating this from raw movement logs is non-trivial:
- The same physical station can appear under multiple codes in the system
- Wagons change ownership and type over time — historical accuracy matters
- Some cycles never complete within the reporting period
- Edge cases like double-loads (wagon reloaded at the same station without an empty run) break naive approaches

This tool was built to replace a manual Excel-based process and handle edge cases that generic reporting tools couldn't address.

---

## Features

- **Cycle detection** — identifies completed and incomplete turnover cycles from sequential wagon operation records
- **Double-load handling** — detects scenarios where a wagon is reloaded at the same station without an empty run
- **Station normalization** — resolves station identity across multiple station codes using a CodeGroup layer
- **Historical passport lookup** — fetches wagon ownership and type as they were at the time of departure, not the current snapshot
- **Time breakdown** — calculates loading idle time, loaded run, unloading idle time, and empty run duration separately
- **Valid station filtering** — checks loading stations against an allowed list per wagon type and reporting date
- **Formatted Excel export** — alternating row styling, frozen headers, auto column widths
- **Batch mode** — generates one report per day across a date range automatically

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Data processing | pandas |
| Database connection | pyodbc (SQL Server) |
| Desktop UI | PyQt5 |
| Excel export | openpyxl |

---

## Project Structure

```
railcar-turnover-analyzer/
├─ app/
│  ├─ turnover_logic.py   # core cycle detection algorithm
│  ├─ workers.py          # background threads, SQL loading, Excel export
│  ├─ ui.py               # main window and controls
│  ├─ widgets.py          # reusable UI components
│  ├─ utils.py            # helper functions
│  └─ styles.py           # UI styling
├─ config.example.json    # connection config template
├─ requirements.txt
└─ main.py
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/railcar-turnover-analyzer.git
cd railcar-turnover-analyzer
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure the connection

Copy the example config and fill in your SQL Server connection details:

```bash
cp config.example.json config.json
```

```json
{
  "server": "your_server",
  "database": "your_database",
  "trusted_connection": true
}
```

### 4. Run the application

```bash
python main.py
```

---

## Data Source

The app connects to a **SQL Server** database and expects tables equivalent to:

| Table | Purpose |
|---|---|
| Station reference | Station codes, names, and CodeGroup mappings |
| Distance matrix | Distances between station pairs by ID |
| Cargo reference | Cargo codes and names |
| Wagon ownership history | Owner, manager, wagon type — with effective dates |
| Client group history | Client group assignments per wagon with date ranges |
| Operations / movement log | Raw wagon movement records (IsFull flag, station, date, cargo, weight) |

> **Note:** Table and column names in this repository are placeholders. Update the SQL queries in `app/workers.py` to match your schema.

---

## How It Works

The core algorithm in `turnover_logic.py` processes each wagon's movement history chronologically and detects turnover cycles using IsFull flags and station sequences:

```
IsFull = 1  →  wagon is loaded (in transit or at station with cargo)
IsFull = 0  →  wagon is empty
```

**Scenario I — Standard cycle:**
```
Loading station (idle) → Loaded run → Unloading station (idle) → Empty run → Next loading
```

**Scenario II — Double-load:**
```
Loading → Unloading → New loading at the same station (cargo/weight change)
```

**Incomplete cycle:** wagon is empty at the end of the period with no subsequent loading found.

**Period tail:** wagon starts the period already in a loaded state — the algorithm skips to the next complete cycle start.

---

## Notes on the Public Version

This repository is sanitized for portfolio purposes:

- Database connection details have been removed
- Production table and column names have been replaced with generic placeholders
- Organization-specific references and internal comments have been removed

To use this against your own environment, update the SQL queries in `app/workers.py` and `app/ui.py` to match your schema.

---

## License

[MIT](LICENSE)

---

*Built to automate a real operational analytics task in rail freight logistics.*
