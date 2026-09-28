"""
university_registration.py — University registration + FERPA A/B.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Two scenarios run for 3 simulated days with paired seeds:

  baseline — static RBAC. Student role has a misconfigured
             `view_any_grade` permission (the legacy policy). Every
             student attempt to view another student's grade
             succeeds and is counted as a FERPA violation.

  czoa     — full CZOA. A FERPADaemon watches for students using
             `view_any_grade`. On the first detection it calls
             `university.revoke(student_role, view_any_grade)`,
             which invalidates the permission engine cache.
             Subsequent attempts are denied by the engine.
             Additional daemons:
               UniversityDaemon (root)
               ├── FERPADaemon          real-time policy correction
               ├── RegistrationDaemon   peak-load monitoring
               └── AdvisorDaemon        at-risk student detection

A neural AtRiskPredictor drives the AdvisorDaemon sweep every
simulated hour.

Output: registration throughput, FERPA violations (before and after
correction), at-risk students flagged.
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

SEED = 89
random.seed(SEED)
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
SIM_DAYS = 3
STEP_MINUTES = 1.0
TICKS = int(SIM_DAYS * 24 * 60 / STEP_MINUTES)

N_STUDENTS  = 1000
N_PROFS     = 30
N_ADVISORS  = 10

PEAK_HOURS = {9, 10, 11, 14, 15, 16}
REGISTRATION_PROB_PER_STUDENT = 0.05      # per student per peak-minute
FERPA_ATTEMPT_PROB_PER_STUDENT = 0.0005   # per student per minute
AT_RISK_SWEEP_MINUTES = 60
AT_RISK_THRESHOLD = 0.65


# =====================================================================
# 1. Build the university
# =====================================================================
def build_university():
    """Construct the zone tree, roles, operations, and UniLog constraints."""
    builder = CZOABuilder("UniversitySystem")

    uni = builder.add_zone("University", parent=builder.root)
    coe = builder.add_zone("CollegeOfEngineering", parent=uni)
    cs  = builder.add_zone("CSDepartment", parent=coe, atomic=True)
    me  = builder.add_zone("MEDepartment", parent=coe, atomic=True)
    ee  = builder.add_zone("EEDepartment", parent=coe, atomic=True)
    registrar = builder.add_zone("Registrar", parent=uni, atomic=True)
    advising  = builder.add_zone("Advising", parent=uni, atomic=True)

    # ---- Application and atomic operations -------------------------
    app = Application("StudentServices", zone=uni)
    register    = app.add_operation(Operation("register"))
    drop        = app.add_operation(Operation("drop"))
    view_own    = app.add_operation(Operation("view_own_grade"))
    view_any    = app.add_operation(Operation("view_any_grade"))
    submit      = app.add_operation(Operation("submit_grade"))
    advise      = app.add_operation(Operation("advise"))
    uni.add_application(app)

    # ---- Roles -------------------------------------------------------
    # NOTE: The Student role intentionally carries a misconfigured
    # `view_any_grade` permission — the legacy policy. This is exactly
    # the kind of drift the FERPADaemon catches in CZOA mode.
    student_role = Role(
        "Student", zone=uni,
        base_permissions=[register, drop, view_own, view_any],
    )
    prof_role = Role(
        "Professor", zone=uni,
        base_permissions=[view_any, submit],
    )
    advisor_role = Role(
        "Advisor", zone=uni,
        base_permissions=[view_any, advise],
    )
    registrar_role = Role(
        "Registrar", zone=uni,
        base_permissions=[register, drop, view_any],
    )
    for r in (student_role, prof_role, advisor_role, registrar_role):
        uni.add_role(r)

    # ---- UniLog separation-of-duty: Student ≠ Professor ------------
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant Student : Role;
            constant Professor : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User .
            hasRole(u, Student) -> not hasRole(u, Professor)
    """)

    ops = {
        "register": register, "drop": drop,
        "view_own": view_own, "view_any": view_any,
        "submit":   submit,   "advise": advise,
    }
    zones = {
        "University": uni, "CoE": coe, "CS": cs, "ME": me, "EE": ee,
        "Registrar": registrar, "Advising": advising,
    }
    return builder, zones, ops


def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 2. Create users
# =====================================================================
def create_users(builder, zones):
    cs, me, ee = zones["CS"], zones["ME"], zones["EE"]
    departments = [cs, me, ee]

    students: list[User] = []
    for i in range(N_STUDENTS):
        dept = random.choice(departments)
        u = User(
            f"student_{i}",
            roles={"Student"},
            attributes={
                "gpa":        random.uniform(1.5, 4.0),
                "attendance": random.uniform(0.30, 1.00),
                "credits":    random.randint(3, 18),
                "at_risk":    False,
            },
        )
        _register_along_path(u, dept)
        students.append(u)

    profs: list[User] = []
    for i in range(N_PROFS):
        dept = random.choice(departments)
        u = User(f"prof_{i}", roles={"Professor"},
                 attributes={"department": dept.name})
        _register_along_path(u, dept)
        profs.append(u)

    advisors: list[User] = []
    for i in range(N_ADVISORS):
        u = User(f"advisor_{i}", roles={"Advisor"})
        _register_along_path(u, zones["Advising"])
        advisors.append(u)

    registrar = User("registrar_0", roles={"Registrar"})
    _register_along_path(registrar, zones["Registrar"])

    return students, profs, advisors, registrar


