# The CZOA/CZOI Tutorial

**A Guided Journey from Fragmented Systems to Unified Intelligence**

---

## Welcome

This tutorial will teach you to think in CZOA — the **Constrained Zoned-Object Architecture** — and to build real systems with the **CZOI toolkit**.

It is not a reference manual. It is a journey. We start with a problem that has frustrated software architects for decades, and we arrive at a framework that lets you build systems that are simultaneously secure, intelligent, and organisation-aligned. Along the way, you'll write code that runs. By the end, you'll be able to look at any complex organisation — a hospital, a bank, a factory, a government — and design a CZOI system that models it faithfully.

**How to use this tutorial:**

- Read it sequentially. Each chapter builds on the last.
- Type every code example. Don't just read them.
- Do the exercises. They're where the learning happens.
- When you get stuck, the [User Guide](USER_GUIDE.md) has the reference details.

**What you'll need:**

- Python 3.9 or later
- The CZOI toolkit: `pip install czoi-toolkit`
- Willingness to think abstractly — but we'll make every abstraction concrete.

**Estimated time:** 12–20 hours to work through carefully. Each chapter takes 45–90 minutes.

---

## Part I — Foundations

### Chapter 1 — The Fragmentation Problem

#### Learning objectives

- Understand why modern enterprise systems are hard to build.
- See the gap between "intelligent systems" and "enterprise systems."
- Get a preview of how CZOA closes that gap.

#### The story of two engineers

Meet **Maya** and **Sam**. They work at the same hospital network but never talk.

**Maya** builds the AI triage system. She's an ML engineer. Her models predict sepsis risk from vital signs with 94 % accuracy. She's published papers. Her code runs on GPUs. She thinks in tensors.

**Sam** builds the access-control system. He's an enterprise architect. He knows the hospital's organisational chart down to the sub-team level. He's implemented RBAC, ABAC, and SoD. His code runs on a mainframe. He thinks in permissions.

When the flu season hits and the hospital needs to redeploy nurses, Maya's sepsis model says "these patients are critical." Sam's access system says "these nurses cannot prescribe." The two systems don't talk. Patients wait.

**This is the fragmentation problem.** The theories that explain intelligence and the methodologies that build secure systems have evolved separately, and the cost is measured in hours of human suffering.

#### Why is this hard?

**Reason 1: Different abstractions.** Maya thinks in vector spaces. Sam thinks in role hierarchies. Their code has no common vocabulary.

**Reason 2: Different correctness criteria.** Maya's model is "correct" if it predicts well. Sam's system is "correct" if no unauthorised access occurs. These are not the same thing, and optimising one often degrades the other.

**Reason 3: Different timescales.** Maya's model retrains every week. Sam's permission structure changes every quarter. How do you compose systems that evolve at different rates?

**Reason 4: Different governance.** Maya's model is judged by regulators who want explainability. Sam's access system is judged by auditors who want accountability. Neither framework accommodates the other's requirements.

#### The CZOA insight

Here's the claim that changes everything:

> **Enterprise systems are a species of intelligent systems.**

An organisation — with its hierarchical departments, functional roles, operational procedures, and adaptation mechanisms — *instantiates the same structural patterns* that researchers use to model general intelligence.

Look at the parallels:

| Intelligence framework | Enterprise system |
|---|---|
| Hierarchical decomposition | Organisational chart |
| Component methods | Job functions |
| Attribute state | Employee data |
| Constraint satisfaction | Compliance rules |
| Adaptive learning | Process improvement |
| Goal optimisation | KPIs |

These are not metaphors. They are the *same structures* viewed through different lenses. Once you see this, the fragmentation dissolves: an enterprise system already has the structure of an intelligent system. It just needs to be formalised the same way.

#### What CZOA gives you

CZOA is the unification. It provides:

1. **A single formalism** (the CZOI 10-tuple) that describes both intelligent behaviour and enterprise security.
2. **A permission calculus** with formal guarantees, integrated with learning.
3. **A constraint language** (UniLang) that expresses organisational policy formally.
4. **A monitoring architecture** (daemons) that ensures continuous compliance.
5. **A recursive composition** that scales from a single team to a global organisation.
6. **A reference implementation** (the CZOI toolkit) that you can use today.

#### A taste of the unification

Here is a tiny CZOI system that captures both the intelligent and the secure aspect:

```python
from czoi import CZOABuilder, Application, Operation, Role, User, Decision

builder = CZOABuilder("Hospital")

# ---- Intelligence perspective ---------------------------------------
hospital = builder.add_zone("CityHospital")
emergency = builder.add_zone("Emergency", parent=hospital, atomic=True)

# Maya's model: predict sepsis risk
from czoi import Predictor
sepsis_model = Predictor("sepsis", threshold=0.85)
# (training would go here)
emergency.add_neural("sepsis", sepsis_model)

# ---- Security perspective -------------------------------------------
app = Application("EMR", zone=hospital)
prescribe = app.add_operation(Operation("prescribe"))
hospital.add_application(app)

attending = Role("Attending", zone=hospital, base_permissions=[prescribe])
nurse = Role("Nurse", zone=hospital, base_permissions=[])
hospital.add_role(attending)
hospital.add_role(nurse)

alice = User("alice", roles={"Attending"})
bob = User("bob", roles={"Nurse"})
for u in (alice, bob):
    for z in emergency.ancestry():
        z.add_user(u)

# ---- Both perspectives in one place ---------------------------------
print("alice can prescribe:",
      builder.permission_engine.decide(alice, prescribe, emergency).name)
print("bob can prescribe:  ",
      builder.permission_engine.decide(bob, prescribe, emergency).name)
```

The sepsis model and the permission structure live in **the same zone**. They can be composed. They can interact. That's CZOA.

#### Exercises

1. **Observe fragmentation.** Think of a system you use daily (email, banking, social media). Identify one "intelligent" feature and one "security" feature. Do they share any code? Any data? Any vocabulary?

2. **Find the parallels.** Pick an organisation you know. Fill in this table:
   - Its hierarchical units:
   - Its roles:
   - Its policies:
   - Its KPIs:
   - Its adaptation mechanisms:

3. **Predict the conflict.** For the hospital example above, imagine a scenario where Maya's model and Sam's permissions disagree. What would "agreement" look like?

#### Further reading

- The CZOA paper, §1 (Introduction)
- Beer's Viable System Model — the pre-CZOA observation that organisations are recursive

---

### Chapter 2 — Zones: The Recursive Foundation

#### Learning objectives

- Understand what a zone is and why it's recursive.
- Build zone hierarchies of arbitrary depth.
- Master the containment principle.

#### A zone is a system

In CZOA, **every organisational unit is a zone**, and every zone is a *full* CZOI system. Not a partial one. Not a child in a tree. A complete system with roles, operations, constraints, neural components, and daemons of its own.

Why? Because that's how real organisations work. A hospital's Emergency department isn't just a data structure pointing to its parent. It has its own procedures, its own staff, its own equipment, its own quality metrics. It could be surgically extracted and run as an independent clinic (with some policy adjustments). It is a system.

CZOA makes this literal. Every zone is a valid CZOI 10-tuple:

```
zone = (Z, R, U, A, O, N, E, Γ, Φ, Δ)
```

The parent-child relationship doesn't merge zones. It **composes** them. The parent governs; the child operates.

#### Building your first tree

```python
from czoi import CZOABuilder

builder = CZOABuilder("Company")
root = builder.root

# A composite zone — can have children
engineering = builder.add_zone("Engineering", parent=root)

# Atomic zones — leaves
backend = builder.add_zone("Backend", parent=engineering, atomic=True)
frontend = builder.add_zone("Frontend", parent=engineering, atomic=True)
mobile = builder.add_zone("Mobile", parent=engineering, atomic=True)

print("Tree:")
for zone in root.walk():
    indent = "  " * zone.depth()
    kind = "atomic" if not zone.zones else "composite"
    print(f"{indent}{zone.name} [{kind}]")
```

Output:

```
Tree:
Company [composite]
  Engineering [composite]
    Backend [atomic]
    Frontend [atomic]
    Mobile [atomic]
```

#### Composite vs atomic

The distinction matters. **`AtomicZone`** is a promise: this zone will never have children. If someone tries to add a child, they get a `TypeError`:

```python
try:
    backend.add_zone(builder.add_zone("Oops", parent=backend))
except TypeError as e:
    print(f"Caught: {e}")
```

Output:

```
Caught: AtomicZone 'Backend' cannot have child zones; use CompositeZone instead
```

Why enforce this? Two reasons:

1. **Recursion termination.** The paper's definition says the recursion ends when `Z_z = ∅`. `AtomicZone` makes that explicit.
2. **Accident prevention.** If you know a zone is a leaf, adding a child should be a deliberate design decision, not an accidental line of code.

**Rule of thumb**: start with `CompositeZone` for anything that might grow, then convert to `AtomicZone` when the design stabilises. Or just use the default (`atomic=False`) until you're sure.

#### Walking the tree

```python
# Pre-order traversal — self, then children, recursively
for zone in root.walk():
    print(zone.name)

# Ancestry — root down to self
for zone in backend.ancestry():
    print(zone.name)

# Depth — root is 0
print(backend.depth())         # 2

# Ancestor check
print(root.is_ancestor_of(backend))       # True
print(backend.is_ancestor_of(root))       # False
```

#### The containment principle

This is the most important structural rule in CZOA:

```
U_child ⊆ U_parent
```

Every user of a child zone must also be a user of its parent. In English: *if you're in the Backend team, you're automatically in the Engineering department.*

Why does this matter? Because it's how authority flows. A department head can see everyone in their sub-teams — *must* be able to, for governance to work. A company's CEO can see everyone in every department. The user sets are nested.

The toolkit enforces this at registration time:

```python
from czoi import User, ZoneContainmentError

alice = User("alice", roles={"Engineer"})

# This works — backend has engineering as ancestor,
# and we register her at every level
for zone in backend.ancestry():
    zone.add_user(alice)

# But this fails — we try to add a new user to backend only
charlie = User("charlie", roles={"Engineer"})
try:
    backend.add_user(charlie)
except ZoneContainmentError as e:
    print(f"Caught: {e}")
```

Output:

```
Caught: User 'charlie' must be affiliated with parent 'Engineering' first (containment principle)
```

#### A useful helper

Registering along the path is so common that you'll want a helper:

```python
def register(user, zone):
    """Register `user` at `zone` and every ancestor."""
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)

# Now this is one line
register(charlie, backend)
```

We'll use this pattern throughout the tutorial.

#### Properties: the state of a zone

Every zone has a typed property store:

```python
backend.properties.set("headcount", 12, type_hint="int")
backend.properties.set("budget_usd", 1_250_000.0, type_hint="float")
backend.properties.set("on_call_rotation", "weekly", type_hint="str")
backend.properties.set("has_24h_support", True, type_hint="bool")

print(backend.properties.get("headcount"))       # 12
print(backend.properties.get("missing", 0))      # 0
print(backend.properties.as_dict())
```

Type hints are enforced:

```python
try:
    backend.properties.set("headcount", "many", type_hint="int")
except TypeError as e:
    print(f"Caught: {e}")
```

```
Caught: headcount: expected int, got <class 'str'>
```

Properties are how zones expose state to:
- **Constraints** (e.g., "capacity must not exceed...")
- **Daemons** (e.g., "monitor budget utilisation")
- **Neural components** (e.g., "predict headcount growth")

#### Deep hierarchies are fine

Don't be afraid of depth. Real organisations have 5–10 levels of hierarchy, and CZOI handles this gracefully.

```python
# A realistic geography
builder = CZOABuilder("Global")
na = builder.add_zone("NorthAmerica", parent=builder.root)
us = builder.add_zone("US", parent=na)
west = builder.add_zone("WestCoast", parent=us)
bay = builder.add_zone("BayArea", parent=west)
sf = builder.add_zone("SanFrancisco", parent=bay, atomic=True)
oak = builder.add_zone("Oakland", parent=bay, atomic=True)

print(f"sf depth: {sf.depth()}")             # 5
print(f"sf ancestry: {[z.name for z in sf.ancestry()]}")
# ['Global', 'NorthAmerica', 'US', 'WestCoast', 'BayArea', 'SanFrancisco']
```

Six levels deep. No problem. The recursion is what makes CZOA scale.

#### Common pitfalls

**Pitfall 1: trying to add children to an atomic zone.**

```python
leaf = builder.add_zone("Leaf", atomic=True)
# leaf.add_zone(...)  # TypeError
```

If you need children, don't mark the zone atomic.

**Pitfall 2: forgetting containment.**

```python
# Wrong: jumps straight to the leaf
sf.add_user(alice)   # ZoneContainmentError

# Right: walk the path
register(alice, sf)
```

**Pitfall 3: assuming children auto-inherit users.**

Children don't inherit users. They can *only* hold users who are already at the parent. The set is a subset, not an automatic copy.

```python
# After registering alice at every level:
print("alice" in sf.users)          # True
print("alice" in bay.users)         # True
print("alice" in west.users)        # True
```

But if you add a new user to a child, you must add them to the parent first.

#### Exercises

1. **Model a university.** Build a hierarchy: University → Colleges → Departments → Research Groups. Use `CompositeZone` for anything with children, `AtomicZone` for leaves. Print the tree.

2. **Containment violation.** Deliberately trigger a `ZoneContainmentError`. Fix it. Then deliberately trigger a `TypeError` from an atomic zone. Fix it.

3. **Properties.** Add a `capacity` property to each zone in your university. Enforce `int`. Try to set it to a string and observe the error.

4. **Deep recursion.** Build a 10-level hierarchy. Register a user at the leaf. Verify they're in every ancestor.

#### Further reading

- The CZOA paper, Definition 1 (Recursive CZOA)
- The User Guide, §5 (Building Zone Hierarchies)

---

### Chapter 3 — The 10-Tuple

#### Learning objectives

- Understand every component of the CZOI 10-tuple.
- See why minimality matters.
- Recognise each component in a real system.

#### The tuple

A CZOI system is:

```
S = (Z, R, U, A, O, N, E, Γ, Φ, Δ)
```

Ten components. Let's go through each one carefully.

#### Z — Zones

The **subsystems**. Every zone has a `zones` dict:

```python
builder = CZOABuilder("Org")
hr = builder.add_zone("HR", parent=builder.root)
it = builder.add_zone("IT", parent=builder.root)

print(builder.root.zones)         # {'HR': ..., 'IT': ...}
```

Already covered in Chapter 2.

#### R — Roles

The **job functions**. Each role belongs to a zone and has base permissions:

```python
from czoi import Role, Operation, Application

app = Application("Payroll", zone=builder.root)
process = app.add_operation(Operation("process_payroll"))
view = app.add_operation(Operation("view_payroll"))
builder.root.add_application(app)

admin = Role("PayrollAdmin", zone=builder.root,
             base_permissions=[process, view])
viewer = Role("PayrollViewer", zone=builder.root,
              base_permissions=[view])
admin.add_junior(viewer)

builder.root.add_role(admin)
builder.root.add_role(viewer)
```

Roles have:
- A name
- A zone of definition
- A set of base operations
- A set of junior roles (seniority)
- A property store for attributes

#### U — Users

The **identities**. Each user holds role names and has attributes:

```python
from czoi import User

alice = User(
    "alice",
    roles={"PayrollAdmin"},
    attributes={"employee_id": "E-1", "clearance": 3},
    credentials={"mfa_enabled": True},
)
builder.root.add_user(alice)
```

Roles on a user are **names**, not objects. The zone resolves them. This is what lets a user carry their role through nested zones.

#### A — Applications

The **structural modules**. Applications group operations:

```python
from czoi import Application

hr_app = Application("HRApp", zone=builder.root)
hire = hr_app.add_operation(Operation("hire_employee"))
fire = hr_app.add_operation(Operation("terminate_employee"))
builder.root.add_application(hr_app)
```

Applications are:
- **Not** permission targets.
- Deployable units.
- Grouping for UI, embedding, and auditing.

#### O — Operations

The **atomic executable actions**. This is where permissions live.

```python
print(hire.qualified_name)     # "HRApp.hire_employee"
print(hire.application.name)   # "HRApp"
print(hire.name)               # "hire_employee"
```

Every permission is granted on an operation:

```python
admin_role.grant(hire)          # OK
# admin_role.grant(hr_app)     # WRONG — apps are not permission targets
```

Why operations and not applications? Because an application like `HRApp` might expose 50 different operations, and you want to grant a role *some* of them, not all.

#### N — Neural components

The **learnable functions**. Any object with a `predict` method works:

```python
from czoi import Predictor
import numpy as np

model = Predictor("attrition", threshold=0.5)
X = np.array([[1, 0.9, 5], [0, 0.3, 1], [0, 0.2, 2], [1, 0.8, 4]])
y = np.array([1.0, 0.0, 0.0, 1.0])
model.fit(X, y, epochs=500)

builder.root.add_neural("attrition", model)
```

Neural components live **inside zones** — this is critical. Different zones can have different models:

```python
backend.add_neural("perf_model", backend_model)
frontend.add_neural("perf_model", frontend_model)
```

Each zone decides what to learn. This is the CZOA answer to "whose model governs?" — the local one, with parent overrides if needed.

#### E — Embeddings

The **semantic vectors**. They map entities into a shared space where similarity is geometric distance.

```python
from czoi import EmbeddingService

emb = EmbeddingService(dimension=64)
v_hire = emb.embed_operation(hire)
v_fire = emb.embed_operation(fire)
v_process = emb.embed_operation(process)

print(f"hire ↔ fire:   {emb.similarity(v_hire, v_fire):.3f}")
print(f"hire ↔ process: {emb.similarity(v_hire, v_process):.3f}")
```

Embeddings enable:
- **Cross-zone role matching** — find equivalent roles in different departments.
- **Anomaly detection** — flag access patterns far from a user's history.
- **Adaptive grants** — suggest permissions based on semantic similarity.

#### Γ — Constraints

The **policy system**, split into four families:

- **I** — Identity: invariants that always hold.
- **T** — Trigger: event-condition-action rules.
- **G** — Goal: optimisation objectives.
- **C** — Access: permission policies.

```python
builder.add_access_constraint("""
    signature {
        sort User;
        predicate approve(u: User);
        predicate execute(u: User);
    }
    forall u: User . not (approve(u) and execute(u))
""")
```

This is a separation-of-duty rule expressed formally.

#### Φ — Permission calculus

The **decision function**. It's two-stage recursive:

1. **Local** — check the user's roles in this zone.
2. **Parent override** — if inconclusive, recurse to the parent.

```python
from czoi import Decision

decision = builder.permission_engine.decide(alice, hire, builder.root)
print(decision.name)   # ALLOW / DENY / INCONCLUSIVE
```

We'll cover Φ in depth in Chapter 6.

#### Δ — Daemons

The **continuous monitors**. Daemons observe the system and emit signals.

```python
from czoi import Daemon, DaemonSignal

class AttritionDaemon(Daemon):
    def __init__(self, model, parent=None):
        super().__init__("AttritionDaemon", parent=parent, interval=5.0)
        self.model = model

    def monitor(self):
        # In a real system, iterate over users
        score = self.model.predict({"tenure": 2, "satisfaction": 0.3,
                                    "promotions": 0})
        if score > 0.8:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"risk": score, "reason": "attrition"},
            )

daemon = AttritionDaemon(model)
builder.add_daemon(daemon)
```

We'll cover daemons fully in Chapter 11.

#### Why exactly these ten?

The ten components are **minimal** and **orthogonal**:

- **Minimal** means: remove any one and the framework can't express something important.
  - Without `Z`, no hierarchy.
  - Without `Φ`, no permission decisions.
  - Without `Γ`, no policy.
  - Without `Δ`, no monitoring.

