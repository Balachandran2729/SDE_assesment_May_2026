import streamlit as st
import json
import os
import heapq # For priority queue to manage events
from datetime import datetime, timedelta

# --- Constants ---
ROUTE_SEGMENTS = {
    "Bengaluru->A": 100,
    "A->B": 120,
    "B->C": 100,
    "C->D": 120,
    "D->Kochi": 100,
    "Kochi->D": 100,
    "D->C": 120,
    "C->B": 100,
    "B->A": 120,
    "A->Bengaluru": 100,
}

STATIONS = ["A", "B", "C", "D"]
TOTAL_DISTANCE_BK = 540 # km
MAX_RANGE = 240 # km
CHARGING_TIME = 25 # minutes
BUS_SPEED_KMH = 60 # km/h

def get_travel_time_km(distance_km, speed_kmh=BUS_SPEED_KMH):
    """Calculates travel time in minutes for a given distance."""
    return (distance_km / speed_kmh) * 60

def str_to_datetime(time_str, base_date=datetime.now().date()):
    """Converts 'HH:MM' string to a datetime object for today."""
    return datetime.combine(base_date, datetime.strptime(time_str, "%H:%M").time())

def datetime_to_str(dt_obj):
    """Converts datetime object back to 'HH:MM' string."""
    return dt_obj.strftime("%H:%M")


# --- SCHEDULER LOGIC (Revised) ---

def load_scenario(scenario_name):
    """Loads scenario data from the scenarios folder."""
    file_path = os.path.join("scenarios", f"{scenario_name}.json")
    with open(file_path, 'r') as f:
        return json.load(f)

