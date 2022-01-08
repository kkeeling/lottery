import csv
import datetime
import decimal
import traceback
import math
import numpy
import os

from celery import chord, chain, group

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.core.paginator import Paginator
from django.db.models import Count, Window, F, Case, When
from django.db.models.aggregates import Sum
from django.db.models.expressions import ExpressionWrapper
from django.db.models.fields import FloatField
from django.db.models.functions import Coalesce, PercentRank
from django.shortcuts import redirect, get_object_or_404
from django.urls import path
from django.utils.duration import _get_duration_components
from django.utils.html import mark_safe, format_html
from django import forms

from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from lottery.admin import lottery_admin_site
from configuration.models import BackgroundTask

from fanduel import models as fanduel_models
from yahoo import models as yahoo_models

from . import models
from . import tasks


class NoCountPaginator(Paginator):
    @property
    def count(self):
        return 999999999 # Some arbitrarily large number,
                         # so we can still get our page tab.from django.http import HttpResponse


# Filters

class ProjectionFilter(SimpleListFilter):
    title = 'projection' # or use _('country') for translated title
    parameter_name = 'projection'

    def lookups(self, request, model_admin):
        return (
            (0.9, '0.9 or better'),
            (4.9, '4.9 or better'),
            (7.9, '7.9 or better'),
            (9.9, '9.9 or better'),
            (14.9, '14.9 or better'),
            (15.9, '15.9 or better'),
            (16.9, '16.9 or better'),
            (17.9, '17.9 or better'),
            (18.9, '18.9 or better'),
            (19.9, '19.9 or better'),
            (20.9, '20.9 or better'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(projection__gte=float(self.value()))


# Forms


class ProjectionListForm(forms.ModelForm):
	balanced_projection = forms.DecimalField(widget=forms.TextInput(attrs={'style':'width:50px;'}))
	balanced_value = forms.DecimalField(widget=forms.TextInput(attrs={'style':'width:50px;'}))
	min_exposure = forms.IntegerField(widget=forms.TextInput(attrs={'style':'width:50px;'}))
	max_exposure = forms.IntegerField(widget=forms.TextInput(attrs={'style':'width:50px;'}))


# Inlines


class SlateBuildInline(admin.TabularInline):
    model = models.SlateBuild
    extra = 0
    fields = (
        'created',
        'total_lineups',
        'configuration',
    )
    readonly_fields = (
        'created',
    )


class SlateGameInline(admin.TabularInline):
    model = models.SlateGame
    extra = 0
    fields = (
        'game',
        'get_game_total',
        'zscore',
    )
    raw_id_fields = (
        'game',
    )
    readonly_fields = (
        'zscore',
        'get_game_total',
    )

    def get_game_total(self, obj):
        return obj.game_total()
    get_game_total.short_description = 'Total'


class GameInline(admin.TabularInline):
    model = models.Game
    extra = 0


class SlateBuildGroupPlayerInline(admin.TabularInline):
    model = models.SlateBuildGroupPlayer
    raw_id_fields = ['slate_player']


class ContestPrizeInline(admin.TabularInline):
    model = models.ContestPrize


class SlateProjectionSheetInline(admin.TabularInline):
    model = models.SlateProjectionSheet
    extra = 0


class SlatePlayerOwnershipProjectionSheetInline(admin.TabularInline):
    model = models.SlatePlayerOwnershipProjectionSheet
    extra = 0


# Admins


@admin.register(models.Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = (
        'dk_name',
        'four4four_name',
        'awesemo_name',
        'awesemo_ownership_name',
        'fc_name',
        'tda_name',
        'fd_name',
        'rts_name',
        'etr_name',
        'yahoo_name',
    )
    search_fields = (
        'dk_name',
        'four4four_name',
        'awesemo_name',
        'awesemo_ownership_name',
        'fc_name',
        'tda_name',
        'fd_name',
        'rts_name',
        'etr_name',
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
            path('alias-choose/<int:pk>/<int:chosen_alias_pk>/', self.choose_alias, name="admin_choose_alias"),
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
            elif missing_alias.site == '4for4':
                alias.four4four_name = missing_alias.player_name
            elif missing_alias.site == 'awesemo':
                alias.awesemo_name = missing_alias.player_name
            elif missing_alias.site == 'awesemo_own':
                alias.awesemo_ownership_name = missing_alias.player_name
            elif missing_alias.site == 'etr':
                alias.etr_name = missing_alias.player_name
            elif missing_alias.site == 'tda':
                alias.tda_name = missing_alias.player_name
            elif missing_alias.site == 'rg':
                alias.rg_name = missing_alias.player_name
            elif missing_alias.site == 'fc':
                alias.fc_name = missing_alias.player_name
            elif missing_alias.site == 'rts':
                alias.rts_name = missing_alias.player_name
            
            alias.save()

            self.message_user(request, 'Alias updated: {}'.format(str(alias)), level=messages.INFO)
        else:
            alias = models.Alias.objects.create(
                dk_name=missing_alias.player_name,
                four4four_name=missing_alias.player_name,
                awesemo_name=missing_alias.player_name,
                awesemo_ownership_name=missing_alias.player_name,
                fc_name=missing_alias.player_name,
                tda_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                etr_name=missing_alias.player_name,
                rts_name=missing_alias.player_name,
                rg_name=missing_alias.player_name
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
                four4four_name=missing_alias.player_name,
                awesemo_name=missing_alias.player_name,
                awesemo_ownership_name=missing_alias.player_name,
                fc_name=missing_alias.player_name,
                tda_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                etr_name=missing_alias.player_name,
                rts_name=missing_alias.player_name,
                rg_name=missing_alias.player_name
            )

        self.message_user(request, '{} new aliases created.'.format(count), level=messages.INFO)
        queryset.delete()


@admin.register(models.SheetColumnHeaders)
class SheetColumnHeadersAdmin(admin.ModelAdmin):
    list_display = (
        'projection_site',
        'site',
        'column_player_name',
        'column_team',
        'column_median_projection',
        'column_floor_projection',
        'column_ceiling_projection',
        'column_rush_att_projection',
        'column_rec_projection',
        'column_own_projection',
        'column_ownership',
        'column_score',
    )


@admin.register(models.Slate)
class SlateAdmin(admin.ModelAdmin):
    list_display = (
        'datetime',
        'name',
        'week',
        'is_complete',
        'site',
        'get_players_link',
        'get_contest_link',
        'sim_button',
    )
    list_editable = (
        'is_complete',
    )
    list_filter = (
        'site',        
    )
    actions = [
        'process_slates', 
        'flatten_projections',
        'get_field_lineup_outcomes',
        'export_field',
        'export_player_outcomes',
        'export_game_sims',
    ]
    inlines = (SlateProjectionSheetInline, SlatePlayerOwnershipProjectionSheetInline, SlateGameInline, )
    fields = (
        'datetime',
        'end_datetime',
        'name',
        'week',
        'site',
        'salaries_sheet_type',
        'salaries',
        'is_complete',
        'fc_actuals_sheet',        
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_slate(request, obj)

    def process_slate(self, request, slate):
        if slate.is_complete:
            if slate.fc_actuals_sheet:
                task1 = BackgroundTask()
                task1.name = 'Process Actuals'
                task1.user = request.user
                task1.save()

                jobs = []
                
                if slate.fc_actuals_sheet is not None:
                    jobs.append(tasks.process_actuals_sheet.si(slate.id, task1.id))

                if slate.site == 'fanduel':
                    fanduel_contests = fanduel_models.Contest.objects.filter(slate_week=slate.week.num, slate_year=slate.week.slate_year)

                    if fanduel_contests.count() > 0:
                        jobs.append(tasks.process_actual_ownership.si(
                            slate.id,
                            fanduel_contests[0].id,
                             BackgroundTask.objects.create(
                                name='Process actual ownership',
                                user=request.user
                            ).id
                        ))
                elif slate.site == 'yahoo':
                    yahoo_contests = yahoo_models.Contest.objects.filter(slate_week=slate.week.num, slate_year=slate.week.slate_year)

                    if yahoo_contests.count() > 0:
                        jobs.append(tasks.process_actual_ownership.si(
                            slate.id,
                            yahoo_contests[0].id,
                             BackgroundTask.objects.create(
                                name='Process actual ownership',
                                user=request.user
                            ).id
                        ))

                if len(jobs) > 0:
                    chain(jobs)()

                messages.add_message(
                    request,
                    messages.WARNING,
                    'Processing actuals for {}.'.format(str(slate)))
        else:
            find_games_task = BackgroundTask()
            find_games_task.name = 'Finding Slate Games'
            find_games_task.user = request.user
            find_games_task.save()

            slate_players_task = BackgroundTask()
            slate_players_task.name = 'Process Slate Players'
            slate_players_task.user = request.user
            slate_players_task.save()

            _ = chain(
                tasks.find_slate_games.s(slate.id, find_games_task.id), 
                tasks.process_slate_players.s(slate.id, slate_players_task.id),
                group([
                    tasks.process_projection_sheet.s(s.id, BackgroundTask.objects.create(
                        name=f'Process Projections from {s.projection_site}',
                        user=request.user
                    ).id) for s in slate.projections.all()
                ]),
                tasks.handle_base_projections.s(slate.id, BackgroundTask.objects.create(
                        name='Process Base Projections',
                        user=request.user
                ).id),
                group([
                    tasks.process_ownership_sheet.s(s.id, BackgroundTask.objects.create(
                        name=f'Process Ownership Projections from {s.projection_site}',
                        user=request.user
                    ).id) for s in slate.ownership_projections_sheets.all()
                ]),
                tasks.assign_zscores_to_players.s(slate.id, BackgroundTask.objects.create(
                        name='Assign Z-Scores to Players',
                        user=request.user
                ).id)
            )()

            messages.add_message(
                request,
                messages.WARNING,
                'Your slate is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the slate is ready.')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nfl-sd-slate-simulate/<int:pk>/', self.simulate, name="admin_nfl_sd_slate_simulate"),
        ]
        return my_urls + urls

    def get_contest_link(self, obj):
        if obj.contests.all().count() == 0:
            return None
        return mark_safe('<a href="/admin/nfl/contest/?id__exact={}">{}</a>'.format(obj.contests.all()[0].id, obj.contests.all()[0].name))
    get_contest_link.short_description = 'Contest'

    def get_players_link(self, obj):
        if obj.players.all().count() == 0:
            return None
        return mark_safe('<a href="/admin/nfl/slateplayer/?slate__id__exact={}">Players</a>'.format(obj.id))
    get_players_link.short_description = 'Players'

    def process_slates(self, request, queryset):
        for slate in queryset:
            self.process_slate(request, slate)
    process_slates.short_description = '(Re)Process selected slates'

    def flatten_projections(self, request, queryset):
        jobs = []

        for slate in queryset:
            jobs.append(
                tasks.flatten_base_projections.s(
                    slate.id,
                    BackgroundTask.objects.create(
                        name=f'Flatten projections for {slate}',
                        user=request.user
                    ).id
                )
            )

        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            'Flattening base projections')
    flatten_projections.short_description = 'Flatten base projections for selected slates'

    def find_games(self, request, queryset):
        for slate in queryset:
            if slate.is_main_slate:
                slate.find_games()
    find_games.short_description = 'Find games for selected slates'

    def export_game_sims(self, request, queryset):
        jobs = []

        for slate_game in models.SlateGame.objects.filter(slate__in=queryset):
            result_file = f'{slate_game.slate}-{slate_game.game.away_team} @ {slate_game.game.home_team}.csv'
            result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
            os.makedirs(result_path, exist_ok=True)
            result_path = os.path.join(result_path, result_file)
            result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

            jobs.append(
                tasks.export_game_sim.s(
                    slate_game.id,
                    result_path,
                    result_url,
                    BackgroundTask.objects.create(
                        name=f'Export Simulation for {slate_game}',
                        user=request.user
                    ).id
                )
            )

        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            'Your exports are being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your exports are ready.')
    export_game_sims.short_description = 'Export Game Sims from selected Slates'

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = get_object_or_404(models.Slate, pk=pk)

        group([
            tasks.simulate_game.s(
                slate_game.id,
                BackgroundTask.objects.create(
                    name=f'Simulate {slate_game}',
                    user=request.user
                ).id
            ) for slate_game in slate.games.all()
        ])()

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating player outcomes for {}'.format(str(slate)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def get_field_lineup_outcomes(self, request, queryset):
        jobs = []
        for slate in queryset:
            slate.field_lineups.all().delete()

            if slate.site == 'yahoo':
                contests = yahoo_models.Contest.objects.filter(slate_week=slate.week.num, slate_year=slate.week.slate_year)
                if contests.count() == 0:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        'Cannot race. No contests found for this slate.'
                    )
                    return
                
                contest = contests[0]

                df_field_lineups = contest.get_lineups_as_dataframe()
                for lineup in df_field_lineups.values.tolist(): 
                    jobs.append(
                        tasks.get_field_lineup_outcomes.si(lineup, slate.id)
                    )

                chord(jobs, tasks.get_field_lineup_outcomes_complete.si(
                    BackgroundTask.objects.create(
                        name='Generating outcomes for field lineups',
                        user=request.user
                    ).id)
                )()

                messages.add_message(
                    request,
                    messages.WARNING,
                    f'Generating field outcomes for {slate}'
                )
            else:
                messages.add_message(
                    request,
                    messages.ERROR,
                    f'{slate.site} is not yet supported for races'
                )
    get_field_lineup_outcomes.short_description = 'Generate field outcomes for selected slates'

    def export_player_outcomes(self, request, queryset):
        jobs = []

        for slate in queryset:
            result_file = f'player-outcomes-{slate}.csv'
            result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
            os.makedirs(result_path, exist_ok=True)
            result_path = os.path.join(result_path, result_file)
            result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

            jobs.append(
                tasks.export_player_outcomes.si(
                    list(models.SlatePlayerProjection.objects.filter(slate_player__slate=slate).values_list('id', flat=True)),
                    result_path,
                    result_url,
                    BackgroundTask.objects.create(
                        name=f'Export Player Outcomes for {slate}',
                        user=request.user
                    ).id
                )
            )

        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            'Your exports are being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your exports are ready.')
    export_player_outcomes.short_description = 'Export player outcomes from selected slates'

    def export_field(self, request, queryset):
        jobs = []

        for slate in queryset:
            result_file = f'field-outcomes-{slate}.csv'
            result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
            os.makedirs(result_path, exist_ok=True)
            result_path = os.path.join(result_path, result_file)
            result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

            jobs.append(
                tasks.export_field_outcomes.si(
                    slate.id,
                    result_path,
                    result_url,
                    BackgroundTask.objects.create(
                        name=f'Export Field Outcomes for {slate}',
                        user=request.user
                    ).id
                )
            )

        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            'Your exports are being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your exports are ready.')
    export_field.short_description = 'Export field lineups from selected contest'


