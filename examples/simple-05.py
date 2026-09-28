"""
simulation.py — Minimal CZOI simulation.

Builds a two-zone system (IT and HR), runs a fixed-length simulation
of access requests, and reports allow/deny statistics. Uses the real
CZOI permission engine, and optionally dumps the access log to JSON.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from czoi import (
    Application,
    CZOABuilder,
    Decision,
    Operation,
    Role,
    User,
)

SEED = 5
random.seed(SEED)

# ---- World constants -------------------------------------------------
N_STEPS = 10
REQUESTS_PER_STEP = 5


# =====================================================================
# 1. Build the system
# =====================================================================
def build_system():
    builder = CZOABuilder("Company")
    root = builder.root
    it = builder.add_zone("IT", parent=root, atomic=True)
    hr = builder.add_zone("HR", parent=root, atomic=True)

    # ---- Applications and operations --------------------------------
    it_app = Application("ITApp", zone=it)
    reboot = it_app.add_operation(Operation("reboot"))
    it.add_application(it_app)

    hr_app = Application("HRApp", zone=hr)
    view_salary = hr_app.add_operation(Operation("view_salary"))
    hr.add_application(hr_app)

    # ---- Roles -------------------------------------------------------
    it_eng = Role("Engineer", zone=it, base_permissions=[reboot])
    hr_assist = Role("Assistant", zone=hr, base_permissions=[view_salary])
    it.add_role(it_eng)
    hr.add_role(hr_assist)

    # ---- Users -------------------------------------------------------
    alice = User("alice", roles={"Engineer"})
    bob   = User("bob",   roles={"Assistant"})
    # Containment principle: register at root, then the zone.
    root.add_user(alice); it.add_user(alice)
    root.add_user(bob);   hr.add_user(bob)

    ops = {"reboot": reboot, "view_salary": view_salary}
    zones = {"root": root, "IT": it, "HR": hr}
    return builder, zones, ops


# =====================================================================
# 2. Access log record
# =====================================================================
@dataclass
class AccessRecord:
    step: int
    user: str
    operation: str
    zone: str
    decision: str

    def as_dict(self) -> dict:
        return {
            "step": self.step, "user": self.user,
            "operation": self.operation, "zone": self.zone,
            "decision": self.decision,
        }


# =====================================================================
# 3. Simulation
# =====================================================================
@dataclass
class Simulation:
    """Generates random access requests and records decisions."""

    builder: object
    zones: dict
    ops: dict
    users: list[User] = field(default_factory=list)
    log: list[AccessRecord] = field(default_factory=list)
    allowed: int = 0
    denied: int = 0

    def _random_request(self):
        """Pick a random user, a random operation, and a random zone."""
        user = random.choice(self.users)
        op_name = random.choice(list(self.ops.keys()))
        zone_name = random.choice(["IT", "HR"])
        return user, self.ops[op_name], self.zones[zone_name]

    def run(self, n_steps: int, requests_per_step: int) -> None:
        engine = self.builder.permission_engine
        for step in range(1, n_steps + 1):
            for _ in range(requests_per_step):
                user, op, zone = self._random_request()
                decision = engine.decide(user, op, zone)
                self.log.append(AccessRecord(
                    step=step,
                    user=user.name,
                    operation=op.qualified_name,
                    zone=zone.name,
                    decision=decision.name,
                ))
                if decision is Decision.ALLOW:
                    self.allowed += 1
                else:
                    self.denied += 1

    # -----------------------------------------------------------------
    def analyze(self) -> dict:
        total = len(self.log)
        return {
            "total_requests": total,
            "allowed":        self.allowed,
            "denied":         self.denied,
            "allow_rate":     self.allowed / total if total else 0.0,
        }

    def save_logs(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([r.as_dict() for r in self.log], fh, indent=2)


# =====================================================================
# 4. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()

    # Restore the users list from the containment hierarchy.
    users = [zones["IT"].users["alice"], zones["HR"].users["bob"]]

    sim = Simulation(builder=builder, zones=zones, ops=ops, users=users)
    sim.run(n_steps=N_STEPS, requests_per_step=REQUESTS_PER_STEP)

    analysis = sim.analyze()
    print("Simulation results:")
    print(f"  total requests : {analysis['total_requests']}")
    print(f"  allowed        : {analysis['allowed']}")
    print(f"  denied         : {analysis['denied']}")
    print(f"  allow rate     : {analysis['allow_rate']:.2f}")

    sim.save_logs("simulation_logs.json")
    print("\nLogs saved to simulation_logs.json")


if __name__ == "__main__":
    main()