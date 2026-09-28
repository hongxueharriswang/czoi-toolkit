"""
evacuation.py — Building evacuation simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Three scenarios compared:
  baseline    — 50 evacuees,  3 guides, moderate familiarity, normal speed.
  guide_rich  — 50 evacuees, 10 guides, lower familiarity, normal speed.
  panic       — 50 evacuees,  0 guides, very low familiarity, erratic speed.

Exercises:
  * Recursive zone tree: Building → Floor1/Floor2 → Rooms / Corridors / Exits.
  * Real CZOI permission calculus (Φ) on every move_to.
  * UniLog separation-of-duty: Evacuee and Guide are exclusive roles.
  * Hierarchical daemons (Δ): EvacuationDaemon at root with CongestionDaemon
    and StuckDaemon as children.
  * Neural evacuation-speed predictor attached to the Building zone.
  * Exit throughput model: 5 concurrent queue slots, 2 flushed per tick.
"""
from __future__ import annotations

import random

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

random.seed(101)
np.random.seed(101)

# ---- Constants -------------------------------------------------------
EXIT_CAPACITY = 5
EXIT_THROUGHPUT = 2
ROOM_CAPACITY = 10
CORRIDOR_CAPACITY = 20
STAIRS_CAPACITY = 15

# Routing graph (zone name → list of allowed next zones)
ROUTES = {
    "Room101":  ["Corridor1"],
    "Room102":  ["Corridor1"],
    "Room201":  ["Corridor2"],
    "Room202":  ["Corridor2"],
    "Corridor1": ["Exit1"],
    "Corridor2": ["Exit2", "Stairs"],   # guide/evacuee chooses
    "Stairs":    ["Corridor1"],
}

SCENARIOS = {
    "baseline": {
        "n_people": 50, "n_guides": 3,
        "familiarity_range": (0.4, 0.8),
        "speed_range": (0.8, 1.5),
    },
    "guide_rich": {
        "n_people": 50, "n_guides": 10,
        "familiarity_range": (0.3, 0.7),
        "speed_range": (0.8, 1.5),
    },
    "panic": {
        "n_people": 50, "n_guides": 0,
        "familiarity_range": (0.1, 0.4),
        "speed_range": (1.2, 2.5),
    },
}


