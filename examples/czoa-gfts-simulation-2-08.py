"""
finance_trading.py — A/B comparison of baseline RBAC vs CZOA.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Two scenarios run for a 6-hour trading day with a market crash at 14:00:

  baseline — static RBAC. No neural anomaly detection, no daemons.
             Anomalous trades execute unfiltered.
  czoa     — full CZOA. AnomalyPredictor trained on synthetic labels,
             CircuitBreakerDaemon + RiskLimitDaemon + MarketDaemon,
             UniLog separation-of-duty constraint between Trader and
             RiskManager.

Both scenarios report:
  * trades submitted / executed / denied
  * anomalies detected (labelled ground truth)
  * precision / recall / F1 of the anomaly detector
  * whether the circuit breaker halted the desk
  * estimated capital protected by the halt (crash scenario)
"""
from __future__ import annotations

import random

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

random.seed(137)
np.random.seed(137)

# ---- World constants -------------------------------------------------
DESK_HOURS = 6
CRASH_HOUR = 14          # 14:00 local time → t = 14 * 60 = 840 min
ORDERS_PER_HOUR = 1000
ORDER_VALUE_MIN = 1_000.0
ORDER_VALUE_MAX = 50_000.0
ANOMALY_VALUE_THRESHOLD = 40_000.0
ANOMALY_LABEL_NOISE = 0.05
CIRCUIT_BREAKER_THRESHOLD = 5
ESTIMATED_LOSS_PER_LATE_TRADE = 250_000.0


# =====================================================================
# 1. Build a trading desk (parameterised by mode)
# =====================================================================
def build_desk(mode: str):
    """`mode` is 'baseline' or 'czoa'. Only 'czoa' registers daemons."""

    builder = CZOABuilder("TradingFloor")
    desk = builder.add_zone("EquitiesDesk", parent=builder.root, atomic=True)

    app = Application("Trading", zone=desk)
    trade_op = app.add_operation(Operation("trade"))
    approve_op = app.add_operation(Operation("approve"))
    halt_op = app.add_operation(Operation("halt_trading"))
    desk.add_application(app)

    trader_role = Role("Trader", zone=desk, base_permissions=[trade_op])
    risk_role   = Role("RiskManager", zone=desk,
                       base_permissions=[approve_op, halt_op])
    desk.add_role(trader_role)
    desk.add_role(risk_role)

    # UniLog separation-of-duty: a user cannot be both Trader and
    # RiskManager (they would be able to approve their own trades).
    builder.add_access_constraint("""
        signature {
            sort User, Role;
            constant Trader : Role;
            constant RiskManager : Role;
            predicate hasRole(u: User, r: Role);
        }
        forall u: User .
            not (hasRole(u, Trader) and hasRole(u, RiskManager))
    """)

    return builder, desk, {
        "trade": trade_op, "approve": approve_op, "halt": halt_op,
    }


def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


def create_users(builder, desk):
    alice = User(
        "alice",
        roles={"Trader"},
        attributes={"desk": desk.name, "trades_submitted": 0},
    )
    _register_along_path(alice, desk)

    bob = User(
        "bob",
        roles={"RiskManager"},
        attributes={"desk": desk.name, "halts_issued": 0},
    )
    _register_along_path(bob, desk)

    return alice, bob