- **Orthogonal** means: each component has a distinct role; none overlaps another.
  - `R` and `O` are different (roles are job functions, operations are actions).
  - `N` and `E` are different (neural components learn, embeddings represent).
  - `Γ` and `Δ` are different (constraints are declarative, daemons are procedural).

This orthogonality is what makes CZOI **composable**. If two components did the same job, you'd have to decide which one to use in each context, and the system would have internal ambiguity.

#### The tuple in one example

```python
from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Operation,
    Predictor, Role, User,
)

# Z — zones
builder = CZOABuilder("Team")
team = builder.add_zone("Engineering", parent=builder.root)
backend = builder.add_zone("Backend", parent=team, atomic=True)

# A — applications
app = Application("Repo", zone=team)
commit = app.add_operation(Operation("commit"))
review = app.add_operation(Operation("review"))
team.add_application(app)

# O — operations
# (already created above; commit, review)

# R — roles
senior = Role("Senior", zone=team, base_permissions=[commit, review])
junior = Role("Junior", zone=team, base_permissions=[commit])
senior.add_junior(junior)
team.add_role(senior)
team.add_role(junior)

# U — users
alice = User("alice", roles={"Senior"})
bob = User("bob", roles={"Junior"})
for z in backend.ancestry():
    z.add_user(alice)
    z.add_user(bob)

# N — neural
review_model = Predictor("review_time", threshold=0.5)
review_model.fit(
    X=[[1, 5, 0], [0.5, 20, 1], [1, 3, 0], [0.3, 40, 1]],
    y=[0.0, 1.0, 0.0, 1.0],
    epochs=500,
)
team.add_neural("review_time", review_model)

# E — embeddings
team.set_embeddings(builder.embedding_service)

# Γ — constraints
builder.add_access_constraint("""
    signature {
        sort User;
        predicate hasSenior(u: User);
        predicate selfReview(u: User);
    }
    forall u: User . not (hasSenior(u) and selfReview(u))
""")

# Φ — permission engine (attached by builder)
engine = builder.permission_engine

# Δ — daemons
class RepoDaemon(Daemon):
    def monitor(self):
        pass    # nothing to do in this minimal example
builder.add_daemon(RepoDaemon("Repo"))

# Everything's in place. Use it.
print(engine.decide(alice, review, team).name)   # ALLOW
print(engine.decide(bob, review, team).name)     # INCONCLUSIVE
```

Ten components, ten lines of setup, one complete system.

#### Exercises

1. **Identify the components.** In the example above, point to where each of the ten components appears. Write it out as a list.

2. **Add a component.** Add a `view_repo` operation. Grant it to both `Senior` and `Junior`. Verify that both can view, but only `Senior` can review.

3. **Extend the neural model.** Add a second model to the `backend` zone that predicts something different (e.g., "code quality"). Show that both models coexist.

4. **Minimality test.** Try to design a system that would need an eleventh component. What would it be? Can you express it using the existing ten?

#### Further reading

- The CZOA paper, Definition 1 and §3
- Chapter 4 (Roles, users, and permissions in depth)

---

## Part II — Core Mechanics

### Chapter 4 — Roles, Users, and the Seniority Relation

#### Learning objectives

- Design role hierarchies that mirror real job families.
- Understand the difference between base and effective permissions.
- Use seniority to avoid permission duplication.

#### The role model

A **role** is a named job function within a zone. It has:

- A **name** (unique within its zone).
- A **base permission set** — the operations directly granted to it.
- A **junior role set** — roles for which this role is senior.
- A **property store** — attributes for the role itself.

```python
from czoi import Role, Operation, Application, CZOABuilder

builder = CZOABuilder("Bank")
bank = builder.root

app = Application("CoreBanking", zone=bank)
deposit = app.add_operation(Operation("deposit"))
withdraw = app.add_operation(Operation("withdraw"))
approve_loan = app.add_operation(Operation("approve_loan"))
view_transactions = app.add_operation(Operation("view_transactions"))
bank.add_application(app)

# A realistic role family
teller = Role("Teller", zone=bank,
              base_permissions=[deposit, withdraw, view_transactions])
senior_teller = Role("SeniorTeller", zone=bank,
                     base_permissions=[approve_loan])
manager = Role("BranchManager", zone=bank,
               base_permissions=[])      # no extra base permissions

# Seniority chain: Manager is senior to SeniorTeller is senior to Teller
manager.add_junior(senior_teller)
senior_teller.add_junior(teller)

bank.add_role(teller)
bank.add_role(senior_teller)
bank.add_role(manager)
```

#### Base vs effective permissions

The **base permissions** of a role are what you explicitly grant. The **effective permissions** include everything inherited from junior roles.

```python
def effective(role):
    """Compute the effective permission set of a role."""
    ops = set(role.base_permissions)
    for junior in role.junior_roles:
        ops |= effective(junior)
    return ops

print("Teller base:", sorted(op.qualified_name for op in teller.base_permissions))
print("SeniorTeller effective:",
      sorted(op.qualified_name for op in effective(senior_teller)))
print("Manager effective:",
      sorted(op.qualified_name for op in effective(manager)))
```

Output:

```
Teller base: ['CoreBanking.deposit', 'CoreBanking.view_transactions', 'CoreBanking.withdraw']
SeniorTeller effective: ['CoreBanking.approve_loan', 'CoreBanking.deposit', 'CoreBanking.view_transactions', 'CoreBanking.withdraw']
Manager effective: ['CoreBanking.approve_loan', 'CoreBanking.deposit', 'CoreBanking.view_transactions', 'CoreBanking.withdraw']
```

Notice: the Manager has **no** base permissions of their own, but inherits everything because they're senior to SeniorTeller, who is senior to Teller. This is how CZOI keeps role definitions small — you don't repeat permissions; you declare relations.

#### Why seniority is important

Without seniority, you'd need:

```python
# Without seniority — duplicated permissions
teller = Role("Teller", base_permissions=[deposit, withdraw, view_transactions])
senior_teller = Role("SeniorTeller",
                     base_permissions=[deposit, withdraw, view_transactions,
                                       approve_loan])
manager = Role("BranchManager",
               base_permissions=[deposit, withdraw, view_transactions,
                                 approve_loan])
```

Every role repeats everything a junior role has. Change one permission → edit three roles. Forget one → security hole.

With seniority:

```python
# With seniority — no duplication
teller = Role("Teller", base_permissions=[deposit, withdraw, view_transactions])
senior_teller = Role("SeniorTeller", base_permissions=[approve_loan])
manager = Role("BranchManager", base_permissions=[])
manager.add_junior(senior_teller)
senior_teller.add_junior(teller)
```

Change `deposit` → edit `teller` → everyone inherits the change.

This is the paper's intra-zone seniority relation (`r₁ ≥_z r₂`), and it mirrors how real organisations work: a manager doesn't have "manager permissions + all subordinate permissions"; they have "all subordinate permissions + a few extras."

#### Users hold role *names*

Here's a subtle but important point. A user's `roles` attribute holds **role names**, not role objects:

```python
from czoi import User

alice = User("alice", roles={"SeniorTeller"})
print(alice.roles)      # {"SeniorTeller"}
```

When the engine checks `alice` in a zone, it looks up the name in **that zone's** `roles` dict. This is what allows a user to carry their role through nested zones:

```python
branch = builder.add_zone("MainBranch", parent=bank, atomic=True)

# Register alice along the path
for z in branch.ancestry():
    z.add_user(alice)

# Both zones have "SeniorTeller" (inherited from parent)
print("SeniorTeller" in bank.roles)      # True
print("SeniorTeller" in branch.roles)    # True
print(bank.roles["SeniorTeller"] is branch.roles["SeniorTeller"])   # True
```

The role *object* is shared. When you call `bank.add_role(role)`, the toolkit propagates it to all existing children:

```python
# Add a new role later
auditor = Role("Auditor", zone=bank, base_permissions=[view_transactions])
bank.add_role(auditor)

# The branch now sees it too
print("Auditor" in branch.roles)         # True
```

#### Registering users correctly

Users must be registered at every ancestor:

```python
def register(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)

bob = User("bob", roles={"Teller"})
register(bob, branch)
```

Alternatively, add to the root and let the containment principle guide you upward. The toolkit requires you to work bottom-up in the `ancestry()` order.

#### Common role patterns

**Pattern 1: Symmetric roles.** Two roles at the same level with distinct permissions:

```python
loan_officer = Role("LoanOfficer", base_permissions=[approve_loan])
auditor = Role("Auditor", base_permissions=[view_transactions])
```

Neither is senior to the other. They do different jobs.

**Pattern 2: Role with shared base.** Two roles with a common ancestor:

```python
employee = Role("Employee", base_permissions=[view_transactions])
teller = Role("Teller", base_permissions=[deposit, withdraw])
teller.add_junior(employee)

loan_officer = Role("LoanOfficer", base_permissions=[approve_loan])
loan_officer.add_junior(employee)
```

Now both tellers and loan officers can view transactions (because both inherit from Employee), but neither can do the other's job.

**Pattern 3: Cascade with branching.** A manager who is senior to multiple specialists:

```python
manager = Role("Manager", base_permissions=[approve_loan])
manager.add_junior(teller)
manager.add_junior(auditor)
```

Manager inherits both Teller and Auditor permissions.

**Pattern 4: Deep chain with back-references.** Sometimes a role needs to be senior to something in a different branch:

```python
vp = Role("VP", base_permissions=[])
vp.add_junior(manager)
# VP now inherits everything Manager has, including what Manager inherited.
```

#### Anti-patterns

**Anti-pattern 1: redundant seniority.**

```python
# Bad — declares A senior to both B and C, but B is already senior to C
a.add_junior(b)
b.add_junior(c)
a.add_junior(c)   # redundant
```

This is harmless but obscures the hierarchy. Prefer a clean tree.

**Anti-pattern 2: cyclic seniority.**

```python
a.add_junior(b)
b.add_junior(a)   # cycle!
```

The effective-permission calculation would loop forever. The toolkit doesn't currently prevent this, so you need to be careful. If you need cyclic relations, reconsider the model.

**Anti-pattern 3: starving the root.**

```python
# Bad — every role is senior to every other, forming a star
top = Role("Top", base_permissions=[everything])
for r in other_roles:
    top.add_junior(r)
```

This is a red flag. Roles should have specialised permissions, not omnibus ones. If you find yourself building a "god role," you probably want a policy that grants temporary elevation via a daemon instead.

#### A word on role equality

`Role` uses `id()`-based hashing. Two roles with the same name are **different objects** if they're constructed separately:

```python
r1 = Role("Manager", zone=bank)
r2 = Role("Manager", zone=bank)
print(r1 == r2)   # False
```

This is intentional. Roles have identity. If you want one role, keep one object.

#### Exercises

1. **Design a hierarchy.** Model a support team with these roles: `SupportAgent`, `SeniorAgent`, `TeamLead`, `SupportManager`. SeniorAgent inherits from SupportAgent; TeamLead from SeniorAgent; SupportManager from TeamLead. Give each role one unique permission.

2. **Compute effective permissions.** Write a function that prints a tree of roles with each role's effective permissions. Verify the top role inherits everything.

3. **Add a cross-branch role.** Add a `QualityAssurance` role that is *not* senior to any support role but shares some permissions. Model this with a common ancestor.

4. **Break containment.** Deliberately try to register a user at a child zone without adding them at the parent. Catch the `ZoneContainmentError` and fix it with a `register` helper.

#### Further reading

- The CZOA paper, §3, item 2 (Roles)
- The User Guide, §6 (Roles, Users, and Operations)

---

### Chapter 5 — Operations and the Application Boundary

#### Learning objectives

- Understand why applications and operations are separate.
- Design operations at the right granularity.
- Use applications for organisation, not for permission.

#### The problem with "one entity"

Imagine you're designing a payroll system. You need roles that can:

- View a payroll record.
- Edit a payroll record.
- Process payroll for the whole company.
- Approve a payroll run.

A naive design might make `Payroll` a single permission target:

```python
# Anti-pattern
role.grant("Payroll")   # grants all four actions
```

But now an auditor who only needs to *view* gets *edit* and *process* and *approve*. That's a security disaster.

The right design treats each action as a **separate operation**:

```python
# Correct
app = Application("Payroll", zone=hr)
view    = app.add_operation(Operation("view_payroll"))
edit    = app.add_operation(Operation("edit_payroll"))
process = app.add_operation(Operation("process_payroll"))
approve = app.add_operation(Operation("approve_payroll"))
```

And grants them individually:

```python
auditor_role.grant(view)
hr_admin_role.grant(view)
hr_admin_role.grant(edit)
hr_admin_role.grant(process)
controller_role.grant(view)
controller_role.grant(approve)
```

Now the auditor cannot edit; the HR admin cannot approve; the controller cannot edit. **Least privilege**, enforced structurally.

#### Operations are the permission target

In CZOA, an operation is the **only** thing you can grant. Not an application. Not a zone. Not a role.

```python
# Correct
role.grant(operation)

# Wrong — will raise
# role.grant(application)
```

Why this strictness? Because it's what makes the framework **minimal**. If you could grant applications, you'd need two parallel permission systems. Two caches. Two audit trails. Two sets of semantics to reason about. CZOI refuses to duplicate. One target: operations.

#### The qualified name

Every operation has a **qualified name** that includes its application:

```python
print(view.qualified_name)          # "Payroll.view_payroll"
print(view.application.name)        # "Payroll"
print(view.name)                    # "view_payroll"
```

The qualified name is what appears in:
- Audit logs.
- Error messages.
- Cross-zone references.

Use it whenever you need a stable identifier.

#### Applications do the organising

Applications are for:
- **Grouping** related operations.
- **Deployment** — one application, one release.
- **UI** — display operations of the same app together.
- **Embeddings** — operation embeddings use the application name for context.
- **Audit** — filter access logs by application.

They are **not** for permission. Grants always go to operations.

#### Granularity: a decision framework

How fine-grained should operations be? Here's a decision tree:

**Question 1: Do these actions have different security implications?**

If yes, split them. `view_salary` and `edit_salary` have vastly different security implications.

**Question 2: Would you ever grant one without the other?**

If yes, split them. If you'd always grant `edit_salary` with `view_salary`, maybe they're the same operation.

**Question 3: Does the audit need to distinguish them?**

If an auditor would ask "was this a view or an edit?", split them. Audit granularity is a requirement, not an optimisation.

**Question 4: Are they used at different times or by different people?**

If yes, split them.

Let's apply this to payroll:

| Action | Security implication | Ever separate? | Audit? | Split? |
|---|---|---|---|---|
| View record | Low | Yes | Yes | ✅ `view_payroll` |
| Edit record | High | Yes | Yes | ✅ `edit_payroll` |
| Process run | Very high | Yes | Yes | ✅ `process_payroll` |
| Approve run | Very high | Yes | Yes | ✅ `approve_payroll` |
| Generate report | Low | Maybe | No | ⚠️ Could merge with view |
| Export CSV | Medium | Yes | Yes | ✅ `export_payroll` |

Four clear splits. Two borderline cases. The rules give you a defensible answer.

#### Cross-application operations

What if an operation spans two applications? For example, `audit_payroll` uses both the Payroll app's data and the Audit app's reports.

Answer: pick one application as the "home." The operation belongs to the app where it's most naturally executed.

```python
audit_app = Application("Audit", zone=hr)
audit_payroll = audit_app.add_operation(Operation("audit_payroll"))
```

The fact that it *reads* Payroll data is a runtime concern, not a modelling concern. The permission is granted on `Audit.audit_payroll`, and that's enough.

#### Operations in audit logs

Every permission decision references a specific operation:

```python
from czoi import Decision, PermissionEngine

engine = builder.permission_engine
engine.audit_enabled = True

engine.decide(alice, view, hr)
engine.decide(alice, edit, hr)

for record in engine.audit:
    print(f"{record.user} {record.operation} → {record.decision.name}")
```

Output:

```
alice Payroll.view_payroll → ALLOW
alice Payroll.edit_payroll → INCONCLUSIVE
```

You can immediately tell: Alice can view but not edit. No ambiguity, no "used the payroll system" vagueness.

#### Property-driven operations

Operations can have attributes:

```python
process_payroll = app.add_operation(Operation(
    "process_payroll",
    attributes={"risk_level": "high", "requires_audit": True},
))
```

These can be used by constraints or daemons:

```python
builder.register_predicate(
    "highRisk",
    lambda o: o.attributes.get("risk_level") == "high",
)

builder.add_access_constraint("""
    signature {
        sort User, Operation;
        predicate highRisk(o: Operation);
        predicate hasApproval(u: User);
    }
    forall u: User, o: Operation .
        highRisk(o) -> hasApproval(u)
""")
```

Now any high-risk operation requires the user to have an approval flag.

#### Refactoring operations

If you find later that an operation is too coarse, you can split it:

```python
# Before
edit_record = app.add_operation(Operation("edit_record"))

# After — split into two
edit_record_basic = app.add_operation(Operation("edit_record_basic"))
edit_record_sensitive = app.add_operation(Operation("edit_record_sensitive"))

# Migrate grants
for role in [hr_admin, auditor]:
    if edit_record in role.base_permissions:
        role.base_permissions.remove(edit_record)
        role.base_permissions.add(edit_record_basic)
        if role.name in ("HRAdmin",):
            role.base_permissions.add(edit_record_sensitive)
```

Migrations like this are cheap because operations have clear semantics. Renaming a single "Payroll permission" would be much harder.

#### Anti-patterns

**Anti-pattern 1: empty operations.**

```python
noop = app.add_operation(Operation("nothing"))
```

If an operation doesn't do anything, don't create it.

**Anti-pattern 2: composite operations.**

```python
# Bad
finalise_quarter = app.add_operation(Operation("finalise_quarter"))
```

This sounds atomic but it isn't — it's a workflow. Break it into the actual operations the workflow invokes.

**Anti-pattern 3: operations that duplicate roles.**

```python
# Bad
manager_login = app.add_operation(Operation("manager_login"))
```

Don't encode roles in operation names. Use roles.

**Anti-pattern 4: hundreds of trivial operations.**

```python
# Overkill
view_payroll_page_1 = app.add_operation(...)
view_payroll_page_2 = app.add_operation(...)
```

The right granularity is "would an auditor ever need to distinguish these?"

#### Exercises

1. **Model a helpdesk.** Design applications and operations for a helpdesk system. Include at least: reading tickets, replying, closing, reassigning, escalating, viewing metrics.

2. **Justify your splits.** For each operation, write one sentence explaining why it's separate from its neighbours. If you can't justify a split, merge the operations.

3. **Find the leak.** Take a role like `Agent` and grant it a "reasonable" set of operations. Is there anything you might have over-granted? Split or remove.

4. **Design for audit.** Given your operations, write the audit query: "Show me every payroll operation by Alice in the last 30 days." What SQL would this require? What operation names would appear?

#### Further reading

- The CZOA paper, §3, items 4 and 5 (Applications and Operations)
- The CZOA paper, §8.4 (Design rationale for the application-operation separation)
- The User Guide, §6 (Roles, Users, and Operations)

---

### Chapter 6 — The Permission Calculus

#### Learning objectives

- Understand the two-stage recursive decision function.
- Know when a decision is `ALLOW`, `DENY`, or `INCONCLUSIVE`.
- Trace a decision through multiple zones.

#### The central problem

You have a user. You have an operation. You have a zone. **Should you allow the request?**

Not a simple question:

- The user may have the operation in a role defined two levels up.
- A constraint might forbid it.
- The parent zone might override.
- A neural component might elevate the decision.

CZOA's answer is the **permission calculus** (Φ). It's a two-stage recursive function.

#### The stages

**Stage 1: Local decision.** Look at the user's roles in this zone.

