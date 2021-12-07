import datetime
import math
import os

from django.contrib import admin, messages
from django.conf import settings

from celery import chain, group, chord
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
        'slate_year',
        'slate_week',
        'is_main_slate',
        'cost',
        'last_page_processed',
    )
    inlines = [
        ContestPrizeInline
    ]
    actions = [
        'get_data_for_contests',
        'get_entries',
        'export_contests',
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

        if contest.last_page_processed == 0:
            contest.entries.all().delete()

        group([
            tasks.get_entries_page_for_contest.si(contest.id, page, math.ceil(contest.num_entries/50)) for page in range(contest.last_page_processed, math.ceil(contest.num_entries/50))
        ])()
    get_entries.short_description = 'Get Entries For Selected Contests'

    def export_contests(self, request, queryset):
        task = BackgroundTask()
        task.name = f'Export Contest Data'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = f'Contest Export {timestamp}.csv'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_contest_data.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        task = BackgroundTask()
        task.name = f'Export Contest Prize Data'
        task.user = request.user
        task.save()

        result_file = f'Contest Prize Export {timestamp}.csv'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_contest_prize_data.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        task = BackgroundTask()
        task.name = f'Export Contest Entries Data'
        task.user = request.user
        task.save()

        result_file = f'Contest Entries Export {timestamp}.csv'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_contest_entries_data.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export_contests.short_description = 'Export data from selected contest'


@admin.register(models.ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'username',
        'contest',
        'entry_url',
    )
    search_fields = (
        'username',
    )
