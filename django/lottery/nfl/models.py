import bisect
import csv
import datetime
import decimal
import difflib
import math
import numpy
import pandas
import pandasql
import requests
import scipy
import statistics
import time
import traceback
import uuid

from collections import namedtuple
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q, Aggregate, FloatField, Case, When, Window, F
from django.db.models.aggregates import Avg, Count, Sum, Max
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import PercentRank
from django.db.models.signals import post_save
from django.urls.base import reverse
from django.dispatch import receiver
from django.utils.html import format_html
from django.urls import reverse_lazy

from configuration.models import BackgroundTask

from . import optimize
from . import new_optimize
from . import tasks


BuildEval = namedtuple('BuildEval', ['top_score', 'total_cashes', 'total_one_pct', 'total_half_pct', 'binked'])

SITE_OPTIONS = (
    ('draftkings', 'DraftKings'),
    ('fanduel', 'Fanduel'),
    ('yahoo', 'Yahoo'),
)

BUILD_STATUS = (
    ('not_started', 'Not Started'),
    ('running', 'Running'),
    ('complete', 'Complete'),
    ('error', 'Error'),
)

SHEET_TYPES = (
    ('site', 'Salary File'),
    ('fantasycruncher', 'FantasyCruncher Export')
)

PROJECTION_SITES = (
    ('4for4', '4For4'),
    ('awesemo', 'Awesemo'),
    ('awesemo_own', 'Awesemo Ownership'),
    ('etr', 'Establish The Run'),
    ('tda', 'The Daily Average'),
    ('rg', 'Rotogrinders'),
    ('fc', 'Fantasy Cruncher'),
    ('rts', 'Run The Sims'),
)

GREAT_BUILD_CASH_THRESHOLD = 0.3


class Median(Aggregate):
    function = 'PERCENTILE_CONT'
    name = 'median'
    output_field = FloatField()
    template = '%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)'


# Player Alias


class Alias(models.Model):
    dk_name = models.CharField(max_length=255, null=True, blank=True)
    four4four_name = models.CharField(max_length=255, null=True, blank=True)
    awesemo_name = models.CharField(max_length=255, null=True, blank=True)
    awesemo_ownership_name = models.CharField(max_length=255, null=True, blank=True)
    fc_name = models.CharField(max_length=255, null=True, blank=True)
    tda_name = models.CharField(max_length=255, null=True, blank=True)
    fd_name = models.CharField(max_length=255, null=True, blank=True)
    etr_name = models.CharField(max_length=255, null=True, blank=True)
    rg_name = models.CharField(max_length=255, null=True, blank=True)
    rts_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Alias'
        verbose_name_plural = 'Aliases'

    def __str__(self):
        return '{}'.format(self.dk_name)

    @classmethod
    def find_alias(clz, player_name, site):
        try:
            if site == 'draftkings':
                alias = Alias.objects.get(dk_name=player_name)
            elif site == 'fanduel':
                alias = Alias.objects.get(fd_name=player_name)
            elif site == '4for4':
                alias = Alias.objects.get(four4four_name=player_name)
            elif site == 'awesemo':
                alias = Alias.objects.get(awesemo_name=player_name)
            elif site == 'awesemo_own':
                alias = Alias.objects.get(awesemo_ownership_name=player_name)
            elif site == 'etr':
                alias = Alias.objects.get(etr_name=player_name)
            elif site == 'tda':
                alias = Alias.objects.get(tda_name=player_name)
            elif site == 'rg':
                alias = Alias.objects.get(rg_name=player_name)
            elif site == 'fc':
                alias = Alias.objects.get(fc_name=player_name)
            elif site == 'rts':
                alias = Alias.objects.get(rts_name=player_name)
            else:
                raise Exception('{} is not a supported site yet.'.format(site))
        except Alias.MultipleObjectsReturned:
            if site == 'draftkings':
                alias = Alias.objects.filter(dk_name=player_name)[0]
            elif site == 'fanduel':
                alias = Alias.objects.filter(fd_name=player_name)[0]
            elif site == '4for4':
                alias = Alias.objects.filter(four4four_name=player_name)[0]
            elif site == 'awesemo':
                alias = Alias.objects.filter(awesemo_name=player_name)[0]
            elif site == 'awesemo_own':
                alias = Alias.objects.filter(awesemo_ownership_name=player_name)[0]
            elif site == 'etr':
                alias = Alias.objects.filter(etr_name=player_name)[0]
            elif site == 'tda':
                alias = Alias.objects.filter(tda_name=player_name)[0]
            elif site == 'rg':
                alias = Alias.objects.filter(rg_name=player_name)[0]
            elif site == 'fc':
                alias = Alias.objects.filter(fc_name=player_name)[0]
            elif site == 'rts':
                alias = Alias.objects.filter(rts_name=player_name)[0]
            else:
                raise Exception('{} is not a supported site yet.'.format(site))
        except Alias.DoesNotExist:
            scores = []
            normal_name = player_name.lower()
            possible_matches = Alias.objects.all()
            for possible_match in possible_matches:
                if site == 'draftkings':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.dk_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'fanduel':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.fd_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == '4for4':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.four4four_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'awesemo':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.awesemo_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'awesemo_own':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.awesemo_ownership_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'etr':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.etr_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'tda':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.tda_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'rg':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.rg_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'fc':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.fc_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'rts':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.rts_name.lower())
                    score = seqmatch.quick_ratio()
                else:
                    raise Exception('{} is not a supported site yet.'.format(site))

                scores.append({'alias': possible_match, 'score': score})
            
            scores = sorted(scores, key=lambda x: x.get('score'), reverse=True)

            # add top 3 scoring aliases to MissingAlias table
            MissingAlias.objects.create(
                player_name=player_name,
                site=site,
                alias_1=scores[0].get('alias'),
                alias_2=scores[1].get('alias'),
                alias_3=scores[2].get('alias'),
            )

            return None

        return alias

    def get_alias(self, for_site):
        if for_site == 'fanduel':
            return self.fd_name
        elif for_site == 'draftkings':
            return self.dk_name
        elif for_site == '4for4':
            return self.four4four_name
        elif for_site == 'awesemo':
            return self.awesemo_name
        elif for_site == 'awesemo_own':
            return self.awesemo_ownership_name
        elif for_site == 'etr':
            return self.etr_name
        elif for_site == 'tda':
            return self.tda_name
        elif for_site == 'rg':
            return self.rg_name
        elif for_site == 'fc':
            return self.fc_name
        elif for_site == 'rts':
            return self.rts_name


class MissingAlias(models.Model):
    player_name = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS+PROJECTION_SITES, default='fanduel')
    alias_1 = models.ForeignKey(Alias, related_name='hint_1', on_delete=models.CASCADE)
    alias_2 = models.ForeignKey(Alias, related_name='hint_2', on_delete=models.CASCADE)
    alias_3 = models.ForeignKey(Alias, related_name='hint_3', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Missing Alias'
        verbose_name_plural = 'Missing Aliases'
    
    def choose_alias_1_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_choose_alias", args=[self.pk, self.alias_1.pk]), str(self.alias_1)
        )
    choose_alias_1_button.short_description = ''
    
    def choose_alias_2_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_choose_alias", args=[self.pk, self.alias_2.pk]), str(self.alias_2)
        )
    choose_alias_2_button.short_description = ''
    
    def choose_alias_3_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_choose_alias", args=[self.pk, self.alias_3.pk]), str(self.alias_3)
        )
    choose_alias_3_button.short_description = ''
    
    def create_new_alias_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #4fb2d3; font-weight: bold; padding: 10px 15px; width:100px">Add New</a>',
            reverse_lazy("admin:admin_choose_alias", args=[self.pk, 0])
        )
    create_new_alias_button.short_description = ''


# Slate Infrastructure


class Week(models.Model):
    num = models.PositiveIntegerField('Week #')
    slate_year = models.PositiveIntegerField()
    start = models.DateField()
    end = models.DateField()

    class Meta:
        ordering = ['start']

    def __str__(self):
        return '{} Week {}'.format(self.slate_year, self.num)

    def update_vegas(self):
        month = self.start.strftime('%m')
        date = self.start.strftime('%d')
        year = self.start.strftime('%Y')

        url = 'https://www.fantasylabs.com/api/sportevents/1/{}_{}_{}/vegas/'.format(month, date, year)
        response = requests.get(url)
        
        event_details = response.json()
        for event in event_details:
            properties = event.get('EventDetails').get('Properties')

            if properties.get('HomeGameSpreadCurrent', None) is not None:
                home_team = event.get('HomeTeamShortVar')
                away_team = event.get('VisitorTeamShortVar')
                game_date = datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S')

                if event.get('HomeTeamShortVar') == 'JAX':
                    home_team = 'JAC'
                if event.get('HomeTeamShortVar') == 'LV' and game_date.year < 2020:
                    home_team = 'OAK'
                if event.get('HomeTeamShortVar') == 'LA':
                    home_team = 'LAR'
                if event.get('VisitorTeamShortVar') == 'JAX':
                    away_team = 'JAC'
                if event.get('VisitorTeamShortVar') == 'LV' and game_date.year < 2020:
                    away_team = 'OAK'
                if event.get('VisitorTeamShortVar') == 'LA':
                    away_team = 'LAR'

                try:
                    game = Game.objects.get(
                        id=event.get("EventId"),
                        week=self
                    )
                    game.home_team = home_team
                    game.away_team = away_team
                    game.game_date = datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S')
                    game.game_total = float(event.get('OU'))
                    game.home_spread = float(properties.get('HomeGameSpreadCurrent'))
                    game.away_spread = float(properties.get('VisitorGameSpreadCurrent'))
                    game.home_implied = float(properties.get('HomeVegasRuns'))
                    game.away_implied = float(properties.get('VisitorVegasRuns'))
                    game.save()
                except Game.DoesNotExist:
                    # check if this game already exists on another week (due to rescheduling)
                    existing_games = Game.objects.filter(id=event.get("EventId"))
                    if existing_games.count() > 0:
                        existing_games.delete()

                    game = Game.objects.create(
                        id=event.get("EventId"),
                        week=self,
                        home_team=home_team,
                        away_team=away_team,
                        game_date=datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S'),
                        game_total=float(event.get('OU')),
                        home_spread=float(properties.get('HomeGameSpreadCurrent')),
                        away_spread=float(properties.get('VisitorGameSpreadCurrent')),
                        home_implied=float(properties.get('HomeVegasRuns')),
                        away_implied=float(properties.get('VisitorVegasRuns'))
                    )

                print(game)


class Game(models.Model):
    week = models.ForeignKey(Week, related_name='games', on_delete=models.CASCADE)
    home_team = models.CharField(max_length=4)
    away_team = models.CharField(max_length=4)
    game_date = models.DateTimeField()
    game_total = models.DecimalField(decimal_places=2, max_digits=4)
    home_spread = models.DecimalField(decimal_places=2, max_digits=4)
    away_spread = models.DecimalField(decimal_places=2, max_digits=4)
    home_implied = models.DecimalField(decimal_places=2, max_digits=4)
    away_implied = models.DecimalField(decimal_places=2, max_digits=4)

    def __str__(self):
        # localtz = pytz.timezone(settings.TIME_ZONE)
        # local_dt = self.game_date.replace(tzinfo=localtz)
        # print(localtz, self.game_date.tzinfo)
        return '{}: {} @ {} {}'.format(str(self.week), self.away_team, self.home_team, self.game_date.strftime('%m/%d/%y %-I:%M %p'))


