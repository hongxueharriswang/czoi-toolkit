"""
self_driving_fleet.py — Ride-hailing fleet simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: City → Downtown / Suburb / Airport / Charging.
  * Applications and atomic operations (request, accept, navigate, charge).
  * Real CZOI permission calculus (Φ) on every action.
  * UniLog access constraint: passengers can request but not accept.
  * Hierarchical daemons (Δ): FleetDaemon at root with BatteryDaemon,
    IdleShortageDaemon, and PassengerDaemon as children.
  * Neural demand prediction (Predictor) attached to the City zone.
  * Attribute-based taxi state via PropertyStore.
"""
from __future__ import annotations

import math
import random

from czoi import (
    Application,
    CZOABuilder,
    Daemon,
    DaemonSignal,
    Decision,
    Operation,
    Predictor,
    Role,
    User,
)

random.seed(11)

# ---- World constants -------------------------------------------------
N_TAXIS = 20
N_PASSENGERS = 30
BATTERY_LOW = 20.0
BATTERY_FULL = 100.0
BATTERY_CHARGE_RATE = 5.0
BATTERY_DRAIN_EN_ROUTE = 0.1
BATTERY_DRAIN_ON_TRIP = 0.2
BATTERY_DRAIN_IDLE = 0.05
REQUEST_PROBABILITY = 0.3
IDLE_SHORTAGE_THRESHOLD = 3


# =====================================================================
# 1. Build the city system
# =====================================================================
def build_system():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("CityTransit")

    # ---- Zones -----------------------------------------------------
    city = builder.add_zone("City", parent=builder.root)
    downtown = builder.add_zone("Downtown", parent=city, atomic=True)
    suburb = builder.add_zone("Suburb", parent=city, atomic=True)
    airport = builder.add_zone("Airport", parent=city, atomic=True)
    charging = builder.add_zone("ChargingStation", parent=city, atomic=True)

    # ---- Application and operations --------------------------------
    app = Application("RideHailing", zone=city)
    request = app.add_operation(Operation("request_ride"))
    accept = app.add_operation(Operation("accept_ride"))
    navigate = app.add_operation(Operation("navigate"))
    charge = app.add_operation(Operation("charge"))
    monitor = app.add_operation(Operation("monitor_fleet"))
    city.add_application(app)

    # ---- Roles and base permissions --------------------------------
    taxi_role = Role(
        "Taxi",
        zone=city,
        base_permissions=[accept, navigate, charge],
    )
    manager_role = Role(
        "FleetManager",
        zone=city,
        base_permissions=[monitor, navigate],
    )
    passenger_role = Role(
        "Passenger",
        zone=city,
        base_permissions=[request],
    )
    city.add_role(taxi_role)
    city.add_role(manager_role)
    city.add_role(passenger_role)

    # ---- UniLog access constraint: SoD between request and accept --
    builder.add_access_constraint("""
        signature {
            sort User, Operation;
            predicate hasRole(u: User, r: Role);
            predicate rideHailing(u: User, o: Operation);
        }
        forall u: User . not (
            hasRole(u, Passenger) and hasRole(u, Taxi)
        )
    """)

    ops = {
        "request": request,
        "accept": accept,
        "navigate": navigate,
        "charge": charge,
        "monitor": monitor,
    }
    zones = {
        "city": city,
        "downtown": downtown,
        "suburb": suburb,
        "airport": airport,
        "charging": charging,
    }
    return builder, zones, ops


# =====================================================================
# 2. Create taxis, passengers, and manager
# =====================================================================
def create_users(builder, city, n_taxis: int, n_passengers: int):
    taxis = []
    for i in range(n_taxis):
        t = User(
            f"taxi_{i}",
            roles={"Taxi"},
            attributes={
                "position": [
                    random.uniform(-122.5, -122.3),
                    random.uniform(37.7, 37.8),
                ],
                "battery": 100.0,
                "status": "idle",
                "passenger_count": 0,
                "trips_completed": 0,
            },
        )
        builder.root.add_user(t)
        city.add_user(t)
        taxis.append(t)

    passengers = []
    for i in range(n_passengers):
        p = User(
            f"passenger_{i}",
            roles={"Passenger"},
            attributes={
                "position": [
                    random.uniform(-122.5, -122.3),
                    random.uniform(37.7, 37.8),
                ],
                "rides_taken": 0,
            },
        )
        builder.root.add_user(p)
        city.add_user(p)
        passengers.append(p)

    manager = User(
        "fleet_manager",
        roles={"FleetManager"},
        attributes={"position": [0.0, 0.0]},
    )
    builder.root.add_user(manager)
    city.add_user(manager)

    return taxis, passengers, manager


