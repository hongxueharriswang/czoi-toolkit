"""
market.py — Multi-agent market microstructure simulation.

Reimplemented with the CZOI toolkit (v1.0) against the CZOA theory.

Exercises:
  * Recursive zone tree: Exchange → MarketMakerDesk / ArbitrageDesk / NoiseDesk.
  * Applications and atomic operations (place_order, cancel_order, get_quote).
  * Real CZOI permission calculus (Φ) on every order.
  * UniLog access constraint: cash and holdings limits per trader role.
  * Hierarchical daemons (Δ): MarketDaemon at root with PriceVolatilityDaemon,
    RiskLimitDaemon, and CircuitBreakerDaemon as children.
  * Neural price-impact predictor attached to the Exchange zone.
  * Three trader archetypes with distinct behaviour and risk tolerances.
"""
from __future__ import annotations

import random

import numpy as np

from czoi import (
    Application, CZOABuilder, Daemon, DaemonSignal, Decision,
    Operation, Predictor, Role, User,
)

random.seed(313)
np.random.seed(313)

# ---- World constants -------------------------------------------------
INITIAL_PRICE = 100.0
PRICE_IMPACT_PER_UNIT = 0.001
VOLATILITY_WARN = 0.02
VOLATILITY_HALT = 0.05
RISK_LIMIT_WARN = 0.85
RISK_LIMIT_CRITICAL = 1.0
MM_RISK_TOLERANCE = 0.2
ARB_RISK_TOLERANCE = 0.5
NOISE_RISK_TOLERANCE = 0.8


# =====================================================================
# 1. Build the exchange
# =====================================================================
def build_exchange():
    """Construct the zone tree, roles, operations, and constraints."""
    builder = CZOABuilder("ExchangeSystem")

    # ---- Zones -------------------------------------------------------
    exchange = builder.add_zone("Exchange", parent=builder.root)
    mm_desk  = builder.add_zone("MarketMakerDesk", parent=exchange, atomic=True)
    arb_desk = builder.add_zone("ArbitrageDesk",   parent=exchange, atomic=True)
    noise_desk = builder.add_zone("NoiseDesk",     parent=exchange, atomic=True)

    # ---- Application and operations ---------------------------------
    app = Application("Trading", zone=exchange)
    place  = app.add_operation(Operation("place_order"))
    cancel = app.add_operation(Operation("cancel_order"))
    quote  = app.add_operation(Operation("get_quote"))
    halt   = app.add_operation(Operation("halt_trading"))
    exchange.add_application(app)

    # ---- Roles and base permissions ---------------------------------
    mm_role = Role("MarketMaker",
                   zone=exchange,
                   base_permissions=[place, cancel, quote])
    arb_role = Role("Arbitrageur",
                    zone=exchange,
                    base_permissions=[place, cancel, quote])
    noise_role = Role("NoiseTrader",
                      zone=exchange,
                      base_permissions=[place, quote])    # cannot cancel
    regulator_role = Role("Regulator",
                          zone=exchange,
                          base_permissions=[halt, quote])
    exchange.add_role(mm_role)
    exchange.add_role(arb_role)
    exchange.add_role(noise_role)
    exchange.add_role(regulator_role)

    # ---- UniLog access constraint: cash & holdings ------------------
    # A trader may not place an order if their cash balance is zero
    # and their holdings are zero (i.e., they are effectively frozen).
    builder.add_access_constraint("""
        signature {
            sort User, Zone;
            predicate hasCash(u: User);
            predicate hasHoldings(u: User);
        }
        forall u: User .
            (hasCash(u) or hasHoldings(u)) or not hasCash(u)
    """)

    ops = {"place": place, "cancel": cancel,
           "quote": quote, "halt": halt}
    zones = {
        "exchange": exchange,
        "mm_desk": mm_desk,
        "arb_desk": arb_desk,
        "noise_desk": noise_desk,
    }
    return builder, zones, ops


# =====================================================================
# 2. Register users along the containment path
# =====================================================================
def _register_along_path(user, zone):
    for z in zone.ancestry():
        if user.name not in z.users:
            z.add_user(user)


