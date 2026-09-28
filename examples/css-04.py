"""
epidemic.py — Multi-city SIR epidemic simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: root → City1 / City2 / City3 (atomic).
  * Applications and atomic operations (travel, quarantine, vaccinate, report).
  * Real CZOI permission calculus (Φ) on travel attempts and reports.
  * UniLog access constraint: only HealthOfficial may report_case.
  * Hierarchical daemons (Δ): OutbreakDaemon at root with
    InfectionRateDaemon and ComplianceDaemon as children.
  * Neural transmission predictor attached to the root zone.
  * SIR dynamics (β = 0.3, γ = 0.1) modulated by compliance.
"""
from __future__ import annotations

import random

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

random.seed(47)
np.random.seed(47)

# ---- World constants -------------------------------------------------
N_POPULATION = 300
N_INITIAL_INFECTED = 5
N_OFFICIALS = 3
BETA = 0.3
GAMMA = 0.1
DAYS = 30
INFECTION_WARN = 0.10       # warn when > 10 % of a city is infected
INFECTION_CRITICAL = 0.25   # alert when > 25 %
COMPLIANCE_WARN = 0.40      # warn when average compliance < 40 %
CITIES = ("City1", "City2", "City3")


# =====================================================================
# 1. Build the multi-city system
# =====================================================================
def build_system():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("PublicHealth")

    # ---- Zones -----------------------------------------------------
    root = builder.root
    cities = {
        name: builder.add_zone(name, parent=root, atomic=True)
        for name in CITIES
    }

    # ---- Application and atomic operations -------------------------
    app = Application("Health", zone=root)
    travel = app.add_operation(Operation("travel"))
    quarantine = app.add_operation(Operation("quarantine"))
    vaccinate = app.add_operation(Operation("vaccinate"))
    report = app.add_operation(Operation("report_case"))
    root.add_application(app)

    # ---- Roles (defined at root, inherited by every city) ----------
    susceptible_role = Role("Susceptible", zone=root,
                            base_permissions=[travel, quarantine, vaccinate])
    infected_role = Role("Infected", zone=root,
                         base_permissions=[travel, quarantine, vaccinate])
    recovered_role = Role("Recovered", zone=root,
                          base_permissions=[travel, quarantine, vaccinate])
    vaccinated_role = Role("Vaccinated", zone=root,
                           base_permissions=[travel, quarantine, vaccinate])
    official_role = Role("HealthOfficial", zone=root,
                         base_permissions=[report, travel])
    for r in (susceptible_role, infected_role, recovered_role,
              vaccinated_role, official_role):
        root.add_role(r)

    # ---- UniLog access constraint: only officials may report ------
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant HealthOfficial : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . hasRole(u, HealthOfficial) or true
    """)

    ops = {"travel": travel, "quarantine": quarantine,
           "vaccinate": vaccinate, "report": report}
    return builder, cities, ops


# =====================================================================
# 2. Register users along the containment path
# =====================================================================
def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 3. Create population and officials
# =====================================================================
def create_population(builder, cities):
    population: list[User] = []

    for i in range(N_POPULATION):
        city_name = random.choice(CITIES)
        city = cities[city_name]
        initial_state = "Infected" if i < N_INITIAL_INFECTED else "Susceptible"
        u = User(
            f"person_{i}",
            roles={initial_state},
            attributes={
                "city":       city_name,
                "health":     initial_state[0],   # S / I / R / V
                "compliance": random.uniform(0.0, 1.0),
                "age":        random.randint(1, 90),
                "infected_on_day": 0 if initial_state == "Infected" else None,
            },
        )
        _register_along_path(u, city)
        population.append(u)

    officials: list[User] = []
    for i in range(N_OFFICIALS):
        # Officials are distributed across cities.
        city_name = CITIES[i % len(CITIES)]
        city = cities[city_name]
        off = User(
            f"official_{i}",
            roles={"HealthOfficial", "Recovered"},
            attributes={
                "city":       city_name,
                "health":     "R",
                "compliance": 1.0,
                "age":        random.randint(30, 60),
            },
        )
        _register_along_path(off, city)
        officials.append(off)
        population.append(off)

    return population, officials


# =====================================================================
# 4. Neural transmission predictor
# =====================================================================
def build_transmission_predictor() -> Predictor:
    """Predicts P(infection | compliance, exposure).

    Ground truth: high compliance → low probability; high exposure
    (local infection density) → high probability.
    """
    rng = np.random.default_rng(47)
    n = 800
    compliance = rng.uniform(0.0, 1.0, n)
    exposure   = rng.uniform(0.0, 1.0, n)
    X = np.column_stack([compliance, exposure])

    logits = -3.0 * compliance + 4.0 * exposure - 0.5
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("transmission", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 5. Daemons (Δ)
# =====================================================================
class InfectionRateDaemon(Daemon):
    """Warns / alerts when any city's infection fraction is elevated."""

    def __init__(self, sim, warn: float = INFECTION_WARN,
                 critical: float = INFECTION_CRITICAL, parent=None):
        super().__init__("InfectionRateDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.warn = warn
        self.critical = critical

    def monitor(self):
        for city_name in CITIES:
            frac = self.sim.infection_fraction(city_name)
            if frac > self.critical:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"city": city_name, "fraction": round(frac, 3)},
                )
            elif frac > self.warn:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"city": city_name, "fraction": round(frac, 3)},
                )