class Slate(models.Model):
    datetime = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name='Slate', null=True, blank=True)
    week = models.ForeignKey(Week, related_name='slates', verbose_name='Week', on_delete=models.SET_NULL, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    is_main_slate = models.BooleanField(default=False)
    is_complete = models.BooleanField(default=False)

    salaries_sheet_type = models.CharField(max_length=255, choices=SHEET_TYPES, default='site')
    salaries = models.FileField(upload_to='uploads/salaries', blank=True, null=True)

    player_outcomes = models.FileField(upload_to='uploads/sims', blank=True, null=True)

    fc_actuals_sheet = models.FileField(verbose_name='FC Actuals CSV', upload_to='uploads/actuals', blank=True, null=True)

    class Meta:
        ordering = ['-name']

    def __str__(self):
        return '{}'.format(self.name) if self.name is not None else '{}'.format(self.datetime)

    @property
    def teams(self):
        games = self.games.all()
        home_teams = list(games.values_list('game__home_team', flat=True))
        away_teams = list(games.values_list('game__away_team', flat=True))

        return home_teams + away_teams

    @property
    def available_projections(self):
        return list(self.projections.all().values_list('projection_site', flat=True))

    @property
    def aux_projections(self):
        return list(self.projections.filter(is_primary=False).values_list('projection_site', flat=True))

    def get_projections(self):
        return SlatePlayerProjection.objects.filter(slate_player__slate=self)

    def analyze_projections(self):
        qs = SlatePlayerProjection.objects.filter(
            slate_player__slate=self
        )

        qs = qs.annotate(
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary')            
        )
        qs = qs.annotate(
            player_value=ExpressionWrapper(F('projection')/(F('player_salary')/1000), output_field=FloatField())
        )

        qs = qs.annotate(
            proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('projection').asc()
            ),
            value_proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('player_value').asc()
            ),
            own_proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('ownership_projection').desc()
            ),
            ao_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('adjusted_opportunity').asc()
            ),
        )

        for p in qs:
            p.value = p.player_value
            p.projection_percentile = p.proj_percentile
            p.ownership_projection_percentile =  p.own_proj_percentile
            p.value_projection_percentile = p.value_proj_percentile
            if p.position == 'RB':
                p.adjusted_opportunity_percentile = p.ao_percentile
                p.rating = float(p.proj_percentile) + float(p.proj_percentile) + float(p.ao_percentile) + float(p.own_proj_percentile) + float(p.value_proj_percentile)
            else:
                p.rating = float(p.proj_percentile) + float(p.proj_percentile) + float(p.own_proj_percentile) + float(p.value_proj_percentile)

            p.save()

    def num_games(self):
        return self.games.all().count()
    num_games.short_description = '# games'

    def num_contests(self):
        return self.contests.all().count()
    num_contests.short_description = '# contests'

    def num_slate_players(self):
        return self.players.all().count()
    num_slate_players.short_description = '# Slate Players'

    def num_projected_players(self):
        return self.players.exclude(projection=None).count()
    num_projected_players.short_description = '# Projected Players'

    def num_qbs(self):
        return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='QB').count()
    num_qbs.short_description = '# qbs'

    def num_in_play(self):
        return self.players.filter(projection__in_play=True).count()
    num_in_play.short_description = '# in play'

    def num_stack_only(self):
        return self.players.filter(projection__stack_only=True).count()
    num_stack_only.short_description = '# stack only'

    def num_rbs(self):
        return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').count()
    num_rbs.short_description = '# rbs'

    def num_top_rbs(self):
        return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB', projection__rb_group__lte=2).count()
    num_top_rbs.short_description = '# top rbs'

    def median_rb_projection(self):
        return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').aggregate(median_projection=Median('projection__projection')).get('median_projection', 0.0)
    median_rb_projection.short_description = 'median rb projection'

    def median_rb_ao(self):
        return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').aggregate(median_opp=Median('projection__adjusted_opportunity')).get('median_opp', 0.0)
    median_rb_ao.short_description = 'median rb ao'
    
    def group_rbs(self):
        BuildPlayerProjection.objects.filter(slate_player__slate=self).update(rb_group=None)
        rbs = BuildPlayerProjection.objects.filter(slate_player__slate=self, slate_player__site_pos='RB', in_play=True)

        group_index = 1
        top_rb = rbs.order_by('-rb_group_value')[0]

        for rb in rbs.order_by('-rb_group_value'):
            if rb.rb_group_value < float(top_rb.rb_group_value) * 0.95:
                group_index += 1
                top_rb = rb
            
            rb.rb_group = group_index
            rb.save()

    def balance_rb_exposures(self):
        rbs = BuildPlayerProjection.objects.filter(slate_player__slate=self, slate_player__site_pos='RB', in_play=True)
        for rb in rbs:
            median_value = max(statistics.median([round(float(p.adjusted_opportunity), 2) for p in rbs.filter(rb_group=rb.rb_group)]), 2.0)
            rb.balanced_projection = median_value
            rb.save()

    def get_great_score(self):
        if self.contests.all().count() > 0:
            return self.contests.all()[0].great_score
        return None

    def get_bink_score(self):
        if self.contests.all().count() > 0:
            return self.contests.all()[0].winning_score
        return None

    def get_one_pct_score(self):
        if self.contests.all().count() > 0:
            return self.contests.all()[0].one_pct_score
        return None

    def find_games(self):
        if not self.is_main_slate:
            return

        self.games.all().delete()

        games = Game.objects.filter(
            week=self.week,
            game_date__gte=self.datetime,
            game_date__lt=self.datetime + datetime.timedelta(hours=5)
        )
        game_totals = list(games.values_list('game_total', flat=True))
        zscores = scipy.stats.zscore(game_totals)

        for (index, game) in enumerate(games):
            SlateGame.objects.create(
                slate=self,
                game=game,
                zscore=zscores[index]
            )

    def calc_player_zscores(self, position):
        projections = list(self.get_projections().filter(slate_player__site_pos=position).values_list('projection', flat=True))
        ao_projections = list(self.get_projections().filter(slate_player__site_pos=position).values_list('adjusted_opportunity', flat=True)) if position == 'RB' else None
        zscores = scipy.stats.zscore(projections)
        ao_zscores = scipy.stats.zscore(ao_projections) if ao_projections is not None else None

        for (index, projection) in enumerate(self.get_projections().filter(slate_player__site_pos=position)):
            projection.zscore = zscores[index]
            projection.ao_zscore = ao_zscores[index] if ao_zscores is not None else 0.0
            projection.save()        

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Sim</a>',
            reverse_lazy("admin:admin_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''


class SlateGame(models.Model):
    slate = models.ForeignKey(Slate, related_name='games', on_delete=models.CASCADE)
    game = models.ForeignKey(Game, related_name='slates', on_delete=models.CASCADE)
    zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    ownership = models.DecimalField('Ownership', max_digits=6, decimal_places=4, default=0.0000)
    ownership_zscore = models.DecimalField('Own Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    avg_stack_ceiling = models.DecimalField('Avg Stack Ceiling', max_digits=5, decimal_places=2, default=0.00)
    rating = models.DecimalField('Rating', max_digits=6, decimal_places=4, default=0.0000)

    class Meta:
        verbose_name = 'Game'
        verbose_name_plural = 'Games'

    def __str__(self):
        return '{}: {}'.format(str(self.slate), str(self.game))

    def calc_ownership(self):
        self.ownership = self.players.all().aggregate(total=Sum('projection__ownership_projection')).get('total')
        self.save()

    def calc_rating(self):
        self.rating = self.zscore / self.ownership_zscore
        self.save()

    def game_total(self):
        return self.game.game_total


class Contest(models.Model):
    slate = models.ForeignKey(Slate, related_name='contests', on_delete=models.CASCADE, null=True, blank=True)
    outcomes_sheet = models.FileField(upload_to='uploads/sims', blank=True, null=True)
    outcomes = ArrayField(ArrayField(models.DecimalField(max_digits=5, decimal_places=2)), null=True, blank=True)
    cost = models.DecimalField(decimal_places=2, max_digits=10)
    num_games = models.IntegerField(null=True, blank=True)
    max_entrants = models.IntegerField()
    max_entries = models.IntegerField()
    mincash_payout = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    mincash_score = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    name = models.CharField(max_length=255)
    places_paid = models.IntegerField(null=True, blank=True)
    prize_pool = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    start_date = models.IntegerField(null=True, blank=False)
    total_entrants = models.IntegerField(null=True, blank=True)
    winning_payout = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    winning_score = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    one_pct_score = models.DecimalField('1% Score', decimal_places=2, max_digits=10, null=True, blank=True)
    one_pct_rank = models.IntegerField('1% Rank', null=True, blank=True)
    half_pct_score = models.DecimalField('0.5% Score', decimal_places=2, max_digits=10, null=True, blank=True)
    half_pct_rank = models.IntegerField('0.5% Rank', null=True, blank=True)
    great_score = models.DecimalField('Great Score', decimal_places=2, max_digits=10, null=True, blank=True)
    play_order = models.IntegerField(default=1)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        ordering = ['slate', '-prize_pool']

    def get_payout(self, rank):
        try:
            prize = self.prizes.get(min_rank__lte=rank, max_rank__gte=rank)
            return prize.prize
        except ContestPrize.DoesNotExist:
            return 0.0

    def simulate(self):
        # lineups = optimize.simulate_contest(self, self.slate.get_projections())
        new_optimize.simulate_contest(self, self.slate.get_projections())


class ContestPrize(models.Model):
    contest = models.ForeignKey(Contest, related_name='prizes', on_delete=models.CASCADE)
    min_rank = models.IntegerField(default=1)
    max_rank = models.IntegerField(default=1)
    prize = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def __str__(self):
        if self.min_rank == self.max_rank:
            return '{}: ${}'.format(self.ordinal(self.min_rank), self.prize)
        else:
            return '{} - {}: {}'.format(self.ordinal(self.min_rank), self.ordinal(self.max_rank), self.prize)

    def ordinal(self, num):
        SUFFIXES = {1: 'st', 2: 'nd', 3: 'rd'}
        # I'm checking for 10-20 because those are the digits that
        # don't follow the normal counting scheme. 
        if 10 <= num % 100 <= 20:
            suffix = 'th'
        else:
            # the second parameter is a default.
            suffix = SUFFIXES.get(num % 10, 'th')
        return str(num) + suffix


class SlatePlayer(models.Model):
    player_id = models.CharField(max_length=255, null=True, blank=True)
    slate = models.ForeignKey(Slate, related_name='players', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    salary = models.IntegerField()
    site_pos = models.CharField(max_length=5)
    team = models.CharField(max_length=4)
    fantasy_points = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    game = models.CharField(max_length=10)
    slate_game = models.ForeignKey(SlateGame, related_name='players', on_delete=models.SET_NULL, blank=True, null=True)
    ownership = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)

    def __str__(self):
        if self.fantasy_points is None:
            return '{} {} ${} (vs. {})'.format(self.team, self.name, self.salary, self.get_opponent())
        return '{} {} ${} (vs. {}) -- {}'.format(self.team, self.name, self.salary, self.get_opponent(), self.fantasy_points)

    @property
    def team_total(self):
        game = self.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_implied if self.team == game.game.home_team else game.game.away_implied

    @property
    def game_total(self):
        game = self.get_slate_game()

        if game == None:
            return None
        
        return game.game.game_total

    @property
    def spread(self):
        game = self.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_spread if self.team == game.game.home_team else game.game.away_spread

    def get_team_color(self):
        return settings.TEAM_COLORS[self.team]

    def get_opponent(self):
        return self.game.replace(self.team, '').replace('_', '')

    def get_slate_game(self):
        games = self.slate.games.filter(
            Q(Q(game__home_team=self.team) | Q(game__away_team=self.team))
        )

        if games.count() > 0:
            return games[0]
        return None

    class Meta:
        ordering = ['-salary', 'name']


class SlatePlayerProjection(models.Model):
    slate_player = models.OneToOneField(SlatePlayer, related_name='projection', on_delete=models.CASCADE)
    projection = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Proj')
    floor = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Flr')
    zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    ceiling = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Ceil')
    stdev = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Stdev')
    ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='AO')
    ao_zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    ownership_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    value_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    adjusted_opportunity_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rating = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rb_group_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    rb_group = models.PositiveIntegerField('RBG', null=True, blank=True)
    balanced_projection = models.DecimalField('BP', null=True, blank=True, max_digits=5, decimal_places=2, default=0.0)
    sim_scores = ArrayField(models.DecimalField(max_digits=4, decimal_places=2), null=True, blank=True)
    in_play = models.BooleanField(default=True)
    stack_only = models.BooleanField(default=False, verbose_name='SO', help_text='Player is only in pool when stacked with QB or opposing QB')
    qb_stack_only = models.BooleanField(default=False, verbose_name='SwQB', help_text='Generate QB stacks with this player')
    opp_qb_stack_only = models.BooleanField(default=False, verbose_name='SwOQB', help_text='Generate Opp QB stacks with this player')
    at_most_one_in_stack = models.BooleanField(default=False, verbose_name='AM1', help_text='Generate stacks with only 1 of players with this designation')
    at_least_one_in_lineup = models.BooleanField(default=False, verbose_name='AL1', help_text='At least one player with this designation should appear in every lineup')
    at_least_two_in_lineup = models.BooleanField(default=False, verbose_name='AL2', help_text='At least two players with this designation should appear in every lineup')
    locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Base Player Projection'
        verbose_name_plural = 'Base Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return '{} -- Proj: {}'.format(str(self.slate_player), self.projection)

    @property
    def name(self):
        return self.slate_player.name

    @property
    def salary(self):
        return self.slate_player.salary

    @property
    def team(self):
        return self.slate_player.team

    @property
    def position(self):
        return self.slate_player.site_pos

    @property
    def position_rank(self):
        aggregate = SlatePlayerProjection.objects.filter(
            slate_player__slate=self.slate_player.slate,
            slate_player__site_pos=self.slate_player.site_pos,
            projection__gt=self.projection).aggregate(ranking=Count('projection'))
        return aggregate.get('ranking') + 1

    @property
    def team_total(self):
        return self.slate_player.team_total

    @property
    def game_total(self):
        return self.slate_player.game_total

    @property
    def game(self):
        return self.slate_player.slate_game

    @property
    def spread(self):
        return self.slate_player.spread

    def get_team_color(self):
        return self.slate_player.get_team_color()

    def calc_sim_scores(self):
        mu = float(self.projection)
        if self.slate_player.site_pos == 'QB':
            sim_scores = [min(i * mu, 99.99) for i in scipy.stats.foldnorm.rvs(2.286320653446043, loc=0.009521750045927459, scale=0.43647078822917096, size=settings.SIMULATION_SIZE)]
        elif self.slate_player.site_pos == 'RB':
            sim_scores = [min(i * mu, 99.99) for i in scipy.stats.gengamma.rvs(0.8569512382187675, 1.7296589884149502, loc=0.1696436245041962, scale=1.0034840685805952, size=settings.SIMULATION_SIZE)]
        elif self.slate_player.site_pos == 'WR':
            sim_scores = [min(i * mu, 99.99) for i in scipy.stats.geninvgauss.rvs(1.5027595619420469, 1.08441508981995, loc=0.1396719464795535, scale=0.30497399320969815, size=settings.SIMULATION_SIZE)]
        elif self.slate_player.site_pos == 'TE':
            sim_scores = [min(i * mu, 99.99) for i in scipy.stats.beta.rvs(1.3211694111775993, 8.619168174695513, loc=0.05324597661516427, scale=7.141266442024949, size=settings.SIMULATION_SIZE)]
        elif self.slate_player.site_pos == 'D' or self.slate_player.site_pos == 'DST':
            sim_scores = [min(i * mu, 99.99) for i in scipy.stats.burr12.rvs(35.758034183278085, 0.4498053645571314, loc=-11.318659107435849, scale=11.704623152048967, size=settings.SIMULATION_SIZE)]
        else:
            sim_scores = None
        
        self.sim_scores = sim_scores
        self.save()

    def get_percentile_sim_score(self, percentile):
        return numpy.percentile(self.sim_scores, decimal.Decimal(percentile))

    def get_opponent(self):
        return self.slate_player.get_opponent()

    def set_rb_group_value(self):
        self.rb_group_value = float(self.projection) * 6 + float(self.adjusted_opportunity) * 4
        self.balanced_projection = self.rb_group_value / 10
        self.save()

    def find_in_play(self):
        if self.slate_player.slate.site == 'fanduel':
            self.find_in_play_fanduel()
        elif self.slate_player.slate.site == 'draftkings':
            self.find_in_play_draftkings()
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))
        
        if self.slate_player.site_pos == 'RB':
            self.set_rb_group_value()

    def find_in_play_fanduel(self):        
        projection_threshold = self.getPlayerThreshold(self.slate_player.site_pos, self.slate_player.slate.num_games())
        ao_threshold = self.getAOThreshold(self.slate_player.slate.num_games())
        if self.slate_player.site_pos == 'RB' and (self.projection >= projection_threshold or self.adjusted_opportunity >= ao_threshold):
            self.in_play = True

            if self.slate_player.slate.num_games() > 4 and self.projection >= 16.4:
                self.at_least_one_in_lineup = True
        elif self.slate_player.site_pos == 'WR' and self.projection >= projection_threshold:
            self.in_play = True
        elif self.slate_player.site_pos == 'QB' and self.projection >= projection_threshold:
            if self.team_total <= 19.5:
                self.in_play = False
            elif self.game_total < 42.0:
                self.in_play = False
            elif self.projection <= 19.9 and self.game_total <= 42.5:
                self.in_play = False
            elif self.team_total < 24.5 and self.projection <= 15.8:
                self.in_play = False
            else:
                self.in_play = True
        elif self.slate_player.site_pos == 'D' or self.slate_player.site_pos == 'DST':
            self.in_play = True
        elif self.slate_player.site_pos == 'TE' and self.projection >= projection_threshold:
            self.in_play = True
        else:
            self.in_play = False
        
        self.save()

    def find_in_play_draftkings(self):        
        projection_threshold = self.getPlayerThreshold(self.slate_player.site_pos, self.slate_player.slate.num_games())
        ao_threshold = self.getAOThreshold(self.slate_player.slate.num_games())
        if self.slate_player.site_pos == 'RB' and (self.projection >= projection_threshold and self.adjusted_opportunity >= ao_threshold):
            self.in_play = True
        elif self.slate_player.site_pos == 'WR' and self.projection >= projection_threshold:
            self.in_play = True
        elif self.slate_player.site_pos == 'QB' and self.projection >= projection_threshold:
            if self.team_total <= 19.5:
                self.in_play = False
            elif self.game_total < 42.0:
                self.in_play = False
            elif self.projection <= 19.9 and self.game_total <= 42.5:
                self.in_play = False
            elif self.team_total < 24.5 and self.projection <= 15.8:
                self.in_play = False
            else:
                self.in_play = True
        elif self.slate_player.site_pos == 'D' or self.slate_player.site_pos == 'DST':
            self.in_play = True
        elif self.slate_player.site_pos == 'TE' and self.projection >= projection_threshold:
            self.in_play = True
        else:
            self.in_play = False
        
        self.save()

    def find_al1(self):
        if self.slate_player.slate.site == 'fanduel':
            self.find_al1_fanduel()
        elif self.slate_player.slate.site == 'draftkings':
            self.find_al1_draftkings()
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def find_al1_fanduel(self):        
        projection_threshold = self.getPlayerAL1Threshold(self.slate_player.slate.num_games())
        self.at_least_one_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
        self.save()

    def find_al1_draftkings(self):        
        projection_threshold = self.getPlayerAL1Threshold(self.slate_player.slate.num_games())
        self.at_least_one_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
        self.save()

    def find_al2(self):
        if self.slate_player.slate.site == 'fanduel':
            self.find_al2_fanduel()
        elif self.slate_player.slate.site == 'draftkings':
            self.find_al2_draftkings()
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def find_al2_fanduel(self):        
        projection_threshold = self.getPlayerAL2Threshold(self.slate_player.slate.num_games())
        self.at_least_two_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
        self.save()

    def find_al2_draftkings(self):        
        projection_threshold = self.getPlayerAL2Threshold(self.slate_player.slate.num_games())
        self.at_least_two_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
        self.save()

    def getPlayerThreshold(self, position, num_games):
        if self.slate_player.slate.site == 'fanduel':
            return self.getFanduelThreshold(position, num_games)
        elif self.slate_player.slate.site == 'draftkings':
            return self.getDraftKingsThreshold(position, num_games)
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def getFanduelThreshold(self, position, num_games):
        # QB
        if position == 'QB':
            if num_games < 4:
                return 9.9
            else:
                return 14.9

        # RB
        elif position == 'RB':
            if num_games > 5:
                return 13.9
            else:
                return 6.9

        # WR
        elif position == 'WR':
            if num_games > 5:
                return 7.9
            else:
                return 4.9

        # TE
        else:
            if num_games > 5:
                return 4.9
            else:
                return 4.9

    def getDraftKingsThreshold(self, position, num_games):
        # QB
        if position == 'QB':
            if num_games < 4:
                return 9.9
            else:
                return 14.9

        # RB
        elif position == 'RB':
            if num_games > 5:
                return 15.9
            else:
                return 6.9

        # WR
        elif position == 'WR':
            if num_games > 5:
                return 8.9
            else:
                return 4.9

        # TE
        else:
            if num_games > 5:
                return 4.9
            else:
                return 4.9

    def getAOThreshold(self, num_games):
        if self.slate_player.slate.site == 'fanduel':
            return self.getFanduelAOThreshold(num_games)
        elif self.slate_player.slate.site == 'draftkings':
            return self.getDraftKingsAOThreshold(num_games)
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def getFanduelAOThreshold(self, num_games):
        if num_games > 4:
            return 19.9
        else:
            return 9.9

    def getDraftKingsAOThreshold(self, num_games):
        if num_games > 4:
            return 19.9
        else:
            return 17.9

    def getPlayerAL1Threshold(self, num_games):
        if self.slate_player.slate.site == 'fanduel':
            return self.getFanduelAL1Threshold(num_games)
        elif self.slate_player.slate.site == 'draftkings':
            return self.getDraftKingsAL1Threshold(num_games)
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def getFanduelAL1Threshold(self, num_games):
        if num_games > 4:
            return 16.4
        else:
            return 16.4

    def getDraftKingsAL1Threshold(self, num_games):
        if num_games > 4:
            return 16.4
        else:
            return 16.4

    def getPlayerAL2Threshold(self, num_games):
        if self.slate_player.slate.site == 'fanduel':
            return self.getFanduelAL2Threshold(num_games)
        elif self.slate_player.slate.site == 'draftkings':
            return self.getDraftKingsAL2Threshold(num_games)
        else:
            raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

    def getFanduelAL2Threshold(self, num_games):
        if num_games > 4:
            return 16.9
        else:
            return 16.9

    def getDraftKingsAL2Threshold(self, num_games):
        if num_games > 4:
            return 16.9
        else:
            return 16.9

    def find_stack_only(self):
        SlatePlayerProjection.objects.filter(
            slate_player__slate=self.slate_player.slate,
            slate_player__team=self.slate_player.team
        ).update(stack_only=False)

        # Get all WR/TE from team
        pass_catchers = SlatePlayerProjection.objects.filter(
            Q(slate_player__slate=self.slate_player.slate),
            Q(slate_player__team=self.slate_player.team),
            Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')
        ).order_by('-projection')

        for (index, pass_catcher) in enumerate(pass_catchers):
            pass_catcher.find_in_play()

            if not pass_catcher.in_play:
                pass_catcher.stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                pass_catcher.in_play = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                pass_catcher.qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                pass_catcher.opp_qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
            else:
                pass_catcher.stack_only = False
                pass_catcher.qb_stack_only = True
                pass_catcher.opp_qb_stack_only = True
                
                # if pass catcher is a TE and they are a bobo, block them from being in stacks with QB or opp QB (unless they are either the #2 option or within 1pt of the #2 option)
                # if pass_catcher.slate_player.site_pos == 'TE' and pass_catcher.projection <= 7.9 and index > 1 and abs(pass_catchers[1].projection - pass_catcher.projection) > 1.01:
                #     pass_catcher.qb_stack_only = True
                #     pass_catcher.opp_qb_stack_only = False
                # else:
                #     pass_catcher.qb_stack_only = True
                #     pass_catcher.opp_qb_stack_only = True

            pass_catcher.save()


