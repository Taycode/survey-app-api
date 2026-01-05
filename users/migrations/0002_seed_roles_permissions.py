from django.db import migrations


def seed_roles_permissions(apps, schema_editor):
    """Seed default roles and permissions."""
    Permission = apps.get_model('users', 'Permission')
    Role = apps.get_model('users', 'Role')
    RolePermission = apps.get_model('users', 'RolePermission')

    # Create permissions
    permissions_data = [
        ('create_survey', 'Create new surveys'),
        ('edit_survey', 'Edit existing surveys'),
        ('delete_survey', 'Delete surveys'),
        ('publish_survey', 'Publish surveys'),
        ('view_responses', 'View survey responses'),
        ('export_responses', 'Export survey responses'),
        ('view_analytics', 'View analytics dashboard'),
        ('manage_users', 'Manage users and roles'),
        ('view_audit_logs', 'View audit logs'),
    ]

    permissions = {}
    for codename, description in permissions_data:
        perm = Permission.objects.create(codename=codename, description=description)
        permissions[codename] = perm

    # Create roles
    admin_role = Role.objects.create(
        name='admin',
        description='Full access to all features'
    )
    manager_role = Role.objects.create(
        name='manager',
        description='Can create/manage surveys and view/export responses'
    )
    viewer_role = Role.objects.create(
        name='viewer',
        description='Read-only access to survey responses'
    )

    # Assign permissions to roles
    # Admin gets all permissions
    for perm in permissions.values():
        RolePermission.objects.create(role=admin_role, permission=perm)

    # Manager permissions
    manager_perms = [
        'create_survey', 'edit_survey', 'delete_survey', 'publish_survey',
        'view_responses', 'export_responses', 'view_analytics'
    ]
    for codename in manager_perms:
        RolePermission.objects.create(role=manager_role, permission=permissions[codename])

    # Viewer permissions
    viewer_perms = ['view_responses']
    for codename in viewer_perms:
        RolePermission.objects.create(role=viewer_role, permission=permissions[codename])


def reverse_seed(apps, schema_editor):
    """Reverse the seeding."""
    Permission = apps.get_model('users', 'Permission')
    Role = apps.get_model('users', 'Role')
    
    Permission.objects.all().delete()
    Role.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_roles_permissions, reverse_seed),
    ]
