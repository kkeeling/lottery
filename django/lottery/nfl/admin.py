import csv
import datetime
import decimal
import traceback
import numpy
import os

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.http import HttpResponse
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

from . import models
from . import tasks

# Filters

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


class NumSlatesFilter(SimpleListFilter):
    title = '# slates' # or use _('country') for translated title
    parameter_name = 'game_total'

    def lookups(self, request, model_admin):
        return (
            (17, '17'),
            (34, '34'),
            (136, '136'),
            (170, '170'),
            (340, '340'),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(num_slates=Count('slates'))

        if self.value():
            return queryset.filter(num_slates=self.value())
        return queryset


# Forms


class ProjectionListForm(forms.ModelForm):
	projection = forms.DecimalField(widget=forms.TextInput(attrs={'style':'width:50px;'}))
	balanced_projection = forms.DecimalField(widget=forms.TextInput(attrs={'style':'width:50px;'}))
	rb_group = forms.DecimalField(widget=forms.TextInput(attrs={'style':'width:35px;'}))


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
        'ownership',
        'ownership_zscore',
        'rating',
    )
    raw_id_fields = (
        'game',
    )
    readonly_fields = (
        'zscore',
        'get_game_total',
        'ownership',
        'ownership_zscore',
        'rating',
    )

    def get_game_total(self, obj):
        return obj.game_total()
    get_game_total.short_description = 'Total'


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
        'get_tl',
        'get_to',
        'get_cash_rate',
        'get_pct_one_pct',
        'get_pct_half_pct',
        'get_el',
        'get_ts',
        'great_score',
        'get_great_score_diff',
        'bink_score',
        'get_great_build',
        'get_binked',
        'get_links',
        'get_exposures_links',
    )
    readonly_fields = (
        'get_tl',
        'get_to',
        'get_cash_rate',
        'get_pct_one_pct',
        'get_pct_half_pct',
        'get_el',
        'get_ts',
        'great_score',
        'bink_score',
        'get_great_build',
        'get_great_score_diff',
        'get_binked',
        'get_links',
        'get_exposures_links',
    )

    def get_tl(self, obj):
        return obj.total_lineups
    get_tl.short_description = 'TL'

    def get_to(self, obj):
        return obj.total_optimals
    get_to.short_description = 'TO'

    def get_binked(self, obj):
        return obj.binked
    get_binked.short_description = 'Bink?'
    get_binked.boolean = True

    def get_great_build(self, obj):
        return obj.great_build
    get_great_build.short_description = 'GB?'
    get_great_build.boolean = True

    def get_cash_rate(self, obj):
        if obj.total_cashes is None or obj.total_lineups == 0:
            return None
        return '{:.2f}'.format(obj.total_cashes/obj.total_lineups * 100)
    get_cash_rate.short_description = 'Cash'
    get_cash_rate.admin_order_field = 'total_cashes'

    def get_pct_one_pct(self, obj):
        if obj.total_one_pct is None or obj.total_lineups == 0:
            return None
        return '{:.2f}'.format(obj.total_one_pct/obj.total_lineups * 100)
    get_pct_one_pct.short_description = '1%'
    get_pct_one_pct.admin_order_field = 'total_one_pct'

    def get_pct_half_pct(self, obj):
        if obj.total_half_pct is None or obj.total_lineups == 0:
            return None
        return '{:.2f}'.format(obj.total_half_pct/obj.total_lineups * 100)
    get_pct_half_pct.short_description = '0.5%'
    get_pct_half_pct.admin_order_field = 'total_half_pct'

    def get_ts(self, obj):
        return obj.top_score
    get_ts.short_description = 'TS'

    def get_gs(self, obj):
        return obj.great_score
    get_gs.short_description = 'GS'

    def get_great_score_diff(self, obj):
        if obj.great_score is None or obj.top_score is None:
            return None
        return '{:.2f}'.format(obj.top_score - obj.great_score)
    get_great_score_diff.short_description = 'Diff'

    def get_links(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )

            html = ''
            if slate_build.projections.all().count() > 0:
                html += '<a href="/admin/nfl/buildplayerprojection/?build_id={}">Proj</a>'.format(slate_build.id)
            if slate_build.num_stacks_created() > 0:
                if html != '':
                    html += '<br />'
                html += '<a href="/admin/nfl/slatebuildstack/?build__id__exact={}">Stacks</a>'.format(slate_build.id)
            if slate_build.num_groups_created() > 0:
                if html != '':
                    html += '<br />'
                html += '<a href="/admin/nfl/slatebuildgroup/?build__id__exact={}">Groups</a>'.format(slate_build.id)
            if slate_build.num_lineups_created() > 0:
                if html != '':
                    html += '<br />'
                html += '<a href="/admin/nfl/slatebuildlineup/?build__id__exact={}">Lineups</a>'.format(slate_build.id)
            if slate_build.num_actuals_created() > 0:
                if html != '':
                    html += '<br />'
                html += '<a href="/admin/nfl/slatebuildactualslineup/?build__id__exact={}">Optimals</a>'.format(slate_build.id)

            return mark_safe(html)
        except models.SlateBuild.DoesNotExist:
            return None
        except models.SlateBuild.MultipleObjectsReturned:
            return None
    get_links.short_description = 'Links'

    def get_exposures_links(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )
            if slate_build.num_lineups_created() > 0:
                html = ''
                html += '<a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=QB">QB</a>'.format(slate_build.id)
                html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=RB">RB</a>'.format(slate_build.id)
                html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=WR">WR</a>'.format(slate_build.id)
                html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=TE">TE</a>'.format(slate_build.id)

                if slate_build.slate.site == 'fanduel':
                    html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=D">DST</a>'.format(slate_build.id)
                elif slate_build.slate.site == 'draftkings':
                    html += '<br /><a href="/admin/nfl/slateplayerbuildexposure/?build_id={}&pos=DST">DST</a>'.format(slate_build.id)

                return mark_safe(html)
            return None
        except models.SlateBuild.DoesNotExist:
            return None
        except models.SlateBuild.MultipleObjectsReturned:
            return None
    get_exposures_links.short_description = 'Exp'

    def get_el(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )

            if slate_build.total_cashes == None:
                return None
            lineups = slate_build.lineups.all().order_by('-actual')
            return lineups[0].expected_lineup_order if lineups.count() > 0 else None
        except models.SlateBuild.DoesNotExist:
            return None
        except models.SlateBuild.MultipleObjectsReturned:
            return None
    get_el.short_description = 'EL'

    def get_projections_link(self, obj):
        try:
            slate_build = models.SlateBuild.objects.get(
                backtest=obj
            )
            if slate_build.projections.all().count() > 0:
                return mark_safe('<a href="/admin/nfl/buildplayerprojection/?build_id={}">Projections</a>'.format(slate_build.id))
            return None
        except models.SlateBuild.DoesNotExist:
            return None
        except models.SlateBuild.MultipleObjectsReturned:
            return None
    get_projections_link.short_description = 'Proj'


