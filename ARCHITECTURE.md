# Architecture Document: Bus Charging Scheduler

## Chosen Approach

The core of the application is a **Greedy Simulator**. It processes buses sequentially (sorted by departure time initially) and assigns charging stops and times based on immediate availability and mandatory range constraints.

## Data Structure Design

- **Scenario Files (JSON):** Contain raw input data: bus IDs, operators, directions, departure times, and default weights.
- **Internal Bus Representation (Dict):** Each bus is represented as a dictionary within a list (`processed_buses`). It contains `id`, `operator`, `direction`, `departure_time` (datetime), `plan` (list of travel/charge events), `current_range_left_km`, `current_time`, `total_wait_time`, `arrival_time_at_destination`.
- **Internal Station Schedule (Dict of Lists):** `station_schedules` is a dictionary mapping station names (A, B, C, D) to lists of tuples `(end_time_of_charge_slot, bus_id)`. This tracks when each station is occupied.

## Anticipated Changes & Scalability Handling

1.  **More Buses:** The algorithm iterates through a list, so adding more buses scales linearly. The simulation logic remains the same.
2.  **More Stations:** The `STATIONS` list and `ROUTE_SEGMENTS` dictionary can be expanded. The scheduling loop needs to account for the new stations in the route sequence and charging decisions.
3.  **More Operators:** The `operator` field in bus data already supports this. Weight adjustments for fairness would apply to the new operator.
4.  **Variable Charging Times:** The `CHARGING_TIME` constant could be replaced by a dictionary mapping station types or IDs to their respective times. The scheduling logic would use this dynamic time.
5.  **Different Route:** The `ROUTE_SEGMENTS` and `STATIONS` constants would be redefined. The core simulation loop might need adjustments to parse the new route structure.
6.  **Adding a New Optimization Rule:** This requires modifying the core `calculate_schedule` function. The new rule's logic would need to influence the decision of *when* and *where* a bus charges, potentially affecting how station schedules are checked or how the `bus.plan` is updated. The weights structure allows for incorporating the new rule's importance.

## Modifying Weights

Weights are read from the `default_weights` object within each scenario JSON file (e.g., `scenarios/scenario_4.json`). Modifying these values directly affects the scheduler's behavior for that specific scenario run.

Example (in `scenario_1.json`):
```json
"default_weights": {
    "individual": 1.5, // Increased importance on individual wait time
    "operator": 0.5,   // Decreased importance on operator fairness
    "overall": 1.0
}