# =====================================================================
# 1. Build the building
# =====================================================================
def build_building():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("EvacuationSystem")

    # ---- Zone tree ---------------------------------------------------
    building = builder.add_zone("Building", parent=builder.root)
    floor1 = builder.add_zone("Floor1", parent=building)
    floor2 = builder.add_zone("Floor2", parent=building)

    room101  = builder.add_zone("Room101", parent=floor1, atomic=True)
    room102  = builder.add_zone("Room102", parent=floor1, atomic=True)
    corridor1 = builder.add_zone("Corridor1", parent=floor1, atomic=True)
    exit1     = builder.add_zone("Exit1", parent=floor1, atomic=True)

    room201  = builder.add_zone("Room201", parent=floor2, atomic=True)
    room202  = builder.add_zone("Room202", parent=floor2, atomic=True)
    corridor2 = builder.add_zone("Corridor2", parent=floor2, atomic=True)
    exit2     = builder.add_zone("Exit2", parent=floor2, atomic=True)

    stairs = builder.add_zone("Stairs", parent=building, atomic=True)

    # ---- Capacities --------------------------------------------------
    for z in (room101, room102, room201, room202):
        z.properties.set("capacity", ROOM_CAPACITY, type_hint="int")
    for z in (corridor1, corridor2):
        z.properties.set("capacity", CORRIDOR_CAPACITY, type_hint="int")
    for z in (exit1, exit2):
        z.properties.set("capacity", EXIT_CAPACITY, type_hint="int")
        z.properties.set("throughput", EXIT_THROUGHPUT, type_hint="int")
    stairs.properties.set("capacity", STAIRS_CAPACITY, type_hint="int")

    # ---- Application and operations ---------------------------------
    app = Application("EvacuationApp", zone=building)
    move   = app.add_operation(Operation("move_to"))
    guide  = app.add_operation(Operation("guide"))
    report = app.add_operation(Operation("report_congestion"))
    building.add_application(app)

    # ---- Roles -------------------------------------------------------
    evacuee_role = Role("Evacuee", zone=building, base_permissions=[move])
    guide_role   = Role("Guide",   zone=building, base_permissions=[move, guide])
    officer_role = Role("SafetyOfficer", zone=building,
                        base_permissions=[report, move])
    building.add_role(evacuee_role)
    building.add_role(guide_role)
    building.add_role(officer_role)

    # ---- UniLog separation-of-duty ----------------------------------
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant Evacuee : Role;
            constant Guide : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . not (hasRole(u, Evacuee) and hasRole(u, Guide))
    """)

    zones = {
        "Building": building, "Floor1": floor1, "Floor2": floor2,
        "Room101": room101, "Room102": room102, "Corridor1": corridor1,
        "Exit1": exit1, "Room201": room201, "Room202": room202,
        "Corridor2": corridor2, "Exit2": exit2, "Stairs": stairs,
    }
    ops = {"move": move, "guide": guide, "report": report}
    return builder, zones, ops


# =====================================================================
# 2. Users along the containment path
# =====================================================================
def _register_along_path(user, zone):
    """Add `user` to `zone` and every ancestor (containment principle)."""
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


def create_people(builder, zones, n_people, n_guides,
                  familiarity_range, speed_range):
    """Create evacuees and guides, distributed across the four rooms."""
    rooms = [zones["Room101"], zones["Room102"],
             zones["Room201"], zones["Room202"]]

    people: list[User] = []
    for i in range(n_people):
        start = random.choice(rooms)
        u = User(
            f"person_{i}",
            roles={"Evacuee"},
            attributes={
                "speed":        random.uniform(*speed_range),
                "familiarity":  random.uniform(*familiarity_range),
                "current_zone": start.name,
                "evacuated":    False,
                "ticks_stuck":  0,
            },
        )
        _register_along_path(u, start)
        people.append(u)

    guides: list[User] = []
    for i in range(n_guides):
        start = random.choice(rooms)
        g = User(
            f"guide_{i}",
            roles={"Guide"},
            attributes={
                "speed":        random.uniform(1.0, 1.8),
                "familiarity":  1.0,
                "current_zone": start.name,
                "evacuated":    False,
                "ticks_stuck":  0,
            },
        )
        _register_along_path(g, start)
        people.append(g)
        guides.append(g)

    return people, guides


# =====================================================================
# 3. Neural evacuation-speed predictor
# =====================================================================
def build_evacuation_predictor() -> Predictor:
    """Predicts P(fast evacuation | familiarity, speed, has_guide).

    Synthetic ground truth: a person with high familiarity, high speed,
    or an accompanying guide evacuates quickly.
    """
    rng = np.random.default_rng(7)
    n = 800
    fam       = rng.uniform(0.0, 1.0, n)
    spd_norm  = rng.uniform(0.5, 2.5, n) / 2.5
    has_guide = (rng.random(n) < 0.2).astype(float)

    X = np.column_stack([fam, spd_norm, has_guide])
    logits = 4.0 * fam + 2.0 * spd_norm + 3.0 * has_guide - 3.5
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("evac_fast", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class CongestionDaemon(Daemon):
    """Warns when a zone's occupancy exceeds a fraction of its capacity."""

    def __init__(self, sim, threshold: float = 0.8, parent=None):
        super().__init__("CongestionDaemon", parent=parent, interval=2.0)
        self.sim = sim
        self.threshold = threshold

    def monitor(self):
        for name, zone in self.sim.zones.items():
            if name in ("Building", "Floor1", "Floor2"):
                continue
            cap = zone.properties.get("capacity", 0)
            if cap <= 0:
                continue
            occ = self.sim.occupancy(name)
            if occ > self.threshold * cap:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"zone": name, "occupancy": occ, "capacity": cap},
                )


class StuckDaemon(Daemon):
    """Signals STATE_CRITICAL for any person stuck too long."""

    def __init__(self, sim, max_ticks: int = 30, parent=None):
        super().__init__("StuckDaemon", parent=parent, interval=5.0)
        self.sim = sim
        self.max_ticks = max_ticks

    def monitor(self):
        for p in self.sim.people:
            if p.attributes.get("evacuated"):
                continue
            ticks = p.attributes.get("ticks_stuck", 0)
            if ticks >= self.max_ticks:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"person": p.name,
                     "zone":   p.attributes.get("current_zone"),
                     "ticks":  ticks},
                )


