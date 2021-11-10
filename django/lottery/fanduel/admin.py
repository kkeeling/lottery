import math

from django.contrib import admin, messages

from celery import chain
from configuration.models import BackgroundTask

from . import models
from . import tasks


class ContestPrizeInline(admin.TabularInline):
    model = models.ContestPrize


@admin.register(models.Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = (
        'url',
        'name',
        'cost',
        'entries_url',
    )
    inlines = [
        ContestPrizeInline
    ]
    actions = [
        'get_data_for_contests',
        'get_entries'
    ]

    def get_data_for_contests(self, request, queryset):
        if queryset.count() > 1:
            messages.add_message(
                request,
                messages.ERROR,
                'You may only request data for 1 contest at a time.'
            )
            return

        contest = queryset[0]

        tasks.get_contest_data.delay(
            contest.id, 
            BackgroundTask.objects.create(user=request.user, name='Get Contest Data').id
        )

        messages.add_message(
            request,
            messages.WARNING,
            f'Getting contest data from {contest.url}'
        )
    get_data_for_contests.short_description = 'Get Data For Selected Contests'

    def get_entries(self, request, queryset):
        if queryset.count() > 1:
            messages.add_message(
                request,
                messages.ERROR,
                'You may only request entries for 1 contest at a time.'
            )
            return

        contest = queryset[0]
        chain([
            tasks.get_entries_page_for_contest.si(contest.id, page, math.ceil(contest.num_entries/10)) for page in range(0, math.ceil(contest.num_entries/10))
        ])()
    get_entries.short_description = 'Get Entries For Selected Contests'


@admin.register(models.ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'contest',
        'entry_url',
    )
