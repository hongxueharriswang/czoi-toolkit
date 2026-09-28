"""Quickstart: recursive zones, roles, and UniLog constraints.

Mirrors the hospital scenario from the CZOA paper's introduction.
"""
from czoi import (
    CZOABuilder, Application, ConstraintKind, Decision, Operation,
    Role, User,
)


def build_hospital():
    b = CZOABuilder("RegionalHealthAuthority")

    # Recursive subsystem tree
    hospital = b.add_zone("CityHospitalA")
    emergency = b.add_zone("Emergency", parent=hospital, atomic=True)

    # Application and operations
    emr = Application("EMR", zone=hospital)
    prescribe = emr.add_operation(Operation("prescribe"))
    dispense = emr.add_operation(Operation("dispense"))
    view = emr.add_operation(Operation("view_patient"))
    hospital.add_application(emr)

    # Roles and intra-zone seniority
    attending = Role("AttendingPhysician", zone=hospital,
                     base_permissions=[prescribe, view])
    nurse = Role("Nurse", zone=hospital,
                 base_permissions=[dispense, view])
    hospital.add_role(attending)
    hospital.add_role(nurse)
    attending.add_junior(nurse)

    # Users (containment enforced automatically)
    alice = User("alice", roles={"AttendingPhysician"})
    bob = User("bob", roles={"Nurse"})
    b.root.add_user(alice)
    b.root.add_user(bob)
    hospital.add_user(alice)
    hospital.add_user(bob)
    emergency.add_user(alice)
    emergency.add_user(bob)

    # UniLog constraints ---------------------------------------------
    b.add_identity_constraint("""
        signature {
            sort Zone, User;
            function parent(z: Zone) : Zone;
            predicate inZone(u: User, z: Zone);
        }
        forall u: User, z: Zone .
            (inZone(u, z) and parent(z) != z) -> inZone(u, parent(z))
    """)

    # Separation of duty — access constraint
    b.add_access_constraint("""
        signature {
            sort User, Operation;
            predicate prescribe(u: User, o: Operation);
            predicate dispense(u: User, o: Operation);
        }
        forall u: User . not (prescribe(u, EMR_prescribe) and
                              dispense(u, EMR_dispense))
    """)

    return b, hospital, emergency, alice, bob, prescribe, dispense


def main():
    b, hospital, emergency, alice, bob, prescribe, dispense = build_hospital()
    engine = b.permission_engine

    print("Emergency inherits roles:", sorted(emergency.roles))
    print("alice prescribe @ Emergency:",
          engine.decide(alice, prescribe, emergency).name)
    print("bob   prescribe @ Emergency:",
          engine.decide(bob, prescribe, emergency).name)
    print("bob   dispense  @ Emergency:",
          engine.decide(bob, dispense, emergency).name)

    print("\nUniLog constraint status:")
    for kind, ok in b.constraint_manager.check_all().items():
        print(f"  {kind}: {'OK' if ok else 'VIOLATED'}")

    print("\nSubsystem tree:")
    for node in b.root.walk():
        indent = "  " * node.depth()
        print(f"{indent}- {node.name} "
              f"(roles={len(node.roles)}, ops={len(node.operations)})")


if __name__ == "__main__":
    main()