import csv
import datetime
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

from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from configuration.models import BackgroundTask
from . import models, tasks


class RetirementFilter(SimpleListFilter):
    title = 'loser retired'
    parameter_name = 'retired'

    def lookups(self, request, model_admin):
        return (
            ('y', 'Retired'),
            ('n', 'Not Retired'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'y':
            return queryset.filter(score__icontains='RET')
        elif self.value() == 'n':
            return queryset.exclude(score__icontains='RET')


class DKEligibleMatchFilter(SimpleListFilter):
    title = 'dk eligible'
    parameter_name = 'eligible'

    def lookups(self, request, model_admin):
        return (
            (True, 'DK Eligible Only'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.exclude(Q(
                Q(w_ace=None) | Q(w_df=None) | Q(l_ace=None) | Q(l_df=None)
            ))


class SpecialTourneyFilter(SimpleListFilter):
    title = 'Special Tourney'
    parameter_name = 'special_tourney'

    def lookups(self, request, model_admin):
        return (
            ('y', 'Davis Cup & Olympics Only'),
            ('n', 'Exclude Davis Cup & Olympics'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'n':
            return queryset.exclude(Q(
                Q(tourney_level='D') | Q(tourney_level='O')
            ))
        elif self.value() == 'y':
            return queryset.filter(Q(
                Q(tourney_level='D') | Q(tourney_level='O')
            ))


class RecentMatchesFilter(SimpleListFilter):
    title = 'recent matches'
    parameter_name = 'recent'

    def lookups(self, request, model_admin):
        return (
            (True, 'Recent Matches Only'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tourney_date__gte=datetime.date(2010, 1, 1))


class ActivePlayerFilter(SimpleListFilter):
    title = 'active players'
    parameter_name = 'active'

    def lookups(self, request, model_admin):
        return (
            (True, 'Active Players Only'),
        )

    def queryset(self, request, queryset):
        if self.value():
            endDate = datetime.date.today() - datetime.timedelta(weeks=52)
            return queryset.filter(
                Q(
                    Q(winning_matches__tourney_date__gte=endDate) | Q(losing_matches__tourney_date__gte=endDate)
                )
            ).distinct()
        return queryset


class RankingHistoryInline(admin.TabularInline):
    model = models.RankingHistory


class PinnacleMatchOddsInline(admin.TabularInline):
    model = models.PinnacleMatchOdds
    extra = 0


class SlateMatchInline(admin.TabularInline):
    model = models.SlateMatch
    extra = 0
    fields = (
        'match',
        'get_event',
        'surface',
        'best_of',
        'common_opponents'
    )
    readonly_fields = (
        'match',
        'get_event',
        'common_opponents'
    )

    def get_event(self, obj):
        return obj.match.event
    get_event.short_description = 'event'

    def common_opponents(self, obj):
        return models.Player.objects.filter(id__in=obj.common_opponents(obj.surface)).count()
    common_opponents.short_description = 'Common Opponents'


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'tour',
        'hand',
        'dob',
        'country',
        'get_num_matches',
        'get_ace_rate',
        'get_v_ace_rate',
        'get_df_rate',
        'get_hold_rate',
        'get_break_rate',
    )

    list_filter = (
        'tour',
        'hand',
        ('country', DropdownFilter),
        ActivePlayerFilter,
    )
    
    search_fields = (
        'first_name',
        'last_name'
    )

    actions = [
    ]

    inlines = [
        RankingHistoryInline
    ]

    def get_num_matches(self, obj):
        return obj.get_num_matches()
    get_num_matches.short_description = '#'

    def get_ace_rate(self, obj):
        return obj.get_ace_rate()
    get_ace_rate.short_description = 'a'

    def get_v_ace_rate(self, obj):
        return obj.get_v_ace_rate()
    get_v_ace_rate.short_description = 'v_a'

    def get_df_rate(self, obj):
        return obj.get_df_rate()
    get_df_rate.short_description = 'df'

    def get_first_in_rate(self, obj):
        rate = obj.get_first_in_rate()
        if rate is not None:
            return '{}%'.format(round(rate*100.0, 2))
        return rate
    get_first_in_rate.short_description = '1stIn'

    def get_first_won_rate(self, obj):
        rate = obj.get_first_won_rate()
        if rate is not None:
            return '{}%'.format(round(rate*100.0, 2))
        return rate
    get_first_won_rate.short_description = '1stW'

    def get_second_won_rate(self, obj):
        rate = obj.get_second_won_rate()
        if rate is not None:
            return '{}%'.format(round(rate*100.0, 2))
        return rate
    get_second_won_rate.short_description = '2ndW'

    def get_hold_rate(self, obj):
        rate = obj.get_hold_rate()
        if rate is not None:
            return '{}%'.format(round(rate*100.0, 2))
        return rate
    get_hold_rate.short_description = 'hld'

    def get_break_rate(self, obj):
        rate = obj.get_break_rate()
        if rate is not None:
            return '{}%'.format(round(rate*100.0, 2))
        return rate
    get_break_rate.short_description = 'brk'


@admin.register(models.Match)
class MatchAdmin(admin.ModelAdmin):
    date_hierarchy = 'tourney_date'
    list_display = (
        'tourney_id',
        'tourney_name',
        'tourney_level',
        'surface',
        'round',
        'best_of',
        'tourney_date',
        'winner',
        'loser',
        'score',
        # 'get_svpt_w',
        'winner_dk_points',
        'loser_dk_points',
    )

    list_filter = (
        ('surface', DropdownFilter),
        ('best_of', DropdownFilter),
        ('winner__tour', DropdownFilter),
        RetirementFilter,
        DKEligibleMatchFilter,
        RecentMatchesFilter,
        SpecialTourneyFilter,
    )

    search_fields = (
        'winner_name',
        'loser_name'
    )

    # def get_queryset(self, request):
    #     qs= super().get_queryset(request)

    #     qs.annotate(
    #         sv_pt_w=(F('w_1stWon') + F('w_2ndWon'))/F('w_svpt')
    #     )

    #     return qs

    # def get_svpt_w(self, obj):
    #     return obj.sv_pt_w
    # get_svpt_w.short_description = 'w_svpt'


@admin.register(models.Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = (
        'dk_name',
        'fd_name',
        'pinn_name',
        'player'
    )
    list_editable = (
        'pinn_name',
        'player',
    )
    search_fields = (
        'dk_name',
        'fd_name',
        'pinn_name'
    )
    raw_id_fields = (
        'player',
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
            path('tennis-alias-choose/<int:pk>/<int:chosen_alias_pk>/', self.choose_alias, name="admin_tennis_choose_alias"),
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
            elif missing_alias.site == 'pinnacle':
                alias.pinn_name = missing_alias.player_name
            
            alias.save()

            self.message_user(request, 'Alias updated: {}'.format(str(alias)), level=messages.INFO)
        else:
            alias = models.Alias.objects.create(
                dk_name=missing_alias.player_name,
                fd_name=missing_alias.player_name,
                pinn_name=missing_alias.player_name
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
                pinn_name=missing_alias.player_name
            )

        self.message_user(request, '{} new aliases created.'.format(count), level=messages.INFO)
        queryset.delete()


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
        'randomness',
        'uniques',
        'min_salary',
    ]


@admin.register(models.Slate)
class SlateAdmin(admin.ModelAdmin):
    list_display = (
        'datetime',
        'name',
        'last_match_datetime',
        'site',
        'is_main_slate',
        'get_players_link',
        'get_projections_link',
        'get_builds_link',
        'sim_button',
    )
    list_editable = (
        'name',
        'site',
        'is_main_slate',
        'last_match_datetime',
    )
    inlines = [
        SlateMatchInline
    ]
    actions = [
        'get_pinn_odds',
        'calculate_slate_structure'
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_slate(request, obj)

    def process_slate(self, request, slate):
        chain(
            tasks.get_pinn_odds.si(
                BackgroundTask.objects.create(
                    name='Update pinnacle odds',
                    user=request.user
                ).id
            ),
            tasks.process_slate_players.si(
                slate.id,
                BackgroundTask.objects.create(
                    name='Process slate players',
                    user=request.user
                ).id
            ),
            tasks.find_slate_matches.si(
                slate.id,
                BackgroundTask.objects.create(
                    name='Find matches for slate',
                    user=request.user
                ).id
            )
        )()

        messages.add_message(
            request,
            messages.WARNING,
            'Your slate is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the slate is ready.')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('tennis-slate-simulate/<int:pk>/', self.simulate, name="tennis_admin_slate_simulate"),
        ]
        return my_urls + urls

    def get_players_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/tennis/slateplayer/?slate__id={}">Players</a>'.format(obj.id))
        return 'None'
    get_players_link.short_description = 'Players'

    def get_projections_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/tennis/slateplayerprojection/?slate_player__slate__id={}">Projections</a>'.format(obj.id))
        return 'None'
    get_projections_link.short_description = 'Projections'

    def get_builds_link(self, obj):
        if obj.players.all().count() > 0:
            return mark_safe('<a href="/admin/tennis/slatebuild/?slate__id={}">Builds</a>'.format(obj.id))
        return 'None'
    get_builds_link.short_description = 'Builds'

    def initialize(self, request, queryset):
        for slate in queryset:
            slate.get_pinn_odds()
            slate.find_opponents()
            slate.create_build()
    initialize.short_description = 'Initialize selected slates'

    def get_pinn_odds(self, request, queryset):
        group(
            [
                chain(
                    tasks.get_pinn_odds.si(
                        BackgroundTask.objects.create(
                            name='Get Pinnacle Odds',
                            user=request.user
                        ).id
                    ),
                    tasks.find_slate_matches.si(
                        slate.id,
                        BackgroundTask.objects.create(
                            name='Find Slate matches',
                            user=request.user
                        ).id
                    )
                ) for slate in queryset
            ]
        )()
    get_pinn_odds.short_description = 'Update odds for selected slates'

    def project_players(self, request, queryset):
        for slate in queryset:
            slate.project_players()
    project_players.short_description = 'Project players for selected slates'

    def project_ownership(self, request, queryset):
        for slate in queryset:
            slate.project_ownership()
    project_ownership.short_description = 'Project ownership for selected slates'

    def calculate_slate_structure(self, request, queryset):
        group([
            tasks.calculate_slate_structure.si(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Calculate structure for {slate}',
                    user=request.user
                ).id) for slate in queryset
        ])()

        messages.add_message(
            request,
            messages.WARNING,
            'Calculating slate structures'
        )
    calculate_slate_structure.short_description = 'Calculate slate structure for selected slates'

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = get_object_or_404(models.Slate, pk=pk)
        chord([
            tasks.simulate_match.si(
                slate_match.id,
                BackgroundTask.objects.create(
                    name=f'Simulate {slate_match}',
                    user=request.user
                ).id
            ) for slate_match in slate.matches.all()
        ], tasks.calculate_target_scores.si(
                slate.id,
                BackgroundTask.objects.create(
                    name=f'Calculate target scores for {slate}',
                    user=request.user
            ).id)
        )()

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating player outcomes for {}'.format(str(slate)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)


@admin.register(models.SlatePlayer)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slate',
        'salary',
        'surface',
        'fantasy_points',
        'player',
        'withdrew',
        'is_replacement_player',
        'opponent',
    )
    list_editable = (
        'surface',
        'opponent',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate__name', DropdownFilter),
    )
    raw_id_fields = (
        'player', 
        'opponent',
    )
    actions = ['withdraw_player']

    def withdraw_player(self, request, queryset):
        for slate_player in queryset:
            slate_player.withdraw_player()


@admin.register(models.SlateBuild)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    list_display = (
        'created',
        'slate',
        'used_in_contests',
        'configuration',
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
        ('configuration', RelatedDropdownFilter),
        ('slate__name', DropdownFilter),
        'used_in_contests',
    )
    search_fields = ('slate__name',)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('tennis-slatebuild-build/<int:pk>/', self.build, name="admin_tennis_slatebuild_build"),
            path('tennis-slatebuild-export/<int:pk>/', self.export_for_upload, name="admin_tennis_slatebuild_export"),
        ]
        return my_urls + urls

    def create_default_groups(self, request, queryset):
        for b in queryset:
            b.create_default_groups()
    create_default_groups.short_description = 'Create default groups for selected builds'

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

    def get_lineups_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/tennis/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Lineups'


@admin.register(models.SlatePlayerProjection)
class SlatePlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'slate_player',
        'slate_match',
        'get_player_salary',
        'get_salary_value',
        'pinnacle_odds',
        'spread',
        'get_common_opponents',
        'spw_rate',
        # 'rpw_rate',
        # 'ace_rate',
        # 'df_rate',
        'implied_win_pct',
        'sim_win_pct',
        'projection',
        # 's75',
        'ceiling',
        'odds_for_target',
        # 'get_odds_for_target_value',
        'in_play',
        # 'optimal_exposure',
        'min_exposure',
        'max_exposure',
        'get_exposure',
    )
    list_filter = (
        'slate_player__slate',
        'slate_player__player__tour',
        'in_play',
    )
    list_editable = (
        'spw_rate',
        # 'rpw_rate',
        # 'ace_rate',
        # 'df_rate',
        'in_play',
        'min_exposure',
        'max_exposure',
    )


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            exposure=Avg('exposures__exposure'), 
        )

        return qs

    def get_player_salary(self, obj):
        return obj.salary
    get_player_salary.short_description = 'salary'
    get_player_salary.admin_order_field = 'slate_player__salary'

    def get_player_link(self, obj):
        return mark_safe('<a href="/admin/tennis/match/?q={}">{}</a>'.format(obj.slate_player.player, obj.slate_player.player))
    get_player_link.short_description = 'Player'

    def get_salary_value(self, obj):
        return round(obj.slate_player.value, 2)
    get_salary_value.short_description = 'value'

    def get_common_opponents(self, obj):
        return obj.slate_match.common_opponents(obj.slate_match.surface, 52).size
    get_common_opponents.short_description = 'comm opp'

    def get_odds_for_target_value(self, obj):
        if obj.odds_for_target_value is None:
            return None
        return '{:.2f}'.format(obj.odds_for_target_value)
    get_odds_for_target_value.short_description = 'otv'
    get_odds_for_target_value.admin_sort_field = 'odds_for_targe_value'

    def get_exposure(self, obj):
        if obj.exposure is None:
            return None
        return '{:.2f}%'.format(float(obj.exposure) * 100.0)
    get_exposure.short_description = 'Exp'
    get_exposure.admin_order_field = 'exposure'


@admin.register(models.SlateBuildLineup)
class SlateBuildLineupAdmin(admin.ModelAdmin):
    list_display = (
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
        'total_salary',
        'implied_win_pct',
        'sim_win_pct',
        'median',
        's90',
    )

    search_fields = (
        'player_1__slate_player__name',
        'player_2__slate_player__name',
        'player_3__slate_player__name',
        'player_4__slate_player__name',
        'player_5__slate_player__name',
        'player_6__slate_player__name',
    )

    raw_id_fields = (
        'player_1',
        'player_2',
        'player_3',
        'player_4',
        'player_5',
        'player_6',
    )


@admin.register(models.PinnacleMatch)
class PinnacleMatchAdmin(admin.ModelAdmin):
    list_display = (
        'event',
        'home_participant',
        'away_participant',
        'start_time',
    )
    search_fields = (
        'event',
        'home_participant',
        'away_participant'
    )
    inlines = [
        PinnacleMatchOddsInline
    ]


@admin.register(models.PinnacleMatchOdds)
class PinnacleMatchOddsAdmin(admin.ModelAdmin):
    list_display = (
        'match',
        'get_event',
        'create_at',
        'home_price',
        'away_price',
        'home_spread',
        'away_spread'
    )
    search_fields = (
        'match__event',
        'match__home_participant',
        'match__away_participant'
    )