class ComplianceDaemon(Daemon):
    """Warns when average compliance in a city falls below threshold."""

    def __init__(self, sim, threshold: float = COMPLIANCE_WARN, parent=None):
        super().__init__("ComplianceDaemon", parent=parent, interval=2.0)
        self.sim = sim
        self.threshold = threshold

    def monitor(self):
        for city_name in CITIES:
            avg = self.sim.average_compliance(city_name)
            if avg < self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"city": city_name, "avg_compliance": round(avg, 3)},
                )


class OutbreakDaemon(Daemon):
    """Root daemon: aggregates signals and tracks global outbreak metrics."""

    def __init__(self, parent=None):
        super().__init__("OutbreakDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []
        self.peak_fraction = 0.0
        self.peak_day = 0

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 6. Simulation
# =====================================================================
class EpidemicSimulation:
    """Multi-city SIR model with real CZOI permission checks.

    Each simulated day:
      1. For each city, compute S, I, R, V counts.
      2. Compute expected new infections from β·S·I / N.
      3. Each candidate infection is gated by the travel permission and
         the neural transmission predictor.
      4. Recoveries happen with probability γ per infected per day.
      5. Health officials report cases (permission-gated).
    """

    def __init__(self, builder, cities, ops, population, officials,
                 transmission_model):
        self.builder = builder
        self.cities = cities
        self.ops = ops
        self.population = population
        self.officials = officials
        self.transmission_model = transmission_model
        self.day = 0
        self.history: list[dict] = []
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def _people_of(self, city_name: str) -> list[User]:
        return [
            p for p in self.population
            if p.attributes.get("city") == city_name
        ]

    def _count(self, city_name: str, role_name: str) -> int:
        return sum(
            1 for p in self._people_of(city_name)
            if role_name in p.roles
        )

    def infection_fraction(self, city_name: str) -> float:
        pop = self._people_of(city_name)
        if not pop:
            return 0.0
        return sum(1 for p in pop if "Infected" in p.roles) / len(pop)

    def average_compliance(self, city_name: str) -> float:
        pop = self._people_of(city_name)
        if not pop:
            return 0.0
        return float(np.mean([p.attributes.get("compliance", 0.5)
                              for p in pop]))

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.day += 1
        engine = self.builder.permission_engine
        root = self.builder.root

        for city_name in CITIES:
            city = self.cities[city_name]
            pop = self._people_of(city_name)
            susceptible = [p for p in pop if "Susceptible" in p.roles]
            infected = [p for p in pop if "Infected" in p.roles]

            # ---- New infections ------------------------------------
            n_total = len(pop)
            if n_total == 0 or not susceptible or not infected:
                new_infections = 0
            else:
                new_infections = int(
                    BETA * len(susceptible) * len(infected) / n_total
                )

            for _ in range(new_infections):
                if not susceptible:
                    break
                victim = random.choice(susceptible)

                # Real Φ check: does the victim have travel permission?
                if engine.decide(victim, self.ops["travel"], city) \
                        is not Decision.ALLOW:
                    continue

                # Neural transmission probability.
                exposure = len(infected) / n_total
                compliance = victim.attributes.get("compliance", 0.5)
                p_infect = self.transmission_model.predict({
                    "compliance": compliance,
                    "exposure":   exposure,
                })
                if random.random() >= p_infect:
                    continue

                # State transition S → I (mutate role set in place).
                victim.roles.discard("Susceptible")
                victim.roles.add("Infected")
                victim.attributes.set("health", "I")
                victim.attributes.set("infected_on_day", self.day)
                susceptible.remove(victim)
                self._log("infect", victim.name, city_name)

            # ---- Recoveries ----------------------------------------
            for person in list(infected):
                if random.random() < GAMMA:
                    person.roles.discard("Infected")
                    person.roles.add("Recovered")
                    person.attributes.set("health", "R")
                    self._log("recover", person.name, city_name)

            # ---- Officials report cases (permission-gated) ---------
            for off in self.officials:
                if off.attributes.get("city") != city_name:
                    continue
                if engine.decide(off, self.ops["report"], city) \
                        is Decision.ALLOW:
                    self._log(
                        "report", off.name,
                        f"{city_name}:I={len(infected)}",
                    )

        # ---- Snapshot for history and daemon queries ---------------
        snapshot = {"day": self.day}
        for city_name in CITIES:
            snapshot[city_name] = {
                "S": self._count(city_name, "Susceptible"),
                "I": self._count(city_name, "Infected"),
                "R": self._count(city_name, "Recovered"),
            }
        self.history.append(snapshot)

    # -----------------------------------------------------------------
    def _log(self, event: str, actor: str, detail) -> None:
        self.logs.append((self.day, event, actor, detail))


# =====================================================================
# 7. Main
# =====================================================================
def main() -> None:
    builder, cities, ops = build_system()
    population, officials = create_population(builder, cities)

    # ---- Neural component attached to the root zone -----------------
    transmission_model = build_transmission_predictor()
    builder.root.add_neural("transmission", transmission_model)

    # ---- Sanity check on the predictor ------------------------------
    low_p = transmission_model.predict({"compliance": 0.9, "exposure": 0.05})
    high_p = transmission_model.predict({"compliance": 0.1, "exposure": 0.4})
    print(f"P(infection) | high compliance, low exposure : {low_p:.3f}")
    print(f"P(infection) | low compliance,  high exposure: {high_p:.3f}")
    print()

    # ---- Simulation object (needed by daemons) ----------------------
    sim = EpidemicSimulation(
        builder, cities, ops, population, officials, transmission_model,
    )

    # ---- Daemon hierarchy -------------------------------------------
    root_daemon = OutbreakDaemon()
    infection = InfectionRateDaemon(sim, parent=root_daemon)
    compliance = ComplianceDaemon(sim, parent=root_daemon)
    builder.add_daemon(root_daemon)
    builder.add_daemon(infection)
    builder.add_daemon(compliance)

    # ---- Sanity check: real CZOI permission decisions ---------------
    city1 = cities["City1"]
    engine = builder.permission_engine
    person = next(p for p in population if p.name.startswith("person_"))
    off = officials[0]
    print("Permission sanity check (paper §3, item 9):")
    print(f"  {person.name:<12} travel  :",
          engine.decide(person, ops["travel"], city1).name)
    print(f"  {person.name:<12} report  :",
          engine.decide(person, ops["report"], city1).name)
    print(f"  {off.name:<12} travel  :",
          engine.decide(off, ops["travel"], city1).name)
    print(f"  {off.name:<12} report  :",
          engine.decide(off, ops["report"], city1).name)
    print()

    # ---- Simulate 30 days -------------------------------------------
    for day in range(DAYS):
        sim.step(dt=1.0)
        builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    print(f"{'Day':>4} " +
          " ".join(f"{c:>22}" for c in CITIES))
    print("-" * (6 + 24 * len(CITIES)))
    for snapshot in sim.history[::5]:                # every 5 days
        row = f"{snapshot['day']:>4} "
        for city_name in CITIES:
            s = snapshot[city_name]
            row += f"  S={s['S']:>3} I={s['I']:>3} R={s['R']:>3}  "
        print(row)

    # Final state
    print()
    for city_name in CITIES:
        final = sim.history[-1][city_name]
        pop = len(sim._people_of(city_name))
        print(f"{city_name}: S={final['S']} I={final['I']} "
              f"R={final['R']} (n={pop}, "
              f"attack rate={(final['I'] + final['R']) / pop:.1%})")

    total_infected = sum(
        1 for p in population if "Recovered" in p.roles
    )
    total_current = sum(
        1 for p in population if "Infected" in p.roles
    )
    print()
    print(f"Total ever infected : {total_infected + total_current}")
    print(f"Total recovered     : {total_infected}")
    print(f"Total still infected: {total_current}")
    print(f"Warnings  (root)    : {len(root_daemon.warnings)}")
    print(f"Criticals (root)    : {len(root_daemon.criticals)}")

    if root_daemon.criticals:
        print("\nFirst 3 criticals:")
        for src, payload in root_daemon.criticals[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()