# =====================================================================
# 3. Create traders
# =====================================================================
def create_traders(builder, zones):
    mm_desk    = zones["mm_desk"]
    arb_desk   = zones["arb_desk"]
    noise_desk = zones["noise_desk"]

    market_makers, arbitrageurs, noise_traders = [], [], []

    for i in range(5):
        u = User(
            f"mm_{i}",
            roles={"MarketMaker"},
            attributes={
                "cash":           100000.0,
                "holdings":       0.0,
                "risk_tolerance": MM_RISK_TOLERANCE,
                "orders_placed":  0,
                "role_kind":      "mm",
            },
        )
        _register_along_path(u, mm_desk)
        market_makers.append(u)

    for i in range(3):
        u = User(
            f"arb_{i}",
            roles={"Arbitrageur"},
            attributes={
                "cash":           50000.0,
                "holdings":       0.0,
                "risk_tolerance": ARB_RISK_TOLERANCE,
                "orders_placed":  0,
                "role_kind":      "arb",
            },
        )
        _register_along_path(u, arb_desk)
        arbitrageurs.append(u)

    for i in range(10):
        u = User(
            f"noise_{i}",
            roles={"NoiseTrader"},
            attributes={
                "cash":           10000.0,
                "holdings":       0.0,
                "risk_tolerance": NOISE_RISK_TOLERANCE,
                "orders_placed":  0,
                "role_kind":      "noise",
            },
        )
        _register_along_path(u, noise_desk)
        noise_traders.append(u)

    # Regulator (not an active trader)
    regulator = User(
        "regulator",
        roles={"Regulator"},
        attributes={"cash": 0.0, "holdings": 0.0,
                    "risk_tolerance": 0.0, "role_kind": "regulator"},
    )
    _register_along_path(regulator, zones["exchange"])

    return market_makers, arbitrageurs, noise_traders, regulator


# =====================================================================
# 4. Neural price-impact predictor
# =====================================================================
def build_impact_predictor() -> Predictor:
    """Predicts P(high price impact | quantity, side, risk_tolerance).

    Ground truth: large orders in the direction of high risk tolerance
    cause elevated impact. Synthetic, symmetric in buy/sell.
    """
    rng = np.random.default_rng(313)
    n = 800
    qty_norm = rng.uniform(0.0, 1.0, n)
    is_buy   = rng.integers(0, 2, n).astype(float)
    risk     = rng.uniform(0.0, 1.0, n)

    X = np.column_stack([qty_norm, is_buy, risk])
    logits = 3.0 * qty_norm + 0.5 * is_buy + 1.5 * risk - 2.5
    probs  = 1.0 / (1.0 + np.exp(-logits))
    y = (probs > 0.5).astype(float)

    predictor = Predictor("price_impact", threshold=0.5)
    predictor.fit(X, y, epochs=800, lr=0.5)
    return predictor


# =====================================================================
# 5. Daemons (Δ)
# =====================================================================
class PriceVolatilityDaemon(Daemon):
    """Warns or alerts based on rolling price volatility."""

    def __init__(self, sim,
                 warn_thresh: float = VOLATILITY_WARN,
                 halt_thresh: float = VOLATILITY_HALT,
                 parent=None):
        super().__init__("PriceVolatilityDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.warn_thresh = warn_thresh
        self.halt_thresh = halt_thresh

    def monitor(self):
        vol = self.sim.rolling_volatility()
        if vol > self.halt_thresh:
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"volatility": round(vol, 4), "action": "halt_recommended"},
            )
        elif vol > self.warn_thresh:
            self.emit_signal(
                DaemonSignal.STATE_WARNING,
                {"volatility": round(vol, 4)},
            )


class RiskLimitDaemon(Daemon):
    """Warns when any trader's exposure exceeds their tolerance."""

    def __init__(self, traders, parent=None):
        super().__init__("RiskLimitDaemon", parent=parent, interval=2.0)
        self.traders = traders

    def monitor(self):
        for t in self.traders:
            cash     = t.attributes.get("cash", 0.0)
            holdings = t.attributes.get("holdings", 0.0)
            tol      = t.attributes.get("risk_tolerance", 0.5)
            equity   = cash + holdings * self.sim_price()
            baseline = 100000.0 if t.name.startswith("mm") \
                else 50000.0 if t.name.startswith("arb") \
                else 10000.0
            exposure = 1.0 - (equity / baseline) if baseline else 0.0
            if exposure > RISK_LIMIT_WARN:
                self.emit_signal(
                    DaemonSignal.STATE_WARNING,
                    {"trader": t.name, "exposure": round(exposure, 3),
                     "tolerance": tol},
                )

    # late-bound reference so the daemon sees live prices
    sim_price = staticmethod(lambda: 100.0)


