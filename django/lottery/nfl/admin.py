import csv
import datetime
import traceback
from django.db.models.aggregates import Avg
import requests
import statistics
import tagulous.admin

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.http import HttpResponse
from django.db.models import Count, Case, When, F, FloatField
from django.db.models.functions import Coalesce, Cast
from django.utils.html import mark_safe, format_html
from django_admin_listfilter_dropdown.filters import DropdownFilter, RelatedDropdownFilter

from . import models
from . import tasks


class GameTotalFilter(SimpleListFilter):
    title = 'game total' # or use _('country') for translated title
    parameter_name = 'game_total'

    def lookups(self, request, model_admin):
        return (
            ('>=50', '50 or better'),
            ('>=49', '49 or better'),
            ('>=48', '48 or better'),
            ('>=47', '47 or better'),
            ('>=46', '46 or better'),
            ('>=45', '45 or better'),
            ('<45', 'lower than 45'),
            ('<44', 'lower than 44'),
            ('<43', 'lower than 43'),
            ('<42', 'lower than 42'),
            ('<41', 'lower than 41'),
            ('<40', 'lower than 40'),
        )

    def queryset(self, request, queryset):
        if self.value() == '>=50':
            return queryset.filter(game_total__gte=50)
        if self.value() == '>=49':
            return queryset.filter(game_total__gte=49)
        if self.value() == '>=48':
            return queryset.filter(game_total__gte=48)
        if self.value() == '>=47':
            return queryset.filter(game_total__gte=47)
        if self.value() == '>=46':
            return queryset.filter(game_total__gte=46)
        if self.value() == '>=45':
            return queryset.filter(game_total__gte=45)
        if self.value() == '<45':
            return queryset.filter(game_total__lt=45)
        if self.value() == '<44':
            return queryset.filter(game_total__lt=44)
        if self.value() == '<43':
            return queryset.filter(game_total__lt=43)
        if self.value() == '<42':
            return queryset.filter(game_total__lt=42)
        if self.value() == '<41':
            return queryset.filter(game_total__lt=41)
        if self.value() == '<40':
            return queryset.filter(game_total__lt=40)


