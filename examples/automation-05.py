"""
drone_swarm.py — Surveillance drone swarm simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Deep recursive zone tree: OperationArea → 100 atomic Sector_i_j + Base.
  * Applications and atomic operations (fly_to, scan, transmit, return).
  * Real CZOI permission calculus (Φ) on every drone action.
  * UniLog access constraint: at most N drones in the same sector.
  * Hierarchical daemons (Δ): SwarmDaemon at root with BatteryDaemon,
    CoverageDaemon, and CollisionDaemon as children.
  * Neural battery-failure prediction attached to the OperationArea.
  * Attribute-based drone state via PropertyStore.
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

random.seed(29)

# ---- World constants -------------------------------------------------
GRID = 10
N_SURVEY = 5
N_RELAY = 2
BATTERY_LOW = 20.0
BATTERY_FULL = 100.0
BATTERY_CHARGE_RATE = 5.0
BATTERY_DRAIN_SURVEY = 1.0
BATTERY_DRAIN_RELAY = 0.5
BASE_POSITION = (-1, -1)   # outside the grid
SECTOR_CAPACITY = 2


# =====================================================================
# 1. Build the operation area
# =====================================================================
def build_system():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("DroneOperations")

    # ---- Zones: OperationArea (composite) + 100 sectors + base -----
    area = builder.add_zone("OperationArea", parent=builder.root)
    base = builder.add_zone("BaseStation", parent=area, atomic=True)

    sectors: dict[tuple[int, int], "ZoneBase"] = {}
    for i in range(GRID):
        for j in range(GRID):
            sec = builder.add_zone(
                f"Sector_{i}_{j}", parent=area, atomic=True,
            )
            sec.properties.set("row", i, type_hint="int")
            sec.properties.set("col", j, type_hint="int")
            sec.properties.set("capacity", SECTOR_CAPACITY, type_hint="int")
            sectors[(i, j)] = sec

    # ---- Application and atomic operations -------------------------
    app = Application("SurveillanceApp", zone=area)
    fly = app.add_operation(Operation("fly_to"))
    scan = app.add_operation(Operation("scan"))
    transmit = app.add_operation(Operation("transmit"))
    return_op = app.add_operation(Operation("return_to_base"))
    recall = app.add_operation(Operation("recall_fleet"))
    area.add_application(app)

    # ---- Roles and base permissions --------------------------------
    survey_role = Role(
        "SurveyDrone",
        zone=area,
        base_permissions=[fly, scan, transmit, return_op],
    )
    relay_role = Role(
        "RelayDrone",
        zone=area,
        base_permissions=[fly, transmit, return_op],
    )
    operator_role = Role(
        "BaseOperator",
        zone=area,
        base_permissions=[recall, transmit],
    )
    area.add_role(survey_role)
    area.add_role(relay_role)
    area.add_role(operator_role)

    # ---- UniLog sector-capacity constraint -------------------------
    builder.add_access_constraint("""
        signature {
            sort User, Zone;
            predicate inZone(u: User, z: Zone);
            predicate sectorFull(z: Zone);
        }
        forall u: User, z: Zone .
            (inZone(u, z) and sectorFull(z)) -> not inZone(u, z)
    """)

    ops = {
        "fly": fly,
        "scan": scan,
        "transmit": transmit,
        "return": return_op,
        "recall": recall,
    }
    zones = {"area": area, "base": base, "sectors": sectors}
    return builder, zones, ops


# =====================================================================
# 2. Create drones and operator
# =====================================================================
def create_users(builder, area, n_survey: int, n_relay: int):
    survey_drones, relay_drones = [], []

    for i in range(n_survey):
        d = User(
            f"survey_{i}",
            roles={"SurveyDrone"},
            attributes={
                "position": BASE_POSITION,
                "battery": 100.0,
                "coverage": set(),
                "scans": 0,
            },
        )
        builder.root.add_user(d)
        area.add_user(d)
        survey_drones.append(d)

    for i in range(n_relay):
        d = User(
            f"relay_{i}",
            roles={"RelayDrone"},
            attributes={
                "position": BASE_POSITION,
                "battery": 100.0,
                "coverage": set(),
                "relayed": 0,
            },
        )
        builder.root.add_user(d)
        area.add_user(d)
        relay_drones.append(d)

    operator = User(
        "base_operator",
        roles={"BaseOperator"},
        attributes={"position": BASE_POSITION},
    )
    builder.root.add_user(operator)
    area.add_user(operator)

    return survey_drones, relay_drones, operator


# =====================================================================
# 3. Neural battery-failure predictor
# =====================================================================
def build_battery_predictor() -> Predictor:
    """Predicts the probability of a drone failing to return.

    Trained on synthetic data. Features:
      [battery_normalised, distance_to_base_normalised,
       wind_normalised]
    """
    import numpy as np

    rng = np.random.default_rng(0)
    n = 400
    X = np.column_stack([
        rng.uniform(0, 1, n),      # battery / 100
        rng.uniform(0, 1, n),      # distance / max
        rng.uniform(0, 1, n),      # wind
    ])
    # Ground truth: failure risk high when battery is low and distance
    # is large (regardless of wind).
    logits = -8 * X[:, 0] + 4 * X[:, 1] + 0.5 * X[:, 2] + 5
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("battery_failure", threshold=0.5)
    predictor.fit(X, y, epochs=1000, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class BatteryDaemon(Daemon):
    """Warns when a drone's battery drops below threshold and it is
    currently deployed (not at base)."""

    def __init__(self, drones, threshold: float = BATTERY_LOW, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.drones = drones
        self.threshold = threshold

    def monitor(self):
        for d in self.drones:
            batt = d.attributes.get("battery", 100.0)
            pos = d.attributes.get("position", BASE_POSITION)
            if batt < self.threshold and pos != BASE_POSITION:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"drone": d.name, "battery": round(batt, 2)},
                )


class CoverageDaemon(Daemon):
    """Warns when coverage progress stalls (few new cells per window)."""

    def __init__(self, sim, min_progress: int = 1, parent=None):
        super().__init__("CoverageDaemon", parent=parent, interval=5.0)
        self.sim = sim
        self.min_progress = min_progress
        self._last_count = 0

    def monitor(self):
        current = len(self.sim.covered_cells)
        delta = current - self._last_count
        if self._last_count > 0 and delta < self.min_progress:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"coverage": current, "delta": delta},
            )
        self._last_count = current


class CollisionDaemon(Daemon):
    """Signals STATE_CRITICAL if too many drones share a sector."""

    def __init__(self, drones, capacity: int = SECTOR_CAPACITY, parent=None):
        super().__init__("CollisionDaemon", parent=parent, interval=1.0)
        self.drones = drones
        self.capacity = capacity

    def monitor(self):
        from collections import Counter
        positions = Counter(
            d.attributes.get("position", BASE_POSITION)
            for d in self.drones
        )
        for pos, count in positions.items():
            if pos == BASE_POSITION:
                continue
            if count > self.capacity:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"position": pos, "count": count,
                     "capacity": self.capacity},
                )


class SwarmDaemon(Daemon):
    """Root daemon aggregating signals from the child daemons."""

    def __init__(self, parent=None):
        super().__init__("SwarmDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []
        self.recall_ordered = False

    def on_signal(self, signal, payload, source=None):
        src = source.name if source is not None else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))
            # Collision criticals trigger a fleet-wide recall.
            if src == "CollisionDaemon":
                self.recall_ordered = True


# =====================================================================
# 5. Simulation
# =====================================================================
class DroneSimulation:
    """Survey-and-scan mission with real CZOI permission checks.

    Every fly_to, scan, transmit, and return_to_base is gated by the
    engine. Relay drones cannot scan (their role lacks the operation).
    """

    def __init__(
        self,
        builder,
        zones,
        ops,
        survey_drones,
        relay_drones,
        operator,
        battery_model: Predictor,
    ):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.survey_drones = survey_drones
        self.relay_drones = relay_drones
        self.operator = operator
        self.all_drones = survey_drones + relay_drones
        self.battery_model = battery_model
        self.covered_cells: set[tuple[int, int]] = set()
        self.time = 0.0
        self.logs: list[tuple] = []
        self.recalls_issued = 0

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        area = self.zones["area"]

        # ---- Survey drones ------------------------------------------
        for d in list(self.survey_drones):
            batt = d.attributes.get("battery", 100.0)
            pos = d.attributes.get("position", BASE_POSITION)

            # Low battery → return to base, then charge.
            if batt < BATTERY_LOW and pos != BASE_POSITION:
                if engine.decide(d, self.ops["return"], area) is Decision.ALLOW:
                    d.attributes.set("position", BASE_POSITION)
                    self._log("return", d.name, None)
                continue

            if pos == BASE_POSITION:
                # Charging at base.
                new_batt = min(BATTERY_FULL, batt + BATTERY_CHARGE_RATE)
                d.attributes.set("battery", new_batt)
                if new_batt >= BATTERY_FULL - 0.1:
                    # Head to a new sector.
                    target = self._pick_uncovered_sector(d)
                    if engine.decide(d, self.ops["fly"], area) is Decision.ALLOW:
                        d.attributes.set("position", target)
                        self._log("fly", d.name, target)
                continue

            # Currently in a sector → try to scan.
            row, col = pos
            cell = (row, col)
            if cell not in d.attributes.get("coverage", set()):
                if engine.decide(d, self.ops["scan"], area) is Decision.ALLOW:
                    d.attributes["coverage"].add(cell)
                    d.attributes.set("scans", d.attributes.get("scans", 0) + 1)
                    self.covered_cells.add(cell)
                    self._log("scan", d.name, cell)
            # Drain battery.
            new_batt = max(0.0, d.attributes.get("battery", 0.0)
                           - BATTERY_DRAIN_SURVEY)
            d.attributes.set("battery", new_batt)
            # Move to next sector occasionally.
            if random.random() < 0.4:
                target = self._pick_uncovered_sector(d)
                if engine.decide(d, self.ops["fly"], area) is Decision.ALLOW:
                    d.attributes.set("position", target)

        # ---- Relay drones -------------------------------------------
        for d in list(self.relay_drones):
            batt = d.attributes.get("battery", 100.0)
            pos = d.attributes.get("position", BASE_POSITION)

            if batt < BATTERY_LOW and pos != BASE_POSITION:
                if engine.decide(d, self.ops["return"], area) is Decision.ALLOW:
                    d.attributes.set("position", BASE_POSITION)
                continue

            if pos == BASE_POSITION:
                new_batt = min(BATTERY_FULL, batt + BATTERY_CHARGE_RATE)
                d.attributes.set("battery", new_batt)
                if new_batt >= BATTERY_FULL - 0.1:
                    # Relays hover near the base to extend comms.
                    if engine.decide(d, self.ops["fly"], area) is Decision.ALLOW:
                        d.attributes.set("position", (0, 0))
                continue

            # Relay transmits (extends comms).
            if engine.decide(d, self.ops["transmit"], area) is Decision.ALLOW:
                d.attributes.set(
                    "relayed", d.attributes.get("relayed", 0) + 1,
                )
            new_batt = max(0.0, d.attributes.get("battery", 0.0)
                           - BATTERY_DRAIN_RELAY)
            d.attributes.set("battery", new_batt)

        # ---- Operator recall (triggered by root daemon) -------------
        swarm = getattr(self.builder, "_swarm_daemon", None)
        if swarm is not None and swarm.recall_ordered and not self.recalls_issued:
            if engine.decide(self.operator, self.ops["recall"], area) is Decision.ALLOW:
                for d in self.all_drones:
                    d.attributes.set("position", BASE_POSITION)
                self.recalls_issued += 1
                self._log("recall", self.operator.name, None)

    # -----------------------------------------------------------------
    def _pick_uncovered_sector(self, d) -> tuple[int, int]:
        """Choose an uncovered sector; fall back to random if all covered."""
        own = d.attributes.get("coverage", set())
        uncovered = [
            (i, j)
            for i in range(GRID)
            for j in range(GRID)
            if (i, j) not in self.covered_cells
            and (i, j) not in own
        ]
        if uncovered:
            return random.choice(uncovered)
        return (random.randint(0, GRID - 1), random.randint(0, GRID - 1))

    # -----------------------------------------------------------------
    def _log(self, event: str, actor: str, payload) -> None:
        self.logs.append((round(self.time, 2), event, actor, payload))


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()
    survey, relay, operator = create_users(
        builder, zones["area"], N_SURVEY, N_RELAY,
    )

    # ---- Neural component attached to OperationArea -----------------
    battery_model = build_battery_predictor()
    zones["area"].add_neural("battery_failure", battery_model)

    # ---- Sanity check on the battery predictor ----------------------
    safe_p = battery_model.predict({
        "battery": 0.9, "distance": 0.2, "wind": 0.3,
    })
    risky_p = battery_model.predict({
        "battery": 0.1, "distance": 0.9, "wind": 0.8,
    })
    print(f"Return-success — high battery, close : {safe_p:.3f}")
    print(f"Return-failure — low battery, far    : {risky_p:.3f}")
    print()

    # ---- Simulation object ------------------------------------------
    sim = DroneSimulation(
        builder, zones, ops, survey, relay, operator, battery_model,
    )

    # ---- Daemon hierarchy -------------------------------------------
    swarm = SwarmDaemon()
    battery = BatteryDaemon(sim.all_drones, threshold=BATTERY_LOW, parent=swarm)
    coverage = CoverageDaemon(sim, min_progress=1, parent=swarm)
    collision = CollisionDaemon(sim.all_drones, capacity=SECTOR_CAPACITY,
                                parent=swarm)
    builder.add_daemon(swarm)
    builder.add_daemon(battery)
    builder.add_daemon(coverage)
    builder.add_daemon(collision)
    builder._swarm_daemon = swarm

    # ---- Sanity check: real CZOI permission decisions ---------------
    area = zones["area"]
    engine = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  survey_0   scan        :",
          engine.decide(survey[0], ops["scan"], area).name)
    print("  survey_0   fly         :",
          engine.decide(survey[0], ops["fly"], area).name)
    print("  relay_0    scan        :",
          engine.decide(relay[0], ops["scan"], area).name)
    print("  relay_0    transmit    :",
          engine.decide(relay[0], ops["transmit"], area).name)
    print("  operator   recall      :",
          engine.decide(operator, ops["recall"], area).name)
    print("  operator   scan        :",
          engine.decide(operator, ops["scan"], area).name)
    print()

    # ---- Simulate 60 minutes at 1-minute steps ---------------------
    for minute in range(60):
        sim.step(dt=1.0)
        if minute % 5 == 0:
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    coverage_pct = 100.0 * len(sim.covered_cells) / (GRID * GRID)
    print(f"Unique cells covered  : {len(sim.covered_cells)} / {GRID * GRID} "
          f"({coverage_pct:.1f}%)")
    print(f"Survey drones active  : {len(survey)}")
    print(f"Relay drones active   : {len(relay)}")
    print(f"Total scans performed : "
          f"{sum(d.attributes.get('scans', 0) for d in survey)}")
    print(f"Total relays          : "
          f"{sum(d.attributes.get('relayed', 0) for d in relay)}")
    print(f"Recall issued         : {swarm.recall_ordered}")
    print(f"Swarm warnings        : {len(swarm.warnings)}")
    print(f"Swarm criticals       : {len(swarm.criticals)}")

    if swarm.criticals:
        print("\nFirst 3 collision alerts:")
        for src, payload in swarm.criticals[:3]:
            print(f"  from {src}: {payload}")

    if swarm.warnings:
        print("\nFirst 3 warnings:")
        for src, payload in swarm.warnings[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()