**Stage 2: Parent override.** If the local decision is inconclusive, ask the parent.

That's it. The complexity is in what "look at the roles" means.

#### Walk-through

Consider a hospital:

```python
from czoi import (
    Application, CZOABuilder, Decision, Operation, Role, User,
)

builder = CZOABuilder("HealthAuthority")
regional = builder.root
hospital = builder.add_zone("CityHospital", parent=regional)
icu = builder.add_zone("ICU", parent=hospital, atomic=True)

app = Application("EMR", zone=hospital)
prescribe = app.add_operation(Operation("prescribe"))
dispense = app.add_operation(Operation("dispense"))
hospital.add_application(app)

attending = Role("Attending", zone=hospital, base_permissions=[prescribe])
nurse = Role("Nurse", zone=hospital, base_permissions=[dispense])
hospital.add_role(attending)
hospital.add_role(nurse)

alice = User("alice", roles={"Attending"})
bob = User("bob", roles={"Nurse"})
for u in (alice, bob):
    for z in icu.ancestry():
        z.add_user(u)
```

Now trace `alice.prescribe` at `icu`:

**Step 1:** engine checks Alice's roles in `icu`. `icu.roles` includes `Attending` (inherited from `hospital`). So `Attending` is a candidate role.

**Step 2:** the effective permissions of `Attending` = `{prescribe}`. `prescribe` is in this set.

**Step 3:** evaluate the access constraints of `icu` (currently none). Constraints pass.

**Result:** `ALLOW`.

```python
engine = builder.permission_engine
print(engine.decide(alice, prescribe, icu).name)   # ALLOW
```

Now trace `bob.prescribe` at `icu`:

**Step 1:** Bob's roles = `{Nurse}`. `Nurse` is in `icu.roles`.

**Step 2:** `Nurse`'s effective permissions = `{dispense}`. `prescribe` is NOT in this set.

**Step 3:** no role covers → local decision is `INCONCLUSIVE`.

**Step 4:** recurse to `icu.parent` = `hospital`.

**Step 5:** check Bob's roles in `hospital`. `Nurse` is there, but its effective permissions still don't include `prescribe`.

**Step 6:** local decision at `hospital` is also `INCONCLUSIVE`.

**Step 7:** recurse to `hospital.parent` = `regional`.

**Step 8:** check Bob's roles at `regional`. No roles cover.

**Step 9:** recurse to `regional.parent` — none.

**Result:** `DENY` at the root.

```python
print(engine.decide(bob, prescribe, icu).name)     # INCONCLUSIVE
```

Wait — why does the example print `INCONCLUSIVE` and not `DENY`?

Because the recursion returns the *last* local decision, which for Bob is `INCONCLUSIVE` — not `DENY`. The engine only returns `DENY` when a **constraint** blocks. Otherwise, `INCONCLUSIVE` at every level means the engine hasn't found a covering role.

Hmm, but the paper says the final fallback is `DENY`. Let me check the actual toolkit behaviour...

Actually, looking at the reference implementation more carefully: the recursion in `_decide_recursive` returns `Decision.DENY` at the root if the parent is None and the local is still inconclusive:

```python
def _decide_recursive(self, user, operation, zone):
    local = self._local_decide(user, operation, zone)
    if local is not Decision.INCONCLUSIVE:
        return local, "local"
    if zone.parent is None:
        return Decision.DENY, "root-deny"
    return self._decide_recursive(user, operation, zone.parent)
```

So at the root, `INCONCLUSIVE` becomes `DENY`. But the intermediate calls return their own local decision — so if you call `decide(bob, prescribe, icu)`, the recursion reaches the root, finds no covering role, and returns `DENY`.

Let me correct the walk-through:

```python
print(engine.decide(bob, prescribe, icu).name)     # DENY
```

The three-valued decision is exposed through the **local** evaluation (`evaluate_local`), not the recursive one.

Actually, I realise this is getting into detail I should double-check. Let me be careful. In the toolkit I shipped:

```python
def decide(self, user, operation, zone):
    # recursive two-stage decision
    decision, stage = self._decide_recursive(user, operation, zone)
    ...
    return decision

def _decide_recursive(self, user, operation, zone):
    local = self._local_decide(user, operation, zone)
    if local is not Decision.INCONCLUSIVE:
        return local, "local"
    if zone.parent is None:
        return Decision.DENY, "root-deny"
    return self._decide_recursive(user, operation, zone.parent)
```

So yes, `decide` returns `DENY` for Bob. The `INCONCLUSIVE` value is only exposed through `evaluate_local`.

I should be accurate about this. Let me correct the tutorial.

OK so let me revise: the walk-through should show `DENY` at the root.

Let me redo:

```python
print(engine.decide(bob, prescribe, icu).name)     # DENY
```

And explain: the recursion walks up to the root, finds no covering role, and the root returns `DENY` because there's nowhere else to go.

But `evaluate_local` would show the intermediate `INCONCLUSIVE` states:

```python
print(engine.evaluate_local(bob, prescribe, icu).name)       # INCONCLUSIVE
print(engine.evaluate_local(bob, prescribe, hospital).name)  # INCONCLUSIVE
print(engine.evaluate_local(bob, prescribe, regional).name)  # INCONCLUSIVE
```

This is worth showing because it explains the two-stage nature explicitly.

OK let me continue writing this chapter. I need to be accurate.

#### The three decision values

| Value | Meaning |
|---|---|
| `ALLOW` | A covering role was found and constraints passed. |
| `DENY` | Either (a) a covering role was found but constraints failed, or (b) the recursion reached the root with no covering role. |
| `INCONCLUSIVE` | This zone's roles don't cover the operation, but a parent might. Only returned by `evaluate_local`, not by the recursive `decide`. |

**Practical implication:** if you call `engine.decide(...)`, you'll see `ALLOW` or `DENY`. Use `engine.evaluate_local(...)` if you want to see the intermediate `INCONCLUSIVE` states — useful for debugging and tracing.

#### Tracing a decision

```python
def trace(engine, user, operation, zone):
    print(f"Trace: {user.name} → {operation.qualified_name} @ {zone.name}")
    chain = [zone] + zone.ancestry()[::-1]   # this zone, then upward
    for z in chain:
        decision = engine.evaluate_local(user, operation, z)
        print(f"  @{z.name:<20} : {decision.name}")
        if decision is not Decision.INCONCLUSIVE:
            break

trace(engine, bob, prescribe, icu)
```

Output:

```
Trace: bob → EMR.prescribe @ ICU
  @ICU                  : INCONCLUSIVE
  @CityHospital         : INCONCLUSIVE
  @HealthAuthority      : INCONCLUSIVE
```

Three `INCONCLUSIVE`s, then the recursive `decide` would return `DENY`. The trace shows exactly where Bob falls short: no zone has a role that covers `prescribe`.

Compare with Alice:

```python
trace(engine, alice, prescribe, icu)
```

```
Trace: alice → EMR.prescribe @ ICU
  @ICU                  : ALLOW
```

One level. Alice's role covers it immediately.

#### The seniority traversal

Inside `_local_decide`, the engine walks the seniority graph:

```python
def _effective_permissions(self, roles):
    perms = set()
    seen = set()
    stack = list(roles)
    while stack:
        r = stack.pop()
        if r in seen:
            continue
        seen.add(r)
        perms |= r.base_permissions
        stack.extend(r.junior_roles)
    return perms
```

