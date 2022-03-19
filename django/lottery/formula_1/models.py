import csv
import datetime
import difflib
from email.policy import default
import math
from pyexpat import model
from django.db.models.fields import related
import numpy
import random
import re
import requests

from statistics import mean

from celery import chain
from django.contrib.postgres.fields import ArrayField
from django.db import models, signals
from django.db.models import Q, Sum
from django.db.models.signals import post_save
from django.utils.html import format_html
from django.urls import reverse_lazy
from django.dispatch import receiver

from configuration.models import BackgroundTask
from . import optimize, tasks


SITE_OPTIONS = (
    ('draftkings', 'DraftKings'),
    ('fanduel', 'Fanduel'),
)

SITE_SCORING = {
    'draftkings': {
        'place_differential': {
            '-19': -5,
            '-18': -5,
            '-17': -5,
            '-16': -5,
            '-15': -5,
            '-14': -5,
            '-13': -5,
            '-12': -5,
            '-11': -5,
            '-10': -5,
            '-9': -3,
            '-8': -3,
            '-7': -3,
            '-6': -3,
            '-5': -3,
            '-4': -2,
            '-3': -2,
            '-2': 0,
            '-1': 0,
            '0': 0,
            '1': 0,
            '2': 0,
            '3': 2,
            '4': 2,
            '5': 3,
            '6': 3,
            '7': 3,
            '8': 3,
            '9': 3,
            '10': 5,
            '11': 5,
            '12': 5,
            '13': 5,
            '14': 5,
            '15': 5,
            '16': 5,
            '17': 5,
            '18': 5,
            '19': 5
        },
        'fastest_lap': 3,
        'laps_led': .1,
        'classified': 1,
        'defeated_teammate': 5,
        'finishing_position': {
            '1': 25,
            '2': 18,
            '3': 15,
            '4': 12,
            '5': 10,
            '6': 8,
            '7': 6,
            '8': 4,
            '9': 2,
            '10': 1,
            '11': 0,
            '12': 0,
            '13': 0,
            '14': 0,
            '15': 0,
            '16': 0,
            '17': 0,
            '18': 0,
            '19': 0,
            '20': 0,
            '21': 0,
            '22': 0
        },
        'constructor_bonuses': {
            'both_classified': 2,
            'both_in_points': 5,
            'both_on_podium': 3
        },
        'max_salary': 50000
    }
}

DK_ROSTER_POSITION_CHOICES = (
    ('D', 'D'),
    ('CPT', 'CPT'),
    ('CNSTR', 'CNSTR'),
)


# Aliases

class Alias(models.Model):
    dk_name = models.CharField(max_length=255, null=True, blank=True)
    fd_name = models.CharField(max_length=255, null=True, blank=True)
    f1_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Alias'
        verbose_name_plural = 'Aliases'

    def __str__(self):
        return f'{self.f1_name}'
    
    @classmethod
    def find_alias(clz, player_name, site):
        try:
            if site == 'draftkings':
                alias = Alias.objects.get(dk_name=player_name)
            elif site == 'fanduel':
                alias = Alias.objects.get(fd_name=player_name)
            elif site == 'f1':
                alias = Alias.objects.get(f1_name=player_name)
            else:
                raise Exception('{} is not a supported site yet.'.format(site))
        except Alias.MultipleObjectsReturned:
            if site == 'draftkings':
                alias = Alias.objects.filter(dk_name=player_name)[0]
            elif site == 'fanduel':
                alias = Alias.objects.filter(fd_name=player_name)[0]
            elif site == 'f1':
                alias = Alias.objects.filter(f1_name=player_name)[0]
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
                elif site == 'f1':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.f1_name.lower())
                    score = seqmatch.quick_ratio()
                else:
                    raise Exception('{} is not a supported site yet.'.format(site))

                scores.append({'alias': possible_match, 'score': score})
            
            scores = sorted(scores, key=lambda x: x.get('score'), reverse=True)

            # add top 3 scoring aliases to MissingAlias table
            a = MissingAlias.objects.create(
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
        elif for_site == 'f1':
            return self.f1_name


class MissingAlias(models.Model):
    player_name = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    alias_1 = models.ForeignKey(Alias, related_name='hint_1', on_delete=models.CASCADE)
    alias_2 = models.ForeignKey(Alias, related_name='hint_2', on_delete=models.CASCADE)
    alias_3 = models.ForeignKey(Alias, related_name='hint_3', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Missing Alias'
        verbose_name_plural = 'Missing Aliases'
    
    def choose_alias_1_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_f1_choose_alias", args=[self.pk, self.alias_1.pk]), str(self.alias_1)
        )
    choose_alias_1_button.short_description = ''
    
    def choose_alias_2_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_f1_choose_alias", args=[self.pk, self.alias_2.pk]), str(self.alias_2)
        )
    choose_alias_2_button.short_description = ''
    
    def choose_alias_3_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_f1_choose_alias", args=[self.pk, self.alias_3.pk]), str(self.alias_3)
        )
    choose_alias_3_button.short_description = ''
    
    def create_new_alias_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #4fb2d3; font-weight: bold; padding: 10px 15px; width:100px">Add New</a>',
            reverse_lazy("admin:admin_f1_choose_alias", args=[self.pk, 0])
        )
    create_new_alias_button.short_description = ''