class SpreadFilter(SimpleListFilter):
    title = 'spread' # or use _('country') for translated title
    parameter_name = 'spread'

    def lookups(self, request, model_admin):
        return (
            (-10, '-10 or better'),
            (-7, '-7 or better'),
            (-3, '-3 or better'),
            (3, '+3 or worse'),
            (7, '+7 or worse'),
            (10, '+10 or worse'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        elif int(self.value()) < 0:
            return queryset.filter(spread__lte=int(self.value()))
        return queryset.filter(spread__gte=int(self.value()))


class ProjectionFilter(SimpleListFilter):
    title = 'projection' # or use _('country') for translated title
    parameter_name = 'projection'

    def lookups(self, request, model_admin):
        return (
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


class NumGamesFilter(SimpleListFilter):
    title = 'num games'
    parameter_name = 'num_games'

    def lookups(self, request, model_admin):
        return (
            (2, '2'),
            (3, '3'),
            (4, '4'),
            (5, '5'),
            (6, '6'),
            (7, '7'),
            (8, '8'),
            (9, '9'),
            (10, '10'),
            (11, '11'),
            (12, '12'),
            (13, '13'),
            (14, '14'),
            (15, '15'),
            (16, '16'),
        )
    
    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.annotate(num_games=Count('slate_player__slate__games')).filter(num_games=self.value())


class PassCatchersOnlyFilter(SimpleListFilter):
    title = 'pass catchers only' # or use _('country') for translated title
    parameter_name = 'pass_catchers_only'

    def lookups(self, request, model_admin):
        return (
            (True, 'Only Pass Catchers'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(slate_player__site_pos__in=['WR', 'TE'])
        return queryset


class SkillPlayersOnlyFilter(SimpleListFilter):
    title = 'RB/WR/TE only' # or use _('country') for translated title
    parameter_name = 'skill_players_only'

    def lookups(self, request, model_admin):
        return (
            (True, 'Only RB/WR/TE'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(slate_player__site_pos__in=['RB', 'WR', 'TE'])
        return queryset


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
    )
    raw_id_fields = (
        'game',
    )


class GameInline(admin.TabularInline):
    model = models.Game
    extra = 0


class BacktestSlateInline(admin.TabularInline):
    model = models.BacktestSlate
    extra = 0
    raw_id_fields = (
        'slate',
    )
    fields = (
        'slate',
        'total_lineups',
        'total_optimals',
        'get_cash_rate',
        'get_pct_one_pct',
        'get_pct_half_pct',
        'top_score',
        'great_score',
        'great_build',
        'get_great_score_diff',
        'binked',
        'get_stacks_link',
        'get_lineups_link',
        'get_optimals_link',
    )
    readonly_fields = (
        'total_lineups',
        'total_optimals',
        'get_cash_rate',
        'get_pct_one_pct',
        'get_pct_half_pct',
        'top_score',
        'great_score',
        'great_build',
        'get_great_score_diff',
        'binked',
        'get_stacks_link',
        'get_lineups_link',
        'get_optimals_link',
    )

    def get_cash_rate(self, obj):
        if obj.total_cashes is None:
            return None
        return '{:.2f}'.format(obj.total_cashes/obj.total_lineups() * 100)
    get_cash_rate.short_description = 'Cash %'
    get_cash_rate.admin_order_field = 'total_cashes'

    def get_pct_one_pct(self, obj):
        if obj.total_one_pct is None:
            return None
        return '{:.2f}'.format(obj.total_one_pct/obj.total_lineups() * 100)
    get_pct_one_pct.short_description = '1%'
    get_pct_one_pct.admin_order_field = 'total_one_pct'

    def get_pct_half_pct(self, obj):
        if obj.total_half_pct is None:
            return None
        return '{:.2f}'.format(obj.total_half_pct/obj.total_lineups() * 100)
    get_pct_half_pct.short_description = '0.5%'
    get_pct_half_pct.admin_order_field = 'total_half_pct'

    def get_great_score_diff(self, obj):
        if obj.great_score is None or obj.top_score is None:
            return None
        return '{:.2f}'.format(obj.top_score - obj.great_score)
    get_great_score_diff.short_description = 'Diff'

    def get_stacks_link(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )
            if slate_build.num_stacks_created() > 0:
                return mark_safe('<a href="/admin/nfl/slatebuildstack/?build__id__exact={}">Stacks</a>'.format(slate_build.id))
            return None
        except models.SlateBuild.DoesNotExist:
            return None
    get_stacks_link.short_description = 'Stacks'

    def get_lineups_link(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )
            if slate_build.num_lineups_created() > 0:
                return mark_safe('<a href="/admin/nfl/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(slate_build.id))
            return None
        except models.SlateBuild.DoesNotExist:
            return None
    get_lineups_link.short_description = 'Lineups'

    def get_optimals_link(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )
            if slate_build.num_actuals_created() > 0:
                return mark_safe('<a href="/admin/nfl/slatebuildactualslineup/?build__id__exact={}">Optimals</a>'.format(slate_build.id))
            return None
        except models.SlateBuild.DoesNotExist:
            return None
    get_optimals_link.short_description = 'Optimals'


class GroupCreationRuleInline(admin.TabularInline):
    model = models.GroupCreationRule
    extra = 0


class SlateBuildGroupPlayerInline(admin.TabularInline):
    model = models.SlateBuildGroupPlayer
    raw_id_fields = ['slate_player']


@admin.register(models.Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = (
        'dk_name',
        'four4four_name',
        'awesemo_name',
        'fc_name',
        'tda_name',
        'fd_name',
        'fdraft_name',
        'ss_name',
        'yahoo_name',     
    )
    search_fields = (
        'dk_name',
        'four4four_name',
        'awesemo_name',
        'fc_name',
        'tda_name',
        'fd_name',
        'fdraft_name',
        'ss_name',
        'yahoo_name',     
    )


@admin.register(models.Slate)
class SlateAdmin(admin.ModelAdmin):
    list_display = (
        'datetime',
        'name',
        'week',
        'is_main_slate',
        'site',
        'get_num_games',
        'get_contest_link',
        'num_slate_players',
        'num_projected_players',
        'num_qbs',
        'num_rbs',
        'num_top_rbs',
        'median_rb_projection',
        'median_rb_ao',
        'num_in_play',
        'num_stack_only',
    )
    list_editable = (
        'name',
        'week',
        'is_main_slate',
    )
    list_filter = (
        'site',
        'is_main_slate',
        
    )
    actions = ['find_games', 'update_vegas', 'clear_slate_players']
    inlines = (SlateGameInline, )
    fields = (
        'datetime',
        'name',
        'is_main_slate',
        'site',
        'num_games',
        'num_slate_players',
        'num_projected_players',
        'num_qbs',
        'num_in_play',
        'num_stack_only',
    )
    readonly_fields = (
        'num_games',
        'num_slate_players',
        'num_projected_players',
        'num_qbs',
        'num_in_play',
        'num_stack_only',
    )
    
    def get_num_games(self, obj):
        game_ids = list(obj.games.all().values_list('game__id', flat=True))
        return mark_safe('<a href="/admin/nfl/game/?id__in={}">{}</a>'.format(','.join('{}'.format(x) for x in game_ids), obj.num_games()))
    get_num_games.short_description = '# Games'

    def get_contest_link(self, obj):
        if obj.contests.all().count() == 0:
            return None
        return mark_safe('<a href="/admin/nfl/contest/?id__exact={}">{}</a>'.format(obj.contests.all()[0].id, obj.contests.all()[0].name))
    get_contest_link.short_description = 'Contest'

    def update_vegas(self, request, queryset):
        for slate in queryset:
            slate.week.update_vegas()

        if queryset.count() == 1:
            messages.success(request, 'Odds and totals updated for {}.'.format(str(queryset[0])))
        else:
            messages.success(request, 'Odds and totals updated for {} slates.'.format(queryset.count()))
    update_vegas.short_description = 'Refresh odds and totals for selected slates'

    def find_games(self, request, queryset):
        for slate in queryset:
            if slate.is_main_slate:
                slate.find_games()
    find_games.short_description = 'Find games for selected slates'

    def clear_slate_players(self, request, queryset):
        for slate in queryset:
            slate.players.all().delete()
    clear_slate_players.short_description = 'Clear players from selected slates'


@admin.register(models.SlatePlayerImportSheet)
class SlatePlayerImportSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlatePlayerActualsSheet)
class SlatePlayerActualsSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlateProjectionSheet)
class SlateProjectionSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_all']

    def save_all(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_all.short_description = 'Save all selected projection sheets'


@admin.register(models.ContestImportSheet)
class ContestSheetAdmin(admin.ModelAdmin):
    list_display = (
        'site',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlatePlayer)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'team',
        'slate',
        'site_pos',
        'salary',
        'fantasy_points',
        'game',
    )
    list_editable = (
        'fantasy_points',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate__name', DropdownFilter),
        ('site_pos', DropdownFilter),
        'team')


@admin.register(models.SlatePlayerBuildExposure)
class SlatePlayerBuildExposureAdmin(admin.ModelAdmin):
    build = None
    list_display = (
        'name',
        'team',
        'site_pos',
        'salary',
        'get_projection',
        'get_adjusted_opportunity',
        'get_rb_group',
        'fantasy_points',
        'game',
        'get_exposure'
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        request.GET = request.GET.copy()
        build_id = request.GET.pop('build_id', None)
        position = request.GET.pop('pos', None)
        
        if build_id is not None and position is not None:
            self.build = models.SlateBuild.objects.get(id=build_id[0])
            queryset = self.model.objects.filter(slate=self.build.slate, projection__in_play=True, site_pos__in=position)
        
        return queryset.order_by('-salary')

    def get_projection(self, obj):
        if obj.projection is None:
            return None
        return obj.projection.projection
    get_projection.short_description = 'Proj'

    def get_adjusted_opportunity(self, obj):
        if obj.projection is None:
            return None
        return obj.projection.adjusted_opportunity
    get_adjusted_opportunity.short_description = 'AO'

    def get_rb_group(self, obj):
        if obj.projection is None:
            return None
        return obj.projection.rb_group
    get_rb_group.short_description = 'RBG'

    def get_exposure(self, obj):
        return '{:.2f}%'.format(self.build.get_exposure(obj)/self.build.num_lineups_created() * 100)
    get_exposure.short_description = 'Exposure'


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
        'adjusted_opportunity',
        'get_player_value',
        'balanced_projection',
        'get_balanced_player_value',
        'rb_group_value',
        'rb_group',
        'game_total',
        'team_total',
        'get_spread',
        'get_num_pass_catchers',
        'in_play',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'at_most_one_in_stack',
        'at_least_one_in_lineup',
        'at_least_two_in_lineup',
        'locked',
        'get_actual_score'
    )
    list_editable = (
        'in_play',
        'projection',
        'balanced_projection',
        'rb_group_value',
        'rb_group',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'locked',
        'at_most_one_in_stack',
        'at_least_one_in_lineup',
        'at_least_two_in_lineup',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        PassCatchersOnlyFilter,
        SkillPlayersOnlyFilter,
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        'slate_player__slate__is_main_slate',
        ('slate_player__slate__name', DropdownFilter),
        ProjectionFilter,
        'in_play',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'slate_player__slate__site',
        NumGamesFilter
    )
    raw_id_fields = ['slate_player']
    actions = ['find_in_play', 'find_stack_only', 'find_al1', 'find_al2', 'set_rb_group_values', 'group_rbs', 'balance_rb_exposures', 'export', 'add_to_stacks', 'remove_at_least_groups']
    
    # def get_queryset(self, request):
    #     qs = super(SlatePlayerProjectionAdmin, self).get_queryset(request)
    #     qs.annotate()
    #     return qs

    def get_slate(self, obj):
        return obj.slate_player.slate
    get_slate.short_description = 'Slate'
    get_slate.admin_order_field = 'slate_player__slate__name'

    def get_player_name(self, obj):
        return obj.slate_player.name
    get_player_name.short_description = 'Player'

    def get_player_salary(self, obj):
        return obj.slate_player.salary
    get_player_salary.short_description = 'Sal'
    get_player_salary.admin_order_field = 'slate_player__salary'

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
        game = obj.slate_player.get_slate_game()
        if game == None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__game'

    def get_spread(self, obj):
        game = obj.slate_player.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_spread if obj.slate_player.team == game.game.home_team else game.game.away_spread
    get_spread.short_description = 'Spread'

    def get_player_value(self, obj):
        return round(float(obj.projection)/(self.get_player_salary(obj)/1000.0), 2)
    get_player_value.short_description = 'Value'

    def get_balanced_player_value(self, obj):
        return round(float(obj.balanced_projection)/(self.get_player_salary(obj)/1000.0), 2)
    get_balanced_player_value.short_description = 'BV'

    def get_num_pass_catchers(self, obj):
        if obj.slate_player.site_pos == 'QB':
            return models.SlatePlayerProjection.objects.filter(
                slate_player__slate=obj.slate_player.slate,
                slate_player__team=obj.slate_player.team, 
                slate_player__site_pos__in=['WR', 'TE'], 
                qb_stack_only=True).count()
        return None
    get_num_pass_catchers.short_description = '# PC'

    def find_in_play(self, request, queryset):
        for player in queryset:
            player.find_in_play()
    find_in_play.short_description = 'Calculate in-play for selected players'

    def find_stack_only(self, request, queryset):
        for player in queryset:
            player.find_stack_only()
    find_stack_only.short_description = 'Calculate stack only for selected players'

    def find_al1(self, request, queryset):
        for player in queryset:
            player.find_al1()
    find_al1.short_description = 'Calculate AL1 for selected players'

    def find_al2(self, request, queryset):
        for player in queryset:
            player.find_al2()
    find_al2.short_description = 'Calculate AL2 for selected players'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

    def set_rb_group_values(self, request, queryset):
        for rb in queryset:
            rb.set_rb_group_value()
    set_rb_group_values.short_description = 'Set rb group values for selected players'

    def group_rbs(self, request, queryset):
        rb = queryset[0]
        rb.slate_player.slate.group_rbs()
    group_rbs.short_description = 'Create rb groups'

    def balance_rb_exposures(self, request, queryset):
        rb = queryset[0]
        rb.slate_player.slate.balance_rb_exposures()
    balance_rb_exposures.short_description = 'Create balanced RB projections for selected players'

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

    def add_to_stacks(self, request, queryset):
        queryset.update(in_play=True, qb_stack_only=True, opp_qb_stack_only=True)

    def remove_at_least_groups(self, request, queryset):
        queryset.update(at_least_one_in_lineup=False, at_least_two_in_lineup=False)
    remove_at_least_groups.short_description = 'Remove ALx designations from selected players'


@admin.register(models.SlateBuildGroup)
class SlateBuildGroupAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'min_from_group',
        'max_from_group',
        'num_players',
        'active',
    )
    list_editable = (
        'min_from_group',
        'max_from_group',
        'active',
    )
    inlines = [
        SlateBuildGroupPlayerInline
    ]


@admin.register(models.SlateBuildLineup)
class SlateBuildLineupAdmin(admin.ModelAdmin):
    list_display = (
        'get_game_stack',
        'get_game_stack_rank',
        'expected_lineup_order',
        'get_qb',
        'get_rb1',
        'get_rb2',
        'get_wr1',
        'get_wr2',
        'get_wr3',
        'get_te',
        'get_flex',
        'get_dst',
        'contains_top_projected_pass_catcher',
        'salary',
        'projection',
        'get_actual',
    )
    # list_filter = (
    #     ('build', RelatedDropdownFilter),
    #     ('build__slate', RelatedDropdownFilter),
    # )
    search_fields = (
        'qb__slate_player__name',
        'rb1__slate_player__name',
        'rb2__slate_player__name',
        'wr1__slate_player__name',
        'wr2__slate_player__name',
        'wr3__slate_player__name',
        'te__slate_player__name',
        'flex__slate_player__name',
        'dst__slate_player__name',
    )

    def get_queryset(self, request):
        return self.model.objects.all().annotate(
            actual_coalesced=Coalesce('actual', 0)
        )

    def get_game_stack(self, obj):
        if obj.stack is None:
            return obj.qb.slate_player.game
        return str(obj.stack)
    get_game_stack.short_description = 'Game Stack'

    def get_game_stack_rank(self, obj):
        if obj.stack is None:
            return None
        return obj.stack.rank
    get_game_stack_rank.short_description = 'Rnk'

    def get_name(self, obj):
        return obj.slate.slate
    get_name.short_description = 'Slate'

    def get_qb(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.qb.get_team_color(), obj.qb))
    get_qb.short_description = 'QB'

    def get_rb1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.rb1.get_team_color(), obj.rb1))
    get_rb1.short_description = 'RB1'

    def get_rb2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.rb2.get_team_color(), obj.rb2))
    get_rb2.short_description = 'RB2'

    def get_wr1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr1.get_team_color(), obj.wr1))
    get_wr1.short_description = 'WR1'

    def get_wr2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr2.get_team_color(), obj.wr2))
    get_wr2.short_description = 'WR2'

    def get_wr3(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr3.get_team_color(), obj.wr3))
    get_wr3.short_description = 'WR3'

    def get_te(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.te.get_team_color(), obj.te))
    get_te.short_description = 'TE'

    def get_flex(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex.get_team_color(), obj.flex))
    get_flex.short_description = 'FLEX'

    def get_dst(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.dst.get_team_color(), obj.dst))
    get_dst.short_description = 'DST'

    def get_actual(self, obj):
        return obj.actual
    get_actual.short_description = 'Actual'
    get_actual.admin_order_field = 'actual_coalesced'