class EvacuationDaemon(Daemon):
    """Root daemon: aggregates child signals and tracks progress."""

    def __init__(self, parent=None):
        super().__init__("EvacuationDaemon", parent=parent, interval=3.0)
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
class EvacuationSimulation:
    """Zone-by-zone evacuation with real CZOI permission checks.

    Each tick:
      1. Exits flush up to `throughput` queued evacuees (marks them
         `evacuated` and removes them from occupancy).
      2. Every remaining person tries to advance along a route,
         gated by both inline capacity and the real Φ engine.
    """

    def __init__(self, builder, zones, ops, people, guides, predictor):
        self.builder   = builder
        self.zones     = zones
        self.ops       = ops
        self.people    = people
        self.guides    = guides
        self.predictor = predictor
        self.time = 0.0
        self.evacuated_count = 0
        self.evacuation_time = None
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def occupancy(self, zone_name: str) -> int:
        return sum(
            1 for p in self.people
            if p.attributes.get("current_zone") == zone_name
            and not p.attributes.get("evacuated")
        )

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine   = self.builder.permission_engine
        building = self.zones["Building"]

        # ---- 1. Process exits (throughput) -------------------------
        for ex_name in ("Exit1", "Exit2"):
            ex = self.zones[ex_name]
            throughput = ex.properties.get("throughput", 1)
            queue = [
                p for p in self.people
                if p.attributes.get("current_zone") == ex_name
                and not p.attributes.get("evacuated")
            ]
            for p in queue[:throughput]:
                p.attributes.set("evacuated",    True)
                p.attributes.set("current_zone", None)
                self.evacuated_count += 1
                if (self.evacuated_count == len(self.people)
                        and self.evacuation_time is None):
                    self.evacuation_time = self.time
                self._log("evacuated", p.name)

        # ---- 2. Each person attempts one move ----------------------
        random.shuffle(self.people)
        for p in self.people:
            if p.attributes.get("evacuated"):
                continue
            cur = p.attributes.get("current_zone")
            if cur is None:
                continue

            next_zone = self._choose_next(p, cur)
            if next_zone is None:
                continue

            # Inline capacity gate
            cap = next_zone.properties.get("capacity", 999)
            if self.occupancy(next_zone.name) >= cap:
                p.attributes.set("ticks_stuck",
                                 p.attributes.get("ticks_stuck", 0) + 1)
                continue

            # Real Φ permission check
            if engine.decide(p, self.ops["move"], building) is not Decision.ALLOW:
                p.attributes.set("ticks_stuck",
                                 p.attributes.get("ticks_stuck", 0) + 1)
                continue

            p.attributes.set("current_zone", next_zone.name)
            p.attributes.set("ticks_stuck", 0)
            self._log("move", p.name, cur, next_zone.name)

    # -----------------------------------------------------------------
    def _choose_next(self, person, cur):
        """Decide the next zone based on routing rules and role."""
        if cur in ("Exit1", "Exit2"):
            return None
        options = ROUTES.get(cur, [])
        if not options:
            return None

        is_guide = person.name.startswith("guide")

        # Guides and evacuees in Corridor2 choose between Exit2 and Stairs.
        if cur == "Corridor2":
            e1_occ = self.occupancy("Exit1")
            e2_occ = self.occupancy("Exit2")
            if is_guide:
                # Guides know the less congested route.
                return self.zones["Stairs"] if e1_occ < e2_occ \
                    else self.zones["Exit2"]
            # Evacuees use familiarity + neural predictor.
            fam = person.attributes.get("familiarity", 0.5)
            spd = person.attributes.get("speed", 1.0) / 2.5
            p_fast = self.predictor.predict(
                {"fam": fam, "spd": spd, "guide": 0.0}
            )
            if p_fast > 0.5 and fam > 0.4:
                return self.zones["Exit2"]
            return self.zones["Stairs"]

        return self.zones[options[0]]

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.time, 2), event) + tuple(args))