# F1 Data

class Constructor(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return f'{self.name}'


class Driver(models.Model):
    driver_id = models.BigIntegerField(primary_key=True, auto_created=True, blank=True)
    full_name = models.CharField(max_length=50, null=True)
    badge = models.CharField(max_length=5, null=True)
    team = models.ForeignKey(Constructor, related_name='drivers', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f'{self.full_name} ({self.team})'
    

class Race(models.Model):
    race_id = models.AutoField(primary_key=True)
    race_season = models.IntegerField(default=2022)
    race_name = models.CharField(max_length=255, null=True)
    race_date = models.DateTimeField(null=True)
    qualifying_date = models.DateTimeField(null=True, blank=True)
    scheduled_distance = models.IntegerField(default=0)
    scheduled_laps = models.IntegerField(default=0)
    num_cars = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.race_name}'


class RaceResult(models.Model):
    race = models.ForeignKey(Race, related_name='results', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='results', on_delete=models.CASCADE)
    finishing_position = models.IntegerField(default=0)
    starting_position = models.IntegerField(default=0)
    laps_led = models.IntegerField(default=0)
    laps_completed = models.IntegerField(default=0)
    finishing_status = models.CharField(max_length=50, default='Running')

    def __str__(self):
        return f'{self.race} - {self.driver}'


class RaceDriverLap(models.Model):
    race = models.ForeignKey(Race, related_name='driver_laps', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='race_laps', on_delete=models.CASCADE)
    lap = models.IntegerField(default=0)
    lap_time = models.FloatField(null=True, blank=True)
    lap_speed = models.FloatField(null=True, blank=True)
    running_pos = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f'{self.driver} Lap {self.lap}'


# Simulations

class RaceSim(models.Model):
    race = models.ForeignKey(Race, related_name='sims', on_delete=models.CASCADE)
    iterations = models.IntegerField(default=10000)
    input_file = models.FileField(upload_to='uploads/sim_input_files', blank=True, null=True)
    dk_salaries = models.FileField(upload_to='uploads/dk_salaries', blank=True, null=True)

    # variance data
    ll_mean = models.IntegerField(default=1)

    def __str__(self):
        return f'{self.race} Sim {self.id}'

    def get_drivers(self):
        return self.race.results.all()

    def export_template_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #f5dd5d; font-weight: bold; padding: 10px 15px;">Template</a>',
            reverse_lazy("admin:admin_f1_slate_template", args=[self.pk])
        )
    export_template_button.short_description = ''

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Run</a>',
            reverse_lazy("admin:admin_f1_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''


class RaceSimFastestLapsProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='fl_profiles', on_delete=models.CASCADE)
    fp_rank = models.IntegerField(default=1)
    probability = models.FloatField(default=0.0)

    def __str__(self):
        return f'Fastest Laps Profile: FP {self.fp_rank} - {self.probability * 100}%'


class RaceSimLapsLedProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='ll_profiles', on_delete=models.CASCADE)
    fp_rank = models.IntegerField(default=1)
    pct_laps_led_min = models.FloatField(default=0.0)
    pct_laps_led_max = models.FloatField(default=0.0)

    def __str__(self):
        return f'Laps Led Profile: {self.pct_laps_led_min * 100}% - {self.pct_laps_led_max * 100}%'


class RaceSimDriver(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='outcomes', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='outcomes', on_delete=models.CASCADE, null=True, blank=True)
    constructor = models.ForeignKey(Constructor, related_name='outcomes', on_delete=models.CASCADE, null=True, blank=True)
    dk_salary = models.IntegerField(default=0)
    dk_position = models.CharField(default='D', choices=DK_ROSTER_POSITION_CHOICES, max_length=10)
    starting_position = models.IntegerField(default=0)
    speed_min = models.IntegerField(default=1)
    speed_max = models.IntegerField(default=5)
    incident_rate = models.FloatField(default=0.0)
    pct_laps_led_min = models.FloatField(default=0.0)
    pct_laps_led_max = models.FloatField(default=0.0)

    fp_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    ll_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    fl_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    incident_outcomes = ArrayField(models.CharField(max_length=5, null=True), null=True, blank=True)

    dk_scores = ArrayField(models.FloatField(), null=True, blank=True)

    avg_fp = models.FloatField(default=0.0)
    avg_ll = models.FloatField(default=0.0)
    avg_dk_score = models.FloatField(default=0.0)

    gto = models.FloatField(default=0.0)

    def __str__(self):
        if self.driver is None:
            return f'{self.constructor}'
        return f'{self.dk_position} {self.driver}'

    def get_teammate(self):
        return RaceSimDriver.objects.filter(
            sim=self.sim,
            driver__team=self.driver.team
        ).exclude(id=self.id)[0]

    def get_scores(self, site):
        sp = self.starting_position

        # only calc score if starting position is set
        if sp == 0:
            return 0

        count = min(min(len(self.fp_outcomes), len(self.ll_outcomes)), len(self.fl_outcomes))

        return [
            (SITE_SCORING.get(site).get('place_differential').get(str(sp - self.fp_outcomes[index])) + 
            SITE_SCORING.get(site).get('fastest_lap') * self.fl_outcomes[index] + 
            SITE_SCORING.get(site).get('finishing_position').get(str(self.fp_outcomes[index])) + 
            SITE_SCORING.get(site).get('laps_led') * self.ll_outcomes[index] + 
            (SITE_SCORING.get(site).get('classified') if self.incident_outcomes[index] == 0 else 0) +
            (SITE_SCORING.get(site).get('defeated_teammate') if self.get_teammate().fp_outcomes[index] > self.fp_outcomes[index] else 0)) for index in range(0, count)
        ]


# DFS Slates

# class SlateBuildConfig(models.Model):
#     name = models.CharField(max_length=255)
#     site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
#     randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.75)
#     uniques = models.IntegerField(default=1)
#     min_salary = models.IntegerField(default=0)
#     optimize_by_percentile = models.IntegerField(default=50)
#     lineup_multiplier = models.IntegerField(default=1)
#     clean_by_percentile = models.IntegerField(default=50)
#     duplicate_threshold = models.FloatField(default=5)

#     class Meta:
#         verbose_name = 'Build Config'
#         verbose_name_plural = 'Build Configs'
#         ordering = ['id']
    
#     def __str__(self):
#         return '{}'.format(self.name)


# class Slate(models.Model):
#     datetime = models.DateTimeField()
#     name = models.CharField(max_length=255, verbose_name='Slate')
#     race = models.ForeignKey(Race, related_name='slates', on_delete=models.SET_NULL, null=True)
#     site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
#     salaries = models.FileField(upload_to='uploads/salaries', blank=True, null=True)

#     class Meta:
#         ordering = ['-name']

#     def __str__(self):
#         return '{}'.format(self.name) if self.name is not None else '{}'.format(self.datetime)


