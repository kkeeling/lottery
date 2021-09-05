from django.contrib import admin
from lottery.admin import lottery_admin_site

from . import models

@admin.register(models.BackgroundTask, site=lottery_admin_site)
class BackgroundTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'action', 'user', 'status', 'created']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False