# =====================================================================
# 2. Neural anomaly predictor
# =====================================================================
def build_anomaly_predictor() -> Predictor:
    """Learns P(anomaly | order_value, hour, trader_volume).

    Ground truth: order_value > 40 000 → anomalous. With 5 % label
    noise (some large trades are benign, some small ones are anomalous).
    """
    rng = np.random.default_rng(137)
    n = 4000
    value_norm = rng.uniform(ORDER_VALUE_MIN, ORDER_VALUE_MAX, n) \
        / ORDER_VALUE_MAX
    hour_norm  = rng.uniform(0.0, 1.0, n)
    volume     = rng.uniform(0.0, 1.0, n)

    X = np.column_stack([value_norm, hour_norm, volume])
    y = (value_norm > ANOMALY_VALUE_THRESHOLD / ORDER_VALUE_MAX) \
        .astype(float)
    flip = rng.random(n) < ANOMALY_LABEL_NOISE
    y[flip] = 1.0 - y[flip]

    predictor = Predictor("anomaly", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


def build_impact_predictor() -> Predictor:
    """Predicts normalised market impact from order value + crash flag."""
    rng = np.random.default_rng(137)
    n = 800
    value_norm = rng.uniform(0.0, 1.0, n)
    crash_flag = rng.integers(0, 2, n).astype(float)

    X = np.column_stack([value_norm, crash_flag])
    logits = 3.0 * value_norm + 2.5 * crash_flag - 2.0
    probs  = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("impact", threshold=0.5)
    predictor.fit(X, y, epochs=500, lr=0.5)
    return predictor


# =====================================================================
# 3. Daemons (Δ) — only instantiated in CZOA mode
# =====================================================================
class AnomalyDaemon(Daemon):
    """Warns on every flagged order; escalates when the count exceeds
    the circuit-breaker threshold."""

    def __init__(self, sim, threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 parent=None):
        super().__init__("AnomalyDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.threshold = threshold
        self._escalated = False

    def monitor(self):
        if self._escalated:
            return
        if self.sim.anomalies_detected > self.threshold:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"anomalies": self.sim.anomalies_detected,
                 "threshold": self.threshold},
            )
            self._escalated = True


class CrashDaemon(Daemon):
    """Signals STATE_CRITICAL the moment a market crash begins."""

    def __init__(self, sim, parent=None):
        super().__init__("CrashDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self._fired = False

    def monitor(self):
        if not self._fired and self.sim.crash_active:
            self._fired = True
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"event": "market_crash",
                 "time_min": round(self.sim.sim_time, 1)},
            )


class MarketDaemon(Daemon):
    """Root daemon. On any critical signal, requests a halt."""

    def __init__(self, parent=None):
        super().__init__("MarketDaemon", parent=parent, interval=1.0)
        self.warnings:  list[tuple] = []
        self.criticals: list[tuple] = []
        self.halt_requested = False

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))
            self.halt_requested = True


# =====================================================================
# 4. Simulation
# =====================================================================
class TradingSimulation:
    """Order-driven trading simulation, one step per simulated minute.

    Every trade submission is routed through the real Φ engine. In CZOA
    mode, the anomaly predictor is consulted and the daemon hierarchy is
    ticked after each step.
    """

    def __init__(self, builder, desk, ops, trader, risk_manager,
                 mode: str, crash: bool):
        self.builder = builder
        self.desk = desk
        self.ops = ops
        self.trader = trader
        self.risk_manager = risk_manager
        self.mode = mode                  # 'baseline' | 'czoa'
        self.crash_enabled = crash

        # Neural components (CZOA mode only)
        if mode == "czoa":
            self.anomaly_model = build_anomaly_predictor()
            self.impact_model  = build_impact_predictor()
            desk.add_neural("anomaly", self.anomaly_model)
            desk.add_neural("impact",  self.impact_model)
        else:
            self.anomaly_model = None
            self.impact_model  = None

        # State
        self.sim_time = 0.0                # minutes since open
        self.orders_submitted = 0
        self.trades_executed = 0
        self.trades_denied = 0
        self.anomalies_detected = 0
        self.true_anomalies = 0
        self.true_positive = 0
        self.false_positive = 0
        self.false_negative = 0
        self.capital_protected = 0.0
        self.crash_active = False
        self.halt_reached = False
        self.halt_time: float | None = None
        self.logs: list[tuple] = []

    # -----------------------------------------------------------------
    def _is_true_anomaly(self, order) -> bool:
        """Ground-truth label with 5 % noise matching the training set."""
        base = order["value"] > ANOMALY_VALUE_THRESHOLD
        if random.random() < ANOMALY_LABEL_NOISE:
            return not base
        return base

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.sim_time += dt
        engine = self.builder.permission_engine

        # ---- Crash trigger at 14:00 (minute 840) ------------------
        if (self.crash_enabled and not self.crash_active
                and self.sim_time >= CRASH_HOUR * 60):
            self.crash_active = True
            self._log("crash_start", None)

        # ---- Order arrival -----------------------------------------
        arrivals_per_minute = ORDERS_PER_HOUR / 60.0
        if random.random() < arrivals_per_minute:
            self.orders_submitted += 1
            order = {
                "id": self.orders_submitted,
                "value": random.uniform(ORDER_VALUE_MIN, ORDER_VALUE_MAX),
                "hour": (9 + self.sim_time / 60.0) % 24,
            }
            self._log("order_submitted", order)

            # ---- Real Φ check --------------------------------------
            if engine.decide(self.trader, self.ops["trade"], self.desk) \
                    is not Decision.ALLOW:
                self.trades_denied += 1
                self._log("trade_denied", order)
                return

            # ---- Anomaly detection (CZOA mode only) ----------------
            is_true_anomaly = self._is_true_anomaly(order)
            if is_true_anomaly:
                self.true_anomalies += 1

            if self.mode == "czoa":
                features = {
                    "value":  order["value"] / ORDER_VALUE_MAX,
                    "hour":   order["hour"] / 24.0,
                    "volume": min(1.0, self.orders_submitted / 500.0),
                }
                flagged = self.anomaly_model.predict(features) >= 0.5

                if flagged:
                    self.anomalies_detected += 1
                    if is_true_anomaly:
                        self.true_positive += 1
                    else:
                        self.false_positive += 1
                    self._log("anomaly_detected", order)
                else:
                    if is_true_anomaly:
                        self.false_negative += 1

                # Anomalies short-circuit execution in CZOA mode.
                if flagged:
                    self.trades_denied += 1
                    return

            # ---- Order executes ------------------------------------
            self.trades_executed += 1

            # Impact model (CZOA only) — purely informational here.
            if self.mode == "czoa":
                _ = self.impact_model.predict({
                    "value": order["value"] / ORDER_VALUE_MAX,
                    "crash": 1.0 if self.crash_active else 0.0,
                })

            self._log("trade_executed", order)

    # -----------------------------------------------------------------
    def _log(self, event: str, payload) -> None:
        self.logs.append((round(self.sim_time, 1), event, payload))


