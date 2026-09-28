"""
assembly_line.py — Manufacturing assembly-line simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: AssemblyCell → WS1 / WS2 / BufferZone.
  * Applications and atomic operations (pick, place, weld, inspect, move).
  * Real CZOI permission calculus (Φ) on every operation.
  * UniLog separation-of-duty: an arm cannot both weld and inspect.
  * Hierarchical daemons (Δ): LineDaemon at root with SafetyDaemon,
    DefectRateDaemon, and ThroughputDaemon as children.
  * Neural defect prediction (Predictor) attached to the AssemblyCell.
  * Attribute-based arm state via PropertyStore.
"""
from __future__ import annotations

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

random.seed(23)

# ---- World constants -------------------------------------------------
N_PICKERS = 2
N_WELDERS = 2
BUFFER_PARTS = 100
PRODUCTS_TARGET = 40
DEFECT_RATE_WARN = 0.15
DEFECT_RATE_CRITICAL = 0.25
IDLE_THRESHOLD = 3


# =====================================================================
# 1. Build the assembly cell
# =====================================================================
def build_system():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("AssemblyPlant")

    # ---- Zones -----------------------------------------------------
    cell = builder.add_zone("AssemblyCell", parent=builder.root)
    ws1 = builder.add_zone("Workstation1", parent=cell, atomic=True)
    ws2 = builder.add_zone("Workstation2", parent=cell, atomic=True)
    buffer = builder.add_zone("BufferZone", parent=cell, atomic=True)

    # Capacity attributes on each workstation.
    ws1.properties.set("capacity", 2, type_hint="int")
    ws2.properties.set("capacity", 2, type_hint="int")
    buffer.properties.set("capacity", 100, type_hint="int")

    # ---- Application and operations --------------------------------
    app = Application("AssemblyApp", zone=cell)
    pick = app.add_operation(Operation("pick"))
    place = app.add_operation(Operation("place"))
    weld = app.add_operation(Operation("weld"))
    inspect = app.add_operation(Operation("inspect"))
    move = app.add_operation(Operation("move"))
    override = app.add_operation(Operation("override_line"))
    cell.add_application(app)

    # ---- Roles and base permissions --------------------------------
    picker_role = Role(
        "PickerArm",
        zone=cell,
        base_permissions=[pick, place, move],
    )
    welder_role = Role(
        "WelderArm",
        zone=cell,
        base_permissions=[weld, move],
    )
    inspector_role = Role(
        "InspectorArm",
        zone=cell,
        base_permissions=[inspect, move],
    )
    supervisor_role = Role(
        "Supervisor",
        zone=cell,
        base_permissions=[override, move],
    )
    cell.add_role(picker_role)
    cell.add_role(welder_role)
    cell.add_role(inspector_role)
    cell.add_role(supervisor_role)

    # ---- UniLog separation-of-duty ---------------------------------
    # An arm cannot hold the Welder role and the Inspector role.
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User . not (
            hasRole(u, WelderArm) and hasRole(u, InspectorArm)
        )
    """)

    ops = {
        "pick": pick,
        "place": place,
        "weld": weld,
        "inspect": inspect,
        "move": move,
        "override": override,
    }
    zones = {"cell": cell, "ws1": ws1, "ws2": ws2, "buffer": buffer}
    return builder, zones, ops


# =====================================================================
# 2. Create arms, inspector, and supervisor
# =====================================================================
def create_users(builder, cell, ws1, ws2, buffer, n_pickers, n_welders):
    pickers, welders = [], []

    for i in range(n_pickers):
        p = User(
            f"picker_{i}",
            roles={"PickerArm"},
            attributes={
                "position": (0, 0),
                "task_queue": [],
                "error_rate": 0.01,
                "parts_picked": 0,
            },
        )
        builder.root.add_user(p)
        cell.add_user(p)
        ws1.add_user(p)
        pickers.append(p)

    for i in range(n_welders):
        w = User(
            f"welder_{i}",
            roles={"WelderArm"},
            attributes={
                "position": (10, 0),
                "task_queue": [],
                "error_rate": 0.02,
                "welds_completed": 0,
            },
        )
        builder.root.add_user(w)
        cell.add_user(w)
        ws2.add_user(w)
        welders.append(w)

    inspector = User(
        "inspector",
        roles={"InspectorArm"},
        attributes={
            "position": (5, 5),
            "task_queue": [],
            "error_rate": 0.001,
            "inspected": 0,
            "defects_found": 0,
        },
    )
    builder.root.add_user(inspector)
    cell.add_user(inspector)
    buffer.add_user(inspector)

    supervisor = User(
        "supervisor",
        roles={"Supervisor"},
        attributes={"position": (5, 5)},
    )
    builder.root.add_user(supervisor)
    cell.add_user(supervisor)

    return pickers, welders, inspector, supervisor


# =====================================================================
# 3. Neural defect predictor
# =====================================================================
def build_defect_predictor() -> Predictor:
    """Predicts defect probability from arm error rate + temperature.

    Trained on synthetic data: higher error rate and higher temperature
    correlate with higher defect probability.
    """
    import numpy as np

    rng = np.random.default_rng(0)
    n = 300
    X = np.column_stack([
        rng.uniform(0.0, 0.05, n),      # error_rate
        rng.uniform(0.5, 1.0, n),       # normalised temperature
        rng.uniform(0.0, 1.0, n),       # part complexity
    ])
    # Ground truth: probability = sigmoid(40 * err + 2 * temp + complexity - 2)
    logits = 40 * X[:, 0] + 2 * X[:, 1] + X[:, 2] - 2.0
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("defect", threshold=0.5)
    predictor.fit(X, y, epochs=1000, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class SafetyDaemon(Daemon):
    """Halts the line if defect rate exceeds the critical threshold."""

    def __init__(self, sim, threshold: float = DEFECT_RATE_CRITICAL,
                 parent=None):
        super().__init__("SafetyDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.threshold = threshold

    def monitor(self):
        total = self.sim.products_made + self.sim.defects
        if total >= 10:
            rate = self.sim.defects / total
            if rate > self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {"defect_rate": round(rate, 3), "total": total},
                )


class DefectRateDaemon(Daemon):
    """Warns when the defect rate exceeds the warning threshold."""

    def __init__(self, sim, threshold: float = DEFECT_RATE_WARN, parent=None):
        super().__init__("DefectRateDaemon", parent=parent, interval=2.0)
        self.sim = sim
        self.threshold = threshold

    def monitor(self):
        total = self.sim.products_made + self.sim.defects
        if total >= 5:
            rate = self.sim.defects / total
            if rate > self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"defect_rate": round(rate, 3)},
                )


class ThroughputDaemon(Daemon):
    """Warns when the line is under-utilised (few active arms)."""

    def __init__(self, arms, threshold: int = IDLE_THRESHOLD, parent=None):
        super().__init__("ThroughputDaemon", parent=parent, interval=3.0)
        self.arms = arms
        self.threshold = threshold

    def monitor(self):
        active = sum(1 for a in self.arms if a.attributes.get("task_queue"))
        if active < self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"active_arms": active, "threshold": self.threshold},
            )


class LineDaemon(Daemon):
    """Root daemon aggregating signals from the children."""

    def __init__(self, parent=None):
        super().__init__("LineDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []
        self.halted = False

    def on_signal(self, signal, payload, source=None):
        src = source.name if source is not None else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))
            # SafetyDaemon criticals halt the line.
            if src == "SafetyDaemon":
                self.halted = True


# =====================================================================
# 5. Simulation
# =====================================================================
class AssemblySimulation:
    """Three-stage pipeline: pick → weld → inspect.

    Every stage transition is gated by the real permission engine, and
    each arm's capabilities are drawn from its role.
    """

    def __init__(
        self,
        builder,
        zones,
        ops,
        pickers,
        welders,
        inspector,
        supervisor,
        defect_model: Predictor,
    ):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.pickers = pickers
        self.welders = welders
        self.inspector = inspector
        self.supervisor = supervisor
        self.defect_model = defect_model
        self.parts_available = BUFFER_PARTS
        self.products_made = 0
        self.defects = 0
        self.time = 0.0
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def step(self, dt: float = 5.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        cell = self.zones["cell"]

        # ---- Pickers ------------------------------------------------
        for p in self.pickers:
            if self.parts_available <= 0:
                break
            op = self.ops["pick"]
            if engine.decide(p, op, cell) is Decision.ALLOW:
                if random.random() < 0.5:
                    p.attributes["task_queue"].append("picked_part")
                    p.attributes.set(
                        "parts_picked",
                        p.attributes.get("parts_picked", 0) + 1,
                    )
                    self.parts_available -= 1
                    self._log("pick", p.name)

        # ---- Transfer to weld queue ---------------------------------
        # A picked part becomes a "weldable part" once the picker
        # has issued the `place` operation.
        for p in self.pickers:
            if (p.attributes["task_queue"]
                    and p.attributes["task_queue"][0] == "picked_part"):
                op = self.ops["place"]
                if engine.decide(p, op, cell) is Decision.ALLOW:
                    p.attributes["task_queue"].pop(0)
                    # Enqueue on the welder with the smallest queue.
                    target = min(
                        self.welders,
                        key=lambda w: len(w.attributes.get("task_queue", [])),
                    )
                    target.attributes["task_queue"].append("part")
                    self._log("place", p.name)

        # ---- Welders ------------------------------------------------
        for w in self.welders:
            if not w.attributes["task_queue"]:
                continue
            op = self.ops["weld"]
            if engine.decide(w, op, cell) is Decision.ALLOW:
                if random.random() < 0.4:
                    w.attributes["task_queue"].pop(0)
                    w.attributes.set(
                        "welds_completed",
                        w.attributes.get("welds_completed", 0) + 1,
                    )
                    # Forward to the inspector.
                    self.inspector.attributes["task_queue"].append("welded_part")
                    self._log("weld", w.name)

        # ---- Inspector ----------------------------------------------
        i = self.inspector
        if i.attributes["task_queue"]:
            op = self.ops["inspect"]
            if engine.decide(i, op, cell) is Decision.ALLOW:
                if random.random() < 0.3:
                    i.attributes["task_queue"].pop(0)
                    i.attributes.set(
                        "inspected",
                        i.attributes.get("inspected", 0) + 1,
                    )
                    features = {
                        "error_rate": 0.02,
                        "temperature": random.uniform(0.5, 1.0),
                        "complexity": random.random(),
                    }
                    defect_p = self.defect_model.predict(features)
                    if random.random() < defect_p:
                        self.defects += 1
                        i.attributes.set(
                            "defects_found",
                            i.attributes.get("defects_found", 0) + 1,
                        )
                        self._log("defect", i.name)
                    else:
                        self.products_made += 1
                        self._log("pass", i.name)

    # -----------------------------------------------------------------
    def _log(self, event: str, actor: str) -> None:
        self.logs.append((round(self.time, 1), event, actor))


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()
    pickers, welders, inspector, supervisor = create_users(
        builder, zones["cell"], zones["ws1"], zones["ws2"], zones["buffer"],
        N_PICKERS, N_WELDERS,
    )
    arms = pickers + welders + [inspector]

    # ---- Neural component attached to the AssemblyCell --------------
    defect_model = build_defect_predictor()
    zones["cell"].add_neural("defect_predictor", defect_model)

    # ---- Sanity check on the defect predictor ----------------------
    safe_p = defect_model.predict({
        "error_rate": 0.005, "temperature": 0.5, "complexity": 0.1,
    })
    risky_p = defect_model.predict({
        "error_rate": 0.045, "temperature": 0.95, "complexity": 0.9,
    })
    print(f"Defect probability — safe arm : {safe_p:.3f}")
    print(f"Defect probability — risky arm: {risky_p:.3f}")
    print()

    # ---- Simulation object (needed for daemons) --------------------
    sim = AssemblySimulation(
        builder, zones, ops, pickers, welders, inspector, supervisor,
        defect_model,
    )

    # ---- Daemon hierarchy -------------------------------------------
    line = LineDaemon()
    safety = SafetyDaemon(sim, parent=line)
    defect_rate = DefectRateDaemon(sim, parent=line)
    throughput = ThroughputDaemon(arms, parent=line)
    builder.add_daemon(line)
    builder.add_daemon(safety)
    builder.add_daemon(defect_rate)
    builder.add_daemon(throughput)

    # ---- Sanity check: real CZOI permission decisions ---------------
    cell = zones["cell"]
    engine = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  picker_0   pick     :",
          engine.decide(pickers[0], ops["pick"], cell).name)
    print("  picker_0   weld     :",
          engine.decide(pickers[0], ops["weld"], cell).name)
    print("  welder_0   weld     :",
          engine.decide(welders[0], ops["weld"], cell).name)
    print("  welder_0   inspect  :",
          engine.decide(welders[0], ops["inspect"], cell).name)
    print("  inspector  inspect  :",
          engine.decide(inspector, ops["inspect"], cell).name)
    print("  supervisor override :",
          engine.decide(supervisor, ops["override"], cell).name)
    print()

    # ---- Simulate 30 minutes at 5-second steps ---------------------
    steps = 30 * 12                    # 30 min / 5 s = 360 steps
    for s in range(steps):
        if line.halted:
            print(f"Line halted at t={sim.time:.0f}s "
                  f"(defect rate {sim.defects / max(1, sim.defects + sim.products_made):.2%})")
            break
        sim.step(dt=5.0)
        if s % 6 == 0:                 # daemons every 30 sim-seconds
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    total_inspected = sim.products_made + sim.defects
    defect_rate = sim.defects / total_inspected if total_inspected else 0.0
    print(f"Products made       : {sim.products_made}")
    print(f"Defects             : {sim.defects}")
    print(f"Total inspected     : {total_inspected}")
    print(f"Defect rate         : {defect_rate:.2%}")
    print(f"Parts remaining     : {sim.parts_available}")
    print(f"Line halted         : {line.halted}")
    print(f"Line warnings       : {len(line.warnings)}")
    print(f"Line criticals      : {len(line.criticals)}")

    if line.criticals:
        print("\nCritical alerts:")
        for src, payload in line.criticals[:3]:
            print(f"  from {src}: {payload}")

    if line.warnings:
        print("\nFirst 3 warnings:")
        for src, payload in line.warnings[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()