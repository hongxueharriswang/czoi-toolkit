"""
nhs_simulation.py — Hospital surge-handling A/B comparison.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Two scenarios run for a 48-hour window with a flu-outbreak surge
starting at hour 12:

  baseline — static RBAC. Attending physicians hold `prescribe`;
             nurses do not. No neural components, no daemons,
             no adaptive permission changes.

  czoa     — full CZOA. Senior nurses exist (trained but not yet
             authorised). When the SurgeDaemon detects that the
             recent arrival rate exceeds a threshold, the
             ClinicalDirectorDaemon grants the SeniorNurse role the
             `prescribe` permission via zone.grant(). When the surge
             subsides, the permission is revoked. A trained
             SepsisPredictor runs over active patients every 30
             simulated minutes via the SepsisDaemon.

Multiple paired runs (same arrival seed for baseline and CZOA) produce
mean and 95 % confidence interval for the improvement in wait time.
"""
from __future__ import annotations

import random
from math import sqrt
from statistics import mean, stdev

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

SEED = 41
random.seed(SEED)
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
BASELINE_ARRIVAL_RATE   = 50.0      # patients / hour
SURGE_ARRIVAL_RATE      = 200.0     # patients / hour
SURGE_START_HOUR        = 12
SIM_HOURS               = 48
N_RUNS                  = 3

SURGE_TRIGGER_RATE      = 100.0     # rolling arrivals/hour to declare surge
SURGE_DEESCALATE_RATE   = 60.0
SURGE_WINDOW_HOURS      = 1.0

TREATMENT_MEAN_MINUTES  = 30.0      # exp. dwell once prescribed
SEPSIS_SWEEP_MINUTES    = 30
SEPSIS_ALERT_THRESHOLD  = 0.85