# =====================================================================
# 3. Neural demand predictor
# =====================================================================
def build_demand_predictor() -> Predictor:
    """Simple demand predictor: higher demand during peak hours.

    Trained on synthetic hourly demand counts. After fit, it predicts
    a probability of at least one request in the next minute.
    """
    import numpy as np

    # Features: [hour_normalised, day_of_week_normalised]
    X = np.array([
        [h / 24.0, d / 7.0]
        for h in range(24)
        for d in range(7)
    ])
    # Ground truth: peak at 8am and 6pm on weekdays.
    y = np.array([
        1.0 if (h in (8, 9, 17, 18) and d < 5) else 0.2
        for h in range(24)
        for d in range(7)
    ])

    predictor = Predictor("ride_demand", threshold=0.5)
    predictor.fit(X, y, epochs=500, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class BatteryDaemon(Daemon):
    """Warns when a taxi's battery drops below threshold."""

    def __init__(self, taxis, threshold: float = BATTERY_LOW, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.taxis = taxis
        self.threshold = threshold

    def monitor(self):
        for t in self.taxis:
            batt = t.attributes.get("battery", 100.0)
            if batt < self.threshold and t.attributes.get("status") != "charging":
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"taxi": t.name, "battery": round(batt, 2)},
                )


class IdleShortageDaemon(Daemon):
    """Signals STATE_WARNING when the idle-taxi pool is too small."""

    def __init__(self, taxis, threshold: int = IDLE_SHORTAGE_THRESHOLD,
                 parent=None):
        super().__init__("IdleShortageDaemon", parent=parent, interval=2.0)
        self.taxis = taxis
        self.threshold = threshold

    def monitor(self):
        idle = sum(
            1 for t in self.taxis
            if t.attributes.get("status") == "idle"
        )
        if idle < self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"idle_count": idle, "threshold": self.threshold},
            )


class PassengerDaemon(Daemon):
    """Detects sustained demand (many requests in a short window)."""

    def __init__(self, parent=None):
        super().__init__("PassengerDaemon", parent=parent, interval=5.0)
        self.recent_requests: list[float] = []

    def record_request(self, t: float) -> None:
        self.recent_requests.append(t)

    def monitor(self):
        # Keep the last 20 requests.
        if len(self.recent_requests) > 20:
            self.recent_requests = self.recent_requests[-20:]
        if len(self.recent_requests) >= 10:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"recent_requests": len(self.recent_requests)},
            )


