"""
basic.py — Minimal CZOI example: roles, seniority, permission checks.

Demonstrates:
  * A Company root zone with an HR child zone.
  * Two roles with an intra-zone seniority relation.
  * An application exposing two atomic operations.
  * Two users, each holding one role.
  * Real CZOA permission calculus (Φ) on every decision.
"""
from czoi import (
    Application, CZOABuilder, Decision, Operation, Role, User,
)


# =====================================================================
# 1. Build the system
# =====================================================================
builder = CZOABuilder("Company")
company = builder.root
hr = builder.add_zone("HR", parent=company, atomic=True)

# ---- Roles with an intra-zone seniority relation -------------------
# The Manager is senior to the Assistant. A manager therefore inherits
# every permission the assistant holds (paper §3, item 2).
manager_role   = Role("Manager",   zone=hr)
assistant_role = Role("Assistant", zone=hr)
manager_role.add_junior(assistant_role)   # Manager >=_HR Assistant

hr.add_role(manager_role)
hr.add_role(assistant_role)

# ---- Application and operations ------------------------------------
app = Application("HRSystem", zone=hr)
view_employee = app.add_operation(Operation("view_employee"))
edit_employee = app.add_operation(Operation("edit_employee"))
hr.add_application(app)

# ---- Base permissions ----------------------------------------------
assistant_role.grant(view_employee)
manager_role.grant(edit_employee)

# ---- Users --------------------------------------------------------
alice = User("alice", roles={"Assistant"})
bob   = User("bob",   roles={"Manager"})

# Containment principle: register at the root first, then the zone.
company.add_user(alice)
hr.add_user(alice)
company.add_user(bob)
hr.add_user(bob)


# =====================================================================
# 2. Check permissions
# =====================================================================
engine = builder.permission_engine

print("Permission checks")
print("-----------------")
print(f"alice view_employee  : "
      f"{engine.decide(alice, view_employee, hr).name}")
print(f"alice edit_employee  : "
      f"{engine.decide(alice, edit_employee, hr).name}")
print(f"bob   view_employee  : "
      f"{engine.decide(bob,   view_employee, hr).name}")
print(f"bob   edit_employee  : "
      f"{engine.decide(bob,   edit_employee, hr).name}")
print()

# ---- Demonstrate the seniority relation ----------------------------
# The manager inherits the assistant's permissions. If we grant the
# assistant a new permission, the manager immediately gains it too.
print("After assistant_role.grant(view_employee):")
print(f"  bob view_employee : "
      f"{engine.decide(bob, view_employee, hr).name}")

# Effective permissions of each role (paper §3, item 9).
def effective(role):
    perms = set(role.base_permissions)
    for junior in role.junior_roles:
        perms |= junior.base_permissions
    return sorted(p.qualified_name for p in perms)

print()
print(f"Assistant effective permissions : {effective(assistant_role)}")
print(f"Manager   effective permissions : {effective(manager_role)}")