@admin.register(models.SlatePlayer)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'team',
        'slate',
        'site_pos',
        'salary',
        'fantasy_points',
        'ownership',
        'slate_game',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate__name', DropdownFilter),
        ('site_pos', DropdownFilter),
        'team')


@admin.register(models.SlatePlayerProjection)
class SlatePlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'zscore',
        'ceiling',
        'floor',
        'stdev',
        'get_ownership_projection',
        'adjusted_opportunity',
        'get_player_value',
        'get_game_total',
        'get_team_total',
        'get_spread',
        'get_actual_score',
        'get_median_sim_score',
        'get_floor_sim_score',
        'get_75th_percentile_sim_score',
        'get_ceiling_sim_score',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate__name', DropdownFilter),
        ('slate_player__slate__site', DropdownFilter),
    )
    raw_id_fields = ['slate_player']
    actions = ['export']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            slate=F('slate_player__slate'), 
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary'),
            player_game=F('slate_player__slate_game')
        )

        return qs

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', ProjectionListForm)
        return super(SlatePlayerProjectionAdmin, self).get_changelist_form(request, **kwargs)

    def get_slate(self, obj):
        return obj.slate_player.slate
    get_slate.short_description = 'Slate'
    get_slate.admin_order_field = 'slate_player__slate__name'

    def get_player_name(self, obj):
        return obj.slate_player.name
    get_player_name.short_description = 'Player'

    def get_player_salary(self, obj):
        return obj.player_salary
    get_player_salary.short_description = 'Sal'
    get_player_salary.admin_order_field = 'player_salary'

    def get_player_position(self, obj):
        return obj.slate_player.site_pos
    get_player_position.short_description = 'Pos'
    get_player_position.admin_order_field = 'slate_player__site_pos'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.slate_game
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__slate_game'

    def get_game_total(self, obj):
        return obj.game_total
    get_game_total.short_description = 'GT'

    def get_team_total(self, obj):
        return obj.team_total
    get_team_total.short_description = 'TT'

    def get_spread(self, obj):
        return obj.spread
    get_spread.short_description = 'SP'

    def get_ownership_projection(self, obj):
        return '{:.1f}'.format(round(float(obj.ownership_projection) * 100.0, 2))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'ownership_orjection'

    def get_player_value(self, obj):
        return '{:.2f}'.format(float(obj.value))
    get_player_value.short_description = 'Val'
    get_player_value.admin_order_field = 'value'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

    def get_median_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return numpy.median(obj.sim_scores)
        return None
    get_median_sim_score.short_description = 'sMU'

    def get_floor_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(10))
        return None
    get_floor_sim_score.short_description = 'sFLR'

    def get_75th_percentile_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(75))
        return None
    get_75th_percentile_sim_score.short_description = 's75'

    def get_ceiling_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(90))
        return None
    get_ceiling_sim_score.short_description = 'sCEIL'

    def export(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Projections'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Projections Export {}.csv'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_projections.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export.short_description = 'Export selected player projections'


@admin.register(models.SlatePlayerRawProjection)
class SlatePlayerRawProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'ceiling',
        'floor',
        'stdev',
        'get_ownership_projection',
        'adjusted_opportunity',
        'get_player_value',
        'get_game_total',
        'get_team_total',
        'get_spread',
        'get_actual_score',
        'get_median_sim_score',
        'get_floor_sim_score',
        'get_75th_percentile_sim_score',
        'get_ceiling_sim_score',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate__name', DropdownFilter),
        ('slate_player__slate__site', DropdownFilter),
    )
    raw_id_fields = ['slate_player']
    actions = ['export']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            slate=F('slate_player__slate'), 
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary'),
            player_game=F('slate_player__slate_game')
        )

        return qs

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', ProjectionListForm)
        return super(SlatePlayerProjectionAdmin, self).get_changelist_form(request, **kwargs)

    def get_slate(self, obj):
        return obj.slate_player.slate
    get_slate.short_description = 'Slate'
    get_slate.admin_order_field = 'slate_player__slate__name'

    def get_player_name(self, obj):
        return obj.slate_player.name
    get_player_name.short_description = 'Player'

    def get_player_salary(self, obj):
        return obj.player_salary
    get_player_salary.short_description = 'Sal'
    get_player_salary.admin_order_field = 'player_salary'

    def get_player_position(self, obj):
        return obj.slate_player.site_pos
    get_player_position.short_description = 'Pos'
    get_player_position.admin_order_field = 'slate_player__site_pos'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.slate_game
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__slate_game'

    def get_game_total(self, obj):
        return obj.game_total
    get_game_total.short_description = 'GT'

    def get_team_total(self, obj):
        return obj.team_total
    get_team_total.short_description = 'TT'

    def get_spread(self, obj):
        return obj.spread
    get_spread.short_description = 'SP'

    def get_ownership_projection(self, obj):
        return '{:.1f}'.format(round(float(obj.ownership_projection) * 100.0, 2))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'ownership_orjection'

    def get_player_value(self, obj):
        return '{:.2f}'.format(float(obj.value))
    get_player_value.short_description = 'Val'
    get_player_value.admin_order_field = 'value'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

    def get_median_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return numpy.median(obj.sim_scores)
        return None
    get_median_sim_score.short_description = 'sMU'

    def get_floor_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(10))
        return None
    get_floor_sim_score.short_description = 'sFLR'

    def get_75th_percentile_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(75))
        return None
    get_75th_percentile_sim_score.short_description = 's75'

    def get_ceiling_sim_score(self, obj):
        if obj.sim_scores and len(obj.sim_scores) > 0:
            return '{:.2f}'.format(obj.get_percentile_sim_score(90))
        return None
    get_ceiling_sim_score.short_description = 'sCEIL'

    def export(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Projections'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Projections Export {}.csv'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_projections.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export.short_description = 'Export selected player projections'


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
        return mark_safe('<br />'.join(list(obj.players.all().values_list('slate_player__name', flat=True))))
    get_players.short_description = 'players'


@admin.register(models.SlateBuildLineup)
class SlateBuildLineupAdmin(admin.ModelAdmin):
    # list_per_page = 10
    # paginator = NoCountPaginator
    list_display = (
        'order_number',
        'expected_lineup_order',
        'get_cpt',
        'get_flex1',
        'get_flex2',
        'get_flex3',
        'get_flex4',
        'get_flex5',
        'salary',
        'projection',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
        'get_roi',
        'get_actual',
    )

    search_fields = (
        'cpt__slate_player__name',
        'flex1__slate_player__name',
        'flex2__slate_player__name',
        'flex3__slate_player__name',
        'flex4__slate_player__name',
        'flex5__slate_player__name',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            actual_coalesced=Coalesce('actual', 0)
        )

        return qs

    def get_cpt(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.cpt.get_team_color(), obj.cpt))
    get_cpt.short_description = 'CPT'

    def get_flex1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex1.get_team_color(), obj.flex1))
    get_flex1.short_description = 'Flex'

    def get_flex2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex2.get_team_color(), obj.flex2))
    get_flex2.short_description = 'Flex'

    def get_flex3(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex3.get_team_color(), obj.flex3))
    get_flex3.short_description = 'Flex'

    def get_flex4(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex4.get_team_color(), obj.flex4))
    get_flex4.short_description = 'Flex'

    def get_flex5(self, obj):
        if obj.flex5 is None:
            return None
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex5.get_team_color(), obj.flex5))
    get_flex5.short_description = 'Flex'

    def get_roi(self, obj):
        if obj.roi is None:
            return None
        return '{:.2f}%'.format(obj.roi * 100)
    get_roi.short_description = 'roi'
    get_roi.admin_order_field = 'roi'

    def get_actual(self, obj):
        return obj.actual
    get_actual.short_description = 'Actual'
    get_actual.admin_order_field = 'actual_coalesced'

    def get_median_score(self, obj):
        return '{:.2f}'.format(obj.median)
    get_median_score.short_description = 'mu'
    get_median_score.admin_order_field = 'median'

    def get_75th_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s75)
    get_75th_percentile_score.short_description = 's75'
    get_75th_percentile_score.admin_order_field = 's75'

    def get_ceiling_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s90)
    get_ceiling_percentile_score.short_description = 'ceil'
    get_ceiling_percentile_score.admin_order_field = 's90'