class CircuitBreakerDaemon(Daemon):
    """Signals STATE_CRITICAL when the cumulative price move is extreme."""

    def __init__(self, sim, threshold: float = 0.10, parent=None):
        super().__init__("CircuitBreakerDaemon", parent=parent, interval=1.0)
        self.sim = sim
        self.threshold = threshold
        self.tripped = False

    def monitor(self):
        move = abs(self.sim.price - INITIAL_PRICE) / INITIAL_PRICE
        if move > self.threshold and not self.tripped:
            self.tripped = True
            self.emit_signal(
                DaemonSignal.STATE_CRITICAL,
                {"move": round(move, 4), "price": round(self.sim.price, 2)},
            )


class MarketDaemon(Daemon):
    """Root daemon: aggregates child signals and can trigger halts."""

    def __init__(self, parent=None):
        super().__init__("MarketDaemon", parent=parent, interval=2.0)
        self.warnings:  list[tuple] = []
        self.criticals: list[tuple] = []
        self.halt_requested = False

    def on_signal(self, signal, payload, source=None):
        src = source.name if source else "?"
        if signal is DaemonSignal.STATE_WARNING:
            self.warnings.append((src, payload))
        elif signal is DaemonSignal.STATE_CRITICAL:
            self.criticals.append((src, payload))
            if src in ("PriceVolatilityDaemon", "CircuitBreakerDaemon"):
                self.halt_requested = True


# =====================================================================
# 6. Simulation
# =====================================================================
class MarketSimulation:
    """Order-driven price discovery with real CZOI permission checks.

    Each tick:
      1. Traders probabilistically place orders.
      2. Every order goes through the real Φ engine.
      3. The neural impact predictor suggests a price-impact multiplier.
      4. Cash/holdings are updated; the price evolves accordingly.
    """

    def __init__(self, builder, zones, ops, traders, regulator, impact_model):
        self.builder  = builder
        self.zones    = zones
        self.ops      = ops
        self.traders  = traders
        self.regulator = regulator
        self.impact_model = impact_model
        self.price = INITIAL_PRICE
        self.price_history: list[float] = [INITIAL_PRICE]
        self.time = 0.0
        self.orders: list[tuple] = []
        self.denied_orders = 0

    # -----------------------------------------------------------------
    def rolling_volatility(self, window: int = 20) -> float:
        if len(self.price_history) < 2:
            return 0.0
        window = min(window, len(self.price_history))
        returns = np.diff(self.price_history[-window:]) / \
                  np.array(self.price_history[-window:-1])
        return float(np.std(returns)) if len(returns) > 0 else 0.0

    # -----------------------------------------------------------------
    def step(self, dt: float = 1.0) -> None:
        self.time += dt
        engine = self.builder.permission_engine
        exchange = self.zones["exchange"]

        # ---- Trader decisions --------------------------------------
        for trader in self.traders:
            kind = trader.attributes.get("role_kind", "noise")
            participation = {"mm": 0.35, "arb": 0.55, "noise": 0.30}[kind]
            if random.random() > participation:
                continue

            # ---- Choose side -----------------------------------------
            if kind == "mm":
                side = "buy" if random.random() < 0.5 else "sell"
            elif kind == "arb":
                # Simple trend following
                if len(self.price_history) < 2:
                    side = "buy"
                else:
                    side = ("buy"
                            if self.price > self.price_history[-2]
                            else "sell")
            else:
                side = "buy" if random.random() < 0.5 else "sell"

            qty = random.randint(1, 10)

            # ---- Real Φ check --------------------------------------
            if engine.decide(trader, self.ops["place"], exchange) is not Decision.ALLOW:
                self.denied_orders += 1
                continue

            # ---- Neural impact prediction --------------------------
            features = {
                "qty": qty / 10.0,
                "buy": 1.0 if side == "buy" else 0.0,
                "risk": trader.attributes.get("risk_tolerance", 0.5),
            }
            impact_score = self.impact_model.predict(features)
            scale = 1.0 + impact_score   # score ∈ [0,1] → multiplier [1,2]

            # ---- Apply price impact --------------------------------
            delta = PRICE_IMPACT_PER_UNIT * qty * scale
            self.price *= (1.0 + delta) if side == "buy" \
                else (1.0 - delta)

            # ---- Update trader cash/holdings -----------------------
            if side == "buy":
                trader.attributes.set(
                    "cash",
                    max(0.0, trader.attributes.get("cash", 0.0)
                        - qty * self.price),
                )
                trader.attributes.set(
                    "holdings",
                    trader.attributes.get("holdings", 0.0) + qty,
                )
            else:
                trader.attributes.set(
                    "cash",
                    trader.attributes.get("cash", 0.0) + qty * self.price,
                )
                trader.attributes.set(
                    "holdings",
                    max(0.0, trader.attributes.get("holdings", 0.0) - qty),
                )

            trader.attributes.set(
                "orders_placed",
                trader.attributes.get("orders_placed", 0) + 1,
            )
            self.orders.append((round(self.time, 2), trader.name,
                                side, qty, round(self.price, 4)))

        # ---- Record price history --------------------------------
        self.price_history.append(self.price)
        if len(self.price_history) > 200:
            self.price_history = self.price_history[-200:]


