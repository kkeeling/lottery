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

from celery import group, chord, chain
from collections import namedtuple
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
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
from fanduel import models as fanduel_models

from . import optimize
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
    ('fantasycruncher', 'FantasyCruncher Export'),
    ('sabersim', 'SaberSim Export')
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
    ('sabersim', 'Saber Sim'),
)

RANK_BY_CHOICES = (
    ('projection', 'Projection'),
    ('median', 'Median'),
    ('s90', 'Ceiling'),
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
    yahoo_name = models.CharField(max_length=255, null=True, blank=True)
    rg_name = models.CharField(max_length=255, null=True, blank=True)
    ss_name = models.CharField(max_length=255, null=True, blank=True)

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
            elif site == 'yahoo':
                alias = Alias.objects.get(yahoo_name=player_name)
            elif site == 'rotogrinders':
                alias = Alias.objects.get(rg_name=player_name)
            elif site == 'sabersim':
                alias = Alias.objects.get(ss_name=player_name)
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
            elif site == 'yahoo':
                alias = Alias.objects.filter(yahoo_name=player_name)[0]
            elif site == 'rotogrinders':
                alias = Alias.objects.filter(rg_name=player_name)[0]
            elif site == 'sabersim':
                alias = Alias.objects.filter(ss_name=player_name)[0]
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
                elif site == 'yahoo':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.yahoo_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'rotogrinders':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.rg_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'sabersim':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.ss_name.lower())
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
        elif for_site == 'yahoo':
            return self.yahoo_name
        elif for_site == 'rotogrinders':
            return self.rg_name
        elif for_site == 'sabersim':
            return self.ss_name


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

            try:
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
            except:
                traceback.print_exc()


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
    end_datetime = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=255, verbose_name='Slate', null=True, blank=True)
    week = models.ForeignKey(Week, related_name='slates', verbose_name='Week', on_delete=models.SET_NULL, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
    is_complete = models.BooleanField(default=False)

    salaries_sheet_type = models.CharField(max_length=255, choices=SHEET_TYPES, default='site')
    salaries = models.FileField(upload_to='uploads/salaries', blank=True, null=True)

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

    def num_in_play(self):
        return self.players.filter(projection__in_play=True).count()
    num_in_play.short_description = '# in play'

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

    def calc_player_zscores(self, position):
        projections = list(self.get_projections().filter(slate_player__site_pos=position, projection__gt=0.0).values_list('projection', flat=True))
        ceiling_projections = list(self.get_projections().filter(slate_player__site_pos=position, projection__gt=0.0).values_list('ceiling', flat=True))
        ao_projections = list(self.get_projections().filter(slate_player__site_pos=position, projection__gt=0.0).values_list('adjusted_opportunity', flat=True)) if position == 'RB' else None
        zscores = scipy.stats.zscore(projections)
        ao_zscores = scipy.stats.zscore(ao_projections) if ao_projections is not None and len(ao_projections) > 0 else None
        ceiling_zscores = scipy.stats.zscore(ceiling_projections) if ceiling_projections is not None and len(ceiling_projections) > 0 else None

        for (index, projection) in enumerate(self.get_projections().filter(slate_player__site_pos=position, projection__gt=0.0)):
            projection.zscore = zscores[index]
            projection.ao_zscore = ao_zscores[index] if ao_zscores is not None else 0.0
            projection.ceiling_zscore = ceiling_zscores[index] if ceiling_zscores is not None else 0.0
            projection.save()        

    def flatten_base_projections(self):
        for projection in SlatePlayerProjection.objects.filter(slate_player__slate=self, projection__gte=2).iterator():
            try:
                mapping = CeilingProjectionRangeMapping.objects.get(
                    min_projection__lte=projection.projection,
                    max_projection__gte=projection.projection
                )

                if self.site == 'yahoo':
                    projection.projection = projection.salary * float(mapping.yh_value_to_assign)
                    projection.value = mapping.yh_value_to_assign
                else:
                    projection.projection = projection.salary / 1000 * float(mapping.value_to_assign)
                    projection.value = mapping.value_to_assign
                projection.save()
            except:
                traceback.print_exc()

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Sim</a>',
            reverse_lazy("admin:admin_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''


class SlateGame(models.Model):
    slate = models.ForeignKey(Slate, related_name='games', on_delete=models.CASCADE)
    game = models.ForeignKey(Game, related_name='slates', on_delete=models.CASCADE)
    zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    game_sim = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Game'
        verbose_name_plural = 'Games'

    def __str__(self):
        return '{}: {}'.format(str(self.slate), str(self.game))

    def game_total(self):
        return self.game.game_total

    def home_spread(self):
        return self.game.home_spread

    def away_spread(self):
        return self.game.away_spread

    def home_team_total(self):
        return self.game.home_implied

    def away_team_total(self):
        return self.game.away_implied

    def get_home_players(self):
        return self.slate.players.filter(team=self.game.home_team)

    def get_away_players(self):
        return self.slate.players.filter(team=self.game.away_team)


class Contest(models.Model):
    slate = models.ForeignKey(Slate, related_name='contests', on_delete=models.CASCADE, null=True, blank=True)
    outcomes_sheet = models.FileField(upload_to='uploads/sims', blank=True, null=True)
    cost = models.DecimalField(decimal_places=2, max_digits=10)
    num_games = models.IntegerField(default=1)
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
    ownership = models.DecimalField(decimal_places=4, max_digits=6, null=True, blank=True)

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
        slate_game = self.get_slate_game()
        if slate_game is None:
            return None
        return slate_game.game.home_team if slate_game.game.away_team == self.team else slate_game.game.away_team

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
    ceiling_zscore = models.DecimalField('Ceiling Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    stdev = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Stdev')
    cpt_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    flex_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='AO')
    ao_zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)

    class Meta:
        verbose_name = 'Base Player Projection'
        verbose_name_plural = 'Base Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return f'${self.salary} {self.name}'

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

    def get_opponent(self):
        return self.slate_player.get_opponent()