class GroupCreationRuleInline(admin.TabularInline):
    model = models.GroupCreationRule
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


@admin.register(models.Alias, site=lottery_admin_site)
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


@admin.register(models.MissingAlias, site=lottery_admin_site)
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


@admin.register(models.SheetColumnHeaders, site=lottery_admin_site)
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


@admin.register(models.Slate, site=lottery_admin_site)
class SlateAdmin(admin.ModelAdmin):
    list_display = (
        'datetime',
        'name',
        'week',
        'is_main_slate',
        'is_complete',
        'site',
        'get_num_games',
        'get_players_link',
        'get_contest_link',
        'sim_button',
    )
    list_editable = (
        'is_main_slate',
        'is_complete',
    )
    list_filter = (
        'site',
        'is_main_slate',
        
    )
    actions = ['process_slates', 'analyze_projections']
    inlines = (SlateProjectionSheetInline, SlatePlayerOwnershipProjectionSheetInline, SlateGameInline, )
    fields = (
        'datetime',
        'name',
        'is_main_slate',
        'week',
        'site',
        'salaries_sheet_type',
        'salaries',
        'player_outcomes',
        'is_complete',
        'fc_actuals_sheet',        
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self.process_slate(request, obj)

    def process_slate(self, request, slate):
        if slate.is_complete:
            if slate.fc_actuals_sheet:
                task = BackgroundTask()
                task.name = 'Process Actuals'
                task.user = request.user
                task.save()

                tasks.process_actuals_sheet.delay(slate.id, task.id)

                messages.add_message(
                    request,
                    messages.WARNING,
                    'Processing actuals for {}.'.format(str(slate)))
        else:
            task = BackgroundTask()
            task.name = 'Finding Slate Games'
            task.user = request.user
            task.save()

            tasks.find_slate_games.delay(slate.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Your slate is being processed. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the slate is ready.')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('slate-simulate/<int:pk>/', self.simulate, name="admin_slate_simulate"),
        ]
        return my_urls + urls
    
    def get_num_games(self, obj):
        game_ids = list(obj.games.all().values_list('game__id', flat=True))
        return mark_safe('<a href="/admin/nfl/game/?id__in={}">{}</a>'.format(','.join('{}'.format(x) for x in game_ids), obj.num_games()))
    get_num_games.short_description = '# Games'

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

    def find_games(self, request, queryset):
        for slate in queryset:
            if slate.is_main_slate:
                slate.find_games()
    find_games.short_description = 'Find games for selected slates'

    def clear_slate_players(self, request, queryset):
        for slate in queryset:
            slate.players.all().delete()
    clear_slate_players.short_description = 'Clear players from selected slates'

    def analyze_projections(self, request, queryset):
        for slate in queryset:
            slate.analyze_projections()
    analyze_projections.short_description = 'Analyze projections for selected slates'

    def simulate(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        slate = get_object_or_404(models.Slate, pk=pk)

        task = BackgroundTask()
        task.name = 'Simulating Player Outcomes'
        task.user = request.user
        task.save()

        tasks.sim_outcomes_for_players.delay(list(models.SlatePlayerProjection.objects.filter(slate_player__slate=slate).values_list('id', flat=True)), task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating player outcomes for {}'.format(str(slate)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)


@admin.register(models.SlatePlayerActualsSheet, site=lottery_admin_site)
class SlatePlayerActualsSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlatePlayerOwnershipProjectionSheet, site=lottery_admin_site)
class SlatePlayerOwnershipProjectionSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlateProjectionSheet, site=lottery_admin_site)
class SlateProjectionSheetAdmin(admin.ModelAdmin):
    list_display = (
        'slate',
    )
    actions = ['save_all']

    def save_all(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_all.short_description = 'Save all selected projection sheets'


@admin.register(models.ContestImportSheet, site=lottery_admin_site)
class ContestSheetAdmin(admin.ModelAdmin):
    list_display = (
        'site',
    )
    actions = ['save_again']

    def save_again(self, request, queryset):
        for sheet in queryset:
            sheet.save()
    save_again.short_description = 'Re-import selected sheets'


@admin.register(models.SlatePlayer, site=lottery_admin_site)
class SlatePlayerAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'team',
        'slate',
        'site_pos',
        'salary',
        'fantasy_points',
        'slate_game',
    )
    search_fields = ('name',)
    list_filter = (
        ('slate__name', DropdownFilter),
        ('site_pos', DropdownFilter),
        'team')


@admin.register(models.SlatePlayerBuildExposure, site=lottery_admin_site)
class SlatePlayerBuildExposureAdmin(admin.ModelAdmin):
    build = None
    list_display = (
        'name',
        'team',
        'site_pos',
        'salary',
        'get_projection',
        'get_adjusted_opportunity',
        'get_balanced_projection',
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

    def get_balanced_projection(self, obj):
        if obj.projection is None:
            return None
        return obj.projection.balanced_projection
    get_balanced_projection.short_description = 'BP'

    def get_rb_group(self, obj):
        if obj.projection is None:
            return None
        return obj.projection.rb_group
    get_rb_group.short_description = 'RBG'

    def get_exposure(self, obj):
        return '{:.2f}%'.format(self.build.get_exposure(obj)/self.build.num_lineups_created() * 100)
    get_exposure.short_description = 'Exposure'


@admin.register(models.SlatePlayerProjection, site=lottery_admin_site)
class SlatePlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'get_player_game_z',
        'projection',
        'zscore',
        'ceiling',
        'floor',
        'stdev',
        'get_ownership_projection',
        'get_rating',
        'adjusted_opportunity',
        'get_player_value',
        'balanced_projection',
        'get_balanced_player_value',
        'rb_group',
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
        'slate_player__slate__is_main_slate',
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

    def get_player_game_z(self, obj):
        game = obj.slate_player.slate_game
        if game is None or game.zscore is None:
            return None
        return '{:.2f}'.format(game.zscore)
    get_player_game_z.short_description = 'Game-z'
    get_player_game_z.admin_order_field = 'slate_player__slate_game__zscore'

    def get_game_total(self, obj):
        return obj.game_total
    get_game_total.short_description = 'GT'

    def get_team_total(self, obj):
        return obj.team_total
    get_team_total.short_description = 'TT'

    def get_spread(self, obj):
        return obj.spread
    get_spread.short_description = 'SP'

    def get_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.proj_percentile * 100)
    get_proj_percentile.short_description = 'proj rank'
    get_proj_percentile.admin_order_field = 'proj_percentile'

    def get_own_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.own_proj_percentile * 100)
    get_own_proj_percentile.short_description = 'own rank'
    get_own_proj_percentile.admin_order_field = 'own_proj_percentile'

    def get_value_projection_percentile(self, obj):
        return '{:.2f}'.format(obj.value_projection_percentile * 100)
    get_value_projection_percentile.short_description = 'sal rank'
    get_value_projection_percentile.admin_order_field = 'value_projection_percentile'

    def get_rating(self, obj):
        return '{:.2f}'.format(obj.rating)
    get_rating.short_description = 'Rtg'
    get_rating.admin_order_field = 'rating'

    def get_ownership_projection(self, obj):
        return '{:.1f}'.format(round(float(obj.ownership_projection) * 100.0, 2))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'ownership_orjection'

    def get_player_value(self, obj):
        return '{:.2f}'.format(float(obj.value))
    get_player_value.short_description = 'Val'
    get_player_value.admin_order_field = 'value'

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


