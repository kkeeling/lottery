import csv
import datetime
import numpy
import os
import traceback

import requests

from celery import shared_task, chord, group, chain

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Q, F
from django.db.models.aggregates import Avg
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import path
from django.utils.html import mark_safe
from django import forms

from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from configuration.models import BackgroundTask
from . import models, tasks, forms


def groupplayerform_factory(build):
    class GroupPlayerForm(forms.ModelForm):
        m_file = forms.ModelChoiceField(
            queryset=models.BuildPlayerProjection.objects.filter(build=build)
        )
    return GroupPlayerForm


# Inlines


class RaceResultInline(admin.TabularInline):
    model = models.RaceResult
    extra = 0
    fields = (
        'driver',
        'starting_position',
        'finishing_position',
        'laps_led',
        'finishing_status',
    )
    readonly_fields = (
        'driver',
        'starting_position',
        'finishing_position',
        'laps_led',
        'finishing_status',
    )


class RaceCautionInline(admin.TabularInline):
    model = models.RaceCautionSegment
    extra = 0
    fields = (
        'start_lap',
        'end_lap',
        'reason',
        'comment',
    )
    readonly_fields = (
        'start_lap',
        'end_lap',
        'reason',
        'comment',
    )


class RaceInfractionInline(admin.TabularInline):
    model = models.RaceInfraction
    extra = 0
    fields = (
        'driver',
        'lap',
        'infraction',
        'penalty',
        'notes',
    )
    readonly_fields = (
        'driver',
        'lap',
        'infraction',
        'penalty',
        'notes',
    )


class RaceSimDriverInline(admin.TabularInline):
    model = models.RaceSimDriver
    extra = 0
    fields = (
        'driver',
        'starting_position',
        'dk_salary',
        'dk_op',
        'speed_min',
        'speed_max',
        'crash_rate',
        'infraction_rate',
        'avg_fp',
        'avg_fl',
        'avg_ll',
        'avg_dk_score',
        'gto',
    )
    read_only_fields = (
        'avg_fp',
        'avg_fl',
        'avg_ll',
        'avg_dk_score',
    )


class RaceSimDamageProfileInline(admin.TabularInline):
    model = models.RaceSimDamageProfile
    extra = 0
    fields = (
        'name',
        'min_cars_involved',
        'max_cars_involved',
        'prob_no_damage',
        'prob_minor_damage',
        'prob_medium_damage',
        'prob_dnf',
    )


class RaceSimPenaltyProfileInline(admin.TabularInline):
    model = models.RaceSimPenaltyProfile
    extra = 0
    fields = (
        'stage',
        'is_green',
        'floor_impact',
        'ceiling_impact',
    )


class RaceSimLapsLedInline(admin.TabularInline):
    model = models.RaceSimLapsLedProfile
    extra = 0
    fields = (
        'pct_laps_led_min',
        'pct_laps_led_max',
        'cum_laps_led_min',
        'cum_laps_led_max',
        'rank_order',
        # 'eligible_fl_max',
    )


class RaceSimFastestLapsInline(admin.TabularInline):
    model = models.RaceSimFastestLapsProfile
    extra = 0
    fields = (
        'pct_fastest_laps_min',
        'pct_fastest_laps_max',
        'cum_fastest_laps_min',
        'cum_fastest_laps_max',
        'eligible_speed_min',
        'eligible_speed_max',
    )


class SlateBuildFieldLineupInline(admin.TabularInline):
    model = models.SlateBuildFieldLineup
    extra = 0
    fields = (
        'opponent_handle',
        'slate_lineup',
    )
    raw_id_fields = (
        'slate_lineup',
    )


class SlateBuildGroupPlayerInline(admin.TabularInline):
    model = models.SlateBuildGroupPlayer
    autocomplete_fields = ['player']

    def get_form(self, request, obj=None, **kwargs):
        if obj is not None and obj.build is not None:
            kwargs['form'] = groupplayerform_factory(obj.build)
        return super(SlateBuildGroupPlayerInline, self).get_form(request, obj, **kwargs)


class ContestPrizeInline(admin.TabularInline):
    model = models.ContestPrize

# Admins

@admin.register(models.Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = (
        'dk_name',
        'fd_name',
        'ma_name',
        'nascar_name'
    )
    list_editable = (
        'fd_name',
        'ma_name',
        'nascar_name'
    )
    search_fields = (
        'dk_name',
        'fd_name',
        'ma_name',
        'nascar_name'
    )


@admin.register(models.MissingAlias)
class MissingAliasAdmin(admin.ModelAdmin):
    list_display = (
        'player_name',
        'site',
        'choose_alias_1_button',
        'choose_alias_2_button',
        'choose_alias_3_button',
        'create_new_alias_button',
    )
    search_fields = (
        'player_name',
        'alias_1',
        'alias_2',
        'alias_3',
    )
    actions = [
        'create_new_aliases'
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nascar-alias-choose/<int:pk>/<int:chosen_alias_pk>/', self.choose_alias, name="admin_nascar_choose_alias"),
        ]
        return my_urls + urls

    def choose_alias(self, request, pk, chosen_alias_pk=0):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        # Get the scenario to activate
        missing_alias = get_object_or_404(models.MissingAlias, pk=pk)
        if chosen_alias_pk > 0:
            # update chosen alias with new player name
            alias = models.Alias.objects.get(pk=chosen_alias_pk)

            if missing_alias.site == 'fanduel':
                alias.fd_name = missing_alias.player_name
            elif missing_alias.site == 'draftkings':
                alias.dk_name = missing_alias.player_name
            elif missing_alias.site == 'ma':
                alias.ma_name = missing_alias.player_name
            elif missing_alias.site == 'nascar':
                alias.nascar_name = missing_alias.player_name
            
            alias.save()

            self.message_user(request, 'Alias updated: {}'.format(str(alias)), level=messages.INFO)
        else:
            alias = models.Alias.objects.create(
                dk_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                ma_name=missing_alias.player_name,
                nascar_name=missing_alias.player_name
            )

            self.message_user(request, 'New alias created: {}'.format(str(alias)), level=messages.INFO)

        missing_alias.delete()

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def create_new_aliases(self, request, queryset):
        count = queryset.count()
        for missing_alias in queryset:
            models.Alias.objects.create(
                dk_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                ma_name=missing_alias.player_name,
                nascar_name=missing_alias.player_name
            )

        self.message_user(request, '{} new aliases created.'.format(count), level=messages.INFO)
        queryset.delete()


@admin.register(models.Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        'get_driver_image',
        'full_name',
        'get_badge',
        'get_manufacturer',
        'team',
    )
    search_fields = (
        'first_name',
        'last_name',
    )
    list_filter = (
        ('team', DropdownFilter),
    )

    def get_driver_image(self, obj):
        if obj.driver_image is not None and obj.driver_image != '':
            return mark_safe(f'<img src="{obj.driver_image}" width="10%" height="10%" />')
        elif obj.badge_image is not None and obj.badge_image != '':
            return mark_safe(f'<img src="{obj.badge_image}" width="10%" height="10%" />')
        return None
    get_driver_image.short_description = "Driver"

    def get_badge(self, obj):
        if obj.badge_image is not None and obj.badge_image != '':
            return mark_safe(f'<img src="{obj.badge_image}" width="10%" height="10%" />')
        return obj.badge
    get_badge.short_description = "#"

    def get_manufacturer(self, obj):
        if obj.manufacturer_image is not None and obj.manufacturer_image != '':
            return mark_safe(f'<img src="{obj.manufacturer_image}" width="10%" height="10%" />')
        return None
    get_manufacturer.short_description = "Manufacturer"


@admin.register(models.Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = (
        'track_name',
        'track_type'
    )
    actions = [
        'export'
    ]

    def export(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Track Data'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = f'tracks-{timestamp}.csv'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_tracks.delay(list(queryset.values_list('track_id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue while you\'re waiting. A new message will appear here once your export is ready.')
    export.short_description = 'Export selected tracks'


@admin.register(models.Race)
class RaceAdmin(admin.ModelAdmin):
    date_hierarchy = 'race_date'
    
    list_display = (
        'race_name',
        'series',
        'race_date',
        'track',
        'scheduled_laps',
    )
    search_fields = (
        'race_name',
        'track__track_name',
    )
    list_filter = (
        'series',
        'track__track_type',
    )
    inlines = [
        RaceResultInline,
        RaceCautionInline,
        RaceInfractionInline,
    ]


@admin.register(models.RaceDriverLap)
class RaceDriverLapAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'race',
        'driver',
        'lap',
        'lap_time',
        'lap_speed',
        'running_pos',
    )
    search_fields = (
        'race__race_name',
        'driver',
    )
    list_filter = (
        ('race', RelatedDropdownFilter),
    )


@admin.register(models.RaceSim)
class RaceSimAdmin(admin.ModelAdmin):
    list_display = (
        'pk',
        'race',
        'iterations',
        'optimal_lineups_per_iteration',
        'run_with_gto',
        'run_with_lineup_rankings',
        'for_backtest',
        'export_template_button',
        'sim_button',
        'export_all_results_button',
        'export_dk_results_button',
        'get_lineups_link',
        'get_builds_link',
    )
    list_editable = (
        'iterations',
        'optimal_lineups_per_iteration',
        'run_with_gto',
        'run_with_lineup_rankings',
    )
    raw_id_fields = (
        'race',
    )
    list_filter = (
        'for_backtest',
    )
    inlines = [
        RaceSimDamageProfileInline,
        RaceSimPenaltyProfileInline,
        RaceSimFastestLapsInline,
        RaceSimLapsLedInline,
        RaceSimDriverInline
    ]
    actions = ['calculate_driver_gto', 'rank_lineups', 'export_results_many', 'create_backtest_sim']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_sim(request, obj)

    def process_sim(self, request, sim):
        if bool(sim.input_file):
            tasks.process_sim_input_file.delay(
                sim.id,
                BackgroundTask.objects.create(
                    name='Processing sim input file',
                    user=request.user
                ).id
            )

            messages.add_message(
                request,
                messages.WARNING,
                'Your sim input file is being processed. You may continue while you\'re waiting. A new message will appear here once the slate is ready.')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nascar-race-template/<int:pk>/', self.export_template, name="nascar_admin_slate_template"),
            path('nascar-race-simulate/<int:pk>/', self.simulate, name="nascar_admin_slate_simulate"),
            path('nascar-race-results/<int:pk>/', self.export_results, name="nascar_admin_slate_export_results"),
            path('nascar-race-dk_results/<int:pk>/', self.export_dk_results, name="nascar_admin_slate_export_dk"),
        ]
        return my_urls + urls

    def get_lineups_link(self, obj):
        if obj.sim_lineups.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/racesimlineup/?sim__id__exact={}" target="_blank">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Optimal Lineups'

    def get_builds_link(self, obj):
        if obj.builds.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/slatebuild/?sim__id__exact={}" target="_blank">Builds</a>'.format(obj.id))
        return 'None'
    get_builds_link.short_description = 'Builds'

    def create_backtest_sim(self, request, queryset):
        for sim in queryset:
            sim.id = None
            sim.for_backtest = True
            sim.save()
    create_backtest_sim.short_description = 'Create out of sample sims'

    def export_template(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        sim = get_object_or_404(models.RaceSim, pk=pk)

        task = BackgroundTask()
        task.name = 'Export Sim Template'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = f'sim_template-{sim.race}-{timestamp}.xlsx'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_sim_template.delay(sim.id, result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue while you\'re waiting. A new message will appear here once your export is ready.')

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        sim = get_object_or_404(models.RaceSim, pk=pk)
        tasks.execute_sim.delay(
            sim.id,
            BackgroundTask.objects.create(
                name=f'Simulate {sim.race}',
                user=request.user
            ).id
        )

        messages.add_message(
            request,
            messages.WARNING,
            f'Simulating player outcomes for {sim.race}'
        )

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def export_results(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        sim = get_object_or_404(models.RaceSim, pk=pk)

        task = BackgroundTask()
        task.name = 'Export Sim Results'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file =f'{sim.race} (Sim ID {sim.id}) - {timestamp}.xlsx'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_results.delay(sim.id, result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue while you\'re waiting. A new message will appear here once your export is ready.')

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def export_dk_results(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        sim = get_object_or_404(models.RaceSim, pk=pk)

        task = BackgroundTask()
        task.name = 'Export Sim Results (DK only)'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file =f'{sim.race} (Sim ID {sim.id}) - {timestamp}.xlsx'
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_dk_results.delay(sim.id, result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue while you\'re waiting. A new message will appear here once your export is ready.')

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def simulate_races(self, request, queryset):
        jobs = [
            tasks.execute_sim.si(
                sim.id,
                BackgroundTask.objects.create(
                    name=f'Simulate {sim.race}',
                    user=request.user
                ).id
            ) for sim in queryset
        ]
        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            f'Simulating player outcomes for {queryset.count()} races'
        )

    def export_results_many(self, request, queryset):
        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)

        jobs = [
            tasks.export_results.si(
                sim.id,
                os.path.join(os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username), f'{sim.race} (Sim ID {sim.id}) - {timestamp}.xlsx'),
                '/media/temp/{}/{}'.format(request.user.username, f'{sim.race} (Sim ID {sim.id}) - {timestamp}.xlsx'),
                BackgroundTask.objects.create(
                    name=f'Export FP for {sim.race}',
                    user=request.user
                ).id
            ) for sim in queryset
        ]
        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            f'Export FP outcomes for {queryset.count()} races'
        )
    export_results_many.short_description = 'Export Results for selected sim'

    def calculate_driver_gto(self, request, queryset):
        jobs = [
            tasks.find_driver_gto.si(
                sim.id,
                BackgroundTask.objects.create(
                    name=f'Find driver GTO for {sim}',
                    user=request.user
                ).id
            ) for sim in queryset
        ]
        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            f'Finding driver GTO for {queryset.count()} races'
        )
    calculate_driver_gto.short_description = 'Calculate Driver GTO'

    def rank_lineups(self, request, queryset):
        jobs = [
            tasks.rank_optimal_lineups.si(
                sim.id,
                BackgroundTask.objects.create(
                    name=f'Rank optimal lineups for {sim}',
                    user=request.user
                ).id
            ) for sim in queryset
        ]
        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            f'Ranking optimal lineups.'
        )
    rank_lineups.short_description = 'Rank optimal lineups for selected sims'


@admin.register(models.RaceSimLineup)
class RaceSimLineupAdmin(admin.ModelAdmin):
    list_display = (
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
        'total_salary',
        'median',
        's75',
        's90',
        'rank_median',
        'rank_s75',
        'rank_s90',
        'count'
    )

    search_fields = (
        'player_1__driver__full_name',
        'player_2__driver__full_name',
        'player_3__driver__full_name',
        'player_4__driver__full_name',
        'player_5__driver__full_name',
        'player_6__driver__full_name',
    )

    list_filter = (
        ('sim', RelatedDropdownFilter),
    )


@admin.register(models.SlateBuildConfig)
class ConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'site',
        'randomness',
        'uniques',
        'min_salary',
        'optimize_by_percentile',
        'lineup_multiplier',
        'clean_by_percentile',
    ]

    list_filter = [
        'site',
    ]


@admin.register(models.Slate)
class SlateAdmin(admin.ModelAdmin):
    list_display = (
        'datetime',
        'name',
        'race',
        'site',
        'get_players_link',
        'get_lineups_link',
        'get_builds_link',
        'make_lineups_button',
        'export_button',
    )
    raw_id_fields = (
        'race',
    )
    # list_editable = (
    #     'name',
    #     'site',
    # )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nascar-slate-make-lineups/<int:pk>/', self.make_lineups, name="admin_nascar_slate_make_lineups"),
            path('nascar-slate-export/<int:pk>/', self.export_lineups, name="admin_nascar_slate_export_lineups"),
        ]
        return my_urls + urls

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_slate(request, obj)

    def process_slate(self, request, slate):
        chain(
            tasks.process_slate_players.si(
                slate.id,
                BackgroundTask.objects.create(
                    name='Process slate players',
                    user=request.user
                ).id
            )
        )()

        messages.add_message(
            request,
            messages.WARNING,
            'Your slate is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the slate is ready.')

    def get_players_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/slateplayer/?slate__id={}">Players</a>'.format(obj.id))
        return 'None'
    get_players_link.short_description = 'Players'

    def get_lineups_link(self, obj):
        if obj.possible_lineups.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/slatelineup/?slate__id__exact={}" target="_blank">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Possible Lineups'

    def get_builds_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/slatebuild/?slate__id={}">Builds</a>'.format(obj.id))
        return 'None'
    get_builds_link.short_description = 'Builds'

    def make_lineups(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = models.Slate.objects.get(pk=pk)
        tasks.create_slate_lineups.delay(
            slate.id,
            BackgroundTask.objects.create(
                name='Make all lineups',
                user=request.user
            ).id
        )

        messages.add_message(
            request,
            messages.WARNING,
            f'Making all possible lineups.'
        )

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def export_lineups(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        # Get the scenario to activate
        slate = models.Slate.objects.get(pk=pk)
        task = BackgroundTask()
        task.name = 'Export All Possible Lineups'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = '{}-{}_upload.csv'.format(slate.name, timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        # tasks.export_build_for_upload.delay(build.id, result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your build export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)


@admin.register(models.SlateLineup)
class SlateLineupAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
        'total_salary',
    )

    search_fields = (
        'player_1__slate_player__name',
        'player_2__slate_player__name',
        'player_3__slate_player__name',
        'player_4__slate_player__name',
        'player_5__slate_player__name',
        'player_6__slate_player__name',
    )

    list_filter = (
        'slate',
    )
    raw_id_fields = (
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
    )


@admin.register(models.SlatePlayer)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'salary',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate__name', DropdownFilter),
    )
    raw_id_fields = (
        'driver', 
    )


@admin.register(models.SlateBuild)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    form = forms.SlateBuildForm
    list_display = (
        'slate',
        'sim',
        'build_type',
        'get_projections_link',
        'get_groups_link',
        'get_lineups_link',
        'get_field_lineups_link',
        'get_matchup_lineups_link',
        'build_button',
        'export_button',
    )
    list_filter = (
        ('slate', RelatedDropdownFilter),
        ('sim', RelatedDropdownFilter),
    )
    raw_id_fields = (
        'slate',
        'sim',
    )
    search_fields = ('slate__name',)
    actions = [
        'rank_lineups'
    ]
    inlines = [
        SlateBuildFieldLineupInline
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nascar-slatebuild-build/<int:pk>/', self.build, name="admin_nascar_slatebuild_build"),
            path('nascar-slatebuild-export/<int:pk>/', self.export_for_upload, name="admin_nascar_slatebuild_export"),
        ]
        return my_urls + urls

    # def get_queryset(self, request):
    #     return super().get_queryset(request).filter(user=request.user)

    def get_form(self, request, obj=None, **kwargs):
        AdminForm = super(SlateBuildAdmin, self).get_form(request, obj, **kwargs)

        class AdminFormWithRequest(AdminForm):
            def __new__(cls, *args, **kwargs):
                kwargs['request'] = request
                return AdminForm(*args, **kwargs)

        return AdminFormWithRequest

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_build(request, obj)

    def process_build(self, request, build):
        chain(
            tasks.process_build.si(
                build.id,
                BackgroundTask.objects.create(
                    name='Process Build',
                    user=request.user
                ).id
            )
        )()

        messages.add_message(
            request,
            messages.WARNING,
            'Your build is being initialized. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the slate is ready.')

    def build(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        build = models.SlateBuild.objects.get(pk=pk)

        if build.build_type == 'cash':
            tasks.execute_cash_workflow.delay(
                build.id,
                BackgroundTask.objects.create(
                    name='Run Cash Workflow',
                    user=request.user
                ).id
            )

            messages.add_message(
                request,
                messages.WARNING,
                f'Running Cash Workflow'
            )
        elif build.build_type == 'h2h':
            tasks.execute_h2h_workflow.delay(
                build.id,
                BackgroundTask.objects.create(
                    name='Run H2H Workflow',
                    user=request.user
                ).id
            )

            messages.add_message(
                request,
                messages.WARNING,
                f'Running H2H Workflow'
            )
        elif build.build_type == 'se':
            tasks.execute_se_workflow.delay(
                build.id,
                BackgroundTask.objects.create(
                    name='Run SE Workflow',
                    user=request.user
                ).id
            )

            messages.add_message(
                request,
                messages.WARNING,
                f'Running SE Workflow'
            )
        else:
            messages.add_message(
                request,
                messages.ERRROR,
                f'{build.build_type} is not supported yet'
            )
        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def export_for_upload(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        # Get the scenario to activate
        build = get_object_or_404(models.SlateBuild, pk=pk)
        if build.num_lineups_created() > 0:
            task = BackgroundTask()
            task.name = 'Export Build For Upload'
            task.user = request.user
            task.save()

            now = datetime.datetime.now()
            timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
            result_file = '{}-{}-{}.csv'.format(build.slate.name, build.build_type, timestamp)
            result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
            os.makedirs(result_path, exist_ok=True)
            result_path = os.path.join(result_path, result_file)
            result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

            tasks.export_build_for_upload.delay(build.id, result_path, result_url, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Your build export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
        else:
            self.message_user(request, 'Cannot export lineups for {}. No lineups exist.'.format(str(build)), level=messages.ERROR)

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def get_projections_link(self, obj):
        if obj.projections.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/buildplayerprojection/?build__id__exact={}">Projections</a>'.format(obj.id))
        return 'None'
    get_projections_link.short_description = 'Projections'

    def get_lineups_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nascar/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Lineups'

    def get_field_lineups_link(self, obj):
        if obj.num_field_lineups() > 0:
            return mark_safe('<a href="/admin/nascar/slatebuildfieldlineup/?build__id__exact={}">Field</a>'.format(obj.id))
        return 'None'
    get_field_lineups_link.short_description = 'Field Lineups'

    def get_matchup_lineups_link(self, obj):
        if obj.matchups.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/slatebuildlineupmatchup/?build__id__exact={}">Matchups</a>'.format(obj.id))
        return 'None'
    get_matchup_lineups_link.short_description = 'Matchups'

    def get_groups_link(self, obj):
        return mark_safe('<a href="/admin/nascar/slatebuildgroup/?build__id__exact={}">Groups</a>'.format(obj.id))
    get_groups_link.short_description = 'Groups'

    def rank_lineups(self, request, queryset):
        jobs = [
            tasks.rank_build_lineups.si(
                build.id,
                BackgroundTask.objects.create(
                    name=f'Rank lineups for {build}',
                    user=request.user
                ).id
            ) for build in queryset
        ]
        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            f'Ranking lineups.'
        )
    rank_lineups.short_description = 'Rank lineups for selected build'


@admin.register(models.BuildPlayerProjection)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'slate_player',
        'get_player_salary',
        'starting_position',
        # 'get_salary_value',
        'projection',
        's75',
        'ceiling',
        'in_play',
        'op',
        'gto',
        'get_exposure',
        'min_exposure',
        'max_exposure',
    )
    list_filter = (
        'in_play',
    )
    list_editable = (
        'in_play',
        'op',
        'min_exposure',
        'max_exposure',
    )
    search_fields = [
        'slate_player__name'
    ]


    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     qs = qs.annotate(
    #         exposure=Avg('exposures__exposure'), 
    #     )

    #     return qs

    def get_player_salary(self, obj):
        return f'${obj.salary}'
    get_player_salary.short_description = 'salary'
    get_player_salary.admin_order_field = 'slate_player__salary'

    # def get_salary_value(self, obj):
    #     return round(obj.slate_player.value, 2)
    # get_salary_value.short_description = 'value'

    def get_exposure(self, obj):
        if obj.exposure is None:
            return None
        return '{:.2f}%'.format(float(obj.exposure) * 100.0)
    get_exposure.short_description = 'Exp'
    get_exposure.admin_order_field = 'exposure'


@admin.register(models.SlateBuildGroup)
class SlateBuildGroupAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'min_from_group',
        'max_from_group',
        'num_players',
        'get_players',
        'active',
    )
    raw_id_fields = (
        'build',
    )
    list_editable = (
        'min_from_group',
        'max_from_group',
        'active',
    )
    inlines = [
        SlateBuildGroupPlayerInline
    ]

    def get_players(self, obj):
        return mark_safe('<br />'.join(list(obj.players.all().values_list('player__slate_player__name', flat=True))))
    get_players.short_description = 'players'


@admin.register(models.SlateBuildLineup)
class SlateBuildLineupAdmin(admin.ModelAdmin):
    list_display = (
        'get_lineup',
        'get_salary',
        'median',
        's75',
        's90',
        'get_win_rate',
    )

    search_fields = (
        'lineup__player_1__slate_player__name',
        'lineup__player_2__slate_player__name',
        'lineup__player_3__slate_player__name',
        'lineup__player_4__slate_player__name',
        'lineup__player_5__slate_player__name',
        'lineup__player_6__slate_player__name',
    )

    def get_lineup(self, obj):
        return mark_safe(f'{obj.slate_lineup.player_1}<br />{obj.slate_lineup.player_2}<br />{obj.slate_lineup.player_3}<br />{obj.slate_lineup.player_4}<br />{obj.slate_lineup.player_5}<br />{obj.slate_lineup.player_6}')
    get_lineup.short_description = ''

    def get_salary(self, obj):
        return obj.slate_lineup.total_salary
    get_salary.short_description = 'salary'
    get_salary.admin_order_field = 'slate_lineup__total_salary'

    def get_win_rate(self, obj):
        return '{:.2f}%'.format(obj.win_rate * 100)
    get_win_rate.short_description = 'win %'
    get_win_rate.admin_order_field = 'win_rate'


@admin.register(models.SlateBuildFieldLineup)
class SlateBuildFieldLineupAdmin(admin.ModelAdmin):
    list_display = (
        'opponent_handle',
        'get_lineup',
        'get_salary',
        'median',
        's75',
        's90',
    )

    search_fields = (
        'slate_lineup__player_1__slate_player__name',
        'slate_lineup__player_2__slate_player__name',
        'slate_lineup__player_3__slate_player__name',
        'slate_lineup__player_4__slate_player__name',
        'slate_lineup__player_5__slate_player__name',
        'slate_lineup__player_6__slate_player__name',
    )

    raw_id_fields = (
        'slate_lineup',
        'build',
    )

    def get_lineup(self, obj):
        return mark_safe(f'{obj.slate_lineup.player_1}<br />{obj.slate_lineup.player_2}<br />{obj.slate_lineup.player_3}<br />{obj.slate_lineup.player_4}<br />{obj.slate_lineup.player_5}<br />{obj.slate_lineup.player_6}')
    get_lineup.short_description = ''

    def get_salary(self, obj):
        return obj.slate_lineup.total_salary
    get_salary.short_description = 'salary'
    get_salary.admin_order_field = 'slate_lineup__total_salary'


@admin.register(models.SlateBuildLineupMatchup)
class SlateBuildLineupMatchupAdmin(admin.ModelAdmin):
    list_display = (
        'get_lineup',
        'get_opponent',
        'get_win_rate',
    )

    search_fields = (
        'slate_lineup__player_1__name',
        'slate_lineup__player_2__name',
        'slate_lineup__player_3__name',
        'slate_lineup__player_4__name',
        'slate_lineup__player_5__name',
        'slate_lineup__player_6__name',
    )

    raw_id_fields = (
        'slate_lineup',
        'field_lineup',
        'build',
    )

    def get_lineup(self, obj):
        return mark_safe(f'{obj.slate_lineup.player_1}<br />{obj.slate_lineup.player_2}<br />{obj.slate_lineup.player_3}<br />{obj.slate_lineup.player_4}<br />{obj.slate_lineup.player_5}<br />{obj.slate_lineup.player_6}')
    get_lineup.short_description = ''

    def get_opponent(self, obj):
        return mark_safe(f'{obj.field_lineup.slate_lineup.player_1}<br />{obj.field_lineup.slate_lineup.player_2}<br />{obj.field_lineup.slate_lineup.player_3}<br />{obj.field_lineup.slate_lineup.player_4}<br />{obj.field_lineup.slate_lineup.player_5}<br />{obj.field_lineup.slate_lineup.player_6}')
    get_opponent.short_description = 'vs.'

    def get_win_rate(self, obj):
        return '{:.2f}%'.format(obj.win_rate * 100)
    get_win_rate.short_description = 'win %'
    get_win_rate.admin_order_field = 'win_rate'


@admin.register(models.Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slate',
        'cost',
        'num_entries',
    )

    raw_id_fields = (
        'slate',
        'sim',
    )

    inlines = [
        ContestPrizeInline
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_contest(request, obj)

    def process_contest(self, request, contest):
        tasks.process_contest.delay(
            contest.id,
            BackgroundTask.objects.create(
                name='Processing Contest',
                user=request.user
            ).id
        )
        messages.add_message(
            request,
            messages.WARNING,
            'Your contest is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the contest is ready.')


@admin.register(models.ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'entry_name',
        'contest',
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
    )

    list_filter = [
        ('contest', RelatedDropdownFilter)
    ]

    search_fields = (
        'player_1__driver__full_name',
        'player_2__driver__full_name',
        'player_3__driver__full_name',
        'player_4__driver__full_name',
        'player_5__driver__full_name',
        'player_6__driver__full_name',
        'entry_name',
    )


@admin.register(models.ContestBacktest)
class ContestBacktestAdmin(admin.ModelAdmin):
    list_display = (
        'contest',
        'exclude_entries_by',
        'get_results_link',
        'run_button',
    )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nascar-contest-backtest-run/<int:pk>/', self.run_backtest, name="nascar_admin_backtest_run"),
        ]
        return my_urls + urls

    def get_results_link(self, obj):
        if obj.entry_outcomes.all().count() > 0:
            return mark_safe('<a href="/admin/nascar/contestbacktestentry/?backtest__id={}">Results</a>'.format(obj.id))
        return 'None'
    get_results_link.short_description = 'Results'

    def run_backtest(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.ContestBacktest, pk=pk)
        backtest.entry_outcomes.all().delete()
        
        tasks.start_contest_simulation.delay(
            backtest.id,
            BackgroundTask.objects.create(
                name='Simulate Contest ROI',
                user=request.user
            ).id
        )
        # chain(
        #     tasks.start_contest_simulation.si(backtest.id),
        #     chord([
        #         tasks.simulate_contest_by_iteration.s(backtest.id, i) for i in range(0, 1)
        #     ], tasks.contest_simulation_complete.si(
        #         backtest.id, 
        #         BackgroundTask.objects.create(
        #             name='Simulate Contest ROI',
        #             user=request.user
        #         ).id
        #     ))
        # )()

        messages.add_message(
            request,
            messages.WARNING,
            f'Simulating ROI for {backtest}'
        )

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)


@admin.register(models.ContestBacktestEntry)
class ContestBacktestEntryAdmin(admin.ModelAdmin):
    list_display = (
        'entry',
        'get_amount_won',
        'get_roi',
    )
    raw_id_fields = (
        'backtest',
        'entry',
    )
    search_fields = (
        'entry__entry_name',
    )

    def get_amount_won(self, obj):
        return '${:.2f}'.format(obj.amount_won)
    get_amount_won.short_description = 'amount_won'
    get_amount_won.admin_order_field = 'amount_won'

    def get_roi(self, obj):
        return '{:.2f}%'.format(obj.roi * 100)
    get_roi.short_description = 'roi'
    get_roi.admin_order_field = 'roi'
