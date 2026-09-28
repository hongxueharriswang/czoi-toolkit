"""
traffic.py — Urban traffic-flow simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: City → District1 / District2 → Roads,
    plus a shared Intersection.
  * Applications and atomic operations (navigate, signal_control, reroute).
  * Real CZOI permission calculus (Φ) on every vehicle move.
  * UniLog access constraint: EmergencyVehicle may enter a full zone.
  * Hierarchical daemons (Δ): TrafficDaemon at root with
    CongestionDaemon, EmergencyDaemon, and ArrivalDaemon as children.
  * Neural congestion predictor attached to the City zone.
  * Route: RoadA → Intersection → (RoadB | RoadC).
"""
from __future__ import annotations

import random

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

random.seed(53)
np.random.seed(53)

# ---- World constants -------------------------------------------------
N_COMMUTERS = 50
N_EMERGENCY = 2
ZONE_CAPACITY = 10
SPEED_LIMIT = 50
CONGESTION_WARN = 0.80
CONGESTION_CRITICAL = 1.00
MIN_ARRIVAL_RATE = 0.05


# =====================================================================
# 1. Build the road network
# =====================================================================
def build_city():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("TrafficNetwork")

    # ---- Zone tree ---------------------------------------------------
    city = builder.add_zone("City", parent=builder.root)
    district1 = builder.add_zone("District1", parent=city)
    district2 = builder.add_zone("District2", parent=city)

    road_a = builder.add_zone("RoadA", parent=district1, atomic=True)
    road_b = builder.add_zone("RoadB", parent=district1, atomic=True)
    road_c = builder.add_zone("RoadC", parent=district2, atomic=True)
    intersection = builder.add_zone("Intersection", parent=city, atomic=True)

    # ---- Attributes on every zone -----------------------------------
    for z in (road_a, road_b, road_c, intersection):
        z.properties.set("capacity", ZONE_CAPACITY, type_hint="int")
        z.properties.set("speed_limit", SPEED_LIMIT, type_hint="int")
        z.properties.set("occupancy", 0, type_hint="int")

    # ---- Application and atomic operations -------------------------
    app = Application("Traffic", zone=city)
    navigate = app.add_operation(Operation("navigate"))
    signal   = app.add_operation(Operation("signal_control"))
    reroute  = app.add_operation(Operation("reroute"))
    city.add_application(app)

    # ---- Roles -------------------------------------------------------
    commuter_role = Role("Commuter", zone=city, base_permissions=[navigate])
    controller_role = Role("TrafficController", zone=city,
                           base_permissions=[signal, reroute])
    emergency_role = Role("EmergencyVehicle", zone=city,
                          base_permissions=[navigate, signal])
    city.add_role(commuter_role)
    city.add_role(controller_role)
    city.add_role(emergency_role)

    # ---- UniLog access constraint: emergency vehicles bypass fullness
    builder.add_access_constraint("""
        signature {
            sort User, Zone, Role;
            constant EmergencyVehicle : Role;
            predicate hasRole(u: User, r: Role);
            predicate zoneFull(z: Zone);
            predicate inZone(u: User, z: Zone);
        }
        forall u: User, z: Zone .
            (inZone(u, z) and zoneFull(z)
             and not hasRole(u, EmergencyVehicle))
            -> not inZone(u, z)
    """)

    ops = {"navigate": navigate, "signal": signal, "reroute": reroute}
    zones = {
        "City": city, "District1": district1, "District2": district2,
        "RoadA": road_a, "RoadB": road_b, "RoadC": road_c,
        "Intersection": intersection,
    }
    return builder, zones, ops


# =====================================================================
# 2. Register users along the containment path
# =====================================================================
def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 3. Create vehicles and controller
# =====================================================================
def create_vehicles(builder, zones):
    road_a = zones["RoadA"]
    road_b = zones["RoadB"]
    road_c = zones["RoadC"]

    commuters: list[User] = []
    for i in range(N_COMMUTERS):
        v = User(
            f"vehicle_{i}",
            roles={"Commuter"},
            attributes={
                "speed":        random.uniform(20.0, 60.0),
                "destination":  random.choice(["RoadB", "RoadC"]),
                "current_zone": "RoadA",
                "arrived":      False,
                "ticks_driving": 0,
            },
        )
        _register_along_path(v, road_a)
        commuters.append(v)

    emergency: list[User] = []
    for i in range(N_EMERGENCY):
        v = User(
            f"emergency_{i}",
            roles={"EmergencyVehicle"},
            attributes={
                "speed":       80.0,
                "destination": random.choice(["RoadB", "RoadC"]),
                "current_zone": "RoadA",
                "arrived":      False,
                "ticks_driving": 0,
            },
        )
        _register_along_path(v, road_a)
        emergency.append(v)

    controller = User(
        "controller",
        roles={"TrafficController"},
        attributes={"current_zone": "City"},
    )
    _register_along_path(controller, zones["City"])

    return commuters, emergency, controller


