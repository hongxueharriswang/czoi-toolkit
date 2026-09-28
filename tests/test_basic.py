"""Basic acceptance tests for the CZOI toolkit."""
import numpy as np
import pytest

from czoi import (
    AnomalyDetector,
    Application,
    AtomicZone,
    CompositeZone,
    ConstraintManager,
    Decision,
    EmbeddingService,
    Operation,
    PermissionEngine,
    Predictor,
    PropertyStore,
    Role,
    RoleMiner,
    User,
    ZoneContainmentError,
)


# ---------------------------------------------------------------------
# Zone recursion & containment
# ---------------------------------------------------------------------
def test_recursive_zone_is_full_10tuple():
    root = CompositeZone("root")
    child = CompositeZone("child", parent=root)
    for attr in ("zones", "roles", "users", "applications",
                 "operations", "neural", "daemons"):
        assert hasattr(child, attr)


def test_atomic_zone_rejects_children():
    leaf = AtomicZone("leaf")
    with pytest.raises(TypeError):
        leaf.add_zone(AtomicZone("forbidden"))


def test_role_inheritance_downward():
    root = CompositeZone("root")
    child = CompositeZone("child", parent=root)
    r = Role("Doctor")
    root.add_role(r)
    assert "Doctor" in child.roles

    r2 = Role("Nurse")
    root.add_role(r2)               # added *after* child exists
    assert "Nurse" in child.roles


def test_user_containment_principle():
    root = CompositeZone("root")
    child = CompositeZone("child", parent=root)
    u = User("alice")
    with pytest.raises(ZoneContainmentError):
        child.add_user(u)
    root.add_user(u)
    child.add_user(u)               # now fine


def test_ancestry_and_depth():
    root = CompositeZone("root")
    a = CompositeZone("a", parent=root)
    b = CompositeZone("b", parent=a)
    assert [n.name for n in b.ancestry()] == ["root", "a", "b"]
    assert b.depth() == 2


# ---------------------------------------------------------------------
# Permission engine
# ---------------------------------------------------------------------
def test_recursive_permission_allow():
    root = CompositeZone("root")
    child = CompositeZone("child", parent=root)
    app = Application("EMR", zone=root)
    op = app.add_operation(Operation("view"))
    root.add_application(app)
    doctor = Role("Doctor", base_permissions=[op])
    root.add_role(doctor)
    alice = User("alice", roles={"Doctor"})
    root.add_user(alice)
    child.add_user(alice)

    engine = PermissionEngine()
    assert engine.decide(alice, op, child) is Decision.ALLOW


def test_permission_denied_for_unknown_role():
    root = CompositeZone("root")
    app = Application("EMR", zone=root)
    op = app.add_operation(Operation("view"))
    root.add_application(app)
    bob = User("bob", roles=set())
    root.add_user(bob)

    engine = PermissionEngine()
    assert engine.decide(bob, op, root) is Decision.DENY


# ---------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------
def test_property_store_types():
    ps = PropertyStore()
    ps.set("clearance", 5, type_hint="int")
    assert ps.get("clearance") == 5
    with pytest.raises(TypeError):
        ps.set("clearance", "high", type_hint="int")


# ---------------------------------------------------------------------
# Neural components
# ---------------------------------------------------------------------
def test_predictor_threshold():
    p = Predictor("sepsis", lambda f: 0.9 if f["lactate"] > 3 else 0.1,
                  threshold=0.85)
    assert p.fires({"lactate": 3.5})
    assert not p.fires({"lactate": 1.0})


def test_anomaly_detector_detects_outlier():
    det = AnomalyDetector("net", input_dim=4, threshold=0.5)
    # Near-zero vector: reconstruction error low
    assert not det.is_anomalous(np.zeros(4))
    # Large vector: reconstruction error high
    assert det.is_anomalous(np.ones(4) * 10)


def test_role_miner_suggests_roles():
    X = np.array([
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 1, 1],
        [0, 0, 1, 1],
    ], dtype=float)
    ops = ["A.x", "A.y", "B.x", "B.y"]
    miner = RoleMiner(min_cluster_size=2)
    result = miner.mine(X, ops)
    assert result.n_clusters >= 1
    assert all(len(v) > 0 for v in result.suggested_roles.values())