@admin.register(models.SlateBuildOptimalLineup)
class SlateBuildOptimalLineupAdmin(admin.ModelAdmin):
    # list_per_page = 10
    # paginator = NoCountPaginator
    list_display = (
        'get_cpt',
        'get_flex1',
        'get_flex2',
        'get_flex3',
        'get_flex4',
        'get_flex5',
        'salary',
        'projection',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
        'get_roi',
        'get_actual',
    )

    search_fields = (
        'cpt__slate_player__name',
        'flex1__slate_player__name',
        'flex2__slate_player__name',
        'flex3__slate_player__name',
        'flex4__slate_player__name',
        'flex5__slate_player__name',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            actual_coalesced=Coalesce('actual', 0)
        )

        return qs

    def get_cpt(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.cpt.get_team_color(), obj.cpt))
    get_cpt.short_description = 'CPT'

    def get_flex1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex1.get_team_color(), obj.flex1))
    get_flex1.short_description = 'Flex'

    def get_flex2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex2.get_team_color(), obj.flex2))
    get_flex2.short_description = 'Flex'

    def get_flex3(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex3.get_team_color(), obj.flex3))
    get_flex3.short_description = 'Flex'

    def get_flex4(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex4.get_team_color(), obj.flex4))
    get_flex4.short_description = 'Flex'

    def get_flex5(self, obj):
        if obj.flex5 is None:
            return None
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex5.get_team_color(), obj.flex5))
    get_flex5.short_description = 'Flex'

    def get_roi(self, obj):
        if obj.roi is None:
            return None
        return '{:.2f}%'.format(obj.roi * 100)
    get_roi.short_description = 'roi'
    get_roi.admin_order_field = 'roi'

    def get_actual(self, obj):
        return obj.actual
    get_actual.short_description = 'Actual'
    get_actual.admin_order_field = 'actual_coalesced'

    def get_median_score(self, obj):
        return '{:.2f}'.format(obj.median)
    get_median_score.short_description = 'mu'
    get_median_score.admin_order_field = 'median'

    def get_75th_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s75)
    get_75th_percentile_score.short_description = 's75'
    get_75th_percentile_score.admin_order_field = 's75'

    def get_ceiling_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s90)
    get_ceiling_percentile_score.short_description = 'ceil'
    get_ceiling_percentile_score.admin_order_field = 's90'


