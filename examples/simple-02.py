"""
gamma.py — Inter-zone role inheritance via gamma mappings.

Demonstrates the paper's inter-zone role mapping:

    γ : (Z_child, r_child) → (Z_parent, r_parent)

In this example:

    γ : (Dev, Developer) → (Corp, Engineer)

A user holding Developer in the Dev zone therefore inherits the
Engineer role's base permissions — including `access_vpn`, defined in
the corporate zone — without being a member of Corp itself.

The CZOI implementation applies the mapping by granting the child
role the parent role's operations. This preserves the toolkit's
minimality (permissions are always on roles; the gamma relation is
expressed as a permission-transfer rule).
"""
from __future__ import annotations

from czoi import (
    Application, CZOABuilder, Decision, Operation, Role, User,
)


# =====================================================================
# Gamma mapping helper
# =====================================================================
def add_gamma_mapping(
    child_zone,
    child_role: Role,
    parent_zone,
    parent_role: Role,
    weight: float = 1.0,
) -> None:
    """Apply γ: (child_zone, child_role) → (parent_zone, parent_role).

    The child role receives every operation in the parent role's base
    permission set. `weight` in [0, 1] scales the transfer: a weight of
    1.0 grants all operations; a lower weight grants only a subset.

    In the paper (§3, item 2), the weight represents the degree of
    permission transfer (e.g., requiring additional training). Here we
    implement the weight deterministically: operations are transferred
    up to `int(weight * len(parent_ops))`, ordered by qualified name
    so the result is reproducible.
    """
    if not 0.0 <= weight <= 1.0:
        raise ValueError("gamma weight must be in [0, 1]")

    parent_ops = sorted(parent_role.base_permissions,
                        key=lambda o: o.qualified_name)
    n_transfer = max(1, int(round(weight * len(parent_ops))))
    for op in parent_ops[:n_transfer]:
        child_role.grant(op)
    child_zone._invalidate_cache()


def remove_gamma_mapping(
    child_zone,
    child_role: Role,
    parent_role: Role,
) -> None:
    """Revoke every operation the child role inherited via γ."""
    for op in parent_role.base_permissions:
        child_role.revoke(op)
    child_zone._invalidate_cache()


# =====================================================================
# 1. Build the corporate system
# =====================================================================
builder = CZOABuilder("Corp")
corp = builder.root
dev = builder.add_zone("Dev", parent=corp, atomic=True)

# ---- Applications and operations -----------------------------------
# The Corp-level application exposes the VPN operation.
global_app = Application("Global", zone=corp)
access_vpn = global_app.add_operation(Operation("access_vpn"))
corp.add_application(global_app)

# The Dev-level application exposes the source-control operation.
dev_app = Application("DevTools", zone=dev)
commit_code = dev_app.add_operation(Operation("commit_code"))
dev.add_application(dev_app)

# ---- Roles --------------------------------------------------------
# Corp Engineer holds the corporate VPN permission.
corp_eng = Role("Engineer", zone=corp, base_permissions=[access_vpn])
corp.add_role(corp_eng)

# Dev Developer holds the source-control permission.
dev_eng = Role("Developer", zone=dev, base_permissions=[commit_code])
dev.add_role(dev_eng)

# ---- Apply the gamma mapping --------------------------------------
# γ : (Dev, Developer) → (Corp, Engineer) with weight 1.0
add_gamma_mapping(dev, dev_eng, corp, corp_eng, weight=1.0)


# =====================================================================
# 2. Create a user
# =====================================================================
alice = User("alice", roles={"Developer"})

# Containment principle: register at the root, then the Dev zone.
# (Alice is a member of Corp by inheritance but is not assigned a role
# in Corp itself.)
corp.add_user(alice)
dev.add_user(alice)


# =====================================================================
# 3. Check permissions
# =====================================================================
engine = builder.permission_engine

print("Permission checks")
print("-----------------")
print(f"alice commit_code  (Dev)  : "
      f"{engine.decide(alice, commit_code, dev).name}")
print(f"alice access_vpn   (Dev)  : "
      f"{engine.decide(alice, access_vpn,  dev).name}")
print(f"alice access_vpn   (Corp) : "
      f"{engine.decide(alice, access_vpn,  corp).name}")
print()

# ---- Demonstrate that removing γ revokes the inherited permission --
print("After remove_gamma_mapping(dev, Developer, Engineer):")
remove_gamma_mapping(dev, dev_eng, corp_eng)
print(f"  alice access_vpn   (Dev) : "
      f"{engine.decide(alice, access_vpn,  dev).name}")

# ---- Restore γ for the effective-permission summary ---------------
add_gamma_mapping(dev, dev_eng, corp, corp_eng, weight=1.0)


# =====================================================================
# 4. Show the effective permission sets
# =====================================================================
def effective(role: Role) -> list[str]:
    """Paper §3, item 9: the effective permission set of a role."""
    ops = set(role.base_permissions)
    for junior in role.junior_roles:
        ops |= junior.base_permissions
    return sorted(o.qualified_name for o in ops)


print()
print(f"Corp Engineer base permissions  : "
      f"{sorted(o.qualified_name for o in corp_eng.base_permissions)}")
print(f"Dev  Developer base permissions : "
      f"{sorted(o.qualified_name for o in dev_eng.base_permissions)}")
print(f"Dev  Developer effective        : {effective(dev_eng)}")