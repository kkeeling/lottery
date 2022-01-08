import csv
import datetime
import traceback

import requests

from celery import shared_task, chord, group, chain

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
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


class SlateMatchInline(admin.TabularInline):
    model = models.SlateMatch
    extra = 0
    fields = (
        'match',
    )
    readonly_fields = (
        'match',
    )


# class SlatePlayerProjectionInline(admin.TabularInline):
#     model = models.SlatePlayerProjection


# class SlateBuildGroupPlayerInline(admin.TabularInline):
#     model = models.SlateBuildGroupPlayer
#     raw_id_fields = ['slate_player']


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


# @admin.register(models.RankingHistory)
# class RankingHistoryAdmin(admin.ModelAdmin):
#     list_display = (
#         'player',
#         'ranking',
#         'ranking_date',
#     )

#     list_filter = (
#         'player__tour',
#     )


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
    # actions = ['initialize', 'get_pinn_odds', 'simulate_slate']

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
        for slate in queryset:
            slate.get_pinn_odds()
    get_pinn_odds.short_description = 'Get odds for selected slates'

    def project_players(self, request, queryset):
        for slate in queryset:
            slate.project_players()
    project_players.short_description = 'Project players for selected slates'

    def project_ownership(self, request, queryset):
        for slate in queryset:
            slate.project_ownership()
    project_ownership.short_description = 'Project ownership for selected slates'

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = get_object_or_404(models.Slate, pk=pk)

        slate_match = slate.matches.all()[3]
        tasks.simulate_match.delay(
            slate_match.id,
            BackgroundTask.objects.create(
                name=f'Simulate {slate_match}',
                user=request.user
            ).id
        )
        # group([
        #     tasks.simulate_match.si(
        #         slate_match.id,
        #         BackgroundTask.objects.create(
        #             name=f'Simulate {slate_match}',
        #             user=request.user
        #         ).id
        #     ) for slate_match in slate.matches.all()
        # ])()

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating player outcomes for {}'.format(str(slate)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def build(self, request, queryset):
        for slate in queryset:
            slate.build()
    build.short_description = 'Build selected slates'

    def find_in_play(self, request, queryset):
        for slate in queryset:
            slate.find_in_play()
    find_in_play.short_description = 'Find in play for selected slate'


# @admin.register(models.SlatePlayer)
# class SlatePlayerAdmin(admin.ModelAdmin):
#     list_display = (
#         'name',
#         'slate',
#         'salary',
#         'surface',
#         'well_known_player',
#         'fantasy_points',
#         'player',
#         'withdrew',
#         'is_replacement_player',
#         'opponent',
#         'times_used_in_sim',
#     )
#     list_editable = (
#         'surface',
#         'well_known_player',
#         'fantasy_points',
#         'opponent',
#     )
#     search_fields = ('name',)
#     list_filter = (
#         ('slate__name', DropdownFilter),
#     )
#     raw_id_fields = (
#         'player', 
#         'opponent',
#     )
#     actions = ['find_opponents', 'withdraw_player']
#     inlines = [SlatePlayerProjectionInline]

#     def find_opponents(self, request, queryset):
#         for slate_player in queryset:
#             slate_player.find_opponent()

#     def withdraw_player(self, request, queryset):
#         for slate_player in queryset:
#             slate_player.withdraw_player()


# @admin.register(models.SlatePlayerImportSheet)
# class SlatePlayerImportSheetAdmin(admin.ModelAdmin):
#     list_display = (
#         'slate',
#     )
#     actions = ['save_again']

#     def save_again(self, request, queryset):
#         for sheet in queryset:
#             sheet.save()
#     save_again.short_description = 'Re-import selected sheets'


