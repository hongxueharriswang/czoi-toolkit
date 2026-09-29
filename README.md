# CZOI Toolkit

**A Python implementation of the Constrained Zoned-Object Architecture (CZOA) for building secure, intelligent, and integrated organizational systems.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![UniLog](https://img.shields.io/badge/unilog--toolkit-%E2%89%A52.0-orange)](https://github.com/hongxueharriswang/unilog-toolkit)

---

## The Integration Crisis

Most modern organizations are not coherent systems. They are **archipelagos of systems** — the legacy ERP that has run the business for twenty years, the department that procured its own CRM, the acquisition that arrived with its own identity provider, the SaaS platform that became critical without anyone planning for it, the analytics stack that nobody quite remembers deploying.

Attempts to unify these landscapes have traditionally taken one of three forms — and all three are broken:

- **Centralize.** Collapse everything into one monolithic system. This destroys local autonomy, forfeits institutional knowledge, and takes years to deliver.
- **Federate loosely.** Connect systems through point-to-point adapters. This preserves autonomy but abandons formal guarantees — no unified policy, no unified audit, no way to reason about cross-system behaviour.
- **Rewrite everything.** Clean and modern on paper. Bankrupting in practice.

What is missing is a framework that **preserves local autonomy while providing global integration guarantees**. A framework in which each subsystem retains its own models, its own policies, its own evolution — while the composition as a whole remains verifiably coherent.

**The CZOI toolkit is that framework.**

---

## What is CZOA?

The **Constrained Zoned-Object Architecture (CZOA)** is a unified formalism that addresses two integration crises simultaneously:

- The **organizational** crisis — fragmented systems, heterogeneous policy, siloed intelligence.
- The **theoretical** crisis — the separation between formal security guarantees and adaptive intelligence.

Both crises share a solution. CZOA shows that the **recursive zone tree** — the same structure that mirrors an organization's hierarchy — is *simultaneously*:

1. The natural representation of organizational heterogeneity.
2. The vehicle for preserving local autonomy.
3. The formal mechanism by which cross-subsystem integration occurs.

Every organizational unit becomes a **zone**. Every zone is itself a full CZOI system — with its own roles, operations, neural components, constraints, and daemons. Zones can be:
- **Native CZOI subsystems** — built directly with the toolkit.
- **Adapter zones** — wrapping legacy systems, third-party SaaS, or external partners without modifying them.

Composition of zones is a formal operation with verifiable properties. Integration, in CZOI, is not an afterthought — it is the primitive.

**Paper**: H. Wang, *"Constrained Zoned-Object Architecture (CZOA): A Unified Framework for Integrating Fragmented Systems, Secure Access, and Organizational Intelligence"*, 2026.

**Related work**:
- COH: [Constrained Object Hierarchies](https://doi.org/10.3390/computers14110478) (Wang 2025)
- ZRB: A Formalized Zoned Role-Based Framework (Wang 2026)
- UniLog: [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit)

---

## What This Toolkit Gives You

**For building new systems:**

- A recursive zone tree where every zone is itself a full CZOA system.
- A two-stage permission calculus (Φ) with parent override and caching.
- Integration with the [UniLog toolkit](https://github.com/hongxueharriswang/unilog-toolkit) for formal constraints across eleven logic families.
- Hierarchical constraint daemons (Δ) with signal propagation.
- Neural components (N) for role mining, anomaly detection, and domain-specific prediction.
- Semantic embeddings (E) with a global alignment functor for cross-zone reasoning.

**For integrating existing systems:**

- **Adapter zones** — wrap legacy systems without modifying them.
- **Federation builder** — compose independent CZOI systems under shared governance.
- **Cross-zone integration relations** (ι) — formalise permission flow, shared constraints, cross-zone monitoring, and vocabulary alignment.
- **Automatic role equivalence discovery** — find semantically equivalent roles across subsystems using embeddings.
- **Zero-touch legacy integration** — no code changes required in the systems being integrated.
- **Compositional preservation** — the Integration Theorem gives formal guarantees that composing systems preserves each one's security invariants.

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

## Quickstart — Building a Native System

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
for u in (alice, bob):
    for z in emergency.ancestry():
        z.add_user(u)

# ---- 4. Check permissions through the real engine -------------------
engine = builder.permission_engine
print(engine.decide(alice, prescribe, emergency).name)  # ALLOW
print(engine.decide(bob,   prescribe, emergency).name)  # INCONCLUSIVE
print(engine.decide(bob,   dispense,  emergency).name)  # ALLOW
```

---

## Quickstart — Integrating a Legacy System

Suppose you have a legacy HR system that you cannot modify. Rather than rewriting it or building point-to-point adapters, you wrap it in an **adapter zone**. From the federation's perspective, the legacy system is now a first-class CZOI subsystem.

```python
from czoi import (
    AdapterZone, CZOABuilder, FederationBuilder, Operation, Role, User,
)

# ---- 1. Define the adapter's CZOI-facing interface ------------------
legacy_hr = AdapterZone(
    name="LegacyHR",
    adapter=MyLegacyHRAdapter(),    # user-supplied adapter
)

view_employee = Operation("view_employee")
edit_employee = Operation("edit_employee")
legacy_hr.expose_operations({
    "view_employee": view_employee,
    "edit_employee": edit_employee,
})

hr_viewer = Role("HRViewer",  zone=legacy_hr,
                 base_permissions=[view_employee])
hr_editor = Role("HREditor",  zone=legacy_hr,
                 base_permissions=[view_employee, edit_employee])
hr_editor.add_junior(hr_viewer)
legacy_hr.add_role(hr_viewer)
legacy_hr.add_role(hr_editor)

# ---- 2. Federate with a newly built subsystem -----------------------
fed = FederationBuilder("MergedCorp")
fed.adopt_subsystem(legacy_hr, name="LegacyHR")
fed.adopt_subsystem(new_builder, name="NewPlatform")

# ---- 3. Share policy across the federation --------------------------
fed.share_constraint("""
    signature {
        sort User, Role;
        constant HRViewer : Role;
        constant FinanceApprover : Role;
        predicate hasRole(u: User, r: Role);
    }
    forall u: User .
        not (hasRole(u, HRViewer) and hasRole(u, FinanceApprover))
""")

# ---- 4. Wire cross-zone monitoring ----------------------------------
fed.add_cross_zone_daemon(FederationHealthDaemon())

# ---- 5. The federation is a full CZOI system ------------------------
engine = fed.permission_engine
print(engine.decide(alice, view_employee, legacy_hr).name)
```

**No changes were made to the legacy system.** Its behaviour is opaque; only the interface is declared. The federation treats it identically to a natively built CZOI zone.

---

## The Integration Theorem

The toolkit ships with a formal guarantee that is unique in the enterprise integration space:

> **Theorem (Compositional Preservation of Security).** Let $S_1$ and $S_2$ be two independent, soundly integrated CZOI systems with no shared operations. Then the composed federation $S = S_1 \oplus S_2$ under a new common parent satisfies:
>
> 1. $S$ is a well-formed CZOI system.
> 2. Every identity constraint of $S_1$ and $S_2$ holds in $S$.
> 3. Every access constraint of $S_1$ and $S_2$ holds in $S$.
> 4. Any additional constraint on the parent is enforced for both subsystems.

**Corollary (Post-Merger Integration Guarantee).** In a post-merger scenario where two legacy organizations are integrated under a new parent authority, if both legacy systems are soundly integrated CZOI systems, the merger preserves each legacy system's security guarantees while enabling explicit cross-system policy at the authority level.

This is not a claim about tooling. It is a mathematical property. You can verify your integration is sound; you cannot *in general* verify an ad-hoc federation.

In the toolkit's post-merger case study (§7.7 of the paper), a regional health authority formed by merging two legacy health authorities achieved:

| Metric | Baseline | CZOI | Improvement |
|---|---|---|---|
| Integration completion time | 180 days | 70 days | **61% reduction** |
| Duplicate role definitions | 187 | 0 | **100% elimination** |
| Cross-authority policy violations | 43 | 2 | **95% reduction** |
| Legacy system modifications required | Yes (both) | No | **Zero-touch** |
| Subsystem autonomy preserved | No | Yes | **Full autonomy** |
| Permission latency (cross-region) | 4.2 ms | 0.42 ms | **90% reduction** |
| Compliance certifications retained | 1 of 2 | 2 of 2 | **Full retention** |
| Cross-region specialist consults | 0 | 2,341 | **N/A → full capability** |

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

Zones come in two native types plus one integration-specific type:

- **`CompositeZone`** — has children.
- **`AtomicZone`** — a leaf; calling `add_zone` raises `TypeError`, matching `Z_z = ∅`.
- **`AdapterZone`** — a leaf whose internal behaviour is opaque, wrapping a legacy or external system through a declared interface.

### Operations are the permission target — not applications

Permissions are granted on **operations**, never on applications. An operation is uniquely identified by `application.operation` (e.g. `EMR.prescribe`). This preserves the orthogonality of the ten components: applications provide deployability and grouping; operations provide the granular units for fine-grained security and auditing.

This distinction is what makes cross-zone integration tractable: two subsystems can use completely different application names and still share operations at the interface level.

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

In a federation, the recursive structure guarantees that any cross-zone access passes through both the requesting and the target zone's local decision functions. The more restrictive constraint wins.

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

The constraint is evaluated on every permission check through the `ConstraintManager.is_satisfied` hook. In a federation, shared constraints at the parent apply to every subsystem.

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

In a federation, **cross-zone daemons** observe pairs of subsystems — detecting vocabulary drift, latency spikes, and anomalous interaction patterns — and emit into their common ancestor.

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

Each subsystem keeps its own models. There is no "shared model" — the federation composes outputs, not state.

### Semantic embeddings for cross-zone alignment

The alignment functor is the mechanism that bridges heterogeneous vocabularies. Two subsystems can use entirely different names for the same operation; the aligned embeddings reveal the equivalence.

```python
from czoi import EmbeddingService

emb = EmbeddingService(dimension=64)
v1 = emb.embed_operation(operation_in_zone_a)
v2 = emb.embed_operation(operation_in_zone_b)
score = emb.similarity(v1, v2)

# Contrastive training of the global alignment functor
emb.train_alignment(positives=[(a, b)], negatives=[(a, c)])
```

In the post-merger case study, this mechanism discovered **47 semantically equivalent role pairs** across two legacy taxonomies — a task that would otherwise have consumed several weeks of manual effort.

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

In a federation, adaptive updates at any subsystem preserve the composed system's safety iff they respect the shared constraints established by the cross-zone integration relation.

---

## Integration Patterns

The categorical structure of CZOA suggests three fundamental integration patterns. Every realistic federation is a composition of these three:

### Pattern 1 — Product (parallel integration)

Two systems remain distinct but are composed under a new parent. This is the pattern for post-merger integration, multi-tenant SaaS, and federated identity.

```
                     [New Parent Authority]
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        [Subsystem A]   [Subsystem B]   [Subsystem C]
        (autonomous)    (autonomous)    (autonomous)
```

### Pattern 2 — Coproduct (alternative integration)

A facade exposes either system depending on context. This is the pattern for A/B testing, blue-green deployment, and geographic failover.

```
                     [Facade Zone]
                          │
              ┌───────────┴───────────┐
              │                       │
        [Active System]        [Standby System]
```

### Pattern 3 — Exponential (governed integration)

One system acts as a policy layer over another. This is the pattern for a parent company governing a subsidiary, a regulator supervising a regulated entity, or a platform hosting tenants.

```
                     [Policy Layer]
                          │
                     [Governed System]
```

---

## Project Layout

```
czoi/
├── core/               # exceptions, types
├── properties/         # typed attribute store
├── operations/         # Operation
├── roles/              # Application, Role, User
├── zones/              # ZoneBase, AtomicZone, CompositeZone, AdapterZone
├── permissions/        # PermissionEngine (Φ)
├── constraints/        # ConstraintManager (Γ) — bridges UniLog
├── neural/             # Predictor, AnomalyDetector, RoleMiner
├── embedding/          # EmbeddingService (E)
├── daemons/            # Daemon base, DaemonManager (Δ)
├── federation/         # FederationBuilder, cross-zone integration
└── toolkit/            # CZOABuilder factory

examples/
├── quickstart.py
├── nhs_simulation.py
├── unilog_constraints.py
├── legacy_adapter.py
└── post_merger.py

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
| `legacy_adapter.py` | Wrapping a legacy system as an adapter zone |
| `post_merger.py` | End-to-end federation of two independent systems |

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
| **`czoa-post-merger-6-08.py`** | **Post-merger enterprise integration** |

Each simulation compares baseline RBAC against CZOI and reports genuine measured improvements (mean, 95 % CI) rather than hard-coded constants.

---

## Testing

```bash
pytest -q                          # all tests
pytest -q tests/test_basic.py      # focused on core behaviour
pytest -q tests/test_federation.py # integration-specific tests
```

The test suite covers:

- Recursive zone construction and containment.
- Role inheritance and seniority.
- Permission calculus (local, parent override, denial).
- UniLog constraint parsing and evaluation.
- Neural components (fit, predict, anomaly detection).
- Daemon hierarchy and signal propagation.
- Embedding similarity and alignment.
- **Adapter zone interface contract.**
- **Federation composition preserving subsystem invariants.**

---

## Design Principles

1. **Minimality** — the ten components of the CZOI tuple are mutually orthogonal. No redundancy, no hidden state.
2. **Recursion** — every zone is a full system. Any subsystem can be developed, tested, and deployed independently while remaining governed by parent constraints.
3. **Containment** — `U_child ⊆ U_parent` is enforced at user-registration time.
4. **Operation-level permissions** — access control is maximally granular; the audit trail is precise.
5. **Formal constraints** — all organisational policy is expressible in UniLog and evaluated against live system state.
6. **Defensive monitoring** — daemons provide continuous compliance verification, independent of the permission engine.
7. **Safety-preserving adaptation** — every adaptive update preserves monotonicity, identity constraints, and audit completeness.
8. **Compositional integration** — heterogeneous subsystems compose into a coherent federation while each preserves its security invariants. Legacy systems are integrated without modification via adapter zones.
9. **Autonomy preservation** — subsystems retain their own models, their own policies, and their own evolution. Integration does not require centralization.

---

## UniLog Integration

The toolkit depends on [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit) for constraint specification. UniLog provides:

- **Eleven solvers**: classical, modal, epistemic, deontic, temporal, dynamic, description, probabilistic, non-monotonic, preference, fuzzy.
- **A concrete syntax** (UniLang) accepting both ASCII and Unicode forms.
- **SMT-based verification** for bounded state spaces.
- **Formal soundness guarantees** witnessed by the toolkit's test suite.

The `ConstraintManager` in CZOI builds a `CZOIModel` (implements the UniLog `Model` ABC) from a live zone and evaluates every loaded formula against it. In a federation, the shared model reads from the root zone and can traverse into every subsystem.

---

## Roadmap

| Feature | Status |
|---|---|
| Recursive zones, permission calculus, constraints, daemons, neural, embeddings | ✅ Shipped |
| UniLog toolkit integration | ✅ Shipped |
| **Adapter zones for legacy systems** | ✅ Shipped |
| **Federation builder for composing independent subsystems** | ✅ Shipped |
| **Cross-zone daemons and integration relations (ι)** | ✅ Shipped |
| First-class `GammaMapping` type | 🔄 In progress |
| Vector store adapters (pgvector, Chroma) | 🔄 In progress |
| Web framework integrations (Django, FastAPI, Flask) | 🔄 In progress |
| **Federated learning across CZOA subsystems** | 📋 Planned |
| **Conflict-resolution algebra for federations** | 📋 Planned |
| Distributed deployment | 📋 Planned |
| Automatic daemon synthesis from UniLang policies | 📋 Planned |
| **Semantic drift detection across federated subsystems** | 📋 Planned |

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

For integration-related contributions, please also include a scenario demonstrating the new behaviour end-to-end with at least two distinct subsystems.

---

## Citation

If you use this toolkit in academic work, please cite:

```bibtex
@article{wang2026czoa,
  author  = {Wang, Harris},
  title   = {Constrained Zoned-Object Architecture (CZOA): A Unified
             Framework for Integrating Fragmented Systems, Secure
             Access, and Organizational Intelligence},
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
- The **enterprise architecture** literature (Greefhorst & Proper 2011; Ross et al. 2006; Lankhorst 2017) for grounding the integration problem in real organizational practice.

---

## Contact

- **Author**: Harris Wang — [harrisw@athabascau.ca](mailto:harrisw@athabascau.ca)
- **Issues**: [github.com/hongxueharriswang/czoi-toolkit/issues](https://github.com/hongxueharriswang/czoi-toolkit/issues)
- **Related**: [unilog-toolkit](https://github.com/hongxueharriswang/unilog-toolkit)

---

*"The organizations that thrive in the next decade will not be those that chose between autonomy and integration. They will be those that discovered how to have both."*