# ---------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------
def test_embedding_similarity_positive():
    svc = EmbeddingService(dimension=32)
    a = svc.embed("EMR.view_patient")
    b = svc.embed("EMR.view_patient")
    c = svc.embed("Payroll.process")
    assert svc.similarity(a, b) > svc.similarity(a, c) - 0.01


# ---------------------------------------------------------------------
# UniLog bridge (skip if unilog not installed)
# ---------------------------------------------------------------------
unilog = pytest.importorskip("unilog", reason="unilog-toolkit not installed")


def test_constraint_manager_parses_and_checks():
    from czoi import CompositeZone, ConstraintManager
    root = CompositeZone("root")
    cm = ConstraintManager()
    root.set_constraints(cm)
    cm.add_identity("""
        signature { sort S; predicate p(s: S); }
        forall s: S . p(s) -> p(s)
    """)
    results = cm.check_all()
    assert results["I"] is True

def test_shared_constraint_manager_serves_whole_tree():
    """The manager must remain bound to the root even after children attach."""
    from czoi import CZOABuilder
    b = CZOABuilder("root")
    child = b.add_zone("child")
    assert b.constraint_manager.root is b.root
    assert child.constraints is b.constraint_manager


def test_permission_cache_invalidated_on_grant():
    from czoi import (
        Application,
        CompositeZone,
        Decision,
        Operation,
        PermissionEngine,
        Role,
        User,
    )
    root = CompositeZone("root")
    engine = PermissionEngine()
    root.set_permission_engine(engine)
    app = Application("A", zone=root)
    op = app.add_operation(Operation("do"))
    root.add_application(app)
    r = Role("R")
    root.add_role(r)
    u = User("u", roles={"R"})
    root.add_user(u)

    assert engine.decide(u, op, root) is Decision.DENY
    root.grant(r, op)
    assert engine.decide(u, op, root) is Decision.ALLOW


def test_anomaly_detector_trains_and_detects():
    import numpy as np

    from czoi import AnomalyDetector
    rng = np.random.default_rng(0)
    X = rng.normal(0, 0.1, (200, 4))
    det = AnomalyDetector("net", input_dim=4)
    det.fit(X, epochs=100)
    assert not det.is_anomalous(np.zeros(4))
    assert det.is_anomalous(np.ones(4) * 5)


def test_role_miner_produces_clusters():
    import numpy as np

    from czoi import RoleMiner
    X = np.array([
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 1, 1],
        [0, 0, 1, 1],
    ], dtype=float)
    miner = RoleMiner(min_cluster_size=2, autoencoder_epochs=50)
    result = miner.mine(X, ["A.x", "A.y", "B.x", "B.y"])
    assert result.n_clusters >= 2
    assert all(v for v in result.suggested_roles.values())


def test_embedding_alignment_training():
    import numpy as np

    from czoi import EmbeddingService
    svc = EmbeddingService(dimension=8)
    a1 = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=float)
    a2 = np.array([0.9, 0.1, 0, 0, 0, 0, 0, 0], dtype=float)
    b = np.array([0, 0, 0, 0, 1, 0, 0, 0], dtype=float)
    svc.train_alignment(
        positives=[(a1, a2)],
        negatives=[(a1, b)],
        epochs=50,
    )
    assert svc.similarity(a1, a2) > svc.similarity(a1, b)


def test_daemon_hierarchy_signals_propagate():
    from czoi import Daemon, DaemonSignal
    received = []

    class Child(Daemon):
        def monitor(self):
            self.emit_signal(DaemonSignal.STATE_CRITICAL, {"x": 1})

    class Parent(Daemon):
        def on_signal(self, signal, payload, source=None):
            received.append((signal, payload))

    root = Parent("root")
    child = Child("child", parent=root)
    child.safe_monitor()
    assert received == [(DaemonSignal.STATE_CRITICAL, {"x": 1})]


def test_composite_zone_clone_deep_copies():
    from czoi import Application, CompositeZone, Operation, Role
    root = CompositeZone("root")
    app = Application("A", zone=root)
    op = app.add_operation(Operation("do"))
    root.add_application(app)
    r = Role("R", base_permissions=[op])
    root.add_role(r)

    clone = root.clone("clone")
    assert "R" in clone.roles
    assert clone.roles["R"] is not root.roles["R"]
    assert clone.roles["R"].base_permissions == {op}  # shared ops