@admin.register(models.SlateBuildActualsLineup)
class SlateBuildActualsLineupAdmin(admin.ModelAdmin):
    list_display = (
        'build',
        'get_game_stack',
        'get_game_stack_rank',
        'get_qb',
        'get_rb1',
        'get_rb2',
        'get_wr1',
        'get_wr2',
        'get_wr3',
        'get_te',
        'get_flex', 
        'get_dst',
        'contains_top_projected_pass_catcher',
        'contains_opp_top_projected_pass_catcher',
        'salary',
        'actual',
    )

    search_fields = (
        'qb__slate_player__name',
    )

    actions = ['export']

    def get_queryset(self, request):
        return self.model.objects.all().annotate(
            actual_coalesced=Coalesce('actual', 0)
        )

    def get_game_stack(self, obj):
        if obj.stack is None:
            return obj.qb.slate_player.game
        return str(obj.stack)
    get_game_stack.short_description = 'Game Stack'
    get_game_stack.admin_order_field = 'stack'

    def get_game_stack_rank(self, obj):
        if obj.stack is None:
            return None
        return obj.stack.rank
    get_game_stack_rank.short_description = 'Rnk'

    def get_name(self, obj):
        return obj.slate.slate
    get_name.short_description = 'Slate'

    def get_qb(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.qb.get_team_color(), obj.qb))
    get_qb.short_description = 'QB'

    def get_rb1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.rb1.get_team_color(), obj.rb1))
    get_rb1.short_description = 'RB1'

    def get_rb2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.rb2.get_team_color(), obj.rb2))
    get_rb2.short_description = 'RB2'

    def get_wr1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr1.get_team_color(), obj.wr1))
    get_wr1.short_description = 'WR1'

    def get_wr2(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr2.get_team_color(), obj.wr2))
    get_wr2.short_description = 'WR2'

    def get_wr3(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.wr3.get_team_color(), obj.wr3))
    get_wr3.short_description = 'WR3'

    def get_te(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.te.get_team_color(), obj.te))
    get_te.short_description = 'TE'

    def get_flex(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.flex.get_team_color(), obj.flex))
    get_flex.short_description = 'FLEX'

    def get_dst(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.dst.get_team_color(), obj.dst))
    get_dst.short_description = 'DST'

    def export(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=optimals.csv'

        lineup_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        lineup_writer.writerow([
            'slate', 
            'week',
            'qb', 
            'rb', 
            'rb', 
            'wr', 
            'wr',
            'wr', 
            'te', 
            'flex', 
            'dst', 
            'score',
            'salary',
            'flex_pos',
            'stack_rank',
            'qb_team', 
            'rb_team', 
            'rb_team', 
            'wr_team', 
            'wr_team',
            'wr_team', 
            'te_team', 
            'flex_team', 
            'dst_team', 
            'qb_opponent', 
            'rb_opponent', 
            'rb_opponent', 
            'wr_opponent', 
            'wr_opponent',
            'wr_opponent', 
            'te_opponent', 
            'flex_opponent', 
            'dst_opponent', 
            'qb_salary', 
            'rb_salary', 
            'rb_salary', 
            'wr_salary', 
            'wr_salary',
            'wr_salary', 
            'te_salary', 
            'flex_salary', 
            'dst_salary', 
            'qb_projection', 
            'rb_projection', 
            'rb_projection', 
            'wr_projection', 
            'wr_projection',
            'wr_projection', 
            'te_projection', 
            'flex_projection', 
            'dst_projection', 
            'qb_actual', 
            'rb_actual', 
            'rb_actual', 
            'wr_actual', 
            'wr_actual',
            'wr_actual', 
            'te_actual', 
            'flex_actual', 
            'dst_actual', 
            'qb_rank', 
            'rb_rank', 
            'rb_rank', 
            'wr_rank', 
            'wr_rank',
            'wr_rank', 
            'te_rank', 
            'flex_rank', 
            'dst_rank',
            'qb_game_total',
            'qb_team_total',
            'rb_game_total',
            'rb_team_total',
            'rb_game_total',
            'rb_team_total',
            'wr_game_total',
            'wr_team_total',
            'wr_game_total',
            'wr_team_total',
            'wr_game_total',
            'wr_team_total',
            'te_game_total',
            'te_team_total',
            'flex_game_total',
            'flex_team_total',
            'dst_game_total',
            'dst_team_total',
            'dst_spread',
            'top_pass_catcher_for_qb',
            'top_opp_pass_catchers_for_qb'
        ])

        for lineup in queryset:
            print(lineup.players)
            lineup_writer.writerow([
                lineup.build.slate.name,
                lineup.build.slate.week,
                lineup.qb.name,
                lineup.rb1.name,
                lineup.rb2.name,
                lineup.wr1.name,
                lineup.wr2.name,
                lineup.wr3.name,
                lineup.te.name,
                lineup.flex.name,
                lineup.dst.name,
                lineup.actual,
                lineup.salary,
                lineup.flex.slate_player.site_pos,
                lineup.stack.rank,
                lineup.qb.team,
                lineup.rb1.team,
                lineup.rb2.team,
                lineup.wr1.team,
                lineup.wr2.team,
                lineup.wr3.team,
                lineup.te.team,
                lineup.flex.team,
                lineup.dst.team,
                lineup.qb.get_opponent(),
                lineup.rb1.get_opponent(),
                lineup.rb2.get_opponent(),
                lineup.wr1.get_opponent(),
                lineup.wr2.get_opponent(),
                lineup.wr3.get_opponent(),
                lineup.te.get_opponent(),
                lineup.flex.get_opponent(),
                lineup.dst.get_opponent(),
                lineup.qb.salary,
                lineup.rb1.salary,
                lineup.rb2.salary,
                lineup.wr1.salary,
                lineup.wr2.salary,
                lineup.wr3.salary,
                lineup.te.salary,
                lineup.flex.salary,
                lineup.dst.salary,
                lineup.qb.projection,
                lineup.rb1.projection,
                lineup.rb2.projection,
                lineup.wr1.projection,
                lineup.wr2.projection,
                lineup.wr3.projection,
                lineup.te.projection,
                lineup.flex.projection,
                lineup.dst.projection,
                lineup.qb.slate_player.fantasy_points,
                lineup.rb1.slate_player.fantasy_points,
                lineup.rb2.slate_player.fantasy_points,
                lineup.wr1.slate_player.fantasy_points,
                lineup.wr2.slate_player.fantasy_points,
                lineup.wr3.slate_player.fantasy_points,
                lineup.te.slate_player.fantasy_points,
                lineup.flex.slate_player.fantasy_points,
                lineup.dst.slate_player.fantasy_points,
                lineup.qb.position_rank,
                lineup.rb1.position_rank,
                lineup.rb2.position_rank,
                lineup.wr1.position_rank,
                lineup.wr2.position_rank,
                lineup.wr3.position_rank,
                lineup.te.position_rank,
                lineup.flex.position_rank,
                lineup.dst.position_rank,
                lineup.qb.get_game_total(),
                lineup.qb.get_team_total(),
                lineup.rb1.get_game_total(),
                lineup.rb1.get_team_total(),
                lineup.rb2.get_game_total(),
                lineup.rb2.get_team_total(),
                lineup.wr1.get_game_total(),
                lineup.wr1.get_team_total(),
                lineup.wr2.get_game_total(),
                lineup.wr2.get_team_total(),
                lineup.wr3.get_game_total(),
                lineup.wr3.get_team_total(),
                lineup.te.get_game_total(),
                lineup.te.get_team_total(),
                lineup.flex.get_game_total(),
                lineup.flex.get_team_total(),
                lineup.dst.get_game_total(),
                lineup.dst.get_team_total(),
                lineup.dst.get_spread(),
                lineup.contains_top_projected_pass_catcher(),
                lineup.contains_opp_top_projected_pass_catcher()
            ])
        
        return response
    export.short_description = 'Export selected lineups'


@admin.register(models.SlateBuildStack)
class SlateBuildStackAdmin(admin.ModelAdmin):
    list_display = (
        'get_stack_name',
        'rank',
        'get_qb',
        'get_player_1',
        'get_player_2',
        'get_opp_player',
        'salary',
        'projection',
        'contains_top_projected_pass_catcher',
        'count',
        'times_used',
        'actual',
        'get_lineups_link'
    )

    list_editable = (
        'count',
    )

    actions = [
        'get_actual_scores'
    ]

    def get_stack_name(self, obj):
        return '{} Stack {}'.format(obj.qb.name, obj.build_order)
    get_stack_name.short_description = 'Stack'

    def get_qb(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.qb.get_team_color(), obj.qb))
    get_qb.short_description = 'QB'

    def get_player_1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.player_1.get_team_color(), obj.player_1))
    get_player_1.short_description = 'Player 1'

    def get_player_2(self, obj):
        if obj.player_2 is None:
            return 'None'
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.player_2.get_team_color(), obj.player_2))
    get_player_2.short_description = 'Player 2'

    def get_opp_player(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.opp_player.get_team_color(), obj.opp_player))
    get_opp_player.short_description = 'Opposing Player'

    def get_lineups_link(self, obj):
        if obj.times_used > 0:
            return mark_safe('<a href="/admin/nfl/slatebuildlineup/?stack__id__exact={}">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Lineups'

    def get_actuals_link(self, obj):
        if obj.num_actuals_created() > 0:
            return mark_safe('<a href="/admin/nfl/slatebuildactualslineup/?stack__id__exact={}">Actuals</a>'.format(obj.id))
        return 'None'
    get_actuals_link.short_description = 'Actuals'

    def get_actual_scores(self, request, queryset):
        for stack in queryset:
            stack.calc_actual_score()
    get_actual_scores.short_description = 'Get actual scores for selected stacks'


@admin.register(models.SlateBuild)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    list_per_page = 34
    list_display = (
        'created',
        'slate',
        'used_in_contests',
        'configuration',
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
        'top_optimal_score',
        'get_stacks_link',
        'get_lineups_link',
        'get_actuals_link',
        # 'get_qb_exposures_link',
        # 'get_rb_exposures_link',
        # 'get_wr_exposures_link',
        # 'get_te_exposures_link',
        # 'get_dst_exposures_link',
        'get_pct_complete',
        'get_optimal_pct_complete',
    )
    list_editable = (
        'used_in_contests',
        'configuration',
        'total_lineups',
        'slate',
    )
    list_filter = (
        ('configuration', RelatedDropdownFilter),
        ('slate__name', DropdownFilter),
        ('slate__week', RelatedDropdownFilter),
        'slate__site',
        'used_in_contests',
        'great_build',
    )
    search_fields = ('slate__name',)
    actions = [
        'create_stacks', 
        'clean_stacks',
        'clean_stacks_50',
        'rank_stacks',
        'build', 
        'find_expected_lineup_order',
        'export_lineups', 
        'export_for_upload', 
        'get_actual_scores', 
        'find_optimal_lineups',
        'duplicate_builds', 
        'delete_lineups', 
        'clear_unused_stacks', 
        'clear_data']

    def create_stacks(self, request, queryset):
        for b in queryset:
            b.create_stacks()
    create_stacks.short_description = 'Create stacks for selected builds'

    def clean_stacks(self, request, queryset):
        for b in queryset:
            if b.slate.site == 'fanduel':
                b.clean_stacks(80)
            elif b.slate.site == 'draftkings':
                b.clean_stacks(90)
    clean_stacks.short_description = 'Clean stacks to top 80 stacks (80 FD/90 DK)'

    def clean_stacks_50(self, request, queryset):
        for b in queryset:
            if b.slate.site == 'fanduel':
                b.clean_stacks(50)
            elif b.slate.site == 'draftkings':
                b.clean_stacks(50)
    clean_stacks_50.short_description = 'Clean stacks to top 50 stacks (50 both)'

    def rank_stacks(self, request, queryset):
        for build in queryset:
            stacks = build.stacks.all().order_by('-projection')
            for (index, stack) in enumerate(stacks):
                stack.rank = index + 1
                stack.save()

    def build(self, request, queryset):
        for b in queryset:
            b.build()
    build.short_description = 'Generate lineups for selected builds'

    def find_expected_lineup_order(self, request, queryset): 
        for build in queryset:
            for (index, lineup) in enumerate(build.lineups.all().order_by('order_number', '-qb__projection')):
                lineup.expected_lineup_order = index + 1
                lineup.save()
    find_expected_lineup_order.short_description = 'Find expected lineup order'

    def export_lineups(self, request, queryset):
        if queryset.count() > 1:
            return
        
        build = queryset[0]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}-{}-lineups.csv'.format(build.slate.name, build.created)

        build_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for (index, lineup) in enumerate(build.lineups.all().order_by('order_number', '-qb__projection')):
            rbs = lineup.get_rbs_by_salary()
            wrs = lineup.get_wrs_by_salary()
            tes = lineup.get_tes_by_salary()
            
            if lineup.get_num_rbs() > 2:
                flex = rbs[2]
            elif lineup.get_num_wrs() > 3:
                flex = wrs[3]
            else:
                flex = tes[1]
            
            row = [
                lineup.order_number,
                str(build.slate),
                lineup.projection,
                lineup.actual,
                lineup.qb.name,
                rbs[0].name,
                rbs[1].name,
                wrs[0].name,
                wrs[1].name,
                wrs[2].name,
                tes[0].name,
                flex.name,
                lineup.dst.name,
                lineup.qb.team,
                rbs[0].team,
                rbs[1].team,
                wrs[0].team,
                wrs[1].team,
                wrs[2].team,
                tes[0].team,
                flex.team,
                lineup.dst.team,
                lineup.qb.get_game(),
                rbs[0].get_game(),
                rbs[1].get_game(),
                wrs[0].get_game(),
                wrs[1].get_game(),
                wrs[2].get_game(),
                tes[0].get_game(),
                flex.get_game(),
                lineup.dst.get_game(),
                lineup.qb.position,
                rbs[0].position,
                rbs[1].position,
                wrs[0].position,
                wrs[1].position,
                wrs[2].position,
                tes[0].position,
                flex.position,
                lineup.dst.position,
                lineup.qb.salary,
                rbs[0].salary,
                rbs[1].salary,
                wrs[0].salary,
                wrs[1].salary,
                wrs[2].salary,
                tes[0].salary,
                flex.salary,
                lineup.dst.salary,
                lineup.qb.projection,
                rbs[0].projection,
                rbs[1].projection,
                wrs[0].projection,
                wrs[1].projection,
                wrs[2].projection,
                tes[0].projection,
                flex.projection,
                lineup.dst.projection,
                lineup.qb.get_opponent(),
                rbs[0].get_opponent(),
                rbs[1].get_opponent(),
                wrs[0].get_opponent(),
                wrs[1].get_opponent(),
                wrs[2].get_opponent(),
                tes[0].get_opponent(),
                flex.get_opponent(),
                lineup.dst.get_opponent(),
                lineup.qb.stack_only,
                rbs[0].stack_only,
                rbs[1].stack_only,
                wrs[0].stack_only,
                wrs[1].stack_only,
                wrs[2].stack_only,
                tes[0].stack_only,
                flex.stack_only,
                lineup.dst.stack_only,
                lineup.salary
            ]
            build_writer.writerow(row)

            print('{} of {} lineups complete'.format(index+1, build.lineups.all().count()))

        return response
    export_lineups.short_description = 'Export lineups for selected builds'            

    def export_for_upload(self, request, queryset):
        if queryset.count() > 1:
            return
        
        build = queryset[0]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename={}-{}_upload.csv'.format(build.slate.name, build.created)


        build_writer = csv.writer(response, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        build_writer.writerow(['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DEF'])

        for (index, lineup) in enumerate(build.lineups.all().order_by('order_number', '-qb__projection')):
            rbs = lineup.get_rbs()
            wrs = lineup.get_wrs()
            tes = lineup.get_tes()
            
            if lineup.get_num_rbs() > 2:
                flex = rbs[2]
            elif lineup.get_num_wrs() > 3:
                flex = wrs[3]
            else:
                flex = tes[1]
            
            if build.slate.site == 'fanduel':
                row = [
                    '{}:{}'.format(lineup.qb.slate_player.player_id, lineup.qb.name),
                    '{}:{}'.format(rbs[0].slate_player.player_id, rbs[0].name),
                    '{}:{}'.format(rbs[1].slate_player.player_id, rbs[1].name),
                    '{}:{}'.format(wrs[0].slate_player.player_id, wrs[0].name),
                    '{}:{}'.format(wrs[1].slate_player.player_id, wrs[1].name),
                    '{}:{}'.format(wrs[2].slate_player.player_id, wrs[2].name),
                    '{}:{}'.format(tes[0].slate_player.player_id, tes[0].name),
                    '{}:{}'.format(flex.slate_player.player_id, flex.name),
                    '{}:{}'.format(lineup.dst.slate_player.player_id, lineup.dst.name)
                ]
            elif build.slate.site == 'draftkings':
                row = [
                    '{1} ({0})'.format(lineup.qb.slate_player.player_id, lineup.qb.name),
                    '{1} ({0})'.format(rbs[0].slate_player.player_id, rbs[0].name),
                    '{1} ({0})'.format(rbs[1].slate_player.player_id, rbs[1].name),
                    '{1} ({0})'.format(wrs[0].slate_player.player_id, wrs[0].name),
                    '{1} ({0})'.format(wrs[1].slate_player.player_id, wrs[1].name),
                    '{1} ({0})'.format(wrs[2].slate_player.player_id, wrs[2].name),
                    '{1} ({0})'.format(tes[0].slate_player.player_id, tes[0].name),
                    '{1} ({0})'.format(flex.slate_player.player_id, flex.name),
                    '{1} ({0})'.format(lineup.dst.slate_player.player_id, lineup.dst.name)
                ]
            else:
                raise Exception('{} is not a supported dfs site.'.format(build.slate.site)) 

            build_writer.writerow(row)
            print('{} of {} lineups complete'.format(index+1, build.lineups.all().count()))
        
        return response
    export_for_upload.short_description = 'Export lineups for upload'

    def get_actual_scores(self, request, queryset):
        for build in queryset:
            build.get_actual_scores()
    get_actual_scores.short_description = 'Get actual scores for selected builds'

    def duplicate_builds(self, request, queryset):
        for build in queryset:
            new_build = models.SlateBuild.objects.create(
                slate=build.slate,
                configuration=build.configuration,
                lineup_start_number=build.lineup_start_number,
                total_lineups=build.total_lineups,
                notes=build.notes,
                tag=build.tag
            )

            for stack in build.stacks.all():
                stack.id = None
                stack.build = new_build
                stack.save()
    duplicate_builds.short_description = 'Duplicate selected builds'

    def delete_lineups(self, request, queryset):
        for build in queryset:
            build.lineups.all().delete()
    delete_lineups.short_description = 'Delete lineups from selected builds'

    def clear_unused_stacks(self, request, queryset):
        for build in queryset:
            build.stacks.filter(count=0).delete()
    clear_unused_stacks.short_description = 'Clear unused stacks from selected builds'

    def build_actuals(self, request, queryset):
        for b in queryset:
            b.build(use_actuals=True)
    build_actuals.short_description = 'Generate actuals for selected builds'

    def clear_data(self, request, queryset):
        for build in queryset:
            build.total_cashes = None
            build.total_one_pct = 0
            build.total_half_pct = 0
            build.top_score = None
            build.binked = False
            build.save()
    clear_data.short_description = 'Clear data from selected builds'

    def find_optimal_lineups(self, request, queryset):
        for build in queryset:
            tasks.build_optimals.delay(build.id)
            messages.success(request, 'Building optimals for {}. Refresh page to check progress'.format(build))
    find_optimal_lineups.short_description = 'Generate optimal lineups for selected builds'

    def get_pct_one_pct(self, obj):
        if obj.total_one_pct is None:
            return 0
        return '{:.2f}'.format(obj.total_one_pct/obj.total_lineups * 100)
    get_pct_one_pct.short_description = '1%'
    get_pct_one_pct.admin_order_field = 'total_one_pct'

    def get_pct_half_pct(self, obj):
        if obj.total_half_pct is None:
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

    def get_stacks_link(self, obj):
        if obj.num_stacks_created() > 0:
            return mark_safe('<a href="/admin/nfl/slatebuildstack/?build__id__exact={}">Stacks</a>'.format(obj.id))
        return 'None'
    get_stacks_link.short_description = 'Stacks'

    def get_lineups_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nfl/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(obj.id))
        return 'None'
    get_lineups_link.short_description = 'Lineups'

    def get_actuals_link(self, obj):
        if obj.num_actuals_created() > 0:
            return mark_safe('<a href="/admin/nfl/slatebuildactualslineup/?build__id__exact={}">Opt</a>'.format(obj.id))
        return 'None'
    get_actuals_link.short_description = 'Opt'

    def get_qb_exposures_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=QB">Exp</a>'.format(obj.id))
        return 'None'
    get_qb_exposures_link.short_description = 'QB'

    def get_rb_exposures_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=RB">Exp</a>'.format(obj.id))
        return 'None'
    get_rb_exposures_link.short_description = 'RB'

    def get_wr_exposures_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=WR">Exp</a>'.format(obj.id))
        return 'None'
    get_wr_exposures_link.short_description = 'WR'

    def get_te_exposures_link(self, obj):
        if obj.num_lineups_created() > 0:
            return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=TE">Exp</a>'.format(obj.id))
        return 'None'
    get_te_exposures_link.short_description = 'TE'

    def get_dst_exposures_link(self, obj):
        if obj.num_lineups_created() > 0:
            if obj.slate.site == 'fanduel':
                return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=D">Exp</a>'.format(obj.id))
            elif obj.slate.site == 'draftkings':
                return mark_safe('<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=DST">Exp</a>'.format(obj.id))
        return 'None'
    get_dst_exposures_link.short_description = 'DST'

    def get_el(self, obj):
        if obj.total_cashes == None:
            return None
        lineups = obj.lineups.all().order_by('-actual')
        return lineups[0].expected_lineup_order if lineups.count() > 0 else None
    get_el.short_description = 'EL'

    def get_pct_complete(self, obj):
        return format_html(
            '''
            <progress value="{0}" max="100"></progress>
            <span style="font-weight:bold">{0}%</span>
            ''',
            float(obj.pct_complete) * 100.0
        )
    get_pct_complete.short_description = '% complete'
    get_pct_complete.admin_order_field = 'pct_complete'

    def get_optimal_pct_complete(self, obj):
        return format_html(
            '''
            <progress value="{0}" max="100"></progress>
            <span style="font-weight:bold">{0}%</span>
            ''',
            float(obj.optimals_pct_complete) * 100.0
        )
    get_optimal_pct_complete.short_description = '% opt done'
    get_optimal_pct_complete.admin_order_field = 'optimals_pct_complete'


