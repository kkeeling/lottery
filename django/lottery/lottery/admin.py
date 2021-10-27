from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.urls import path

from django_celery_beat.admin import *


class LotteryAdminSite(admin.AdminSite):	
    # Extend AdminSite so we can add dynamic context to admin views, like the index.
    site_url = None
    enable_nav_sidebar = False
    site_header = 'GreatLotto'
    site_title = 'GreatLotto'
    index_title = 'Dashboard'

    def index(self, request, extra_context=None):
        if extra_context == None:
            extra_context = {}

        return super(LotteryAdminSite, self).index(request, extra_context)

    def get_urls(self):
        custom_urls = [
            # path('project/plans/', self.admin_view(plan_editor_view), name='plan_editor'),
        ]
        urls = super(LotteryAdminSite, self).get_urls()
        return custom_urls + urls

lottery_admin_site = LotteryAdminSite(name='lottery_admin')


# admin.site.unregister(IntervalSchedule)
# admin.site.unregister(CrontabSchedule)
# admin.site.unregister(SolarSchedule)
# admin.site.unregister(ClockedSchedule)
# admin.site.unregister(PeriodicTask)

# admin.register(IntervalSchedule, site=lottery_admin_site)
# admin.register(CrontabSchedule, site=lottery_admin_site)
# admin.register(SolarSchedule, site=lottery_admin_site)
# admin.register(ClockedSchedule, ClockedScheduleAdmin, site=lottery_admin_site)
# admin.register(PeriodicTask, PeriodicTaskAdmin, site=lottery_admin_site)