class SlatePlayerRawProjection(models.Model):
    slate_player = models.ForeignKey(SlatePlayer, related_name='raw_projections', on_delete=models.CASCADE)
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='4for4')
    projection = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Proj')
    floor = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Flr')
    ceiling = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Ceil')
    stdev = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Stdev')
    cpt_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    flex_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='AO')
    ao_zscore = models.DecimalField('Z-Score', max_digits=6, decimal_places=4, default=0.0000)
    value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        verbose_name = 'Raw Player Projection'
        verbose_name_plural = 'Raw Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return f'{str(self.slate_player)} -- Proj: {self.projection}'

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
    randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.3)
    uniques = models.IntegerField(default=1)
    min_salary = models.IntegerField(default=59000)
    use_simulation = models.BooleanField(default=False)
    lineup_multiplier = models.SmallIntegerField(default=5)
    optimize_with_ceilings = models.BooleanField(default=False)
    lineup_removal_by = models.CharField(max_length=15, choices=RANK_BY_CHOICES, default='projection')

    class Meta:
        verbose_name = 'Build Config'
        verbose_name_plural = 'Build Configs'
        ordering = ['id']
    
    def __str__(self):
        return '{}'.format(self.name)


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
            'player': build_projection
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


class CeilingProjectionRangeMapping(models.Model):
    min_projection = models.DecimalField(max_digits=6, decimal_places=4)
    max_projection = models.DecimalField(max_digits=6, decimal_places=4)
    value_to_assign = models.DecimalField(max_digits=6, decimal_places=4)
    yh_value_to_assign = models.DecimalField(max_digits=6, decimal_places=4)

    class Model:
        verbose_name = 'Ceiling Projection Range Mapping'
        verbose_name_plural = 'Ceiling Projection Range Mappings'


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
    slate = models.ForeignKey(Slate, related_name='ownership_projections_sheets', on_delete=models.CASCADE)
    sheet = models.FileField(upload_to='uploads/ownership_projections')
    projection_site = models.CharField(max_length=255, choices=PROJECTION_SITES, default='awesemo')

    def __str__(self):
        return '{}'.format(str(self.slate))