# =====================================================================
# 4. Neural congestion predictor
# =====================================================================
def build_congestion_predictor() -> Predictor:
    """Predicts P(zone will congest | occupancy_ratio, speed_limit, hour).

    Synthetic ground truth: zones at high occupancy during rush hours
    are likely to congest. Speed limit is a weak negative factor.
    """
    rng = np.random.default_rng(53)
    n = 800
    occ_ratio = rng.uniform(0.0, 1.0, n)
    speed_norm = rng.uniform(20.0, 80.0, n) / 80.0
    peak_hour = rng.integers(0, 2, n).astype(float)

    X = np.column_stack([occ_ratio, speed_norm, peak_hour])
    logits = 4.0 * occ_ratio - 1.0 * speed_norm + 1.5 * peak_hour - 2.5
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("congestion", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 5. Daemons (Δ)
# =====================================================================
class CongestionDaemon(Daemon):
    """Warns / alerts when a road zone is over its warning threshold."""

    def __init__(self, sim, warn: float = CONGESTION_WARN,
                 critical: float = CONGESTION_CRITICAL, parent=None):
        super().__init__("CongestionDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.warn = warn
        self.critical = critical

    def monitor(self):
        for name in ("RoadA", "RoadB", "RoadC", "Intersection"):
            zone = self.sim.zones[name]
            cap = zone.properties.get("capacity", 1)
            occ = self.sim.occupancy(name)
            ratio = occ / cap if cap else 0.0
            if ratio >= self.critical:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"zone": name, "occupancy": occ, "capacity": cap},
                )
            elif ratio >= self.warn:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"zone": name, "occupancy": occ, "capacity": cap,
                     "ratio": round(ratio, 2)},
                )


class EmergencyDaemon(Daemon):
    """Tracks emergency vehicles and signals when one is on the road."""

    def __init__(self, emergency, parent=None):
        super().__init__("EmergencyDaemon", parent=parent, interval=2.0)
        self.emergency = emergency

    def monitor(self):
        for v in self.emergency:
            if v.attributes.get("arrived"):
                continue
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"vehicle": v.name,
                 "zone": v.attributes.get("current_zone"),
                 "destination": v.attributes.get("destination")},
            )


class ArrivalDaemon(Daemon):
    """Signals when the arrival rate stalls (potential gridlock)."""

    def __init__(self, sim, min_rate: float = MIN_ARRIVAL_RATE, parent=None):
        super().__init__("ArrivalDaemon", parent=parent, interval=5.0)
        self.sim = sim
        self.min_rate = min_rate
        self._last_arrived = 0

    def monitor(self):
        arrived = self.sim.arrived_count
        delta = arrived - self._last_arrived
        self._last_arrived = arrived
        if self.sim.time > 30 and delta == 0:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"arrived_total": arrived, "recent_delta": delta},
            )


class TrafficDaemon(Daemon):
    """Root daemon: aggregates child signals."""

    def __init__(self, parent=None):
        super().__init__("TrafficDaemon", parent=parent, interval=2.0)
        self.warnings:  list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 6. Simulation
# =====================================================================
class TrafficSimulation:
    """Vehicle routing with real CZOI permission checks.

    Route: RoadA → Intersection → destination (RoadB or RoadC).

    On each tick, each non-arrived vehicle attempts one move. The move
    is gated by:
      1. Inline capacity check on the destination zone.
      2. The real Φ engine (which for regular commuters honours the
         UniLog "zoneFull → denied" constraint).
      3. Emergency vehicles bypass the capacity gate directly and are
         protected by the UniLog constraint's EmergencyVehicle clause.
    """

    def __init__(self, builder, zones, ops, commuters, emergency, controller):
        self.builder = builder
        self.zones   = zones
        self.ops     = ops
        self.commuters = commuters
        self.emergency = emergency
        self.controller = controller
        self.vehicles = commuters + emergency
        self.time = 0.0
        self.arrived_count = 0
        self.denied_moves = 0
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def occupancy(self, zone_name: str) -> int:
        return sum(
            1 for v in self.vehicles
            if v.attributes.get("current_zone") == zone_name
            and not v.attributes.get("arrived")
        )

    # -----------------------------------------------------------------
    def _next_zone(self, vehicle) -> str | None:
        current = vehicle.attributes.get("current_zone")
        dest = vehicle.attributes.get("destination")
        if current == dest:
            return None
        if current == "RoadA":
            return "Intersection"
        if current == "Intersection":
            return dest
        return None

    # -----------------------------------------------------------------
    def step(self, dt: float = 5.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        city = self.zones["City"]

        random.shuffle(self.vehicles)
        for v in self.vehicles:
            if v.attributes.get("arrived"):
                continue

            nxt_name = self._next_zone(v)
            if nxt_name is None:
                # No next zone → consider arrived if at destination.
                if v.attributes.get("current_zone") == v.attributes.get("destination"):
                    v.attributes.set("arrived", True)
                    self.arrived_count += 1
                    self._log("arrive", v.name,
                              v.attributes.get("destination"))
                continue

            nxt = self.zones[nxt_name]
            cap = nxt.properties.get("capacity", 999)
            occ = self.occupancy(nxt_name)
            is_emergency = v.has_role("EmergencyVehicle")

            # ---- Inline capacity gate (bypassed for emergency) -----
            if not is_emergency and occ >= cap:
                v.attributes.set("ticks_driving",
                                 v.attributes.get("ticks_driving", 0) + 1)
                continue

            # ---- Real Φ check --------------------------------------
            if engine.decide(v, self.ops["navigate"], city) \
                    is not Decision.ALLOW:
                self.denied_moves += 1
                continue

            # ---- Perform the move ----------------------------------
            prev = v.attributes.get("current_zone")
            v.attributes.set("current_zone", nxt_name)
            v.attributes.set("ticks_driving",
                             v.attributes.get("ticks_driving", 0) + 1)

            # Immediate arrival check (destination reached this tick).
            if nxt_name == v.attributes.get("destination"):
                v.attributes.set("arrived", True)
                self.arrived_count += 1
                self._log("arrive", v.name, nxt_name)
            else:
                self._log("move", v.name, prev, nxt_name)

        # ---- Refresh per-zone occupancy attribute ---------------
        for name in ("RoadA", "RoadB", "RoadC", "Intersection"):
            self.zones[name].properties.set("occupancy",
                                            self.occupancy(name),
                                            type_hint="int")

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.time, 1), event) + tuple(args))