@admin.register(models.SlateFieldLineup)
class SlateFieldLineupAdmin(admin.ModelAdmin):
    # list_per_page = 10
    # paginator = NoCountPaginator
    list_display = (
        'get_cpt',
        'get_flex1',
        'get_flex2',
        'get_flex3',
        'get_flex4',
        'get_flex5',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
        'get_roi',
        'get_actual',
    )

    search_fields = (
        'cpt__slate_player__name',
        'flex1__slate_player__name',
        'flex2__slate_player__name',
        'flex3__slate_player__name',
        'flex4__slate_player__name',
        'flex5__slate_player__name',
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            actual_coalesced=Coalesce('actual', 0)
        )

        return qs

    def get_cpt(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.cpt.get_team_color(), obj.cpt))
    get_cpt.short_description = 'CPT'

    def get_flex1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex1.get_team_color(), obj.flex1))
    get_flex1.short_description = 'Flex'

    def get_flex2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex2.get_team_color(), obj.flex2))
    get_flex2.short_description = 'Flex'

    def get_flex3(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex3.get_team_color(), obj.flex3))
    get_flex3.short_description = 'Flex'

    def get_flex4(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex4.get_team_color(), obj.flex4))
    get_flex4.short_description = 'Flex'

    def get_flex5(self, obj):
        if obj.flex5 is None:
            return None
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex5.get_team_color(), obj.flex5))
    get_flex5.short_description = 'Flex'

    def get_roi(self, obj):
        if obj.roi is None:
            return None
        return '{:.2f}%'.format(obj.roi * 100)
    get_roi.short_description = 'roi'
    get_roi.admin_order_field = 'roi'

    def get_actual(self, obj):
        return obj.actual
    get_actual.short_description = 'Actual'
    get_actual.admin_order_field = 'actual_coalesced'

    def get_median_score(self, obj):
        return '{:.2f}'.format(obj.median)
    get_median_score.short_description = 'mu'
    get_median_score.admin_order_field = 'median'

    def get_75th_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s75)
    get_75th_percentile_score.short_description = 's75'
    get_75th_percentile_score.admin_order_field = 's75'

    def get_ceiling_percentile_score(self, obj):
        return '{:.2f}'.format(obj.s90)
    get_ceiling_percentile_score.short_description = 'ceil'
    get_ceiling_percentile_score.admin_order_field = 's90'