# =====================================================================
# 6. Scenario runner
# =====================================================================
def run_scenario(name, n_people, n_guides, familiarity_range, speed_range,
                 max_seconds: int = 250):
    """Build a fresh system, run one scenario, return summary stats."""
    builder, zones, ops = build_building()
    people, guides = create_people(
        builder, zones, n_people, n_guides,
        familiarity_range, speed_range,
    )
    predictor = build_evacuation_predictor()
    zones["Building"].add_neural("evac_fast", predictor)

    sim = EvacuationSimulation(
        builder, zones, ops, people, guides, predictor,
    )

    # ---- Daemon hierarchy ------------------------------------------
    root = EvacuationDaemon()
    congestion = CongestionDaemon(sim, parent=root)
    stuck      = StuckDaemon(sim, max_ticks=30, parent=root)
    builder.add_daemon(root)
    builder.add_daemon(congestion)
    builder.add_daemon(stuck)

    # ---- Run --------------------------------------------------------
    for step in range(max_seconds):
        sim.step(dt=1.0)
        if step % 5 == 0:
            builder.daemon_manager.tick()
        if sim.evacuated_count >= len(people):
            break

    return {
        "name":       name,
        "evacuated":  sim.evacuated_count,
        "total":      len(people),
        "time":       sim.evacuation_time,
        "elapsed":    sim.time,
        "warnings":   len(root.warnings),
        "criticals":  len(root.criticals),
        "denied":     builder.permission_engine.stats()["denies"],
    }


# =====================================================================
# 7. Main
# =====================================================================
def main() -> None:
    # ---- Sanity checks ---------------------------------------------
    builder, zones, ops = build_building()
    people, guides = create_people(
        builder, zones, n_people=5, n_guides=2,
        familiarity_range=(0.5, 0.7), speed_range=(1.0, 1.5),
    )
    building = zones["Building"]
    engine   = builder.permission_engine
    evacuee  = people[0]
    guide    = guides[0]

    print("Permission sanity check (paper §3, item 9):")
    print(f"  {evacuee.name:<14} move  :",
          engine.decide(evacuee, ops["move"], building).name)
    print(f"  {evacuee.name:<14} guide :",
          engine.decide(evacuee, ops["guide"], building).name)
    print(f"  {guide.name:<14} move  :",
          engine.decide(guide, ops["move"], building).name)
    print(f"  {guide.name:<14} guide :",
          engine.decide(guide, ops["guide"], building).name)

    predictor = build_evacuation_predictor()
    p_high = predictor.predict({"fam": 0.9, "spd": 0.8, "guide": 1.0})
    p_low  = predictor.predict({"fam": 0.15, "spd": 0.4, "guide": 0.0})
    print()
    print(f"P(fast evac) — familiar, guided  : {p_high:.3f}")
    print(f"P(fast evac) — panicked, alone   : {p_low:.3f}")
    print()

    # ---- Run scenarios ---------------------------------------------
    results = []
    for name, cfg in SCENARIOS.items():
        print("=" * 60)
        print(f"Scenario: {name}")
        print("=" * 60)
        r = run_scenario(name, **cfg)
        results.append(r)

        if r["time"] is not None:
            print(f"  Evacuated : {r['evacuated']}/{r['total']} "
                  f"in {r['time']:.1f}s")
        else:
            print(f"  Evacuated : {r['evacuated']}/{r['total']} "
                  f"(not complete after {r['elapsed']:.0f}s)")
        print(f"  Warnings  : {r['warnings']}")
        print(f"  Criticals : {r['criticals']}")
        print(f"  Φ denies  : {r['denied']}")
        print()

    # ---- Comparison table ------------------------------------------
    print("=" * 60)
    print("Comparison")
    print("=" * 60)
    header = (f"{'Scenario':<12} {'Evac':>10} {'Time(s)':>10} "
              f"{'Warn':>6} {'Crit':>6} {'Deny':>6}")
    print(header)
    print("-" * len(header))
    for r in results:
        t = f"{r['time']:.1f}" if r["time"] is not None else "—"
        evac = f"{r['evacuated']}/{r['total']}"
        print(f"{r['name']:<12} {evac:>10} {t:>10} "
              f"{r['warnings']:>6} {r['criticals']:>6} {r['denied']:>6}")


if __name__ == "__main__":
    main()