class SlatePlayerRawProjection(models.Model):
    slate_player = models.ForeignKey(SlatePlayer, related_name='raw_projections', on_delete=models.CASCADE)
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='4for4')
    projection = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Proj')
    floor = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Flr')
    ceiling = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Ceil')
    stdev = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Stdev')
    ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='AO')
    value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    ownership_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    value_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    adjusted_opportunity_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rating = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)

    class Meta:
        verbose_name = 'Raw Player Projection'
        verbose_name_plural = 'Raw Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return '{} -- {}}: {}'.format(str(self.slate_player), self.projection)

    @property
    def name(self):
        return self.slate_player.name

    @property
    def salary(self):
        return self.slate_player.salary

    @property
    def team(self):
        return self.slate_player.team

    @property
    def game(self):
        return self.slate_player.slate_game

    @property
    def position(self):
        return self.slate_player.site_pos

    @property
    def position_rank(self):
        aggregate = SlatePlayerRawProjection.objects.filter(
            slate_player__slate=self.slate_player.slate,
            slate_player__site_pos=self.slate_player.site_pos,
            projection__gt=self.projection).aggregate(ranking=Count('projection'))
        return aggregate.get('ranking') + 1

    def get_team_color(self):
        return self.slate_player.get_team_color()

    def get_game_total(self):
        game = self.slate_player.get_slate_game()

        if game == None:
            return None
        
        return game.game.game_total

    def get_team_total(self):
        game = self.slate_player.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_implied if self.slate_player.team == game.game.home_team else game.game.away_implied

    def get_spread(self):
        game = self.slate_player.get_slate_game()

        if game == None:
            return None
        
        return game.game.home_spread if self.slate_player.team == game.game.home_team else game.game.away_spread

    def get_opponent(self):
        return self.slate_player.get_opponent()


# Rules & Configuration


class SlateBuildConfig(models.Model):
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    game_stack_size = models.IntegerField(default=4)
    use_super_stacks = models.BooleanField(default=False)
    num_players_vs_dst = models.IntegerField(default=0)
    max_dst_exposure = models.DecimalField(decimal_places=2, max_digits=2, default=0.15)
    allow_rbs_from_same_game = models.BooleanField(default=False)
    allow_qb_dst_from_same_team = models.BooleanField(default=True)
    allow_rb_qb_from_same_team = models.BooleanField(default=False)
    allow_rb_qb_from_opp_team = models.BooleanField(default=False)
    allow_dst_rb_stack = models.BooleanField(default=True)
    randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.3)
    use_similarity_scores = models.BooleanField(default=False)
    use_iseo = models.BooleanField(default=True, help_text='When true, players within a stack are exposed proportional to their projection relative to total stack projection')
    use_iseo_plus = models.BooleanField(default=True, help_text='When true, stacks will be pre-made and balanced such that the number of lineups for each stack is proportional to the stack projection relative to all stacks')
    use_iseo_rbs = models.BooleanField(default=True, help_text='When true, rbs exposure will be balanced by using adjusted opportunity and running back groups')
    uniques = models.IntegerField(default=1)
    min_salary = models.IntegerField(default=59000)
    allow_rb_as_flex = models.BooleanField(default=True)
    allow_wr_as_flex = models.BooleanField(default=True)
    allow_te_as_flex = models.BooleanField(default=False)
    allow_rb_in_qb_stack = models.BooleanField(default=True)
    allow_wr_in_qb_stack = models.BooleanField(default=True)
    allow_te_in_qb_stack = models.BooleanField(default=True)
    allow_rb_in_opp_qb_stack = models.BooleanField(default=True)
    allow_wr_in_opp_qb_stack = models.BooleanField(default=True)
    allow_te_in_opp_qb_stack = models.BooleanField(default=True)
    lineup_removal_pct = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)

    class Meta:
        verbose_name = 'Build Config'
        verbose_name_plural = 'Build Configs'
        ordering = ['id']
    
    def __str__(self):
        return '{}'.format(self.name)

    @property
    def flex_positions(self):
        f_pos = []

        if self.allow_rb_as_flex:
            f_pos.append('RB')

        if self.allow_wr_as_flex:
            f_pos.append('WR')

        if self.allow_te_as_flex:
            f_pos.append('TE')
        return f_pos

    @property
    def qb_stack_positions(self):
        f_pos = []

        if self.allow_rb_in_qb_stack:
            f_pos.append('RB')

        if self.allow_wr_in_qb_stack:
            f_pos.append('WR')

        if self.allow_te_in_qb_stack:
            f_pos.append('TE')
        return f_pos

    @property
    def opp_qb_stack_positions(self):
        f_pos = []

        if self.allow_rb_in_opp_qb_stack:
            f_pos.append('RB')

        if self.allow_wr_in_opp_qb_stack:
            f_pos.append('WR')

        if self.allow_te_in_opp_qb_stack:
            f_pos.append('TE')
        return f_pos


class PlayerProjectionField(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    maps_to = models.CharField(max_length=50)

    def __str__(self):
        return '{} = SlatePlayerProjection.{}'.format(self.slug, self.maps_to)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Selection Criteria Field'
        verbose_name_plural = 'Selection Criteria Fields'


class PlayerSelectionCriteria(models.Model):
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    
    # in play thresholds
    qb_threshold = models.TextField(null=True, blank=True, help_text='Forumla for picking qbs in play')
    rb_threshold = models.TextField(null=True, blank=True, help_text='Forumla for picking rbs in play')
    wr_threshold = models.TextField(null=True, blank=True, help_text='Forumla for picking wrs in play')
    te_threshold = models.TextField(null=True, blank=True, help_text='Forumla for picking tes in play')
    dst_threshold = models.TextField(null=True, blank=True, help_text='Forumla for picking dsts in play')

    def __str__(self):
        return '{}'.format(self.name)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'In-Play Criteria'
        verbose_name_plural = 'In-Play Criteria'

    def meets_threshold(self, build_projection):
        # variables used in threshold equations

        locals = {
            'projection': float(build_projection.projection),
            'team_total': float(build_projection.team_total) if build_projection.team_total is not None else 0.0,
            'game_total': float(build_projection.game_total) if build_projection.game_total is not None else 0.0,
            'game_zscore': float(build_projection.game.zscore) if build_projection.game is not None and build_projection.game.zscore is not None else 0.0,
            'spread': float(build_projection.spread) if build_projection.spread is not None else 0.0,
            'adjusted_opportunity': float(build_projection.adjusted_opportunity),
            'position_rank': build_projection.position_rank,
            'zscore': float(build_projection.zscore) if build_projection.zscore else 0.0,
            'ao_zscore': float(build_projection.ao_zscore) if build_projection.ao_zscore else 0.0
        }

        if build_projection.slate_player.site_pos == 'QB' and self.qb_threshold is not None and self.qb_threshold != '':
            return eval(self.qb_threshold, {'__builtins__': {}}, locals)
        elif build_projection.slate_player.site_pos == 'RB' and self.rb_threshold is not None and self.rb_threshold != '':
            return eval(self.rb_threshold, {'__builtins__': {}}, locals)
        elif build_projection.slate_player.site_pos == 'WR' and self.wr_threshold is not None and self.wr_threshold != '':
            return eval(self.wr_threshold, {'__builtins__': {}}, locals)
        elif build_projection.slate_player.site_pos == 'TE' and self.te_threshold is not None and self.te_threshold != '':
            return eval(self.te_threshold, {'__builtins__': {}}, locals)
        elif (build_projection.slate_player.site_pos == 'D' or build_projection.slate_player.site_pos == 'DST') and self.dst_threshold is not None and self.dst_threshold != '':
            return eval(self.dst_threshold, {'__builtins__': {}}, locals)
        
        return True


class LineupConstructionRule(models.Model):
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        ordering = ['name']
        verbose_name = 'Lineup Construction Rule'
        verbose_name_plural = 'Lineup Construction Rules'


class GroupCreationRule(models.Model):
    name = models.CharField(max_length=255)
    construction = models.ForeignKey(LineupConstructionRule, related_name='group_rules', on_delete=models.CASCADE)
    allow_rb = models.BooleanField(default=False)
    allow_wr = models.BooleanField(default=False)
    allow_te = models.BooleanField(default=False)
    at_least = models.PositiveSmallIntegerField(default=0, help_text='At least X players meeting threshold, where X is the number you input')
    at_most = models.PositiveSmallIntegerField(default=0, help_text='At most X players meeting threshold, where X is the number you input')
    threshold = models.TextField(null=True, blank=True, help_text='Forumla for limit threshold')

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        ordering = ['name']
        verbose_name = 'Group Creation Rule'
        verbose_name_plural = 'Group Creation Rules'
    
    @property
    def allowed_positions(self):
        f_pos = []

        if self.allow_rb:
            f_pos.append('RB')

        if self.allow_wr:
            f_pos.append('WR')

        if self.allow_te:
            f_pos.append('TE')
        return f_pos

    def meets_threshold(self, build_projection):
        locals = {
            'projection': float(build_projection.projection),
            'team_total': float(build_projection.team_total) if build_projection.team_total is not None else 0.0,
            'game_total': float(build_projection.game_total) if build_projection.game_total is not None else 0.0,
            'game_zscore': float(build_projection.game.zscore) if build_projection.game is not None and build_projection.game.zscore is not None else 0.0,
            'spread': float(build_projection.spread) if build_projection.spread is not None else 0.0,
            'adjusted_opportunity': float(build_projection.adjusted_opportunity),
            'position_rank': build_projection.position_rank,
            'zscore': float(build_projection.zscore) if build_projection.zscore else 0.0,
            'ao_zscore': float(build_projection.ao_zscore) if build_projection.ao_zscore else 0.0
        }

        if build_projection.slate_player.site_pos in self.allowed_positions:
            return eval(self.threshold, {'__builtins__': {}}, locals)
        
        return False


class StackConstructionRule(models.Model):
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    lock_top_pc = models.BooleanField(default=False)
    top_pc_margin = models.DecimalField(max_digits=4, decimal_places=2, default=2.00)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        ordering = ['name']
        verbose_name = 'Stack Construction Rule'
        verbose_name_plural = 'Stack Construction Rules'

    def passes_rule(self, stack):
        return not self.lock_top_pc or (self.lock_top_pc and stack.contains_top_projected_pass_catcher(self.top_pc_margin))


# Importing


class SheetColumnHeaders(models.Model):
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='4for4')
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    column_player_name = models.CharField(max_length=50)
    column_team = models.CharField(max_length=50)
    column_median_projection = models.CharField(max_length=50)
    column_floor_projection = models.CharField(max_length=50, blank=True, null=True)
    column_ceiling_projection = models.CharField(max_length=50, blank=True, null=True)
    column_rush_att_projection = models.CharField(max_length=50, blank=True, null=True)
    column_rec_projection = models.CharField(max_length=50, blank=True, null=True)
    column_own_projection = models.CharField(max_length=50, blank=True, null=True)
    column_ownership = models.CharField(max_length=50, blank=True, null=True)
    column_score = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = 'Column Headers'
        verbose_name_plural = 'Column Headers'


    def __str__(self):
        return '{} -{}'.format(self.projection_site, self.site)