@admin.register(models.SlateBuild)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    list_per_page = 25
    list_display = (
        'id',
        'view_page_button',
        'prepare_projections_button',
        'flatten_exposure_button',
        'build_button',
        'export_button',
        'slate',
        'used_in_contests',
        'configuration',
        'in_play_criteria',
        'get_projections_ready',
        'get_construction_ready',
        'get_ready',
        'get_pct_complete',
        'get_optimal_pct_complete',
        'total_lineups',
        'num_lineups_created',
        'total_cashes',
        'get_pct_one_pct',
        'get_pct_half_pct',
        'top_score',
        'get_el',
        'get_great_score',
        'great_build',
        'get_bink_score',
        'binked', 
        'total_optimals',
        'top_optimal_score',
        'get_links',
        'get_exposures_links',
        'status',
        'get_elapsed_time',
        'get_backtest',
        'error_message',
    )
    list_editable = (
        'used_in_contests',
        'total_lineups',
    )
    list_filter = (
        ('configuration', RelatedDropdownFilter),
        ('slate__name', DropdownFilter),
        ('slate__week', RelatedDropdownFilter),
        'slate__site',
        'used_in_contests',
        'great_build',
    )
    raw_id_fields = [
        'slate',
        'configuration',
        'in_play_criteria',
    ]
    search_fields = ('slate__name',)
    actions = [
        'reset',
        'clean_lineups',
        'find_expected_lineup_order',
        'export_lineups', 
        'export_optimals',
        'get_actual_scores', 
        'race_build',
        'find_optimal_lineups',
        'duplicate_builds', 
        'clear_data'
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nfl_sd-slatebuild-build/<int:pk>/', self.build, name="nfl_sd_admin_slatebuild_build"),
            path('nfl_sd-slatebuild-export/<int:pk>/', self.export_for_upload, name="nfl_sd_admin_slatebuild_export"),
            path('nfl_sd-slatebuild-prepare-projections/<int:pk>/', self.prepare_projections, name="nfl_sd_admin_slatebuild_prepare_projections"),
            path('nfl_sd-slatebuild-prepare-construction/<int:pk>/', self.prepare_construction, name="nfl_sd_admin_slatebuild_prepare_construction"),
            path('nfl_sd-slatebuild-flatten_exposures/<int:pk>/', self.flatten_exposures, name="nfl_sd_admin_slatebuild_flatten_exposure"),
        ]
        return my_urls + urls
    
    def export_button_field(self, obj):
        return format_html(
            "<button onclick='doSomething({})' style='width: 58px; margin: auto; color: #ffffff; background-color: #4fb2d3; font-weight: bold;'>Export</button>", 
            obj.id
        )
    export_button_field.short_description = ''

    def get_backtest(self, obj):
        if obj.backtest is None:
            return None
        return obj.backtest.backtest.name
    get_backtest.short_description = 'Backtest'

    def get_ready(self, obj):
        return obj.ready
    get_ready.short_description = 'GO'
    get_ready.boolean = True

    def get_projections_ready(self, obj):
        return obj.projections_ready
    get_projections_ready.short_description = 'PR'
    get_projections_ready.boolean = True

    def get_construction_ready(self, obj):
        return obj.construction_ready
    get_construction_ready.short_description = 'CR'
    get_construction_ready.boolean = True

    def get_pct_one_pct(self, obj):
        if obj.total_one_pct is None or obj.total_lineups == 0:
            return 0
        return '{:.2f}'.format(obj.total_one_pct/obj.total_lineups * 100)
    get_pct_one_pct.short_description = '1%'
    get_pct_one_pct.admin_order_field = 'total_one_pct'

    def get_pct_half_pct(self, obj):
        if obj.total_half_pct is None or obj.total_lineups == 0:
            return 0
        return '{:.2f}'.format(obj.total_half_pct/obj.total_lineups * 100)
    get_pct_half_pct.short_description = '0.5%'
    get_pct_half_pct.admin_order_field = 'total_half_pct'

    def get_great_score(self, obj):
        if obj.slate.contests.all().count() > 0:
            return obj.slate.contests.all()[0].great_score
        return None
    get_great_score.short_description = 'gs'

    def get_bink_score(self, obj):
        if obj.slate.contests.all().count() > 0:
            return obj.slate.contests.all()[0].winning_score
        return None
    get_bink_score.short_description = 'milly'

    def did_get_great_score(self, obj):
        great_score = self.get_great_score(obj)
        if great_score is None or obj.top_score is None:
            return False
        return obj.top_score >= great_score
    did_get_great_score.boolean = True
    did_get_great_score.short_description = 'gb'

    def get_links(self, obj):
        html = ''
        if obj.num_stacks_created() > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildstack/?build__id__exact={}">Stacks</a>'.format(obj.id)
        if obj.num_groups_created() > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildgroup/?build__id__exact={}">Groups</a>'.format(obj.id)
        if obj.num_lineups_created() > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id)
        if obj.num_actuals_created() > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildactualslineup/?build__id__exact={}">Optimals</a>'.format(obj.id)

        return mark_safe(html)
    get_links.short_description = 'Links'

    def get_exposures_links(self, obj):
        if obj.num_lineups_created() > 0:
            html = ''
            html += '<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=QB">QB</a>'.format(obj.id)
            html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=RB">RB</a>'.format(obj.id)
            html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=WR">WR</a>'.format(obj.id)
            html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=TE">TE</a>'.format(obj.id)

            if obj.slate.site == 'fanduel':
                html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=D">DST</a>'.format(obj.id)
            elif obj.slate.site == 'draftkings':
                html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=DST">DST</a>'.format(obj.id)

            return mark_safe(html)
    get_exposures_links.short_description = 'Exp'

    def get_el(self, obj):
        if obj.total_cashes == None:
            return None
        lineups = obj.lineups.all().order_by('-actual')
        return lineups[0].order_number if lineups.count() > 0 else None
    get_el.short_description = 'EL'

    def get_elapsed_time(self, obj):
        _, _, minutes, seconds, _ = _get_duration_components(obj.elapsed_time)
        return '{:02d}:{:02d}'.format(minutes, seconds)
    get_elapsed_time.short_description = 'Time'
    get_elapsed_time.admin_order_field = 'elapsed_time'

    def get_pct_complete(self, obj):
        return '{:.2f}%'.format(float(obj.pct_complete) * 100.0)
    get_pct_complete.short_description = 'prog'
    get_pct_complete.admin_order_field = 'pct_complete'

    def get_optimal_pct_complete(self, obj):
        return '{:.2f}%'.format(float(obj.optimals_pct_complete) * 100.0)
    get_optimal_pct_complete.short_description = 'o prog'
    get_optimal_pct_complete.admin_order_field = 'optimals_pct_complete'

    def reset(self, request, queryset):
        for build in queryset:
            build.reset()
            messages.success(request, 'Reset {}.'.format(build))
    reset.short_description = 'Reset selected builds'

    def prepare_projections(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        task = BackgroundTask()
        task.name = 'Prepare Projections'
        task.user = request.user
        task.save()

        build = models.SlateBuild.objects.get(pk=pk)
        tasks.prepare_projections_for_build.delay(build.id, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Preparing projections for {}. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once they are ready.'.format(str(build)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def prepare_construction(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        task = BackgroundTask()
        task.name = 'Prepare Construction'
        task.user = request.user
        task.save()

        build = models.SlateBuild.objects.get(pk=pk)
        build.construction_ready = False
        build.save()

        build.groups.all().delete()
        build.stacks.all().delete()

        # get all qbs in play
        qbs = build.projections.filter(slate_player__site_pos='QB', in_play=True)
        total_qb_projection = qbs.aggregate(total_projection=Sum('projection')).get('total_projection')
        
        # for each qb, create all possible stacking configurations

        chord([
            tasks.create_groups_for_build.s(
                build.id, 
                BackgroundTask.objects.create(
                    name='Create Groups',
                    user=request.user
                ).id
            ),
            group([
                tasks.create_stacks_for_qb.s(build.id, qb.id, total_qb_projection) for qb in qbs
            ])
        ], tasks.prepare_construction_complete.s(build.id, task.id))()

        messages.add_message(
            request,
            messages.WARNING,
            'Preparing stacks and groups for {}. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once they are ready.'.format(str(build)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def flatten_exposures(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        task = BackgroundTask()
        task.name = 'Flatten Exposures'
        task.user = request.user
        task.save()

        build = models.SlateBuild.objects.get(pk=pk)
        tasks.flatten_exposure.delay(build.id, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Flattening exposure for {}. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once they are ready.'.format(str(build)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def get_target_score(self, request, queryset):
        for build in queryset:
            tasks.get_target_score.delay(build.id)
            messages.success(request, 'Getting target score for {}. Refresh this page to check progress.'.format(build))
    get_target_score.short_description = 'Get target score for selected builds'

    def build(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        build = models.SlateBuild.objects.get(pk=pk)
        build.execute_build(request.user)
        # tasks.execute_build.delay(build.id, request.user.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Building {} lineups from {} unique stacks. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once they are ready.'.format(build.total_lineups, build.stacks.filter(count__gt=0).count()))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def export_lineups(self, request, queryset):
        if queryset.count() > 1:
            return
        
        build = queryset[0]

        task = BackgroundTask()
        task.name = 'Export Lineups for Analysis'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Lineups Export {}.xlsx'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_lineups_for_analysis.delay(list(build.lineups.all().values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export_lineups.short_description = 'Export lineups for selected builds'            

    def export_optimals(self, request, queryset):
        if queryset.count() > 1:
            return
        
        build = queryset[0]

        task = BackgroundTask()
        task.name = 'Export Optimals'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Optimals Export {}.xlsx'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_lineups_for_analysis.delay(list(build.actuals.all().values_list('id', flat=True)), result_path, result_url, task.id, True)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export_optimals.short_description = 'Export optimals for selected builds'

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

    def analyze_lineups(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Analyze Lineups'
        task.user = request.user
        task.save()

        models.SlateBuildLineup.objects.filter(
            build__in=queryset
        ).update(ev=0, mean=0, std=0, sim_rating=0, s75=0, s90=0)
        
        group([
            tasks.analyze_lineups_for_build.s(build.id, task.id, False) for build in queryset
        ])()

        messages.add_message(
            request,
            messages.WARNING,
            'Analyzing lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')


        # for build in queryset:
        #     build_lineups = build.lineups.all().order_by('id')
        #     build_lineups.update(ev=0, mean=0, std=0, sim_rating=0)
        #     contest = build.slate.contests.get(use_for_sims=True)

        #     if settings.DEBUG:
        #         num_outcomes = 100
        #     else:
        #         num_outcomes = 10000

        #     lineup_limit = 100
        #     lineup_pages = math.ceil(build_lineups.count()/lineup_limit)

        #     limit = 50  # sim columns per call
        #     pages = math.ceil(num_outcomes/limit)  # number of calls to make

        #     for lineup_page in range(0, lineup_pages):
        #         lineup_min = lineup_page * lineup_limit
        #         lineup_max = lineup_min + lineup_limit
        #         lineups = build_lineups[lineup_min:lineup_max]

        #         chord([tasks.analyze_lineup_outcomes.s(
        #             build.id,
        #             contest.id,
        #             list(lineups.values_list('id', flat=True)),
        #             col_count * limit + 3,  # index min
        #             (col_count * limit + 3) + limit,  # index max
        #             False
        #         ) for col_count in range(0, pages)], tasks.combine_lineup_outcomes.s(build.id, list(lineups.values_list('id', flat=True)), False))()

            # messages.add_message(
            #     request,
            #     messages.WARNING,
            #     'Analyzing lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    analyze_lineups.short_description = 'Analyze lineups for selected builds'

    def rate_lineups(self, request, queryset):
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Rate Lineups'
            task.user = request.user
            task.save()

            tasks.rate_lineups.delay(build.id, task.id, False)

            messages.add_message(
                request,
                messages.WARNING,
                'Rating lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    rate_lineups.short_description = 'Rate lineups for selected builds'

    def clean_lineups(self, request, queryset):
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Clean Lineups'
            task.user = request.user
            task.save()

            tasks.clean_lineups.delay(build.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Cleaning lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    clean_lineups.short_description = 'Clean lineups for selected builds'

    def find_expected_lineup_order(self, request, queryset):
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Order Lineups'
            task.user = request.user
            task.save()

            tasks.find_expected_lineup_order.delay(build.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Ordering lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    find_expected_lineup_order.short_description = 'Order lineups for selected builds'

    def analyze_optimals(self, request, queryset):
        for build in queryset:
            # task = BackgroundTask()
            # task.name = 'Analyze Optimals'
            # task.user = request.user
            # task.save()

            # tasks.analyze_optimals.delay(build.id, task.id)

            optimal_lineups = build.actuals.all().order_by('id')
            optimal_lineups.update(ev=0, mean=0, std=0, sim_rating=0)
            contest = build.slate.contests.get(use_for_sims=True)

            if settings.DEBUG:
                num_outcomes = 100
            else:
                num_outcomes = 10000

            lineup_limit = 100
            lineup_pages = math.ceil(optimal_lineups.count()/lineup_limit)

            limit = 50  # sim columns per call
            pages = math.ceil(num_outcomes/limit)  # number of calls to make

            for lineup_page in range(0, lineup_pages):
                lineup_min = lineup_page * lineup_limit
                lineup_max = lineup_min + lineup_limit
                lineups = optimal_lineups[lineup_min:lineup_max]

                chord([tasks.analyze_lineup_outcomes.s(
                    build.id,
                    contest.id,
                    list(lineups.values_list('id', flat=True)),
                    col_count * limit + 3,  # index min
                    (col_count * limit + 3) + limit,  # index max
                    True
                ) for col_count in range(0, pages)], tasks.combine_lineup_outcomes.s(build.id, list(lineups.values_list('id', flat=True)), True))()

            messages.add_message(
                request,
                messages.WARNING,
                'Analyzing optimals. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    analyze_optimals.short_description = 'Analyze optimals for selected builds'

    def rate_optimals(self, request, queryset):
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Rate Optimals'
            task.user = request.user
            task.save()

            tasks.rate_lineups.delay(build.id, task.id, True)

            messages.add_message(
                request,
                messages.WARNING,
                'Rating optimals. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    rate_optimals.short_description = 'Rate optimals for selected builds'

    def get_actual_scores(self, request, queryset):
        for build in queryset:
            build_lineups = list(build.lineups.all().order_by('id').values_list('id', flat=True))
            lineup_limit = 100
            lineup_pages = math.ceil(len(build_lineups)/lineup_limit)

            stacks = build.stacks.all().values_list('id', flat=True)
            stack_limit = 100
            stack_pages = math.ceil(len(stacks)/stack_limit)

            chord([
                group([
                    group([
                        tasks.calculate_actuals_for_stacks.s(
                            list(stacks[(stack_page * stack_limit):(stack_page * stack_limit) + stack_limit])
                        ) for stack_page in range(0, stack_pages)
                    ]),
                    group([
                        tasks.calculate_actuals_for_lineups.s(
                            list(build_lineups[(lineup_page * lineup_limit):(lineup_page * lineup_limit) + lineup_limit])
                        ) for lineup_page in range(0, lineup_pages)
                    ])
                ])
            ], tasks.calculate_actuals_for_build.si(
                build.id,
                BackgroundTask.objects.create(
                    name='Calculate Actual Build Metrics',
                    user=request.user
                ).id
            ))()

            messages.add_message(
                request,
                messages.WARNING,
                'Calculating actual scores.')
    get_actual_scores.short_description = 'Get actual scores for selected builds'

    def race_build(self, request, queryset):
        group([
            tasks.race_lineups_in_build.s(
                build.id,
                BackgroundTask.objects.create(
                    name='Race lineups',
                    user=request.user
                ).id
            ) for build in queryset
        ])()

        messages.add_message(
            request,
            messages.WARNING,
            'Racing lineups.')
    race_build.short_description = 'Race lineups for selected builds'

    def duplicate_builds(self, request, queryset):
        for build in queryset:
            new_build = models.SlateBuild.objects.create(
                slate=build.slate,
                backtest=None,
                configuration=build.configuration,
                in_play_criteria=build.in_play_criteria,
                lineup_construction=build.lineup_construction,
                stack_construction=build.stack_construction,
                stack_cutoff=build.stack_cutoff,
                lineup_start_number=build.lineup_start_number,
                total_lineups=build.total_lineups,
                notes=build.notes,
                target_score=build.target_score
            )

            for proj in build.projections.all():
                proj.id = None
                proj.build = new_build
                proj.save()

            for stack in build.stacks.all():
                stack.id = None
                stack.build = new_build
                stack.save()

            for group in build.groups.all():
                old_group_id = group.id

                group.id = None
                group.build = new_build
                group.save()

                for p in models.SlateBuildGroupPlayer.objects.filter(group__id=old_group_id):
                    models.SlateBuildGroupPlayer.objects.create(
                        group=group,
                        slate_player=p.slate_player
                    )
    duplicate_builds.short_description = 'Duplicate selected builds'

    def find_optimal_lineups(self, request, queryset):
        for build in queryset:
            build.build_optimals()
            messages.success(request, 'Building optimals for {}. Refresh page to check progress'.format(build))
    find_optimal_lineups.short_description = 'Generate optimal lineups for selected builds'


@admin.register(models.BuildPlayerProjection)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'get_player_zscore',
        'get_ceiling',
        'get_player_ceiling_zscore',
        'get_4for4_proj',
        'get_awesemo_proj',
        'get_etr_proj',
        'get_tda_proj',
        'get_exposure',
        'get_ownership_projection',
        'get_ss_ownership_projection',
        'get_rg_ownership_projection',
        'get_player_ao',
        'get_player_ao_zscore',
        'value',
        'balanced_projection',
        'balanced_value',
        'get_game_total',
        'get_team_total',
        'get_spread',
        'in_play',
        'locked',
        'min_exposure',
        'max_exposure',
        'get_actual_score',
        'get_actual_ownership'
    )
    list_editable = (
        'in_play',
        'balanced_projection',
        'balanced_value',
        'min_exposure',
        'max_exposure',
        'locked',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate__name', DropdownFilter),
        ProjectionFilter,
        'in_play',
        'slate_player__slate__site',
    )
    raw_id_fields = ['slate_player']
    actions = [
    ]
    change_list_template = 'admin/nfl/build_player_projection_changelist.html'

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('slate_player__projection')
        qs = qs.annotate(
            slate=F('slate_player__slate'), 
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary'),
            actual_own=F('slate_player__ownership'),       
        )

        return qs

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', ProjectionListForm)
        return super(BuildPlayerProjectionAdmin, self).get_changelist_form(request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context,)

        build_id = request.GET.get('build_id', None)
        if build_id:
            if hasattr(response, 'context_data'):
                response.context_data['build'] = models.SlateBuild.objects.get(pk=build_id)

        return response

    def get_slate(self, obj):
        return obj.slate
    get_slate.short_description = 'Slate'
    get_slate.admin_order_field = 'slate__name'

    def get_player_name(self, obj):
        return obj.slate_player.name
    get_player_name.short_description = 'Player'

    def get_player_salary(self, obj):
        return obj.player_salary
    get_player_salary.short_description = 'Sal'
    get_player_salary.admin_order_field = 'player_salary'

    def get_player_position(self, obj):
        return obj.site_pos
    get_player_position.short_description = 'Pos'
    get_player_position.admin_order_field = 'site_pos'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.slate_game
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__slate_game'

    def get_player_zscore(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.zscore is None:
            return None
        return '{:.2f}'.format(proj.zscore)
    get_player_zscore.short_description = 'z'
    get_player_zscore.admin_order_field = 'slate_player__projection__zscore'

    def get_ceiling(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ceiling is None:
            return None
        return '{:.2f}'.format(proj.ceiling)
    get_ceiling.short_description = 'ceil'
    get_ceiling.admin_order_field = 'slate_player__projection__ceiling'

    def get_player_ceiling_zscore(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ceiling_zscore is None:
            return None
        return '{:.2f}'.format(proj.ceiling_zscore)
    get_player_ceiling_zscore.short_description = 'cz'
    get_player_ceiling_zscore.admin_order_field = 'slate_player__projection__ceiling_zscore'

    def get_player_ao(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ao_zscore is None:
            return None
        return '{:.2f}'.format(proj.adjusted_opportunity)
    get_player_ao.short_description = 'ao'
    get_player_ao.admin_order_field = 'slate_player__projection__adjusted_opportunity'

    def get_player_ao_zscore(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ao_zscore is None:
            return None
        return '{:.2f}'.format(proj.ao_zscore)
    get_player_ao_zscore.short_description = 'ao_z'
    get_player_ao_zscore.admin_order_field = 'slate_player__projection__ao_zscore'

    def get_game_total(self, obj):
        return obj.game_total
    get_game_total.short_description = 'GT'

    def get_team_total(self, obj):
        return obj.team_total
    get_team_total.short_description = 'TT'

    def get_spread(self, obj):
        return obj.spread
    get_spread.short_description = 'SP'

    def get_4for4_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='4for4')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_4for4_proj.short_description = '444'

    def get_awesemo_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='awesemo')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_awesemo_proj.short_description = 'A'

    def get_etr_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='etr')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_etr_proj.short_description = 'ETR'

    def get_tda_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='tda')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_tda_proj.short_description = 'TDA'

    def get_rts_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='rts')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_rts_proj.short_description = 'RTS'

    def get_ownership_projection(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ownership_projection is None:
            return None
        return '{:.2f}%'.format(float(proj.ownership_projection*100))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'slate_player__projection__ownership_projection'

    def get_rg_ownership_projection(self, obj):
        try:
            proj = models.SlatePlayerRawProjection.objects.get(
                projection_site='rg',
                slate_player=obj.slate_player
            )
            if proj.ownership_projection is None:
                return None
            return '{:.2f}%'.format(float(proj.ownership_projection*100))
        except models.SlatePlayerRawProjection.DoesNotExist:
            return None
    get_rg_ownership_projection.short_description = 'RG-OP'

    def get_ss_ownership_projection(self, obj):
        try:
            proj = models.SlatePlayerRawProjection.objects.get(
                projection_site='sabersim',
                slate_player=obj.slate_player
            )
            if proj.ownership_projection is None:
                return None
            return '{:.2f}%'.format(float(proj.ownership_projection*100))
        except models.SlatePlayerRawProjection.DoesNotExist:
            return None
    get_ss_ownership_projection.short_description = 'SS-OP'

    def get_exposure(self, obj):
        return '{:.2f}%'.format(float(obj.exposure) * 100.0)
    get_exposure.short_description = 'Exp'
    get_exposure.admin_order_field = 'exposure'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

    def get_actual_ownership(self, obj):
        if obj.actual_own is None:
            return None
        return '{:.2f}%'.format(float(obj.actual_own*100))
    get_actual_ownership.short_description = 'Own'
    get_actual_ownership.admin_order_field = 'actual_own'

    def export(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=projections.csv'


        build_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        build_writer.writerow([
            'player', 
            'slate', 
            'salary', 
            'position', 
            'team', 
            'projection', 
            'adjusted_opportunity',
            'value', 
            'game_total', 
            'team_total', 
            'spread', 
            'actual'
        ])

        for projection in queryset:
            build_writer.writerow([
                self.get_player_name(projection), 
                self.get_slate(projection), 
                self.get_player_salary(projection), 
                self.get_player_position(projection), 
                self.get_player_team(projection), 
                projection.projection, 
                projection.adjusted_opportunity,
                self.get_player_value(projection), 
                projection.game_total, 
                projection.team_total, 
                projection.spread, 
                self.get_actual_score(projection)
            ])
        
        return response
    export.short_description = 'Export selected player projections'


@admin.register(models.Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slate',
        'cost',
        'num_games',
        'winning_score',
        'one_pct_score',
        'half_pct_score',
        'great_score',
    )
    list_editable = (
        'winning_score',
        'one_pct_score',
        'half_pct_score',
        'great_score',
    )
    list_filter = (
        'num_games',
        ('slate', RelatedDropdownFilter),
        'slate__site',
    )
    inlines = [
        ContestPrizeInline
    ]


@admin.register(models.CeilingProjectionRangeMapping)
class CeilingProjectionRangeMappingAdmin(admin.ModelAdmin):
    list_display = (
        'min_projection',
        'max_projection',
        'value_to_assign',
        'yh_value_to_assign',
    )
    list_editable = (
        'value_to_assign',
        'yh_value_to_assign',
    )


@admin.register(models.SlateBuildConfig)
class ConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'site',
        'randomness',
        'uniques',
        'min_salary',
    ]

    list_filter = [
        'site',
    ]


@admin.register(models.PlayerSelectionCriteria)
class PlayerSelectionCriteriaAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'site',
        'qb_threshold',
        'rb_threshold',
        'wr_threshold',
        'te_threshold',
        'dst_threshold',
    )


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        'get_game_title',
        'game_date',
        'game_total',
        'home_team',
        'home_spread',
        'home_implied',
        'away_team',
        'away_spread',
        'away_implied',
    )
    list_filter = (
        ('week', RelatedDropdownFilter),
    )
    def get_game_title(self, obj):
        return '{} @ {}'.format(obj.away_team, obj.home_team)
    get_game_title.short_description = 'Game'


@admin.register(models.Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = (
        'get_week_title',
        'start',
        'end',
        'get_num_games',
    )
    date_hierarchy = 'start'
    actions = ['update_vegas']
    inlines = [GameInline]

    def get_week_title(self, obj):
        return str(obj)

    def update_vegas(self, request, queryset):
        for week in queryset:
            task = BackgroundTask()
            task.name = 'Update Vegas'
            task.user = request.user
            task.save()

            tasks.update_vegas_for_week.delay(week.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Updating odds for {} games. A new message will appear here once complete.'.format(str(week)))
    
    def get_num_games(self, obj):
        return mark_safe('<a href="/admin/nfl/game/?week__id__exact={}">{}</a>'.format(obj.id, obj.games.all().count()))
    get_num_games.short_description = '# Games'


@admin.register(models.GroupImportSheet)
class GroupImportSheetAdmin(admin.ModelAdmin):
    list_display = (
        'build',
    )
    raw_id_fields = (
        'build',
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_sheet(request, obj)

    def process_sheet(self, request, sheet):
        task = BackgroundTask()
        task.name = 'Process Group Import'
        task.user = request.user
        task.save()

        tasks.process_group_import_sheet.delay(sheet.id, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your group import is being processed.')