Note the `seen` set — it prevents infinite loops if the seniority graph has cycles (which it shouldn't, but defensive programming).

Every senior role contributes its base permissions to the effective set. So if Alice has `Attending`, and `Attending` is senior to `Resident`, and `Resident` is senior to `Intern`, Alice's effective set includes all three roles' base permissions.

#### Where constraints plug in

After the engine finds a covering role, it evaluates the **access constraints** of the zone:

```python
if zone.constraints is not None:
    checker = getattr(zone.constraints, "is_satisfied", None)
    if callable(checker) and not checker(user, operation, zone):
        return Decision.DENY
```

So the flow is:

1. Find covering role.
2. Evaluate constraints.
3. If constraints pass → `ALLOW`.
4. If constraints fail → `DENY`.

This is why `DENY` and `INCONCLUSIVE` are different: `DENY` means "you have the role, but you can't use it" (constraint blocked); `INCONCLUSIVE` means "you don't have the role here, but try the parent."

#### Cross-zone permissions

The toolkit's `_decide_recursive` doesn't currently implement the full cross-zone permission traversal from the paper's equation:

```
P_effective(r, z) =
    P_base^z(r)
    ∪ ⋃_{r' ∈ seniority_z(r)} P_base^z(r')
    ∪ ⋃_{z_child ∈ Z_z} γ(z_child, r)
    ∪ Φ_parent^{-1}(r, z)
```

The γ (gamma) term is modelled as an **explicit grant** rather than an implicit traversal. See Chapter 15 (Cross-zone reasoning) for the full pattern.

#### Caching

The engine caches decisions:

```python
key = (id(user), id(operation), id(zone))
if self.cache_enabled and key in self._cache:
    return self._cache[key]
```

The cache is invalidated automatically when you:
- Call `zone.grant(role, op)` or `zone.revoke(role, op)`.
- Add a role, user, or operation.

If you mutate a role directly (`role.grant(op)`), the cache is **not** invalidated. This is a performance trade-off: you can bypass the invalidation for batch operations by calling `engine.invalidate()` at the end.

#### Statistics

```python
stats = engine.stats()
print(stats)
# {'hits': 43, 'misses': 1180, 'parent_lookups': 4, 'denies': 0}
```

- **hits** — cached decisions.
- **misses** — engine evaluations.
- **parent_lookups** — recursive upward calls.
- **denies** — count of `DENY` results.

Watch the `parent_lookups` metric. If it's very high relative to `misses`, your role definitions are too specific (roles exist only at deep levels), forcing the engine to recurse. Moving common roles to a higher level fixes this.

#### Common patterns

**Pattern 1: local capability.** A role defined at the same zone as the operation:

```python
hospital_role = Role("Doctor", zone=hospital, base_permissions=[prescribe])
hospital.add_role(hospital_role)
```

Decisions are resolved at the first level.

**Pattern 2: inherited capability.** A role defined at a parent, resolved through recursion:

```python
regional_role = Role("Chief", zone=regional, base_permissions=[prescribe])
regional.add_role(regional_role)
```

Both `hospital` and `icu` see the role via inheritance. No recursion needed (the role name is in every descendant's `roles` dict).

**Pattern 3: constraint override.** A role covers the operation but a constraint blocks:

```python
builder.add_access_constraint("""
    forall u: User . not (hasRole(u, NightShift) and prescribe(u))
""")
```

Now any night-shift doctor is denied `prescribe`. The engine still finds the covering role, then evaluates the constraint, then returns `DENY`.

**Pattern 4: neural elevation.** A neural component overrides the base decision:

```python
from czoi import NeuralContribution

def elevation(user, operation, zone, base):
    if (operation.name == "prescribe"
            and user.has_role("SeniorNurse")
            and zone.properties.get("surge_active", False)):
        return Decision.ALLOW
    return base

engine.set_neural_contribution(NeuralContribution(elevation))
```

If the neural contribution returns `ALLOW`, the decision becomes `ALLOW` (subject to constraints).

#### Exercises

1. **Trace a decision.** Using the hospital example, trace `alice.dispense` and `bob.dispense`. Which zones are consulted? What are the intermediate decisions?

2. **Add seniority.** Make `Attending` senior to `Nurse`. Now Bob (a Nurse) still can't prescribe directly, but Alice (Attending) inherits all of Bob's permissions. Verify.

3. **Add a constraint.** Write a constraint that denies `prescribe` to anyone whose `attributes["shift"] == "night"`. Set Alice's shift to night and verify she's denied.

4. **Enable audit.** Turn on `audit_enabled`, run some decisions, and print every `DecisionRecord`. Which stage was used for each?

5. **Measure cache impact.** Run 1000 identical decisions with `cache_enabled=True` and with `cache_enabled=False`. Compare the times.

#### Further reading

- The CZOA paper, §3, item 9 (Permission Calculus)
- The CZOA paper, §8.4 (Design rationale)
- The User Guide, §7 (The Permission Calculus)

---

## Part III — Intelligence

### Chapter 7 — Neural Components

#### Learning objectives

- Understand why neural components are first-class citizens in CZOI.
- Train a `Predictor`, `AnomalyDetector`, and `RoleMiner`.
- Attach neural components to zones.
- Use neural components inside daemons and permission hooks.

#### Why neural components?

Traditional access-control systems separate "policy" from "intelligence." Policy is static; intelligence is external. If you want to do something intelligent, you build a separate system.

CZOA refuses that separation. Neural components are part of the zone — not bolted on, not in a separate service, not behind an API. They have the same status as roles and operations. This means:

- **Every zone can learn.** Different zones have different models.
- **The framework composes intelligence.** A neural component in a child zone inherits the parent's constraints automatically.
- **Decisions can use learning.** The permission engine can consult neural outputs.

#### The three built-in primitives

The toolkit ships with three:

1. **`Predictor`** — a trainable linear model with sigmoid output.
2. **`AnomalyDetector`** — an autoencoder for detecting outliers.
3. **`RoleMiner`** — unsupervised discovery of role structures.

Plus, any object with a `predict` method works.

#### Predictor

A `Predictor` is trained on labelled data and produces a probability:

```python
from czoi import Predictor
import numpy as np

# Training data: [hours_worked, projects_completed, years_at_company]
X = np.array([
    [50, 10, 1],   # low tenure, high output → not leaving
    [30,  2, 5],   # mid tenure, low output → maybe leaving
    [60, 15, 8],   # high tenure, high output → staying
    [25,  1, 4],   # low output, mid tenure → leaving
    [55, 12, 2],   # low tenure, high output → staying
    [20,  0, 3],   # low output → leaving
])
y = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])   # 1 = will leave

model = Predictor("attrition", threshold=0.5)
model.fit(X, y, epochs=1000, lr=0.1)

# Predict for a new employee
new_employee = {"hours": 25, "projects": 1, "tenure": 4}
score = model.predict(new_employee)
print(f"Attrition probability: {score:.3f}")

# Or ask for a boolean
if model.fires(new_employee):
    print("High attrition risk")
```

The model learns to weight the features. In this case, `projects` and `hours` are strong negative predictors (few projects → likely leaving), while tenure is ambiguous.

#### Training data format

`fit` accepts:
- A numpy array of shape `(n_samples, n_features)`.
- A list of dicts (converted to vectors by key order).
- A list of lists.

The keys used in `predict` must match the training keys' order. If you train with a dict, make sure to pass dicts with the same key order to `predict`.

#### AnomalyDetector

Anomaly detection is fundamentally different from prediction: you have no labels. You want to learn what's *normal* and flag what isn't.

```python
from czoi import AnomalyDetector
import numpy as np

# Normal access patterns: [user_id, hour, minute, operation_id]
normal = np.array([
    [1, 9, 15, 3],
    [1, 10, 30, 4],
    [2, 11, 45, 3],
    [2, 14, 20, 4],
    [3, 9, 0, 3],
    [3, 13, 55, 4],
    [4, 10, 10, 3],
    [4, 15, 25, 4],
])

# Fit — this learns the manifold of normal behaviour
detector = AnomalyDetector(
    name="access_pattern",
    input_dim=4,
    latent_dim=2,
    seed=42,
)
detector.fit(normal, epochs=500, lr=0.05)

# A normal request
normal_request = np.array([1, 10, 20, 3])
print(f"Normal score: {detector.score(normal_request):.3f}")
print(f"Is anomalous? {detector.is_anomalous(normal_request)}")

# An anomalous request — 3am, high-privilege operation
anomalous_request = np.array([1, 3, 0, 99])
print(f"Anomalous score: {detector.score(anomalous_request):.3f}")
print(f"Is anomalous? {detector.is_anomalous(anomalous_request)}")
```

The autoencoder compresses input through a bottleneck, then reconstructs it. Normal samples reconstruct well (low error); anomalous ones reconstruct poorly (high error). The threshold is auto-calibrated at the 95th percentile of training scores.

#### The features matter

Anomaly detection is only as good as the features. A raw user ID is not meaningful — the autoencoder can memorise which IDs appear, but can't generalise. Better features are:

- **Time of day** (normalised to [0, 1]).
- **Day of week** (0 = Monday).
- **Operation category** (one-hot encoded).
- **Rate of requests** (requests per minute).
- **Historical similarity** (cosine to the user's past behaviour).

CZOA doesn't dictate the feature engineering — that's your job — but it gives you a place to put the detector.

#### RoleMiner

Role mining is the discovery of role structures from access logs. Given a binary matrix (users × operations), cluster users with similar access patterns into candidate roles.

```python
from czoi import RoleMiner
import numpy as np

# Users 0-9 in one team, users 10-19 in another
X = np.zeros((20, 6))
X[0:10, 0:3] = 1.0    # users 0-9 use operations 0-2
X[10:20, 3:6] = 1.0   # users 10-19 use operations 3-5

# Slight noise to simulate real-world imperfection
X[2, 3] = 1.0
X[15, 4] = 0.0

operation_names = ["read_doc", "edit_doc", "share_doc",
                   "view_code", "commit_code", "review_code"]

miner = RoleMiner(latent_dim=4, min_cluster_size=2, seed=42)
result = miner.mine(X, operation_names)

print(f"Discovered {result.n_clusters} clusters")
for role, ops in result.suggested_roles.items():
    print(f"  {role}: {ops}")
print(f"Confidence: {result.confidence}")
```

Output:

```
Discovered 2 clusters
  MinedRole_0: ['read_doc', 'edit_doc', 'share_doc']
  MinedRole_1: ['view_code', 'commit_code', 'review_code']
Confidence: {'MinedRole_0': 1.0, 'MinedRole_1': 0.9667}
```

The miner has correctly identified the two teams from the raw access data.

**Important caveat**: RoleMiner produces *suggestions*. A human administrator should review them before making them real roles. The paper's pipeline is:

1. Encode users/operations.
2. Train an autoencoder.
3. Cluster latent codes.
4. **Validate against identity and access constraints.**
5. Present high-confidence candidates.

Step 4 is critical. A mined role might violate SoD or span zones that shouldn't be crossed. The toolkit gives you the suggestions; you enforce the policy.

#### Attaching neural components to zones

```python
team = builder.add_zone("Engineering", parent=builder.root)

attrition_model = Predictor("attrition", threshold=0.5)
attrition_model.fit(...)
team.add_neural("attrition", attrition_model)

anomaly_detector = AnomalyDetector("access", input_dim=4, latent_dim=2)
anomaly_detector.fit(...)
team.add_neural("access_anomaly", anomaly_detector)
```

Neural components live in `zone.neural` — a dict you can inspect, iterate, and pass around.

```python
for name, model in team.neural.items():
    print(f"{name}: {type(model).__name__}")
```

#### Using neural components in daemons

```python
from czoi import Daemon, DaemonSignal

class AttritionDaemon(Daemon):
    def __init__(self, zone, parent=None):
        super().__init__("AttritionDaemon", parent=parent, interval=60.0)
        self.zone = zone

    def monitor(self):
        model = self.zone.neural["attrition"]
        for user in self.zone.users.values():
            features = {
                "hours": user.attributes.get("hours", 0),
                "projects": user.attributes.get("projects", 0),
                "tenure": user.attributes.get("tenure", 0),
            }
            score = model.predict(features)
            if score > 0.8:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"user": user.name, "risk": score},
                )
```

The daemon reads the model from `zone.neural`, applies it to the zone's users, and emits signals. This is the paper's §5.1 pattern: neural components drive monitoring.

#### Using neural components in permission decisions

```python
from czoi import NeuralContribution, Decision

def context_hook(user, operation, zone, base):
    """Deny access if the anomaly detector flags the user's current pattern."""
    if operation.name not in ("prescribe", "edit_payroll"):
        return base

    detector = zone.neural.get("access_anomaly")
    if detector is None:
        return base

    features = [
        user.attributes.get("last_hour", 12),
        user.attributes.get("last_minute", 0),
        user.attributes.get("last_op_id", 0),
        user.attributes.get("request_rate", 1),
    ]
    import numpy as np
    if detector.is_anomalous(np.array(features)):
        return Decision.DENY

    return base

builder.permission_engine.set_neural_contribution(
    NeuralContribution(context_hook)
)
```

Now every high-privilege decision consults the anomaly detector. If the user's current pattern looks anomalous, the decision is denied — even if the user has the role.

#### The limits

Neural components are **not** a replacement for constraints. They're a supplement:

- **Constraints are declarative and verifiable.** They're part of the formal policy. You can prove things about them.
- **Neural components are statistical and heuristic.** They respond to patterns but have no formal guarantees.

The right composition: constraints enforce the hard rules; neural components handle the soft ones. Never rely on a neural component for a security guarantee.

#### Exercises

1. **Train a Predictor.** Create a `Predictor` for "will miss deadline" using synthetic data. Attach it to a `Projects` zone. Write a daemon that flags projects above 0.7.

2. **Build an anomaly detector.** Use `AnomalyDetector` on synthetic access logs. Determine the right threshold by sweeping it and observing false positives vs false negatives.

3. **Run the RoleMiner.** Generate a synthetic access matrix with 3 clear groups. Run the miner. How many clusters does it find? Are they the right ones?

4. **Compose.** Build a system where the anomaly detector's output feeds a permission hook. Show a case where a legitimate user is denied because their access pattern is unusual. Discuss whether this is the right behaviour.

5. **Compare.** Train a `Predictor` on 100 samples and on 10,000 samples. Measure the accuracy on a held-out set. How much does the extra data help?

#### Further reading

- The CZOA paper, §5 (Learning-enhanced access control)
- The CZOA paper, §5.1 (Neural-enhanced permission mining)
- The User Guide, §10 (Neural Components)

---

### Chapter 8 — Semantic Embeddings

#### Learning objectives

- Understand what embeddings are and why they matter for cross-zone reasoning.
- Train an alignment layer with contrastive loss.
- Use embeddings for cross-zone role matching and anomaly detection.

#### The problem embeddings solve

An organisation has many zones. Each has roles. Some roles are semantically similar even though they have different names:

- `Engineer` in zone A and `Developer` in zone B do the same thing.
- `Manager` in zone A and `TeamLead` in zone B have similar responsibilities.
- `Auditor` and `Controller` both check things.

How do you know? You could hard-code mappings. Or you could let the semantic similarity of the role names and their permissions emerge from data.

Embeddings turn "similarity" into geometry: two entities are similar if their vectors are close.

#### The EmbeddingService

```python
from czoi import EmbeddingService

# Hash-based by default — deterministic, no dependencies
emb = EmbeddingService(dimension=64)

# Or with a transformer backend for real semantics
emb = EmbeddingService(
    model_name="all-MiniLM-L6-v2",
    use_transformer=True,
)
```

Hash-based embeddings are useful for:
- Unit tests (fast, deterministic).
- Offline environments.
- When you just need "different strings → different vectors."

Transformer embeddings are useful for:
- Real semantic similarity.
- Cross-zone role matching.
- Anomaly detection where "similar operations" matters.

#### Basic usage

```python
from czoi import Operation

op1 = Operation("view_patient")
op2 = Operation("read_patient_record")
op3 = Operation("process_payroll")

v1 = emb.embed(op1.name)
v2 = emb.embed(op2.name)
v3 = emb.embed(op3.name)

print(f"view_patient ↔ read_patient_record: {emb.similarity(v1, v2):.3f}")
print(f"view_patient ↔ process_payroll:     {emb.similarity(v1, v3):.3f}")
```

With a transformer backend:

```
view_patient ↔ read_patient_record: 0.72
view_patient ↔ process_payroll:     0.15
```

The first pair is semantically related (both concern viewing patient data). The second pair is unrelated.

#### Embedding operations and roles

The service provides helpers:

```python
v_op = emb.embed_operation(op1)
v_role = emb.embed_role(doctor_role)
```

`embed_operation` combines the application name and operation name:

```python
def embed_operation(self, operation):
    app = getattr(operation, "application", None)
    app_name = getattr(app, "name", "") if app else ""
    return self.embed(f"{app_name}.{operation.name}")
```

`embed_role` averages the embeddings of the role's permissions:

```python
def embed_role(self, role):
    vectors = [self.embed_operation(op) for op in role.base_permissions]
    return np.mean(vectors, axis=0)
```

This gives you a "semantic fingerprint" of a role — what it can do, expressed as a vector.

#### The alignment functor

Local embeddings live in zone-specific spaces. But you often need a shared space to compare across zones. The paper's `E_align` functor projects local embeddings into a global space.

In the toolkit, alignment is a trainable linear layer:

```python
# Default alignment: normalisation
v_local = emb.embed("Emergency.attending_physician")
v_global = emb.align_to_global(v_local)
```

By default, this just normalises the vector. But you can **train** an alignment matrix using labelled pairs:

```python
positives = [
    (emb.embed("attending_physician"), emb.embed("doctor")),
    (emb.embed("senior_nurse"), emb.embed("registered_nurse")),
    (emb.embed("view_patient"), emb.embed("read_patient_record")),
]
negatives = [
    (emb.embed("attending_physician"), emb.embed("payroll_clerk")),
    (emb.embed("senior_nurse"), emb.embed("auditor")),
]

emb.train_alignment(positives, negatives, epochs=200, lr=0.01, margin=0.5)
```

The training objective:

```
sum_positives ||a - b||²
- sum_negatives max(0, margin - ||a - b||)²
```

In English: pull positive pairs together, push negative pairs apart.

After training, `align_to_global` uses the learned matrix:

```python
v1 = emb.align_to_global(emb.embed("attending_physician"))
v2 = emb.align_to_global(emb.embed("doctor"))
v3 = emb.align_to_global(emb.embed("payroll_clerk"))

print(f"attending ↔ doctor:       {emb.similarity(v1, v2):.3f}")
print(f"attending ↔ payroll_clerk: {emb.similarity(v1, v3):.3f}")
```

The first similarity should be high, the second low.

#### Persistence

Save and load the alignment layer:

```python
emb.save_alignment("alignment.npy")
# Later...
emb.load_alignment("alignment.npy")
```

The alignment is a numpy array you can version alongside your models.

#### Use case 1: cross-zone role matching

Given a role in one zone, find semantically similar roles in other zones:

```python
def find_similar_roles(source_role, target_zone, threshold=0.75):
    source_vec = emb.align_to_global(emb.embed_role(source_role))
    results = []
    for role in target_zone.roles.values():
        target_vec = emb.align_to_global(emb.embed_role(role))
        sim = emb.similarity(source_vec, target_vec)
        if sim > threshold:
            results.append((role, sim))
    return sorted(results, key=lambda x: -x[1])

# Find roles in the ICU zone similar to the Emergency Attending
similar = find_similar_roles(attending, icu_zone, threshold=0.6)
for role, score in similar:
    print(f"{role.name}: {score:.3f}")
```

This is the paper's §5.2 "cross-zone understanding" pattern. It enables:

- **Role unification**: if two zones have equivalent roles, merge them.
- **Permission transfer**: grant one role the permissions of a similar role.
- **Migration**: when merging zones, identify which roles map to each other.

#### Use case 2: anomaly detection via embedding distance

For each user, maintain a centroid of their historical behaviour. Flag requests far from the centroid:

```python
def update_centroid(user, operation, emb, alpha=0.1):
    op_vec = emb.embed_operation(operation)
    old = user.attributes.get("_centroid")
    if old is None:
        user.attributes.set("_centroid", op_vec)
    else:
        new = (1 - alpha) * old + alpha * op_vec
        user.attributes.set("_centroid", new)

def is_unusual(user, operation, emb, threshold=0.7):
    centroid = user.attributes.get("_centroid")
    if centroid is None:
        return False
    op_vec = emb.embed_operation(operation)
    sim = emb.similarity(centroid, op_vec)
    return sim < threshold
```

Every time a user performs an operation, update their centroid. Before allowing a new operation, check its similarity to the centroid. If it's too far, flag it.

This is a simple online anomaly detector. It complements the autoencoder by handling the "this doesn't look like what this user usually does" case.

#### Use case 3: nearest-neighbour search

Given a new operation, find the most similar existing operations:

```python
def nearest_operations(target_op, all_ops, emb, k=5):
    target_vec = emb.embed_operation(target_op)
    scored = []
    for op in all_ops:
        if op is target_op:
            continue
        vec = emb.embed_operation(op)
        scored.append((op, emb.similarity(target_vec, vec)))
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
```

This is useful for:
- Suggesting which existing role could cover a new operation.
- Detecting duplicate operations.
- Auto-grouping operations into applications.

#### Hash-based vs transformer embeddings

**Hash-based** (default):

- Pros: no dependencies, fast, deterministic, works offline.
- Cons: no semantics — "patient" and "doctor" are unrelated because their hashes differ.

**Transformer**:

- Pros: real semantic similarity, generalises to unseen text.
- Cons: requires `sentence-transformers`, slower, may not reflect your domain.

**Recommendation**: start with hash-based for unit tests, switch to transformer for production. Train an alignment layer on domain-specific pairs to adapt the transformer to your organisation.

#### A word on dimensions

`dimension=64` is fine for most purposes. Larger (256, 512) captures more nuance but is slower. Smaller (16, 32) is faster but loses detail.

For cross-zone matching with many roles (100+), 128 is a reasonable default. For anomaly detection, 32 is usually enough.

#### Exercises

1. **Compute similarities.** Take 10 operation names. Compute pairwise similarities with hash-based embeddings. Then with transformer embeddings. How do they differ?

2. **Train alignment.** Create 20 positive pairs and 20 negative pairs from your domain. Train an alignment. Verify that positive pairs become more similar and negative pairs less.

3. **Find similar roles.** Given a role in one zone, find semantically similar roles in a second zone. What threshold works best?

4. **Anomaly centroid.** Implement a per-user centroid tracker. Run 50 simulated operations for one user. Then simulate 5 unusual operations. How well does centroid distance flag them?

5. **Reflect on ambiguity.** "audit_payroll" — is this closer to "view_payroll" (read) or "approve_payroll" (write)? What does the embedding say? Does it match your intuition?

#### Further reading

- The CZOA paper, §5.2 (Semantic embeddings for cross-zone understanding)
- The User Guide, §11 (Semantic Embeddings)

---

### Chapter 9 — Adaptive Access Control

#### Learning objectives

- Understand when and why permissions should adapt.
- Implement adaptive grants and revocations.
- Use neural contributions for context-aware decisions.
- Preserve safety while adapting.

#### The problem

Static permissions work well when conditions are stable. But conditions change:

- A flu outbreak causes a surge in patient arrivals.
- A market crash requires rapid trading-limit adjustments.
- A supplier failure demands reallocating workers across roles.

During these events, the normal permission structure is too rigid. You need to adapt.

CZOA's approach: **adaptation is a first-class operation**, subject to formal safety guarantees.

#### Two mechanisms

The toolkit gives you two ways to adapt:

1. **Dynamic grants/revocations**: change a role's base permissions at runtime.
2. **Neural contributions**: adjust individual decisions based on context.

Both are safe when they follow Theorem 7 of the paper.

#### Mechanism 1: Dynamic grants

The simplest adaptation. When a condition triggers, grant a role a permission. When the condition passes, revoke it.

```python
from czoi import CZOABuilder, Decision, Role, Operation, Application

builder = CZOABuilder("Hospital")
hospital = builder.add_zone("CityHospital", parent=builder.root)
emergency = builder.add_zone("Emergency", parent=hospital, atomic=True)

app = Application("EMR", zone=hospital)
prescribe = app.add_operation(Operation("prescribe"))
hospital.add_application(app)

senior_nurse = Role("SeniorNurse", zone=hospital)
hospital.add_role(senior_nurse)

# Normal conditions: SeniorNurse cannot prescribe
engine = builder.permission_engine
print(engine.decide(alice, prescribe, emergency).name)   # DENY

# Surge begins
hospital.grant(senior_nurse, prescribe)
print(engine.decide(alice, prescribe, emergency).name)   # ALLOW

# Surge ends
hospital.revoke(senior_nurse, prescribe)
print(engine.decide(alice, prescribe, emergency).name)   # DENY
```

Note: `zone.grant` and `zone.revoke` invalidate the permission cache automatically. The change takes effect on the next `decide` call.

#### Wiring it to a daemon

A realistic scenario: a daemon detects the surge and triggers the grant.

```python
from czoi import Daemon, DaemonSignal

class SurgeDaemon(Daemon):
    def __init__(self, hospital, senior_nurse_role, prescribe_op, parent=None):
        super().__init__("SurgeDaemon", parent=parent, interval=5.0)
        self.hospital = hospital
        self.role = senior_nurse_role
        self.op = prescribe_op
        self.active = False

    def monitor(self):
        arrivals = self.hospital.properties.get("recent_arrivals", 0)
        if not self.active and arrivals > 200:
            self.active = True
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "surge_started", "arrivals": arrivals},
            )
        elif self.active and arrivals < 100:
            self.active = False
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"event": "surge_ended"},
            )

class DirectorDaemon(Daemon):
    def __init__(self, hospital, ops, parent=None):
        super().__init__("Director", parent=parent, interval=1.0)
        self.hospital = hospital
        self.ops = ops
        self.active = False

    def on_signal(self, signal, payload, source=None):
        event = payload.get("event")
        if event == "surge_started" and not self.active:
            self.active = True
            self.hospital.grant(
                self.hospital.roles["SeniorNurse"],
                self.ops["prescribe"],
            )
        elif event == "surge_ended" and self.active:
            self.active = False
            self.hospital.revoke(
                self.hospital.roles["SeniorNurse"],
                self.ops["prescribe"],
            )

# Wire up
surge = SurgeDaemon(hospital, senior_nurse, prescribe)
director = DirectorDaemon(hospital, {"prescribe": prescribe})
surge.parent = director

builder.add_daemon(director)
builder.add_daemon(surge)
```

Now the adaptation is fully automatic: daemons monitor; the director acts.

#### Mechanism 2: Neural contributions

Sometimes you don't want to change roles — you want to change individual decisions based on fine-grained context.

```python
from czoi import NeuralContribution, Decision

def surge_hook(user, operation, zone, base):
    """Elevate SeniorNurse during surge, but only for prescriptions
    of non-controlled substances."""
    if (operation.name == "prescribe"
            and user.has_role("SeniorNurse")
            and zone.properties.get("surge_active", False)):
        # Check the drug category via user attributes
        drug_class = user.attributes.get("prescribing_drug_class", "general")
        if drug_class == "general":
            return Decision.ALLOW
    return base

builder.permission_engine.set_neural_contribution(
    NeuralContribution(surge_hook)
)
```

The hook receives the base decision and can return:

- **The base decision** — leave it unchanged.
- **`Decision.ALLOW`** — elevate.
- **`Decision.DENY`** — lock down (this is powerful; use carefully).

#### Comparison: when to use which

| Situation | Use |
|---|---|
| Well-defined event (surge, crash, incident) | **Grant/revoke** — clear boundaries |
| Context-sensitive (time of day, attributes) | **Hook** — evaluated every time |
| Cross-cutting policy applied to many roles | **Constraint** — one expression, evaluated everywhere |
| Long-term structural change | **Refactor roles** — not adaptation |

#### Safety guarantees (Theorem 7)

The paper states: an adaptive update is safe iff:

1. **Monotonicity**: permissions only increase without explicit revocation.
2. **Constraint satisfaction**: all identity and access constraints hold.
3. **Audit trail**: the change is recorded.

The toolkit helps you satisfy all three:

**For monotonicity:**

```python
# Good — the grant is explicit and reversible
hospital.grant(role, op)
# ... later ...
hospital.revoke(role, op)

# Bad — mutating the set directly skips cache invalidation and audit
role.base_permissions.add(op)
```

**For constraint satisfaction:**

The engine evaluates constraints on every decision. If a grant violates a constraint, the engine denies at decision time. So the grant itself doesn't break safety — the decision does, and it's caught.

**For audit trail:**

```python
from czoi import PermissionEngine

builder.permission_engine = PermissionEngine(audit_enabled=True)
for zone in builder.root.walk():
    zone.set_permission_engine(builder.permission_engine)

# Every grant/revoke is reflected in subsequent audit records
for record in builder.permission_engine.audit:
    print(f"{record.timestamp} {record.user} {record.operation} "
          f"@{record.zone} → {record.decision.name}")
```

#### Anti-patterns

**Anti-pattern 1: adapting without a trigger.**

```python
# Bad
if random.random() < 0.1:
    hospital.grant(role, op)
```

Adaptation must be event-driven, not random.

**Anti-pattern 2: adapting without a boundary.**

```python
# Bad
def my_hook(user, operation, zone, base):
    return Decision.ALLOW   # always allow
```

Hook must have a boundary — when does the elevation apply?

**Anti-pattern 3: forgetting to revoke.**

```python
# Bad
hospital.grant(role, op)
# ... never revoked
```

Every grant should have a corresponding revoke path. Otherwise you've just changed the static policy.

**Anti-pattern 4: complex hook logic.**

```python
# Bad
def hook(user, operation, zone, base):
    if (user.attributes.get("a") > 3
            and user.attributes.get("b") < 5
            and "x" in user.name
            and random.random() < 0.7):
        return Decision.ALLOW
    return base
```

Complex logic belongs in a constraint, not a hook. Hooks should be one-liners that reference well-named predicates.

#### A realistic scenario

A financial trading desk has these roles: `Trader`, `RiskManager`, `Compliance`.

Normal conditions: traders can trade; risk managers approve trades above a threshold; compliance observes.

Market crash: the circuit breaker daemon triggers. During the crash:

- Traders can only trade small orders.
- Risk managers can elevate their approval threshold.
- Compliance can halt trading.

```python
from czoi import CZOABuilder, Application, Operation, Role, User, Decision, NeuralContribution

builder = CZOABuilder("TradingDesk")
desk = builder.add_zone("Equities", parent=builder.root, atomic=True)

app = Application("OMS", zone=desk)
trade_small = app.add_operation(Operation("trade_small"))
trade_large = app.add_operation(Operation("trade_large"))
approve = app.add_operation(Operation("approve_trade"))
halt = app.add_operation(Operation("halt_trading"))
desk.add_application(app)

trader = Role("Trader", zone=desk,
              base_permissions=[trade_small, trade_large])
risk = Role("RiskManager", zone=desk, base_permissions=[approve])
compliance = Role("Compliance", zone=desk, base_permissions=[halt])
for r in (trader, risk, compliance):
    desk.add_role(r)

# Adaptive hook: during crash, deny large trades
def crash_hook(user, operation, zone, base):
    if operation.name == "trade_large" and zone.properties.get("crash", False):
        return Decision.DENY
    return base

builder.permission_engine.set_neural_contribution(
    NeuralContribution(crash_hook)
)

# Normal: large trade allowed
alice = User("alice", roles={"Trader"})
desk.add_user(alice)
print(builder.permission_engine.decide(alice, trade_large, desk).name)
# ALLOW

# Crash: large trade denied
desk.properties.set("crash", True)
print(builder.permission_engine.decide(alice, trade_large, desk).name)
# DENY
```

This hook dynamically adjusts the trader's permissions based on the desk's crash state. Small trades remain allowed; large trades are blocked.

#### Exercises

1. **Surge grant.** Build a hospital example where the surge daemon grants `prescribe` to senior nurses. Verify that the decision changes.

2. **Time-based adaptation.** Write a hook that grants `view_audit_log` only during business hours (9am–5pm).

3. **Compound adaptation.** Write a hook that combines two conditions: surge active AND user has been trained (attribute flag). Grant only when both hold.

4. **Boundary test.** Take the crash-hook example and add a counter. How many grants/revocations happen in a simulated 100-tick run?

5. **Safety audit.** Add `audit_enabled=True`. Show that every decision during the surge is recorded with the correct stage.

#### Further reading

- The CZOA paper, §5.3 (Adaptive access control)
- The CZOA paper, Theorem 7 (Safety of adaptation)
- The User Guide, §12 (Adaptive Access Control)

---

## Part IV — Governance

### Chapter 10 — Constraints via UniLog

#### Learning objectives

- Understand the four families of constraints (I, T, G, C).
- Write UniLang constraints for real organisational policies.
- Register custom predicates.
- Understand how constraints interact with permissions.

#### Why a formal language?

You could write policies in Python:

```python
def is_allowed(user, operation, zone):
    if user.role == "Doctor" and user.role == "Auditor":
        return False
    ...
```

But Python policies have problems:

- **Not declarative.** The rules are entangled with control flow.
- **Hard to verify.** No formal semantics.
- **Not portable.** Move to a different system → rewrite all policies.
- **Not auditable.** An auditor reads Python and tries to infer the rules.

CZOA uses **UniLang** — a formal logic language. Rules are declarative, verifiable, portable, and readable.

#### The four families

**Γ = (I, T, G, C)**

| Family | Name | Purpose |
|---|---|---|
| **I** | Identity | Invariants that must always hold |
| **T** | Trigger | Event-condition-action rules |
| **G** | Goal | Optimisation objectives |
| **C** | Access | Permission-related policies |

Different families serve different purposes; the classification helps you reason about which policy does what.

#### The signature

Every UniLang constraint starts with a `signature` block declaring the vocabulary:

```python
builder.add_access_constraint("""
    signature {
        sort User, Role, Operation, Zone;
        constant Doctor : Role;
        constant Auditor : Role;
        function parent(z: Zone) : Zone;
        predicate hasRole(u: User, r: Role);
        predicate inZone(u: User, z: Zone);
        predicate prescribe(u: User, o: Operation);
    }
    forall u: User . not (hasRole(u, Doctor) and hasRole(u, Auditor))
""")
```

The signature declares:

- **Sorts**: the types of entities (User, Role, Operation, Zone).
- **Constants**: named entities (Doctor, Auditor).
- **Functions**: mappings (parent, which takes a Zone and returns a Zone).
- **Predicates**: relations (hasRole, which takes a User and Role and returns bool).

After the signature, the constraint itself is written as a first-order logic formula.

#### The four families in practice

**Access constraints (C)** — the most common:

```python
builder.add_access_constraint("""
    signature {
        sort User;
        predicate canPrescribe(u: User);
        predicate canDispense(u: User);
    }
    forall u: User . not (canPrescribe(u) and canDispense(u))
""")
```

Separation of duty: no user can both prescribe and dispense.

**Identity constraints (I)** — invariants:

```python
builder.add_identity_constraint("""
    signature {
        sort Zone, User;
        predicate inZone(u: User, z: Zone);
        function parent(z: Zone) : Zone;
    }
    forall u: User, z: Zone .
        (inZone(u, z) and parent(z) != z) -> inZone(u, parent(z))
""")
```

If a user is in a zone, they're also in its parent. This is the containment principle formalised.

**Trigger constraints (T)** — event-condition-action:

```python
builder.add_trigger_constraint("""
    signature {
        sort Patient;
        predicate critical(p: Patient);
        predicate alerted(p: Patient);
    }
    forall p: Patient . critical(p) -> alerted(p)
""")
```

If a patient becomes critical, they must be alerted.

**Goal constraints (G)** — optimisation:

```python
builder.add_goal_constraint("""
    signature {
        sort KPI;
        predicate minimise(k: KPI);
        predicate optimise(k: KPI);
    }
    forall k: KPI . minimise(k) -> optimise(k)
""")
```

Every KPI that should be minimised is a target for optimisation.

#### Built-in predicates

The toolkit exposes several predicates on every constraint:

| Predicate | Meaning |
|---|---|
| `inZone(u, z)` | User `u` is registered in zone `z` |
| `childOf(c, p)` | Zone `c` is a direct child of zone `p` |
| `hasRole(u, r)` | User `u` holds role `r` |
| `canPerform(u, o)` | User `u` is allowed to perform operation `o` |

And one function:

| Function | Meaning |
|---|---|
| `parent(z)` | The parent zone of `z` (or `z` itself for the root) |

These let you write constraints without defining everything from scratch.

#### Custom predicates

For domain-specific rules, register your own:

```python
builder.register_predicate(
    "onShift",
    lambda u: u.attributes.get("shift") in ("day", "evening"),
)

builder.register_predicate(
    "highRisk",
    lambda op: op.attributes.get("risk_level") == "high",
)

builder.register_predicate(
    "zoneFull",
    lambda z: z.properties.get("occupancy", 0) >= z.properties.get("capacity", 1),
)

builder.add_access_constraint("""
    signature {
        sort User, Operation, Zone;
        predicate onShift(u: User);
        predicate highRisk(o: Operation);
        predicate zoneFull(z: Zone);
        predicate inZone(u: User, z: Zone);
    }
    forall u: User, z: Zone, o: Operation .
        (inZone(u, z) and zoneFull(z) and not onShift(u))
        -> not inZone(u, z)
""")
```

The lambda receives the entity (user, operation, or zone) and returns a bool. It's evaluated against the live system, so it can read current state.

#### Combining constraints

Multiple constraints are **conjunctive** — all must hold:

```python
builder.add_access_constraint("...")   # rule 1
builder.add_access_constraint("...")   # rule 2
builder.add_access_constraint("...")   # rule 3

# Any decision must satisfy all three.
```

To express OR, use a single constraint with `or`:

```python
builder.add_access_constraint("""
    forall u: User . isManager(u) or isAuditor(u)
""")
```

#### How constraints interact with permissions

The engine flow:

1. Find a covering role for the operation.
2. Call `constraint_manager.is_satisfied(user, operation, zone)`.
3. If it returns `False`, the decision is `DENY`.
4. Otherwise, the decision is `ALLOW`.

```python
def _local_decide(self, user, operation, zone):
    roles = self._roles_in_zone(user, zone)
    if not roles:
        return Decision.INCONCLUSIVE

    effective = self._effective_permissions(roles)
    if operation not in effective:
        return Decision.INCONCLUSIVE

    if zone.constraints is not None:
        checker = getattr(zone.constraints, "is_satisfied", None)
        if callable(checker) and not checker(user, operation, zone):
            return Decision.DENY

    return Decision.ALLOW
```

This means **access constraints have veto power** over role-based permissions. A user with the covering role can still be denied if a constraint fails.

#### Constraint precedence

Parent constraints override child constraints:

```
Γ_child ⊆ Γ_parent
```

If a parent forbids an operation, the child cannot allow it. If a child forbids an operation, only that child is affected.

Practically, this means: put broad policies at high levels, specific ones at low levels.

#### Checking constraints manually

```python
results = builder.constraint_manager.check_all()
for kind, ok in results.items():
    print(f"{kind}: {'OK' if ok else 'VIOLATED'}")
```

Or scoped to a zone:

```python
results = builder.constraint_manager.check_zone(emergency)
```

Useful for diagnostics and testing.

#### Common patterns

**Pattern 1: Separation of duty.**

```python
forall u: User . not (canApprove(u) and canExecute(u))
```

**Pattern 2: Role combination denial.**

```python
forall u: User . not (hasRole(u, Vendor) and hasRole(u, Approver))
```

**Pattern 3: Attribute-based.**

```python
forall u: User . (hasRole(u, Manager) -> hasAttribute(u, "training_complete"))
```

**Pattern 4: Temporal.**

```python
G (monday -> F_[0,5] report_sent)
```

The temporal operators `G` (globally) and `F_[lo, hi]` (finally within a range) let you express time-bounded requirements.

#### The limits of UniLang

UniLang is a **first-order logic with temporal extensions**. It's expressive but not Turing-complete. That's a feature, not a bug: it means constraints are decidable (for finite domains, which enterprise systems are). You can't write an infinite loop; you can't write arbitrary code.

If you need computation beyond first-order logic, put it in a neural component or a daemon — not in a constraint.

#### Exercises

1. **Write a SoD constraint.** Enforce that no user can both `submit_expense` and `approve_expense`.

2. **Containment formalised.** Write an identity constraint that says: "for every user in a zone, there is a chain of parent relations to the root."

3. **Attribute-based.** Write a constraint using a custom predicate `hasClearance(u, level)` that requires level ≥ 3 for a sensitive operation.

4. **Compile and test.** Register a constraint and check that `check_all` returns `True`. Then deliberately violate it and see `False`.

5. **Combination.** Write two constraints that only jointly prevent an attack. Test that removing either one breaks security.

#### Further reading

- The CZOA paper, §3, item 8 (Constraint System)
- The UniLog toolkit documentation
- The User Guide, §8 (Constraints with UniLog)

---

### Chapter 11 — Daemons and Continuous Monitoring

#### Learning objectives

- Understand what daemons are and how they differ from permission checks.
- Build hierarchical daemon trees.
- Use signals for coordination.
- Handle errors and lifecycle.

#### The problem

Permission checks happen **on demand**. A user requests an operation; the engine checks; the decision is made. This works for one-shot requests but doesn't cover:

- **Continuous conditions**: "warn me if any user has been idle for 24 hours."
- **Aggregate conditions**: "alert if more than 10 % of users are failing login."
- **Real-time conditions**: "halt trading if the price drops 5 % in 1 minute."

These need a different mechanism: **continuous monitoring**.

CZOA uses **daemons** — processes that run periodically, read state, and emit signals.

#### The Daemon base class

```python
from czoi import Daemon

class BatteryDaemon(Daemon):
    def __init__(self, robots, threshold=0.2, parent=None):
        super().__init__("BatteryDaemon", parent=parent, interval=1.0)
        self.robots = robots
        self.threshold = threshold

    def monitor(self):
        for r in self.robots:
            if r.attributes.get("battery", 1.0) < self.threshold:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"robot": r.name, "battery": r.attributes.get("battery")},
                )
```

The pieces:

- **`name`** — an identifier.
- **`parent`** — where signals go (None for root daemons).
- **`interval`** — how often to run (in seconds).
- **`monitor`** — the periodic work.

#### Signals

Daemons emit **signals** rather than taking direct action. A signal is a typed message with a payload.

```python
from czoi import DaemonSignal

# Predefined types
DaemonSignal.STATE_NORMAL
DaemonSignal.STATE_WARNING
DaemonSignal.STATE_CRITICAL
DaemonSignal.REVOKE
DaemonSignal.ESCALATE
```

Signals propagate **up the daemon tree**:

```
BatteryDaemon → FleetDaemon → OrganizationDaemon
```

The `handle_signal` method (in the base class) calls `on_signal` locally, then forwards to the parent. This gives you a natural escalation mechanism.

#### Handling signals

```python
class FleetDaemon(Daemon):
    def __init__(self, parent=None):
        super().__init__("FleetDaemon", parent=parent, interval=2.0)
        self.warnings = []
        self.criticals = []

    def on_signal(self, signal, payload, source=None):
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((source.name, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((source.name, payload))
```

`on_signal` receives:

- The signal type.
- The payload dict.
- The source daemon (who emitted it).

This is where you act on signals: record them, escalate, trigger compensating actions.

#### Running daemons

**Synchronous** — for tests and step-based simulations:

```python
for step in range(60):
    sim.step()
    builder.daemon_manager.tick()
```

`tick()` invokes every daemon's monitor once, in registration order.

**Asynchronous** — for production:

```python
import asyncio

async def main():
    await builder.daemon_manager.run(duration=300.0)

asyncio.run(main())
```

`run()` schedules each daemon in a thread pool and ticks them at their declared intervals. Slow daemons don't block the event loop.

#### Hierarchical daemons

The real power comes from the tree:

```python
# Root
class OrganizationDaemon(Daemon):
    def on_signal(self, signal, payload, source=None):
        print(f"[ORG] {source.name} → {signal.name}: {payload}")

# Middle
class RegionDaemon(Daemon):
    def on_signal(self, signal, payload, source=None):
        if signal is DaemonSignal.STATE_CRITICAL:
            # Escalate criticals immediately
            print(f"[REGION] Escalating {source.name}'s critical")

# Leaves
class HospitalDaemon(Daemon):
    def monitor(self):
        if some_condition():
            self.emit_signal(DaemonSignal.STATE_CRITICAL, {"details": "..."})

# Wire it up
org = OrganizationDaemon()
region = RegionDaemon(parent=org)
hospital = HospitalDaemon(parent=region)

for d in (org, region, hospital):
    builder.add_daemon(d)
```

Now a critical signal from `hospital` bubbles up through `region` to `org`, and each level has the opportunity to react.

#### The DaemonManager

```python
manager = builder.daemon_manager
print(manager.default_interval)     # 1.0
print(manager.daemons)              # list of registered daemons
```

Methods:

- `add(daemon)` — register a daemon.
- `extend(daemons)` — register several.
- `tick()` — invoke all monitors once (sync).
- `run(duration=None)` — run until stopped (async).
- `stop()` — stop the async loop.
- `shutdown()` — stop and shut down the executor.

#### Error isolation

A daemon that raises doesn't crash its siblings:

```python
def safe_monitor(self):
    if not self.enabled:
        return
    try:
        self.monitor()
    except Exception:
        log.exception("Daemon %s raised", self.name)
```

The manager always calls `safe_monitor`, never `monitor` directly. This is critical for production — one faulty daemon shouldn't take down the whole monitoring system.

#### Lifecycle

Daemons have a `enabled` flag:

```python
daemon.stop()      # disabled
daemon.start()     # enabled
```

Use this to temporarily disable a daemon without removing it.

#### A realistic example

A security operations center:

```python
class LoginRateDaemon(Daemon):
    """Monitor the login rate; emit warnings above threshold."""

    def __init__(self, zone, threshold=100, parent=None):
        super().__init__("LoginRateDaemon", parent=parent, interval=1.0)
        self.zone = zone
        self.threshold = threshold

    def monitor(self):
        rate = self.zone.properties.get("logins_per_minute", 0)
        if rate > self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"rate": rate, "threshold": self.threshold},
            )

class AnomalyDaemon(Daemon):
    """Detect anomalous access patterns."""

    def __init__(self, zone, parent=None):
        super().__init__("AnomalyDaemon", parent=parent, interval=5.0)
        self.zone = zone

    def monitor(self):
        detector = self.zone.neural.get("anomaly")
        if detector is None:
            return
        for user in list(self.zone.users.values())[:100]:     # sample
            features = user.attributes.get("recent_pattern", [0, 0, 0, 0])
            import numpy as np
            if detector.is_anomalous(np.array(features)):
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"user": user.name},
                )

class SecurityDirectorDaemon(Daemon):
    """Root daemon; coordinates responses."""

    def __init__(self, parent=None):
        super().__init__("SecurityDirector", parent=parent, interval=1.0)
        self.escalations = []

    def on_signal(self, signal, payload, source=None):
        if signal is DaemonSignal.STATE_WARNING:
            # If a user was flagged twice in a row, revoke their access
            user = payload.get("user")
            if user:
                self.escalations.append(user)
                if self.escalations.count(user) > 1:
                    # Revoke everything for that user
                    for zone in self.zone.walk():
                        if user in zone.users:
                            target = zone.users[user]
                            for role_name in list(target.roles):
                                role = zone.roles.get(role_name)
                                if role is None:
                                    continue
                                for op in list(role.base_permissions):
                                    zone.revoke(role, op)
```

Now the director daemon watches for repeated warnings and escalates by revoking access.

#### Daemons vs constraints

Daemons and constraints are complementary:

| Aspect | Constraints | Daemons |
|---|---|---|
| When | On every decision | Periodically |
| Evaluated by | The engine, per check | The manager, per tick |
| Language | UniLang | Python |
| Purpose | Policy | Monitoring |
| Action | Block a decision | Emit a signal |
| Guarantee | Formal (decidable) | Statistical (heuristic) |

**Use constraints** for what you must prevent. **Use daemons** for what you want to observe.

#### Common patterns

**Pattern 1: Threshold warning.**

```python
def monitor(self):
    value = self.zone.properties.get("metric", 0)
    if value > self.threshold:
        self.emit_signal(DaemonSignal.STATE_WARNING, {"value": value})
```

**Pattern 2: Rate-of-change.**

```python
def monitor(self):
    current = self.zone.properties.get("value", 0)
    prev = self._prev
    self._prev = current
    if prev is not None:
        delta = current - prev
        if abs(delta) > self.max_delta:
            self.emit_signal(DaemonSignal.STATE_CRITICAL, {"delta": delta})
```

**Pattern 3: Rolling window.**

```python
from collections import deque

def monitor(self):
    self.window.append(self.zone.properties.get("value", 0))
    if len(self.window) > self.window_size:
        self.window.popleft()
    avg = sum(self.window) / len(self.window)
    if avg > self.threshold:
        self.emit_signal(DaemonSignal.STATE_WARNING, {"average": avg})
```

**Pattern 4: Composite.**

```python
def monitor(self):
    for rule in self.rules:
        if rule.evaluate(self.zone):
            self.emit_signal(rule.severity, rule.payload(self.zone))
```

#### Anti-patterns

**Anti-pattern 1: acting directly in monitor.**

```python
# Bad — the monitor should emit, not act
def monitor(self):
    for user in users:
        if user.attributes["suspicious"]:
            revoke_access(user)   # direct action
```

Instead, emit a signal and let the parent daemon act.

**Anti-pattern 2: expensive monitors.**

```python
# Bad — recomputes everything every tick
def monitor(self):
    all_records = load_entire_database()   # expensive!
    for r in all_records:
        ...
```

Daemons should be cheap. Cache where possible.

**Anti-pattern 3: too many daemons.**

If you have 100 daemons running every second, you're doing something wrong. Consolidate related monitors.

**Anti-pattern 4: ignoring intervals.**

```python
# Bad — ignores the interval, might fire 1000x per second
def monitor(self):
    ...
```

Respect the interval. If you need to fire more often, lower the interval; don't ignore it.

#### Exercises

1. **Build a warning daemon.** Create a daemon that warns when the number of failed login attempts exceeds a threshold.

2. **Hierarchical.** Set up a two-level daemon tree. Show that a warning from the child reaches the parent.

3. **Escalation.** Extend the security director example to escalate to a critical if 5 different users are flagged in 10 seconds.

4. **Rate-of-change.** Build a daemon that measures the rate of change of some metric and alerts when it exceeds a threshold.

5. **Daemon shutdown.** Show that calling `daemon.stop()` disables the monitor. Re-enable with `daemon.start()`.

#### Further reading

- The CZOA paper, §5.4 (Constraint daemons)
- The User Guide, §9 (Daemons and Signals)

---

## Part V — Building Real Systems

### Chapter 12 — Designing for a Domain

#### Learning objectives

- Translate an organisation into a CZOI zone tree.
- Choose the right level of abstraction.
- Identify roles, operations, and constraints.
- Anticipate where adaptation will be needed.

#### The design process

CZOA is not just a runtime — it's a design methodology. When you approach a new domain, follow this process:

1. **Map the organisation.** Draw the reporting structure.
2. **Identify the zone tree.** Choose which units become zones.
3. **Define roles.** Enumerate job functions within each zone.
4. **Enumerate operations.** List the atomic actions each zone supports.
5. **Grant base permissions.** Assign operations to roles.
6. **Write constraints.** Capture policy invariants.
7. **Identify adaptation points.** Where will conditions change?
8. **Choose neural components.** Which zones benefit from learning?
9. **Design daemons.** What must be monitored?
10. **Iterate.** Validate with domain experts.

Let's apply this to a concrete domain: **a regional hospital network**.

#### Step 1: Map the organisation

A hospital network might look like:

```
RegionalHealthAuthority
├── CityHospitalA
│   ├── Emergency
│   ├── ICU
│   ├── Surgery
│   └── Pediatrics
├── CityHospitalB
│   ├── Emergency
│   └── ICU
└── RegionalLabs
    ├── Pathology
    └── Radiology
```

#### Step 2: Zone tree

Each unit becomes a zone:

```python
from czoi import CZOABuilder

builder = CZOABuilder("RegionalHealthAuthority")
authority = builder.root

hosp_a = builder.add_zone("CityHospitalA", parent=authority)
emerg_a = builder.add_zone("Emergency", parent=hosp_a, atomic=True)
icu_a = builder.add_zone("ICU", parent=hosp_a, atomic=True)
surgery_a = builder.add_zone("Surgery", parent=hosp_a, atomic=True)
peds_a = builder.add_zone("Pediatrics", parent=hosp_a, atomic=True)

hosp_b = builder.add_zone("CityHospitalB", parent=authority)
emerg_b = builder.add_zone("Emergency", parent=hosp_b, atomic=True)
icu_b = builder.add_zone("ICU", parent=hosp_b, atomic=True)

labs = builder.add_zone("RegionalLabs", parent=authority)
pathology = builder.add_zone("Pathology", parent=labs, atomic=True)
radiology = builder.add_zone("Radiology", parent=labs, atomic=True)
```

**Decision point: how deep?** Go as deep as the organisation goes. If ICUs in a hospital are managed separately from wards, make them separate zones. If they share the same staff and procedures, keep them at one level.

#### Step 3: Roles

Enumerate the job functions. In a hospital:

- `AttendingPhysician`
- `ResidentPhysician`
- `RegisteredNurse`
- `Pharmacist`
- `HospitalAdministrator`
- `QualityOfficer`
- `LabTechnician`

```python
from czoi import Role

attending = Role("AttendingPhysician", zone=authority)
resident = Role("ResidentPhysician", zone=authority)
nurse = Role("RegisteredNurse", zone=authority)
pharmacist = Role("Pharmacist", zone=authority)
admin = Role("HospitalAdministrator", zone=authority)
quality = Role("QualityOfficer", zone=authority)
lab_tech = Role("LabTechnician", zone=authority)

# Seniority
attending.add_junior(resident)
resident.add_junior(nurse)

for r in (attending, resident, nurse, pharmacist, admin, quality, lab_tech):
    authority.add_role(r)
```

**Decision point: where to define roles?** If a role exists across multiple hospitals, define it at the authority level. If it's hospital-specific, define it in that hospital.

#### Step 4: Operations

Enumerate the atomic actions. In a hospital:

- `view_patient`
- `admit_patient`
- `discharge_patient`
- `order_lab`
- `prescribe_med`
- `dispense_med`
- `perform_surgery`
- `view_audit_log`
- `submit_quality_report`

```python
from czoi import Application, Operation

emr = Application("EMR", zone=authority)
view_patient = emr.add_operation(Operation("view_patient"))
admit = emr.add_operation(Operation("admit_patient"))
discharge = emr.add_operation(Operation("discharge_patient"))
order_lab = emr.add_operation(Operation("order_lab"))
prescribe = emr.add_operation(Operation("prescribe_med"))
dispense = emr.add_operation(Operation("dispense_med"))
surgery = emr.add_operation(Operation("perform_surgery"))

audit = Application("Audit", zone=authority)
view_audit = audit.add_operation(Operation("view_audit_log"))

quality_app = Application("Quality", zone=authority)
submit_quality = quality_app.add_operation(Operation("submit_quality_report"))

for a in (emr, audit, quality_app):
    authority.add_application(a)
```

**Decision point: how granular?** Apply the Chapter 5 rules. If a security officer would want to distinguish them, split them.

#### Step 5: Permissions

Grant operations to roles based on job function:

```python
# Attending physicians
attending.grant(view_patient)
attending.grant(admit)
attending.grant(discharge)
attending.grant(order_lab)
attending.grant(prescribe)
attending.grant(surgery)

# Residents (subset, no surgery)
resident.grant(view_patient)
resident.grant(admit)
resident.grant(order_lab)
resident.grant(prescribe)

# Nurses
nurse.grant(view_patient)
nurse.grant(dispense)

# Pharmacists
pharmacist.grant(view_patient)
pharmacist.grant(dispense)

# Admins
admin.grant(view_patient)
admin.grant(admit)
admin.grant(discharge)

# Quality officers
quality.grant(view_audit)
quality.grant(submit_quality)

# Lab techs
lab_tech.grant(view_patient)
lab_tech.grant(order_lab)
```

**Decision point: cross-role patterns.** Nurse and Pharmacist both dispense. Resident and Attending both prescribe. Consider whether some permissions should live on a shared junior role.

#### Step 6: Constraints

Capture the hospital's policies:

```python
# Separation of duty: no one can both prescribe and dispense
builder.add_access_constraint("""
    signature {
        sort User;
        predicate prescribe(u: User);
        predicate dispense(u: User);
    }
    forall u: User . not (prescribe(u) and dispense(u))
""")

# Only attendings can perform surgery
builder.add_access_constraint("""
    signature {
        sort User;
        predicate canSurgery(u: User);
        predicate isAttending(u: User);
    }
    forall u: User . canSurgery(u) -> isAttending(u)
""")
```

Register the required predicates:

```python
builder.register_predicate(
    "prescribe",
    lambda u: any("AttendingPhysician" in r or "ResidentPhysician" in r
                  for r in u.roles),
)
builder.register_predicate(
    "dispense",
    lambda u: any("Nurse" in r or "Pharmacist" in r for r in u.roles),
)
```

**Decision point: which policies go where?** Broad policies at the authority level (all hospitals); narrow policies at individual hospitals.

#### Step 7: Adaptation points

Where will conditions change?

- **Surges** — a flu outbreak triples arrivals.
- **Staff shortages** — residents on strike.
- **Equipment failures** — a surgery suite goes offline.

For each, plan the adaptation:

```python
class SurgeDaemon(Daemon):
    """Detect surge onset and elevate SeniorNurse to prescribe."""
    ...
```

#### Step 8: Neural components

Which zones benefit from learning?

- **Emergency** — sepsis prediction, arrival forecasting.
- **ICU** — mortality prediction, ventilator allocation.
- **Surgery** — post-op complication prediction.
- **Radiology** — imaging analysis.

```python
# Emergency
sepsis_model = Predictor("sepsis", threshold=0.85)
sepsis_model.fit(...)
emerg_a.add_neural("sepsis", sepsis_model)

# ICU
mortality_model = Predictor("mortality", threshold=0.7)
mortality_model.fit(...)
icu_a.add_neural("mortality", mortality_model)
```

Each zone has its own models. No conflicts; no shared state.

#### Step 9: Daemons

What must be monitored?

- **Clinical safety** — sepsis alerts, medication interactions.
- **Compliance** — audit-log access, consent violations.
- **Operational** — ICU bed availability, OR scheduling.
- **Security** — access patterns, unusual activity.

```python
class ClinicalSafetyDaemon(Daemon):
    """Check every active patient every 30 minutes."""
    ...

class ComplianceDaemon(Daemon):
    """Monitor audit-log access and consent status."""
    ...

class CapacityDaemon(Daemon):
    """Track ICU and ED bed availability."""
    ...

class SecurityDaemon(Daemon):
    """Flag unusual access patterns."""
    ...
```

#### Step 10: Iterate

Show the design to a domain expert. The most common feedback:

- "We don't have a separate Pediatrics department" → merge zones.
- "That's not how our shifts work" → adjust role definitions.
- "We'd never allow that" → add a constraint.
- "We do adapt in practice, though" → add a daemon.

Iterate until the model matches the domain.

#### The design matrix

A useful output of the design process:

| Zone | Roles | Operations | Constraints | Daemons | Neural |
|---|---|---|---|---|---|
| Authority | All roles | All ops | Broad SoD | Compliance | — |
| CityHospitalA | Local roles | EMR ops | HIPAA | Clinical safety | — |
| Emergency | ED-specific | Emerg ops | — | Sepsis alerts | Sepsis predictor |
| ICU | ICU-specific | ICU ops | — | Mortality alerts | Mortality predictor |
| ... | ... | ... | ... | ... | ... |

#### Common design mistakes

**Mistake 1: too many zones.** If a zone has one user and one role, it's not a zone — it's a role attribute.

**Mistake 2: too few zones.** If your "Hospital" zone has 50 roles, split by department.

**Mistake 3: over-specific roles.** "EmergencyAttendingWeekendNight" — the role encodes too many attributes. Use a base role + attributes.

**Mistake 4: under-specific operations.** "manage_stuff" — what does this actually do? Break it up.

**Mistake 5: no constraints.** If your system has no constraints, you're not using CZOA's key feature.

**Mistake 6: ignoring adaptation.** Static permissions in a dynamic domain are a bug waiting to happen.

#### Exercises

1. **Design a bank.** Build a CZOI model for a regional bank with branches, roles, and constraints. Include at least 3 levels of hierarchy.

2. **Design a university.** Model registration, grade management, and FERPA compliance.

3. **Design a factory.** Model production lines, roles, and safety constraints.

4. **Justify choices.** For each zone you create, write one sentence explaining why it needs to be its own zone (vs. a role attribute or a sub-zone).

5. **Predict adaptation.** For each domain, list 3 events that would require adaptive access control.

#### Further reading

- The CZOA paper, §7 (Evaluation)
- The User Guide, §15 (Complete Worked Example)

---

### Chapter 13 — Testing and Verification

#### Learning objectives

- Write unit tests for CZOI systems.
- Verify permission decisions.
- Test constraint satisfaction.
- Test adaptive behaviour.

#### Why testing matters

CZOA systems have **formal guarantees** — but only if they're built right. Testing ensures your implementation actually delivers those guarantees.

#### Testing permission decisions

Every permission decision is a testable assertion:

```python
import pytest
from czoi import CZOABuilder, Application, Operation, Role, User, Decision


@pytest.fixture
def hospital():
    builder = CZOABuilder("Hospital")
    hospital = builder.add_zone("CityHospital", parent=builder.root)
    emergency = builder.add_zone("Emergency", parent=hospital, atomic=True)

    app = Application("EMR", zone=hospital)
    prescribe = app.add_operation(Operation("prescribe"))
    dispense = app.add_operation(Operation("dispense"))
    hospital.add_application(app)

    attending = Role("Attending", zone=hospital, base_permissions=[prescribe])
    nurse = Role("Nurse", zone=hospital, base_permissions=[dispense])
    hospital.add_role(attending)
    hospital.add_role(nurse)

    alice = User("alice", roles={"Attending"})
    bob = User("bob", roles={"Nurse"})
    for u in (alice, bob):
        for z in emergency.ancestry():
            z.add_user(u)

    return {
        "builder": builder,
        "hospital": hospital,
        "emergency": emergency,
        "prescribe": prescribe,
        "dispense": dispense,
        "alice": alice,
        "bob": bob,
    }


def test_attending_can_prescribe(hospital):
    result = hospital["builder"].permission_engine.decide(
        hospital["alice"], hospital["prescribe"], hospital["emergency"],
    )
    assert result is Decision.ALLOW


def test_nurse_cannot_prescribe(hospital):
    result = hospital["builder"].permission_engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    )
    assert result is Decision.DENY


def test_nurse_can_dispense(hospital):
    result = hospital["builder"].permission_engine.decide(
        hospital["bob"], hospital["dispense"], hospital["emergency"],
    )
    assert result is Decision.ALLOW
```

Notice:
- **A fixture builds the system once.**
- **Each test checks one decision.**
- **The three-valued decision is checked explicitly** — not just truthy/falsy.

#### Testing constraints

```python
def test_sod_constraint_blocks_both_roles(hospital):
    """A user with both Attending and Nurse roles should be denied
    prescribe because of the SoD constraint."""
    # Add the constraint
    hospital["builder"].add_access_constraint("""
        signature {
            sort User;
            predicate prescribe(u: User);
            predicate dispense(u: User);
        }
        forall u: User . not (prescribe(u) and dispense(u))
    """)

    # Register the predicates (needed for evaluation)
    hospital["builder"].register_predicate(
        "prescribe",
        lambda u: "Attending" in u.roles,
    )
    hospital["builder"].register_predicate(
        "dispense",
        lambda u: "Nurse" in u.roles,
    )

    # Bob now has both roles
    hospital["bob"].roles.add("Attending")

    # The engine should deny Bob's prescribe (constraint blocks it)
    result = hospital["builder"].permission_engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    )
    assert result is Decision.DENY
```

The assertion is specific: **the constraint is what causes the deny**, not just a missing role.

#### Testing seniority

```python
def test_seniority_inheritance(hospital):
    """A senior role inherits the permissions of a junior role."""
    # Make Attending senior to Nurse
    attending = hospital["hospital"].roles["Attending"]
    nurse = hospital["hospital"].roles["Nurse"]
    attending.add_junior(nurse)

    # Now Alice (Attending) should be able to dispense (Nurse's permission)
    result = hospital["builder"].permission_engine.decide(
        hospital["alice"], hospital["dispense"], hospital["emergency"],
    )
    assert result is Decision.ALLOW
```

#### Testing cache invalidation

```python
def test_cache_invalidation_on_grant(hospital):
    """Granting a permission should invalidate the engine cache."""
    engine = hospital["builder"].permission_engine

    # Bob is denied
    decision1 = engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    )
    assert decision1 is Decision.DENY

    # Grant Nurse the prescribe permission
    nurse = hospital["hospital"].roles["Nurse"]
    hospital["hospital"].grant(nurse, hospital["prescribe"])

    # Bob is now allowed
    decision2 = engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    )
    assert decision2 is Decision.ALLOW
```

This verifies that the cache is invalidated when it should be.

#### Testing daemons

```python
from czoi import Daemon, DaemonSignal


class TestDaemon(Daemon):
    def __init__(self, parent=None):
        super().__init__("TestDaemon", parent=parent, interval=1.0)
        self.calls = 0
        self.signals = []

    def monitor(self):
        self.calls += 1

    def on_signal(self, signal, payload, source=None):
        self.signals.append((signal, payload))


def test_daemon_ticks():
    daemon = TestDaemon()
    builder = CZOABuilder("Test")
    builder.add_daemon(daemon)

    for _ in range(3):
        builder.daemon_manager.tick()

    assert daemon.calls == 3


def test_signal_propagation():
    parent = TestDaemon()
    child = TestDaemon(parent=parent)

    child.emit_signal(DaemonSignal.STATE_WARNING, {"test": True})

    assert len(parent.signals) == 1
    assert parent.signals[0][0] is DaemonSignal.STATE_WARNING
```

#### Testing neural components

```python
import numpy as np
from czoi import Predictor, AnomalyDetector


def test_predictor_learns():
    # Linearly separable data
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    y = np.array([0.0, 0.0, 0.0, 1.0])   # AND gate

    model = Predictor("and_gate", threshold=0.5)
    model.fit(X, y, epochs=1000, lr=0.5)

    assert model.fires([1, 1])                # True AND True
    assert not model.fires([0, 1])            # False AND True
    assert not model.fires([0, 0])            # False AND False


def test_anomaly_detector_separates_classes():
    rng = np.random.default_rng(42)
    normal = rng.normal(0, 0.5, (200, 4))
    anomalies = rng.normal(5, 0.5, (20, 4))

    detector = AnomalyDetector("test", input_dim=4, latent_dim=2, seed=42)
    detector.fit(normal, epochs=200)

    # Normal samples should not be flagged
    normal_flags = [detector.is_anomalous(x) for x in normal[:50]]
    assert sum(normal_flags) < 10   # < 20% false positive rate

    # Anomalous samples should be flagged
    anomaly_flags = [detector.is_anomalous(x) for x in anomalies]
    assert sum(anomaly_flags) > 15   # > 75% detection rate
```

#### Testing adaptive behaviour

```python
def test_surge_grant_changes_decision(hospital):
    """A surge grant should change Nurse's decision."""
    engine = hospital["builder"].permission_engine
    nurse = hospital["hospital"].roles["Nurse"]

    # Normal: Nurse cannot prescribe
    assert engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    ) is Decision.DENY

    # Grant during surge
    hospital["hospital"].grant(nurse, hospital["prescribe"])

    # Now Nurse can prescribe
    assert engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    ) is Decision.ALLOW

    # Revoke
    hospital["hospital"].revoke(nurse, hospital["prescribe"])

    # Back to normal
    assert engine.decide(
        hospital["bob"], hospital["prescribe"], hospital["emergency"],
    ) is Decision.DENY
```

#### Property-based testing

For complex systems, use property-based testing (with `hypothesis`):

```python
from hypothesis import given, strategies as st

@given(
    user_roles=st.sets(st.sampled_from(["Attending", "Nurse", "Admin"])),
)
def test_any_role_set_is_consistent(user_roles):
    """For any combination of roles, the engine returns a valid decision."""
    builder = CZOABuilder("Test")
    zone = builder.add_zone("Zone", parent=builder.root, atomic=True)

    app = Application("App", zone=zone)
    op = app.add_operation(Operation("op"))
    zone.add_application(app)

    user = User("u", roles=user_roles)
    zone.add_user(user)

    decision = builder.permission_engine.decide(user, op, zone)
    assert decision in (Decision.ALLOW, Decision.DENY, Decision.INCONCLUSIVE)
```

This checks that no combination of roles produces an invalid decision.

#### Verification checklist

Before deploying a CZOI system, verify:

- [ ] Every role has been tested with a positive decision.
- [ ] Every role has been tested with a negative decision.
- [ ] Every constraint has a test that shows it blocks what it should.
- [ ] Every daemon has a test that shows it fires when it should.
- [ ] Adaptive behaviour has been tested on both the trigger and the reset.
- [ ] The audit trail captures every decision (when enabled).
- [ ] The cache is invalidated correctly on grants and revocations.

#### Exercises

1. **Write a test suite.** For the hospital example in Chapter 12, write tests covering all roles and operations.

2. **Test a constraint.** Write a test that proves a SoD constraint blocks a specific combination. Also write a test that shows it allows everything else.

3. **Test adaptation.** Write a test that shows a surge grant changes a decision, and that the revoke restores the original.

4. **Test daemons.** Write a test for the SurgeDaemon that verifies it emits `STATE_CRITICAL` when arrivals exceed the threshold.

5. **Property-based.** Use hypothesis to generate 100 random systems and verify that every decision is one of the three valid values.

#### Further reading

- The CZOI toolkit test suite (in the repository)
- The User Guide, §13 (Audit and Observability)

---

### Chapter 14 — Deployment Patterns

#### Learning objectives

- Choose a deployment architecture for CZOI.
- Integrate with existing systems.
- Handle persistence, scaling, and observability.
- Plan for updates and migrations.

#### The core question

**Where does the CZOI runtime live?**

Options:

1. **Embedded** — inside your application process.
2. **Sidecar** — a separate service alongside your app.
3. **Centralised** — one shared permission service.
4. **Hybrid** — per-zone runtimes coordinated globally.

Each has trade-offs.

#### Pattern 1: Embedded

The CZOI runtime is a Python library in your application:

```python
# myapp.py
from czoi import CZOABuilder

class MyApp:
    def __init__(self):
        self.builder = CZOABuilder("App")
        # ... set up zones, roles, ops ...
        self.engine = self.builder.permission_engine

    def handle_request(self, user_name, operation_name):
        user = self.builder.root.users[user_name]
        op = self.builder.root.operations[operation_name]
        decision = self.engine.decide(user, op, self.builder.root)
        if decision.name == "ALLOW":
            return do_the_thing()
        else:
            raise PermissionError(decision.name)
```

**Pros:**
- Simple. No network. Low latency.
- No deployment infrastructure needed.

**Cons:**
- Permission state must be consistent across all instances.
- No cross-instance cache sharing.
- Hard to change permissions without redeploying.

**Best for:** Small systems, prototypes, single-instance deployments.

#### Pattern 2: Sidecar

A local sidecar process handles permission decisions via a Unix socket or local HTTP:

```
[App] ──(local HTTP)──> [CZOA Sidecar] ──(reads state)──> [State Store]
```

The app queries the sidecar for every decision:

```python
import requests

def decide(user, operation, zone):
    resp = requests.post("http://localhost:8080/decide", json={
        "user": user, "operation": operation, "zone": zone,
    })
    return resp.json()["decision"]
```

**Pros:**
- Permission logic separate from application code.
- Can update the sidecar without redeploying the app.
- Low latency (localhost).

**Cons:**
- More infrastructure.
- Sidecar becomes a single point of failure per host.

**Best for:** Microservices, medium-scale systems.

#### Pattern 3: Centralised

One permission service for the whole organisation:

```
[App A] ──┐
[App B] ──┼──> [CZOA Permission Service] ──> [State Store]
[App C] ──┘
```

Each app queries the service:

```python
def decide(user, operation, zone):
    resp = requests.post("https://auth.example.com/decide", json={...})
    return resp.json()["decision"]
```

**Pros:**
- Single source of truth.
- Easy to update permissions globally.
- Centralised audit.

**Cons:**
- Network latency on every decision.
- Single point of failure (unless replicated).
- Cache consistency challenges.

**Best for:** Large organisations with many services.

#### Pattern 4: Hybrid (recommended)

The toolkit's design supports a hybrid model:

- **Global policy** — constraints, role definitions — lives in a shared service.
- **Local decision-making** — each service runs its own CZOI runtime.
- **Synchronisation** — the local runtimes pull policy updates periodically.

```
                     [Policy Service]
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    [App A]          [App B]          [App C]
    (local CZOI)     (local CZOI)     (local CZOI)
```

Each app has:

```python
class AppRuntime:
    def __init__(self):
        self.builder = CZOABuilder("App")
        self._load_policy()
        # Poll for updates every 60 seconds
        self._start_policy_poller()

    def _load_policy(self):
        policy = requests.get("https://policy.example.com/current").json()
        # Rebuild zones, roles, ops from policy
        ...

    def decide(self, user, operation, zone):
        return self.builder.permission_engine.decide(user, operation, zone)
```

**Pros:**
- Fast local decisions (no network per decision).
- Global policy updates propagate within seconds.
- Each app can be scaled independently.

**Cons:**
- More complex. Requires a policy distribution mechanism.
- Eventual consistency (a 60-second lag on updates).

**Best for:** Production-scale systems.

#### Persistence patterns

Regardless of deployment pattern, you need to persist:

1. **Zone configuration** — the tree, roles, operations.
2. **User assignments** — who has which role in which zone.
3. **Audit records** — every decision.
4. **Neural model state** — trained models.
5. **Adaptive state** — current surge/crash flags, elevated permissions.

#### Persistence: configuration

Zones, roles, and operations rarely change. Store them in:
- **YAML or JSON** — for git-tracked configuration.
- **A relational database** — for dynamic updates.
- **A CMS** — for admin-managed policy.

Example YAML:

```yaml
zones:
  - name: Hospital
    properties:
      capacity: 500
    children:
      - name: Emergency
        atomic: true
      - name: ICU
        atomic: true

roles:
  - name: AttendingPhysician
    zone: Hospital
    permissions: [prescribe, view_patient, admit]

operations:
  - qualified_name: EMR.prescribe
  - qualified_name: EMR.view_patient
```

Load it into a CZOI runtime:

```python
import yaml

def load_from_yaml(builder, path):
    config = yaml.safe_load(open(path))

    def build_zones(specs, parent):
        for spec in specs:
            zone = builder.add_zone(
                spec["name"], parent=parent, atomic=spec.get("atomic", False),
            )
            for k, v in spec.get("properties", {}).items():
                zone.properties.set(k, v)
            if "children" in spec:
                build_zones(spec["children"], parent=zone)

    build_zones(config["zones"], builder.root)
    # ... load roles and operations similarly ...
```

#### Persistence: user assignments

Users change often. Store them in a database:

```python
from django.db import models

class UserRoleAssignment(models.Model):
    user_name = models.CharField(max_length=100, db_index=True)
    zone_name = models.CharField(max_length=100)
    role_name = models.CharField(max_length=100)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user_name", "zone_name", "role_name"),)
```

On startup:

```python
def load_users(builder):
    assignments = UserRoleAssignment.objects.all()
    users = {}
    for a in assignments:
        if a.user_name not in users:
            users[a.user_name] = User(a.user_name, roles=set())
        users[a.user_name].roles.add(a.role_name)

    for user in users.values():
        for zone in builder.root.walk():
            if any(r in zone.roles for r in user.roles):
                # Register along the path
                for z in zone.ancestry():
                    if user.name not in z.users:
                        z.add_user(user)
```

#### Persistence: audit records

Audit records are write-heavy. Use:
- **Append-only databases** — Cassandra, Kafka, or a partitioned PostgreSQL table.
- **Time-series databases** — InfluxDB, TimescaleDB.
- **Cold storage** — S3, Glacier, for compliance retention.

```python
from czoi import PermissionEngine

# In the app
builder.permission_engine = PermissionEngine(audit_enabled=True)

# Background task flushes audit records to storage
async def flush_audit(builder, interval=5.0):
    import asyncio
    while True:
        await asyncio.sleep(interval)
        records = builder.permission_engine.audit[:]
        builder.permission_engine.audit.clear()
        for r in records:
            await kafka.produce("czoi-audit", value=r.as_dict())
```

#### Persistence: neural models

Neural models have versioned state:

```python
class ModelVersion(models.Model):
    zone = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=20)
    artifact_path = models.CharField(max_length=500)
    trained_at = models.DateTimeField()
    metrics = models.JSONField()
```

Loading:

```python
def load_model(zone, name):
    version = ModelVersion.objects.filter(
        zone=zone.name, name=name,
    ).order_by("-trained_at").first()
    if version is None:
        return None
    # Load the artifact (pickle, joblib, etc.)
    return load_artifact(version.artifact_path)
```

#### Scaling considerations

**Vertical scaling** — a single process handles more requests. Limited by CPU/memory. Works up to thousands of decisions/second.

**Horizontal scaling** — multiple processes each run their own CZOI runtime. Requires shared policy state. Works to millions of decisions/second.

For horizontal scaling, ensure:
- **Policy sync** — the config is identical across instances.
- **User sync** — user roles are consistent across instances.
- **Cache coherency** — either share a cache or accept eventual consistency.
- **Audit aggregation** — records from all instances flow to a central store.

#### Observability

**Metrics to track:**

```python
from prometheus_client import Counter, Histogram

decisions_total = Counter(
    "czoi_decisions_total",
    "Total CZOI decisions",
    ["decision", "zone"],
)
decision_latency = Histogram(
    "czoi_decision_latency_seconds",
    "Decision latency",
)

def decide(user, op, zone):
    with decision_latency.time():
        decision = engine.decide(user, op, zone)
    decisions_total.labels(decision=decision.name, zone=zone.name).inc()
    return decision
```

**Logging:**

```python
import structlog

log = structlog.get_logger()

def decide(user, op, zone):
    decision = engine.decide(user, op, zone)
    log.info(
        "decision",
        user=user.name, operation=op.qualified_name,
        zone=zone.name, decision=decision.name,
    )
    return decision
```

**Tracing:**

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def decide(user, op, zone):
    with tracer.start_as_current_span("czoi.decide") as span:
        span.set_attribute("user", user.name)
        span.set_attribute("operation", op.qualified_name)
        decision = engine.decide(user, op, zone)
        span.set_attribute("decision", decision.name)
        return decision
```

#### Updates and migrations

**Adding a new operation:**

```python
# Add the operation
new_op = app.add_operation(Operation("new_action"))

# Grant it to appropriate roles
for role in [admin, superadmin]:
    role.grant(new_op)

# In a real deployment:
# 1. Test in staging
# 2. Roll out the operation definition first
# 3. Then update roles
# 4. Then enable the code path that uses it
```

**Removing a role:**

```python
# 1. Migrate users to a replacement role
for user in zone.users.values():
    if "OldRole" in user.roles:
        user.roles.remove("OldRole")
        user.roles.add("NewRole")

# 2. Remove the role from the zone
del zone.roles["OldRole"]

# 3. Update constraints that reference it
# ...
```

**Changing a constraint:**

```python
# 1. Add the new constraint alongside the old
builder.add_access_constraint("new rule")

# 2. Test both
results = builder.constraint_manager.check_all()
assert all(results.values())

# 3. Remove the old constraint (requires restart or explicit removal)
# ...
```

Migrations are safe because CZOI is declarative. You describe the target state; the runtime enforces it.

#### Anti-patterns

**Anti-pattern 1: shared mutable state across instances.**

```python
# Bad
global_roles = {}   # shared across processes → chaos
```

Use a shared store (Redis, database) for cross-instance state.

**Anti-pattern 2: rebuilding the zone tree per request.**

```python
# Bad
def decide(user, op, zone_name):
    builder = CZOABuilder("Fresh")   # per request!
    ...
```

Build once, reuse.

**Anti-pattern 3: no cache invalidation strategy.**

If you cache decisions across instances, ensure invalidation propagates. Pub/sub or versioned keys.

**Anti-pattern 4: ignoring the audit trail.**

If you enable audit but never flush, memory grows unbounded. Stream to storage.

#### Exercises

1. **Embedded prototype.** Build a small Flask app that uses an embedded CZOI runtime for permissions.

2. **Persistence.** Design a database schema for storing zones, roles, and user assignments. Write the load function.

3. **Observability.** Add Prometheus metrics to a CZOI service. Track decisions by decision type and zone.

4. **Migration.** Take a system with 3 roles and add a new role. Migrate users, update constraints, and verify all decisions still work.

5. **Scaling plan.** Write a one-page document describing how you'd scale a CZOI system to 1M decisions per second.

#### Further reading

- The User Guide, §14 (Persistence and Web Frameworks)
- The CZOI toolkit's example integrations

---

## Part VI — Advanced Topics

### Chapter 15 — Cross-Zone Reasoning

#### Learning objectives

- Implement inter-zone role mappings (γ).
- Use embeddings for cross-zone role matching.
- Handle cross-zone operations.

#### The problem

Sometimes a user in one zone needs a permission defined in another. Examples:

- A senior engineer in the Backend team needs to deploy Frontend code during an on-call rotation.
- A hospital in one city needs to access a patient's records from another city's hospital.
- A developer needs to access a shared library managed by another team.

The paper models this with **γ (gamma) mappings**: inter-zone role relations.

#### Modelling γ as an explicit grant

The cleanest implementation:

```python
def add_gamma_mapping(
    child_zone,
    child_role,
    parent_zone,
    parent_role,
    weight=1.0,
):
    """Grant child_role the operations of parent_role."""
    parent_ops = sorted(parent_role.base_permissions,
                        key=lambda o: o.qualified_name)
    n_transfer = max(1, int(round(weight * len(parent_ops))))
    for op in parent_ops[:n_transfer]:
        child_role.grant(op)
    child_zone._invalidate_cache()
```

Usage:

```python
# In a company: Developer inherits Engineer's permissions during on-call
add_gamma_mapping(dev_zone, developer, corp_zone, engineer, weight=1.0)
```

Now the Developer role has all of Engineer's base permissions.

#### Weight semantics

The weight scales the transfer:

- **weight = 1.0**: all permissions transfer.
- **weight = 0.5**: half transfer (rounded up).
- **weight = 0.0**: none transfer.

At fractional weights, the transfer is deterministic — sorted by qualified name:

```python
parent_ops = sorted(parent_role.base_permissions, key=lambda o: o.qualified_name)
n_transfer = max(1, int(round(weight * len(parent_ops))))
for op in parent_ops[:n_transfer]:
    child_role.grant(op)
```

This means: with weight 0.5 and two parent permissions `[A, B]`, only `A` transfers (since `round(0.5 * 2) = 1`).

#### Removing γ

```python
def remove_gamma_mapping(child_zone, child_role, parent_role):
    """Revoke every operation the child role inherited via γ."""
    for op in parent_role.base_permissions:
        child_role.revoke(op)
    child_zone._invalidate_cache()
```

Every γ mapping should be reversible. This is essential for adaptation: cross-zone access granted during a crisis should be revoked when the crisis passes.

#### Cross-zone via embeddings

For systems with many zones and roles, embeddings can identify **which** γ mappings to add:

```python
def discover_gamma_mappings(zones, threshold=0.8):
    """Find semantically similar role pairs across zones."""
    candidates = []
    for source_zone in zones:
        for source_role in source_zone.roles.values():
            source_vec = emb.align_to_global(emb.embed_role(source_role))
            for target_zone in zones:
                if target_zone is source_zone:
                    continue
                for target_role in target_zone.roles.values():
                    target_vec = emb.align_to_global(emb.embed_role(target_role))
                    sim = emb.similarity(source_vec, target_vec)
                    if sim > threshold:
                        candidates.append(
                            (source_zone, source_role, target_zone, target_role, sim)
                        )
    return sorted(candidates, key=lambda x: -x[4])
```

The top candidates are your γ mapping suggestions. A human reviews them before they take effect.

#### Cross-zone operations

Sometimes an operation touches resources in two zones. Model it as an operation in one zone, and reference the other via a constraint or daemon:

```python
# The operation lives in Zone A
cross_op = app_a.add_operation(Operation("access_zone_b_data"))

# A constraint ensures the user has the right to touch Zone B
builder.add_access_constraint("""
    signature {
        sort User, Zone;
        predicate hasZoneBAccess(u: User);
        predicate accessingZoneB(u: User);
    }
    forall u: User . accessingZoneB(u) -> hasZoneBAccess(u)
""")

builder.register_predicate(
    "hasZoneBAccess",
    lambda u: any(
        "ZoneBAuditor" in role_name
        for zone in builder.root.walk()
        for role_name in u.roles
    ),
)

builder.register_predicate(
    "accessingZoneB",
    lambda u: u.attributes.get("_current_operation") == "access_zone_b_data",
)
```

This is verbose but explicit. It says: "when you perform this operation, you must have Zone B access."

#### Cross-zone daemons

Sometimes coordination happens via daemons:

```python
class CrossZoneCoordinator(Daemon):
    """Root daemon that coordinates across child zones."""

    def __init__(self, zones, parent=None):
        super().__init__("CrossZoneCoordinator", parent=parent, interval=5.0)
        self.zones = zones

    def monitor(self):
        # Example: if any zone reports a critical state, notify all
        criticals = [
            z for z in self.zones
            if z.properties.get("state") == "critical"
        ]
        if len(criticals) >= 2:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "cascading_failure",
                 "zones": [z.name for z in criticals]},
            )
```

#### A worked example: on-call rotation

A company rotates on-call duty across teams. During your rotation, you get elevated permissions across all services.

```python
from czoi import CZOABuilder, Application, Operation, Role, User, Daemon, DaemonSignal

builder = CZOABuilder("Company")
company = builder.root

# Services
backend = builder.add_zone("Backend", parent=company, atomic=True)
frontend = builder.add_zone("Frontend", parent=company, atomic=True)
database = builder.add_zone("Database", parent=company, atomic=True)

# Operations per service
backend_app = Application("Backend", zone=backend)
deploy_backend = backend_app.add_operation(Operation("deploy"))
backend.add_application(backend_app)

frontend_app = Application("Frontend", zone=frontend)
deploy_frontend = frontend_app.add_operation(Operation("deploy"))
frontend.add_application(frontend_app)

db_app = Application("Database", zone=database)
run_migration = db_app.add_operation(Operation("migrate"))
database.add_application(db_app)

# Roles
backend_dev = Role("BackendDev", zone=company, base_permissions=[deploy_backend])
frontend_dev = Role("FrontendDev", zone=company, base_permissions=[deploy_frontend])
dba = Role("DBA", zone=company, base_permissions=[run_migration])
on_call = Role("OnCall", zone=company, base_permissions=[])
company.add_role(backend_dev)
company.add_role(frontend_dev)
company.add_role(dba)
company.add_role(on_call)

# On-call engineer: cross-zone permissions via γ
add_gamma_mapping(company, on_call, company, backend_dev, weight=1.0)
add_gamma_mapping(company, on_call, company, frontend_dev, weight=1.0)
add_gamma_mapping(company, on_call, company, dba, weight=0.5)   # partial

# User on-call this week
alice = User("alice", roles={"OnCall"})
company.add_user(alice)

engine = builder.permission_engine
print(engine.decide(alice, deploy_backend, company).name)    # ALLOW
print(engine.decide(alice, deploy_frontend, company).name)   # ALLOW
print(engine.decide(alice, run_migration, company).name)     # ALLOW
```

Alice, who is only "OnCall," can deploy backend and frontend code and run migrations — because γ mappings have transferred those permissions to the OnCall role.

#### Anti-patterns

**Anti-pattern 1: γ without boundaries.**

```python
# Bad — grants everything, forever
add_gamma_mapping(dev, developer, corp, engineer, weight=1.0)
```

Always plan a revoke path.

**Anti-pattern 2: γ chains without termination.**

```python
# Bad — A inherits from B, B inherits from A
add_gamma_mapping(a_zone, a_role, b_zone, b_role)
add_gamma_mapping(b_zone, b_role, a_zone, a_role)
```

The permission sets grow unboundedly (well, until every operation is transferred). Avoid cycles.

**Anti-pattern 3: hidden γ.**

If a γ mapping isn't visible in the role's base_permissions, it's hard to audit. Always expose it via grants — don't hide it in a hook.

#### Exercises

1. **Basic γ.** Build a two-zone system where a user in Zone A inherits a permission from Zone B. Verify the decision.

2. **Weight test.** Try γ with weight 0.25, 0.5, 0.75, 1.0. Show how the transferred permissions change.

3. **Revoke.** After adding a γ mapping, call `remove_gamma_mapping`. Verify the permission is gone.

4. **Discovery.** Use embeddings to find likely γ pairs across 4 zones with 3 roles each. Sort by similarity score.

5. **On-call rotation.** Extend the on-call example with a daemon that grants `on_call` role to a user at the start of their week, and revokes it at the end.

#### Further reading

- The CZOA paper, §3, item 2 (γ mappings)
- The User Guide, §7 (Cross-zone permission traversal)

---

### Chapter 16 — Composition and Systems-of-Systems

#### Learning objectives

- Compose two CZOI systems into a larger system.
- Understand the categorical structure (products, coproducts).
- Reason about emergent behaviour.

#### The composition principle

CZOA is **compositional**: any two CZOI systems can be combined into a larger CZOI system. This is what makes it a **system-of-systems** architecture.

#### Composition operators

The paper defines several:

- **Product (×)**: parallel composition. Both subsystems exist, independently.
- **Coproduct (+)**: alternative composition. One or the other.
- **Exponential (→)**: morphism objects. One subsystem governs another.

For most practical purposes, you'll use **product** — combining two systems into a larger one.

#### Product via clone

The toolkit provides `CompositeZone.product_with`:

```python
from czoi import CZOABuilder

# Build two independent systems
builder_a = CZOABuilder("OrgA")
zone_a = builder_a.add_zone("TeamA", parent=builder_a.root, atomic=True)

builder_b = CZOABuilder("OrgB")
zone_b = builder_b.add_zone("TeamB", parent=builder_b.root, atomic=True)

# Compose: place both under a new parent
builder = CZOABuilder("Merged")
merged_a = builder.add_zone("OrgA_clone", parent=builder.root)
merged_b = builder.add_zone("OrgB_clone", parent=builder.root)
```

#### Deep composition via `clone`

`CompositeZone.clone()` does a structural deep-copy — new Role objects, new Operation references, but shared Operation *objects*:

```python
from czoi import CompositeZone, Role, Application, Operation

original = CompositeZone("Original")
app = Application("App", zone=original)
op = app.add_operation(Operation("do"))
original.add_application(app)

role = Role("Doer", zone=original, base_permissions=[op])
original.add_role(role)

# Clone
clone = original.clone(name="Clone")

print(clone.roles["Doer"] is role)                      # False — new Role
print(clone.roles["Doer"].base_permissions == {op})     # True — same Operations
print(clone.operations["App.do"] is op)                 # True — shared Operation
```

Why share operations but not roles? Because operations are **immutable** (their identity is their qualified name) while roles are **mutable** (they carry permissions). Cloning roles isolates mutations.

#### System-of-systems example

Consider three organisations merging:

```python
# Organisation A
builder_a = CZOABuilder("CorpA")
hr_a = builder_a.add_zone("HR", parent=builder_a.root, atomic=True)
hr_role_a = Role("HRManager", zone=hr_a, base_permissions=[])
hr_a.add_role(hr_role_a)

# Organisation B
builder_b = CZOABuilder("CorpB")
hr_b = builder_b.add_zone("HR", parent=builder_b.root, atomic=True)
hr_role_b = Role("HRManager", zone=hr_b, base_permissions=[])
hr_b.add_role(hr_role_b)

# Organisation C
builder_c = CZOABuilder("CorpC")
hr_c = builder_c.add_zone("HR", parent=builder_c.root, atomic=True)
hr_role_c = Role("HRManager", zone=hr_c, base_permissions=[])
hr_c.add_role(hr_role_c)

# Merge: place all three under a new holding company
holding = CZOABuilder("Holding")
holding_a = holding.add_zone("CorpA", parent=holding.root)
holding_b = holding.add_zone("CorpB", parent=holding.root)
holding_c = holding.add_zone("CorpC", parent=holding.root)

# Add the HR zones under each
for parent, hr in [(holding_a, hr_a), (holding_b, hr_b), (holding_c, hr_c)]:
    new_hr = parent.add_zone("HR", parent=parent, atomic=True)
    for role in hr.roles.values():
        new_role = Role(role.name, zone=new_hr,
                        base_permissions=list(role.base_permissions))
        new_hr.add_role(new_role)
```

Now the holding company has three subsidiaries, each with their own HR zone. Constraints at the holding level apply globally; constraints at each subsidiary apply locally.

#### Emergent properties

Composition can produce **emergent properties** — things that are true of the whole but not of any part.

Example: two zones each running at 40 % capacity might seem fine individually, but together they consume 80 % of shared resources — an emergent condition.

Model this with a **cross-zone daemon**:

```python
class ResourceCoordinator(Daemon):
    def __init__(self, zones, threshold=0.8, parent=None):
        super().__init__("ResourceCoordinator", parent=parent, interval=5.0)
        self.zones = zones
        self.threshold = threshold

    def monitor(self):
        total_util = sum(
            z.properties.get("utilisation", 0) for z in self.zones
        )
        if total_util > self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"total_utilisation": total_util,
                 "zones": [z.name for z in self.zones]},
            )