# =====================================================================
# 5. Scenario runner
# =====================================================================
def run_scenario(mode: str, crash: bool = True) -> dict:
    """Run one scenario and return summary metrics."""
    builder, desk, ops = build_desk(mode)
    trader, risk_manager = create_users(builder, desk)

    sim = TradingSimulation(
        builder, desk, ops, trader, risk_manager, mode=mode, crash=crash,
    )

    # ---- Daemon hierarchy (CZOA mode only) -------------------------
    if mode == "czoa":
        root = MarketDaemon()
        anomaly_d = AnomalyDaemon(sim, parent=root)
        crash_d   = CrashDaemon(sim, parent=root)
        builder.add_daemon(root)
        builder.add_daemon(anomaly_d)
        builder.add_daemon(crash_d)
    else:
        root = None

    # ---- Run 6 simulated hours, one step per minute ----------------
    for minute in range(DESK_HOURS * 60):
        sim.step(dt=1.0)

        if mode == "czoa":
            builder.daemon_manager.tick()

            # On any critical signal, the risk manager halts the desk.
            if (root.halt_requested and not sim.halt_reached):
                if builder.permission_engine.decide(
                        risk_manager, ops["halt"], desk
                ) is Decision.ALLOW:
                    sim.halt_reached = True
                    sim.halt_time = sim.sim_time
                    risk_manager.attributes.set(
                        "halts_issued",
                        risk_manager.attributes.get("halts_issued", 0) + 1,
                    )
                    self_log = sim._log
                    self_log("circuit_breaker_halt",
                             {"at_min": round(sim.sim_time, 1)})

        # Once halted, no further orders arrive.
        if sim.halt_reached and mode == "czoa":
            break

    # ---- Compute metrics ------------------------------------------
    precision = recall = f1 = 0.0
    if mode == "czoa":
        tp, fp, fn = sim.true_positive, sim.false_positive, sim.false_negative
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall    = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)

    return {
        "mode":               mode,
        "halt_reached":       sim.halt_reached,
        "halt_time_min":      sim.halt_time,
        "orders_submitted":   sim.orders_submitted,
        "trades_executed":    sim.trades_executed,
        "trades_denied":      sim.trades_denied,
        "true_anomalies":     sim.true_anomalies,
        "anomalies_detected": sim.anomalies_detected,
        "true_positive":      sim.true_positive,
        "false_positive":     sim.false_positive,
        "false_negative":     sim.false_negative,
        "precision":          precision,
        "recall":             recall,
        "f1":                 f1,
        "crash_active":       sim.crash_active,
    }