# class SlatePlayer(models.Model):
#     slate_player_id = models.CharField(max_length=255)
#     slate = models.ForeignKey(Slate, related_name='players', on_delete=models.CASCADE)
#     name = models.CharField(max_length=255)
#     salary = models.IntegerField()
#     fantasy_points = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     ownership = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     driver = models.ForeignKey(Driver, related_name='slates', null=True, blank=True, on_delete=models.SET_NULL)

#     def __str__(self):
#         return '{} ${}'.format(self.name, self.salary)

#     class Meta:
#         ordering = ['-salary', 'name']


# class SlateBuild(models.Model):
#     slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)
#     sim = models.ForeignKey(RaceSim, related_name='builds', on_delete=models.SET_NULL, null=True)
#     created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     used_in_contests = models.BooleanField(default=False, verbose_name='Used')
#     configuration = models.ForeignKey(SlateBuildConfig, related_name='builds', verbose_name='Config', on_delete=models.SET_NULL, null=True)
#     total_lineups = models.PositiveIntegerField(verbose_name='total', default=0)
#     max_entrants = models.PositiveIntegerField(verbose_name='max_entrants', default=50000)

#     class Meta:
#         verbose_name = 'Slate Build'
#         verbose_name_plural = 'Slate Builds'

#     def __str__(self):
#         return '{} ({})'.format(self.slate.name, self.configuration)

#     def execute_build(self, user):
#         self.lineups.all().delete()
        
#         chain(
#             tasks.build_lineups.si(
#                 self.id,
#                 BackgroundTask.objects.create(
#                     name='Build Lineups',
#                     user=user
#                 ).id
#             ),
#             tasks.clean_lineups.si(
#                 self.id,
#                 BackgroundTask.objects.create(
#                     name='Clean Lineups',
#                     user=user
#                 ).id
#             ),
#             # tasks.calculate_exposures.si(
#             #     self.id,
#             #     BackgroundTask.objects.create(
#             #         name='Calculate Exposures',
#             #         user=user
#             #     ).id
#             # )
#         )()

#     def num_lineups_created(self):
#         return self.lineups.all().count()
#     num_lineups_created.short_description = 'created'

#     def get_exposure(self, slate_player):
#         return self.lineups.filter(
#             Q(
#                 Q(player_1__slate_player_id=slate_player.slate_player_id) | 
#                 Q(player_2__slate_player_id=slate_player.slate_player_id) | 
#                 Q(player_3__slate_player_id=slate_player.slate_player_id) | 
#                 Q(player_4__slate_player_id=slate_player.slate_player_id) | 
#                 Q(player_5__slate_player_id=slate_player.slate_player_id) | 
#                 Q(player_6__slate_player_id=slate_player.slate_player_id)
#             )
#         ).count()

#     def build_button(self):
#         return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Build</a>',
#             reverse_lazy("admin:admin_nascar_slatebuild_build", args=[self.pk])
#         )
#     build_button.short_description = ''
    
#     def export_button(self):
#         return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #5b80b2; font-weight: bold; padding: 10px 15px;">Export</a>',
#             reverse_lazy("admin:admin_nascar_slatebuild_export", args=[self.pk])
#         )
#     export_button.short_description = ''


# class BuildPlayerProjection(models.Model):
#     build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='projections', on_delete=models.CASCADE)
#     slate_player = models.ForeignKey(SlatePlayer, db_index=True, related_name='builds', on_delete=models.CASCADE)
#     starting_position = models.IntegerField(default=0)
#     sim_scores = ArrayField(models.FloatField(), null=True, blank=True)
#     projection = models.FloatField(db_index=True, default=0.0, verbose_name='Proj')
#     ceiling = models.FloatField(db_index=True, default=0.0, verbose_name='Ceil')
#     s75 = models.FloatField(db_index=True, default=0.0, verbose_name='s75')
#     in_play = models.BooleanField(default=True)
#     op = models.FloatField(default=0.0)
#     gto = models.FloatField(default=0.0)
#     min_exposure = models.FloatField(default=0.0, verbose_name='min')
#     max_exposure = models.FloatField(default=1.0, verbose_name='max')

