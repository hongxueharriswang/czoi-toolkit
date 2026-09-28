"""
security_daemon.py — Periodic security daemon over a live CZOI audit stream.

Demonstrates the paper's §5.4 constraint-daemon pattern:

  1. A small CZOI system is built with a permission engine that has
     audit records enabled.
  2. Synthetic traffic (some legitimate, some suspicious) drives the
     engine.
  3. A SecurityDaemon runs every simulated minute. It reads the newest
     audit records, converts them to feature vectors, and scores them
     with a trained AnomalyDetector.
  4. High-risk events trigger STATE_CRITICAL signals upward to a root
     SentinelDaemon, which revokes the offender's role permissions.
  5. DaemonManager runs everything asynchronously via a thread pool —
     the monitors are synchronous, the scheduler is async.
"""
from __future__ import annotations

import asyncio
import random
from datetime import timezone

import numpy as np

from czoi import (
    AnomalyDetector,
    Application,
    CZOABuilder,
    Daemon,
    DaemonSignal,
    Operation,
    Role,
    User,
)

SEED = 17
random.seed(SEED)
np.random.seed(SEED)

# ---- World constants -------------------------------------------------
N_USERS   = 20
N_TICKS   = 60          # simulated minutes
RISK_THRESHOLD_FOR_ACTION = 0.8   # signal critical above this

# Feature bounds: [user_idx, hour, minute, op_idx]
# Normalised z-scores will be learned inside the detector.


# =====================================================================
# 1. Build the target system
# =====================================================================
def build_target():
    """A small corporate system with two roles and three operations."""
    builder = CZOABuilder("Corp")

    corp = builder.root
    dev  = builder.add_zone("Dev", parent=corp, atomic=True)

    app = Application("Platform", zone=corp)
    read_doc    = app.add_operation(Operation("read_doc"))
    commit_code = app.add_operation(Operation("commit_code"))
    deploy      = app.add_operation(Operation("deploy_prod"))
    corp.add_application(app)

    viewer = Role("Viewer",   zone=corp, base_permissions=[read_doc])
    dev_role = Role("Developer", zone=corp,
                    base_permissions=[read_doc, commit_code])
    ops_role = Role("OpsEngineer", zone=dev,
                    base_permissions=[read_doc, commit_code, deploy])
    corp.add_role(viewer)
    corp.add_role(dev_role)
    dev.add_role(ops_role)

    users: list[User] = []
    for i in range(N_USERS):
        role = random.choice(["Viewer", "Developer", "OpsEngineer"])
        u = User(f"user_{i}", roles={role},
                 attributes={"role_kind": role, "revoked": False})
        corp.add_user(u)
        dev.add_user(u)
        users.append(u)

    # Enable audit records on the engine.
    builder.permission_engine.audit_enabled = True

    return builder, corp, dev, users, {
        "read_doc": read_doc,
        "commit_code": commit_code,
        "deploy": deploy,
    }


# =====================================================================
# 2. Synthetic traffic generator
# =====================================================================
def simulate_traffic(builder, users, ops, t_minutes: int) -> None:
    """Generate one step of access requests.

    Most users access resources they legitimately hold. A few
    'suspicious' users attempt operations they do not hold — the
    permission engine will ALLOW or DENY them accordingly, and audit
    records are written.
    """
    engine = builder.permission_engine
    corp = builder.root
    _op_list = list(ops.values())

    # 5 % of requests come from a suspicious pattern: off-hours, high
    # attempt rate on privileged operations.
    is_off_hours = (t_minutes % 60) < 20 or (t_minutes % 60) > 50

    for _ in range(random.randint(1, 4)):
        user = random.choice(users)

        if is_off_hours and random.random() < 0.4:
            # Suspicious: try privileged operations they may not hold.
            op = random.choice([ops["deploy"], ops["commit_code"]])
        else:
            # Legitimate: try one of their permissions.
            role = corp.roles[user.attributes["role_kind"]]
            if not role.base_permissions:
                continue
            op = random.choice(list(role.base_permissions))

        engine.decide(user, op, corp)


