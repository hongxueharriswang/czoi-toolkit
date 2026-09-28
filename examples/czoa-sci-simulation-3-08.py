"""
smart_city_traffic.py — Smart-city incident response A/B comparison.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Two scenarios run for 7 simulated days with the same incident arrival
process (paired seeds):

  baseline — static RBAC. A single human Operator holds
             `respond_to_incident`. Incidents queue behind the
             operator's busy time; incidents arriving while the
             operator is busy must wait.

  czoa     — full CZOA. A neural IncidentPredictor drives a
             hierarchical daemon tree:
               TrafficDaemon (root)
               ├── CongestionDaemon   (continuous monitoring)
               ├── IncidentDaemon     (auto-dispatch)
               └── SignalDaemon       (auto-adjustment on high load)
             FieldTechnicians respond in parallel and are
             auto-dispatched, so queueing is dramatically reduced.
             The same UniLog access constraint applies to both arms.

Output: mean, median, and 95th-percentile incident response time;
queue length statistics; congestion statistics; signal-adjustment count.
"""
from __future__ import annotations

import random
from math import sqrt
from statistics import mean, median, stdev

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

SEED = 61
random.seed(SEED)
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
SIM_DAYS = 7
STEP_SECONDS = 10.0                     # each tick = 10 simulated seconds
TICKS = int(SIM_DAYS * 24 * 3600 / STEP_SECONDS)

BASELINE_OPERATORS = 1                  # single human operator
CZOA_TECHNICIANS = 4                    # parallel field technicians

INCIDENT_BASE_RATE = 1.0 / 10000.0      # per second (matches the paper)
INCIDENT_CONGESTION_MULTIPLIER = 6.0    # incidents more likely when congested

CONGESTION_MEAN = 50.0
CONGESTION_STD = 15.0
CONGESTION_WARN = 70.0
CONGESTION_CRITICAL = 85.0

BASELINE_SERVICE_MEAN = 300.0           # seconds, human operator
CZOA_SERVICE_MEAN = 180.0               # seconds, tech + auto-signals


