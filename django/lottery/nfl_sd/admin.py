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


class LineupDuplicatedFilter(SimpleListFilter):
    title = 'duplicated' # or use _('country') for translated title
    parameter_name = 'duplicated'

    def lookups(self, request, model_admin):
        return (
            (10, '10 or less'),
            (20, '20 or less'),
            (30, '30 or less'),
            (40, '40 or less'),
            (50, '50 or less'),
            (60, '60 or less'),
            (70, '70 or less'),
            (80, '80 or less'),
            (90, '90 or less'),
            (100, '100 or less'),
            (101, 'more than 100'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(duplicated__lte=float(self.value()))


# Forms


class SlateForm(forms.ModelForm):
    class Meta:
        model = models.Slate
        fields = [
            'week',
            'site',
            'game',
            'num_contest_entries',
            'salaries_sheet_type',
            'salaries',
            'is_complete',
            'fc_actuals_sheet'    
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = kwargs.get("instance")
        if instance is not None and instance.week is not None:
            games = models.Game.objects.filter(week=instance.week)
        else:
            games = models.Game.objects.all()

        self.fields['game'].queryset  = games


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
            path('alias-nflsd-choose/<int:pk>/<int:chosen_alias_pk>/', self.choose_alias, name="admin_nflsd_choose_alias"),
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
    list_filter = (
        'projection_site',
        'site',
    )


@admin.register(models.Slate)
class SlateAdmin(admin.ModelAdmin):
    form = SlateForm
    list_display = (
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
        'export_game_sim',
    ]
    inlines = (SlateProjectionSheetInline, SlatePlayerOwnershipProjectionSheetInline,)
    # fields = (
    #     'week',
    #     'site',
    #     'game',
    #     'salaries_sheet_type',
    #     'salaries',
    #     'is_complete',
    #     'fc_actuals_sheet',        
    # )
    raw_id_fields = (
        'week',
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
            slate_players_task = BackgroundTask()
            slate_players_task.name = 'Process Slate Players'
            slate_players_task.user = request.user
            slate_players_task.save()

            _ = chain(
                tasks.process_slate_players.si(slate.id, slate_players_task.id),
                group([
                    tasks.process_projection_sheet.si(
                        s.id, 
                        BackgroundTask.objects.create(
                            name=f'Process Projections from {s.projection_site}',
                            user=request.user
                        ).id) for s in slate.projections.all()
                ]),
                tasks.handle_base_projections.si(
                    slate.id, 
                    BackgroundTask.objects.create(
                        name='Process Base Projections',
                        user=request.user
                    ).id),
                group([
                    tasks.process_ownership_sheet.si(s.id, BackgroundTask.objects.create(
                        name=f'Process Ownership Projections from {s.projection_site}',
                        user=request.user
                    ).id) for s in slate.ownership_projections_sheets.all()
                ]),
                # tasks.assign_zscores_to_players.s(slate.id, BackgroundTask.objects.create(
                #         name='Assign Z-Scores to Players',
                #         user=request.user
                # ).id)
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
        return mark_safe('<a href="/admin/nfl_sd/slateplayer/?slate__id__exact={}">Players</a>'.format(obj.id))
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

    def export_game_sim(self, request, queryset):
        jobs = []

        for slate in queryset:
            result_file = f'{slate}.csv'
            result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
            os.makedirs(result_path, exist_ok=True)
            result_path = os.path.join(result_path, result_file)
            result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

            jobs.append(
                tasks.export_game_sim.s(
                    slate.game.id,
                    result_path,
                    result_url,
                    BackgroundTask.objects.create(
                        name=f'Export Simulation for {slate.game}',
                        user=request.user
                    ).id
                )
            )

        group(jobs)()

        messages.add_message(
            request,
            messages.WARNING,
            'Your exports are being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your exports are ready.')
    export_game_sim.short_description = 'Export Game Sim from selected Slates'

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = get_object_or_404(models.Slate, pk=pk)
        tasks.simulate_slate.delay(
            slate.id,
            BackgroundTask.objects.create(
                name=f'Simulate {slate}',
                user=request.user
            ).id
        )
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
        'roster_position',
        'salary',
        'fantasy_points',
        'ownership',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate', RelatedDropdownFilter),
        ('site_pos', DropdownFilter),
        ('roster_position', DropdownFilter),
        'team')


@admin.register(models.SlatePlayerProjection)
class SlatePlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_roster_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'ceiling',
        'floor',
        'stdev',
        'get_ownership_projection',
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
        ('slate_player__roster_position', DropdownFilter),
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate', RelatedDropdownFilter),
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
            player_game=F('slate_player__slate__game')
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

    def get_player_roster_position(self, obj):
        return obj.slate_player.roster_position
    get_player_roster_position.short_description = 'rPos'
    get_player_roster_position.admin_order_field = 'slate_player__get_player_roster_position'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.slate.game
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.id, game.away_team, game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__slate__game'

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
        'projection_site',
        'get_player_salary',
        'get_player_position',
        'get_player_roster_position',
        'get_player_team',
        'get_player_opponent',
        'projection',
        'ceiling',
        'floor',
        'stdev',
        'get_ownership_projection',
        'adjusted_opportunity',
        'get_player_value',
        'get_actual_score',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        'projection_site',
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__roster_position', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate', RelatedDropdownFilter),
        ('slate_player__slate__site', DropdownFilter),
    )
    raw_id_fields = ['slate_player']
    actions = ['export']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            slate=F('slate_player__slate'), 
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary')
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

    def get_player_roster_position(self, obj):
        return obj.slate_player.roster_position
    get_player_roster_position.short_description = 'rPos'
    get_player_roster_position.admin_order_field = 'slate_player__get_player_roster_position'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

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
    list_display = (
        'id',
        'get_cpt',
        'get_flex1',
        'get_flex2',
        'get_flex3',
        'get_flex4',
        'get_flex5',
        'salary',
        'projection',
        'ownership_projection',
        'duplicated',
        'get_roi',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
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

    list_filter = (
        LineupDuplicatedFilter,
        'cpt',
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
    list_per_page = 25
    list_display = (
        'id',
        'view_page_button',
        'prepare_projections_button',
        'build_button',
        'export_button',
        'slate',
        'used_in_contests',
        'configuration',
        'get_projections_ready',
        'get_ready',
        'get_pct_complete',
        'total_lineups',
        'num_lineups_created',
        'get_links',
        'status',
        'get_elapsed_time',
    )
    list_editable = (
        'used_in_contests',
        'total_lineups',
    )
    list_filter = (
        ('configuration', RelatedDropdownFilter),
        ('slate', RelatedDropdownFilter),
        ('slate__week', RelatedDropdownFilter),
        'slate__site',
        'used_in_contests',
    )
    raw_id_fields = [
        'slate',
        'configuration',
    ]
    actions = [
        'reset',
        'clean_lineups',
        'find_expected_lineup_order',
        'export_lineups', 
        'race_build',
        'duplicate_builds', 
        'clear_data'
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('nfl_sd-slatebuild-build/<int:pk>/', self.build, name="admin_nflsd_slatebuild_build"),
            path('nfl_sd-slatebuild-export/<int:pk>/', self.export_for_upload, name="admin_nflsd_slatebuild_export"),
            path('nfl_sd-slatebuild-prepare-projections/<int:pk>/', self.prepare_projections, name="admin_nflsd_slatebuild_prepare_projections"),
        ]
        return my_urls + urls
    
    def export_button_field(self, obj):
        return format_html(
            "<button onclick='doSomething({})' style='width: 58px; margin: auto; color: #ffffff; background-color: #4fb2d3; font-weight: bold;'>Export</button>", 
            obj.id
        )
    export_button_field.short_description = ''

    def get_ready(self, obj):
        return obj.ready
    get_ready.short_description = 'GO'
    get_ready.boolean = True

    def get_projections_ready(self, obj):
        return obj.projections_ready
    get_projections_ready.short_description = 'PR'
    get_projections_ready.boolean = True

    def get_links(self, obj):
        html = ''
        if obj.num_lineups_created() > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl_sd/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id)

        return mark_safe(html)
    get_links.short_description = 'Links'

    def get_elapsed_time(self, obj):
        _, _, minutes, seconds, _ = _get_duration_components(obj.elapsed_time)
        return '{:02d}:{:02d}'.format(minutes, seconds)
    get_elapsed_time.short_description = 'Time'
    get_elapsed_time.admin_order_field = 'elapsed_time'

    def get_pct_complete(self, obj):
        return '{:.2f}%'.format(float(obj.pct_complete) * 100.0)
    get_pct_complete.short_description = 'prog'
    get_pct_complete.admin_order_field = 'pct_complete'

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
            'Building all lineups for every possible captain')

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


@admin.register(models.BuildPlayerProjection)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_player_salary',
        'get_player_position',
        'get_player_roster_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'get_ceiling',
        'get_awesemo_proj',
        'get_etr_proj',
        'get_rg_proj',
        'get_exposure',
        'get_ownership_projection',
        'value',
        'get_game_total',
        'get_team_total',
        'get_spread',
        'in_play',
        'locked',
        'min_exposure',
        'max_exposure',
    )
    list_editable = (
        'in_play',
        'min_exposure',
        'max_exposure',
        'locked',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        ('slate_player__roster_position', DropdownFilter),
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        ('slate_player__slate', RelatedDropdownFilter),
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

    def get_player_roster_position(self, obj):
        return obj.slate_player.roster_position
    get_player_roster_position.short_description = 'rPos'
    get_player_roster_position.admin_order_field = 'slate_player__get_player_roster_position'

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.slate.game
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.id, game.away_team, game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__slate__game'

    def get_ceiling(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ceiling is None:
            return None
        return '{:.2f}'.format(proj.ceiling)
    get_ceiling.short_description = 'ceil'
    get_ceiling.admin_order_field = 'slate_player__projection__ceiling'

    def get_game_total(self, obj):
        return obj.game_total
    get_game_total.short_description = 'GT'

    def get_team_total(self, obj):
        return obj.team_total
    get_team_total.short_description = 'TT'

    def get_spread(self, obj):
        return obj.spread
    get_spread.short_description = 'SP'

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

    def get_rg_proj(self, obj):
        projs = obj.available_projections.filter(projection_site='rg')
        if projs.count() > 0:
            return projs[0].projection
        return None
    get_rg_proj.short_description = 'RG'

    def get_ownership_projection(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ownership_projection is None:
            return None
        return '{:.2f}%'.format(float(proj.ownership_projection*100))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'slate_player__projection__ownership_projection'

    def get_exposure(self, obj):
        return '{:.2f}%'.format(float(obj.exposure) * 100.0)
    get_exposure.short_description = 'Exp'
    get_exposure.admin_order_field = 'exposure'

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
