# Bus Charging Scheduler

This application schedules charging times for electric buses on a fixed route, optimizing for individual wait times, operator fleet smoothness, and overall network time.

## Prerequisites

- Python 3.8+
- pip (Python package installer)

## Setup and Running

1.  Clone this repository.
2.  Navigate to the project directory in your terminal.
3.  Install dependencies: `pip install streamlit`
4.  Run the application: `streamlit run app.py`
5.  The application will open in your default web browser.

## Changing Weights (Conceptual)

The optimization weights (`individual`, `operator`, `overall`) are loaded from the scenario JSON files (e.g., `scenarios/scenario_4.json`). To adjust them, modify the `default_weights` object within the desired scenario file. The scheduler reads these values dynamically.

## Adding a New Rule (Conceptual)

To add a new rule, you would need to modify the `calculate_schedule` function in `app.py`. Specifically, you would need to integrate the new rule's logic into the decision-making process for charging stops and scheduling at stations, potentially adjusting how `station_schedules` are managed or how `bus.plan` is constructed based on the new optimization criteria.