#     class Meta:
#         verbose_name = 'Player Projection'
#         verbose_name_plural = 'Player Projections'
#         ordering = ['-slate_player__salary']

#     def __str__(self):
#         return '{}'.format(str(self.slate_player))

#     @property
#     def name(self):
#         return self.slate_player.name

#     @property
#     def salary(self):
#         return self.slate_player.salary

#     @property
#     def exposure(self):
#         if self.build.lineups.all().count() > 0:
#             return self.build.lineups.filter(
#                 Q(
#                     Q(player_1=self) | 
#                     Q(player_2=self) | 
#                     Q(player_3=self) | 
#                     Q(player_4=self) | 
#                     Q(player_5=self) | 
#                     Q(player_6=self)
#                 )
#             ).count() / self.build.lineups.all().count()
#         return 0

#     def get_percentile_projection(self, percentile):
#         return numpy.percentile(self.sim_scores, float(percentile))


# class SlateBuildGroup(models.Model):
#     build = models.ForeignKey(SlateBuild, related_name='groups', on_delete=models.CASCADE)
#     name = models.CharField(max_length=255)
#     max_from_group = models.PositiveIntegerField(default=1)
#     min_from_group = models.PositiveIntegerField(default=0)
#     active = models.BooleanField(default=True)

#     class Meta:
#         verbose_name = 'Group'
#         verbose_name_plural = 'Groups'
    
#     def __str__(self):
#         return '{}'.format(self.name)

#     @property
#     def num_players(self):
#         return self.players.all().count()


# class SlateBuildGroupPlayer(models.Model):
#     group = models.ForeignKey(SlateBuildGroup, related_name='players', on_delete=models.CASCADE)
#     player = models.ForeignKey(BuildPlayerProjection, related_name='groups', on_delete=models.CASCADE)

#     class Meta:
#         verbose_name = 'Player'
#         verbose_name_plural = 'Players'
    
#     def __str__(self):
#         return '{}'.format(self.player)
 
        
# class SlateBuildLineup(models.Model):
#     build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
#     player_1 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_1', on_delete=models.CASCADE)
#     player_2 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_2', on_delete=models.CASCADE)
#     player_3 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_3', on_delete=models.CASCADE)
#     player_4 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_4', on_delete=models.CASCADE)
#     player_5 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_5', on_delete=models.CASCADE)
#     player_6 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_6', on_delete=models.CASCADE, null=True, blank=True)
#     total_salary = models.IntegerField(default=0)
#     sim_scores = ArrayField(models.FloatField(), null=True, blank=True)
#     ownership_projection = models.DecimalField(max_digits=10, decimal_places=9, default=0.0)
#     duplicated = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     roi = models.FloatField(default=0.0, db_index=True)
#     median = models.FloatField(db_index=True, default=0.0)
#     s75 = models.FloatField(db_index=True, default=0.0)
#     s90 = models.FloatField(db_index=True, default=0.0)
#     sort_proj = models.FloatField(db_index=True, default=0.0)

#     class Meta:
#         verbose_name = 'Lineup'
#         verbose_name_plural = 'Lineups'
#         ordering = ['-sort_proj']

#     @property
#     def players(self):
#         return [
#             self.player_1, 
#             self.player_2, 
#             self.player_3, 
#             self.player_4, 
#             self.player_5, 
#             self.player_6
#         ]

#     def get_percentile_sim_score(self, percentile):
#         return numpy.percentile(self.sim_scores, float(percentile))

#     def simulate(self):
#         self.ownership_projection = numpy.prod([x.op for x in self.players])
#         self.duplicated = numpy.prod([x.op for x in self.players]) * self.build.max_entrants
#         self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, self.build.sim.iterations)]
#         self.median = numpy.median(self.sim_scores)
#         self.s75 = self.get_percentile_sim_score(75)
#         self.s90 = self.get_percentile_sim_score(90)
#         self.sort_proj = self.get_percentile_sim_score(self.build.configuration.clean_by_percentile)
#         self.save()