class GroupImportSheet(models.Model):
    build = models.ForeignKey('SlateBuild', on_delete=models.CASCADE)
    sheet = models.FileField(upload_to='uploads/groups')

    def __str__(self):
        return '{}'.format(str(self.build))


# Builds


class SlateBuild(models.Model):
    # References
    slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)

    # Configuration & Rules
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    used_in_contests = models.BooleanField(default=False, verbose_name='Used')
    configuration = models.ForeignKey(SlateBuildConfig, related_name='builds', verbose_name='CFG', on_delete=models.SET_NULL, null=True)
    in_play_criteria = models.ForeignKey(PlayerSelectionCriteria, on_delete=models.SET_NULL, related_name='builds', verbose_name='IPC', null=True, blank=True)
    lineup_start_number = models.IntegerField(default=1)
    total_lineups = models.PositiveIntegerField(verbose_name='total', default=0)

    # Build analysis
    top_score = models.DecimalField(verbose_name='top', decimal_places=2, max_digits=5, blank=True, null=True)
    total_optimals = models.PositiveIntegerField('#opt', default=0, blank=True, null=True)
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

        stacks_ready = self.stacks.all().count() >= self.stack_cutoff * 0.90
        self.construction_ready = groups_ready and stacks_ready
        self.save()

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
                    projection.projection = player.projection.ceiling if self.configuration.optimize_with_ceilings else player.projection.projection
                    if self.slate.site == 'yahoo':
                        projection.value = round(float(projection.projection)/float(player.salary), 2)
                    else:
                        projection.value = round(float(projection.projection)/(player.salary/1000.0), 2)
                    projection.ownership_projection = player.projection.ownership_projection
                    projection.balanced_projection = projection.projection if self.configuration.optimize_with_ceilings else player.projection.balanced_projection
                    if self.slate.site == 'yahoo':
                        projection.balanced_value = round(float(projection.balanced_projection)/float(player.salary), 2)
                    else:
                        projection.balanced_value = round(float(projection.balanced_projection)/(player.salary/1000.0), 2)
                    projection.adjusted_opportunity = player.projection.adjusted_opportunity
                    projection.in_play = False

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

    def flatten_exposure(self):
        for projection in self.projections.filter(projection__gte=5):
            mapping = CeilingProjectionRangeMapping.objects.get(
                min_projection__lte=projection.projection,
                max_projection__gte=projection.projection
            )

            if self.slate.site == 'yahoo':
                projection.balanced_projection = projection.salary * float(mapping.yh_value_to_assign)
                projection.balanced_value = mapping.yh_value_to_assign
            else:
                projection.balanced_projection = projection.salary / 1000 * float(mapping.value_to_assign)
                projection.balanced_value = mapping.value_to_assign
            projection.save()

    def execute_build(self, user):
        self.status = 'running'
        self.error_message = None
        self.pct_complete = 0.0
        self.save()

        # task = BackgroundTask()
        # task.name = 'Build Lineups'
        # task.user = user
        # task.save()

        # chain(tasks.monitor_build.s(self.id), tasks.build_complete.si(self.id, task.id))()

        # last_qb = None
        # stacks = self.stacks.filter(count__gt=0).order_by('-qb__projection', 'qb__slate_player', 'build_order')
        # jobs = []
        # for stack in stacks:
        #     qb = stack.qb.id
        #     num_qb_stacks = self.stacks.filter(qb__id=qb).count()
        #     if last_qb is None or qb != last_qb:
        #         lineup_number = 1
        #     else:
        #         lineup_number += 1

        #     jobs.append(tasks.build_lineups_for_stack.s(stack.id, lineup_number, num_qb_stacks))

        #     last_qb = qb

        # group(jobs)()

    def analyze_lineups(self):
        group([
            tasks.analyze_lineup_outcomes.s(lineup_id) for lineup_id in list(self.lineups.all().values_list('id', flat=True))
        ])()

    def clean_lineups(self):
        if self.configuration.ev_cutoff > 0.0:
            self.lineups.filter(ev__lt=self.configuration.ev_cutoff).delete()

        if self.configuration.std_cutoff > 0.0:
            self.lineups.filter(std__gt=self.configuration.std_cutoff).delete()

        ordered_lineups = self.lineups.all().order_by(f'-{self.configuration.lineup_removal_by}')
        ordered_lineups.filter(id__in=ordered_lineups.values_list('pk', flat=True)[int(self.total_lineups*1.20):]).delete()

    def update_build_progress(self):
        all_stacks = self.stacks.filter(count__gt=0)
        remaining_stacks = all_stacks.filter(lineups_created=False)
        if remaining_stacks.count() == 0:
            self.pct_complete = 1.0
            self.save()
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
        num_qbs = self.lineups.all().aggregate(num_qbs=Count('qb', distinct=True)).get('num_qbs')
        all_lineups = self.lineups.all()
        current_qb = None
        qb_count = 0
        index = 0
        for lineup in all_lineups.order_by('-qb__projection', 'qb__slate_player_id', '-s90'):
            if current_qb is None or current_qb != lineup.qb:
                current_qb = lineup.qb
                qb_count += 1
                index = 0
            else:
                index += 1
            
            lineup.expected_lineup_order = ((num_qbs * index) + 1) + (qb_count - 1)
            lineup.save()
        
        for i, lineup in enumerate(all_lineups.order_by('expected_lineup_order')):
            lineup.order_number = i+1
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
        pass
        # if self.slate.contests.count() > 0:
        #     contest = self.slate.contests.get(outcomes_sheet__isnull=False)
        #     optimals = self.actuals.all().order_by('id')
        #     optimals.update(ev=0, mean=0, std=0)

        #     tasks.analyze_lineups_page(self.id, contest.id, list(optimals.values_list('id', flat=True)), True)

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

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Sim</a>',
            reverse_lazy("admin:admin_slatebuild_simulate", args=[self.pk])
        )
    sim_button.short_description = ''
    
    def prepare_projections_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #a41515; font-weight: bold; padding: 10px 15px;">Prep Proj</a>',
            reverse_lazy("admin:admin_slatebuild_prepare_projections", args=[self.pk])
        )
    prepare_projections_button.short_description = ''
    
    def flatten_exposure_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #a41515; font-weight: bold; padding: 10px 15px;">Flat</a>',
            reverse_lazy("admin:admin_slatebuild_flatten_exposure", args=[self.pk])
        )
    flatten_exposure_button.short_description = ''
    
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
    cpt_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    flex_ownership_projection = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, verbose_name='Own')
    adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='AO')
    value = models.DecimalField('V', max_digits=5, decimal_places=2, default=0.0, db_index=True)
    balanced_projection = models.DecimalField('BP', null=True, blank=True, max_digits=7, decimal_places=4, default=0.0)
    balanced_value = models.DecimalField('BV', max_digits=7, decimal_places=4, default=0.0, db_index=True)
    in_play = models.BooleanField(default=True, db_index=True)
    min_exposure = models.IntegerField('Min', default=0)
    max_exposure = models.IntegerField('Max', default=100)
    locked = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Player Projection'
        verbose_name_plural = 'Player Projections'
        ordering = ['-projection']

    def __str__(self):
        return f'${self.salary} {self.name}'

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

    def get_qb(self):
        qbs = BuildPlayerProjection.objects.filter(
            build=self.build,
            slate_player__site_pos='QB',
            slate_player__team=self.team
        ).order_by('-projection')

        print(qbs)
        if qbs.count() > 0:
            return qbs[0]
        return None 

    def get_opposing_qb(self):
        opp_qbs = BuildPlayerProjection.objects.filter(
            build=self.build,
            slate_player__site_pos='QB',
            slate_player__team=self.get_opponent()
        ).order_by('-projection')

        if opp_qbs.count() > 0:
            return opp_qbs[0]
        return None 

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