class SlateProjectionSheet(models.Model):
    slate = models.ForeignKey(Slate, related_name='projections', on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='4for4')
    projection_sheet = models.FileField(upload_to='uploads/projections')

    def __str__(self):
        return '{}'.format(str(self.slate))


class SlatePlayerActualsSheet(models.Model):
    slate = models.OneToOneField(Slate, related_name='actuals', on_delete=models.CASCADE)
    sheet = models.FileField(upload_to='uploads/actuals')

    def __str__(self):
        return '{}'.format(str(self.slate))


class SlatePlayerOwnershipProjectionSheet(models.Model):
    slate = models.OneToOneField(Slate, related_name='ownership_projections_sheets', on_delete=models.CASCADE)
    sheet = models.FileField(upload_to='uploads/ownership_projections')
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='awesemo')

    def __str__(self):
        return '{}'.format(str(self.slate))


class ContestImportSheet(models.Model):
    SITE_OPTIONS = (
        ('draftkings', 'DraftKings'),
        ('fanduel', 'Fanduel'),
        ('yahoo', 'Yahoo'),
    )
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    sheet = models.FileField(upload_to='uploads/contest')

    def __str__(self):
        return '{}'.format(str(self.site))


# Builds


class SlateBuild(models.Model):
    # References
    slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)
    backtest = models.OneToOneField('BacktestSlate', related_name='build', on_delete=models.SET_NULL, null=True, blank=True)

    # Configuration & Rules
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    used_in_contests = models.BooleanField(default=False, verbose_name='Used')
    configuration = models.ForeignKey(SlateBuildConfig, related_name='builds', verbose_name='CFG', on_delete=models.SET_NULL, null=True)
    in_play_criteria = models.ForeignKey(PlayerSelectionCriteria, on_delete=models.SET_NULL, related_name='builds', verbose_name='IPC', null=True, blank=True)
    lineup_construction = models.ForeignKey(LineupConstructionRule, on_delete=models.SET_NULL, related_name='builds', verbose_name='LC', null=True, blank=True)
    stack_construction = models.ForeignKey(StackConstructionRule, on_delete=models.SET_NULL, related_name='builds', verbose_name='SC', null=True, blank=True)
    stack_cutoff = models.SmallIntegerField('SO', default=0, help_text='# of allowe stacks (ex. 80 for FD, and 90 for DK)')
    lineup_start_number = models.IntegerField(default=1)
    total_lineups = models.PositiveIntegerField(verbose_name='total', default=0)
    target_score = models.DecimalField(verbose_name='TRGT', decimal_places=2, max_digits=5, blank=True, null=True)

    # Build analysis
    top_score = models.DecimalField(verbose_name='top', decimal_places=2, max_digits=5, blank=True, null=True)
    total_optimals = models.PositiveIntegerField(default=0, blank=True, null=True)
    total_cashes = models.PositiveIntegerField(verbose_name='cashes', blank=True, null=True)
    total_one_pct = models.PositiveIntegerField(verbose_name='1%', blank=True, null=True)
    total_half_pct = models.PositiveIntegerField(verbose_name='0.5%', blank=True, null=True)
    great_build = models.BooleanField(verbose_name='gb', default=False)
    binked = models.BooleanField(verbose_name='bink', help_text='Finished 1st, 2nd, or 3rd', default=False)
    notes = models.TextField(blank=True, null=True)

    # Build Status
    status = models.CharField(max_length=25, choices=BUILD_STATUS, default='not_started')
    projections_ready = models.BooleanField(default=False)
    construction_ready = models.BooleanField(default=False)
    pct_complete = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    optimals_pct_complete = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    error_message = models.TextField(blank=True, null=True)
    elapsed_time = models.DurationField(default=datetime.timedelta())

    class Meta:
        verbose_name = 'Slate Build'
        verbose_name_plural = 'Slate Builds'

    def __str__(self):
        return '{} ({}) @ {}'.format(self.slate.name, self.configuration, self.created.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %H:%M'))

    @property
    def ready(self):
        return self.projections_ready and self.construction_ready

    def num_in_play(self, pos):
        return self.projections.filter(slate_player__site_pos=pos, in_play=True).count()

    def reset(self):
        self.clear_analysis()

        for stack in self.stacks.all():
            stack.reset()

        self.status = 'not_started'
        self.error_message = None
        self.pct_complete = 0.0
        self.elapsed_time = datetime.timedelta()
        self.save()

        self.calc_projections_ready()
        self.calc_construction_ready()

    def clear_analysis(self):
        self.top_score = None
        self.total_optimals = 0.0
        self.total_cashes = None
        self.total_one_pct = None
        self.total_half_pct = None
        self.great_build = False
        self.binked = False        

    def calc_projections_ready(self):
        self.projections_ready = self.projections.all().count() >= self.slate.num_projected_players()
        self.save()

    def calc_construction_ready(self):
        groups_ready = False
        if self.lineup_construction is None:
            groups_ready = True
        else:
            group_rules = self.lineup_construction.group_rules.all()
            groups = SlateBuildGroup.objects.filter(
                build=self
            )
            groups_ready = groups.count() >= group_rules.count()

        if self.stack_construction is not None and self.stack_construction.lock_top_pc:
            stacks_ready = self.stacks.all().count() >= self.stack_cutoff * 0.50
        else:
            stacks_ready = self.stacks.all().count() >= self.stack_cutoff * 0.90

        self.construction_ready = groups_ready and stacks_ready
        self.save()
    
    def analyze_projections(self):
        qs = BuildPlayerProjection.objects.filter(
            build=self
        )

        qs = qs.annotate(
            site_pos=F('slate_player__site_pos'), 
            player_salary=F('slate_player__salary')            
        )
        qs = qs.annotate(
            player_value=ExpressionWrapper(F('projection')/(F('player_salary')/1000), output_field=FloatField())
        )

        qs = qs.annotate(
            proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('projection').asc()
            ),
            value_proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('player_value').asc()
            ),
            own_proj_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('ownership_projection').desc()
            ),
            ao_percentile=Window(
                expression=PercentRank(),
                partition_by=['site_pos'],
                order_by=F('adjusted_opportunity').asc()
            ),
        )

        for p in qs:
            p.value = p.player_value
            p.projection_percentile = p.proj_percentile
            p.ownership_projection_percentile =  p.own_proj_percentile
            p.value_projection_percentile = p.value_proj_percentile
            p.rb_group = 0
            if p.position == 'RB':
                p.adjusted_opportunity_percentile = p.ao_percentile
                p.rating = float(p.proj_percentile) + float(p.proj_percentile) + float(p.ao_percentile) + float(p.own_proj_percentile) + float(p.value_proj_percentile)
            else:
                p.rating = float(p.proj_percentile) + float(p.proj_percentile) + float(p.own_proj_percentile) + float(p.value_proj_percentile)

            p.save()

    def prepare_projections(self):
        self.projections_ready = False
        self.save()

        # copy default projections if they don't exist
        self.update_projections(replace=True)
        self.analyze_projections()

        # find players that are in-play
        for projection in self.projections.all():
            projection.find_in_play()
            # projection.set_rb_group_value()
        
        # find stack-only players
        self.find_stack_only()

        self.calc_projections_ready()

        self.get_target_score()

    def prepare_construction(self):
        self.construction_ready = False
        self.save()

        self.groups.all().delete()

        # create groups
        if self.lineup_construction is not None:
            for (index, group_rule) in enumerate(self.lineup_construction.group_rules.all()):
                group = SlateBuildGroup.objects.create(
                    build=self,
                    name='{}: Group {}'.format(self.slate.name, index+1),
                    min_from_group=group_rule.at_least,
                    max_from_group=group_rule.at_most
                )

                # add players to group
                for projection in self.projections.filter(in_play=True, slate_player__site_pos__in=group_rule.allowed_positions):
                    if group_rule.meets_threshold(projection):
                        SlateBuildGroupPlayer.objects.create(
                            group=group,
                            slate_player=projection.slate_player
                        )

                group.save()
    
        # create stacks
        self.create_stacks()

        # clean stacks
        self.clean_stacks()

        self.total_lineups = self.stacks.all().aggregate(total=Sum('count')).get('total') 
        self.save()

        self.calc_construction_ready()

    def get_target_score(self):
        top_projected_lineup = optimize.optimize(
            self.slate.site,
            self.projections.all()
        )[0]

        self.target_score = top_projected_lineup.fantasy_points_projection
        self.save()

    def update_projections(self, replace=True):
        '''
        Makes or updates build specific projections from slate projections
        '''

        # for each player on slate, update (or add) that player's projection for this build
        for player in self.slate.players.all():
            # if a player projection exists for this player, add him to build projection 
            if hasattr(player, 'projection'):
                (projection, created) = BuildPlayerProjection.objects.get_or_create(
                    build=self,
                    slate_player=player
                )
                
                # only replace values if projection is new or replace == true
                if replace or created:
                    projection.projection = player.projection.projection
                    projection.value = round(float(player.projection.projection)/(player.salary/1000.0), 2)
                    projection.ownership_projection = player.projection.ownership_projection
                    projection.balanced_projection = player.projection.balanced_projection
                    projection.balanced_value = round(float(player.projection.balanced_projection)/(player.salary/1000.0), 2)
                    projection.adjusted_opportunity = player.projection.adjusted_opportunity
                    projection.rb_group = 0

                    if projection.position == 'DST' or projection.position == 'D':
                        projection.max_exposure = self.configuration.max_dst_exposure * 100

                    projection.save()
            else:
                # player projection does not exist so remove build projection if it exists
                try:
                    projection = BuildPlayerProjection.objects.get(
                        build=self,
                        slate_player=player
                    )
                    projection.delete()
                except BuildPlayerProjection.DoesNotExist:
                    pass

    def find_stack_only(self):
        for game in self.slate.games.all():
            self.projections.filter(
                slate_player__team=game.game.home_team
            ).update(stack_only=False)

            # Get all WR/TE from team
            pass_catchers = self.projections.filter(
                Q(slate_player__team=game.game.home_team),
                Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')
            ).order_by('-projection')

            # Get all WR/TE from opposing team
            opp_pass_catchers = self.projections.filter(
                Q(slate_player__team=game.game.away_team),
                Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')
            ).order_by('-projection')

            for (index, pass_catcher) in enumerate(pass_catchers):
                pass_catcher.find_in_play()

                if not pass_catcher.in_play:
                    pass_catcher.stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.in_play = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.opp_qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                else:
                    pass_catcher.stack_only = False
                    pass_catcher.qb_stack_only = True
                    pass_catcher.opp_qb_stack_only = True

                pass_catcher.save()

            for (index, pass_catcher) in enumerate(opp_pass_catchers):
                pass_catcher.find_in_play()

                if not pass_catcher.in_play:
                    pass_catcher.stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.in_play = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                    pass_catcher.opp_qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
                else:
                    pass_catcher.stack_only = False
                    pass_catcher.qb_stack_only = True
                    pass_catcher.opp_qb_stack_only = True

                pass_catcher.save()

    def balance_rbs(self):
        rbs = self.projections.filter(slate_player__site_pos='RB', in_play=True)

        for rb in rbs:
            rb.balanced_projection = rb.projection
            rb.save()

        rbs = rbs.annotate(
            player_salary=F('slate_player__salary')            
        )
        rbs = rbs.annotate(
            player_value=ExpressionWrapper(F('projection')/(F('player_salary')/1000), output_field=FloatField())
        )

        rbs = rbs.annotate(
            proj_percentile=Window(
                expression=PercentRank(),
                order_by=F('projection').asc()
            ),
            value_projection_percentile=Window(
                expression=PercentRank(),
                order_by=F('player_value').asc()
            ),
            ao_percentile=Window(
                expression=PercentRank(),
                order_by=F('adjusted_opportunity').asc()
            ),
            proj_rating=ExpressionWrapper(F('proj_percentile') + F('proj_percentile') + F('ao_percentile'), output_field=FloatField())
        )

        rbs = list(rbs.order_by('-proj_rating'))
        processed = []
        for (index, rb) in enumerate(rbs):
            processed.append(rb.id)
            if index < len(rbs) - 1:
                rb_value = float(rb.balanced_projection) / (float(rb.salary) / 1000)
                rb2 = rbs[index+1]
                diff = rb.compare(rb2)
                print(rb.name, rb_value, rb2.name, diff)
                if abs(diff) <= .02:  # means they are "the same" player
                    rb2.balanced_projection = rb2.salary / 1000 * rb_value
        
        for rb in rbs:
            rb.save()
               
    def num_possible_stacks(self):
        num_stacks = 0
        qbs = self.projections.filter(slate_player__site_pos='QB', in_play=True)

        for qb in qbs:
            stack_players = self.projections.filter(
                Q(Q(slate_player__site_pos__in=self.configuration.qb_stack_positions) | Q(site_pos__in=self.configuration.opp_qb_stack_positions))
            ).filter(
                Q(Q(qb_stack_only=True, team=qb.team) | Q(opp_qb_stack_only=True, team=qb.get_opponent()))
            )

            # team_players includes all in-play players on same team as qb, including stack-only players
            team_players = stack_players.filter(slate_player__team=qb.team, slate_player__site_pos__in=self.configuration.qb_stack_positions).order_by('-balanced_projection')
            # opp_players includes all in-play players on opposing team, including stack-only players that are allowed in opponent stack
            opp_players = stack_players.filter(slate_player__game=qb.game, slate_player__site_pos__in=self.configuration.opp_qb_stack_positions).exclude(slate_player__team=qb.team).order_by('-balanced_projection')

            am1_players = team_players.filter(
                Q(Q(stack_only=True) | Q(at_most_one_in_stack=True))
            )
            team_has_all_stack_only = (am1_players.count() == team_players.count())

            if self.configuration.game_stack_size == 3:
                num_stacks += ((math.factorial(team_players.count())/(math.factorial(team_players.count() - 1))) * (math.factorial(opp_players.count())/(math.factorial(opp_players.count() - 1))))

            elif self.configuration.game_stack_size == 4:
                num_stacks += ((math.factorial(team_players.count())/(math.factorial(team_players.count() - 2) * math.factorial(2))) * (math.factorial(opp_players.count())/(math.factorial(opp_players.count() - 1))))

        return num_stacks         

    def create_stacks(self):
        # Delete existing stacks for this build
        SlateBuildStack.objects.filter(build=self).delete()

        # get all qbs in play
        qbs = self.projections.filter(slate_player__site_pos='QB', in_play=True)
        total_qb_projection = qbs.aggregate(total_projection=Sum('projection')).get('total_projection')
        
        # for each qb, create all possible stacking configurations
        for qb in qbs:
            tasks.create_stacks_for_qb(self.id, qb.id, total_qb_projection)

        self.calc_zscores_for_stacks()
        self.rank_stacks()

    def rank_stacks(self):
        stacks = self.stacks.all().order_by('-projection')
        for (index, stack) in enumerate(stacks):
            stack.rank = index + 1
            stack.save()

    def clean_stacks(self):
        '''
        Will remove all but {stack_cutoff} stacks, and then redistribute the removed lineups evenly
        '''
        if self.stack_cutoff > 0:
            ordered_stacks = self.stacks.all().order_by('-projection')[:self.stack_cutoff]

            # delete stacks not in this queryset
            self.stacks.exclude(id__in=list(ordered_stacks.values_list('id', flat=True))).update(count=0)

            num_lineups_to_distribute = self.total_lineups - sum(s.count for s in ordered_stacks)
            for stack in ordered_stacks:
                stack.count += math.ceil(num_lineups_to_distribute/self.stack_cutoff)
                stack.save()

    def calc_zscores_for_stacks(self):
        projections = list(self.stacks.all().order_by('-projection').values_list('projection', flat=True))
        zscores = scipy.stats.zscore(projections)

        for (index, stack) in enumerate(self.stacks.all().order_by('-projection')):
            stack.projection_zscore = zscores[index]
            stack.save()

    def speed_test(self):
        _ = optimize.optimize(
            self.slate.site,
            self.projections.all(),
            10
        )

    def execute_build(self, user):
        self.total_lineups = SlateBuildStack.objects.filter(build=self).aggregate(total=Sum('count')).get('total')
        self.stacks.all().update(lineups_created=False)
        
        self.status = 'running'
        self.error_message = None
        self.pct_complete = 0.0
        self.save()

        task = BackgroundTask()
        task.name = 'Build Lineups'
        task.user = user
        task.save()

        tasks.monitor_build.delay(self.id, task.id)

        last_qb = None
        stacks = self.stacks.filter(count__gt=0).order_by('-qb__projection', 'qb__slate_player', 'build_order')
        for stack in stacks:
            qb = stack.qb.id
            num_qb_stacks = self.stacks.filter(qb__id=qb).count()
            if last_qb is None or qb != last_qb:
                lineup_number = 1
            else:
                lineup_number += 1

            tasks.build_lineups_for_stack.delay(stack.id, lineup_number, num_qb_stacks)

            last_qb = qb

    def analyze_lineups(self):
        if self.slate.contests.count() > 0:
            contest = self.slate.contests.get(outcomes_sheet__isnull=False)
            build_lineups = self.lineups.all().order_by('id')
            build_lineups.update(ev=0, mean=0, std=0)

            tasks.analyze_lineups_page(self.id, contest.id, list(build_lineups.values_list('id', flat=True)), False)

    def clean_lineups(self):
        if self.configuration.lineup_removal_pct > 0.0:
            sorted = self.lineups.all().order_by('-projection')
            projections = numpy.array([float(v) for v in sorted.values_list('projection', flat=True)])
            target_score = numpy.percentile(projections, int(float(self.configuration.lineup_removal_pct) * 100))

            sorted.filter(projection__lt=target_score).delete()

    def update_build_progress(self):
        all_stacks = self.stacks.filter(count__gt=0)
        remaining_stacks = all_stacks.filter(lineups_created=False)
        if remaining_stacks.count() == 0:
            self.pct_complete = 1.0
            self.status = 'complete'
            self.save()

            self.clean_lineups()

            self.find_expected_lineup_order()

            if self.backtest is not None:
                # analyze build
                self.get_actual_scores()
        else:
            self.pct_complete = (all_stacks.count() - remaining_stacks.count()) / all_stacks.count()
            self.save()

    def handle_exception(self, stack, exc):
        # if a stack has an error, remove unmade lineups from total
        self.total_lineups -= (stack.count - stack.times_used)

        if self.error_message is None or self.error_message == '':
            self.error_message = '{} Error: {}'.format(stack, str(exc))
        else:
             self.error_message = '\n{} Error: {}'.format(stack, str(exc))
        
        self.save()

    def find_expected_lineup_order(self): 
        for (index, lineup) in enumerate(self.lineups.all().order_by('order_number', '-qb__projection')):
            lineup.expected_lineup_order = index + 1
            lineup.save()

    def num_lineups_created(self):
        return self.lineups.all().count()
    num_lineups_created.short_description = 'created'
    
    def num_stacks_created(self):
        return self.stacks.all().count()
    
    def num_groups_created(self):
        return self.groups.all().count()

    def get_actual_scores(self):
        contest = self.slate.contests.all()[0]

        top_score = 0
        total_cashes = 0
        total_one_pct = 0
        total_half_pct = 0
        binked = False
        great_build = False

        for stack in self.stacks.all():
            stack.calc_actual_score()

        for lineup in self.lineups.all():
            score = lineup.calc_actual_score()
            top_score = max(top_score, score)
            if score >= contest.mincash_score:
                total_cashes += 1
            if score >= contest.one_pct_score:
                total_one_pct += 1
            if score >= contest.half_pct_score:
                total_half_pct += 1
            if score >= contest.winning_score:
                binked = True
            if score >= contest.great_score:
                great_build = True

        self.top_score = top_score
        self.total_cashes = total_cashes
        self.total_one_pct = total_one_pct
        self.total_half_pct = total_half_pct
        self.great_build = great_build
        self.binked = binked
        self.save()

    def num_actuals_created(self):
        return self.actuals.all().count()

    def get_exposure(self, slate_player):
        return self.lineups.filter(
            Q(
                Q(qb__slate_player__id=slate_player.id) | 
                Q(rb1__slate_player__id=slate_player.id) |
                Q(rb2__slate_player__id=slate_player.id) |
                Q(wr1__slate_player__id=slate_player.id) |
                Q(wr2__slate_player__id=slate_player.id) |
                Q(wr3__slate_player__id=slate_player.id) |
                Q(te__slate_player__id=slate_player.id) |
                Q(flex__slate_player__id=slate_player.id) |
                Q(dst__slate_player__id=slate_player.id)
            )
        ).count()

    def build_optimals(self):
        self.actuals.all().delete()
        self.total_optimals = 0
        self.optimals_pct_complete = 0.0
        self.save()
        
        self.stacks.all().update(optimals_created=False)

        tasks.monitor_build_optimals.delay(self.id)

        for stack in self.stacks.filter(count__gt=0):
            tasks.build_optimals_for_stack.delay(stack.id)

    def analyze_optimals(self):
        if self.slate.contests.count() > 0:
            contest = self.slate.contests.get(outcomes_sheet__isnull=False)
            optimals = self.actuals.all().order_by('id')
            optimals.update(ev=0, mean=0, std=0)

            tasks.analyze_lineups_page(self.id, contest.id, list(optimals.values_list('id', flat=True)), True)

    def top_optimal_score(self):
        return self.actuals.all().aggregate(top_score=Max('actual')).get('top_score')
    top_optimal_score.short_description = 'Top Opt'
    
    def balance_rbs_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Balance RBs</a>',
            reverse_lazy("admin:admin_slatebuild_balance_rbs", args=[self.pk])
        )
    balance_rbs_button.short_description = ''
    
    def speed_test_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Test</a>',
            reverse_lazy("admin:admin_slatebuild_speed_test", args=[self.pk])
        )
    speed_test_button.short_description = ''
    
    def prepare_projections_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #a41515; font-weight: bold; padding: 10px 15px;">Prep Proj</a>',
            reverse_lazy("admin:admin_slatebuild_prepare_projections", args=[self.pk])
        )
    prepare_projections_button.short_description = ''
    
    def prepare_construction_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #f5dd5d; font-weight: bold; padding: 10px 15px;">Prep Const</a>',
            reverse_lazy("admin:admin_slatebuild_prepare_construction", args=[self.pk])
        )
    prepare_construction_button.short_description = ''
    
    def simulate_stacks_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #f5dd5d; font-weight: bold; padding: 10px 15px;">Sim Stacks</a>',
            reverse_lazy("admin:admin_slatebuild_sim_stacks", args=[self.pk])
        )
    simulate_stacks_button.short_description = ''

    def build_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Build</a>',
            reverse_lazy("admin:admin_slatebuild_build", args=[self.pk])
        )
    build_button.short_description = ''
    
    def export_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #5b80b2; font-weight: bold; padding: 10px 15px;">Export</a>',
            reverse_lazy("admin:admin_slatebuild_export", args=[self.pk])
        )
    export_button.short_description = ''
    
    def view_page_button(self):
        return format_html('<a href="/admin/nfl/buildplayerprojection/?build_id={}" class="link" style="color: #ffffff; background-color: #bf3030; font-weight: bold; padding: 10px 15px;">Proj</a>',
            self.pk)
    view_page_button.short_description = ''