# =====================================================================
# 1. Build the hospital
# =====================================================================
def build_hospital():
    """Construct zones, roles, operations, and the SoD constraint."""
    builder = CZOABuilder("HealthAuthority")

    er = builder.add_zone("EmergencyRoom", parent=builder.root, atomic=True)

    app = Application("EMR", zone=er)
    view      = app.add_operation(Operation("view_patient"))
    prescribe = app.add_operation(Operation("prescribe"))
    er.add_application(app)

    # All three roles exist in CZOA mode. In baseline mode only Nurse
    # and Attending are actually created as users.
    nurse_role = Role("Nurse",        zone=er, base_permissions=[view])
    senior_role = Role("SeniorNurse", zone=er, base_permissions=[view])
    attending_role = Role("Attending", zone=er,
                          base_permissions=[view, prescribe])
    er.add_role(nurse_role)
    er.add_role(senior_role)
    er.add_role(attending_role)
    senior_role.add_junior(nurse_role)

    # UniLog separation of duty: no user holds both Nurse and Attending.
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant Nurse : Role;
            constant Attending : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . not (hasRole(u, Nurse) and hasRole(u, Attending))
    """)

    ops = {"view": view, "prescribe": prescribe}
    roles = {
        "nurse": nurse_role,
        "senior": senior_role,
        "attending": attending_role,
    }
    return builder, er, ops, roles


# =====================================================================
# 2. Register users along the containment path
# =====================================================================
def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


def create_staff(builder, er, mode: str):
    staff: list[User] = []

    for i in range(4):
        n = User(f"nurse_{i}", roles={"Nurse"},
                 attributes={"role_kind": "nurse"})
        _register_along_path(n, er)
        staff.append(n)

    # Senior nurses exist only in the CZOA arm — the organisation has
    # trained them but they are not yet authorised to prescribe.
    if mode == "czoa":
        for i in range(2):
            sn = User(f"senior_nurse_{i}", roles={"SeniorNurse"},
                      attributes={"role_kind": "senior_nurse"})
            _register_along_path(sn, er)
            staff.append(sn)

    for i in range(3):
        a = User(f"attending_{i}", roles={"Attending"},
                 attributes={"role_kind": "attending"})
        _register_along_path(a, er)
        staff.append(a)

    return staff


# =====================================================================
# 3. Neural sepsis predictor
# =====================================================================
def build_sepsis_predictor() -> Predictor:
    """Predicts P(sepsis | heart rate, temperature, lactate).

    Synthetic ground truth: high lactate combined with tachycardia
    or fever indicates sepsis. Trained on 1000 samples.
    """
    rng = np.random.default_rng(SEED)
    n = 1000
    hr      = rng.uniform(60.0, 140.0, n)
    temp    = rng.uniform(36.0, 40.5, n)
    lactate = rng.uniform(0.5, 6.0, n)

    X = np.column_stack([hr / 140.0,
                         (temp - 36.0) / 4.5,
                         lactate / 6.0])
    logits = 3.0 * (lactate / 6.0) + 2.0 * (hr / 140.0) \
           + 1.5 * ((temp - 36.0) / 4.5) - 4.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("sepsis", threshold=SEPSIS_ALERT_THRESHOLD)
    predictor.fit(X, y, epochs=1000, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class SurgeDaemon(Daemon):
    """Detects surge onset and de-escalation via a rolling arrival rate."""

    def __init__(self, sim, parent=None):
        super().__init__("SurgeDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.active = False

    def monitor(self):
        rate = self.sim.recent_arrival_rate_per_hour(SURGE_WINDOW_HOURS)
        if not self.active and rate >= SURGE_TRIGGER_RATE:
            self.active = True
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "surge_started",
                 "rate": round(rate, 1),
                 "at_hour": round(self.sim.sim_time_hours, 2)},
            )
        elif self.active and rate <= SURGE_DEESCALATE_RATE:
            self.active = False
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"event": "surge_ended",
                 "rate": round(rate, 1),
                 "at_hour": round(self.sim.sim_time_hours, 2)},
            )


class SepsisDaemon(Daemon):
    """Sweeps active patients every 30 sim-minutes for high sepsis risk."""

    def __init__(self, sim, predictor, parent=None):
        super().__init__("SepsisDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.predictor = predictor
        self.alerts: list[tuple] = []
        self._last_sweep_min = -SEPSIS_SWEEP_MINUTES

    def monitor(self):
        now_min = self.sim.sim_time_hours * 60.0
        if now_min - self._last_sweep_min < SEPSIS_SWEEP_MINUTES:
            return
        self._last_sweep_min = now_min

        for p in list(self.sim.active_patients):
            v = p["vitals"]
            risk = self.predictor.predict({
                "hr":      v["hr"] / 140.0,
                "temp":    (v["temp"] - 36.0) / 4.5,
                "lactate": v["lactate"] / 6.0,
            })
            if risk >= SEPSIS_ALERT_THRESHOLD:
                self.alerts.append(
                    (round(self.sim.sim_time_hours, 2),
                     p["pid"], round(risk, 3)),
                )
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"pid": p["pid"], "risk": round(risk, 3)},
                )


class ClinicalDirectorDaemon(Daemon):
    """Root daemon — reacts to surge signals by adjusting permissions."""

    def __init__(self, sim, er, ops, roles, parent=None):
        super().__init__("ClinicalDirector", parent=parent, interval=1.0)
        self.sim = sim
        self.er = er
        self.ops = ops
        self.roles = roles
        self.surge_active = False
        self.events: list[tuple] = []
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        event = payload.get("event")

        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))

        if event == "surge_started" and not self.surge_active:
            self.surge_active = True
            self.er.grant(self.roles["senior"], self.ops["prescribe"])
            self.events.append(
                ("grant_prescribe", round(self.sim.sim_time_hours, 2)),
            )
        elif event == "surge_ended" and self.surge_active:
            self.surge_active = False
            self.er.revoke(self.roles["senior"], self.ops["prescribe"])
            self.events.append(
                ("revoke_prescribe", round(self.sim.sim_time_hours, 2)),
            )


# =====================================================================
# 5. Simulation
# =====================================================================
class HealthcareSimulation:
    """Patient-flow simulation with real CZOI permission checks.

    Each simulated minute:
      1. Patients arrive with Poisson probability (rate depends on surge).
      2. Untriaged patients request triage (Nurse → view_patient).
      3. Triaged patients request a prescription
         (Attending, or SeniorNurse during CZOA surge → prescribe).
      4. Prescribed patients are treated by the prescriber, who is
         busy for an exponentially-distributed dwell time.
      5. Discharged patients record their end-to-end wait.
    """

    def __init__(self, builder, er, ops, staff, mode, sepsis_predictor=None):
        self.builder = builder
        self.er = er
        self.ops = ops
        self.staff = staff
        self.mode = mode
        self.sepsis_predictor = sepsis_predictor

        self.sim_time_hours = 0.0
        self.patient_counter = 0
        self.active_patients: list[dict] = []
        self.discharged: list[dict] = []
        self.wait_times: list[float] = []      # minutes
        self.arrivals_log: list[float] = []    # arrival times (hours)
        self.logs: list[tuple] = []

        self.nurses         = [s for s in staff
                               if s.attributes.get("role_kind") == "nurse"]
        self.senior_nurses  = [s for s in staff
                               if s.attributes.get("role_kind") == "senior_nurse"]
        self.attendings     = [s for s in staff
                               if s.attributes.get("role_kind") == "attending"]

        self._nurse_cursor = 0

    # -----------------------------------------------------------------
    def recent_arrival_rate_per_hour(self, window_hours: float = 1.0) -> float:
        cutoff = self.sim_time_hours - window_hours
        recent = sum(1 for t in self.arrivals_log if t >= cutoff)
        return recent / window_hours

    # -----------------------------------------------------------------
    def _next_nurse(self) -> User | None:
        if not self.nurses:
            return None
        n = self.nurses[self._nurse_cursor % len(self.nurses)]
        self._nurse_cursor += 1
        return n

    # -----------------------------------------------------------------
    def _find_free_prescriber(self) -> User | None:
        """Least-recently-used prescriber whose busy_until has passed."""
        engine = self.builder.permission_engine
        now_min = self.sim_time_hours * 60.0
        pool = self.attendings + self.senior_nurses
        for p in pool:
            if p.attributes.get("busy_until", 0.0) > now_min:
                continue
            if engine.decide(p, self.ops["prescribe"], self.er) \
                    is not Decision.ALLOW:
                continue
            return p
        return None

    # -----------------------------------------------------------------
    def step(self, dt_hours: float = 1.0 / 60.0) -> None:
        self.sim_time_hours += dt_hours

        # ---- Patient arrivals -------------------------------------
        rate = SURGE_ARRIVAL_RATE if self.sim_time_hours >= SURGE_START_HOUR \
            else BASELINE_ARRIVAL_RATE
        if random.random() < rate * dt_hours:
            self.patient_counter += 1
            self.active_patients.append({
                "pid": self.patient_counter,
                "arrived_at": self.sim_time_hours,
                "stage": "waiting",
                "stage_since": self.sim_time_hours,
                "treatment_dwell_hours": 0.0,
                "vitals": {
                    "hr":      random.uniform(60.0, 140.0),
                    "temp":    random.uniform(36.0, 40.5),
                    "lactate": random.uniform(0.5, 6.0),
                },
            })
            self.arrivals_log.append(self.sim_time_hours)
            self._log("arrival", self.patient_counter)

        # ---- Advance each patient ---------------------------------
        engine = self.builder.permission_engine
        for p in list(self.active_patients):
            stage = p["stage"]

            if stage == "waiting":
                nurse = self._next_nurse()
                if nurse and engine.decide(nurse, self.ops["view"], self.er) \
                        is Decision.ALLOW:
                    p["stage"] = "triaged"
                    p["stage_since"] = self.sim_time_hours
                    self._log("triage", p["pid"])

            elif stage == "triaged":
                prescriber = self._find_free_prescriber()
                if prescriber is not None:
                    dwell = random.expovariate(1.0 / TREATMENT_MEAN_MINUTES)
                    prescriber.attributes.set(
                        "busy_until",
                        self.sim_time_hours * 60.0 + dwell,
                    )
                    p["stage"] = "in_treatment"
                    p["stage_since"] = self.sim_time_hours
                    p["treatment_dwell_hours"] = dwell / 60.0
                    p["prescriber"] = prescriber.name
                    self._log("prescribe", p["pid"], prescriber.name)

            elif stage == "in_treatment":
                if self.sim_time_hours - p["stage_since"] \
                        >= p["treatment_dwell_hours"]:
                    wait_min = (self.sim_time_hours - p["arrived_at"]) * 60.0
                    self.wait_times.append(wait_min)
                    self.discharged.append(p)
                    self.active_patients.remove(p)
                    self._log("discharge", p["pid"], round(wait_min, 1))

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.sim_time_hours, 2), event) + tuple(args))


# =====================================================================
# 6. Scenario runner
# =====================================================================
def run_scenario(mode: str, seed: int) -> dict:
    """Run one scenario. `seed` is reset so baseline and CZOA see the
    same arrival sequence when called with the same value."""
    random.seed(seed)
    np.random.seed(seed)

    builder, er, ops, roles = build_hospital()
    staff = create_staff(builder, er, mode)

    sepsis_predictor = build_sepsis_predictor() if mode == "czoa" else None
    if mode == "czoa":
        er.add_neural("sepsis", sepsis_predictor)

    sim = HealthcareSimulation(
        builder, er, ops, staff, mode, sepsis_predictor,
    )

    # ---- Daemon hierarchy (CZOA mode only) -------------------------
    director = surge = sepsis = None
    if mode == "czoa":
        director = ClinicalDirectorDaemon(sim, er, ops, roles)
        surge = SurgeDaemon(sim, parent=director)
        sepsis = SepsisDaemon(sim, sepsis_predictor, parent=director)
        builder.add_daemon(director)
        builder.add_daemon(surge)
        builder.add_daemon(sepsis)

    # ---- Run 48 simulated hours, one tick per minute ---------------
    for minute in range(SIM_HOURS * 60):
        sim.step(dt_hours=1.0 / 60.0)
        if mode == "czoa":
            builder.daemon_manager.tick()

    # ---- Metrics ---------------------------------------------------
    avg_wait = mean(sim.wait_times) if sim.wait_times else 0.0
    return {
        "mode":             mode,
        "avg_wait_min":     avg_wait,
        "wait_times":       sim.wait_times,
        "discharged":       len(sim.discharged),
        "still_waiting":    len(sim.active_patients),
        "sepsis_alerts":    len(sepsis.alerts) if sepsis else 0,
        "surge_events":     director.events if director else [],
        "permission_stats": builder.permission_engine.stats(),
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
    builder, er, ops, roles = build_hospital()
    nurse = User("n0", roles={"Nurse"}, attributes={"role_kind": "nurse"})
    _register_along_path(nurse, er)
    sn = User("sn0", roles={"SeniorNurse"}, attributes={"role_kind": "senior_nurse"})
    _register_along_path(sn, er)
    att = User("a0", roles={"Attending"}, attributes={"role_kind": "attending"})
    _register_along_path(att, er)
    engine = builder.permission_engine

    print("Permission sanity check (paper §3, item 9):")
    print(f"  nurse        view      :",
          engine.decide(nurse, ops["view"], er).name)
    print(f"  nurse        prescribe :",
          engine.decide(nurse, ops["prescribe"], er).name)
    print(f"  senior_nurse prescribe :",
          engine.decide(sn, ops["prescribe"], er).name)
    print(f"  attending    prescribe :",
          engine.decide(att, ops["prescribe"], er).name)
    print()

    # Adaptive grant demonstration: after er.grant(senior, prescribe),
    # senior nurse can prescribe.
    er.grant(roles["senior"], ops["prescribe"])
    print("After er.grant(SeniorNurse, prescribe):")
    print(f"  senior_nurse prescribe :",
          engine.decide(sn, ops["prescribe"], er).name)
    print()

    # Neural predictor sanity check
    sepsis = build_sepsis_predictor()
    low  = sepsis.predict({"hr": 0.6, "temp": 0.2, "lactate": 0.1})
    high = sepsis.predict({"hr": 0.9, "temp": 0.8, "lactate": 0.9})
    print(f"P(sepsis) | normal vitals    : {low:.3f}")
    print(f"P(sepsis) | septic vitals    : {high:.3f}")
    print()

    # ---- Paired runs -----------------------------------------------
    baseline_waits, czoa_waits = [], []
    baseline_discharged, czoa_discharged = [], []
    total_sepsis_alerts = 0

    print("=" * 68)
    print(f"Running {N_RUNS} paired simulations of {SIM_HOURS} h each")
    print("=" * 68)
    for run in range(N_RUNS):
        seed = SEED + run
        b = run_scenario("baseline", seed)
        c = run_scenario("czoa", seed)

        baseline_waits.append(b["avg_wait_min"])
        czoa_waits.append(c["avg_wait_min"])
        baseline_discharged.append(b["discharged"])
        czoa_discharged.append(c["discharged"])
        total_sepsis_alerts += c["sepsis_alerts"]

        print(f"  Run {run + 1}: baseline "
              f"wait={b['avg_wait_min']:.1f} min, "
              f"discharged={b['discharged']};  "
              f"czoa wait={c['avg_wait_min']:.1f} min, "
              f"discharged={c['discharged']}, "
              f"sepsis_alerts={c['sepsis_alerts']}")

    bm, bci = _ci95(baseline_waits)
    cm, cci = _ci95(czoa_waits)
    improvement_pct = (bm - cm) / bm * 100.0 if bm else 0.0

    print()
    print("=" * 68)
    print("Summary")
    print("=" * 68)
    print(f"{'Scenario':<12} {'Avg wait (min)':>16} {'95 % CI':>16} "
          f"{'Discharged':>12}")
    print("-" * 60)
    print(f"{'baseline':<12} {bm:>16.2f} {bci:>16.2f} "
          f"{mean(baseline_discharged):>12.1f}")
    print(f"{'czoa':<12} {cm:>16.2f} {cci:>16.2f} "
          f"{mean(czoa_discharged):>12.1f}")
    print()
    print(f"Wait-time improvement: {improvement_pct:.1f} %")
    print(f"Total sepsis alerts across all CZOA runs: {total_sepsis_alerts}")

    # Show surge events from the last CZOA run
    print()
    print("Surge events (last CZOA run):")
    for event, hour in c["surge_events"]:
        print(f"  {event:<20} at hour {hour:.2f}")


if __name__ == "__main__":
    main()