```

The coordinator watches the aggregate, not the parts.

#### Composition and constraints

When you compose, constraints are inherited downward:

```
Γ_composed ⊇ Γ_child1 ∪ Γ_child2
```

Each child inherits the parent's constraints. So a constraint on the holding company applies to all subsidiaries.

```python
holding.add_access_constraint("""
    signature { sort User; predicate executiveOverride(u: User); }
    forall u: User . executiveOverride(u) -> true
""")

# Now this applies to CorpA, CorpB, CorpC.
```

This is the key to governance: put broad policies high, specific policies low.

#### Composition and permissions

Permission decisions don't automatically cross subsystem boundaries. If CorpA's HR role needs to see CorpB's HR data, you need an explicit γ mapping (Chapter 15).

#### Composition and daemons

Daemons are hierarchical: a daemon in a child zone can signal to a daemon in the parent.

```python
# In each subsidiary
sub_daemon = SubsidiaryDaemon(parent=holding_daemon)
```

The holding-level daemon receives signals from all subsidiaries. This is the paper's §5.4 monitoring hierarchy.

#### The categorical view

For readers familiar with category theory, the paper's §4 shows that CZOI systems form a **Cartesian closed category**:

- **Objects**: CZOI systems.
- **Morphisms**: structure-preserving maps.
- **Products**: parallel composition.
- **Coproducts**: alternative composition.
- **Exponentials**: function spaces (subsystem → subsystem maps).

The practical implications:

1. **Products commute**: A × B ≅ B × A (order doesn't matter for parallel composition).
2. **Products are associative**: A × (B × C) ≅ (A × B) × C (bracketing doesn't matter).
3. **There's an identity**: the empty system (with no zones) acts as a unit for product.
4. **Functions compose**: if you have morphisms A → B and B → C, you get A → C.

These laws let you reason about compositions algebraically. You can prove properties of a large composed system from properties of its parts.

#### Anti-patterns

**Anti-pattern 1: shallow composition.**

```python
# Bad — just stacking zones without inheriting constraints
holding.add_zone("CorpA_clone")   # loses CorpA's constraints
```

Use `clone()` to preserve structure.

**Anti-pattern 2: ignoring boundaries.**

```python
# Bad — CorpA's user assumes access to CorpB
alice.roles.add("CorpB_HRAdmin")   # name doesn't exist in CorpB
```

Cross-boundary permissions need explicit γ mappings.

**Anti-pattern 3: no coordinating daemon.**

Composing without a top-level coordinator means emergent problems go unnoticed. Always have a root daemon.

#### Exercises

1. **Two-company merger.** Build two small CZOI systems, each with 2 zones and 2 roles. Merge them under a holding company. Verify that constraints from the holding apply to both.

2. **Clone and mutate.** Clone a composite zone, mutate the clone's roles, and verify the original is unchanged.

3. **Emergent condition.** Build 3 zones, each with a `utilisation` property. Write a daemon that alerts when the sum exceeds a threshold.

4. **Categorical laws.** Write tests that verify:
   - A × B ≅ B × A (same zone structure, same roles)
   - A × (B × C) ≅ (A × B) × C
   - Product with empty is identity

5. **Cross-subsidiary γ.** Add a γ mapping from CorpA's HR to CorpB's HR. Verify a CorpA user now has CorpB permissions during a specific condition.

#### Further reading

- The CZOA paper, §4 (Category-theoretic foundations)
- The User Guide, §5 (Building Zone Hierarchies)

---

### Chapter 17 — The Category-Theoretic View

#### Learning objectives

- Understand the categorical foundations of CZOA.
- Appreciate why the formalism is more than bookkeeping.
- See how the categorical view enables compositional reasoning.

#### Why category theory?

Category theory is the mathematics of structure. It abstracts away the *what* and focuses on the *how* — how things relate, how they compose, how they transform.

CZOA uses category theory to make precise claims like:

- "Any two CZOI systems can be composed."
- "Composition preserves constraints."
- "Permissions in a composed system are determined by the parts."

These aren't just slogans. They have formal proofs and algorithmic consequences.

#### The category CZOA_Rec

The category has:

- **Objects**: recursive CZOI systems `S = (Z, R, U, A, O, N, E, Γ, Φ, Δ)`.
- **Morphisms**: `f: S₁ → S₂` — families of structure-preserving maps:
  - `f_Z: Z₁ → Z₂` on zones.
  - `f_R: R₁ → R₂` on roles.
  - `f_U: U₁ → U₂` on users.
  - ... and so on, commuting with operations and preserving constraints.

A morphism is essentially a **homomorphism** — a mapping that preserves all the structure.

#### Cartesian closedness

A category is **Cartesian closed** if it has:

1. **Finite products** — parallel composition.
2. **Finite coproducts** — alternative composition.
3. **Exponentials** — function objects.

The paper (Theorem 4) proves CZOA_Rec has all three.

**Product**: `S₁ × S₂` is the parallel composition. Each subsystem retains its identity; the product is a system containing both.

**Coproduct**: `S₁ + S₂` is the alternative. You have one or the other.

**Exponential**: `S₂^S₁` is the space of morphisms from `S₁` to `S₂`. In practice, this is the space of policies that transform `S₁` into `S₂`.

#### Practical implications

**Implication 1: Composition is associative and commutative (for products).**

`S₁ × (S₂ × S₃)` is isomorphic to `(S₁ × S₂) × S₃`. So you can compose in any order.

**Implication 2: There's an identity system.**

The empty system (no zones, roles, users) acts as the unit. `S × ∅ ≅ S`.

**Implication 3: Morphisms compose.**

If you have `f: A → B` and `g: B → C`, you automatically get `g ∘ f: A → C`. Useful for chaining policy transformations.

**Implication 4: Products preserve constraints.**

If `S₁` satisfies `Γ₁` and `S₂` satisfies `Γ₂`, then `S₁ × S₂` satisfies `Γ₁ ∪ Γ₂` (with appropriate disambiguation of sorts and constants).

This means: **you can verify subsystems independently and compose the verifications.**

#### The functors

The paper defines three functors:

- **`F_tree`**: `CZOA_Rec → Tree` — extracts the zone tree.
- **`F_perm`**: `CZOA_Rec → Poset` — extracts the effective permission partial order.
- **`F_learn`**: `CZOA_Rec → Learn` — extracts the learning dynamics.

Functors preserve structure. So:

- If you transform a system (`f: S₁ → S₂`), the zone tree transforms accordingly (`F_tree(f): F_tree(S₁) → F_tree(S₂)`).
- The permission structure transforms correspondingly.
- The learning dynamics transform correspondingly.

This is Theorem 5 in the paper: **changes to a subsystem propagate consistently through the recursive hierarchy.**

#### The recursion as initial algebra

The recursive definition of zones:

```
Z_z = {z' : z' is a CZOI system}
```

Is an **initial algebra** for the hierarchical decomposition functor. In English: the recursive structure is the *canonical* way to represent hierarchical systems. There's no simpler representation.

This matters because it means:

- **No information loss** from the recursive representation.
- **Every hierarchy can be encoded** this way.
- **Composition is natural** — it's just the algebra's operation.

#### Putting it together

The categorical view gives you:

1. **A foundation for compositional reasoning.** You can prove things about systems by proving them about parts and invoking the composition theorems.

2. **A formal semantics for morphisms.** When you write "this system refines that one," you're describing a morphism. The categorical structure tells you when morphisms exist and how they compose.

3. **A language for policy transformations.** Migrations, upgrades, and merges are all morphisms. They have identities, inverses (when bijective), and composition.

4. **Compatibility with other mathematical frameworks.** Because CZOA_Rec is a well-behaved category, you can apply techniques from:
   - **Coalgebra** — for state machines and bisimulation.
   - **Enriched category theory** — for weighted or probabilistic versions.
   - **Higher category theory** — for systems of systems of systems.

#### Do I need to use category theory?

**No.** Most CZOI users won't invoke category theory in their daily work. But knowing the framework exists gives you confidence in:

- **Composition safety.** When you compose systems, you know constraints are preserved.
- **Refactoring correctness.** When you refactor, the categorical structure guarantees equivalence conditions.
- **Formal verification.** You can prove system properties using category-theoretic tools.

Think of it like SQL's relational algebra: you don't think about it when writing queries, but its existence is why your queries behave predictably.

#### A worked example: verification by composition

Suppose you have two subsystems `S₁` and `S₂`, and you want to prove that `S₁ × S₂` has no SoD violations.

**Traditional approach:** check every role combination in the composed system. With 10 roles each, that's 10,000 combinations. Expensive.

**Categorical approach:**

1. Prove `S₁` has no SoD violations.
2. Prove `S₂` has no SoD violations.
3. Prove the SoD constraint is preserved under product (which is a general theorem).
4. Conclude `S₁ × S₂` has no SoD violations.

Three local checks instead of 10,000 global ones. The categorical structure gives you the composition theorem for free.

#### Exercises

1. **Identify morphisms.** In the two-company merger example, what is the morphism from each subsidiary to the holding company?

2. **Prove associativity.** Show (by example) that `(A × B) × C` and `A × (B × C)` produce isomorphic zone trees.

3. **Constraint preservation.** Take a simple SoD constraint. Show that if `S₁` and `S₂` each satisfy it, then so does `S₁ × S₂`.

4. **F_tree functor.** Implement a function that extracts a nested dict representation of the zone tree. Show it commutes with composition.

5. **Refactor as morphism.** Take a system with roles `A` and `B`, and refactor to roles `A'` and `B'` where `A'` subsumes both. Write the morphism from the original to the refactored system.