# =====================================================================
# 3. Neural at-risk predictor
# =====================================================================
def build_at_risk_predictor() -> Predictor:
    """Predicts P(at_risk | gpa, attendance, credits).

    Synthetic ground truth: low GPA, low attendance, low credits
    strongly indicate at-risk. Trained on 1 500 samples.
    """
    rng = np.random.default_rng(SEED)
    n = 1500
    gpa    = rng.uniform(1.5, 4.0, n)
    att    = rng.uniform(0.30, 1.00, n)
    cr     = rng.integers(3, 19, n).astype(float)

    X = np.column_stack([gpa / 4.0, att, cr / 18.0])
    logits = -3.0 * (gpa / 4.0) - 2.5 * att - 1.0 * (cr / 18.0) + 5.0
    probs  = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("at_risk", threshold=AT_RISK_THRESHOLD)
    predictor.fit(X, y, epochs=1000, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class FERPADaemon(Daemon):
    """Watches for students using `view_any_grade`. On the first
    detection, revokes the misconfigured permission from the Student
    role. Subsequent attempts are denied by the engine."""

    def __init__(self, sim, uni, student_role, view_any_op, parent=None):
        super().__init__("FERPADaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.uni = uni
        self.student_role = student_role
        self.view_any_op = view_any_op
        self.detections = 0
        self.revocations = 0

    def on_detection(self) -> None:
        """Called by the simulation whenever a student's view_any_grade
        succeeds."""
        self.detections += 1
        if self.revocations == 0:
            # Revoke the misconfigured permission; this invalidates
            # the permission engine's cache via ZoneBase.revoke.
            self.uni.revoke(self.student_role, self.view_any_op)
            self.revocations += 1
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "ferpa_permission_revoked",
                 "detections": self.detections},
            )


class RegistrationDaemon(Daemon):
    """Warns when registration load exceeds a threshold."""

    def __init__(self, sim, threshold: float = 50.0, parent=None):
        super().__init__("RegistrationDaemon", parent=parent, interval=5.0)
        self.sim = sim
        self.threshold = threshold
        self.alerts = 0

    def monitor(self):
        rate = self.sim.recent_registration_rate()
        if rate > self.threshold:
            self.alerts += 1
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"event": "registration_load", "rate": round(rate, 1)},
            )


class AdvisorDaemon(Daemon):
    """Sweeps active students every simulated hour for at-risk
    prediction. Uses the AtRiskPredictor to flag students."""

    def __init__(self, sim, predictor, parent=None):
        super().__init__("AdvisorDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.predictor = predictor
        self.alerts = 0
        self._last_sweep = -AT_RISK_SWEEP_MINUTES

    def monitor(self):
        now = self.sim.sim_minutes
        if now - self._last_sweep < AT_RISK_SWEEP_MINUTES:
            return
        self._last_sweep = now

        for s in self.sim.students:
            risk = self.predictor.predict({
                "gpa":        s.attributes.get("gpa", 3.0) / 4.0,
                "attendance": s.attributes.get("attendance", 0.8),
                "credits":    s.attributes.get("credits", 12) / 18.0,
            })
            if risk >= AT_RISK_THRESHOLD and not s.attributes.get("at_risk"):
                s.attributes.set("at_risk", True)
                self.alerts += 1
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"event": "at_risk_flagged",
                     "student": s.name, "risk": round(risk, 3)},
                )