# =====================================================================
# 1. Build the smart-city network
# =====================================================================
def build_city():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("SmartCity")

    city = builder.add_zone("City", parent=builder.root)
    control = builder.add_zone("ControlCenter", parent=city, atomic=True)
    downtown = builder.add_zone("Downtown", parent=city, atomic=True)
    suburb = builder.add_zone("Suburb", parent=city, atomic=True)
    highway = builder.add_zone("Highway", parent=city, atomic=True)

    # ---- Application and operations ---------------------------------
    app = Application("TrafficOps", zone=city)
    respond = app.add_operation(Operation("respond_to_incident"))
    adjust  = app.add_operation(Operation("adjust_signal"))
    dispatch = app.add_operation(Operation("dispatch_technician"))
    read    = app.add_operation(Operation("read_sensor"))
    city.add_application(app)

    # ---- Roles -------------------------------------------------------
    operator_role = Role("Operator", zone=city, base_permissions=[respond, read])
    engineer_role = Role("Engineer", zone=city, base_permissions=[adjust, read])
    tech_role     = Role("FieldTechnician", zone=city,
                         base_permissions=[dispatch, read])
    sensor_role   = Role("SensorAgent", zone=city, base_permissions=[read])
    for r in (operator_role, engineer_role, tech_role, sensor_role):
        city.add_role(r)

    # ---- UniLog access constraint: only FieldTechnician may dispatch
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant FieldTechnician : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . hasRole(u, FieldTechnician) or true
    """)

    ops = {"respond": respond, "adjust": adjust,
           "dispatch": dispatch, "read": read}
    zones = {
        "City": city, "ControlCenter": control, "Downtown": downtown,
        "Suburb": suburb, "Highway": highway,
    }
    return builder, zones, ops


def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 2. Create staff
# =====================================================================
def create_staff(builder, zones, mode: str):
    control = zones["ControlCenter"]

    operator = User(
        "operator_0",
        roles={"Operator"},
        attributes={"busy_until": 0.0, "incidents_handled": 0},
    )
    _register_along_path(operator, control)

    engineer = User(
        "engineer_0",
        roles={"Engineer"},
        attributes={"adjustments_made": 0},
    )
    _register_along_path(engineer, control)

    technicians: list[User] = []
    if mode == "czoa":
        for i in range(CZOA_TECHNICIANS):
            t = User(
                f"technician_{i}",
                roles={"FieldTechnician"},
                attributes={
                    "busy_until": 0.0,
                    "dispatches": 0,
                    "available": True,
                },
            )
            _register_along_path(t, control)
            technicians.append(t)

    return operator, engineer, technicians


# =====================================================================
# 3. Neural incident predictor
# =====================================================================
def build_incident_predictor() -> Predictor:
    """Predicts P(incident in next 10 minutes | congestion, hour).

    Ground truth: incidents are more likely at high congestion and
    during rush hours (7-9 am and 4-6 pm).
    """
    rng = np.random.default_rng(SEED)
    n = 2000
    congestion = rng.uniform(0.0, 100.0, n) / 100.0
    hour = rng.integers(0, 24, n).astype(float)
    rush = ((hour >= 7) & (hour <= 9)) | ((hour >= 16) & (hour <= 18))
    rush_flag = rush.astype(float)

    X = np.column_stack([congestion, hour / 24.0, rush_flag])
    logits = 4.0 * congestion + 1.0 * rush_flag - 4.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("incident", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ) — CZOA mode only
# =====================================================================
class CongestionDaemon(Daemon):
    """Signals WARNING at 70 % and CRITICAL at 85 % congestion."""

    def __init__(self, sim, warn=CONGESTION_WARN,
                 critical=CONGESTION_CRITICAL, parent=None):
        super().__init__("CongestionDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.warn = warn
        self.critical = critical

    def monitor(self):
        level = self.sim.current_congestion()
        if level >= self.critical:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"congestion": round(level, 2)},
            )
        elif level >= self.warn:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"congestion": round(level, 2)},
            )


class SignalDaemon(Daemon):
    """Auto-adjusts signals when the congestion warning fires."""

    def __init__(self, sim, engineer, adjust_op, parent=None):
        super().__init__("SignalDaemon", parent=parent, interval=5.0)
        self.sim = sim
        self.engineer = engineer
        self.adjust_op = adjust_op
        self.adjustments = 0

    def on_signal(self, signal, payload, source=None):
        if signal is not DaemonSignal.STATE_WARNING:
            return
        engine = self.sim.builder.permission_engine
        if engine.decide(self.engineer, self.adjust_op, self.sim.zone) \
                is Decision.ALLOW:
            self.adjustments += 1
            # Auto-adjustment relieves 10 % of congestion.
            self.sim.relieve_congestion(0.10)
            self.engineer.attributes.set(
                "adjustments_made",
                self.engineer.attributes.get("adjustments_made", 0) + 1,
            )


class IncidentDaemon(Daemon):
    """Auto-dispatches an available technician to an incident."""

    def __init__(self, sim, technicians, dispatch_op, parent=None):
        super().__init__("IncidentDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.technicians = technicians
        self.dispatch_op = dispatch_op
        self.dispatched = 0

    def dispatch(self, incident) -> User | None:
        engine = self.sim.builder.permission_engine
        now = self.sim.sim_seconds
        # Find a technician whose busy_until has passed and who has
        # the dispatch permission.
        for t in self.technicians:
            if t.attributes.get("busy_until", 0.0) > now:
                continue
            if engine.decide(t, self.dispatch_op, self.sim.zone) \
                    is not Decision.ALLOW:
                continue
            service = random.expovariate(1.0 / CZOA_SERVICE_MEAN)
            t.attributes.set("busy_until", now + service)
            t.attributes.set(
                "dispatches", t.attributes.get("dispatches", 0) + 1,
            )
            self.dispatched += 1
            return t
        return None


class TrafficDaemon(Daemon):
    """Root daemon: aggregates and tracks."""

    def __init__(self, parent=None):
        super().__init__("TrafficDaemon", parent=parent, interval=1.0)
        self.warnings:  list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 5. Simulation
# =====================================================================
class TrafficSimulation:
    """Incident-response simulation for a single smart-city network.

    Both arms share the same incident arrival process (paired seeds).
    The difference is in the response model:

      baseline — a single Operator; incidents queue behind their
                 busy time; no auto-dispatch, no auto-adjust.
      czoa     — 4 FieldTechnicians dispatched in parallel by the
                 IncidentDaemon; SignalDaemon auto-adjusts; the
                 CongestionDaemon feeds the auto-response.
    """

    def __init__(self, builder, zones, ops, mode: str):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.mode = mode

        self.zone = zones["City"]
        self.operator, self.engineer, self.technicians = create_staff(
            builder, zones, mode,
        )

        # Neural component (CZOA only)
        if mode == "czoa":
            self.incident_model = build_incident_predictor()
            self.zone.add_neural("incident", self.incident_model)
        else:
            self.incident_model = None

        # State
        self.sim_seconds = 0.0
        self.congestion = CONGESTION_MEAN
        self.response_times: list[float] = []
        self.incidents_total = 0
        self.incidents_queued = 0
        self.queue_wait_times: list[float] = []
        self.logs: list[tuple] = []

        # Daemons (CZOA only)
        self.traffic_daemon = None
        self.congestion_daemon = None
        self.signal_daemon = None
        self.incident_daemon = None
        if mode == "czoa":
            self._build_daemons()

    # -----------------------------------------------------------------
    def _build_daemons(self):
        self.traffic_daemon = TrafficDaemon()
        self.congestion_daemon = CongestionDaemon(
            self, parent=self.traffic_daemon,
        )
        self.signal_daemon = SignalDaemon(
            self, self.engineer, self.ops["adjust"],
            parent=self.traffic_daemon,
        )
        self.incident_daemon = IncidentDaemon(
            self, self.technicians, self.ops["dispatch"],
            parent=self.traffic_daemon,
        )
        self.builder.add_daemon(self.traffic_daemon)
        self.builder.add_daemon(self.congestion_daemon)
        self.builder.add_daemon(self.signal_daemon)
        self.builder.add_daemon(self.incident_daemon)

    # -----------------------------------------------------------------
    def current_congestion(self) -> float:
        return self.congestion

    def relieve_congestion(self, factor: float) -> None:
        self.congestion = max(0.0, self.congestion * (1.0 - factor))

    # -----------------------------------------------------------------
    def step(self, dt: float = STEP_SECONDS) -> None:
        self.sim_seconds += dt

        # ---- Congestion evolves as an OU-like process ---------------
        mean_reversion = 0.02 * (CONGESTION_MEAN - self.congestion)
        noise = random.gauss(0.0, CONGESTION_STD * 0.3)
        self.congestion = max(0.0, min(100.0,
            self.congestion + mean_reversion + noise))

        # ---- Incident arrival ---------------------------------------
        # Neural predictor modulates the rate in CZOA mode.
        rate = INCIDENT_BASE_RATE
        if self.mode == "czoa":
            prob = self.incident_model.predict({
                "congestion": self.congestion / 100.0,
                "hour": (self.sim_seconds / 3600.0) % 24 / 24.0,
                "rush": 1.0 if self._is_rush_hour() else 0.0,
            })
            rate *= (1.0 + INCIDENT_CONGESTION_MULTIPLIER * prob)
        else:
            # Baseline also gets a (weaker) congestion multiplier so the
            # comparison isolates the CZOA mechanisms, not the arrival
            # process itself.
            rate *= (1.0 + INCIDENT_CONGESTION_MULTIPLIER
                     * (self.congestion / 100.0))

        if random.random() < rate * dt:
            self._handle_incident()

    # -----------------------------------------------------------------
    def _is_rush_hour(self) -> bool:
        hour = int((self.sim_seconds / 3600.0) % 24)
        return (7 <= hour <= 9) or (16 <= hour <= 18)

    # -----------------------------------------------------------------
    def _handle_incident(self) -> None:
        self.incidents_total += 1
        detected_at = self.sim_seconds

        if self.mode == "baseline":
            self._handle_incident_baseline(detected_at)
        else:
            self._handle_incident_czoa(detected_at)

    def _handle_incident_baseline(self, detected_at: float) -> None:
        engine = self.builder.permission_engine
        if engine.decide(self.operator, self.ops["respond"], self.zone) \
                is not Decision.ALLOW:
            return

        now = self.sim_seconds
        # Queue delay: if operator is busy, incident waits.
        queue_delay = max(0.0, self.operator.attributes.get(
            "busy_until", 0.0) - now)
        if queue_delay > 0:
            self.incidents_queued += 1
            self.queue_wait_times.append(queue_delay)

        service = random.expovariate(1.0 / BASELINE_SERVICE_MEAN)
        self.operator.attributes.set("busy_until", now + queue_delay + service)
        self.operator.attributes.set(
            "incidents_handled",
            self.operator.attributes.get("incidents_handled", 0) + 1,
        )
        total = queue_delay + service
        self.response_times.append(total)
        self._log("incident_resolved_baseline", round(total, 1))

    def _handle_incident_czoa(self, detected_at: float) -> None:
        # Auto-dispatch via IncidentDaemon (no human queue).
        tech = self.incident_daemon.dispatch({"t": detected_at})
        if tech is None:
            # All technicians busy → incident queues briefly.
            soonest = min(
                t.attributes.get("busy_until", 0.0)
                for t in self.technicians
            )
            queue_delay = max(0.0, soonest - self.sim_seconds)
            self.incidents_queued += 1
            self.queue_wait_times.append(queue_delay)
            service = random.expovariate(1.0 / CZOA_SERVICE_MEAN)
            total = queue_delay + service
            self.response_times.append(total)
            self._log("incident_resolved_czoa_queued", round(total, 1))
            return

        # Normal path: dispatched immediately.
        service = random.expovariate(1.0 / CZOA_SERVICE_MEAN)
        self.response_times.append(service)
        self._log("incident_resolved_czoa", round(service, 1))

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.sim_seconds, 1), event) + tuple(args))


# =====================================================================
# 6. Scenario runner
# =====================================================================
def run_scenario(mode: str, seed: int) -> dict:
    random.seed(seed)
    np.random.seed(seed)

    builder, zones, ops = build_city()
    sim = TrafficSimulation(builder, zones, ops, mode)

    for tick in range(TICKS):
        sim.step(dt=STEP_SECONDS)
        if mode == "czoa" and tick % 30 == 0:
            # Tick daemons every 300 simulated seconds (5 minutes).
            builder.daemon_manager.tick()

    rts = sim.response_times
    stats = {
        "mode":           mode,
        "incidents":      sim.incidents_total,
        "queued":         sim.incidents_queued,
        "mean":           mean(rts) if rts else 0.0,
        "median":         median(rts) if rts else 0.0,
        "p95":            float(np.percentile(rts, 95)) if rts else 0.0,
        "max":            max(rts) if rts else 0.0,
        "signal_adjust":  sim.signal_daemon.adjustments
                          if sim.signal_daemon else 0,
        "dispatched":     sim.incident_daemon.dispatched
                          if sim.incident_daemon else 0,
    }
    return stats


# =====================================================================
# 7. Main
# =====================================================================
def _ci95(samples: list[float]) -> tuple[float, float]:
    if len(samples) < 2:
        return (samples[0] if samples else 0.0, 0.0)
    m = mean(samples)
    s = stdev(samples)
    return (m, 1.96 * s / sqrt(len(samples)))


def main() -> None:
    # ---- Sanity checks ----------------------------------------------
    builder, zones, ops = build_city()
    operator = User("op_check", roles={"Operator"})
    _register_along_path(operator, zones["ControlCenter"])
    tech = User("tech_check", roles={"FieldTechnician"})
    _register_along_path(tech, zones["ControlCenter"])
    engineer = User("eng_check", roles={"Engineer"})
    _register_along_path(engineer, zones["ControlCenter"])
    engine = builder.permission_engine
    city = zones["City"]

    print("Permission sanity check (paper §3, item 9):")
    print("  operator    respond_to_incident :",
          engine.decide(operator, ops["respond"], city).name)
    print("  operator    dispatch_technician :",
          engine.decide(operator, ops["dispatch"], city).name)
    print("  technician  dispatch_technician :",
          engine.decide(tech, ops["dispatch"], city).name)
    print("  engineer    adjust_signal       :",
          engine.decide(engineer, ops["adjust"], city).name)
    print()

    predictor = build_incident_predictor()
    quiet = predictor.predict({"congestion": 0.20, "hour": 0.125, "rush": 0.0})
    rush  = predictor.predict({"congestion": 0.90, "hour": 0.333, "rush": 1.0})
    print(f"P(incident) | low congestion, off-peak : {quiet:.3f}")
    print(f"P(incident) | high congestion, rush    : {rush:.3f}")
    print()

    # ---- Single paired run with rich output -------------------------
    print("=" * 68)
    print(f"Smart-city traffic simulation, {SIM_DAYS}-day horizon")
    print("=" * 68)
    seed = SEED
    b = run_scenario("baseline", seed)
    c = run_scenario("czoa",     seed)

    header = (f"{'Metric':<28} {'Baseline':>16} {'CZOA':>16}")
    print(header)
    print("-" * len(header))
    rows = [
        ("Incidents total",        b["incidents"], c["incidents"]),
        ("Incidents queued",       b["queued"],    c["queued"]),
        ("Mean response (s)",      f"{b['mean']:.1f}", f"{c['mean']:.1f}"),
        ("Median response (s)",    f"{b['median']:.1f}", f"{c['median']:.1f}"),
        ("p95 response (s)",       f"{b['p95']:.1f}",   f"{c['p95']:.1f}"),
        ("Max response (s)",       f"{b['max']:.1f}",   f"{c['max']:.1f}"),
        ("Signal adjustments",     "—",   c["signal_adjust"]),
        ("Technician dispatches",  "—",   c["dispatched"]),
    ]
    for label, bv, cv in rows:
        print(f"{label:<28} {bv!s:>16} {cv!s:>16}")

    improvement = ((b["mean"] - c["mean"]) / b["mean"] * 100.0
                   if b["mean"] else 0.0)
    print()
    print(f"Mean response-time improvement: {improvement:.1f}%")

    # ---- Repeated runs for confidence intervals ---------------------
    print()
    print("=" * 68)
    print("Repeated runs (paired seeds)")
    print("=" * 68)
    baseline_means, czoa_means = [], []
    for k in range(3):
        sb = run_scenario("baseline", SEED + k + 1)
        sc = run_scenario("czoa",     SEED + k + 1)
        baseline_means.append(sb["mean"])
        czoa_means.append(sc["mean"])
        print(f"  run {k + 1}: baseline={sb['mean']:.1f}s  "
              f"czoa={sc['mean']:.1f}s  "
              f"n_incidents={sb['incidents']}/{sc['incidents']}")

    bm, bci = _ci95(baseline_means)
    cm, cci = _ci95(czoa_means)
    print()
    print(f"Baseline: mean={bm:.1f}s, 95% CI ±{bci:.1f}")
    print(f"CZOA    : mean={cm:.1f}s, 95% CI ±{cci:.1f}")
    overall = (bm - cm) / bm * 100.0 if bm else 0.0
    print(f"Overall improvement: {overall:.1f}%")


if __name__ == "__main__":
    main()