#### Further reading

- The CZOA paper, §4 (Category-theoretic foundations)
- Fong & Spivak, *An Invitation to Applied Category Theory: Seven Sketches in Compositionality* (free online)

---

## Conclusion

You've reached the end of the CZOA tutorial. Let's take stock of what you've learned.

### The journey

You started with a problem: intelligent systems and enterprise systems have evolved separately, leaving a gap that costs real organisations real resources. You learned that CZOA closes that gap by showing they're the same kind of thing.

You built up the theory in layers:

1. **Zones** — recursive systems that mirror organisational structure.
2. **Roles, users, operations** — the identity and capability model.
3. **The permission calculus** — two-stage recursive decisions.
4. **Neural components** — learnable functions inside every zone.
5. **Embeddings** — semantic vectors for cross-zone reasoning.
6. **Adaptive access control** — dynamic permissions with safety guarantees.
7. **Constraints** — formal policy in UniLang.
8. **Daemons** — continuous monitoring and coordinated response.

Then you learned to apply it:

- **Designing for a domain** — a step-by-step process.
- **Testing** — how to verify CZOI systems.
- **Deployment** — four patterns from embedded to hybrid.
- **Cross-zone reasoning** — γ mappings and semantic matching.
- **Composition** — systems of systems and categorical laws.