class BuildPlayerProjection(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='projections', on_delete=models.CASCADE)
    slate_player = models.ForeignKey(SlatePlayer, db_index=True, related_name='build_projections', on_delete=models.CASCADE)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Proj')
    ownership_projection = models.DecimalField(max_digits=3, decimal_places=2, db_index=True, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='AO')
    value = models.DecimalField('V', max_digits=5, decimal_places=2, default=0.0, db_index=True)
    projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    ownership_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    value_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    adjusted_opportunity_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rating = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rb_group_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, null=True, blank=True)
    rb_group = models.PositiveIntegerField('RBG', default=0, null=True, blank=True)
    balanced_projection = models.DecimalField('BP', null=True, blank=True, max_digits=5, decimal_places=2, default=0.0)
    balanced_value = models.DecimalField('BV', max_digits=5, decimal_places=2, default=0.0, db_index=True)
    in_play = models.BooleanField(default=True, db_index=True)
    stack_only = models.BooleanField(default=False, verbose_name='SO', help_text='Player is only in pool when stacked with QB or opposing QB')
    qb_stack_only = models.BooleanField(default=False, verbose_name='SwQB', help_text='Generate QB stacks with this player')
    opp_qb_stack_only = models.BooleanField(default=False, verbose_name='SwOQB', help_text='Generate Opp QB stacks with this player')
    at_most_one_in_stack = models.BooleanField(default=False, verbose_name='AM1', help_text='Generate stacks with only 1 of players with this designation')
    at_least_one_in_lineup = models.BooleanField(default=False, verbose_name='AL1', help_text='At least one player with this designation should appear in every lineup')
    at_least_two_in_lineup = models.BooleanField(default=False, verbose_name='AL2', help_text='At least two players with this designation should appear in every lineup')
    min_exposure = models.IntegerField('Min', default=0)
    max_exposure = models.IntegerField('Max', default=100)
    locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Player Projection'
        verbose_name_plural = 'Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return '{} -- Proj: {} -- GT: {:.2f}'.format(str(self.slate_player), self.projection, self.game_total if self.game_total is not None else 0.0)

    @property
    def name(self):
        return self.slate_player.name

    @property
    def salary(self):
        return self.slate_player.salary

    @property
    def team(self):
        return self.slate_player.team

    @property
    def position(self):
        return self.slate_player.site_pos

    @property
    def position_rank(self):
        rank = self.build.projections.filter(
            slate_player__site_pos=self.slate_player.site_pos,
            projection__gt=self.projection if self.projection else 0
        ).count()
        return rank + 1

    @property
    def exposure(self):
        if self.build.lineups.all().count() > 0:
            return self.build.lineups.filter(
                Q(
                    Q(qb=self) | 
                    Q(rb1=self) | 
                    Q(rb2=self) | 
                    Q(wr1=self) | 
                    Q(wr2=self) | 
                    Q(wr3=self) | 
                    Q(te=self) | 
                    Q(flex=self) | 
                    Q(dst=self)
                )
            ).count() / self.build.lineups.all().count()
        return 0

    @property
    def available_projections(self):
        return self.slate_player.raw_projections.all()

    @property
    def team_total(self):
        return self.slate_player.team_total

    @property
    def game_total(self):
        return self.slate_player.game_total

    @property
    def spread(self):
        return self.slate_player.spread

    @property
    def game(self):
        return self.slate_player.slate_game

    @property
    def zscore(self):
        if self.slate_player.projection and self.slate_player.projection.zscore:
            return self.slate_player.projection.zscore
        return None

    @property
    def ao_zscore(self):
        if self.slate_player.projection and self.slate_player.projection.ao_zscore:
            return self.slate_player.projection.ao_zscore
        return None

    @property
    def sim_scores(self):
        return self.slate_player.projection.sim_scores

    def get_team_color(self):
        return self.slate_player.get_team_color()

    def get_opponent(self):
        return self.slate_player.get_opponent()

    def set_rb_group_value(self):
        if self.slate_player.site_pos == 'RB':
            self.rb_group_value = float(self.projection) * 6 + float(self.adjusted_opportunity) * 4
            self.balanced_projection = self.rb_group_value / 10
            self.save()

    def find_in_play(self):
        self.in_play = self.build.in_play_criteria.meets_threshold(self)
        self.save()

    def compare(self, player2):
        '''
        Returns a number between -1 and 1 that indicates differences between 2 players.

        A value of -1.0 indicates that player 1 is 100% different (worse) than player 2
        A value of 0.0 indicates the two players are exactly the same
        A value of 1.0 indicates that player 1 is 100% different (better) than player 2

        value = (Sum of player1's metric percentiles - Sum of player2's metric percentiles) / Sum of player2's metric percentiles
        '''
        if self.position != player2.position:
            raise Exception('{} and {} cannot be compared as they play different positions'.format(self.name, player2.name))
        
        player1_rating = self.projection_rating
        player2_rating = player2.projection_rating

        return (player1_rating - player2_rating) / max(player1_rating, player2_rating)