@admin.register(models.SlatePlayerRawProjection, site=lottery_admin_site)
class SlatePlayerRawProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'projection_site',
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
        'get_rating',
        'adjusted_opportunity',
        'get_player_value',
        'get_actual_score'
    )
    search_fields = ('slate_player__name',)
    list_filter = (
        ('slate_player__site_pos', DropdownFilter),
        ('slate_player__team', DropdownFilter),
        'slate_player__slate__is_main_slate',
        ('slate_player__slate__name', DropdownFilter),
        ('projection_site', DropdownFilter),
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

    def get_player_team(self, obj):
        return obj.slate_player.team
    get_player_team.short_description = 'Tm'
    get_player_team.admin_order_field = 'slate_player__team'

    def get_player_opponent(self, obj):
        return obj.slate_player.get_opponent()
    get_player_opponent.short_description = 'Opp'

    def get_player_game(self, obj):
        game = obj.slate_player.get_slate_game()
        if game is None:
            return None
        return mark_safe('<a href="/admin/nfl/game/{}/">{}@{}</a>'.format(game.game.id, game.game.away_team, game.game.home_team))
    get_player_game.short_description = 'Game'
    get_player_game.admin_order_field = 'slate_player__game'

    def get_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.proj_percentile * 100)
    get_proj_percentile.short_description = 'proj rank'
    get_proj_percentile.admin_order_field = 'proj_percentile'

    def get_own_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.own_proj_percentile * 100)
    get_own_proj_percentile.short_description = 'own rank'
    get_own_proj_percentile.admin_order_field = 'own_proj_percentile'

    def get_value_projection_percentile(self, obj):
        return '{:.2f}'.format(obj.value_projection_percentile * 100)
    get_value_projection_percentile.short_description = 'sal rank'
    get_value_projection_percentile.admin_order_field = 'value_projection_percentile'

    def get_rating(self, obj):
        return '{:.2f}'.format(obj.rating)
    get_rating.short_description = 'Rtg'
    get_rating.admin_order_field = 'rating'

    def get_ownership_projection(self, obj):
        return '{:.1f}'.format(round(float(obj.ownership_projection) * 100.0, 2))
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'ownership_orjection'

    def get_spread(self, obj):
        game = obj.slate_player.get_slate_game()

        if game is None:
            return None
        
        return game.game.home_spread if obj.slate_player.team == game.game.home_team else game.game.away_spread
    get_spread.short_description = 'Spread'

    def get_player_value(self, obj):
        return '{:.2f}'.format(float(obj.value))
    get_player_value.short_description = 'Val'
    get_player_value.admin_order_field = 'value'

    def get_num_pass_catchers(self, obj):
        if obj.slate_player.site_pos == 'QB':
            return models.SlatePlayerProjection.objects.filter(
                slate_player__slate=obj.slate_player.slate,
                slate_player__team=obj.slate_player.team, 
                slate_player__site_pos__in=['WR', 'TE'], 
                qb_stack_only=True).count()
        return None
    get_num_pass_catchers.short_description = '# PC'

    def get_actual_score(self, obj):
        return obj.slate_player.fantasy_points
    get_actual_score.short_description = 'Actual'
    get_actual_score.admin_order_field = 'slate_player__fantasy_points'

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


@admin.register(models.SlateBuildGroup, site=lottery_admin_site)
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


