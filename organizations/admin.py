from django.contrib import admin
from .models import Organization, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'member_count']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    @admin.display(description='Members')
    def member_count(self, obj):
        return obj.members.count()


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'joined_at']
    list_filter = ['role', 'joined_at']
    search_fields = ['user__email', 'organization__name']
    readonly_fields = ['id', 'joined_at']
