"""
opinion_dynamics.py — Agent-based opinion dynamics on a social network.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: Global → CommunityA / CommunityB.
  * Applications and atomic operations (express, influence, update, moderate).
  * Real CZOI permission calculus (Φ) on every interaction.
  * UniLog separation-of-duty: Influencer and Moderator are exclusive.
  * Hierarchical daemons (Δ): OpinionDaemon at root with PolarizationDaemon,
    EchoChamberDaemon, and ConsensusDaemon as children.
  * Neural assimilation predictor attached to the Global zone.
  * Weighted bounded-confidence opinion dynamics (Hegselmann-Krause style).
"""
from __future__ import annotations

import random

import numpy as np

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

random.seed(42)
np.random.seed(42)

# ---- World constants -------------------------------------------------
N_AGENTS = 100
N_INFLUENCERS = 10
N_MODERATORS = 2
N_NEIGHBORS = 5
ASSIMILATION_THRESHOLD = 0.2
POLARIZATION_LOW = 0.02
POLARIZATION_HIGH = 0.15
ECHO_CHAMBER_THRESHOLD = 0.15
CONSENSUS_FRACTION = 0.90


# =====================================================================
# 1. Build the social system
# =====================================================================
def build_system():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("OpinionDynamics")

    # ---- Zones -----------------------------------------------------
    global_zone = builder.add_zone("Global", parent=builder.root)
    comm_a = builder.add_zone("CommunityA", parent=global_zone, atomic=True)
    comm_b = builder.add_zone("CommunityB", parent=global_zone, atomic=True)

    # ---- Application and atomic operations -------------------------
    app = Application("OpinionApp", zone=global_zone)
    express = app.add_operation(Operation("express_opinion"))
    influence = app.add_operation(Operation("influence_neighbor"))
    update = app.add_operation(Operation("update_opinion"))
    moderate = app.add_operation(Operation("moderate_post"))
    global_zone.add_application(app)

    # ---- Roles and base permissions --------------------------------
    influencer = Role(
        "Influencer",
        zone=global_zone,
        base_permissions=[influence, express],
    )
    follower = Role(
        "Follower",
        zone=global_zone,
        base_permissions=[express, update],
    )
    moderator = Role(
        "Moderator",
        zone=global_zone,
        base_permissions=[express, moderate],
    )
    global_zone.add_role(influencer)
    global_zone.add_role(follower)
    global_zone.add_role(moderator)

    # ---- UniLog separation-of-duty: Influencer and Moderator -------
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant Influencer : Role;
            constant Moderator : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User .
            not (hasRole(u, Influencer) and hasRole(u, Moderator))
    """)

    ops = {
        "express": express,
        "influence": influence,
        "update": update,
        "moderate": moderate,
    }
    zones = {
        "global": global_zone,
        "CommunityA": comm_a,
        "CommunityB": comm_b,
    }
    return builder, zones, ops


# =====================================================================
# 2. Create agents, influencers, and moderators
# =====================================================================
def create_agents(builder, zones, n_agents, n_influencers, n_moderators):
    agents = []
    for i in range(n_agents):
        is_influencer = i < n_influencers
        role = "Influencer" if is_influencer else "Follower"
        weight = (
            random.uniform(0.1, 1.0) if is_influencer else 0.2
        )
        comm_name = random.choice(["CommunityA", "CommunityB"])

        u = User(
            f"agent_{i}",
            roles={role},
            attributes={
                "opinion": random.uniform(0.0, 1.0),
                "influence_weight": weight,
                "interactions": 0,
                "community": comm_name,
                "is_influencer": is_influencer,
            },
        )
        builder.root.add_user(u)
        zones["global"].add_user(u)
        zones[comm_name].add_user(u)
        agents.append(u)

    # ---- Random neighbor network: 5 neighbors per agent ------------
    for u in agents:
        others = [a for a in agents if a is not u]
        neighbors = random.sample(others, N_NEIGHBORS)
        u.attributes.set("neighbors", [n.name for n in neighbors])

    # ---- Moderators ------------------------------------------------
    moderators = []
    for i in range(n_moderators):
        m = User(
            f"moderator_{i}",
            roles={"Moderator"},
            attributes={"opinion": 0.5, "influence_weight": 0.2},
        )
        builder.root.add_user(m)
        zones["global"].add_user(m)
        moderators.append(m)

    return agents, moderators


# =====================================================================
# 3. Neural assimilation predictor
# =====================================================================
def build_assimilation_predictor() -> Predictor:
    """Predicts P(assimilation | |diff|, w_u, w_n).

    Ground truth in the synthetic data is "assimilate if |diff| < 0.2",
    with 5% label noise. After fitting, the model learns a soft
    decision boundary near the threshold.
    """
    rng = np.random.default_rng(42)
    n = 800
    diff = rng.uniform(0.0, 0.5, n)
    w_u = rng.uniform(0.1, 1.0, n)
    w_n = rng.uniform(0.1, 1.0, n)
    X = np.column_stack([diff, w_u, w_n])

    y = (diff < ASSIMILATION_THRESHOLD).astype(float)
    flip_mask = rng.random(n) < 0.05
    y[flip_mask] = 1.0 - y[flip_mask]

    predictor = Predictor("assimilation", threshold=0.5)
    predictor.fit(X, y, epochs=500, lr=0.5)
    return predictor


# =====================================================================
# 4. Daemons (Δ)
# =====================================================================
class PolarizationDaemon(Daemon):
    """Warns about consensus (too low variance) or polarisation (too high)."""

    def __init__(self, agents, low_thresh: float = POLARIZATION_LOW,
                 high_thresh: float = POLARIZATION_HIGH, parent=None):
        super().__init__("PolarizationDaemon", parent=parent, interval=1.0)
        self.agents = agents
        self.low_thresh = low_thresh
        self.high_thresh = high_thresh

    def monitor(self):
        opinions = [a.attributes.get("opinion", 0.5) for a in self.agents]
        var = float(np.var(opinions))
        if var < self.low_thresh:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"variance": round(var, 4), "status": "consensus"},
            )
        elif var > self.high_thresh:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"variance": round(var, 4), "status": "polarised"},
            )


class EchoChamberDaemon(Daemon):
    """Warns when cross-community interactions fall below threshold."""

    def __init__(self, sim, thresh: float = ECHO_CHAMBER_THRESHOLD,
                 parent=None):
        super().__init__("EchoChamberDaemon", parent=parent, interval=2.0)
        self.sim = sim
        self.thresh = thresh
        self._last_cross = 0
        self._last_within = 0

    def monitor(self):
        cross = self.sim.cross_community_interactions - self._last_cross
        within = self.sim.within_community_interactions - self._last_within
        self._last_cross = self.sim.cross_community_interactions
        self._last_within = self.sim.within_community_interactions
        total = cross + within
        if total > 5:
            ratio = cross / total
            if ratio < self.thresh:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"cross_ratio": round(ratio, 3),
                     "cross": cross, "within": within},
                )


class ConsensusDaemon(Daemon):
    """Signals STATE_CRITICAL when almost all opinions converge."""

    def __init__(self, agents, fraction: float = CONSENSUS_FRACTION,
                 parent=None):
        super().__init__("ConsensusDaemon", parent=parent, interval=5.0)
        self.agents = agents
        self.fraction = fraction

    def monitor(self):
        opinions = [a.attributes.get("opinion", 0.5) for a in self.agents]
        mean = float(np.mean(opinions))
        close = sum(1 for o in opinions if abs(o - mean) < 0.05)
        frac = close / len(opinions)
        if frac > self.fraction:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"consensus_fraction": round(frac, 3), "mean": round(mean, 3)},
            )


class OpinionDaemon(Daemon):
    """Root daemon aggregating all child signals."""

    def __init__(self, parent=None):
        super().__init__("OpinionDaemon", parent=parent, interval=2.0)
        self.warnings: list[tuple] = []
        self.criticals: list[tuple] = []

    def on_signal(self, signal, payload, source=None):
        src = source.name if source is not None else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))


# =====================================================================
# 5. Simulation
# =====================================================================
class OpinionSimulation:
    """Weighted bounded-confidence opinion dynamics.

    In every tick, one agent u interacts with a random neighbor v:
      1. Both must hold express_opinion — checked by the engine.
      2. The neural predictor scores P(assimilation | |diff|, w_u, w_n).
      3. If P ≥ 0.5, both adopt the weighted average of their opinions.
    """

    def __init__(
        self,
        builder,
        zones,
        ops,
        agents,
        moderators,
        predictor: Predictor,
    ):
        self.builder = builder
        self.zones = zones
        self.ops = ops
        self.agents = agents
        self.moderators = moderators
        self.predictor = predictor
        self._by_name = {a.name: a for a in agents}
        self.time = 0.0
        self.interactions = 0
        self.cross_community_interactions = 0
        self.within_community_interactions = 0
        self.denied_interactions = 0
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        global_zone = self.zones["global"]

        # ---- Pick u and a random neighbor v -------------------------
        u = random.choice(self.agents)
        neighbor_names = u.attributes.get("neighbors", [])
        if not neighbor_names:
            return
        v = self._by_name.get(random.choice(neighbor_names))
        if v is None or v is u:
            return

        # ---- Permission checks (real CZOA Φ) ------------------------
        express = self.ops["express"]
        if engine.decide(u, express, global_zone) is not Decision.ALLOW:
            self.denied_interactions += 1
            return
        if engine.decide(v, express, global_zone) is not Decision.ALLOW:
            self.denied_interactions += 1
            return

        # ---- Neural assimilation prediction -------------------------
        op_u = u.attributes.get("opinion", 0.5)
        op_v = v.attributes.get("opinion", 0.5)
        diff = abs(op_u - op_v)
        w_u = u.attributes.get("influence_weight", 0.2)
        w_v = v.attributes.get("influence_weight", 0.2)

        prob = self.predictor.predict({
            "diff": diff, "w_u": w_u, "w_v": w_v,
        })
        if prob < 0.5:
            return

        # ---- Assimilate: weighted average ---------------------------
        new_opinion = (w_u * op_u + w_v * op_v) / (w_u + w_v)
        u.attributes.set("opinion", new_opinion)
        v.attributes.set("opinion", new_opinion)
        u.attributes.set("interactions",
                         u.attributes.get("interactions", 0) + 1)
        v.attributes.set("interactions",
                         v.attributes.get("interactions", 0) + 1)

        # ---- Track cross/within-community interactions --------------
        if u.attributes.get("community") == v.attributes.get("community"):
            self.within_community_interactions += 1
        else:
            self.cross_community_interactions += 1
        self.interactions += 1

        self._log("assimilate", u.name, v.name, round(new_opinion, 3))

    # -----------------------------------------------------------------
    def _log(self, event: str, *args) -> None:
        self.logs.append((round(self.time, 2), event) + args)


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_system()
    agents, moderators = create_agents(
        builder, zones, N_AGENTS, N_INFLUENCERS, N_MODERATORS,
    )

    # ---- Neural component attached to the Global zone ---------------
    predictor = build_assimilation_predictor()
    zones["global"].add_neural("assimilation", predictor)

    # ---- Sanity check on the predictor ------------------------------
    close_p = predictor.predict({"diff": 0.05, "w_u": 0.5, "w_v": 0.5})
    far_p = predictor.predict({"diff": 0.45, "w_u": 0.5, "w_v": 0.5})
    print(f"P(assimilate) | diff=0.05 : {close_p:.3f}")
    print(f"P(assimilate) | diff=0.45 : {far_p:.3f}")
    print()

    # ---- Simulation object (needed by the EchoChamberDaemon) --------
    sim = OpinionSimulation(
        builder, zones, ops, agents, moderators, predictor,
    )

    # ---- Daemon hierarchy -------------------------------------------
    root = OpinionDaemon()
    polarization = PolarizationDaemon(agents, parent=root)
    echo = EchoChamberDaemon(sim, parent=root)
    consensus = ConsensusDaemon(agents, parent=root)
    builder.add_daemon(root)
    builder.add_daemon(polarization)
    builder.add_daemon(echo)
    builder.add_daemon(consensus)

    # ---- Sanity check: real CZOI permission decisions ---------------
    global_zone = zones["global"]
    engine = builder.permission_engine
    inf = agents[0]
    fol = agents[50]
    mod = moderators[0]
    print("Permission sanity check (paper §3, item 9):")
    print("  agent_0    (Influencer) express   :",
          engine.decide(inf, ops["express"], global_zone).name)
    print("  agent_0    (Influencer) influence :",
          engine.decide(inf, ops["influence"], global_zone).name)
    print("  agent_50   (Follower)   express   :",
          engine.decide(fol, ops["express"], global_zone).name)
    print("  agent_50   (Follower)   influence :",
          engine.decide(fol, ops["influence"], global_zone).name)
    print("  moderator_0 (Moderator) moderate  :",
          engine.decide(mod, ops["moderate"], global_zone).name)
    print()

    # ---- Simulate 500 interactions ---------------------------------
    for step in range(500):
        sim.step(dt=1.0)
        if step % 25 == 0:
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    opinions = [a.attributes.get("opinion", 0.5) for a in agents]
    influencers_ops = [
        a.attributes.get("opinion", 0.5)
        for a in agents if a.attributes.get("is_influencer")
    ]
    followers_ops = [
        a.attributes.get("opinion", 0.5)
        for a in agents if not a.attributes.get("is_influencer")
    ]

    print(f"Final opinions  — mean: {np.mean(opinions):.3f}, "
          f"std: {np.std(opinions):.3f}")
    print(f"Influencers     — mean: {np.mean(influencers_ops):.3f}")
    print(f"Followers       — mean: {np.mean(followers_ops):.3f}")
    print(f"Total interactions: {sim.interactions}")
    print(f"  cross-community : {sim.cross_community_interactions}")
    print(f"  within-community: {sim.within_community_interactions}")
    print(f"  denied by engine: {sim.denied_interactions}")
    print(f"Warnings        : {len(root.warnings)}")
    print(f"Criticals       : {len(root.criticals)}")

    if root.warnings:
        print("\nFirst 3 warnings:")
        for src, payload in root.warnings[:3]:
            print(f"  from {src}: {payload}")

    if root.criticals:
        print("\nFirst 3 criticals:")
        for src, payload in root.criticals[:3]:
            print(f"  from {src}: {payload}")

    print(f"\nPermission engine stats: {engine.stats()}")


if __name__ == "__main__":
    main()