@admin.register(models.BuildPlayerProjection)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'projection',
        'adjusted_opportunity',
        'get_player_value',
        'balanced_projection',
        'get_balanced_player_value',
        'rb_group_value',
        'rb_group',
        'game_total',
        'team_total',
        'get_spread',
        'get_num_pass_catchers',
        'in_play',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'at_most_one_in_stack',
        'at_least_one_in_lineup',
        'at_least_two_in_lineup',
        'locked',
        'get_actual_score'
    )
    list_editable = (
        'in_play',
        'projection',
        'balanced_projection',
        'rb_group_value',
        'rb_group',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'locked',
        'at_most_one_in_stack',
        'at_least_one_in_lineup',
        'at_least_two_in_lineup',
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        PassCatchersOnlyFilter,
        SkillPlayersOnlyFilter,
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        'slate_player__slate__is_main_slate',
        ('slate_player__slate__name', DropdownFilter),
        ProjectionFilter,
        'in_play',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'slate_player__slate__site',
        NumGamesFilter
    )
    raw_id_fields = ['slate_player']
    actions = ['find_in_play', 'find_stack_only', 'find_al1', 'find_al2', 'set_rb_group_values', 'group_rbs', 'balance_rb_exposures', 'export', 'add_to_stacks', 'remove_at_least_groups']
    
    # def get_queryset(self, request):
    #     qs = super(SlatePlayerProjectionAdmin, self).get_queryset(request)
    #     qs.annotate()
    #     return qs

    def get_slate(self, obj):
        return obj.slate_player.slate
    get_slate.short_description = 'Slate'
    get_slate.admin_order_field = 'slate_player__slate__name'

    def get_player_name(self, obj):
        return obj.slate_player.name
    get_player_name.short_description = 'Player'

    def get_player_salary(self, obj):
        return obj.slate_player.salary
    get_player_salary.short_description = 'Sal'
    get_player_salary.admin_order_field = 'slate_player__salary'

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
        game = obj.slate_player.get_slate_game()
        if game == None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__game'

    def get_spread(self, obj):
        game = obj.slate_player.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_spread if obj.slate_player.team == game.game.home_team else game.game.away_spread
    get_spread.short_description = 'Spread'

    def get_player_value(self, obj):
        return round(float(obj.projection)/(self.get_player_salary(obj)/1000.0), 2)
    get_player_value.short_description = 'Value'

    def get_balanced_player_value(self, obj):
        return round(float(obj.balanced_projection)/(self.get_player_salary(obj)/1000.0), 2)
    get_balanced_player_value.short_description = 'BV'

    def get_num_pass_catchers(self, obj):
        if obj.slate_player.site_pos == 'QB':
            return models.SlatePlayerProjection.objects.filter(
                slate_player__slate=obj.slate_player.slate,
                slate_player__team=obj.slate_player.team, 
                slate_player__site_pos__in=['WR', 'TE'], 
                qb_stack_only=True).count()
        return None
    get_num_pass_catchers.short_description = '# PC'

    def find_in_play(self, request, queryset):
        for player in queryset:
            player.find_in_play()
    find_in_play.short_description = 'Calculate in-play for selected players'

    def find_stack_only(self, request, queryset):
        for player in queryset:
            player.find_stack_only()
    find_stack_only.short_description = 'Calculate stack only for selected players'

    def find_al1(self, request, queryset):
        for player in queryset:
            player.find_al1()
    find_al1.short_description = 'Calculate AL1 for selected players'

    def find_al2(self, request, queryset):
        for player in queryset:
            player.find_al2()
    find_al2.short_description = 'Calculate AL2 for selected players'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

    def set_rb_group_values(self, request, queryset):
        for rb in queryset:
            rb.set_rb_group_value()
    set_rb_group_values.short_description = 'Set rb group values for selected players'

    def group_rbs(self, request, queryset):
        rb = queryset[0]
        rb.slate_player.slate.group_rbs()
    group_rbs.short_description = 'Create rb groups'

    def balance_rb_exposures(self, request, queryset):
        rb = queryset[0]
        rb.slate_player.slate.balance_rb_exposures()
    balance_rb_exposures.short_description = 'Create balanced RB projections for selected players'

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

    def add_to_stacks(self, request, queryset):
        queryset.update(in_play=True, qb_stack_only=True, opp_qb_stack_only=True)

    def remove_at_least_groups(self, request, queryset):
        queryset.update(at_least_one_in_lineup=False, at_least_two_in_lineup=False)
    remove_at_least_groups.short_description = 'Remove ALx designations from selected players'


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