class SlateBuildStack(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='stacks', on_delete=models.CASCADE)
    game = models.ForeignKey(SlateGame, db_index=True, related_name='stacks', on_delete=models.SET_NULL, blank=True, null=True)
    mini_game = models.ForeignKey(SlateGame, db_index=True, related_name='mini_stacks', on_delete=models.SET_NULL, blank=True, null=True)
    build_order = models.PositiveIntegerField(default=1, db_index=True)
    rank = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    qb = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='qb_stacks', on_delete=models.CASCADE)
    player_1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='p1_stacks', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='p2_stacks', on_delete=models.CASCADE, blank=True, null=True)
    opp_player = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='opp_stacks', on_delete=models.CASCADE, blank=True, null=True)
    mini_player_1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='mini_1_stacks', on_delete=models.CASCADE, blank=True, null=True)
    mini_player_2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='mini_2_stacks', on_delete=models.CASCADE, blank=True, null=True)
    contains_top_pc = models.BooleanField(default=False, db_index=True)
    salary = models.PositiveIntegerField(db_index=True)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    projection_zscore = models.DecimalField('Z-Score', db_index=True, max_digits=6, decimal_places=4, default=0.0000)
    count = models.PositiveIntegerField(default=0, db_index=True, help_text='# of lineups in which this stack should appear')
    times_used = models.PositiveIntegerField(default=0, db_index=True)
    lineups_created = models.BooleanField(default=False)
    optimals_created = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)
    actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_index=True)

    class Meta:
        verbose_name = 'Stack'
        verbose_name_plural = 'Stacks'
        ordering = ['-qb__projection', '-count', '-projection']
        
    def __str__(self):
        return '{} Stack {}'.format(self.qb.name, self.build_order)

    @property
    def players(self):
        p = [
            self.qb,
            self.player_1
        ]
        if self.player_2:
            p.append(self.player_2)
        if self.opp_player:
            p.append(self.opp_player)
        if self.mini_player_1:
            p.append(self.mini_player_1)
        if self.mini_player_2:
            p.append(self.mini_player_2)
        
        return p

    def contains_top_projected_pass_catcher(self, margin=2.0):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            build=self.build,
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.team
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= margin]
            
            return self.player_1 in top_projected_players or (self.player_2 is not None and self.player_2 in top_projected_players)
        return False
    contains_top_projected_pass_catcher.short_description = '#1 PC?'
    contains_top_projected_pass_catcher.boolean = True

    def contains_opp_top_projected_pass_catcher(self):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.get_opponent()
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

            return self.opp_player in top_projected_players
        return False
    contains_opp_top_projected_pass_catcher.short_description = '#1 OPP PC?'
    contains_opp_top_projected_pass_catcher.boolean = True

    def contains_slate_player(self, slate_player):
        return self.qb.slate_player == slate_player or self.player_1.slate_player == slate_player or (self.player_2 is not None and self.player_2.slate_player == slate_player) or (self.opp_player is not None and self.opp_player.slate_player == slate_player)

    def calc_salary(self):
        slate_player_ids = [p.slate_player.id for p in self.players]
        salary = sum(p.salary for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
        self.salary = salary
        self.save()

        return salary        

    def calc_projection(self):
        slate_player_ids = [p.slate_player.id for p in self.players]
        projection = sum(p.projection for p in SlatePlayerProjection.objects.filter(slate_player__id__in=slate_player_ids))
        self.actual = projection
        self.save()

        return projection        

    def calc_actual_score(self):
        slate_player_ids = [p.slate_player.id for p in self.players]
        score = sum(p.fantasy_points for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
        self.actual = score
        self.save()

        return score                

    def calc_sim_scores(self):
        mu = float(sum(p.projection for p in [self.qb, self.player_1, self.player_2, self.opp_player]))
        sim_scores = [min(i * mu, 999.99) for i in scipy.stats.exponweib.rvs(3.2212819188775237, 1.8784436736213124, loc=-0.08318691129888284, scale=0.782305472516587, size=settings.SIMULATION_SIZE)]
        self.sim_scores = sim_scores
        self.save()

    def has_possible_optimals(self):
        '''
        Returns true if this stack can make at least 1 lineup in the top 1% of the milly
        '''
        lineups = optimize.optimize_for_stack(
            self.build.slate.site,
            self,
            self.build.projections.all(),
            self.build.slate.teams,
            self.build.configuration,
            1,
            self.build.groups.filter(active=True),
            for_optimals=True
        )

        if len(lineups) > 0:
            lineup = lineups[0]
            return lineup.fantasy_points_projection >= self.build.slate.get_great_score()

        return False

    def reset(self):
        self.lineups.all().delete()
        self.times_used = 0
        self.lineups_created = False
        self.error_message = None
        self.save()

    def build_lineups_for_stack(self, lineup_number, num_qb_stacks):
        self.reset()

        try:
            lineups = optimize.optimize_for_stack(
                self.build.slate.site,
                self,
                self.build.projections.all(),
                self.build.slate.teams,
                self.build.configuration,
                self.count,
                groups=self.build.groups.filter(active=True)
            )

            count = 0
            for (index, lineup) in enumerate(lineups):
                count += 1
                player_ids = [p.id for p in lineup.players]
                SlateBuildLineup.objects.create(
                    build=self.build,
                    stack=self,
                    order_number=lineup_number + (num_qb_stacks * index),
                    qb=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[0].id, build=self.build),
                    rb1=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[1].id, build=self.build),
                    rb2=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[2].id, build=self.build),
                    wr1=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[3].id, build=self.build),
                    wr2=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[4].id, build=self.build),
                    wr3=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[5].id, build=self.build),
                    te=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[6].id, build=self.build),
                    flex=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[7].id, build=self.build),
                    dst=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[8].id, build=self.build),
                    salary=lineup.salary_costs,
                    projection=lineup.fantasy_points_projection,
                    ownership_projection=sum(x.projection for x in BuildPlayerProjection.objects.filter(build=self.build, slate_player__player_id__in=player_ids))
                )

            self.times_used = count
            self.lineups_created = True
            self.save()
        except Exception as exc:
            traceback.print_exc()
            self.lineups_created = True
            self.error_message = str(exc)
            self.save()

            self.build.handle_exception(self, exc)

    def build_optimals(self, num_lineups=1):  
        lineups = optimize.optimize_for_stack(
            self.build.slate.site,
            self,
            self.build.projections.all(),
            self.build.slate.teams,
            self.build.configuration,
            num_lineups,
            self.build.groups.filter(active=True),
            for_optimals=True
        )

        for lineup in lineups:
            if lineup.fantasy_points_projection >= self.build.slate.get_great_score():
                db_lineup = SlateBuildActualsLineup.objects.create(
                    build=self.build,
                    stack=self,
                    qb=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[0].id, build=self.build),
                    rb1=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[1].id, build=self.build),
                    rb2=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[2].id, build=self.build),
                    wr1=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[3].id, build=self.build),
                    wr2=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[4].id, build=self.build),
                    wr3=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[5].id, build=self.build),
                    te=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[6].id, build=self.build),
                    flex=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[7].id, build=self.build),
                    dst=BuildPlayerProjection.objects.get(slate_player__player_id=lineup.players[8].id, build=self.build),
                    salary=lineup.salary_costs,
                    actual=lineup.fantasy_points_projection
                )
                # db_lineup.simulate()

    def num_tes(self):
        count = 0
        for p in self.players():
            if p.slate_player.site_pos == 'TE':
                count += 1
        return count

    def get_median_sim_score(self):
        if self.sim_scores:
            return numpy.median(self.sim_scores)
        return 0

    def get_percentile_sim_score(self, percentile):
        if self.sim_scores:
            return numpy.percentile([float(i) for i in self.sim_scores], percentile)
        return 0

    def get_ceiling_sim_score(self):
        if self.sim_scores:
            return self.get_percentile_sim_score(90)
        return 0


class SlateBuildLineup(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
    stack = models.ForeignKey(SlateBuildStack, db_index=True, verbose_name='Stack', related_name='lineups', on_delete=models.CASCADE, null=True, blank=True)
    order_number = models.IntegerField(default=0, db_index=True)
    expected_lineup_order = models.PositiveIntegerField(default=0, db_index=True)
    qb = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='qb', on_delete=models.CASCADE)
    rb1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='rb1', on_delete=models.CASCADE)
    rb2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='rb2', on_delete=models.CASCADE)
    wr1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='wr1', on_delete=models.CASCADE)
    wr2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='wr2', on_delete=models.CASCADE)
    wr3 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='wr3', on_delete=models.CASCADE)
    te = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='te', on_delete=models.CASCADE)
    flex = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex', on_delete=models.CASCADE)
    dst = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='dst', on_delete=models.CASCADE)
    salary = models.PositiveIntegerField(db_index=True)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    ownership_projection = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, db_index=True)
    ownership_projection_percentile = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    rating = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
    ev = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, db_index=True)
    mean = models.DecimalField(db_index=True, max_digits=100, decimal_places=2, default=0.0)
    std = models.DecimalField(db_index=True, max_digits=100, decimal_places=2, default=0.0)
    actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)

    class Meta:
        verbose_name = 'Lineup'
        verbose_name_plural = 'Lineups'
        ordering = ['-actual', 'order_number', '-qb__projection']

    @property
    def players(self):
        return [
            self.qb, 
            self.rb1,
            self.rb2,
            self.wr1,
            self.wr2,
            self.wr3,
            self.te,
            self.flex,
            self.dst
        ]

    @property
    def non_stack_sim_scores(self):
        matrix = [
            self.rb1.sim_scores,
            self.rb2.sim_scores,
        ]

        if not self.stack.contains_slate_player(self.wr1.slate_player):
            matrix.append(self.wr1.sim_scores)    
        if not self.stack.contains_slate_player(self.wr2.slate_player):
            matrix.append(self.wr2.sim_scores)    
        if not self.stack.contains_slate_player(self.wr3.slate_player):
            matrix.append(self.wr3.sim_scores)    
        if not self.stack.contains_slate_player(self.te.slate_player):
            matrix.append(self.te.sim_scores)    
        if not self.stack.contains_slate_player(self.flex.slate_player):
            matrix.append(self.flex.sim_scores) 
        
        matrix.append(self.dst.sim_scores)

        return matrix  

    def contains_top_projected_pass_catcher(self):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            build=self.build,
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.team,
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

            return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
        return False
    contains_top_projected_pass_catcher.short_description = '#1 PC?'
    contains_top_projected_pass_catcher.boolean = True

    def contains_opp_top_projected_pass_catcher(self):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.get_opponent()
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

            return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
        return False
    contains_opp_top_projected_pass_catcher.short_description = '#1 OPP PC?'
    contains_opp_top_projected_pass_catcher.boolean = True

    def get_num_rbs(self):
        if self.flex.slate_player.site_pos == 'RB':
            return 3
        return 2

    def get_num_wrs(self):
        if self.flex.slate_player.site_pos == 'WR':
            return 4
        return 3

    def get_num_tes(self):
        if self.flex.slate_player.site_pos == 'TE':
            return 2
        return 1

    def get_rbs(self):
        rbs = [self.rb1, self.rb2]
        if self.get_num_rbs() > 2:
            rbs.append(self.flex)
        return rbs

    def get_rbs_by_salary(self):
        rbs = self.get_rbs()       
        rbs.sort(key=lambda p: p.slate_player.salary, reverse=True)
        return rbs

    def get_wrs(self):
        wrs = [self.wr1, self.wr2, self.wr3]
        if self.get_num_wrs() > 3:
            wrs.append(self.flex)        
        return wrs

    def get_wrs_by_salary(self):
        wrs = self.get_wrs()
        wrs.sort(key=lambda p: p.slate_player.salary, reverse=True)
        return wrs

    def get_tes(self):
        tes = [self.te]
        if self.get_num_tes() > 1:
            tes.append(self.flex)
        return tes

    def get_tes_by_salary(self):
        tes = self.get_tes()
        tes.sort(key=lambda  p: p.slate_player.salary, reverse=True)
        return tes
        
    def calc_actual_score(self):
        slate_player_ids = [p.slate_player.id for p in self.players]
        score = sum(p.fantasy_points for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
        self.actual = score
        self.save()

        return score        

    def simulate(self):
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.save()


class SlateBuildActualsLineup(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='actuals', on_delete=models.CASCADE)
    stack = models.ForeignKey(SlateBuildStack, db_index=True, verbose_name='Stack', related_name='actuals', on_delete=models.CASCADE, null=True, blank=True)
    expected_lineup_order = models.PositiveIntegerField(db_index=True, default=0)
    qb = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_qb', on_delete=models.CASCADE)
    rb1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_rb1', on_delete=models.CASCADE)
    rb2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_rb2', on_delete=models.CASCADE)
    wr1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_wr1', on_delete=models.CASCADE)
    wr2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_wr2', on_delete=models.CASCADE)
    wr3 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_wr3', on_delete=models.CASCADE)
    te = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_te', on_delete=models.CASCADE)
    flex = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_flex', on_delete=models.CASCADE)
    dst = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='actuals_dst', on_delete=models.CASCADE)
    salary = models.PositiveIntegerField(db_index=True)
    sim_scores = ArrayField(models.DecimalField(db_index=True, max_digits=5, decimal_places=2), null=True, blank=True)
    ev = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    mean = models.DecimalField(db_index=True, max_digits=100, decimal_places=2, default=0.0)
    std = models.DecimalField(db_index=True, max_digits=100, decimal_places=2, default=0.0)
    actual = models.DecimalField(db_index=True, max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = 'Actuals Lineup'
        verbose_name_plural = 'Actuals Lineups'
        ordering = ['-actual', '-qb__projection']

    @property
    def players(self):
        return [
            self.qb, 
            self.rb1,
            self.rb2,
            self.wr1,
            self.wr2,
            self.wr3,
            self.te,
            self.flex,
            self.dst
        ]

    def contains_top_projected_pass_catcher(self, margin=2.0):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.team
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= margin]

            return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
        return False
    contains_top_projected_pass_catcher.short_description = '#1 PC?'
    contains_top_projected_pass_catcher.boolean = True

    def contains_opp_top_projected_pass_catcher(self):
        pass_catchers = BuildPlayerProjection.objects.filter(
            Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
            slate_player__slate=self.build.slate,
            slate_player__team=self.qb.slate_player.get_opponent()
        ).order_by('-projection')

        if pass_catchers.count() > 0:
            top_projection = pass_catchers[0].projection
            top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

            return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
        return False
    contains_opp_top_projected_pass_catcher.short_description = '#1 OPP PC?'
    contains_opp_top_projected_pass_catcher.boolean = True

    def get_num_rbs(self):
        if self.flex.slate_player.site_pos == 'RB':
            return 3
        return 2

    def get_num_wrs(self):
        if self.flex.slate_player.site_pos == 'WR':
            return 4
        return 3

    def get_num_tes(self):
        if self.flex.slate_player.site_pos == 'TE':
            return 2
        return 1

    def get_rbs_by_salary(self):
        rbs = [self.rb1, self.rb2]
        if self.get_num_rbs() > 2:
            rbs.append(self.flex)
        
        rbs.sort(key=lambda p: p.slate_player.salary, reverse=True)
        return rbs

    def get_wrs_by_salary(self):
        wrs = [self.wr1, self.wr2, self.wr3]
        if self.get_num_wrs() > 3:
            wrs.append(self.flex)
        
        wrs.sort(key=lambda p: p.slate_player.salary, reverse=True)
        return wrs

    def get_tes_by_salary(self):
        tes = [self.te]
        if self.get_num_tes() > 1:
            tes.append(self.flex)
        
        tes.sort(key=lambda  p: p.slate_player.salary, reverse=True)
        return tes

    @property
    def non_stack_sim_scores(self):
        matrix = [
            self.rb1.sim_scores,
            self.rb2.sim_scores,
        ]

        if not self.stack.contains_slate_player(self.wr1.slate_player):
            matrix.append(self.wr1.sim_scores)    
        if not self.stack.contains_slate_player(self.wr2.slate_player):
            matrix.append(self.wr2.sim_scores)    
        if not self.stack.contains_slate_player(self.wr3.slate_player):
            matrix.append(self.wr3.sim_scores)    
        if not self.stack.contains_slate_player(self.te.slate_player):
            matrix.append(self.te.sim_scores)    
        if not self.stack.contains_slate_player(self.flex.slate_player):
            matrix.append(self.flex.sim_scores) 
        
        matrix.append(self.dst.sim_scores)

        return matrix  

    def get_median_sim_score(self):
        matrix = [self.stack.sim_scores] + self.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.median(scores)

    def get_ceiling_sim_score(self):
        matrix = [self.stack.sim_scores] + self.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.amax(scores)

    def get_percentile_sim_score(self, percentile):
        matrix = [self.stack.sim_scores] + self.non_stack_sim_scores
        score_matrix = numpy.array(matrix)

        try:
            scores = score_matrix.sum(axis=0)
        except:
            traceback.print_exc()
            return None
        return numpy.percentile(scores, decimal.Decimal(percentile))

    def simulate(self):
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.save()