@admin.register(models.SlateBuildLineup, site=lottery_admin_site)
class SlateBuildLineupAdmin(admin.ModelAdmin):
    list_per_page = 50
    list_display = (
        'stack',
        'get_stack_rank',
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
        'contains_opp_top_projected_pass_catcher',
        'salary',
        'projection',
        # 'rating',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
        'get_actual',
    )

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
        qs = super().get_queryset(request)
        qs = qs.annotate(
            actual_coalesced=Coalesce('actual', 0),
            stack_rank=F('stack__rank')
        )

        return qs

    def get_game_stack(self, obj):
        if obj.stack is None:
            return obj.qb.slate_player.game
        return str(obj.stack)
    get_game_stack.short_description = 'Game Stack'

    def get_stack_rank(self, obj):
        if obj.stack is None:
            return None
        return obj.stack_rank
    get_stack_rank.short_description = 'Rnk'
    get_stack_rank.admin_order_field = 'stack_rank'

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

    def get_median_score(self, obj):
        matrix = [obj.stack.sim_scores] + obj.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.median(scores)
    get_median_score.short_description = 'mu'

    def get_75th_percentile_score(self, obj):
        matrix = [obj.stack.sim_scores] + obj.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.percentile(scores, decimal.Decimal(75.0))
    get_75th_percentile_score.short_description = '75'

    def get_ceiling_percentile_score(self, obj):
        matrix = [obj.stack.sim_scores] + obj.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.amax(scores)
    get_ceiling_percentile_score.short_description = 'ceil'


