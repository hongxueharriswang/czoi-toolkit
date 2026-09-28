"""NHS-style simulation: adaptive surge handling with daemons + UniLog."""
import asyncio

from czoi import (
    Application,
    CZOABuilder,
    Daemon,
    DaemonSignal,
    Operation,
    Predictor,
    Role,
    User,
)


class ClinicalSafetyDaemon(Daemon):
    """Flags patients with high sepsis risk (paper §7.2)."""

    def __init__(self, model: Predictor, threshold: float = 0.85,
                 parent=None):
        super().__init__("ClinicalSafety", parent=parent)
        self.model = model
        self.threshold = threshold

    def monitor(self):
        # Toy feature vector
        score = self.model.predict({"hr": 118, "temp": 39.2, "lactate": 3.1})
        if score > self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"score": score, "reason": "sepsis"},
            )


class RootResponseDaemon(Daemon):
    """Coordinates cross-subsystem response."""

    def __init__(self, parent=None):
        super().__init__("RootResponse", parent=parent)
        self.events: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        self.events.append((signal, payload, source.name if source else None))


def main():
    b = CZOABuilder("RegionalAuthority")
    hosp = b.add_zone("Hospital1")
    clinic = b.add_zone("Clinic1", atomic=True)

    # Operations / roles
    emr = Application("EMR", zone=hosp)
    admit = emr.add_operation(Operation("admit"))
    dispense = emr.add_operation(Operation("dispense"))
    hosp.add_application(emr)

    attending = Role("Attending", zone=hosp, base_permissions=[admit, dispense])
    nurse = Role("Nurse", zone=hosp, base_permissions=[dispense])
    hosp.add_role(attending)
    hosp.add_role(nurse)

    u = User("alice", roles={"Nurse"})
    b.root.add_user(u)
    hosp.add_user(u)
    clinic.add_user(u)

    # Daemon hierarchy
    root_daemon = RootResponseDaemon()
    sepsis = Predictor("sepsis", lambda f: 0.9 if f["lactate"] > 3 else 0.1)
    safety = ClinicalSafetyDaemon(sepsis, threshold=0.85, parent=root_daemon)
    b.add_daemon(safety)
    b.add_daemon(root_daemon)

    print("alice admit @ Clinic1:", b.permission_engine.decide(u, admit, clinic))

    asyncio.run(b.daemon_manager.run(duration=0.1))
    print("Signals received at root:", len(root_daemon.events))
    for sig, payload, src in root_daemon.events:
        print(f"  from {src}: {sig.name} {payload}")


if __name__ == "__main__":
    main()