class SlateBuildLineup(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
    order_number = models.IntegerField(default=0, db_index=True)
    expected_lineup_order = models.PositiveIntegerField(default=0, db_index=True)
    cpt = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='cpt', on_delete=models.CASCADE)
    flex1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex1', on_delete=models.CASCADE)
    flex2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex2', on_delete=models.CASCADE)
    flex3 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex3', on_delete=models.CASCADE)
    flex4 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex4', on_delete=models.CASCADE)
    flex5 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='flex5', on_delete=models.CASCADE, null=True, blank=True)
    salary = models.PositiveIntegerField(db_index=True)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, db_index=True)
    mean = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    median = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    std = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s75 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s90 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)

    class Meta:
        verbose_name = 'Lineup'
        verbose_name_plural = 'Lineups'
        ordering = ['-actual', 'order_number']

    @property
    def players(self):
        return [
            self.cpt, 
            self.flex1,
            self.flex2,
            self.flex3,
            self.flex4,
            self.flex5,
        ]
        
    def calc_actual_score(self):
        slate_player_ids = [p.slate_player.id for p in self.players]
        score = sum(p.fantasy_points for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
        self.actual = score
        self.save()

        return score        

    def simulate(self):
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.median = numpy.median(self.sim_scores)
        self.s75 = self.get_percentile_sim_score(75)
        self.s90 = self.get_percentile_sim_score(98)
        self.save()


class SlateFieldLineup(models.Model):
    slate = models.ForeignKey(Slate, db_index=True, verbose_name='Slate', related_name='field_lineups', on_delete=models.CASCADE)
    username = models.CharField(max_length=50, db_index=True)
    cpt = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='cpt', on_delete=models.CASCADE)
    flex1 = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='flex1', on_delete=models.CASCADE)
    flex2 = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='flex2', on_delete=models.CASCADE)
    flex3 = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='flex3', on_delete=models.CASCADE)
    flex4 = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='flex4', on_delete=models.CASCADE)
    flex5 = models.ForeignKey(SlatePlayerProjection, db_index=True, related_name='flex5', on_delete=models.CASCADE)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)

    @property
    def players(self):
        return [
            self.cpt, 
            self.flex1,
            self.flex2,
            self.flex3,
            self.flex4,
            self.flex5,
        ]

    def simulate(self):
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.save()


class SlateBuildOptimalLineup(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='actuals', on_delete=models.CASCADE)
    cpt = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_cpt', on_delete=models.CASCADE)
    flex1 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_flex1', on_delete=models.CASCADE)
    flex2 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_flex2', on_delete=models.CASCADE)
    flex3 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_flex3', on_delete=models.CASCADE)
    flex4 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_flex4', on_delete=models.CASCADE)
    flex5 = models.ForeignKey(BuildPlayerProjection, db_index=True, related_name='optimals_flex5', on_delete=models.CASCADE)
    salary = models.PositiveIntegerField(db_index=True)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True)
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, db_index=True)
    mean = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    median = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    std = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s75 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s90 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)

    class Meta:
        verbose_name = 'Optimals Lineup'
        verbose_name_plural = 'Optimals Lineups'
        ordering = ['-actual']

    @property
    def players(self):
        return [
            self.cpt, 
            self.flex1,
            self.flex2,
            self.flex3,
            self.flex4,
            self.flex5,
        ]

    def simulate(self):
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.save()


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