class SlatePlayerBuildExposure(SlatePlayer):
    '''
    Proxy model for viewing slate player exposures within a build
    '''
    class Meta:
        proxy = True
        ordering = ['projection__rb_group', '-salary']
        verbose_name = 'Exposure'
        verbose_name_plural = 'Exposures'


class SlateBuildGroup(models.Model):
    build = models.ForeignKey(SlateBuild, related_name='groups', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    max_from_group = models.PositiveIntegerField(default=1)
    min_from_group = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
    
    def __str__(self):
        return '{}'.format(self.name)

    @property
    def num_players(self):
        return self.players.all().count()


class SlateBuildGroupPlayer(models.Model):
    group = models.ForeignKey(SlateBuildGroup, related_name='players', on_delete=models.CASCADE)
    slate_player = models.ForeignKey(SlatePlayer, related_name='groups', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Player'
        verbose_name_plural = 'Players'
    
    def __str__(self):
        return '{}'.format(self.slate_player)


# Backtesting


class Backtest(models.Model):
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name='Backtest')
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    lineups_per_slate = models.PositiveSmallIntegerField(default=600)
    lineup_config = models.ForeignKey(SlateBuildConfig, on_delete=models.SET_NULL, related_name='backtests', verbose_name='CFG', null=True, blank=True)
    in_play_criteria = models.ForeignKey(PlayerSelectionCriteria, on_delete=models.SET_NULL, related_name='backtests', verbose_name='IPC', null=True, blank=True)
    lineup_construction = models.ForeignKey(LineupConstructionRule, on_delete=models.SET_NULL, related_name='backtests', verbose_name='LC', null=True, blank=True)
    stack_construction = models.ForeignKey(StackConstructionRule, on_delete=models.SET_NULL, related_name='backtests', verbose_name='SC', null=True, blank=True)
    stack_cutoff = models.SmallIntegerField(default=0, help_text='# of allowe stacks (ex. 80 for FD, and 90 for DK)')
    total_lineups = models.PositiveIntegerField('TL', default=0)
    total_optimals = models.PositiveIntegerField('TO', default=0)
    status = models.CharField(max_length=25, choices=BUILD_STATUS, default='not_started')
    completed_lineups = models.PositiveIntegerField(default=0)
    pct_complete = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    optimals_pct_complete = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    error_message = models.TextField(blank=True, null=True)
    elapsed_time = models.DurationField('Time', default=datetime.timedelta())
    median_cash_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    median_one_pct_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    median_half_pct_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    great_build_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    optimal_build_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.0)
    median_great_build_diff = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        ordering = ('-created',)
        verbose_name = 'Backtest'
        verbose_name_plural = 'Backtesting Center'

    @property
    def ready(self):
        return self.slates.filter(build__projections_ready=True, build__construction_ready=True).count() == self.slates.all().count()

    @property
    def projections_ready(self):
        return self.slates.filter(build__projections_ready=True).count() == self.slates.all().count()

    @property
    def construction_ready(self):
        return self.slates.filter(build__construction_ready=True).count() == self.slates.all().count()

    def reset(self):
        self.status = 'not_started'
        self.error_message = None
        self.completed_lineups = 0
        self.pct_complete = 0.0
        self.total_lineups = 0
        self.total_optimals = 0
        self.optimals_pct_complete = 0.0
        self.elapsed_time = datetime.timedelta()
        self.median_cash_rate = 0.0
        self.median_one_pct_rate = 0.0
        self.median_half_pct_rate = 0.0
        self.great_build_rate = 0.0
        self.optimal_build_rate = 0.0
        self.median_great_build_diff = 0.0
        self.save()

        # reset any existing slate builds
        for slate in self.slates.all():
            slate.reset()

    def prepare_projections(self):
        for slate in self.slates.all():
            slate.prepare_projections()

    def prepare_construction(self):
        for slate in self.slates.all():
            slate.prepare_construction()

    def execute(self, user):
        self.status = 'running'
        self.error_message = None
        self.completed_lineups = 0
        self.pct_complete = 0.0
        self.total_optimals = 0
        self.optimals_pct_complete = 0.0
        self.elapsed_time = datetime.timedelta()
        
        self.total_lineups = self.slates.all().aggregate(total=Sum('build__total_lineups')).get('total')
        self.save()

        SlateBuild.objects.filter(backtest__backtest=self).update(status='not_started')
        SlateBuildStack.objects.filter(build__backtest__backtest=self).update(lineups_created=False)

        task = BackgroundTask()
        task.name = 'Execute Backtest'
        task.user = user
        task.save()

        # if self.ready:
        # start monitoring
        tasks.monitor_backtest.delay(self.id, task.id)

        # execute the builds
        # self.execute_next_slate(user)

        return True
        # return False

    def execute_next_slate(self, user):
        incomplete_slates = self.slates.exclude(build__status='complete').order_by('slate__week')
        if incomplete_slates.count() > 0:
            slate = incomplete_slates[0]
            print('next slate = {}'.format(slate))
            slate.status = 'running'
            slate.save()
            tasks.run_slate_for_backtest.delay(slate.id, user.id)

    def analyze(self):
        avg_total_lineups = self.slates.filter(build__status='complete').aggregate(avg_total_lineups=Avg('build__total_lineups')).get('avg_total_lineups')
        median_cashed = self.slates.filter(build__status='complete').aggregate(median_cashed=Median('build__total_cashes')).get('median_cashed')
        median_one_pct = self.slates.filter(build__status='complete').aggregate(median_one_pct=Median('build__total_one_pct')).get('median_one_pct')
        median_half_pct = self.slates.filter(build__status='complete').aggregate(median_half_pct=Median('build__total_half_pct')).get('median_half_pct')

        great_builds = self.slates.filter(build__status='complete').aggregate(great_builds=Count(
            Case(When(build__great_build=True,
                        then=1))
        )).get('great_builds')

        optimal_builds = self.slates.filter(build__status='complete').aggregate(optimal_builds=Count(
            Case(When(build__total_optimals__gte=20,
                        then=1))
        )).get('optimal_builds')

        self.median_cash_rate = median_cashed / avg_total_lineups
        self.median_one_pct_rate = median_one_pct / avg_total_lineups
        self.median_half_pct_rate = median_half_pct / avg_total_lineups
        self.great_build_rate = great_builds / self.slates.filter(build__status='complete').count()
        self.optimal_build_rate = optimal_builds / self.slates.filter(build__status='complete').count()
        self.total_optimals = self.slates.all().aggregate(total_optimals=Sum('build__total_optimals')).get('total_optimals')
        
        self.save()

    def find_optimals(self):
        self.total_optimals = 0
        self.optimals_pct_complete = 0.0
        self.save()

        SlateBuildStack.objects.filter(
            build__backtest__backtest=self
        ).update(optimals_created=False)

        tasks.monitor_backtest_optimals.delay(self.id)

        for slate in self.slates.all():
            slate.build_optimals()

    # def update_optimal_pct_complete(self, build):
    #     complete_builds = SlateBuild.objects.filter(backtest__in=self.slates.all(), optimals_pct_complete=1.0)
    #     self.total_optimals = self.slates.filter(build__status='complete').aggregate(total_optimals=Sum('build__total_optimals'))
    #     self.optimals_pct_complete = complete_builds.count()/self.slates.all().count() + ((1/self.slates.all().count()) * build.optimals_pct_complete)
    #     self.save()

    def update_status(self, user):
        all_stacks = SlateBuildStack.objects.filter(build__backtest__in=self.slates.all(), count__gt=0)
        remaining_stacks = all_stacks.filter(lineups_created=False)
        completed_lineups = SlateBuild.objects.filter(backtest__in=self.slates.all()).aggregate(total_lineups=Count('lineups')).get('total_lineups')
        
        self.completed_lineups = completed_lineups
        self.pct_complete = (all_stacks.count() - remaining_stacks.count())/all_stacks.count()
        
        if SlateBuild.objects.filter(backtest__in=self.slates.all()).exclude(status='complete').count() == 0:
            self.pct_complete = 1.0
            self.total_lineups = completed_lineups
            self.status = 'complete'
        else:
            # only one build running at once
            running_builds = self.slates.filter(build__status='running')
            if running_builds.count() == 0:
                self.execute_next_slate(user)
            
        self.save()

    def handle_exception(self, slate, exc):
        self.status = 'error'
        if self.error_message is None or self.error_message == '':
            self.error_message = '{} Error: {}'.format(slate, str(exc))
        else:
             self.error_message = '\n{} Error: {}'.format(slate, str(exc))
        
        self.save()

    def duplicate(self):
        new_test = Backtest.objects.create(
            name='{} COPY'.format(self.name),
            site=self.site,
            lineups_per_slate=self.lineups_per_slate,
            lineup_config=self.lineup_config,
            in_play_criteria=self.in_play_criteria,
            lineup_construction=self.lineup_construction,
            stack_construction=self.stack_construction,
            stack_cutoff=self.stack_cutoff
        )

        for slate in self.slates.all():
            BacktestSlate.objects.create(
                backtest=new_test,
                slate=slate.slate
            )
    
    def initialize_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #a5408a; font-weight: bold; padding: 10px 15px;">Init</a>',
            reverse_lazy("admin:admin_backtest_init", args=[self.pk])
        )
    initialize_button.short_description = ''
    
    def prepare_projections_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #4fb2d3; font-weight: bold; padding: 10px 15px;">Proj</a>',
            reverse_lazy("admin:admin_backtest_prepare_projections", args=[self.pk])
        )
    prepare_projections_button.short_description = ''
    
    def prepare_construction_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #bf3030; font-weight: bold; padding: 10px 15px;">Const</a>',
            reverse_lazy("admin:admin_backtest_prepare_construction", args=[self.pk])
        )
    prepare_construction_button.short_description = ''
    
    def build_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Build</a>',
            reverse_lazy("admin:admin_backtest_build", args=[self.pk])
        )
    build_button.short_description = ''


class BacktestSlate(models.Model):
    '''
    Slates in a backtest
    '''
    backtest = models.ForeignKey(Backtest, related_name='slates', on_delete=models.CASCADE)
    slate = models.ForeignKey(Slate, related_name='backtests', on_delete=models.CASCADE)

    def __str__(self):
        return str(self.slate)
    
    class Meta:
        ordering = ('-slate__week__year', '-slate__week__num')
        verbose_name = 'Slate'
        verbose_name_plural = 'Slates'

    @property
    def top_score(self):
        try:
            return SlateBuild.objects.get(backtest=self).top_score
        except:
            return None

    @property
    def total_lineups(self):
        try:
            return SlateBuild.objects.get(backtest=self).num_lineups_created()
        except:
            return None

    @property
    def total_optimals(self):
        try:
            return SlateBuild.objects.get(backtest=self).total_optimals
        except:
            return None

    @property
    def total_cashes(self):
        try:
            return SlateBuild.objects.get(backtest=self).total_cashes
        except:
            return None

    @property
    def total_one_pct(self):
        try:
            return SlateBuild.objects.get(backtest=self).total_one_pct
        except:
            return None

    @property
    def total_half_pct(self):
        try:
            return SlateBuild.objects.get(backtest=self).total_half_pct
        except:
            return None

    @property
    def great_build(self):
        try:
            return SlateBuild.objects.get(backtest=self).great_build
        except:
            return None

    @property
    def binked(self):
        try:
            return SlateBuild.objects.get(backtest=self).binked
        except:
            return None

    @property
    def great_score(self):
        return self.slate.get_great_score()

    @property
    def bink_score(self):
        return self.slate.get_bink_score()

    @property
    def ready(self):
        return self.build.ready

    @property
    def projections_ready(self):
        return self.build.projections_ready

    @property
    def construction_ready(self):
        self.build.construction_ready

    def reset(self):
        # create a build
        (build, created) = SlateBuild.objects.get_or_create(
            slate=self.slate,
            backtest=self,
        )
        build.configuration = self.backtest.lineup_config
        build.in_play_criteria = self.backtest.in_play_criteria
        build.lineup_construction = self.backtest.lineup_construction
        build.stack_construction = self.backtest.stack_construction
        build.stack_cutoff = self.backtest.stack_cutoff
        build.total_lineups = self.backtest.lineups_per_slate
        build.save()

        if not created:
            build.reset()

    def prepare_projections(self):
        self.build.projections_ready = False
        self.save()

        tasks.prepare_projections.delay(self.build.id)

    def prepare_construction(self):
        self.build.construction_ready = False
        self.save()

        tasks.prepare_construction.delay(self.build.id)
    
    def execute(self, user):
        # make lineups
        self.build.execute_build(user)
    
    def build_optimals(self):
        # make lineups
        self.build.build_optimals()

    def handle_exception(self, exc):
        self.backtest.handle_exception(self, exc)


# Signals


# @receiver(post_save, sender=SlateProjectionSheet)
def process_projection_sheet(sender, instance, **kwargs):
    SlatePlayerProjection.objects.filter(slate_player__slate=instance.slate).update(projection=0.0, in_play=False, stack_only=False)

    if instance.slate.site == 'fanduel':
        process_fanduel_projection_sheet(instance)
        # for projection in SlatePlayerProjection.objects.filter(slate_player__site_pos='D'):
        #     projection.find_stack_only()
    elif instance.slate.site == 'draftkings':
        process_draftkings_projection_sheet(instance)
        # for projection in SlatePlayerProjection.objects.filter(slate_player__site_pos='DST'):
        #     projection.find_stack_only()
    else:
        raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))
    
    # instance.slate.group_rbs()
    # instance.slate.balance_rb_exposures()


