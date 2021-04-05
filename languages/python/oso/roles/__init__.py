from dataclasses import dataclass
from typing import Any
# Roles Library

# Set up roles (configure)


# Internal types
@dataclass
class Permission:
    id: int
    resource_type: Any
    action: str

@dataclass
class Role:
    id: int
    resource_type: Any
    name: str

@dataclass
class ScopedRole:
    id: int
    resource_id: int
    role_id: int

@dataclass
class RolePermission:
    id: int
    role_id: int
    permission_id: int

@dataclass
class ScopedRolePermission:
    id: int
    scoped_role_id: int
    permission_id: int

@dataclass
class ParentRelationship:
    id: int
    name: str
    child_type: Any
    parent_type: Any
    parent_selector: Any

# If you have from_role, you also get to_role
# add types probably
@dataclass
class ImpliedRole:
    id: int
    from_role_id: int
    to_role_id: int

# scoped the second most specifically, scoped for all children of the parent
class ParentImpliedRole:
    id: int
    parent_id: int
    from_role: int #nullable
    to_role: int   #nullable

# scoped the most specifically, for a single child record
class ParentChildImpliedRole:
    id: int
    parent_id: int
    child_id: int
    from_role: int #nullable
    to_role: int   #nullable

@dataclass
class UserRole:
    id: int
    user: Any
    resource: Any
    role_id: int

# Roles api from polar

# TODO: A nice way to add indexes to this.
class Collection:
    def __init__(self):
        self.elements = {}
        self.next_id = 0

    def get_id(self):
        id = self.next_id
        self.next_id += 1
        return id

class OsoRoles:
    def __init__(self):
        self.parent_relationships = Collection()
        self.permissions = Collection()
        self.roles = Collection()
        self.scoped_roles = Collection()
        self.role_permissions = Collection()
        self.scoped_role_permissions = Collection()
        self.implied_roles = Collection()
        self.parent_implied_roles = Collection()
        self.parent_child_implied_roles = Collection()
        self.user_roles = Collection()

    def new_relationship(self, name, child, parent, get):
        id = self.parent_relationships.get_id()
        relationship = ParentRelationship(id=id, name=name, parent_type=parent, child_type=child, parent_selector=get)
        self.parent_relationships.elements[id] = relationship
        return relationship

    def new_permission(self, resource, action):
        id = self.permissions.get_id()
        permission = Permission(id=id, resource_type=resource, action=action)
        self.permissions.elements[id] = permission
        return permission

    def new_role(self, resource, name):
        id = self.roles.get_id()
        role = Role(id=id, resource_type=resource, name=name)
        self.roles.elements[id] = role
        return role

    #TODO: scoped roles

    def new_role_permission(self, role, permission):
        # @TODO:
        # If resources don't match, ensure there's a relationship.
        # If permission is on a child type, ensure there's no roles for that child type.

        assert(isinstance(role, Role))
        assert(isinstance(permission, Permission))

        assert(role.id in self.roles.elements)
        assert(permission.id in self.permissions.elements)

        id = self.role_permissions.get_id()
        role_permission = RolePermission(id=id, role_id=role.id, permission_id=permission.id)
        self.role_permissions.elements[id] = role_permission

        return role_permission

    #TODO: scoped role permissions

    def new_role_implies(self, from_role, to_role):
        # @TODO:
        # If resources don't match, ensure there's a relationship.
        # Two mutually exclusive roles can not be implied by the same role.

        assert(isinstance(from_role, Role))
        assert(isinstance(to_role, Role))

        assert(from_role.id in self.roles.elements)
        assert(to_role.id in self.roles.elements)

        id = self.implied_roles.get_id()
        implied_role = ImpliedRole(id=id, from_role_id=from_role.id, to_role_id=to_role.id)
        self.implied_roles.elements[id] = implied_role

        return implied_role

    #TODO: Scoped implied roles (by parent)
    #TODO: Scoped implied roles (by parent and child)

    # Start of the "dynamic api"

    def assign_role(self, user, resource, role):
        # @TODO:
        # Can't be assigned to two different mutually exclusive roles.
        # Role has to be on the resource.

        assert(isinstance(role, Role))
        assert(role.id in self.roles.elements)

        id = self.user_roles.get_id()
        user_role = UserRole(id=id, user=user, resource=resource, role_id=role.id)
        self.user_roles.elements[id] = user_role

        return user_role

    # Internal api for evaluation of stuff
    def _role_allows(self, user, action, resource):
        # a user is aloud to take an action on a resource if they have
        # permission to.
        # That permission comes from a role.
        # That role comes from a direct assignment to a role with the permission
        # or assignment to a role that implies a role with the permission.

        #@TODO Handle scoping.

        # Find the permission.
        permission = None
        for _, perm in self.permissions.elements.items():
            if perm.resource_type == resource.__class__ and perm.action == action:
                permission = perm
                break
        if not permission:
            return False

        # Find all role ids with that permission.
        role_ids = set()
        for _, role_perm in self.role_permissions.elements.items():
            if role_perm.permission_id == permission.id:
                role_ids.add(role_perm.role_id)
        if len(role_ids) == 0:
            return False

        # Recursively find all roles that imply those roles.
        # @TODO: Handle scoped implied rules.
        while True:
            size = len(role_ids)

            for _, implied_role in self.implied_roles.elements.items():

                new_role_ids = set()
                for role_id in role_ids:
                    if implied_role.to_role_id == role_id:
                        new_role_ids.add(implied_role.from_role_id)

                role_ids = role_ids.union(new_role_ids)

            if len(role_ids) == size:
                break

        # Get the actual roles.
        roles = []
        for _, role in self.roles.elements.items():
            if role.id in role_ids:
                roles.append(role)

        # For each role, if it's not on the same type as this resource, get
        # the resource that it is on and it's id.
        role_type_resources = []
        for role in roles:
            if role.resource_type == resource.__class__:
                # Role is defined on the same type as resource.
                role_type_resources.append((role, resource.__class__, resource))
            else:
                # Role is defined on a different type than resource.
                # Walk up the parent relationships to get the resource the role is on.
                role_resource = resource
                role_resource_type = resource.__class__
                while role_resource_type != role.resource_type:
                    # @NOTE: This code assumes there's only one parent for a type.
                    found = False
                    for _, relationship in self.parent_relationships.elements.items():
                        if relationship.child_type == role_resource_type:
                            role_resource = relationship.parent_selector(role_resource)
                            role_resource_type = role_resource.__class__
                            found = True
                            break
                    if not found:
                        print("Error: No path to resource type that a permission is defined on")
                        print("This should be forbidden to construct!")
                        return False
                role_type_resources.append((role, role_resource_type, role_resource))

        # See if the user is assigned to any of those roles
        for _, user_role in self.user_roles.elements.items():
            for (role,_,resource) in role_type_resources:
                if user_role.role_id == role.id and user_role.user == user and user_role.resource == resource:
                    return True

        return False

    #TODO: Update role
    #TODO: Remove role

    def enable(self, oso):
        # The "Polar api"
        class Roles:
            @staticmethod
            def role_allows(user, action, resource):
                return self._role_allows(user, action, resource)

        oso.register_class(Roles)