def calculate_schedule(scenario_data):
    """
    Calculates the charging schedule using a Discrete Event Simulation approach.
    Considers weights for conflict resolution.
    """
    buses = scenario_data["buses"]
    weights = scenario_data.get("default_weights", {"individual": 1.0, "operator": 1.0, "overall": 1.0})

    # --- Data Structures for Simulation ---
    # Priority queue for events: (timestamp, event_type, bus_id, ...)
    # event_type: 'depart', 'arrive_at_station', 'finish_charging'
    event_queue = []

    # Track bus state
    bus_states = {}
    for bus_info in buses:
        bus_id = bus_info["id"]
        bus_states[bus_id] = {
            "id": bus_id,
            "operator": bus_info["operator"],
            "direction": bus_info["direction"],
            "departure_time": str_to_datetime(bus_info["departure_time_str"]),
            "plan": [],
            "current_range_left_km": MAX_RANGE,
            "current_location": "Bengaluru" if "Bengaluru" in bus_info["direction"] else "Kochi",
            "current_time": str_to_datetime(bus_info["departure_time_str"]),
            "total_wait_time": 0,
            "arrival_time_at_destination": None,
            "route_segments": [],
            "next_segment_index": 0,
            "charging_at_station": None, # Currently charging at which station
        }

        # Determine the route segments based on direction
        if bus_info["direction"] == "Bengaluru->Kochi":
            route_segments = ["Bengaluru->A", "A->B", "B->C", "C->D", "D->Kochi"]
        else: # Kochi -> Bengaluru
            route_segments = ["Kochi->D", "D->C", "C->B", "B->A", "A->Bengaluru"]

        bus_states[bus_id]["route_segments"] = route_segments

        # Add the initial departure event
        heapq.heappush(event_queue, (bus_states[bus_id]["current_time"], 'depart', bus_id))


    # Track station schedules {station: [(end_time, bus_id), ...]}
    station_schedules = {station: [] for station in STATIONS}

    # --- Simulation Loop ---
    while event_queue:
        current_time, event_type, bus_id = heapq.heappop(event_queue)
        bus = bus_states[bus_id]

        if event_type == 'depart':
            # Bus starts its journey. Schedule the arrival at the first station.
            if bus["next_segment_index"] < len(bus["route_segments"]):
                segment_key = bus["route_segments"][bus["next_segment_index"]]
                distance = ROUTE_SEGMENTS[segment_key]
                next_station = segment_key.split("->")[1]

                travel_duration_mins = get_travel_time_km(distance, BUS_SPEED_KMH)
                arrival_time = bus["current_time"] + timedelta(minutes=travel_duration_mins)

                bus["plan"].append({
                    "type": "travel",
                    "to": next_station,
                    "start_time": datetime_to_str(bus["current_time"]),
                    "end_time": datetime_to_str(arrival_time),
                    "duration_mins": travel_duration_mins
                })

                # Determine if charging is needed at this station
                # Simple heuristic: if remaining range after *this* segment would be less than max_range, charge here.
                # Or, if we've traveled >= 240km since last charge and this is not the destination.
                # We need to track distance since last charge point.
                # Let's refine: Need to ensure we can reach the *next* required charging point or destination.
                # For now, a simpler approach: charge if range would drop below the distance needed to reach the *last* required charging point or destination.

                # A more robust way: Pre-calculate mandatory stops based on range
                # But let's implement a greedy check: if I'm at this station, can I reach the *next* station without charging?
                # No, that's too late. Need to decide *before* leaving the previous station.
                # Let's implement a check: if I don't charge here, can I reach the farthest possible point in my route?
                # We'll use a greedy approach: charge if the remaining range is insufficient to reach the next required point.

                # Determine the remaining route distance from the next station
                remaining_route_distance = sum(ROUTE_SEGMENTS[s] for s in bus["route_segments"][bus["next_segment_index"]:])
                # Check if the remaining distance requires charging *somewhere* in the future segments
                # Greedy: Charge if the range left now is insufficient for the *next* segment *and* there are more segments after that
                # Or, charge if the cumulative distance from the *next* station onwards exceeds the range, necessitating a charge *before* proceeding further.

                # Simpler greedy: Charge if the range left now is less than the distance to the *farthest* point reachable without another charge.
                # Farthest point: From the next station, how far can we go? range - distance_to_next_station.
                # We need to check if the remaining route *after* reaching next_station is feasible with that remaining range.
                distance_to_next = distance
                range_after_reaching_next = bus["current_range_left_km"] - distance_to_next
                remaining_route_after_next = sum(ROUTE_SEGMENTS[s] for s in bus["route_segments"][bus["next_segment_index"]+1:])
                need_to_charge_here = (range_after_reaching_next < remaining_route_after_next) and (remaining_route_after_next > 0)

                # Alternative Greedy: Charge if range left is insufficient for the *next* leg AND it's not the final leg.
                need_to_charge_here_simple = (bus["current_range_left_km"] < distance) and (bus["next_segment_index"] < len(bus["route_segments"]) - 1)

                if need_to_charge_here_simple:
                    # Bus needs to charge at the next station
                    bus["charging_at_station"] = next_station
                    # Schedule arrival event which will trigger charging logic
                    heapq.heappush(event_queue, (arrival_time, 'arrive_at_station', bus_id))
                else:
                    # Bus just travels through
                    bus["current_time"] = arrival_time
                    bus["current_location"] = next_station
                    bus["current_range_left_km"] -= distance
                    bus["next_segment_index"] += 1
                    # If not at destination, schedule arrival at next segment
                    if bus["next_segment_index"] < len(bus["route_segments"]):
                        heapq.heappush(event_queue, (arrival_time, 'depart', bus_id)) # Continue journey
                    else:
                        # Reached destination
                        bus["arrival_time_at_destination"] = datetime_to_str(arrival_time)

        elif event_type == 'arrive_at_station':
             station = bus["charging_at_station"]
             arrival_time = current_time

             # --- HANDLE CHARGING AT STATION (Conflict Resolution Based on Weights) ---
             station_schedule = station_schedules[station]
             # Sort schedule by end time to find gaps - needed for finding the *first* available slot
             station_schedule.sort(key=lambda x: x[0])

             # Find the earliest possible charging start time
             # Option 1: First available slot after arrival time
             charge_start_time = arrival_time
             for end_time, _ in station_schedule:
                 if charge_start_time < end_time:
                     # Station is busy, bus must wait until the slot is free
                     charge_start_time = end_time

             # Option 2: Potentially consider weights here for prioritization
             # E.g., if operator weight is high, maybe prioritize finishing one operator's bus quickly?
             # Or if individual wait is high, try to minimize wait for this specific bus?
             # The simplest interpretation of the weights for *conflict resolution* is to prioritize based on arrival time (FCFS)
             # *unless* we want to implement a more complex priority system based on the weights.
             # Let's stick to FCFS for now, which is fair and simple, and aligns with the basic greedy approach.
             # The weights are primarily for the *decision of which stations to visit*, not necessarily the order *within* a station,
             # although the choice of *when* to visit *can* be influenced by expected waits at stations (which is harder).

             # For the *order within a station*, FCFS at the *actual arrival time* is a standard approach.
             # The weights influence *which* station/bus pairs are scheduled, which indirectly affects arrival times at stations.
             # Our charging logic here is FCFS based on arrival.

             charge_end_time = charge_start_time + timedelta(minutes=CHARGING_TIME)

             # Calculate wait time
             wait_time = (charge_start_time - arrival_time).total_seconds() / 60
             bus["total_wait_time"] += wait_time

             # Update bus plan
             bus["plan"][-1]["wait_time_mins"] = round(wait_time, 2) # Update the last travel event with wait time if applicable
             bus["plan"].append({
                 "type": "charge",
                 "at": station,
                 "start_time": datetime_to_str(charge_start_time),
                 "end_time": datetime_to_str(charge_end_time),
                 "duration_mins": CHARGING_TIME,
                 "wait_time_mins": round(wait_time, 2)
             })

             # Update bus state
             bus["current_time"] = charge_end_time
             bus["current_range_left_km"] = MAX_RANGE # Fully charged
             bus["current_location"] = station
             bus["charging_at_station"] = None # Finished charging
             bus["next_segment_index"] += 1 # Move to the next segment after charging

             # Update station schedule
             station_schedules[station].append((charge_end_time, bus_id))

             # Schedule departure for the next segment
             if bus["next_segment_index"] < len(bus["route_segments"]):
                 heapq.heappush(event_queue, (charge_end_time, 'depart', bus_id))
             else:
                 # Reached destination after charging
                 bus["arrival_time_at_destination"] = datetime_to_str(charge_end_time)

    # Return the calculated plans and station schedules
    return {
        "per_bus_timelines": list(bus_states.values()),
        "per_station_orders": station_schedules
    }