@admin.register(models.SlateBuildActualsLineup, site=lottery_admin_site)
class SlateBuildActualsLineupAdmin(admin.ModelAdmin):
    list_per_page = 25
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
        'ev',
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

    def get_median_score(self, obj):
        return obj.get_median_sim_score()
    get_median_score.short_description = 'sMU'

    def get_75th_percentile_score(self, obj):
        return obj.get_percentile_sim_score(75)
    get_75th_percentile_score.short_description = 's75'

    def get_ceiling_percentile_score(self, obj):
        return obj.get_percentile_sim_score(100)
    get_ceiling_percentile_score.short_description = 'sCEIL'

    def export(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Optimals'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Optimals Export {}.csv'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_optimal_lineups.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
    export.short_description = 'Export selected lineups'


@admin.register(models.SlateBuildStack, site=lottery_admin_site)
class SlateBuildStackAdmin(admin.ModelAdmin):
    list_display = (
        'get_stack_name',
        'rank',
        'get_qb',
        'get_player_1',
        'get_player_2',
        'get_opp_player',
        'get_mini_player_1',
        'get_mini_player_2',
        'salary',
        'projection',
        'get_game_z',
        'contains_top_projected_pass_catcher',
        'contains_opp_top_projected_pass_catcher',
        'count',
        'times_used',
        'lineups_created',
        'actual',
        'get_lineups_link',
        'error_message',
        'get_median_score',
        'get_75th_percentile_score',
        'get_ceiling_percentile_score',
    )

    list_editable = (
        'count',
    )

    raw_id_fields = (
        'qb',
        'player_1',
        'player_2',
        'opp_player',
    )

    actions = [
        'build', 
        'simulate_stack_outcomes',
        'get_actual_scores',
        'export'
    ]

    def get_stack_name(self, obj):
        return '{} Stack {}'.format(obj.qb.name, obj.build_order)
    get_stack_name.short_description = 'Stack'
    get_stack_name.admin_order_field = 'qb__name'

    def get_qb(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.qb.get_team_color(), obj.qb))
    get_qb.short_description = 'QB'
    get_qb.admin_order_field = 'qb__name'

    def get_player_1(self, obj):
        return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.player_1.get_team_color(), obj.player_1))
    get_player_1.short_description = 'Player 1'

    def get_player_2(self, obj):
        if obj.player_2:
            return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.player_2.get_team_color(), obj.player_2))
        return None
    get_player_2.short_description = 'Player 2'

    def get_opp_player(self, obj):
        if obj.opp_player:
            return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.opp_player.get_team_color(), obj.opp_player))
        return None
    get_opp_player.short_description = 'Opposing Player'

    def get_mini_player_1(self, obj):
        if obj.mini_player_1:
            return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.mini_player_1.get_team_color(), obj.mini_player_1))
        return None
    get_mini_player_1.short_description = 'Mini Player 1'

    def get_mini_player_2(self, obj):
        if obj.mini_player_2:
            return mark_safe('<p style="background-color:{}; color:#ffffff;">{}</p>'.format(obj.mini_player_2.get_team_color(), obj.mini_player_2))
        return None
    get_mini_player_2.short_description = 'Mini Player 2'

    def get_game_z(self, obj):
        game = obj.qb.slate_player.slate_game
        if game is None or game.zscore is None:
            return None
        return '{:.2f}'.format(game.zscore)
    get_game_z.short_description = 'Game-z'
    get_game_z.admin_order_field = 'qb__slate_player__slate_game__zscore'

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

    def build(self, request, queryset):
        for stack in queryset:
            tasks.build_lineups_for_stack.delay(stack.id, 1, 1)
            messages.success(request, 'Building lineups for {}. Refresh page to check progress'.format(stack))
    build.short_description = 'Generate lineups for selected stacks'

    def get_actual_scores(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Assign Stack Actuals'
        task.user = request.user
        task.save()
        
        tasks.assign_actual_scores_to_stacks.delay(list(queryset.values_list('id', flat=True)), task_id=task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Assigning actual scores to stacks. A message will appear here when complete.'
        )
    get_actual_scores.short_description = 'Get actual scores for selected stacks'

    def simulate_stack_outcomes(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Simulate Stack Outcomes'
        task.user = request.user
        task.save()

        tasks.sim_outcomes_for_stacks.delay(list(queryset.values_list('id', flat=True)), task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating outcomes for {} stacks.'.format(queryset.count()))
    simulate_stack_outcomes.short_description = 'Simulate outcomes for selected stacks'

    def get_median_score(self, obj):
        return '{:.2f}'.format(obj.get_median_sim_score())
    get_median_score.short_description = 'mu'

    def get_75th_percentile_score(self, obj):
        return '{:.2f}'.format(obj.get_percentile_sim_score(75))
    get_75th_percentile_score.short_description = 'p75'

    def get_ceiling_percentile_score(self, obj):
        return '{:.2f}'.format(obj.get_percentile_sim_score(90))
    get_ceiling_percentile_score.short_description = 'ceil'

    def export(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Stacks'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Stacks Export {}.csv'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        tasks.export_stacks.delay(list(queryset.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')

    export.short_description = 'Export selected stacks'


@admin.register(models.SlateBuild, site=lottery_admin_site)
class SlateBuildAdmin(admin.ModelAdmin):
    date_hierarchy = 'slate__datetime'
    list_per_page = 25
    list_display = (
        'id',
        'view_page_button',
        'prepare_projections_button',
        'prepare_construction_button',
        'build_button',
        'simulate_stacks_button',
        'export_button',
        'slate',
        'used_in_contests',
        'configuration',
        'in_play_criteria',
        'lineup_construction',
        'stack_construction',
        'stack_cutoff',
        'target_score',
        'get_projections_ready',
        'get_construction_ready',
        'get_ready',
        'status',
        'get_elapsed_time',
        'get_pct_complete',
        'get_optimal_pct_complete',
        'error_message',
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
        'get_links',
        'get_exposures_links',
        'get_backtest'
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
    search_fields = ('slate__name',)
    actions = [
        'reset',
        # 'prepare_projections',
        # 'prepare_construction',
        'analyze_lineups',
        'analyze_optimals',
        'export_lineups', 
        'get_actual_scores', 
        'find_optimal_lineups',
        'duplicate_builds', 
        'clear_data'
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('slatebuild-speed-test/<int:pk>/', self.speed_test, name="admin_slatebuild_speed_test"),
            path('slatebuild-build/<int:pk>/', self.build, name="admin_slatebuild_build"),
            path('slatebuild-export/<int:pk>/', self.export_for_upload, name="admin_slatebuild_export"),
            path('slatebuild-balance-rbs/<int:pk>/', self.balance_rbs, name="admin_slatebuild_balance_rbs"),
            path('slatebuild-prepare-projections/<int:pk>/', self.prepare_projections, name="admin_slatebuild_prepare_projections"),
            path('slatebuild-prepare-construction/<int:pk>/', self.prepare_construction, name="admin_slatebuild_prepare_construction"),
            path('slatebuild-sim_stacks/<int:pk>/', self.simulate_stack_outcomes, name="admin_slatebuild_sim_stacks"),
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
        return lineups[0].expected_lineup_order if lineups.count() > 0 else None
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
        tasks.prepare_construction_for_build.delay(build.id, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Preparing stacks and groups for {}. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once they are ready.'.format(str(build)))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def simulate_stack_outcomes(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        task = BackgroundTask()
        task.name = 'Simulate Stack Outcomes'
        task.user = request.user
        task.save()

        build = models.SlateBuild.objects.get(pk=pk)
        tasks.sim_outcomes_for_stacks.delay(list(build.stacks.all().values_list('id', flat=True)), task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Simulating outcomes for {} stacks.'.format(build.stacks.all().count()))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def balance_rbs(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        # Get the scenario to activate
        build = get_object_or_404(models.SlateBuild, pk=pk)
        if build.ready:
            build.balance_rbs()
            self.message_user(request, 'RBs balanced for {}.'.format(str(build)), level=messages.INFO)
        else:
            self.message_user(request, 'Cannot balance RBs for {}. Check projections and construction.'.format(str(build)), level=messages.ERROR)

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def get_target_score(self, request, queryset):
        for build in queryset:
            tasks.get_target_score.delay(build.id)
            messages.success(request, 'Getting target score for {}. Refresh this page to check progress.'.format(build))
    get_target_score.short_description = 'Get target score for selected builds'

    def speed_test(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        # Get the scenario to activate
        build = get_object_or_404(models.SlateBuild, pk=pk)
        tasks.speed_test.delay(build.id)
        self.message_user(request, 'Speed test for {}.'.format(str(build)), level=messages.INFO)

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def build(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        build = models.SlateBuild.objects.get(pk=pk)
        tasks.execute_build(build.id, request.user.id)

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

    def export_for_upload(self, request, pk):
        # TODO: Left off here...Make this use the work flow branden used on BT Studies to take pressure off http request
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
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Analyze Lineups'
            task.user = request.user
            task.save()

            tasks.analyze_lineups.delay(build.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Analyzing lineups. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    analyze_lineups.short_description = 'Analyze lineups for selected builds'

    def analyze_optimals(self, request, queryset):
        for build in queryset:
            task = BackgroundTask()
            task.name = 'Analyze Optimals'
            task.user = request.user
            task.save()

            tasks.analyze_optimals.delay(build.id, task.id)

            messages.add_message(
                request,
                messages.WARNING,
                'Analyzing optimals. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once complete.')
    analyze_optimals.short_description = 'Analyze optimals for selected builds'

    def get_actual_scores(self, request, queryset):
        for build in queryset:
            build.get_actual_scores()
    get_actual_scores.short_description = 'Get actual scores for selected builds'

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


@admin.register(models.BuildPlayerProjection, site=lottery_admin_site)
class BuildPlayerProjectionAdmin(admin.ModelAdmin):
    list_display = (
        'get_player_name',
        'get_slate',
        'get_player_salary',
        'get_player_position',
        'get_player_team',
        'get_player_opponent',
        'get_player_game',
        'get_player_game_z',
        'projection',
        'get_player_zscore',
        'get_4for4_proj',
        'get_awesemo_proj',
        'get_etr_proj',
        'get_tda_proj',
        'get_exposure',
        'get_ownership_projection',
        'get_rating',
        'adjusted_opportunity',
        'get_player_ao_zscore',
        'get_player_value',
        'balanced_projection',
        'get_balanced_player_value',
        'rb_group',
        'get_game_total',
        'get_team_total',
        'get_spread',
        'get_num_pass_catchers',
        'in_play',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'locked',
        'get_actual_score'
    )
    list_editable = (
        'in_play',
        'projection',
        'balanced_projection',
        'rb_group',
        'stack_only',
        'qb_stack_only',
        'opp_qb_stack_only',
        'locked',
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
    actions = [
        'set_rb_group_values', 
        'group_rbs', 
        'balance_rb_exposures'
    ]
    change_list_template = 'admin/nfl/build_player_projection_changelist.html'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            slate=F('slate_player__slate'), 
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary')            
        )
        qs = qs.annotate(
            player_value=ExpressionWrapper(F('projection')/(F('player_salary')/1000), output_field=FloatField())
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

    def get_player_ao_zscore(self, obj):
        proj = obj.slate_player.projection
        if proj is None or proj.ao_zscore is None:
            return None
        return '{:.2f}'.format(proj.ao_zscore)
    get_player_ao_zscore.short_description = 'ao_z'
    get_player_ao_zscore.admin_order_field = 'slate_player__projection__ao_zscore'

    def get_player_game_z(self, obj):
        game = obj.slate_player.slate_game
        if game is None or game.zscore is None:
            return None
        return '{:.2f}'.format(game.zscore)
    get_player_game_z.short_description = 'Game-z'
    get_player_game_z.admin_order_field = 'slate_player__slate_game__zscore'

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

    def get_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.proj_percentile * 100)
    get_proj_percentile.short_description = 'proj rank'
    get_proj_percentile.admin_order_field = 'proj_percentile'

    def get_own_proj_percentile(self, obj):
        return '{:.2f}'.format(obj.own_proj_percentile * 100)
    get_own_proj_percentile.short_description = 'own rank'
    get_own_proj_percentile.admin_order_field = 'own_proj_percentile'

    def get_value_projection_percentile(self, obj):
        return '{:.2f}'.format(obj.value_projection_percentile * 100)
    get_value_projection_percentile.short_description = 'sal rank'
    get_value_projection_percentile.admin_order_field = 'value_projection_percentile'

    def get_rating(self, obj):
        return '{:.2f}'.format(float(obj.rating))
    get_rating.short_description = 'Rtg'
    get_rating.admin_order_field = 'rating'

    def get_ownership_projection(self, obj):
        return '{:.2f}%'.format(float(obj.ownership_projection) * 100.0)
    get_ownership_projection.short_description = 'OP'
    get_ownership_projection.admin_order_field = 'ownership_orjection'

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

    def get_exposure(self, obj):
        return '{:.2f}%'.format(float(obj.exposure) * 100.0)
    get_exposure.short_description = 'Exp'
    get_exposure.admin_order_field = 'exposure'

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


@admin.register(models.Contest, site=lottery_admin_site)
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

    # def save_model(self, request, obj, form, change):
    #     super().save_model(request, obj, form, change)
    #     self.process_contest(request, obj)

    # def process_contest(self, request, contest):
    #     task = BackgroundTask()
    #     task.name = 'Process Contest Outcomes'
    #     task.user = request.user
    #     task.save()

    #     tasks.process_contest_sim_datasheet.delay(contest.id, task.id)

    #     messages.add_message(
    #         request,
    #         messages.WARNING,
    #         'Loading contest simulations. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once the contest is ready.')


@admin.register(models.SlateBuildConfig, site=lottery_admin_site)
class ConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'site',
        'game_stack_size',
        'use_super_stacks',
        'num_players_vs_dst',
        'max_dst_exposure',
        'allow_rbs_from_same_game',
        'allow_qb_dst_from_same_team',
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
        'allow_te_in_opp_qb_stack',
        'lineup_removal_pct'
    ]

    list_filter = [
        'site',
        'allow_rbs_from_same_game',
        'allow_qb_dst_from_same_team',
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


@admin.register(models.PlayerSelectionCriteria, site=lottery_admin_site)
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


@admin.register(models.LineupConstructionRule, site=lottery_admin_site)
class LineupConstructionRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'site',
    )
    inlines = [
        GroupCreationRuleInline
    ]


@admin.register(models.StackConstructionRule, site=lottery_admin_site)
class StackConstructionRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'site',
        'lock_top_pc',
        'top_pc_margin',
    )


@admin.register(models.Game, site=lottery_admin_site)
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


@admin.register(models.Week, site=lottery_admin_site)
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


@admin.register(models.Backtest, site=lottery_admin_site)
class BacktestAdmin(admin.ModelAdmin):
    list_per_page = 15
    list_display = (
        'name',
        'initialize_button',
        'prepare_projections_button',
        'prepare_construction_button',
        'build_button',
        'created',
        'site',
        'lineup_config',
        'in_play_criteria',
        'lineup_construction',
        'stack_construction',
        'get_num_slates',
        'total_lineups',
        'is_initialized',
        'projections_ready',
        'construction_ready',
        'ready',
        'get_median_cash_rate',
        'get_median_one_pct_rate',
        'get_median_half_pct_rate',
        'get_great_build_rate',
        'get_optimal_build_rate',
        'total_optimals',
        'status',
        'get_elapsed_time',
        'get_pct_complete',
        'get_optimals_pct_complete',
        'get_links',
        'error_message',
    )
    list_filter = (
        'site',
        'lineup_config',
        'in_play_criteria',
        'lineup_construction',
        'stack_construction',
        NumSlatesFilter,
    )
    search_fields = ('name', )
    readonly_fields = (
        'status',
        'pct_complete',
        'total_lineups',
        'total_optimals',
        'completed_lineups',
        'optimals_pct_complete',
        'error_message',
        'elapsed_time',    
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
        'add2021MainSlates',
        'addMainSlates10x',
        'add2019MainSlates10x',
        'add2020MainSlates10x',
        'add2021MainSlates10x',
        'reset',
        'prepare_projections',
        'prepare_construction',
        'execute',
        'analyze',
        'duplicate',
        'find_optimals',
        'export_optimals'
    ]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('backtest-init/<int:pk>/', self.init_one, name="admin_backtest_init"),
            path('backtest-prepare-projections/<int:pk>/', self.prepare_projections_one, name="admin_backtest_prepare_projections"),
            path('backtest-prepare-construction/<int:pk>/', self.prepare_construction_one, name="admin_backtest_prepare_construction"),
            path('backtest-build/<int:pk>/', self.execute_one, name="admin_backtest_build"),
        ]
        return my_urls + urls

    def get_queryset(self, request):
        qs = super(BacktestAdmin, self).get_queryset(request)

        qs = qs.annotate(num_slates=Count('slates'))
        qs = qs.annotate(num_slates_coalesced=Coalesce('num_slates', 0))

        return qs

    def get_num_slates(self, obj):
        return obj.num_slates
    get_num_slates.short_description = '# slates'

    def ready(self, obj):
        return obj.ready
    ready.boolean = True
    ready.short_description = 'Go'

    def is_initialized(self, obj):
        return obj.slates.all().count() == models.SlateBuild.objects.filter(backtest__backtest=obj).count()
    is_initialized.boolean = True
    is_initialized.short_description = 'Init'

    def projections_ready(self, obj):
        return obj.projections_ready
    projections_ready.boolean = True
    projections_ready.short_description = 'PR'

    def construction_ready(self, obj):
        return obj.construction_ready
    construction_ready.boolean = True
    construction_ready.short_description = 'CR'

    def get_elapsed_time(self, obj):
        _, hours, minutes, _, _ = _get_duration_components(obj.elapsed_time)
        return '{:02d}:{:02d}'.format(hours, minutes)
    get_elapsed_time.short_description = 'Time'
    get_elapsed_time.admin_order_field = 'elapsed_time'

    def get_pct_complete(self, obj):
        return '{0}%'.format(float(obj.pct_complete) * 100.0)
    get_pct_complete.short_description = 'Prog'
    get_pct_complete.admin_order_field = 'pct_complete'

    def get_optimals_pct_complete(self, obj):
        return '{0}%'.format(float(obj.optimals_pct_complete) * 100.0)
    get_optimals_pct_complete.short_description = 'O Prog'
    get_optimals_pct_complete.admin_order_field = 'optimals_pct_complete'

    def get_median_cash_rate(self, obj):
        if obj.median_cash_rate is None:
            return None
        return '{:.1f}%'.format(obj.median_cash_rate * 100)
    get_median_cash_rate.short_description = 'cash'
    get_median_cash_rate.admin_order_field = 'median_cash_rate'

    def get_median_one_pct_rate(self, obj):
        if obj.median_one_pct_rate is None:
            return None
        return '{:.1f}%'.format(obj.median_one_pct_rate * 100)
    get_median_one_pct_rate.short_description = '1%'
    get_median_one_pct_rate.admin_order_field = 'median_one_pct_rate'

    def get_median_half_pct_rate(self, obj):
        if obj.median_half_pct_rate is None:
            return None
        return '{:.1f}%'.format(obj.median_half_pct_rate * 100)
    get_median_half_pct_rate.short_description = '0.5%'
    get_median_half_pct_rate.admin_order_field = 'median_half_pct_rate'

    def get_great_build_rate(self, obj):
        if obj.great_build_rate is None:
            return None
        return '{:.1f}%'.format(obj.great_build_rate * 100)
    get_great_build_rate.short_description = 'gb%'
    get_great_build_rate.admin_order_field = 'great_build_rate'

    def get_optimal_build_rate(self, obj):
        if obj.optimal_build_rate is None:
            return None
        return '{:.1f}%'.format(obj.optimal_build_rate * 100)
    get_optimal_build_rate.short_description = 'opt%'
    get_optimal_build_rate.admin_order_field = 'optimal_build_rate'

    def get_links(self, obj):
        html = ''
        all_stacks = models.SlateBuildStack.objects.filter(build__backtest__in=obj.slates.all(), count__gt=0)

        if all_stacks.count() > 0:
            html += '<a href="/admin/nfl/slatebuildstack/?build__id__in={}">Stacks</a>'.format(','.join([str(x.build.id) for x in obj.slates.all()]))
        if obj.completed_lineups > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildlineup/?build__id__in={}">Lineups</a>'.format(','.join([str(x.build.id) for x in obj.slates.all()]))
        if obj.total_optimals > 0:
            if html != '':
                html += '<br />'
            html += '<a href="/admin/nfl/slatebuildactualslineup/?build__id__in={}">Optimals</a>'.format(','.join([str(x.build.id) for x in obj.slates.all()]))

        return mark_safe(html)
    get_links.short_description = 'Links'
    
    def addMainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True)):
                models.BacktestSlate.objects.create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    addMainSlates.short_description = 'Add all main slates to selected backtests'
    
    def add2019MainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2019)):
                models.BacktestSlate.objects.create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2019MainSlates.short_description = 'Add all 2019 main slates to selected backtests'
    
    def add2020MainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2020)):
                models.BacktestSlate.objects.create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2020MainSlates.short_description = 'Add all 2020 main slates to selected backtests'
    
    def add2021MainSlates(self, request, queryset):
        for backtest in queryset:
            for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2021)):
                models.BacktestSlate.objects.create(
                    backtest=backtest,
                    slate=slate
                )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2021MainSlates.short_description = 'Add all 2021 main slates to selected backtests'
    
    def addMainSlates10x(self, request, queryset):
        for backtest in queryset:
            for _ in range(0,10):
                for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True)):
                    models.BacktestSlate.objects.create(
                        backtest=backtest,
                        slate=slate
                    )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    addMainSlates10x.short_description = 'Add all 10x main slates to selected backtests'
    
    def add2019MainSlates10x(self, request, queryset):
        for backtest in queryset:
            for _ in range(0,10):
                for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2019)):
                    models.BacktestSlate.objects.create(
                        backtest=backtest,
                        slate=slate
                    )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2019MainSlates10x.short_description = 'Add all 10x 2019 main slates to selected backtests'
    
    def add2020MainSlates10x(self, request, queryset):
        for backtest in queryset:
            for _ in range(0,10):
                for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2020)):
                    models.BacktestSlate.objects.create(
                        backtest=backtest,
                        slate=slate
                    )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2020MainSlates10x.short_description = 'Add all 10x 2020 main slates to selected backtests'
    
    def add2021MainSlates10x(self, request, queryset):
        for backtest in queryset:
            for _ in range(0,10):
                for (index, slate) in enumerate(models.Slate.objects.filter(site=backtest.site, is_main_slate=True, week__slate_year=2021)):
                    models.BacktestSlate.objects.create(
                        backtest=backtest,
                        slate=slate
                    )
            messages.success(request, 'Added {} slates to {}.'.format(index + 1, backtest.name))
    add2021MainSlates10x.short_description = 'Add all 10x 2021 main slates to selected backtests'

    def reset(self, request, queryset):
        for backtest in queryset:
            tasks.initialize_backtest.delay(backtest.id)
            messages.success(request, 'Initializing {}. Refresh page to check progress'.format(backtest.name))
    reset.short_description = '(Re)Initialize selected backtests'

    def prepare_projections(self, request, queryset):
        for backtest in queryset:
            tasks.prepare_projections_for_backtest.delay(backtest.id)
            messages.success(request, 'Preparing projections for {}. Refresh page to check progress'.format(backtest.name))
    prepare_projections.short_description = 'Prepare projections for selected backtests'

    def prepare_construction(self, request, queryset):
        for backtest in queryset:
            tasks.prepare_construction_for_backtest.delay(backtest.id)
            messages.success(request, 'Preparing construction for {}. Refresh page to check progress'.format(backtest.name))
    prepare_construction.short_description = 'Prepare construction for selected backtests'

    def execute(self, request, queryset):
        for backtest in queryset:
            # if backtest.ready:
            if True:
                tasks.run_backtest.delay(backtest.id, request.user.id)
                messages.success(request, 'Executing {}. Refresh page to check progress'.format(backtest.name))
            else:
                messages.error(request, 'Cannot execute {}. Backtest isn\'t ready yet.'.format(backtest.name))
    execute.short_description = 'Run selected backtests'

    def init_one(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.Backtest, pk=pk)
        tasks.initialize_backtest.delay(backtest.id)
        messages.success(request, 'Initializing {}. Refresh page to check progress'.format(backtest.name))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def prepare_projections_one(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.Backtest, pk=pk)
        tasks.prepare_projections_for_backtest.delay(backtest.id)
        messages.success(request, 'Preparing projections for {}. Refresh page to check progress'.format(backtest.name))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def prepare_construction_one(self, request, pk):
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.Backtest, pk=pk)
        tasks.prepare_construction_for_backtest.delay(backtest.id)
        messages.success(request, 'Preparing construction for {}. Refresh page to check progress'.format(backtest.name))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def execute_one(self, request, pk):
        # TODO: Left off here...Make this use the work flow branden used on BT Studies to take pressure off http request
        context = dict(
           # Include common variables for rendering the admin template.
           self.admin_site.each_context(request),
           # Anything else you want in the context...
        )

        backtest = get_object_or_404(models.Backtest, pk=pk)
        tasks.run_backtest.delay(backtest.id, request.user.id)
        messages.success(request, 'Executing {}. Refresh page to check progress'.format(backtest.name))

        # redirect or TemplateResponse(request, "sometemplate.html", context)
        return redirect(request.META.get('HTTP_REFERER'), context=context)

    def analyze(self, request, queryset):
        for backtest in queryset:
            if backtest.status == 'complete':
                tasks.analyze_backtest.delay(backtest.id)
                messages.success(request, 'Analyzing {}. Refresh page to check progress'.format(backtest.name))
            else:
                messages.error(request, 'Cannot analyze {}. Backtest isn\'t complete yet.'.format(backtest.name))
    analyze.short_description = 'Analyze selected backtests'

    def duplicate(self, request, queryset):
        for backtest in queryset:
            backtest.duplicate()
            messages.success(request, 'Successfully duplicated {}.'.format(backtest.name))
    duplicate.short_description = 'Duplicate selected backtests'

    def find_optimals(self, request, queryset):
        for backtest in queryset:
            backtest.find_optimals()
            messages.success(request, 'Finding optimals for {}. Refresh page to check progress'.format(backtest.name))
    find_optimals.short_description = 'Find optimal lineups for all unique slates in selected backtests'

    def export_optimals(self, request, queryset):
        task = BackgroundTask()
        task.name = 'Export Optimals'
        task.user = request.user
        task.save()

        now = datetime.datetime.now()
        timestamp = now.strftime('%m-%d-%Y %-I:%M %p')
        result_file = 'Optimals Export {}.csv'.format(timestamp)
        result_path = os.path.join(settings.MEDIA_ROOT, 'temp', request.user.username)
        os.makedirs(result_path, exist_ok=True)
        result_path = os.path.join(result_path, result_file)
        result_url = '/media/temp/{}/{}'.format(request.user.username, result_file)

        optimals = models.SlateBuildActualsLineup.objects.filter(build__backtest__backtest__in=queryset)
        tasks.export_optimal_lineups.delay(list(optimals.values_list('id', flat=True)), result_path, result_url, task.id)

        messages.add_message(
            request,
            messages.WARNING,
            'Your export is being compiled. You may continue to use GreatLeaf while you\'re waiting. A new message will appear here once your export is ready.')
