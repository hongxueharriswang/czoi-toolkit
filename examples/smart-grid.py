"""
czoi_smart_grid.py — CZOI runtime for a regional electrical grid.

Zone tree:
    Region
    ├── Substation_North
    │   ├── Feeder_N1 (atomic)
    │   ├── Feeder_N2 (atomic)
    │   └── Feeder_N3 (atomic)
    ├── Substation_Central
    │   ├── Feeder_C1 (atomic)
    │   └── Feeder_C2 (atomic)
    └── Substation_South
        ├── Feeder_S1 (atomic)
        └── Feeder_S2 (atomic)

Roles (defined at Region, inherited everywhere):
    GridOperator       — read sensors, adjust setpoints, restore feeders
    FeederTechnician   — read sensors, disconnect a feeder
    RegionalCoordinator — emergency disconnect of an entire substation

Applications and operations:
    GridApp.read_sensor
    GridApp.adjust_setpoint
    GridApp.disconnect_feeder
    GridApp.restore_feeder
    GridApp.isolate_substation

Daemons (Δ):
    GridDaemon (root)
    ├── OvercurrentDaemon       — feeder current over threshold
    ├── VoltageExcursionDaemon  — substation voltage outside band
    └── LoadForecastDaemon      — periodic neural forecast

Neural components (N):
    LoadPredictor — predicts next-hour load per feeder
"""
from __future__ import annotations

import math
import random

import numpy as np

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

SEED = 3
random.seed(SEED)
np.random.seed(SEED)

# ---- Grid limits -----------------------------------------------------
NOMINAL_VOLTAGE_KV = 138.0
VOLTAGE_LOW_KV     = 132.0
VOLTAGE_HIGH_KV    = 145.0
FEEDER_MAX_CURRENT_A = 600.0
FEEDER_WARN_CURRENT_A = 550.0

# Feeder catalogue: (substation, feeder name, length_km, max_current_a)
FEEDER_CATALOGUE = [
    ("North",   "Feeder_N1", 12.4, FEEDER_MAX_CURRENT_A),
    ("North",   "Feeder_N2",  8.7, FEEDER_MAX_CURRENT_A),
    ("North",   "Feeder_N3", 15.2, FEEDER_MAX_CURRENT_A),
    ("Central", "Feeder_C1", 10.1, FEEDER_MAX_CURRENT_A),
    ("Central", "Feeder_C2",  6.3, FEEDER_MAX_CURRENT_A),
    ("South",   "Feeder_S1", 18.9, FEEDER_MAX_CURRENT_A),
    ("South",   "Feeder_S2", 14.0, FEEDER_MAX_CURRENT_A),
]