class FleetDaemon(Daemon):
    """Root daemon: aggregates signals from children."""

    def __init__(self, parent=None):
        super().__init__("FleetDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source is not None else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 5. Simulation
# =====================================================================
class TaxiSimulation:
    """Ride-hailing simulation with real CZOI permission checks.

    Every accept_ride, navigate, and charge is gated by the engine.
    Passengers issue request_ride, which the engine also evaluates.
    """

    def __init__(self, builder, zones, ops, taxis, passengers, manager):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.taxis = taxis
        self.passengers = passengers
        self.manager = manager
        self.requests = 0
        self.served = 0
        self.denied_requests = 0
        self.wait_times: list[float] = []
        self.time = 0.0
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        city = self.zones["city"]
        hour = (self.time / 60.0) % 24.0

        # ---- Generate requests --------------------------------------
        if random.random() < REQUEST_PROBABILITY:
            self._issue_request(engine, city, hour)

        # ---- Advance each taxi's state machine ----------------------
        for t in list(self.taxis):
            self._advance_taxi(t, engine, city)

    # -----------------------------------------------------------------
    def _issue_request(self, engine, city, hour):
        self.requests += 1
        passenger = random.choice(self.passengers)
        pickup = random.choice(["Downtown", "Suburb", "Airport"])
        dropoff = random.choice(["Downtown", "Suburb", "Airport"])
        while dropoff == pickup:
            dropoff = random.choice(["Downtown", "Suburb", "Airport"])

        # Real permission check: can the passenger request a ride?
        op = self.ops["request"]
        if engine.decide(passenger, op, city) is not Decision.ALLOW:
            self.denied_requests += 1
            self._log("request_denied", passenger.name, pickup, dropoff)
            return

        self._log("request", passenger.name, pickup, dropoff)

        # Find an idle taxi with permission to accept.
        candidates = [
            t for t in self.taxis
            if t.attributes.get("status") == "idle"
            and engine.decide(t, self.ops["accept"], city) is Decision.ALLOW
        ]
        if not candidates:
            self._log("no_idle_taxi", passenger.name, pickup, dropoff)
            return

        nearest = min(
            candidates,
            key=lambda t: self._distance(
                t.attributes["position"],
                passenger.attributes["position"],
            ),
        )
        nearest.attributes.set("status", "en_route")
        nearest.attributes.set("pickup", pickup)
        nearest.attributes.set("dropoff", dropoff)
        wait = random.uniform(1.0, 5.0)
        self.wait_times.append(wait)
        self.served += 1
        self._log("assign", nearest.name, passenger.name, round(wait, 2))

    # -----------------------------------------------------------------
    def _advance_taxi(self, t, engine, city):
        status = t.attributes.get("status")
        batt = t.attributes.get("battery", 100.0)

        # ---- Charging ----------------------------------------------
        if batt < BATTERY_LOW and status != "charging":
            if engine.decide(t, self.ops["charge"], city) is Decision.ALLOW:
                t.attributes.set("status", "charging")
                t.attributes.set("position", list(
                    self.zones["charging"].properties.get("position", [0.0, 0.0])
                    or [0.0, 0.0]
                ))
                self._log("move_to_charge", t.name, None, None)
                return

        if status == "charging":
            new_batt = min(BATTERY_FULL, batt + BATTERY_CHARGE_RATE)
            t.attributes.set("battery", new_batt)
            if new_batt >= BATTERY_FULL - 0.1:
                t.attributes.set("status", "idle")
            return

        # ---- Normal state transitions ------------------------------
        if status == "en_route":
            t.attributes.set("battery", max(0.0, batt - BATTERY_DRAIN_EN_ROUTE))
            if random.random() < 0.3:
                t.attributes.set("status", "on_trip")
                t.attributes.set("passenger_count", 1)
                self._log("pickup", t.name, None, None)
        elif status == "on_trip":
            t.attributes.set("battery", max(0.0, batt - BATTERY_DRAIN_ON_TRIP))
            if random.random() < 0.4:
                t.attributes.set("status", "idle")
                t.attributes.set("passenger_count", 0)
                trips = t.attributes.get("trips_completed", 0) + 1
                t.attributes.set("trips_completed", trips)
                self._log("dropoff", t.name, None, None)
        else:   # idle
            t.attributes.set("battery", max(0.0, batt - BATTERY_DRAIN_IDLE))
            # Small random walk within the city.
            pos = t.attributes["position"]
            pos[0] += random.uniform(-0.001, 0.001)
            pos[1] += random.uniform(-0.001, 0.001)

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.time, 2), event) + tuple(args))

    @staticmethod
    def _distance(a, b) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()
    taxis, passengers, manager = create_users(
        builder, zones["city"], N_TAXIS, N_PASSENGERS
    )

    # ---- Neural component attached to the City zone -----------------
    demand_model = build_demand_predictor()
    zones["city"].add_neural("ride_demand", demand_model)

    # ---- Daemon hierarchy -------------------------------------------
    fleet = FleetDaemon()
    battery = BatteryDaemon(taxis, threshold=BATTERY_LOW, parent=fleet)
    shortage = IdleShortageDaemon(taxis, parent=fleet)
    passenger = PassengerDaemon(parent=fleet)
    builder.add_daemon(fleet)
    builder.add_daemon(battery)
    builder.add_daemon(shortage)
    builder.add_daemon(passenger)

    # ---- Sanity check: real CZOI permission decisions ---------------
    city = zones["city"]
    engine = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  taxi_0      accept   :", engine.decide(taxis[0], ops["accept"], city).name)
    print("  taxi_0      navigate :", engine.decide(taxis[0], ops["navigate"], city).name)
    print("  passenger_0 request  :", engine.decide(passengers[0], ops["request"], city).name)
    print("  passenger_0 accept   :", engine.decide(passengers[0], ops["accept"], city).name)
    print("  manager     monitor  :", engine.decide(manager, ops["monitor"], city).name)
    print("  manager     accept   :", engine.decide(manager, ops["accept"], city).name)
    print()

    # ---- Demand prediction sanity check -----------------------------
    demand_peak = demand_model.predict({"hour": 8 / 24.0, "day": 1 / 7.0})
    demand_off = demand_model.predict({"hour": 3 / 24.0, "day": 6 / 7.0})
    print(f"Demand at 8am weekday  : {demand_peak:.3f}")
    print(f"Demand at 3am weekend  : {demand_off:.3f}")
    print()

    # ---- Simulation: 1 hour at 1-minute steps ----------------------
    sim = TaxiSimulation(
        builder, zones, ops, taxis, passengers, manager,
    )
    for minute in range(60):
        sim.step(dt=1.0)
        if minute % 5 == 0:
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    avg_wait = (
        sum(sim.wait_times) / len(sim.wait_times)
        if sim.wait_times else 0.0
    )
    print(f"Requests issued     : {sim.requests}")
    print(f"Requests served     : {sim.served}")
    print(f"Requests denied     : {sim.denied_requests}")
    print(f"Average wait time   : {avg_wait:.2f} min")
    print(f"Taxis tracked       : {len(taxis)}")
    print(f"Fleet warnings      : {len(fleet.warnings)}")
    print(f"Fleet criticals     : {len(fleet.criticals)}")

    if fleet.criticals:
        print("\nFirst 3 high-demand alerts:")
        for src, payload in fleet.criticals[:3]:
            print(f"  from {src}: {payload}")

    if fleet.warnings:
        print("\nFirst 3 low-battery alerts:")
        for src, payload in fleet.warnings[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()