### What you can do now

You can:

- Look at any organisation and design a CZOI model.
- Write formal constraints that capture policy.
- Build adaptive systems that respond to changing conditions.
- Compose subsystems into a system of systems.
- Verify your designs with tests and analysis.
- Deploy CZOI systems in production.

### What to explore next

Some directions not covered in this tutorial:

- **Federated CZOA** — coordinating CZOI systems across organisational boundaries.
- **Quantum CZOA** — the paper's speculative extension.
- **Automated zone discovery** — inferring zone trees from data.
- **Daemon synthesis** — generating daemons from UniLang policies.
- **Standardisation** — NIST, OASIS, and other standards efforts.

### A final thought

CZOA is more than a framework. It's a way of seeing. Once you start seeing organisations as recursive systems of intelligent zones, you can't unsee it. Every org chart looks different. Every permission check has a shape. Every constraint has a formal language.

The CZOI toolkit is your tool for turning that vision into working software. Use it well.

### Getting help

- **The User Guide** — reference details.
- **The repository** — source code and examples.
- **The paper** — formal foundations.
- **GitHub issues** — questions and bug reports.

### Contributing

If you build something interesting with CZOI — a new pattern, a new integration, a new domain — consider contributing it back. The toolkit grows with its users.

---

*End of tutorial. Thank you for reading.*

