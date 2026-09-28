"""Demonstrates the four families of UniLog constraints."""
from czoi import ConstraintKind, CZOABuilder


def main():
    b = CZOABuilder("DemoOrg")
    cm = b.constraint_manager

    # Identity constraint
    cm.add(ConstraintKind.IDENTITY, """
        signature { sort Zone; predicate valid(z: Zone); }
        forall z: Zone . valid(z) -> valid(z)
    """)

    # Trigger constraint (temporal)
    cm.add(ConstraintKind.TRIGGER, """
        signature {
            sort Patient; predicate critical(p: Patient);
            predicate alerted(p: Patient);
        }
        forall p: Patient . critical(p) -> alerted(p)
    """)

    # Goal constraint
    cm.add(ConstraintKind.GOAL, """
        signature { sort KPI; predicate min(k: KPI); predicate opt(k: KPI); }
        forall k: KPI . min(k) -> opt(k)
    """)

    # Access constraint
    cm.add(ConstraintKind.ACCESS, """
        signature {
            sort User;
            predicate prescribe(u: User);
            predicate dispense(u: User);
        }
        forall u: User . not (prescribe(u) and dispense(u))
    """)

    results = cm.check_all()
    for kind, ok in results.items():
        print(f"{kind}: {'OK' if ok else 'VIOLATED'}")


if __name__ == "__main__":
    main()
    