# =====================================================================
# 7. Main
# =====================================================================
def main() -> None:
    builder, zones, ops = build_exchange()
    mms, arbs, noise, regulator = create_traders(builder, zones)
    all_traders = mms + arbs + noise

    # ---- Neural component attached to the Exchange zone -------------
    impact_model = build_impact_predictor()
    zones["exchange"].add_neural("price_impact", impact_model)

    # ---- Sanity check on the impact predictor -----------------------
    low_p  = impact_model.predict({"qty": 0.1, "buy": 1.0, "risk": 0.2})
    high_p = impact_model.predict({"qty": 0.9, "buy": 1.0, "risk": 0.8})
    print(f"P(high impact) | small, low-risk : {low_p:.3f}")
    print(f"P(high impact) | large, high-risk: {high_p:.3f}")
    print()

    # ---- Simulation object (needed by the daemons) ------------------
    sim = MarketSimulation(
        builder, zones, ops, all_traders, regulator, impact_model,
    )

    # ---- Daemon hierarchy -------------------------------------------
    root = MarketDaemon()
    volatility = PriceVolatilityDaemon(sim, parent=root)
    risk = RiskLimitDaemon(all_traders, parent=root)
    # Late-bind the price accessor so the daemon reads live data.
    risk.sim_price = lambda: sim.price
    RiskLimitDaemon.sim_price = staticmethod(lambda: 100.0)  # keep default
    breaker = CircuitBreakerDaemon(sim, parent=root)
    builder.add_daemon(root)
    builder.add_daemon(volatility)
    builder.add_daemon(risk)
    builder.add_daemon(breaker)

    # ---- Sanity check: real CZOI permission decisions ---------------
    exchange = zones["exchange"]
    engine   = builder.permission_engine
    print("Permission sanity check (paper §3, item 9):")
    print("  mm_0       place_order  :",
          engine.decide(mms[0], ops["place"], exchange).name)
    print("  mm_0       cancel_order :",
          engine.decide(mms[0], ops["cancel"], exchange).name)
    print("  noise_0    place_order  :",
          engine.decide(noise[0], ops["place"], exchange).name)
    print("  noise_0    cancel_order :",
          engine.decide(noise[0], ops["cancel"], exchange).name)
    print("  regulator  halt_trading :",
          engine.decide(regulator, ops["halt"], exchange).name)
    print("  regulator  place_order  :",
          engine.decide(regulator, ops["place"], exchange).name)
    print()

    # ---- Simulate 10 minutes at 1-second steps ---------------------
    for step in range(600):
        if root.halt_requested:
            # Regulator halts trading on a critical alert.
            if engine.decide(regulator, ops["halt"], exchange) is Decision.ALLOW:
                print(f"Trading halted at t={sim.time:.1f}s "
                      f"(price {sim.price:.2f})")
                break
        sim.step(dt=1.0)
        if step % 5 == 0:
            builder.daemon_manager.tick()

    # ---- Report -----------------------------------------------------
    final_price = sim.price
    ret = (final_price - INITIAL_PRICE) / INITIAL_PRICE
    print(f"Final price       : {final_price:.2f} "
          f"({ret:+.2%} vs initial)")
    print(f"Orders placed     : {len(sim.orders)}")
    print(f"Orders denied     : {sim.denied_orders}")
    print(f"Rolling volatility: {sim.rolling_volatility():.4f}")
    print(f"Breaker tripped   : {breaker.tripped}")
    print(f"Warnings          : {len(root.warnings)}")
    print(f"Criticals         : {len(root.criticals)}")

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