---

## Appendices

### Appendix A — Quick Reference

**Building**

```python
from czoi import (
    CZOABuilder, Application, Operation, Role, User,
    Daemon, DaemonSignal, Predictor, AnomalyDetector, RoleMiner,
    EmbeddingService, Decision, NeuralContribution,
)

builder = CZOABuilder("Name")
zone = builder.add_zone("ZoneName", parent=builder.root, atomic=False)
```

**Roles and operations**

```python
app = Application("App", zone=zone)
op = app.add_operation(Operation("do_thing"))
zone.add_application(app)

role = Role("Role", zone=zone, base_permissions=[op])
zone.add_role(role)
role.add_junior(junior_role)
```

**Users**

```python
user = User("user", roles={"Role"}, attributes={"key": "value"})
for z in zone.ancestry():
    z.add_user(user)
```

**Permissions**

```python
decision = builder.permission_engine.decide(user, op, zone)
# Decision.ALLOW / DENY / INCONCLUSIVE
```

**Constraints**

```python
builder.add_access_constraint("""... UniLang ...""")
builder.add_identity_constraint("""... UniLang ...""")
builder.add_trigger_constraint("""... UniLang ...""")
builder.add_goal_constraint("""... UniLang ...""")
```

**Daemons**

```python
class MyDaemon(Daemon):
    def monitor(self):
        self.emit_signal(DaemonSignal.STATE_WARNING, {"key": "value"})
    def on_signal(self, signal, payload, source=None):
        pass

builder.add_daemon(MyDaemon("Name"))
builder.daemon_manager.tick()    # sync
await builder.daemon_manager.run()    # async
```

**Neural**

```python
model = Predictor("name", threshold=0.5)
model.fit(X, y, epochs=500)
score = model.predict({"feature": 0.5})

detector = AnomalyDetector("name", input_dim=5, latent_dim=2)
detector.fit(X_normal)
flag = detector.is_anomalous(x)

zone.add_neural("name", model)
```

**Embeddings**

```python
emb = EmbeddingService(dimension=64)
v = emb.embed("text")
sim = emb.similarity(v1, v2)
emb.train_alignment(positives, negatives)
```

**Adaptation**

```python
zone.grant(role, op)     # invalidates cache
zone.revoke(role, op)    # invalidates cache

def hook(user, op, zone, base):
    return Decision.ALLOW if condition else base
builder.permission_engine.set_neural_contribution(NeuralContribution(hook))
```

### Appendix B — Glossary

- **AtomicZone** — a leaf zone with no children.
- **Application** — a structural module grouping operations.
- **CompositeZone** — a zone that may have children.
- **Containment principle** — `U_child ⊆ U_parent`.
- **Decision** — `ALLOW`, `DENY`, or `INCONCLUSIVE`.
- **Effective permissions** — the union of base and inherited permissions.
- **γ (gamma) mapping** — an inter-zone role permission transfer.
- **Neural component** — a learnable function inside a zone.
- **Operation** — an atomic permission target.
- **Role** — a job function within a zone.
- **Seniority** — the intra-zone role hierarchy.
- **UniLang** — the formal constraint language.
- **Zone** — a recursive CZOI subsystem.

### Appendix C — Further Resources

**Papers**

- Wang, H. (2025). Constrained Object Hierarchies as a Unified Theoretical Model for Intelligence and Intelligent Systems. *Computers*, 14(11), 478.
- Wang, H. (2026). A Formalized Zoned Role-Based Framework. *Computers*, 15(3), 1-26.
- Wang, H. (2026). Constrained Zoned-Object Architecture (CZOA). *Preprint*.
- Wang, H. (2026). UniLog: A Unified Logic Framework. *Preprint*.

**Code**

- [CZOI Toolkit](https://github.com/hongxueharriswang/czoi-toolkit)
- [UniLog Toolkit](https://github.com/hongxueharriswang/unilog-toolkit)

**Background**

- Beer, S. (1972). *Brain of the Firm*. Allen Lane. — The Viable System Model.
- Fong, B. & Spivak, D. (2019). *An Invitation to Applied Category Theory*. Cambridge.
- Hu et al. (2014). NIST Guide to Attribute-Based Access Control.

---

*End of tutorial.*