# =====================================================================
# 7. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_city()
    commuters, emergency, controller = create_vehicles(builder, zones)

    # ---- Neural component attached to the City zone -----------------
    congestion_model = build_congestion_predictor()
    zones["City"].add_neural("congestion", congestion_model)

    # ---- Sanity check on the predictor ------------------------------
    low_p  = congestion_model.predict(
        {"occ": 0.2, "speed_norm": 0.7, "peak": 0.0},
    )
    high_p = congestion_model.predict(
        {"occ": 0.9, "speed_norm": 0.4, "peak": 1.0},
    )
    print(f"P(congestion) | low occ, off-peak : {low_p:.3f}")
    print(f"P(congestion) | high occ, peak    : {high_p:.3f}")
    print()

    # ---- Simulation object ------------------------------------------
    sim = TrafficSimulation(
        builder, zones, ops, commuters, emergency, controller,
    )

    # ---- Daemon hierarchy -------------------------------------------
    root = TrafficDaemon()
    congestion = CongestionDaemon(sim, parent=root)
    emergency_d = EmergencyDaemon(emergency, parent=root)
    arrival = ArrivalDaemon(sim, parent=root)
    builder.add_daemon(root)
    builder.add_daemon(congestion)
    builder.add_daemon(emergency_d)
    builder.add_daemon(arrival)

    # ---- Sanity check: real CZOI permission decisions ---------------
    city = zones["City"]
    engine = builder.permission_engine
    commuter = commuters[0]
    emerg = emergency[0]
    print("Permission sanity check (paper §3, item 9):")
    print(f"  {commuter.name:<14} navigate       :",
          engine.decide(commuter, ops["navigate"], city).name)
    print(f"  {commuter.name:<14} signal_control :",
          engine.decide(commuter, ops["signal"], city).name)
    print(f"  {emerg.name:<14} navigate       :",
          engine.decide(emerg, ops["navigate"], city).name)
    print(f"  {emerg.name:<14} signal_control :",
          engine.decide(emerg, ops["signal"], city).name)
    print(f"  {'controller':<14} signal_control :",
          engine.decide(controller, ops["signal"], city).name)
    print(f"  {'controller':<14} navigate       :",
          engine.decide(controller, ops["navigate"], city).name)
    print()

    # ---- Simulate 10 minutes at 5-second steps ---------------------
    steps = 10 * 12                 # 10 min / 5 s = 120 steps
    for s in range(steps):
        sim.step(dt=5.0)
        if s % 3 == 0:
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    print(f"Arrived               : {sim.arrived_count}/{len(sim.vehicles)}")
    print(f"Commuters arrived     : "
          f"{sum(1 for v in commuters if v.attributes.get('arrived'))}"
          f"/{len(commuters)}")
    print(f"Emergency arrived     : "
          f"{sum(1 for v in emergency if v.attributes.get('arrived'))}"
          f"/{len(emergency)}")
    print(f"Denied moves          : {sim.denied_moves}")
    print("Final occupancy:")
    for name in ("RoadA", "RoadB", "RoadC", "Intersection"):
        print(f"  {name:<14}: {sim.occupancy(name):>3} / "
              f"{zones[name].properties.get('capacity')}")
    print(f"Root warnings         : {len(root.warnings)}")
    print(f"Root criticals        : {len(root.criticals)}")

    if root.criticals:
        print("\nFirst 3 criticals:")
        for src, payload in root.criticals[:3]:
            print(f"  from {src}: {payload}")

    if root.warnings:
        print("\nFirst 3 warnings:")
        for src, payload in root.warnings[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()