def process_fanduel_projection_sheet(instance):
    with open(instance.projection_sheet.path, mode='r') as projection_file:
        csv_reader = csv.reader(projection_file, delimiter=',')
        row_count = 0
        missing_players = []

        for row in csv_reader:
            if row_count > 0:
                player_name= row[3].replace('Oakland', 'Las Vegas').replace('Washington Redskins', 'Washington Football Team')
                alias = None

                if player_name == '#N/A':
                    continue
                try:
                    alias = Alias.objects.get(four4four_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(fd_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(fc_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
             
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name__in=[alias.fc_name, alias.tda_name, alias.fd_name, alias.four4four_name, alias.awesemo_name],
                            team='JAC' if row[5] == 'JAX' else row[5]
                        )

                        print('Found {} on slate.'.format(slate_player), row[40])
                        if row[40] != '':
                            mu = float(row[40])
                            ceil = float(row[47])
                            flr = float(row[44])
                            stdev = numpy.std([mu, ceil, flr], dtype=numpy.float64)
                            try:
                                projection = SlatePlayerProjection.objects.get(
                                    slate_player=slate_player
                                )
                                projection.projection=mu
                                projection.floor=flr
                                projection.ceiling=ceil
                                projection.stdev=stdev
                                projection.balanced_projection=mu #if slate_player.site_pos != 'RB' else projection.balanced_projection
                                projection.adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0
                                projection.save()
                            except SlatePlayerProjection.DoesNotExist:
                                try:
                                    projection = SlatePlayerProjection.objects.create(
                                        slate_player=slate_player,
                                        projection=mu,
                                        floor=flr,
                                        ceiling=ceil,
                                        stdev=stdev,
                                        balanced_projection=mu,
                                        adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0,
                                        in_play=False,
                                        stack_only=False
                                    )
                                except:
                                    traceback.print_exc()
                            
                            # projection.find_in_play()
                    except SlatePlayer.DoesNotExist:
                        print('{} is not on slate.'.format(player_name))
            row_count += 1

        if len(missing_players) > 0:
            print()
            print('Missing players:')
            for p in missing_players:
                print(p)


def process_draftkings_projection_sheet(instance):
    with open(instance.projection_sheet.path, mode='r') as projection_file:
        csv_reader = csv.reader(projection_file, delimiter=',')
        row_count = 0
        missing_players = []

        for row in csv_reader:
            if row_count > 0:
                player_name= row[3].replace('Oakland', 'Las Vegas').replace('Washington Redskins', 'Washington Football Team')
                alias = None

                if player_name == '#N/A':
                    continue
                try:
                    alias = Alias.objects.get(four4four_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(dk_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(fc_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
             
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name__in=[alias.fc_name, alias.tda_name, alias.dk_name, alias.four4four_name, alias.awesemo_name],
                            team='JAC' if row[5] == 'JAX' else row[5]
                        )

                        in_play = True
                        stack_only = False

                        if row[28] != '':
                            try:
                                projection = SlatePlayerProjection.objects.get(
                                    slate_player=slate_player
                                )
                                projection.projection=float(row[28])
                                projection.balanced_projection=float(row[28]) #if slate_player.site_pos != 'RB' else projection.balanced_projection
                                projection.adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0
                                projection.game_total=float(row[63])
                                projection.team_total=float(row[65])
                                projection.spread=float(row[64])
                                projection.save()
                            except SlatePlayerProjection.DoesNotExist:
                                projection = SlatePlayerProjection.objects.create(
                                    slate_player=slate_player,
                                    projection=float(row[28]),
                                    balanced_projection=float(row[28]),
                                    adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0,
                                    game_total=float(row[63]),
                                    team_total=float(row[65]),
                                    spread=float(row[64]),
                                    in_play=False,
                                    stack_only=False
                                )
                            
                            # projection.find_in_play()
                            print(player_name, float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0)
                    except:
                        pass
            row_count += 1

        if len(missing_players) > 0:
            print()
            print('Missing players:')
            for p in missing_players:
                print(p)


def process_fantasycruncher_slate_player_sheet(instance):
    with open(instance.sheet.path, mode='r') as actuals_file:
        csv_reader = csv.reader(actuals_file, delimiter=',')
        row_count = 0
        missing_players = []

        for row in csv_reader:
            if row_count > 0:
                player_id = uuid.uuid4()
                site_pos = row[1]
                player_name = row[0].replace('Redskins', 'Washington Football Team')
                salary = row[6]
                game = '{}_{}'.format(row[2].replace('JAX', 'JAC'), row[3].replace('@ ', '').replace('JAX', 'JAC')) if '@' in row[3] else '{}_{}'.format(row[3].replace('vs ', '').replace('JAX', 'JAC'), row[2].replace('JAX', 'JAC'))
                team = row[2]

                alias = None

                try:
                    alias = Alias.objects.get(fc_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(tda_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(four4four_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            player_id=player_id,
                            slate=instance.slate,
                            name=alias.fd_name if instance.slate.site == 'fanduel' else alias.dk_name,
                            team=team
                        )
                    except SlatePlayer.DoesNotExist:
                        slate_player = SlatePlayer(
                            player_id=player_id,
                            slate=instance.slate,
                            team=team,
                            name=alias.fd_name if instance.slate.site == 'fanduel' else alias.dk_name
                        )

                    slate_player.salary = salary
                    slate_player.site_pos = site_pos
                    slate_player.game = game
                    slate_player.save()
                    
                    print(slate_player)
            row_count += 1

        if len(missing_players) > 0:
            print('Missing players:')
            for p in missing_players:
                print(p)


@receiver(post_save, sender=SlatePlayerActualsSheet)
def process_slate_player_actuals_sheet(sender, instance, **kwargs):
    if instance.slate.site == 'fanduel':
        process_fanduel_slate_player_actuals_sheet(instance)
    elif instance.slate.site == 'draftkings':
        process_draftkings_slate_player_actuals_sheet(instance)
    else:
        raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))


def process_fanduel_slate_player_actuals_sheet(instance):
    with open(instance.sheet.path, mode='r') as actuals_file:
        csv_reader = csv.reader(actuals_file, delimiter=',')
        row_count = 0

        failed_rows = []
        missing_players = []
        for row in csv_reader:
            if row_count > 0:
                player_name = row[0].replace('Redskins', 'Washington Football Team')
                print(player_name, row[22])

                try:
                    alias = Alias.objects.get(fc_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(fd_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(four4four_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name=alias.fd_name,
                            team=row[2]
                        )

                        if row[12] is not None and row[12] != '':
                            ownership = float(row[12].replace('%', ''))
                        else:
                            ownership = None

                        slate_player.fantasy_points = float(row[22]) if row[22] is not None and row[22] != '' else 0.0
                        slate_player.ownership = ownership
                        slate_player.save()
                    except SlatePlayer.DoesNotExist:
                        failed_rows.append(row)
                    
            row_count += 1

        print()
        if len(missing_players) > 0:
            print('Missing players:')
            for p in missing_players:
                print(p)
        if len(failed_rows) > 0:
            print('Failed rows:')
            for r in failed_rows:
                print(r)   


def process_draftkings_slate_player_actuals_sheet(instance):
    with open(instance.sheet.path, mode='r') as actuals_file:
        csv_reader = csv.reader(actuals_file, delimiter=',')
        row_count = 0

        failed_rows = []
        missing_players = []
        for row in csv_reader:
            if row_count > 0:
                player_name = row[0]
                print(player_name, row[22])

                try:
                    alias = Alias.objects.get(fc_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(dk_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(four4four_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name__in=[alias.dk_name, alias.tda_name, alias.fc_name, alias.four4four_name, alias.awesemo_name],
                            team=row[2]
                        )

                        if row[12] is not None and row[12] != '':
                            ownership = float(row[12].replace('%', ''))
                        else:
                            ownership = None

                        slate_player.fantasy_points = float(row[22]) if row[22] is not None and row[22] != '' else 0.0
                        slate_player.ownership = ownership
                        slate_player.save()
                    except SlatePlayer.DoesNotExist:
                        failed_rows.append(row)
                    
            row_count += 1

        print()
        if len(missing_players) > 0:
            print('Missing players:')
            for p in missing_players:
                print(p)
        if len(failed_rows) > 0:
            print('Failed rows:')
            for r in failed_rows:
                print(r)   


# @receiver(post_save, sender=SlatePlayerOwnershipProjectionSheet)
def process_slate_player_ownership_sheet(sender, instance, **kwargs):
    if instance.slate.site == 'fanduel':
        process_fanduel_slate_player_ownership_sheet(instance)
    elif instance.slate.site == 'draftkings':
        process_draftkings_slate_player_ownership_sheet(instance)
    else:
        raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))


def process_fanduel_slate_player_ownership_sheet(instance):
    with open(instance.sheet.path, mode='r') as actuals_file:
        csv_reader = csv.reader(actuals_file, delimiter=',')
        row_count = 0

        failed_rows = []
        missing_players = []
        for row in csv_reader:
            if row_count > 0:
                player_name = row[0].replace('Redskins', 'Washington Football Team')
                print(player_name, row[11])

                try:
                    alias = Alias.objects.get(fc_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(fd_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(four4four_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name=alias.fd_name,
                            team=row[4]
                        )

                        if row[11] is not None and row[11] != '':
                            ownership = float(row[11].replace('%', ''))/100.0
                        else:
                            ownership = None

                        try:
                            slate_player.projection.ownership_projection = ownership
                            slate_player.projection.save()
                        except SlatePlayer.projection.RelatedObjectDoesNotExist:
                            pass
                    except SlatePlayer.DoesNotExist:
                        failed_rows.append(row)
                    
            row_count += 1

        print()
        if len(missing_players) > 0:
            print('Missing players:')
            for p in missing_players:
                print(p)
        if len(failed_rows) > 0:
            print('Failed rows:')
            for r in failed_rows:
                print(r)   


def process_draftkings_slate_player_ownership_sheet(instance):
    with open(instance.sheet.path, mode='r') as actuals_file:
        csv_reader = csv.reader(actuals_file, delimiter=',')
        row_count = 0

        failed_rows = []
        missing_players = []
        for row in csv_reader:
            if row_count > 0:
                player_name = row[0]
                print(player_name, row[22])

                try:
                    alias = Alias.objects.get(fc_name=player_name)
                except Alias.DoesNotExist:
                    try:
                        alias = Alias.objects.get(dk_name=player_name)
                    except Alias.DoesNotExist:
                        try:
                            alias = Alias.objects.get(four4four_name=player_name)
                        except Alias.DoesNotExist:
                            missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate=instance.slate,
                            name__in=[alias.dk_name, alias.tda_name, alias.fc_name, alias.four4four_name, alias.awesemo_name],
                            team=row[2]
                        )

                        if row[12] is not None and row[12] != '':
                            ownership = float(row[12].replace('%', ''))
                        else:
                            ownership = None

                        slate_player.fantasy_points = float(row[22]) if row[22] is not None and row[22] != '' else 0.0
                        slate_player.ownership = ownership
                        slate_player.save()
                    except SlatePlayer.DoesNotExist:
                        failed_rows.append(row)
                    
            row_count += 1

        print()
        if len(missing_players) > 0:
            print('Missing players:')
            for p in missing_players:
                print(p)
        if len(failed_rows) > 0:
            print('Failed rows:')
            for r in failed_rows:
                print(r)   


@receiver(post_save, sender=ContestImportSheet)
def process_contest_sheet(sender, instance, **kwargs):
    with open(instance.sheet.path, mode='r') as f:
        csv_reader = csv.reader(f, delimiter=',')
        row_count = 0

        for row in csv_reader:
            if row_count > 0:
                try:
                    site = 'DK' if instance.site == 'draftkings' else 'FanDuel'
                    week = int(row[1].replace(',', ''))
                    slate_type = row[2]
                    dt = datetime.datetime.strptime('{} {}'.format(row[3], row[4]), '%m/%d/%Y %H:%M')
                    num_games = int(row[5].replace(',', ''))
                    name = row[6]
                    cost = float(row[7].replace('$', '').replace(',', ''))
                    prize_pool = float(row[8].replace('$', '').replace(',', ''))
                    max_entries = int(row[9].replace(',', ''))
                    max_entrants = int(row[10].replace(',', ''))
                    total_entrants = int(row[11].replace(',', ''))
                    winning_score = float(row[13].replace('$', '').replace(',', ''))
                    top_payout = float(row[14].replace('$', '').replace(',', ''))
                    min_cash_score = float(row[15].replace('$', '').replace(',', ''))
                    min_cash_payout = float(row[16].replace('$', '').replace(',', ''))
                    places_paid = int(row[17].replace(',', ''))
                    one_pct_rank = int(row[18].replace(',', ''))
                    one_pct_score = float(row[19].replace('$', '').replace(',', ''))
                    half_pct_rank = int(row[20].replace(',', ''))
                    half_pct_score = float(row[21].replace('$', '').replace(',', ''))

                    # get or create slate
                    try:
                        slate = Slate.objects.get(
                            datetime=dt,
                            week=week,
                            site=instance.site,
                            is_main_slate=slate_type.lower()=='main'
                        )
                    except Slate.DoesNotExist:
                        slate = Slate.objects.create(
                            datetime=dt,
                            name='{}-{}-{}-{}'.format(row[0][2:], site, str(week).zfill(2), slate_type),
                            week=week,
                            site=instance.site,
                            num_games=num_games,
                            is_main_slate=slate_type.lower()=='main'
                        )

                    print(slate)
                    try:
                        contest = Contest.objects.get(
                            slate=slate
                        )

                        contest.name = name
                        contest.num_games = num_games
                        contest.cost = cost
                        contest.max_entrants = max_entrants
                        contest.max_entries = max_entries
                        contest.mincash_payout = min_cash_payout
                        contest.mincash_score = min_cash_score
                        contest.places_paid = places_paid
                        contest.prize_pool = prize_pool
                        contest.start_date = 0
                        contest.total_entrants = total_entrants
                        contest.winning_payout = top_payout
                        contest.winning_score = winning_score
                        contest.url = None
                        contest.one_pct_score = one_pct_score
                        contest.one_pct_rank = one_pct_rank
                        contest.half_pct_score = half_pct_score
                        contest.half_pct_rank = half_pct_rank
                        contest.save()
                    except Contest.DoesNotExist:
                        contest = Contest.objects.create(
                            slate=slate,
                            name=name,
                            num_games=num_games,
                            cost=cost,
                            max_entrants=max_entrants,
                            max_entries=max_entries,
                            mincash_payout=min_cash_payout,
                            mincash_score=min_cash_score,
                            places_paid=places_paid,
                            prize_pool=prize_pool,
                            start_date=0,
                            total_entrants=total_entrants,
                            winning_payout=top_payout,
                            winning_score=winning_score,
                            url=None,
                            one_pct_score=one_pct_score,
                            one_pct_rank=one_pct_rank,
                            half_pct_score=half_pct_score,
                            half_pct_rank=half_pct_rank
                        )
                    
                    print(contest)
                except:
                    traceback.print_exc()
                    break
            row_count += 1