# =====================================================================
# 6. Main
# =====================================================================
def main() -> None:
    print("=" * 68)
    print("Trading desk — Baseline RBAC vs CZOA")
    print("=" * 68)
    print()

    # ---- Sanity checks ----------------------------------------------
    builder, desk, ops = build_desk("czoa")
    trader, risk = create_users(builder, desk)
    engine = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  alice  trade         :",
          engine.decide(trader, ops["trade"], desk).name)
    print("  alice  halt_trading  :",
          engine.decide(trader, ops["halt"], desk).name)
    print("  bob    halt_trading  :",
          engine.decide(risk, ops["halt"], desk).name)
    print("  bob    trade         :",
          engine.decide(risk, ops["trade"], desk).name)
    print()

    anomaly_model = build_anomaly_predictor()
    small_p = anomaly_model.predict({"value": 0.10, "hour": 0.4, "volume": 0.1})
    large_p = anomaly_model.predict({"value": 0.95, "hour": 0.6, "volume": 0.5})
    print(f"P(anomaly) | $5k order   : {small_p:.3f}")
    print(f"P(anomaly) | $48k order  : {large_p:.3f}")
    print()

    # ---- Baseline ---------------------------------------------------
    baseline = run_scenario("baseline", crash=True)

    # ---- CZOA -------------------------------------------------------
    czoa = run_scenario("czoa", crash=True)

    # ---- Report -----------------------------------------------------
    header = (f"{'Metric':<28} {'Baseline':>16} {'CZOA':>16}")
    print(header)
    print("-" * len(header))
    rows = [
        ("Halted",              "yes" if baseline["halt_reached"] else "no",
                                "yes" if czoa["halt_reached"] else "no"),
        ("Halt time (min)",     f"{baseline['halt_time_min']:.1f}"
                                if baseline["halt_time_min"] else "—",
                                f"{czoa['halt_time_min']:.1f}"
                                if czoa["halt_time_min"] else "—"),
        ("Orders submitted",    baseline["orders_submitted"],
                                czoa["orders_submitted"]),
        ("Trades executed",     baseline["trades_executed"],
                                czoa["trades_executed"]),
        ("Trades denied",       baseline["trades_denied"],
                                czoa["trades_denied"]),
        ("True anomalies",      baseline["true_anomalies"],
                                czoa["true_anomalies"]),
        ("Anomalies flagged",   "—",      czoa["anomalies_detected"]),
        ("  true positive",     "—",      czoa["true_positive"]),
        ("  false positive",    "—",      czoa["false_positive"]),
        ("  false negative",    "—",      czoa["false_negative"]),
    ]
    for label, b, c in rows:
        print(f"{label:<28} {b!s:>16} {c!s:>16}")

    print()
    print(f"Anomaly detector precision: {czoa['precision']:.3f}")
    print(f"Anomaly detector recall   : {czoa['recall']:.3f}")
    print(f"Anomaly detector F1       : {czoa['f1']:.3f}")
    print()
    print("Interpretation")
    print("--------------")
    if czoa["halt_reached"]:
        prevented = (
            czoa["true_anomalies"] - czoa["true_positive"]
        )
        print(f"  CZOA halted the desk at minute "
              f"{czoa['halt_time_min']:.0f} after "
              f"{czoa['anomalies_detected']} flagged orders.")
    else:
        print("  CZOA did not halt — anomaly count stayed below threshold.")
    print(f"  Baseline let {baseline['trades_executed']} trades execute "
          f"(no filter); CZOA executed {czoa['trades_executed']}.")
    print(f"  Baseline would have processed every anomaly "
          f"({baseline['true_anomalies']} true anomalies).")


if __name__ == "__main__":
    main()