# class SlateBuildAdmin(admin.ModelAdmin):
#     date_hierarchy = 'slate__datetime'
#     list_display = (
#         'created',
#         'slate',
#         'used_in_contests',
#         'configuration',
#         'total_lineups',
#         'get_groups_link',
#         'num_lineups_created',
#         'get_lineups_link',
#         'get_exposures_link',
#         'avg_sal',
#         'total_exposure',
#         'field_avg_sal',
#         'opt_avg_sal',
#         'sugg_avg_sal',
#         'tag',
#         'notes'
#     )
#     list_editable = (
#         'used_in_contests',
#         'configuration',
#         'total_lineups',
#         'slate',
#         'notes',
#         'tag'
#     )
#     list_filter = (
#         ('configuration', RelatedDropdownFilter),
#         ('slate__name', DropdownFilter),
#         'used_in_contests',
#         'tag'
#     )
#     search_fields = ('slate__name',)
#     actions = [
#         'create_default_groups',
#         'build', 
#     ]

#     def create_default_groups(self, request, queryset):
#         for b in queryset:
#             b.create_default_groups()
#     create_default_groups.short_description = 'Create default groups for selected builds'

#     def build(self, request, queryset):
#         for b in queryset:
#             b.build()
#     build.short_description = 'Generate lineups for selected builds'

#     def get_groups_link(self, obj):
#         if obj.num_groups > 0:
#             return mark_safe('<a href="/admin/tennis/slatebuildgroup/?build__id__exact={}">Groups</a>'.format(obj.id))
#         return 'None'
#     get_groups_link.short_description = 'Groups'

#     def get_lineups_link(self, obj):
#         if obj.num_lineups_created() > 0:
#             return mark_safe('<a href="/admin/tennis/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id))
#         return 'None'
#     get_lineups_link.short_description = 'Lineups'

#     def get_exposures_link(self, obj):
#         if obj.num_lineups_created() > 0:
#             return mark_safe('<a href="/admin/tennis/slateplayerbuildexposure/?build_id={}">Exp</a>'.format(obj.id))
#         return 'None'
#     get_exposures_link.short_description = 'Exp'
# tagulous.admin.register(models.SlateBuild, SlateBuildAdmin)


# @admin.register(models.SlateBuildGroup)
# class SlateBuildGroupAdmin(admin.ModelAdmin):
#     list_display = (
#         'name',
#         'min_from_group',
#         'max_from_group',
#         'total_exposure',
#         'num_players',
#         'active',
#     )
#     list_editable = (
#         'min_from_group',
#         'max_from_group',
#         'total_exposure',
#         'active',
#     )
#     inlines = [
#         SlateBuildGroupPlayerInline
#     ]


# @admin.register(models.SlatePlayerProjection)
# class SlatePlayerProjectionAdmin(admin.ModelAdmin):
#     list_display = (
#         'slate_player',
#         'get_player_link',
#         'opponent',
#         'get_player_salary',
#         'get_salary_value',
#         'pinnacle_odds',
#         'implied_win_pct',
#         'spread',
#         'get_rank',
#         'get_num_matches',
#         'get_ace_rate',
#         'get_v_ace_rate',
#         'get_opponent_v_ace_rate',
#         'get_df_rate',
#         'get_hold_rate',
#         'get_opponent_hold_rate',
#         'get_break_rate',
#         'min_exposure_for_op',
#         'max_exposure_for_op',
#         'projected_exposure',
#         'optimal_exposure',
#         'suggested_exposure',
#         'desired_exposure',
#         'min_exposure',
#         'max_exposure',
#         'in_play',
#         'lock',
#         'get_default_group',
#     )
#     list_editable = (
#         'pinnacle_odds',
#         'implied_win_pct',
#         'spread',
#         'min_exposure_for_op',
#         'max_exposure_for_op',
#         'suggested_exposure',
#         'desired_exposure',
#         'min_exposure',
#         'max_exposure',
#         'in_play',
#         'lock',
#     )
#     list_filter = (
#         'slate_player__slate',
#         'slate_player__player__tour',
#         'in_play',
#     )
#     actions = ['calc_implied_win_pct', 'get_predictions', 'export_for_ml', 'find_in_play', 'calc_suggested_exp']