# =====================================================================
# 3. Neural risk scorer
# =====================================================================
def build_risk_detector() -> AnomalyDetector:
    """Autoencoder trained on normal access patterns.

    Features per request:
      [user_idx, hour_of_day, minute_of_hour, operation_idx]
    Normal traffic: work hours (8–18) and low-privilege operations.
    Anomalous traffic: off-hours and high-privilege operations.
    """
    rng = np.random.default_rng(SEED)
    n = 800
    # Normal training data: work-hour, low-privilege attempts.
    user_idx = rng.integers(0, N_USERS, n)
    hour     = rng.normal(13, 3, n).clip(8, 18)
    minute   = rng.integers(0, 60, n)
    op_idx   = rng.choice([0, 1], n, p=[0.7, 0.3])   # read_doc or commit

    X = np.column_stack([user_idx / N_USERS, hour / 24.0,
                         minute / 60.0, op_idx / 2.0])

    detector = AnomalyDetector(
        name="access_risk",
        input_dim=4,
        latent_dim=2,
        threshold=0.5,
        seed=SEED,
    )
    detector.fit(X, epochs=300, lr=0.05)
    return detector


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class SecurityDaemon(Daemon):
    """Reads the newest audit records, scores them, and emits critical
    signals for high-risk events.

    Runs synchronously inside the DaemonManager's thread pool.
    """

    def __init__(self, builder, users, ops, detector, parent=None,
                 check_every: int = 5):
        super().__init__("SecurityDaemon", parent=parent, interval=0.05)
        self.builder = builder
        self.users = {u.name: u for u in users}
        self.ops = ops
        self.detector = detector
        self.check_every = check_every
        self._cursor = 0                # index into the audit list
        self._scored = 0
        self._flagged = 0

    # -----------------------------------------------------------------
    def _features(self, record) -> np.ndarray:
        """Convert one DecisionRecord into a feature vector."""
        # Derive user_idx and op_idx from the alphabetical ordering.
        user_names = sorted(self.users.keys())
        op_names = sorted(self.ops.keys())
        try:
            ui = user_names.index(record.user) / max(len(user_names) - 1, 1)
        except ValueError:
            ui = 0.0
        try:
            oi = op_names.index(record.operation.split(".")[-1]) \
                 / max(len(op_names) - 1, 1)
        except ValueError:
            oi = 0.0
        ts = record.timestamp.astimezone(timezone.utc)
        hour_norm = (ts.hour + ts.minute / 60.0) / 24.0
        minute_norm = ts.minute / 60.0
        return np.array([ui, hour_norm, minute_norm, oi])

    # -----------------------------------------------------------------
    def monitor(self):
        audit = self.builder.permission_engine.audit
        # Score any new records since the last tick.
        new_records = audit[self._cursor:]
        self._cursor = len(audit)

        for record in new_records:
            self._scored += 1
            features = self._features(record)
            if self.detector.is_anomalous(features):
                self._flagged += 1
                score = self.detector.score(features)
                self.emit_signal(
                    DaemonSignal.STATE_CRITICAL,
                    {
                        "event": "high_risk_access",
                        "user": record.user,
                        "operation": record.operation,
                        "zone": record.zone,
                        "score": round(score, 3),
                        "at": record.timestamp.isoformat(),
                    },
                )

    # -----------------------------------------------------------------
    def stats(self) -> dict[str, int]:
        return {"scored": self._scored, "flagged": self._flagged}


class SentinelDaemon(Daemon):
    """Root daemon. On a critical signal, revokes the offender's
    permissions in the affected zone and records the event."""

    def __init__(self, builder, parent=None):
        super().__init__("SentinelDaemon", parent=parent, interval=0.1)
        self.builder = builder
        self.revocations: list[tuple] = []
        self._revoked_users: set[str] = set()

    def on_signal(self, signal, payload, source=None):
        if signal is not DaemonSignal.STATE_CRITICAL:
            return
        if payload.get("event") != "high_risk_access":
            return

        user_name = payload["user"]
        if user_name in self._revoked_users:
            return                      # already locked down

        # Find the user and revoke every role they hold.
        target_user = None
        for zone in self.builder.root.walk():
            if user_name in zone.users:
                target_user = zone.users[user_name]
                break
        if target_user is None:
            return

        for role_name in list(target_user.roles):
            # Locate the role in the root zone.
            role = self.builder.root.roles.get(role_name)
            if role is None:
                continue
            for op in list(role.base_permissions):
                self.builder.root.revoke(role, op)

        target_user.attributes.set("revoked", True)
        self._revoked_users.add(user_name)
        self.revocations.append((user_name, payload["operation"],
                                 payload["score"]))


# =====================================================================
# 5. Main — async orchestration
# =====================================================================
async def run_simulation() -> None:
    print("=" * 68)
    print("Security daemon demonstration")
    print("=" * 68)

    builder, corp, users, ops = build_target()
    detector = build_risk_detector()

    # ---- Daemon hierarchy ------------------------------------------
    sentinel = SentinelDaemon(builder)
    security = SecurityDaemon(builder, users, ops, detector,
                              parent=sentinel)
    builder.add_daemon(sentinel)
    builder.add_daemon(security)

    # ---- Spawn a producer task that drives traffic ------------------
    async def traffic_producer():
        for minute in range(N_TICKS):
            simulate_traffic(builder, users, ops, minute)
            await asyncio.sleep(0.02)      # 20 ms per simulated minute

    # ---- Run the daemons concurrently with the producer -------------
    await asyncio.gather(
        traffic_producer(),
        builder.daemon_manager.run(duration=N_TICKS * 0.02 + 0.1),
    )

    # ---- Report -----------------------------------------------------
    print()
    print(f"Requests logged    : {len(builder.permission_engine.audit)}")
    print(f"Events scored      : {security.stats()['scored']}")
    print(f"High-risk flags    : {security.stats()['flagged']}")
    print(f"Users revoked      : {len(sentinel.revocations)}")
    print()
    if sentinel.revocations:
        print("Revocations:")
        for user_name, operation, score in sentinel.revocations[:10]:
            print(f"  {user_name:<10} on {operation:<24} score={score}")

    # ---- Verify that revoked users are now denied ------------------
    engine = builder.permission_engine
    if sentinel.revocations:
        offender = sentinel.revocations[0][0]
        target = next(u for u in users if u.name == offender)
        # Try any privileged op held by their original role.
        sample_op = ops["deploy"]
        print()
        print(f"Post-revocation check for {offender}:")
        print(f"  {sample_op.qualified_name:<24} : "
              f"{engine.decide(target, sample_op, corp).name}")


def main() -> None:
    asyncio.run(run_simulation())


if __name__ == "__main__":
    main()