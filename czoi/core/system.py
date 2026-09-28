# czoi/core/system.py
class System:
    """Base class for a full CZOA 10‑tuple system."""
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.zones: dict[str, System] = {}      # Z
        self.roles: dict[str, Role] = {}        # R
        self.users: dict[str, User] = {}        # U
        self.applications: dict[str, Application] = {}  # A
        self.operations: dict[str, Operation] = {}      # O
        self.neural: dict[str, NeuralComponent] = {}    # N
        self.embeddings: EmbeddingService = EmbeddingService()  # E
        self.constraints: ConstraintManager = ConstraintManager()  # Γ
        self.permission_engine: PermissionEngine = PermissionEngine()  # Φ
        self.daemons: list[Daemon] = []         # Δ

    def add_zone(self, zone: 'System'):
        self.zones[zone.name] = zone

    def add_role(self, role: 'Role'):
        self.roles[role.name] = role

    def add_application(self, app: 'Application'):
        self.applications[app.name] = app
        for op in app.operations.values():
            self.operations[op.name] = op

    # ... similar methods for users, neural components, daemons, etc.

class Zone(System):
    """A zone is a full CZOA system with a parent pointer."""
    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        # Inherit roles, operations, etc. from parent zone
        if parent:
            self.roles.update(parent.roles)
            self.operations.update(parent.operations)
            # ... inherit other components as per containment principles