# CZOI Toolkit

**A Python implementation of the Constrained Zoned-Object Architecture (CZOA) for building secure and intelligent integrated organizational systems.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![UniLog](https://img.shields.io/badge/unilog--toolkit-%E2%89%A52.0-orange)](https://github.com/hongxueharriswang/unilog-toolkit)

---

## What is CZOA?

The **Constrained Zoned-Object Architecture (CZOA)** is a unified formalism that bridges two previously disconnected fields:

- **Theories of intelligence** — how adaptive behaviour emerges from hierarchical composition, constraint satisfaction, and learning.
- **Enterprise system engineering** — how to build secure, maintainable systems aligned with organisational structure.

CZOA shows that enterprise systems are a natural species of intelligent systems. Every organizational unit (a hospital, a department, a factory cell, a drone sector) is modelled as a **zone** — a fully autonomous subsystem with its own roles, operations, neural components, constraints, and daemons — that is recursively composed into a system-of-systems.

The CZOI toolkit is the reference implementation. It provides:

- A recursive zone tree where every zone is itself a full CZOA system.
- A two-stage permission calculus (Φ) with parent override and caching.
- Integration with the [UniLog toolkit](https://github.com/hongxueharriswang/unilog-toolkit) for formal constraint specification across eleven logic families.
- Hierarchical constraint daemons (Δ) with signal propagation.
- Neural components (N) for role mining, anomaly detection, and domain-specific prediction.
- Semantic embeddings (E) with a global alignment functor for cross-zone reasoning.

**Paper**: H. Wang, *"Constrained Zoned-Object Architecture (CZOA): A Unified Framework for Building Secure and Intelligent Integrated Organizational Systems"*, 2026.

**Related work**:
- COH: [Constrained Object Hierarchies](https://doi.org/10.3390/computers14110478) (Wang 2025)
- ZRB: A Formalized Zoned Role-Based Framework (Wang 2026)
- UniLog: [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit)

---

## Installation

```bash
# Core toolkit
pip install czoi-toolkit

# With optional features
pip install czoi-toolkit[neural]     # scikit-learn for role mining
pip install czoi-toolkit[embedding]  # sentence-transformers for semantic embeddings
pip install czoi-toolkit[dev]        # pytest and dev tools
```

The toolkit depends on `unilog-toolkit>=2.0` and `numpy>=1.19`.

### From source

```bash
git clone https://github.com/hongxueharriswang/czoi-toolkit.git
cd czoi-toolkit
pip install -e ".[dev]"
```

---

## Quickstart

```python
from czoi import CZOABuilder, Application, Operation, Role, User, Decision

# ---- 1. Build the recursive zone tree -------------------------------
builder = CZOABuilder("RegionalHealthAuthority")

hospital = builder.add_zone("CityHospitalA")
emergency = builder.add_zone("Emergency", parent=hospital, atomic=True)

# ---- 2. Define operations and roles ---------------------------------
app = Application("EMR", zone=hospital)
prescribe = app.add_operation(Operation("prescribe"))
dispense  = app.add_operation(Operation("dispense"))
hospital.add_application(app)

attending = Role("AttendingPhysician", zone=hospital,
                 base_permissions=[prescribe])
nurse     = Role("Nurse", zone=hospital,
                 base_permissions=[dispense])
hospital.add_role(attending)
hospital.add_role(nurse)
attending.add_junior(nurse)   # Attending is senior to Nurse

# ---- 3. Create users (containment enforced automatically) -----------
alice = User("alice", roles={"AttendingPhysician"})
bob   = User("bob",   roles={"Nurse"})
builder.root.add_user(alice); hospital.add_user(alice); emergency.add_user(alice)
builder.root.add_user(bob);   hospital.add_user(bob);   emergency.add_user(bob)

# ---- 4. Check permissions through the real engine -------------------
engine = builder.permission_engine
print(engine.decide(alice, prescribe, emergency).name)  # ALLOW
print(engine.decide(bob,   prescribe, emergency).name)  # INCONCLUSIVE
print(engine.decide(bob,   dispense,  emergency).name)  # ALLOW
```

---

## Core Concepts

### Zones are recursive systems

Every zone is itself a full CZOA 10-tuple:

```
S = (Z, R, U, A, O, N, E, Γ, Φ, Δ)
```

| Component | Meaning |
|---|---|
| **Z** | Child zones (recursive subsystems) |
| **R** | Roles with base permissions and intra-zone seniority |
| **U** | Users (containment: `U_child ⊆ U_parent`) |
| **A** | Applications — structural modules |
| **O** | Operations — atomic permission targets |
| **N** | Neural components (learnable functions) |
| **E** | Embeddings + global alignment functor |
| **Γ** | Constraint system (I, T, G, C) |
| **Φ** | Permission calculus (two-stage recursive) |
| **Δ** | Constraint daemons (continuous monitoring) |

Zones come in two concrete types:

- **`CompositeZone`** — has children.
- **`AtomicZone`** — a leaf; calling `add_zone` raises `TypeError`, matching `Z_z = ∅`.

### Operations are the permission target — not applications

Permissions are granted on **operations**, never on applications. An operation is uniquely identified by `application.operation` (e.g. `EMR.prescribe`). This preserves the orthogonality of the ten components: applications provide deployability and grouping; operations provide the granular units for fine-grained security and auditing.

```python
# Correct
role.grant(operation)

# Incorrect (applications are not permission targets)
# role.grant(application)
```

### Two-stage permission calculus

```
P_effective(r, z) =
    P_base^z(r)
    ∪ ⋃_{r' ∈ seniority_z(r)} P_base^z(r')
    ∪ ⋃_{z_child ∈ Z_z} γ(z_child, r)
    ∪ Φ_parent^{-1}(r, z)
```

When a user requests an operation:

1. **Local check** — evaluates the user's roles in the current zone and its access constraints.
2. **Parent override** — if the local decision is `INCONCLUSIVE` or the operation touches cross-subsystem resources, the engine recurses to the parent zone.

```python
engine.decide(user, operation, zone)  # returns Decision.ALLOW / DENY / INCONCLUSIVE
```

### Constraints via UniLog

The CZOI toolkit delegates constraint specification to the [UniLog toolkit](https://github.com/hongxueharriswang/unilog-toolkit), a fibred logic framework with eleven solvers (classical, modal, epistemic, deontic, temporal, dynamic, description, probabilistic, non-monotonic, preference, fuzzy).

```python
builder.add_access_constraint("""
    signature {
        sort User, Role;
        constant Doctor : Role;
        constant Auditor : Role;
        predicate hasRole(u: User, r: Role);
    }
    forall u: User .
        not (hasRole(u, Doctor) and hasRole(u, Auditor))
""")
```

The constraint is evaluated on every permission check through the `ConstraintManager.is_satisfied` hook.

### Hierarchical daemons

Daemons are continuous monitors that emit typed signals up a daemon tree.

```python
from czoi import Daemon, DaemonSignal

class BatteryDaemon(Daemon):
    def __init__(self, robots, threshold=0.2, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.robots = robots
        self.threshold = threshold

    def monitor(self):
        for r in self.robots:
            if r.attributes.get("battery", 1.0) < self.threshold:
                self.emit_signal(DaemonSignal.STATE_WARNING,
                                 {"robot": r.name})

class FleetDaemon(Daemon):
    def on_signal(self, signal, payload, source=None):
        # Handle child signals; propagate upward if there is a parent
        ...
```

The `DaemonManager` runs daemons asynchronously via a thread pool so a slow monitor never blocks the event loop.

```python
builder.add_daemon(fleet)
builder.add_daemon(battery)
await builder.daemon_manager.run(duration=60.0)
```

### Neural components

Three built-in neural components are provided:

- **`Predictor`** — a trainable linear/logistic model with `fit`, `predict`, `fires`.
- **`AnomalyDetector`** — an autoencoder with a calibrated threshold; `score` and `is_anomalous`.
- **`RoleMiner`** — unsupervised permission mining via an autoencoder + clustering (paper §5.1).

```python
from czoi import Predictor, AnomalyDetector, RoleMiner
import numpy as np

model = Predictor("sepsis", threshold=0.85)
model.fit(X_train, y_train, epochs=500)

detector = AnomalyDetector("access", input_dim=5, latent_dim=3)
detector.fit(X_normal, epochs=300)
detector.is_anomalous(x)   # -> bool

miner = RoleMiner(latent_dim=8, min_cluster_size=3)
result = miner.mine(X_binary, operation_names)
result.suggested_roles      # {"MinedRole_0": ["read_doc", ...], ...}
```

### Semantic embeddings

```python
from czoi import EmbeddingService

emb = EmbeddingService(dimension=64)
v1 = emb.embed_operation(operation)
v2 = emb.embed_role(role)
score = emb.similarity(v1, v2)

# Contrastive training of the global alignment functor
emb.train_alignment(positives=[(a, b)], negatives=[(a, c)])
```

### Adaptive access control

The toolkit supports dynamic permission adjustment that preserves safety (paper Theorem 7):

```python
builder.root.grant(role, operation)   # invalidates the permission cache
builder.root.revoke(role, operation)  # invalidates the permission cache
```

A `NeuralContribution` hook lets a neural component influence a decision:

```python
from czoi import NeuralContribution

def surge_hook(user, operation, zone, base):
    if (operation.name == "prescribe"
            and zone.properties.get("surge_active", False)):
        return Decision.ALLOW
    return base

builder.permission_engine.set_neural_contribution(
    NeuralContribution(surge_hook)
)
```

---

## Project Layout

```
czoi/
├── core/               # exceptions, types
├── properties/         # typed attribute store
├── operations/         # Operation
├── roles/              # Application, Role, User
├── zones/              # ZoneBase, AtomicZone, CompositeZone (recursive)
├── permissions/        # PermissionEngine (Φ)
├── constraints/        # ConstraintManager (Γ) — bridges UniLog
├── neural/             # Predictor, AnomalyDetector, RoleMiner
├── embedding/          # EmbeddingService (E)
├── daemons/            # Daemon base, DaemonManager (Δ)
└── toolkit/            # CZOABuilder factory

examples/
├── quickstart.py
├── nhs_simulation.py
├── unilog_constraints.py
└── ...

tests/
└── test_basic.py
```

---

## Examples

The `examples/` directory contains runnable demonstrations:

| Example | Demonstrates |
|---|---|
| `quickstart.py` | Recursive zones, roles, seniority, UniLog constraint |
| `nhs_simulation.py` | Surge handling with daemons and adaptive permissions |
| `unilog_constraints.py` | The four families of constraints (I, T, G, C) |

Real-world domain simulations are provided in the top-level `automation-*.py` and `css-*.py` scripts:

| Script | Domain |
|---|---|
| `automation-01.py` | Warehouse robot transport |
| `automation-02.py` | Multi-AGV warehouse with zone capacity |
| `automation-03.py` | Self-driving ride-hailing fleet |
| `automation-04.py` | Manufacturing assembly line |
| `automation-05.py` | Drone swarm coverage |
| `css-01.py` | Opinion dynamics on social networks |
| `css-02.py` | Building evacuation |
| `css-03.py` | Market microstructure |
| `css-04.py` | Multi-city SIR epidemic |
| `css-05.py` | Urban traffic flow |
| `czoa-nhs-simulation-1-08.py` | Hospital surge (paired A/B) |
| `czoa-gfts-simulation-2-08.py` | Trading desk with circuit breaker |
| `czoa-sci-simulation-3-08.py` | Smart-city incident response |
| `czoa-uams-simulation-4-08.py` | University registration + FERPA |
| `czoa-scms-simulation-5-08.py` | Supply chain distribution center |

Each simulation compares baseline RBAC against CZOA and reports genuine measured improvements (mean, 95 % CI) rather than hard-coded constants.

---

## Testing

```bash
pytest -q                          # all tests
pytest -q tests/test_basic.py      # focused on core behaviour
```

The test suite covers:

- Recursive zone construction and containment.
- Role inheritance and seniority.
- Permission calculus (local, parent override, denial).
- UniLog constraint parsing and evaluation.
- Neural components (fit, predict, anomaly detection).
- Daemon hierarchy and signal propagation.
- Embedding similarity and alignment.

---

## Design Principles

1. **Minimality** — the ten components of the CZOI tuple are mutually orthogonal. No redundancy, no hidden state.
2. **Recursion** — every zone is a full system. Any subsystem can be developed, tested, and deployed independently while remaining governed by parent constraints.
3. **Containment** — `U_child ⊆ U_parent` is enforced at user-registration time.
4. **Operation-level permissions** — access control is maximally granular; the audit trail is precise.
5. **Formal constraints** — all organisational policy is expressible in UniLog and evaluated against live system state.
6. **Defensive monitoring** — daemons provide continuous compliance verification, independent of the permission engine.
7. **Safety-preserving adaptation** — every adaptive update preserves monotonicity, identity constraints, and audit completeness (paper Theorem 7).

---

## UniLog Integration

The toolkit depends on [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit) for constraint specification. UniLog provides:

- **Eleven solvers**: classical, modal, epistemic, deontic, temporal, dynamic, description, probabilistic, non-monotonic, preference, fuzzy.
- **A concrete syntax** (UniLang) accepting both ASCII and Unicode forms.
- **SMT-based verification** for bounded state spaces.
- **Formal soundness guarantees** witnessed by the toolkit's test suite.

The `ConstraintManager` in CZOI builds a `CZOIModel` (implements the UniLog `Model` ABC) from a live zone and evaluates every loaded formula against it.

---

## Roadmap

| Feature | Status |
|---|---|
| Recursive zones, permission calculus, constraints, daemons, neural, embeddings | ✅ Shipped |
| UniLog toolkit integration | ✅ Shipped |
| First-class `GammaMapping` type | 🔄 In progress |
| Vector store adapters (pgvector, Chroma) | 🔄 In progress |
| Web framework integrations (Django, FastAPI, Flask) | 🔄 In progress |
| Distributed deployment | 📋 Planned |
| Federated CZOA across organizations | 📋 Planned |
| Automatic daemon synthesis from UniLang policies | 📋 Planned |

---

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` first.

```bash
# Set up a development environment
git clone https://github.com/hongxueharriswang/czoi-toolkit.git
cd czoi-toolkit
pip install -e ".[dev,neural,embedding]"

# Run the tests
pytest -q

# Check formatting
ruff check czoi/
```

Pull requests should:

- Include tests for any new behaviour.
- Preserve the ten-component minimality (no new state on `ZoneBase`).
- Update the docstring of any modified public API.
- Run clean under `pytest -q` and `ruff check`.

---

## Citation

If you use this toolkit in academic work, please cite:

```bibtex
@article{wang2026czoa,
  author  = {Wang, Harris},
  title   = {Constrained Zoned-Object Architecture (CZOA): A Unified
             Framework for Building Secure and Intelligent Integrated
             Organizational Systems},
  journal = {Preprint},
  year    = {2026}
}

@article{wang2026unilog,
  author  = {Wang, Harris},
  title   = {UniLog: A Unified Logic Framework for Constrained Object
             Hierarchies and Constrained Zone-Object Architecture},
  journal = {Preprint},
  year    = {2026}
}

@article{wang2025coh,
  author  = {Wang, Harris},
  title   = {Constrained Object Hierarchies as a Unified Theoretical
             Model for Intelligence and Intelligent Systems},
  journal = {Computers},
  volume  = {14},
  pages   = {478},
  year    = {2025}
}
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

The CZOI toolkit builds directly on:

- The **UniLog toolkit** for its constraint engine.
- The **CZOA formalism** and its predecessors — **COH** and **ZRB**.
- The **Viable System Model** (Beer 1972) for its hierarchical-organisation inspiration.
- Two decades of research on **role-based access control** (RBAC), **attribute-based access control** (ABAC), and **separation of duty** in enterprise systems.

---

## Contact

- **Author**: Harris Wang — [harrisw@athabascau.ca](mailto:harrisw@athabascau.ca)
- **Issues**: [github.com/hongxueharriswang/czoi-toolkit/issues](https://github.com/hongxueharriswang/czoi-toolkit/issues)
- **Related**: [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit)