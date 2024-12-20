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
from . import models, tasks


# Forms

def groupplayerform_factory(build):
    class GroupPlayerForm(forms.ModelForm):
        m_file = forms.ModelChoiceField(
            queryset=models.BuildPlayerProjection.objects.filter(build=build)
        )
    return GroupPlayerForm


class RaceResultInline(admin.TabularInline):
    model = models.RaceResult
    extra = 20
    fields = (
        'driver',
        'starting_position',
        'finishing_position',
        'laps_led',
        'finishing_status',
    )


class RaceSimDriverInline(admin.TabularInline):
    model = models.RaceSimDriver
    extra = 0
    fields = (
        'driver',
        'constructor',
        'starting_position',
        'dk_position',
        'dk_salary',
        'speed_min',
        'speed_max',
        'incident_rate',
        'pct_laps_led_min',
        'pct_laps_led_max',
        'avg_fp',
        'avg_ll',
        'avg_dk_score',
        'gto',
    )
    read_only_fields = (
        'driver',
        'constructor',
        'avg_fp',
        'avg_ll',
        'avg_dk_score',
    )


class RaceSimLapsLedInline(admin.TabularInline):
    model = models.RaceSimLapsLedProfile
    extra = 0
    fields = (
        'fp_rank',
        'pct_laps_led_min',
        'pct_laps_led_max',
    )


class RaceSimFastestLapsInline(admin.TabularInline):
    model = models.RaceSimFastestLapsProfile
    extra = 0
    fields = (
        'fp_rank',
        'probability',
    )


class RaceSimNumLeadersInline(admin.TabularInline):
    model = models.RaceSimNumLeadersProfile
    extra = 0
    fields = (
        'leader_count',
        'probability',
    )


class SlateBuildGroupPlayerInline(admin.TabularInline):
    model = models.SlateBuildGroupPlayer
    autocomplete_fields = ['player']

    def get_form(self, request, obj=None, **kwargs):
        if obj is not None and obj.build is not None:
            kwargs['form'] = groupplayerform_factory(obj.build)
        return super(SlateBuildGroupPlayerInline, self).get_form(request, obj, **kwargs)


# Admins

@admin.register(models.Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'dk_name',
        'fd_name',
        'f1_name'
    )
    list_editable = (
        'dk_name',
        'fd_name',
        'f1_name'
    )
    search_fields = (
        'dk_name',
        'fd_name',
        'f1_name'
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
            path('f1-alias-choose/<int:pk>/<int:chosen_alias_pk>/', self.choose_alias, name="admin_f1_choose_alias"),
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
            elif missing_alias.site == 'f1':
                alias.f1_name = missing_alias.player_name
            
            alias.save()

            self.message_user(request, 'Alias updated: {}'.format(str(alias)), level=messages.INFO)
        else:
            alias = models.Alias.objects.create(
                dk_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                f1_name=missing_alias.player_name
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
                f1_name=missing_alias.player_name
            )

        self.message_user(request, '{} new aliases created.'.format(count), level=messages.INFO)
        queryset.delete()


@admin.register(models.Constructor)
class ConstructorAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'badge',
        'team',
    )
    search_fields = (
        'full_name',
    )
    list_filter = (
        ('team', RelatedDropdownFilter),
    )


@admin.register(models.Race)
class RaceAdmin(admin.ModelAdmin):
    date_hierarchy = 'race_date'
    
    list_display = (
        'race_name',
        'race_date',
        'scheduled_laps',
    )
    search_fields = (
        'race_name',
    )
    inlines = [
        RaceResultInline,
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
        'run_with_gto',
        'for_backtest',
        'export_template_button',
        'sim_button',
        'export_all_results_button',
        'export_dk_results_button',
        'get_lineups_link',
    )
    list_editable = (
        'iterations',
        'run_with_gto',
    )
    raw_id_fields = (
        'race',
    )
    list_filter = (
        'for_backtest',
    )
    inlines = [
        RaceSimFastestLapsInline,
        RaceSimNumLeadersInline,
        RaceSimLapsLedInline,
        RaceSimDriverInline
    ]
    actions = ['calculate_driver_gto', 'create_backtest_sim']

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
            path('f1-race-template/<int:pk>/', self.export_template, name="admin_f1_slate_template"),
            path('f1-race-simulate/<int:pk>/', self.simulate, name="admin_f1_slate_simulate"),
            path('f1-race-results/<int:pk>/', self.export_results, name="f1_admin_slate_export_results"),
            path('f1-race-dk_results/<int:pk>/', self.export_dk_results, name="f1_admin_slate_export_dk"),
        ]
        return my_urls + urls

    def get_lineups_link(self, obj):
        if obj.sim_lineups.all().count() > 0:
            return mark_safe('<a href="/admin/formula_1/racesimlineup/?sim__id__exact={}" target="_blank">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Optimal Lineups'

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

    def create_backtest_sim(self, request, queryset):
        for sim in queryset:
            sim.id = None
            sim.for_backtest = True
            sim.save()

            self.process_sim(request, sim)

    create_backtest_sim.short_description = 'Create out of sample sims'


@admin.register(models.RaceSimLineup)
class RaceSimLineupAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cpt',
        'flex_1',
        'flex_2',
        'flex_3',
        'flex_4',
        'constructor',
        'total_salary',
        'median',
        's75',
        's90',
        'count',
    )

    search_fields = (
        'cpt__driver__full_name',
        'flex_1__driver__full_name',
        'flex_2__driver__full_name',
        'flex_3__driver__full_name',
        'flex_4__driver__full_name',
        'constructor__constructor__name',
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
        'get_builds_link',
    )
    raw_id_fields = (
        'race',
    )

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
            return mark_safe('<a href="/admin/formula_1/slateplayer/?slate__id={}">Players</a>'.format(obj.id))
        return 'None'
    get_players_link.short_description = 'Players'

    def get_builds_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/formula_1/slatebuild/?slate__id={}">Builds</a>'.format(obj.id))
        return 'None'
    get_builds_link.short_description = 'Builds'


@admin.register(models.SlatePlayer)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'position',
        'salary',
        'fantasy_points',
    )
    search_fields = ('name',)
    list_filter = (
        'position',
        ('slate__name', DropdownFilter),
    )
    raw_id_fields = (
        'driver', 
        'constructor',
    )


@admin.register(models.SlateBuild)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    list_display = (
        'created',
        'slate',
        'sim',
        'used_in_contests',
        'configuration',
        'get_projections_link',
        'get_groups_link',
        'total_lineups',
        'num_lineups_created',
        'get_lineups_link',
        'build_button',
        'export_button',
    )
    list_editable = (
        'used_in_contests',
        'configuration',
        'total_lineups',
    )
    list_filter = (
        ('sim', RelatedDropdownFilter),
    )
    raw_id_fields = (
        'slate',
        'sim',
        'configuration',
    )
    search_fields = ('slate__name',)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('f1-slatebuild-build/<int:pk>/', self.build, name="admin_f1_slatebuild_build"),
            path('f1-slatebuild-export/<int:pk>/', self.export_for_upload, name="admin_f1_slatebuild_export"),
        ]
        return my_urls + urls

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_build(request, obj)

    def process_build(self, request, build):
        tasks.process_build.delay(
            build.id,
            BackgroundTask.objects.create(
                name='Process Build',
                user=request.user
            ).id
        )

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
        build.execute_build(request.user)

        messages.add_message(
            request,
            messages.WARNING,
            f'Building {build.total_lineups} lineups.'
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
            result_file = '{}-{}_upload.csv'.format(build.slate.name, timestamp)
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
            return mark_safe('<a href="/admin/formula_1/buildplayerprojection/?build__id__exact={}">Projections</a>'.format(obj.id))
        return 'None'
    get_projections_link.short_description = 'Projections'

    def get_lineups_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/formula_1/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Lineups'

    def get_groups_link(self, obj):
        return mark_safe('<a href="/admin/formula_1/slatebuildgroup/?build__id__exact={}">Groups</a>'.format(obj.id))
    get_groups_link.short_description = 'Groups'


@admin.register(models.BuildPlayerProjection)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'slate_player',
        'get_position',
        'get_team',
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
        'slate_player__position',
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
    #         position=F('slate_player__position'), 
    #         salary=F('slate_player__salary')
    #     )

    #     return qs

    def get_position(self, obj):
        return f'{obj.slate_player.position}'
    get_position.short_description = 'position'
    get_position.admin_order_field = 'slate_player__position'

    def get_team(self, obj):
        if obj.slate_player.position == 'CNSTR':
            return obj.slate_player.constructor.name
        return f'{obj.slate_player.driver.team.name}'
    get_team.short_description = 'team'

    def get_player_salary(self, obj):
        return f'${obj.slate_player.salary}'
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
        'cpt',
        'flex_1',
        'flex_2',
        'flex_3',
        'flex_4',
        'constructor',
        'total_salary',
        'median',
        's75',
        's90',
        'sort_proj',
        'duplicated'
    )

    search_fields = (
        'cpt__slate_player__name',
        'flex_1__slate_player__name',
        'flex_2__slate_player__name',
        'flex_3__slate_player__name',
        'flex_4__slate_player__name',
        'constructor__slate_player__name',
    )