@admin.register(models.SlateBuildConfig)
class ConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'site',
        'game_stack_size',
        'num_players_vs_dst',
        'max_dst_exposure',
        'allow_rbs_from_same_game',
        'allow_rb_qb_from_same_team',
        'allow_rb_qb_from_opp_team',
        'allow_dst_rb_stack',
        'randomness',
        'use_similarity_scores',
        'use_iseo',
        'use_iseo_plus',
        'uniques',
        'min_salary',
        'allow_rb_as_flex',
        'allow_wr_as_flex',
        'allow_te_as_flex',
        'allow_rb_in_qb_stack',
        'allow_wr_in_qb_stack',
        'allow_te_in_qb_stack',
        'allow_rb_in_opp_qb_stack',
        'allow_wr_in_opp_qb_stack',
        'allow_te_in_opp_qb_stack'
    ]

    list_filter = [
        'site',
        'allow_rbs_from_same_game',
        'allow_rb_qb_from_same_team',
        'allow_rb_qb_from_opp_team',
        'allow_dst_rb_stack',
        'use_similarity_scores',
        'uniques',
        'min_salary',
        'allow_rb_as_flex',
        'allow_wr_as_flex',
        'allow_te_as_flex',
        'allow_rb_in_qb_stack',
        'allow_wr_in_qb_stack',
        'allow_te_in_qb_stack',
        'allow_rb_in_opp_qb_stack',
        'allow_wr_in_opp_qb_stack',
        'allow_te_in_opp_qb_stack'
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


@admin.register(models.LineupConstructionRule)
class LineupConstructionRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'site',
    )
    inlines = [
        GroupCreationRuleInline
    ]