#     def get_player_salary(self, obj):
#         return obj.salary
#     get_player_salary.short_description = 'salary'
#     get_player_salary.admin_order_field = 'slate_player__salary'

#     def get_player_link(self, obj):
#         return mark_safe('<a href="/admin/tennis/match/?q={}">{}</a>'.format(obj.slate_player.player, obj.slate_player.player))
#     get_player_link.short_description = 'Player'

#     def get_salary_value(self, obj):
#         return round(obj.slate_player.value, 2)
#     get_salary_value.short_description = 'value'

#     def get_prediction_r2(self, obj):
#         PREDICTION_R2s = {
#             '104': 0.1161,
#             '52': 0.1038,
#             '26': 0.1467,
#             '13': 0.1731,
#             '4': 0.2864,
#             '2': 0.3477,
#         }
#         return PREDICTION_R2s[obj.slate_player.get_prediction_threshold()]
#     get_prediction_r2.short_description = 'r^2'

#     def get_num_matches(self, obj):
#         return obj.slate_player.get_num_matches()
#     get_num_matches.short_description = '#'

#     def get_ace_rate(self, obj):
#         return obj.slate_player.get_ace_rate()
#     get_ace_rate.short_description = 'ace'

#     def get_v_ace_rate(self, obj):
#         return obj.slate_player.get_v_ace_rate()
#     get_v_ace_rate.short_description = 'v_ace'

#     def get_opponent_v_ace_rate(self, obj):
#         return obj.slate_player.get_opponent_v_ace_rate()
#     get_opponent_v_ace_rate.short_description = 'opp_v_ace'

#     def get_df_rate(self, obj):
#         return obj.slate_player.get_df_rate()
#     get_df_rate.short_description = 'df'

#     def get_hold_rate(self, obj):
#         rate = obj.slate_player.get_hold_rate()
#         if rate is not None:
#             return '{}%'.format(round(rate*100.0, 2))
#         return rate
#     get_hold_rate.short_description = 'hld'

#     def get_opponent_hold_rate(self, obj):
#         rate = obj.slate_player.get_opponent_hold_rate()
#         if rate is not None:
#             return '{}%'.format(round(rate*100.0, 2))
#         return rate
#     get_opponent_hold_rate.short_description = 'opp_hld'

#     def get_break_rate(self, obj):
#         rate = obj.slate_player.get_break_rate()
#         if rate is not None:
#             return '{}%'.format(round(rate*100.0, 2))
#         return rate
#     get_break_rate.short_description = 'brk'

#     def get_rank(self, obj):
#         rank = obj.slate_player.get_rank()
#         if rank is not None:
#             return rank
#         return None
#     get_rank.short_description = 'rnk'

#     def get_optimal_exposure(self, obj):
#         if obj.slate_player.times_used_in_sim == 0 or obj.slate_player.slate.total_sim_lineups == 0:
#             return None
#         return '{:2f}'.format((obj.slate_player.times_used_in_sim / obj.slate_player.slate.total_sim_lineups) * 100)
#     get_optimal_exposure.short_description = 'opt exp'

#     def get_default_group(self, obj):
#         groups = models.SlateBuildGroup.objects.filter(players__slate_player__projection=obj)
#         if groups.count() > 0:
#             return groups[0].name

#         return None
#     get_default_group.short_description = 'group'

#     def calc_implied_win_pct(self, request, queryset):
#         for projection in queryset:
#             projection.calc_implied_win_pct()
#     calc_implied_win_pct.short_description = 'Calculate implied win pct for selected players'

#     def get_predictions(self, request, queryset):
#         for projection in queryset:
#             projection.get_projection_from_ml()
#     get_predictions.short_description = 'Get predictions for selected players'

#     def export_for_ml(self, request, queryset):
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename=players.csv'