class UniversityDaemon(Daemon):
    """Root daemon — aggregates signals from all children."""

    def __init__(self, parent=None):
        super().__init__("UniversityDaemon", parent=parent, interval=1.0)
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
class UniversitySimulation:
    """Student services simulation with real CZOI permission checks.

    Each tick (1 simulated minute):
      1. If in a peak hour, each student has a small probability of
         attempting registration. Each attempt goes through Φ.
      2. Each student has a small probability of attempting a FERPA
         breach (`view_any_grade`). Each attempt goes through Φ.
         Successful attempts are counted as violations and, in CZOA
         mode, trigger the FERPADaemon.
      3. Daemons are ticked by the caller after every step.
    """

    def __init__(self, builder, zones, ops, mode: str):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.mode = mode

        self.students, self.profs, self.advisors, self.registrar = \
            create_users(builder, zones)

        # Neural component (CZOA only)
        if mode == "czoa":
            self.at_risk_model = build_at_risk_predictor()
            zones["University"].add_neural("at_risk", self.at_risk_model)
        else:
            self.at_risk_model = None

        # State
        self.sim_minutes = 0.0
        self.reg_attempts = 0
        self.reg_success = 0
        self.reg_denied = 0
        self.ferpa_attempts = 0
        self.ferpa_violations = 0
        self.ferpa_denied = 0
        self.registration_window: list[tuple[float, int]] = []
        self.logs: list[tuple] = []

        # Daemons (CZOA only)
        self.uni_daemon = None
        self.ferpa_daemon = None
        self.reg_daemon = None
        self.advisor_daemon = None
        if mode == "czoa":
            self._build_daemons()

    # -----------------------------------------------------------------
    def _build_daemons(self):
        self.uni_daemon = UniversityDaemon()
        self.ferpa_daemon = FERPADaemon(
            self,
            self.zones["University"],
            self.zones["University"].roles["Student"],
            self.ops["view_any"],
            parent=self.uni_daemon,
        )
        self.reg_daemon = RegistrationDaemon(self, parent=self.uni_daemon)
        self.advisor_daemon = AdvisorDaemon(
            self, self.at_risk_model, parent=self.uni_daemon,
        )
        for d in (self.uni_daemon, self.ferpa_daemon,
                  self.reg_daemon, self.advisor_daemon):
            self.builder.add_daemon(d)

    # -----------------------------------------------------------------
    @property
    def sim_hours(self) -> float:
        return self.sim_minutes / 60.0

    def recent_registration_rate(self, window_minutes: float = 10.0) -> float:
        cutoff = self.sim_minutes - window_minutes
        count = sum(c for (t, c) in self.registration_window if t >= cutoff)
        return count / window_minutes

    # -----------------------------------------------------------------
    def step(self, dt: float = STEP_MINUTES) -> None:
        self.sim_minutes += dt
        engine = self.builder.permission_engine
        uni = self.zones["University"]

        hour = int(self.sim_hours % 24)
        is_peak = hour in PEAK_HOURS

        # ---- Registration ------------------------------------------
        reg_this_tick = 0
        if is_peak:
            for s in self.students:
                if random.random() >= REGISTRATION_PROB_PER_STUDENT:
                    continue
                reg_this_tick += 1
                self.reg_attempts += 1
                if engine.decide(s, self.ops["register"], uni) \
                        is Decision.ALLOW:
                    self.reg_success += 1
                else:
                    self.reg_denied += 1

        if reg_this_tick:
            self.registration_window.append(
                (self.sim_minutes, reg_this_tick),
            )
        cutoff = self.sim_minutes - 60.0
        self.registration_window = [
            (t, c) for (t, c) in self.registration_window if t >= cutoff
        ]

        # ---- FERPA attempts ----------------------------------------
        for s in self.students:
            if random.random() >= FERPA_ATTEMPT_PROB_PER_STUDENT:
                continue
            self.ferpa_attempts += 1
            decision = engine.decide(s, self.ops["view_any"], uni)
            if decision is Decision.ALLOW:
                self.ferpa_violations += 1
                self._log("ferpa_violation", s.name)
                if self.mode == "czoa" and self.ferpa_daemon is not None:
                    self.ferpa_daemon.on_detection()
            else:
                self.ferpa_denied += 1

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.sim_minutes, 1), event) + tuple(args))


