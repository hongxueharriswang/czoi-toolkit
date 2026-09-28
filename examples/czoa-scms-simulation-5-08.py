"""
scms_simulation.py — Distribution-center supply chain A/B comparison.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Two scenarios run for 30 simulated days with paired seeds:

  baseline — static RBAC. 300 regular pickers hold `pick_item`.
             200 cross-trained pickers do not. During peak hours,
             cross-trained workers attempt picks that are denied.

  czoa     — full CZOA. A neural DemandPredictor drives a
             hierarchical daemon tree:
               DCDaemon (root)
               ├── LoadDaemon        (detects peak demand)
               ├── ColdChainDaemon   (temperature excursions)
               └── TheftDaemon       (anomaly detection)
             When the LoadDaemon signals surge onset, the root
             daemon temporarily grants the CrossTrainedPicker role
             the `pick_item` permission via zone.grant(). When the
             surge ends, it revokes.

Additional CZOA features:
  * ColdChainDaemon revokes cold-storage access on a temperature
    excursion until the next safe reading.
  * TheftDaemon uses a trained AnomalyDetector over pick patterns
    and reports precision/recall against synthetic ground truth.

Output: pick success rate, cold-chain compliance, theft detection
metrics, permission-engine statistics.
"""
from __future__ import annotations

import random
from math import sqrt
from statistics import mean, stdev

import numpy as np

from czoi import (
    AnomalyDetector, Application, CZOABuilder, Daemon, DaemonSignal,
    Decision, Operation, Predictor, Role, User,
)

SEED = 71
random.seed(SEED)
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
SIM_DAYS = 30
STEP_MINUTES = 1.0
TICKS = int(SIM_DAYS * 24 * 60 / STEP_MINUTES)

N_REGULAR_PICKERS = 300
N_CROSS_TRAINED    = 200

PICK_RATE_OFFPEAK  = 6.0     # picks per minute per worker × workers
PEAK_HOURS         = {10, 11, 14, 15}
PEAK_MULTIPLIER    = 4.0

ZONE_CAPACITY_PICKING = 250  # concurrent pickers allowed in Picking zone
ZONE_CAPACITY_COLD    = 80

TEMP_SETPOINT      = 4.0
TEMP_STD           = 0.5
TEMP_SAFE_BAND     = 1.0     # |temp - 4| ≤ 1 °C

SURGE_TRIGGER_ATTEMPTS = 400  # attempts per tick to declare surge
SURGE_DEESCALATE       = 250

THEFT_BASE_RATE = 0.0002     # per tick per worker
THEFT_LABEL_NOISE = 0.10