# --- STREAMLIT UI ---
def main():
    st.title("Bus Charging Scheduler")

    # Scenario Selection
    scenario_names = ["scenario_1", "scenario_2", "scenario_3", "scenario_4", "scenario_5"]
    selected_scenario_name = st.selectbox("Select Scenario", options=scenario_names)

    if selected_scenario_name:
        scenario_data = load_scenario(selected_scenario_name)

        st.header(f"Scenario: {scenario_data['name']}")
        st.subheader("Description")
        st.write(scenario_data.get('description', 'N/A'))
        st.subheader("Input Data")
        st.dataframe(scenario_data["buses"]) # Display raw input
        st.subheader("Weights Used")
        st.write(scenario_data.get('default_weights', {}))

        # Run Scheduler Button (Optional, might run automatically)
        # if st.button("Run Scheduler"):
        schedule_result = calculate_schedule(scenario_data)

        st.subheader("Per-Bus Timelines")
        for bus_info in schedule_result["per_bus_timelines"]:
            with st.expander(f"Bus ID: {bus_info['id']} ({bus_info['operator']}) - {bus_info['direction']}"):
                st.write(f"**Departure:** {datetime_to_str(bus_info['departure_time'])}")
                for event in bus_info['plan']:
                     if event['type'] == 'travel':
                         st.write(f"  Travel to {event['to']}: {event['start_time']} - {event['end_time']} ({event['duration_mins']:.2f} mins)")
                     elif event['type'] == 'charge':
                         st.write(f"  Charge at {event['at']}: {event['start_time']} - {event['end_time']} (Wait: {event['wait_time_mins']:.2f} mins)")
                st.write(f"**Arrival:** {bus_info['arrival_time_at_destination']}")

        st.subheader("Per-Station Usage Order")
        for station, schedule_list in schedule_result["per_station_orders"].items():
            st.write(f"**Station {station}:**")
            if schedule_list:
                sorted_schedule = sorted(schedule_list, key=lambda x: x[0]) # Sort by end time, then calc start time
                for end_time, bus_id in sorted_schedule:
                    # Calculate start time from end time and charging duration
                    start_time = end_time - timedelta(minutes=CHARGING_TIME)
                    st.write(f"  - {bus_id}: {datetime_to_str(start_time)} - {datetime_to_str(end_time)}")
            else:
                st.write("  (No buses scheduled to charge)")
            st.write("") # Blank line


if __name__ == "__main__":
    main()