# =====================================================================
# 6. Scenario runner
# =====================================================================
def run_scenario(mode: str, seed: int) -> dict:
    random.seed(seed)
    np.random.seed(seed)

    builder, zones, ops = build_university()
    sim = UniversitySimulation(builder, zones, ops, mode)

    for tick in range(TICKS):
        sim.step(dt=STEP_MINUTES)
        if mode == "czoa":
            builder.daemon_manager.tick()

    return {
        "mode":             mode,
        "reg_attempts":     sim.reg_attempts,
        "reg_success":      sim.reg_success,
        "reg_denied":       sim.reg_denied,
        "reg_rate":         sim.reg_success / max(1, sim.reg_attempts),
        "ferpa_attempts":   sim.ferpa_attempts,
        "ferpa_violations": sim.ferpa_violations,
        "ferpa_denied":     sim.ferpa_denied,
        "ferpa_revocations": sim.ferpa_daemon.revocations
                             if sim.ferpa_daemon else 0,
        "reg_load_alerts":  sim.reg_daemon.alerts
                            if sim.reg_daemon else 0,
        "at_risk_alerts":   sim.advisor_daemon.alerts
                            if sim.advisor_daemon else 0,
        "at_risk_students": sum(
            1 for s in sim.students if s.attributes.get("at_risk")
        ),
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
    # ---- Sanity checks ---------------------------------------------
    builder, zones, ops = build_university()
    uni = zones["University"]
    student = User("s_check", roles={"Student"})
    _register_along_path(student, zones["CS"])
    prof = User("p_check", roles={"Professor"})
    _register_along_path(prof, zones["CS"])
    advisor = User("a_check", roles={"Advisor"})
    _register_along_path(advisor, zones["Advising"])
    engine = builder.permission_engine

    print("Permission sanity check (paper §3, item 9):")
    print("  student  register        :",
          engine.decide(student, ops["register"], uni).name)
    print("  student  view_own_grade  :",
          engine.decide(student, ops["view_own"], uni).name)
    print("  student  view_any_grade  :",
          engine.decide(student, ops["view_any"], uni).name)
    print("  prof     view_any_grade  :",
          engine.decide(prof, ops["view_any"], uni).name)
    print("  prof     submit_grade    :",
          engine.decide(prof, ops["submit"], uni).name)
    print()

    # Demonstrate the FERPADaemon-style revocation.
    uni.revoke(uni.roles["Student"], ops["view_any"])
    print("After university.revoke(Student, view_any_grade):")
    print("  student  view_any_grade  :",
          engine.decide(student, ops["view_any"], uni).name)
    print()

    # Neural at-risk sanity check
    at_risk_model = build_at_risk_predictor()
    safe = at_risk_model.predict(
        {"gpa": 0.95, "attendance": 0.95, "credits": 0.9},
    )
    risky = at_risk_model.predict(
        {"gpa": 0.40, "attendance": 0.35, "credits": 0.4},
    )
    print(f"P(at-risk) | strong student : {safe:.3f}")
    print(f"P(at-risk) | weak student   : {risky:.3f}")
    print()

    # ---- Single paired run -----------------------------------------
    print("=" * 68)
    print(f"University simulation, {SIM_DAYS}-day horizon, paired seed")
    print("=" * 68)
    b = run_scenario("baseline", SEED)
    c = run_scenario("czoa",     SEED)

    header = (f"{'Metric':<28} {'Baseline':>16} {'CZOA':>16}")
    print(header)
    print("-" * len(header))
    rows = [
        ("Registration attempts",  b["reg_attempts"],   c["reg_attempts"]),
        ("  registration success", b["reg_success"],    c["reg_success"]),
        ("  registration denied",  b["reg_denied"],     c["reg_denied"]),
        ("  success rate",         f"{b['reg_rate']:.4f}",
                                   f"{c['reg_rate']:.4f}"),
        ("FERPA attempts",         b["ferpa_attempts"], c["ferpa_attempts"]),
        ("FERPA violations",       b["ferpa_violations"],
                                   c["ferpa_violations"]),
        ("FERPA denied by engine", b["ferpa_denied"],   c["ferpa_denied"]),
        ("FERPA revocations",      "—", c["ferpa_revocations"]),
        ("Registration load alerts","—", c["reg_load_alerts"]),
        ("At-risk alerts",         "—",  c["at_risk_alerts"]),
        ("Distinct at-risk students","—", c["at_risk_students"]),
    ]
    for label, bv, cv in rows:
        print(f"{label:<28} {bv!s:>16} {cv!s:>16}")

    print()
    if b["ferpa_violations"]:
        reduction = (b["ferpa_violations"] - c["ferpa_violations"]) \
                    / b["ferpa_violations"] * 100.0
        print(f"FERPA violation reduction: {reduction:.1f}%")
        print(f"  Baseline: {b['ferpa_violations']} successful "
              f"unauthorised grade views")
        print(f"  CZOA:     {c['ferpa_violations']} (all before the "
              f"first FERPADaemon correction)")
    else:
        print("No FERPA violations occurred in the baseline run "
              "(rare-attempt scenario).")

    # ---- Repeated runs ---------------------------------------------
    print()
    print("=" * 68)
    print("Repeated runs (paired seeds)")
    print("=" * 68)
    baseline_violations, czoa_violations = [], []
    for k in range(3):
        rb = run_scenario("baseline", SEED + k + 1)
        rc = run_scenario("czoa",     SEED + k + 1)
        baseline_violations.append(rb["ferpa_violations"])
        czoa_violations.append(rc["ferpa_violations"])
        print(f"  run {k + 1}: baseline={rb['ferpa_violations']} "
              f"violations, czoa={rc['ferpa_violations']} "
              f"violations, at-risk flagged={rc['at_risk_students']}")

    bm, bci = _ci95([float(v) for v in baseline_violations])
    cm, cci = _ci95([float(v) for v in czoa_violations])
    print()
    print(f"Baseline violations: mean={bm:.1f}, 95% CI ±{bci:.1f}")
    print(f"CZOA     violations: mean={cm:.1f}, 95% CI ±{cci:.1f}")


if __name__ == "__main__":
    main()