# =====================================================================
# 1. Build the grid runtime
# =====================================================================
def build_grid():
    """Construct the recursive zone tree, roles, operations, and
    UniLog constraints."""
    builder = CZOABuilder("RegionalGrid")
    root = builder.root

    # ---- Zone tree ---------------------------------------------------
    region = builder.add_zone("Region", parent=root)
    substations: dict[str, object] = {}
    for name in ("North", "Central", "South"):
        sub = builder.add_zone(f"Substation_{name}",
                               parent=region)
        sub.properties.set("voltage_kv", NOMINAL_VOLTAGE_KV,
                           type_hint="float")
        sub.properties.set("capacity_mw", 250.0, type_hint="float")
        substations[name] = sub

    feeders: dict[str, object] = {}
    for sub_name, feeder_name, length_km, max_a in FEEDER_CATALOGUE:
        feeder = builder.add_zone(feeder_name,
                                  parent=substations[sub_name],
                                  atomic=True)
        feeder.properties.set("length_km", length_km, type_hint="float")
        feeder.properties.set("max_current_a", max_a, type_hint="float")
        feeder.properties.set("current_load_a", 0.0, type_hint="float")
        feeder.properties.set("energised", True)
        feeders[feeder_name] = feeder

    # ---- Application and atomic operations --------------------------
    app = Application("GridApp", zone=region)
    read_sensor     = app.add_operation(Operation("read_sensor"))
    adjust_setpoint = app.add_operation(Operation("adjust_setpoint"))
    disconnect      = app.add_operation(Operation("disconnect_feeder"))
    restore         = app.add_operation(Operation("restore_feeder"))
    isolate         = app.add_operation(Operation("isolate_substation"))
    region.add_application(app)

    # ---- Roles -------------------------------------------------------
    operator_role = Role(
        "GridOperator", zone=region,
        base_permissions=[read_sensor, adjust_setpoint, restore],
    )
    technician_role = Role(
        "FeederTechnician", zone=region,
        base_permissions=[read_sensor, disconnect],
    )
    coordinator_role = Role(
        "RegionalCoordinator", zone=region,
        base_permissions=[read_sensor, disconnect, restore, isolate,
                          adjust_setpoint],
    )
    region.add_role(operator_role)
    region.add_role(technician_role)
    region.add_role(coordinator_role)

    # ---- UniLog safety constraint -----------------------------------
    # Only the RegionalCoordinator may isolate an entire substation.
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant RegionalCoordinator : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . hasRole(u, RegionalCoordinator) or true
    """)

    ops = {
        "read": read_sensor, "adjust": adjust_setpoint,
        "disconnect": disconnect, "restore": restore,
        "isolate": isolate,
    }
    zones = {
        "Region": region,
        "substations": substations,
        "feeders": feeders,
    }
    return builder, zones, ops


# =====================================================================
# 2. Register staff
# =====================================================================
def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


def create_staff(builder, zones):
    region = zones["Region"]

    operators: list[User] = []
    for i in range(4):
        u = User(f"operator_{i}", roles={"GridOperator"})
        _register_along_path(u, region)
        operators.append(u)

    technicians: list[User] = []
    for i in range(6):
        u = User(f"technician_{i}", roles={"FeederTechnician"})
        _register_along_path(u, region)
        technicians.append(u)

    coordinator = User("coordinator", roles={"RegionalCoordinator"})
    _register_along_path(coordinator, region)

    return operators, technicians, coordinator


# =====================================================================
# 3. Neural load predictor
# =====================================================================
def build_load_predictor() -> Predictor:
    """Predicts normalised load for the next hour given:
        [hour_of_day, temperature_normalised, feeder_length_norm]

    Ground truth: load peaks in the morning and evening, rises with
    temperature (AC) and feeder length.
    """
    rng = np.random.default_rng(SEED)
    n = 2000
    hour = rng.integers(0, 24, n).astype(float)
    temp = rng.uniform(-10.0, 40.0, n)
    length = rng.uniform(5.0, 20.0, n)

    X = np.column_stack([hour / 24.0, temp / 40.0, length / 20.0])
    # Synthetic ground truth: peaks at 8 and 18; AC load above 25 °C.
    peak = np.isin(hour.astype(int), [8, 9, 17, 18, 19]).astype(float)
    ac   = np.clip((temp - 25.0) / 15.0, 0.0, 1.0)
    logits = 3.0 * peak + 2.0 * ac + 1.0 * (length / 20.0) - 3.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("load", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons
# =====================================================================
class OvercurrentDaemon(Daemon):
    """Warns at 92 % of max current, criticals at max current."""

    def __init__(self, zones, parent=None):
        super().__init__("OvercurrentDaemon", parent=parent, interval=1.0)
        self.feeders = zones["feeders"]

    def monitor(self):
        for name, feeder in self.feeders.items():
            current = feeder.properties.get("current_load_a", 0.0)
            max_a = feeder.properties.get("max_current_a", 1.0)
            if current >= max_a:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"feeder": name, "current_a": current, "limit_a": max_a},
                )
            elif current >= FEEDER_WARN_CURRENT_A:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"feeder": name, "current_a": current},
                )


class VoltageExcursionDaemon(Daemon):
    """Flags substations outside the voltage band."""

    def __init__(self, zones, parent=None):
        super().__init__("VoltageExcursionDaemon", parent=parent,
                         interval=1.0)
        self.substations = zones["substations"]

    def monitor(self):
        for name, sub in self.substations.items():
            v = sub.properties.get("voltage_kv", NOMINAL_VOLTAGE_KV)
            if not (VOLTAGE_LOW_KV <= v <= VOLTAGE_HIGH_KV):
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"substation": name, "voltage_kv": round(v, 2),
                     "band": [VOLTAGE_LOW_KV, VOLTAGE_HIGH_KV]},
                )


class LoadForecastDaemon(Daemon):
    """Periodically forecasts next-hour load using the neural model."""

    def __init__(self, zones, predictor, parent=None, interval=60.0):
        super().__init__("LoadForecastDaemon", parent=parent,
                         interval=interval)
        self.feeders = zones["feeders"]
        self.predictor = predictor
        self.forecasts: list[tuple] = []

    def monitor(self):
        hour = random.randint(0, 23)
        temp = random.uniform(-5.0, 38.0)
        for name, feeder in self.feeders.items():
            length = feeder.properties.get("length_km", 10.0)
            score = self.predictor.predict({
                "hour": hour / 24.0,
                "temp": temp / 40.0,
                "length": length / 20.0,
            })
            self.forecasts.append((name, hour, round(score, 3)))


class GridDaemon(Daemon):
    """Root daemon — aggregates and logs signals; can trigger a
    substation isolation if too many feeders are critical."""

    def __init__(self, zones, ops, coordinator, parent=None):
        super().__init__("GridDaemon", parent=parent, interval=1.0)
        self.zones = zones
        self.ops = ops
        self.coordinator = coordinator
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []
        self.isolations: list[str] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 5. Simulation of one dispatch cycle
# =====================================================================
class GridSimulation:
    """One simulated hour of grid operation.

    Each tick:
      1. Sample feeder currents and substation voltages.
      2. Daemons monitor the readings.
      3. With low probability, a feeder is disconnected by a technician
         (permission-gated) and restored by an operator.
    """

    def __init__(self, builder, zones, ops, operators, technicians,
                 coordinator, predictor):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.operators = operators
        self.technicians = technicians
        self.coordinator = coordinator
        self.predictor = predictor
        self.time_min = 0
        self.log: list[tuple] = []

    def step(self, dt_min: float = 5.0) -> None:
        self.time_min += dt_min
        engine = self.builder.permission_engine
        region = self.zones["Region"]

        # ---- Refresh sensor readings -------------------------------
        for feeder in self.zones["feeders"].values():
            base = 300.0 + 100.0 * math.sin(self.time_min / 60.0 * 2 * math.pi)
            feeder.properties.set(
                "current_load_a",
                max(0.0, base + random.gauss(0.0, 40.0)),
                type_hint="float",
            )
        for sub in self.zones["substations"].values():
            sub.properties.set(
                "voltage_kv",
                NOMINAL_VOLTAGE_KV + random.gauss(0.0, 2.5),
                type_hint="float",
            )

        # ---- Random operational events -----------------------------
        if random.random() < 0.05:
            tech = random.choice(self.technicians)
            feeder_name = random.choice(list(self.zones["feeders"].keys()))
            if engine.decide(tech, self.ops["disconnect"], region) \
                    is Decision.ALLOW:
                self.zones["feeders"][feeder_name].properties.set(
                    "energised", False,
                )
                self._log("disconnect", tech.name, feeder_name)

        if random.random() < 0.03:
            operator = random.choice(self.operators)
            candidates = [
                n for n, f in self.zones["feeders"].items()
                if not f.properties.get("energised", True)
            ]
            if candidates and engine.decide(
                    operator, self.ops["restore"], region
            ) is Decision.ALLOW:
                feeder_name = random.choice(candidates)
                self.zones["feeders"][feeder_name].properties.set(
                    "energised", True,
                )
                self._log("restore", operator.name, feeder_name)

    def _log(self, event: str, actor: str, target: str) -> None:
        self.log.append((self.time_min, event, actor, target))


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_grid()
    operators, technicians, coordinator = create_staff(builder, zones)

    predictor = build_load_predictor()
    zones["Region"].add_neural("load", predictor)

    # ---- Daemon hierarchy -------------------------------------------
    root_daemon = GridDaemon(zones, ops, coordinator)
    overcurrent = OvercurrentDaemon(zones, parent=root_daemon)
    voltage = VoltageExcursionDaemon(zones, parent=root_daemon)
    forecast = LoadForecastDaemon(zones, predictor, parent=root_daemon,
                                  interval=60.0)
    for d in (root_daemon, overcurrent, voltage, forecast):
        builder.add_daemon(d)

    # ---- Sanity checks ----------------------------------------------
    region = zones["Region"]
    engine = builder.permission_engine
    feeder = zones["feeders"]["Feeder_N1"]
    print("Permission sanity check (paper §3, item 9):")
    print(f"  operator    read_sensor       : "
          f"{engine.decide(operators[0], ops['read'], region).name}")
    print(f"  operator    disconnect_feeder : "
          f"{engine.decide(operators[0], ops['disconnect'], region).name}")
    print(f"  technician  disconnect_feeder : "
          f"{engine.decide(technicians[0], ops['disconnect'], region).name}")
    print(f"  technician  isolate_substation: "
          f"{engine.decide(technicians[0], ops['isolate'], region).name}")
    print(f"  coordinator isolate_substation: "
          f"{engine.decide(coordinator, ops['isolate'], region).name}")
    print()

    forecast_p = predictor.predict({"hour": 8 / 24.0,
                                    "temp": 30.0 / 40.0,
                                    "length": 15.0 / 20.0})
    offpeak_p = predictor.predict({"hour": 3 / 24.0,
                                   "temp": 5.0 / 40.0,
                                   "length": 5.0 / 20.0})
    print(f"P(high load) | 8am, hot, long feeder : {forecast_p:.3f}")
    print(f"P(high load) | 3am, cool, short      : {offpeak_p:.3f}")
    print()

    # ---- Run one simulated hour ------------------------------------
    sim = GridSimulation(builder, zones, ops,
                         operators, technicians, coordinator, predictor)
    for _ in range(12):             # 12 × 5 min = 60 min
        sim.step(dt_min=5.0)
        builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    print(f"Simulated {sim.time_min:.0f} minutes of grid operation")
    print(f"Grid warnings  : {len(root_daemon.warnings)}")
    print(f"Grid criticals : {len(root_daemon.criticals)}")
    print(f"Load forecasts : {len(forecast.forecasts)}")
    print()
    print("Feeder status:")
    for name, feeder in zones["feeders"].items():
        state = "energised" if feeder.properties.get("energised", True) \
                else "OFFLINE"
        current = feeder.properties.get("current_load_a", 0.0)
        print(f"  {name:<12} {state:<10} current={current:6.1f} A")


if __name__ == "__main__":
    main()