@admin.register(models.StackConstructionRule)
class StackConstructionRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'site',
        'lock_top_pc',
        'top_pc_margin',
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
            week.update_vegas()

        if queryset.count() == 1:
            messages.success(request, 'Odds and totals updated for {}.'.format(str(queryset[0])))
        else:
            messages.success(request, 'Odds and totals updated for {} weeks.'.format(queryset.count()))
    
    def get_num_games(self, obj):
        return mark_safe('<a href="/admin/nfl/game/?week__id__exact={}">{}</a>'.format(obj.id, obj.games.all().count()))
    get_num_games.short_description = '# Games'


@admin.register(models.Backtest)
class BacktestAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'created',
        'site',
        'lineup_config',
        'in_play_criteria',
        'lineup_construction',
        'stack_construction',
        'status',
        'get_pct_complete',
        'get_optimals_pct_complete',
        'error_message',
        'median_cash_rate',
        'median_one_pct_rate',
        'median_half_pct_rate',
        'great_build_rate',
        'optimal_build_rate'
    )
    readonly_fields = (
        'status',
        'pct_complete',
        'total_lineups',
        'total_optimals',
        'completed_lineups',
        'optimals_pct_complete',
        'error_message',
        
    )
    raw_id_fields = (
        'lineup_config',
        'in_play_criteria',
        'lineup_construction',
        'stack_construction',
    )
    inlines = [BacktestSlateInline]
    actions = [
        'addMainSlates',
        'add2019MainSlates',
        'add2020MainSlates',
        'execute',
        'find_optimals',
    ]

    def get_queryset(self, request):
        qs = super(BacktestAdmin, self).get_queryset(request)

        qs = qs.annotate(median_cashed=models.Median('slates__builds__total_cashes'))
        qs = qs.annotate(median_cashed_coalesced=Coalesce('median_cashed', 0))
        qs = qs.annotate(median_cash_rate=models.Median('slates__builds__total_cashes')/Avg('lineups_per_slate'))
        qs = qs.annotate(median_cash_rate_coalesced=Coalesce('median_cash_rate', 0))

        qs = qs.annotate(median_one_pct=models.Median('slates__builds__total_one_pct'))
        qs = qs.annotate(median_one_pct_coalesced=Coalesce('median_one_pct', 0))
        qs = qs.annotate(median_one_pct_rate=models.Median('slates__builds__total_one_pct')/Avg('lineups_per_slate'))
        qs = qs.annotate(median_one_pct_rate_coalesced=Coalesce('median_one_pct_rate', 0))

        qs = qs.annotate(median_half_pct=models.Median('slates__builds__total_half_pct'))
        qs = qs.annotate(median_half_pct_coalesced=Coalesce('median_half_pct', 0))
        qs = qs.annotate(median_half_pct_rate=models.Median('slates__builds__total_half_pct')/Avg('lineups_per_slate'))
        qs = qs.annotate(median_half_pct_rate_coalesced=Coalesce('median_half_pct_rate', 0))

        qs = qs.annotate(num_slates=Count('slates'))
        qs = qs.annotate(num_slates_coalesced=Coalesce('num_slates', 0))

        qs = qs.annotate(great_builds=Count(
            Case(When(slates__builds__great_build=True,
                        then=1))
        ))
        qs = qs.annotate(great_builds_coalesced=Coalesce('great_builds', 0))

        qs = qs.annotate(great_build_rate=Case(
            When(num_slates=0), 
            default=Cast(F('great_builds'), FloatField()) / Cast(F('num_slates'), FloatField())
        ))
        qs = qs.annotate(great_build_rate_coalesced=Coalesce('great_build_rate', 0))

        qs = qs.annotate(optimal_builds=Count(
            Case(When(slates__builds__total_optimals__gte=20,
                        then=1))
        ))
        qs = qs.annotate(optimal_builds_coalesced=Coalesce('optimal_builds', 0))

        qs = qs.annotate(optimal_build_rate=Case(
            When(num_slates=0), 
            default=Cast(F('optimal_builds'), FloatField()) / Cast(F('num_slates'), FloatField())
        ))
        # qs = qs.annotate(optimal_build_rate=Cast(F('optimal_builds'), FloatField()) / Cast(F('num_slates'), FloatField()))
        qs = qs.annotate(optimal_build_rate_coalesced=Coalesce('optimal_build_rate', 0))

        return qs

    def get_pct_complete(self, obj):
        return format_html(
            '''
            <progress value="{0}" max="100"></progress>
            <span style="font-weight:bold">{0}%</span>
            ''',
            float(obj.pct_complete) * 100.0
        )
    get_pct_complete.short_description = '% complete'
    get_pct_complete.admin_order_field = 'pct_complete'

    def get_optimals_pct_complete(self, obj):
        return format_html(
            '''
            <progress value="{0}" max="100"></progress>
            <span style="font-weight:bold">{0}%</span>
            ''',
            float(obj.optimals_pct_complete) * 100.0
        )
    get_optimals_pct_complete.short_description = '% opt done'
    get_optimals_pct_complete.admin_order_field = 'optimals_pct_complete'

    def median_cash_rate(self, obj):
        if obj.median_cash_rate is None:
            return None
        return '{:.2f}%'.format(obj.median_cash_rate * 100)
    median_cash_rate.short_description = 'cash'
    median_cash_rate.admin_order_field = 'median_cash_rate_coalesced'

    def median_one_pct_rate(self, obj):
        if obj.median_one_pct_rate is None:
            return None
        return '{:.2f}%'.format(obj.median_one_pct_rate * 100)
    median_one_pct_rate.short_description = '1%'
    median_one_pct_rate.admin_order_field = 'median_one_pct_rate_coalesced'

    def median_half_pct_rate(self, obj):
        if obj.median_half_pct_rate is None:
            return None
        return '{:.2f}%'.format(obj.median_half_pct_rate * 100)
    median_half_pct_rate.short_description = '0.5%'
    median_half_pct_rate.admin_order_field = 'median_half_pct_rate_coalesced'

    def great_build_rate(self, obj):
        if obj.great_build_rate is None:
            return None
        return '{:.2f}%'.format(obj.great_build_rate * 100)
    great_build_rate.short_description = 'gb'
    great_build_rate.admin_order_field = 'great_build_rate_coalesced'

    def optimal_build_rate(self, obj):
        if obj.optimal_build_rate is None:
            return None
        return '{:.2f}%'.format(obj.optimal_build_rate * 100)
    optimal_build_rate.short_description = 'opt'
    optimal_build_rate.admin_order_field = 'optimal_build_rate_coalesced'
    
    def addMainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True)):
                (backtest_slate, created) = models.BacktestSlate.objects.get_or_create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    addMainSlates.short_description = 'Add all main slates to selected backtests'
    
    def add2019MainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2019)):
                (backtest_slate, created) = models.BacktestSlate.objects.get_or_create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2019MainSlates.short_description = 'Add all 2019 main slates to selected backtests'
    
    def add2020MainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2020)):
                (backtest_slate, created) = models.BacktestSlate.objects.get_or_create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2020MainSlates.short_description = 'Add all 2020 main slates to selected backtests'

    def execute(self, request, queryset):
        for backtest in queryset:
            tasks.run_backtest.delay(backtest.id)
            messages.success(request, 'Executing {}. Refresh page to check progress'.format(backtest.name))
    execute.short_description = 'Run selected backtests'

    def find_optimals(self, request, queryset):
        for backtest in queryset:
            tasks.find_optimals_for_backtest.delay(backtest.id)
            messages.success(request, 'Finding optimals for {}. Refresh page to check progress'.format(backtest.name))
    find_optimals.short_description = 'Find optimals for selected backtests'