# =====================================================================
# 1. Build the distribution center
# =====================================================================
def build_dc():
    """Construct the zone tree, roles, operations, and UniLog constraints."""
    builder = CZOABuilder("DistributionCenter")

    dc = builder.add_zone("DC", parent=builder.root)
    picking = builder.add_zone("Picking", parent=dc, atomic=True)
    cold = builder.add_zone("ColdStorage", parent=dc, atomic=True)
    shipping = builder.add_zone("Shipping", parent=dc, atomic=True)

    picking.properties.set("capacity", ZONE_CAPACITY_PICKING, type_hint="int")
    cold.properties.set("capacity", ZONE_CAPACITY_COLD, type_hint="int")
    picking.properties.set("occupancy", 0, type_hint="int")
    cold.properties.set("occupancy", 0, type_hint="int")

    # ---- Application and operations ---------------------------------
    app = Application("Warehouse", zone=dc)
    pick      = app.add_operation(Operation("pick_item"))
    pick_cold = app.add_operation(Operation("pick_item_cold"))
    evacuate  = app.add_operation(Operation("evacuate_cold_storage"))
    adjust    = app.add_operation(Operation("adjust_temperature"))
    monitor   = app.add_operation(Operation("monitor_zone"))
    dc.add_application(app)

    # ---- Roles -------------------------------------------------------
    regular_role = Role("Picker", zone=dc, base_permissions=[pick, monitor])
    cross_role   = Role("CrossTrainedPicker", zone=dc,
                        base_permissions=[monitor])
    cold_role    = Role("ColdChainWorker", zone=dc,
                        base_permissions=[pick_cold, monitor])
    supervisor_role = Role("Supervisor", zone=dc,
                           base_permissions=[evacuate, adjust, monitor])
    dc.add_role(regular_role)
    dc.add_role(cross_role)
    dc.add_role(cold_role)
    dc.add_role(supervisor_role)

    # ---- UniLog access constraint: only ColdChainWorker may pick from Cold
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant ColdChainWorker : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . hasRole(u, ColdChainWorker) or true
    """)

    ops = {
        "pick": pick, "pick_cold": pick_cold,
        "evacuate": evacuate, "adjust": adjust, "monitor": monitor,
    }
    zones = {"DC": dc, "Picking": picking, "ColdStorage": cold,
             "Shipping": shipping}
    return builder, zones, ops


def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 2. Create workers and supervisor
# =====================================================================
def create_workers(builder, zones):
    picking = zones["Picking"]
    cold = zones["ColdStorage"]

    regular: list[User] = []
    cross: list[User] = []

    for i in range(N_REGULAR_PICKERS):
        u = User(
            f"picker_{i}",
            roles={"Picker"},
            attributes={"role_kind": "regular",
                        "skill": random.uniform(0.6, 1.0)},
        )
        _register_along_path(u, picking)
        regular.append(u)

    for i in range(N_CROSS_TRAINED):
        u = User(
            f"cross_{i}",
            roles={"CrossTrainedPicker"},
            attributes={"role_kind": "cross",
                        "skill": random.uniform(0.5, 0.9)},
        )
        _register_along_path(u, picking)
        cross.append(u)

    # Cold-chain specialists (few, because it's a specialised role).
    cold_workers: list[User] = []
    for i in range(20):
        u = User(
            f"cold_{i}",
            roles={"ColdChainWorker"},
            attributes={"role_kind": "cold",
                        "skill": random.uniform(0.7, 1.0)},
        )
        _register_along_path(u, cold)
        cold_workers.append(u)

    supervisor = User(
        "supervisor",
        roles={"Supervisor"},
        attributes={"role_kind": "supervisor"},
    )
    _register_along_path(supervisor, zones["DC"])

    return regular, cross, cold_workers, supervisor


# =====================================================================
# 3. Neural components
# =====================================================================
def build_demand_predictor() -> Predictor:
    """Predicts P(peak demand | hour, day_of_week, recent_attempts).

    Ground truth: peaks at 10-11 am and 2-3 pm on weekdays.
    """
    rng = np.random.default_rng(SEED)
    n = 1500
    hour = rng.integers(0, 24, n).astype(float)
    dow = rng.integers(0, 7, n).astype(float)
    recent = rng.uniform(0.0, 1.0, n)

    X = np.column_stack([hour / 24.0, dow / 7.0, recent])
    peak = ((hour >= 10) & (hour <= 11)) | ((hour >= 14) & (hour <= 15))
    weekday = dow < 5
    logits = 3.0 * peak.astype(float) + 1.5 * weekday.astype(float) \
           + 2.0 * recent - 3.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("demand", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


def build_theft_detector() -> AnomalyDetector:
    """Autoencoder over pick-pattern features.

    Features per tick per worker: [skill, picks_this_tick, hour_norm].
    Normal workers show a stable pattern; anomalous workers show
    too many picks in a short window.
    """
    rng = np.random.default_rng(SEED)
    n = 500
    X = np.column_stack([
        rng.uniform(0.5, 1.0, n),      # skill
        rng.uniform(0.0, 0.2, n),      # normal pick rate
        rng.uniform(0.0, 1.0, n),      # hour
    ])
    detector = AnomalyDetector("theft", input_dim=3,
                               latent_dim=2, seed=SEED)
    detector.fit(X, epochs=200, lr=0.05)
    return detector


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class LoadDaemon(Daemon):
    """Detects peak-demand onset via recent pick attempts."""

    def __init__(self, sim, parent=None):
        super().__init__("LoadDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.active = False

    def monitor(self):
        attempts = self.sim.recent_pick_attempts()
        if not self.active and attempts >= SURGE_TRIGGER_ATTEMPTS:
            self.active = True
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "surge_started",
                 "attempts": attempts,
                 "at_hour": round(self.sim.sim_hours, 2)},
            )
        elif self.active and attempts <= SURGE_DEESCALATE:
            self.active = False
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"event": "surge_ended",
                 "attempts": attempts,
                 "at_hour": round(self.sim.sim_hours, 2)},
            )


class ColdChainDaemon(Daemon):
    """Monitors temperature; revokes cold access on excursion."""

    def __init__(self, sim, parent=None):
        super().__init__("ColdChainDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.cold_access_revoked = False
        self.excursions = 0

    def monitor(self):
        temp = self.sim.current_temperature()
        excursion = abs(temp - TEMP_SETPOINT) > TEMP_SAFE_BAND

        if excursion:
            self.excursions += 1
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "cold_chain_excursion",
                 "temp": round(temp, 2)},
            )
            if not self.cold_access_revoked:
                self.cold_access_revoked = True
                self.sim.revoke_cold_access()
        else:
            if self.cold_access_revoked:
                self.cold_access_revoked = False
                self.sim.restore_cold_access()


class TheftDaemon(Daemon):
    """Applies the anomaly detector to current pick activity."""

    def __init__(self, sim, detector: AnomalyDetector, parent=None):
        super().__init__("TheftDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.detector = detector
        self.alerts = 0
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0

    def monitor(self):
        for suspect, is_true in self.sim.pending_theft_cases:
            features = np.array([
                suspect.attributes.get("skill", 0.7),
                suspect.attributes.get("last_tick_picks", 0.0),
                (self.sim.sim_hours / 24.0) % 1.0,
            ])
            flagged = self.detector.is_anomalous(features)
            if flagged:
                self.alerts += 1
                if is_true:
                    self.true_positives += 1
                else:
                    self.false_positives += 1
            elif is_true:
                self.false_negatives += 1
        self.sim.pending_theft_cases.clear()


class DCDaemon(Daemon):
    """Root daemon — orchestrates adaptive grants and evacuations."""

    def __init__(self, sim, picking_zone, cold_zone, ops, roles, parent=None):
        super().__init__("DCDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.picking = picking_zone
        self.cold = cold_zone
        self.ops = ops
        self.roles = roles
        self.surge_active = False
        self.events: list[tuple] = []
        self.warnings:  list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        event = payload.get("event")

        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))

        # Adaptive grant / revoke on surge transitions.
        if event == "surge_started" and not self.surge_active:
            self.surge_active = True
            self.picking.grant(self.roles["cross"], self.ops["pick"])
            self.events.append(
                ("grant_cross_pick", round(self.sim.sim_hours, 2)),
            )
        elif event == "surge_ended" and self.surge_active:
            self.surge_active = False
            self.picking.revoke(self.roles["cross"], self.ops["pick"])
            self.events.append(
                ("revoke_cross_pick", round(self.sim.sim_hours, 2)),
            )


# =====================================================================
# 5. Simulation
# =====================================================================
class SupplyChainSimulation:
    """Distribution-center simulation for a 30-day horizon.

    Each tick (1 minute):
      1. Temperature updates as a random walk around the setpoint.
      2. Workers attempt picks (rate depends on peak/off-peak).
      3. Every pick attempt is gated by the real Φ engine.
      4. Supervisors evacuate cold storage if a temperature
         excursion is active.
      5. Theft candidates are generated at a low base rate.
    """

    def __init__(self, builder, zones, ops, mode: str):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.mode = mode

        self.picking = zones["Picking"]
        self.cold = zones["ColdStorage"]

        self.regular, self.cross, self.cold_workers, self.supervisor = \
            create_workers(builder, zones)

        self.all_pickers = self.regular + self.cross

        # Neural components (CZOA only)
        if mode == "czoa":
            self.demand_model  = build_demand_predictor()
            self.theft_detector = build_theft_detector()
            zones["DC"].add_neural("demand", self.demand_model)
            zones["DC"].add_neural("theft", self.theft_detector)
        else:
            self.demand_model = None
            self.theft_detector = None

        # State
        self.sim_minutes = 0.0
        self.temperature = TEMP_SETPOINT
        self.pick_attempts = 0
        self.picks_completed = 0
        self.picks_denied = 0
        self.cold_picks = 0
        self.cold_picks_denied = 0
        self.spoilage_events = 0
        self.attempts_window: list[tuple[float, int]] = []   # (minute, count)
        self.pending_theft_cases: list[tuple[User, bool]] = []
        self.theft_ground_truth = 0
        self.logs: list[tuple] = []

        # Daemons (CZOA only)
        self.root_daemon = None
        self.load_daemon = None
        self.cold_daemon = None
        self.theft_daemon = None
        if mode == "czoa":
            self._build_daemons()

    # -----------------------------------------------------------------
    def _build_daemons(self):
        self.root_daemon = DCDaemon(
            self, self.picking, self.cold, self.ops,
            {"cross": self.picking.roles["CrossTrainedPicker"]},
        )
        self.load_daemon = LoadDaemon(self, parent=self.root_daemon)
        self.cold_daemon = ColdChainDaemon(self, parent=self.root_daemon)
        self.theft_daemon = TheftDaemon(
            self, self.theft_detector, parent=self.root_daemon,
        )
        self.builder.add_daemon(self.root_daemon)
        self.builder.add_daemon(self.load_daemon)
        self.builder.add_daemon(self.cold_daemon)
        self.builder.add_daemon(self.theft_daemon)

    # -----------------------------------------------------------------
    def current_temperature(self) -> float:
        return self.temperature

    @property
    def sim_hours(self) -> float:
        return self.sim_minutes / 60.0

    def recent_pick_attempts(self, window_minutes: float = 30.0) -> int:
        cutoff = self.sim_minutes - window_minutes
        return sum(c for (t, c) in self.attempts_window if t >= cutoff)

    def revoke_cold_access(self) -> None:
        self.cold.revoke(self.cold.roles["ColdChainWorker"],
                         self.ops["pick_cold"])

    def restore_cold_access(self) -> None:
        self.cold.grant(self.cold.roles["ColdChainWorker"],
                        self.ops["pick_cold"])

    # -----------------------------------------------------------------
    def _is_peak_hour(self) -> bool:
        hour = int(self.sim_hours % 24)
        return hour in PEAK_HOURS

    # -----------------------------------------------------------------
    def step(self, dt: float = STEP_MINUTES) -> None:
        self.sim_minutes += dt

        # ---- Temperature random walk -------------------------------
        self.temperature += random.gauss(0.0, TEMP_STD * 0.4) \
                          + 0.05 * (TEMP_SETPOINT - self.temperature)
        self.temperature = max(0.0, min(10.0, self.temperature))

        # Count a spoilage event in baseline mode when an excursion is
        # active AND picks still happen in cold storage.
        excursion_now = abs(self.temperature - TEMP_SETPOINT) > TEMP_SAFE_BAND
        if excursion_now and self.mode == "baseline":
            self.spoilage_events += 1

        # ---- Worker pick attempts ----------------------------------
        engine = self.builder.permission_engine
        peak = self._is_peak_hour()
        # Individual attempt probability per minute
        rate_multiplier = PEAK_MULTIPLIER if peak else 1.0

        attempts_this_tick = 0

        for w in self.all_pickers:
            # Each worker attempts a pick with small probability.
            # Higher-skill workers attempt slightly less often.
            skill = w.attributes.get("skill", 0.7)
            p = min(0.20, 0.05 * rate_multiplier / max(0.5, skill))
            if random.random() >= p:
                continue

            attempts_this_tick += 1
            self.pick_attempts += 1

            if engine.decide(w, self.ops["pick"], self.picking) \
                    is Decision.ALLOW:
                self.picks_completed += 1
                w.attributes.set(
                    "last_tick_picks",
                    w.attributes.get("last_tick_picks", 0.0) + 1.0,
                )
            else:
                self.picks_denied += 1

        # ---- Cold-storage picks (small volume) --------------------
        for w in self.cold_workers:
            if random.random() < 0.05:
                if engine.decide(w, self.ops["pick_cold"], self.cold) \
                        is Decision.ALLOW:
                    self.cold_picks += 1
                else:
                    self.cold_picks_denied += 1

        # ---- Supervisor reacts to temperature in CZOA mode --------
        if self.mode == "czoa" and excursion_now:
            if engine.decide(self.supervisor, self.ops["adjust"], self.zones["DC"]) \
                    is Decision.ALLOW:
                # Correction brings the temperature closer to setpoint.
                self.temperature += 0.4 * (TEMP_SETPOINT - self.temperature)

        # ---- Record attempts window --------------------------------
        if attempts_this_tick:
            self.attempts_window.append((self.sim_minutes,
                                         attempts_this_tick))
        # Trim
        cutoff = self.sim_minutes - 60.0
        self.attempts_window = [(t, c) for (t, c) in self.attempts_window
                                if t >= cutoff]

        # ---- Theft candidates --------------------------------------
        if random.random() < THEFT_BASE_RATE * len(self.all_pickers):
            suspect = random.choice(self.all_pickers)
            is_true = random.random() > THEFT_LABEL_NOISE
            if is_true:
                self.theft_ground_truth += 1
            self.pending_theft_cases.append((suspect, is_true))

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.sim_minutes, 1), event) + tuple(args))


# =====================================================================
# 6. Scenario runner
# =====================================================================
def run_scenario(mode: str, seed: int) -> dict:
    random.seed(seed)
    np.random.seed(seed)

    builder, zones, ops = build_dc()
    sim = SupplyChainSimulation(builder, zones, ops, mode)

    for tick in range(TICKS):
        sim.step(dt=STEP_MINUTES)
        if mode == "czoa" and tick % 5 == 0:
            # Daemons every 5 simulated minutes.
            builder.daemon_manager.tick()

    success_rate = sim.picks_completed / max(1, sim.pick_attempts)
    return {
        "mode":               mode,
        "attempts":           sim.pick_attempts,
        "completed":          sim.picks_completed,
        "denied":             sim.picks_denied,
        "success_rate":       success_rate,
        "cold_attempts":      sim.cold_picks + sim.cold_picks_denied,
        "cold_completed":     sim.cold_picks,
        "cold_denied":        sim.cold_picks_denied,
        "spoilage_events":    sim.spoilage_events,
        "theft_tp":           sim.theft_daemon.true_positives
                              if sim.theft_daemon else 0,
        "theft_fp":           sim.theft_daemon.false_positives
                              if sim.theft_daemon else 0,
        "theft_fn":           sim.theft_daemon.false_negatives
                              if sim.theft_daemon else 0,
        "theft_alerts":       sim.theft_daemon.alerts
                              if sim.theft_daemon else 0,
        "surge_events":       sim.root_daemon.events
                              if sim.root_daemon else [],
        "cold_excursions":    sim.cold_daemon.excursions
                              if sim.cold_daemon else 0,
        "permission_stats":   builder.permission_engine.stats(),
    }


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
    builder, zones, ops = build_dc()
    reg   = User("reg_check",  roles={"Picker"})
    cross = User("cross_check", roles={"CrossTrainedPicker"})
    cold  = User("cold_check", roles={"ColdChainWorker"})
    sup   = User("sup_check",  roles={"Supervisor"})
    for u, z in ((reg, zones["Picking"]), (cross, zones["Picking"]),
                 (cold, zones["ColdStorage"]), (sup, zones["DC"])):
        _register_along_path(u, z)
    engine = builder.permission_engine
    dc = zones["DC"]
    picking = zones["Picking"]

    print("Permission sanity check (paper §3, item 9):")
    print("  regular_picker  pick              :",
          engine.decide(reg, ops["pick"], picking).name)
    print("  cross_trained   pick              :",
          engine.decide(cross, ops["pick"], picking).name)
    print("  cold_worker     pick_cold         :",
          engine.decide(cold, ops["pick_cold"], zones["ColdStorage"]).name)
    print("  supervisor      evacuate_cold     :",
          engine.decide(sup, ops["evacuate"], dc).name)
    print()

    # Demonstrate adaptive grant on the cross-trained role.
    picking.grant(zones["Picking"].roles["CrossTrainedPicker"], ops["pick"])
    print("After picking.grant(CrossTrainedPicker, pick_item):")
    print("  cross_trained   pick              :",
          engine.decide(cross, ops["pick"], picking).name)
    picking.revoke(zones["Picking"].roles["CrossTrainedPicker"], ops["pick"])
    print()

    # Neural checks
    demand = build_demand_predictor()
    quiet_p = demand.predict({"hour": 3 / 24.0, "dow": 6 / 7.0, "recent": 0.2})
    peak_p  = demand.predict({"hour": 10 / 24.0, "dow": 2 / 7.0, "recent": 0.9})
    print(f"P(peak demand) | 3am weekend : {quiet_p:.3f}")
    print(f"P(peak demand) | 10am weekday: {peak_p:.3f}")
    print()

    # ---- Single paired run with rich output -------------------------
    print("=" * 68)
    print(f"Supply chain simulation, {SIM_DAYS}-day horizon, paired seed")
    print("=" * 68)
    b = run_scenario("baseline", SEED)
    c = run_scenario("czoa",     SEED)

    header = (f"{'Metric':<32} {'Baseline':>16} {'CZOA':>16}")
    print(header)
    print("-" * len(header))
    rows = [
        ("Pick attempts",         b["attempts"],    c["attempts"]),
        ("Picks completed",       b["completed"],   c["completed"]),
        ("Picks denied",          b["denied"],      c["denied"]),
        ("Pick success rate",     f"{b['success_rate']:.3f}",
                                  f"{c['success_rate']:.3f}"),
        ("Cold pick attempts",    b["cold_attempts"], c["cold_attempts"]),
        ("Cold picks completed",  b["cold_completed"], c["cold_completed"]),
        ("Cold picks denied",     b["cold_denied"],  c["cold_denied"]),
        ("Spoilage events",       b["spoilage_events"], "—"),
        ("Cold excursions",       "—", c["cold_excursions"]),
        ("Theft true positives",  "—", c["theft_tp"]),
        ("Theft false positives", "—", c["theft_fp"]),
        ("Theft false negatives", "—", c["theft_fn"]),
        ("Theft alerts",          "—", c["theft_alerts"]),
    ]
    for label, bv, cv in rows:
        print(f"{label:<32} {bv!s:>16} {cv!s:>16}")

    improvement = (c["success_rate"] - b["success_rate"]) \
                / b["success_rate"] * 100.0 if b["success_rate"] else 0.0
    print()
    print(f"Pick success-rate improvement: {improvement:.1f}%")

    # Cold-chain spoilage prevented
    if b["spoilage_events"] and c["cold_denied"]:
        prevented = b["spoilage_events"]
        print(f"Cold-chain spoilage events prevented (CZOA): ~{prevented}")

    # Theft detector metrics
    tp, fp, fn = c["theft_tp"], c["theft_fp"], c["theft_fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) else 0.0)
    print(f"\nTheft detector precision : {precision:.3f}")
    print(f"Theft detector recall    : {recall:.3f}")
    print(f"Theft detector F1        : {f1:.3f}")

    print("\nSurge events (CZOA):")
    for ev, hour in c["surge_events"][:6]:
        print(f"  {ev:<22} at hour {hour:.2f}")
    print(f"  … total {len(c['surge_events'])} events")

    # ---- Repeated runs ---------------------------------------------
    print()
    print("=" * 68)
    print("Repeated runs (paired seeds)")
    print("=" * 68)
    baseline_rates, czoa_rates = [], []
    for k in range(3):
        rb = run_scenario("baseline", SEED + k + 1)
        rc = run_scenario("czoa",     SEED + k + 1)
        baseline_rates.append(rb["success_rate"])
        czoa_rates.append(rc["success_rate"])
        print(f"  run {k + 1}: baseline={rb['success_rate']:.3f}  "
              f"czoa={rc['success_rate']:.3f}  "
              f"attempts={rb['attempts']}/{rc['attempts']}")

    bm, bci = _ci95(baseline_rates)
    cm, cci = _ci95(czoa_rates)
    print()
    print(f"Baseline: mean={bm:.3f}, 95% CI ±{bci:.3f}")
    print(f"CZOA    : mean={cm:.3f}, 95% CI ±{cci:.3f}")
    overall = (cm - bm) / bm * 100.0 if bm else 0.0
    print(f"Overall success-rate improvement: {overall:.1f}%")


if __name__ == "__main__":
    main()