#         writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#         writer.writerow([
#             'id',
#             'w_ace_52',
#             'w_v_ace_52',
#             'w_df_52',
#             'w_1stIn_52',
#             'w_1stWon_52',
#             'w_2ndWon_52',
#             'w_hld_pct_52',
#             'w_brk_pct_52',
#             'l_ace_52',
#             'l_v_ace_52',
#             'l_def_52',
#             'l_1stIn_52',
#             'l_1stWon_52',
#             'l_2ndWon_52',
#             'l_hld_pct_52',
#             'l_brk_pct_52'
#         ])
        
#         for (index, projection) in enumerate(queryset):
#             print('{} out of {}'.format(index+1, queryset.count()))
#             try:
#                 writer.writerow([
#                     projection.slate_player.name,
#                     projection.slate_player.get_ace_rate(),
#                     projection.slate_player.get_v_ace_rate(),
#                     projection.slate_player.get_df_rate(), 
#                     projection.slate_player.get_first_in_rate(), 
#                     projection.slate_player.get_first_won_rate(), 
#                     projection.slate_player.get_second_won_rate(), 
#                     projection.slate_player.get_hold_rate(), 
#                     projection.slate_player.get_break_rate(), 
#                     projection.slate_player.get_opponent_ace_rate(),
#                     projection.slate_player.get_opponent_v_ace_rate(),
#                     projection.slate_player.get_opponent_df_rate(), 
#                     projection.slate_player.get_opponent_first_in_rate(), 
#                     projection.slate_player.get_opponent_first_won_rate(), 
#                     projection.slate_player.get_opponent_second_won_rate(), 
#                     projection.slate_player.get_opponent_hold_rate(), 
#                     projection.slate_player.get_opponent_break_rate()
#                 ])
#             except:
#                 traceback.print_exc()
        
#         return response
#     export_for_ml.short_description = 'Export selected players for machine learning'

#     def find_in_play(self, request, queryset):
#         for projection in queryset:
#             projection.find_in_play()
#     find_in_play.short_description = 'Find in play for selected players'

#     def calc_suggested_exp(self, request, queryset):
#         for projection in queryset:
#             projection.calc_suggested_exposure()
#     calc_suggested_exp.short_description = 'Calculate suggested exposure for selected players'


# @admin.register(models.SlateSimulationLineup)
# class SlateSimulationLineupAdmin(admin.ModelAdmin):
#     list_display = (
#         'player_1',
#         'player_2',
#         'player_3',
#         'player_4',
#         'player_5',
#         'player_6',
#         'total_salary',
#         'six_win_odds',
#         'times_used'
#     )

#     search_fields = (
#         'player_1__name',
#         'player_2__name',
#         'player_3__name',
#         'player_4__name',
#         'player_5__name',
#         'player_6__name',
#     )

#     actions = [
#         'export_for_upload'
#     ]

#     def export_for_upload(self, request, queryset):
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename={}_upload.csv'.format(queryset[0].slate.name)

#         build_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#         build_writer.writerow(['P', 'P', 'P', 'P', 'P', 'P'])

#         for (index, lineup) in enumerate(queryset):
#             row = [
#                 '{1} ({0})'.format(lineup.player_1.slate_player_id, lineup.player_1.name),
#                 '{1} ({0})'.format(lineup.player_2.slate_player_id, lineup.player_2.name),
#                 '{1} ({0})'.format(lineup.player_3.slate_player_id, lineup.player_3.name),
#                 '{1} ({0})'.format(lineup.player_4.slate_player_id, lineup.player_4.name),
#                 '{1} ({0})'.format(lineup.player_5.slate_player_id, lineup.player_5.name),
#                 '{1} ({0})'.format(lineup.player_6.slate_player_id, lineup.player_6.name),
#             ]

#             build_writer.writerow(row)
#             print('{} of {} lineups complete'.format(index+1, queryset.count()))
        
#         return response
#     export_for_upload.short_description = 'Export lineups for upload'


# @admin.register(models.SlateBuildLineup)
# class SlateBuildLineupAdmin(admin.ModelAdmin):
#     list_display = (
#         'player_1',
#         'player_2',
#         'player_3',
#         'player_4',
#         'player_5',
#         'player_6',
#         'total_salary',
#         'six_win_odds'
#     )

#     search_fields = (
#         'player_1__name',
#         'player_2__name',
#         'player_3__name',
#         'player_4__name',
#         'player_5__name',
#         'player_6__name',
#     )

#     actions = [
#         'export_for_upload'
#     ]

#     def export_for_upload(self, request, queryset):
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename={}_upload.csv'.format(queryset[0].build.slate.name)

#         build_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#         build_writer.writerow(['P', 'P', 'P', 'P', 'P', 'P'])

#         for (index, lineup) in enumerate(queryset):
#             row = [
#                 '{1} ({0})'.format(lineup.player_1.slate_player_id, lineup.player_1.name),
#                 '{1} ({0})'.format(lineup.player_2.slate_player_id, lineup.player_2.name),
#                 '{1} ({0})'.format(lineup.player_3.slate_player_id, lineup.player_3.name),
#                 '{1} ({0})'.format(lineup.player_4.slate_player_id, lineup.player_4.name),
#                 '{1} ({0})'.format(lineup.player_5.slate_player_id, lineup.player_5.name),
#                 '{1} ({0})'.format(lineup.player_6.slate_player_id, lineup.player_6.name),
#             ]

#             build_writer.writerow(row)
#             print('{} of {} lineups complete'.format(index+1, queryset.count()))
        
#         return response
#     export_for_upload.short_description = 'Export lineups for upload'


# @admin.register(models.SlatePlayerBuildExposure)
# class SlatePlayerBuildExposureAdmin(admin.ModelAdmin):
#     build = None
#     list_display = (
#         'name',
#         'salary',
#         'get_projection',
#         'get_projected_exposure',
#         'get_desired_exposure',
#         'get_exposure'
#     )

#     def get_queryset(self, request):
#         queryset = super().get_queryset(request)
#         request.GET = request.GET.copy()
#         build_id = request.GET.pop('build_id', None)
        
#         if build_id is not None:
#             self.build = models.SlateBuild.objects.get(id=build_id[0])
#             queryset = self.model.objects.filter(slate=self.build.slate, projection__in_play=True)
        
#         return queryset.order_by('-salary')

#     def get_projection(self, obj):
#         if obj.projection is None:
#             return None
#         return obj.projection.median_winning_projection
#     get_projection.short_description = 'Proj'

#     def get_desired_exposure(self, obj):
#         return '{:.2f}%'.format(obj.projection.desired_exposure * 100)
#     get_desired_exposure.short_description = 'Desired Exposure'

#     def get_projected_exposure(self, obj):
#         return '{:.2f}%'.format(obj.projection.projected_exposure * 100)
#     get_projected_exposure.short_description = 'Proj Exposure'

#     def get_exposure(self, obj):
#         return '{:.2f}%'.format(self.build.get_exposure(obj)/self.build.num_lineups_created() * 100)
#     get_exposure.short_description = 'Exposure'


# @admin.register(models.PinnacleMatch)
# class PinnacleMatchAdmin(admin.ModelAdmin):
#     list_display = (
#         'event',
#         'home_participant',
#         'away_participant'
#     )
#     search_fields = (
#         'event',
#         'home_participant',
#         'away_participant'
#     )


# @admin.register(models.PinnacleMatchOdds)
# class PinnacleMatchOddsAdmin(admin.ModelAdmin):
#     list_display = (
#         'match',
#         'get_event',
#         'create_at',
#         'home_price',
#         'away_price',
#         'home_spread',
#         'away_spread'
#     )
#     search_fields = (
#         'match__event',
#         'match__home_participant',
#         'match__away_participant'
#     )
