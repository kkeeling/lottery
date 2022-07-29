import csv
import datetime
import difflib
from email.policy import default
import math
from pyexpat import model
from urllib import request
from django.db.models.fields import related
import numpy
import random
import re
import requests

from statistics import mean

from celery import chain, group
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models, signals
from django.db.models import Q, Sum, Avg
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
        'place_differential': 1,
        'fastest_laps': .45,
        'laps_led': .25,
        'finishing_position': {
            '1': 45,
            '2': 42,
            '3': 41,
            '4': 40,
            '5': 39,
            '6': 38,
            '7': 37,
            '8': 36,
            '9': 35,
            '10': 34,
            '11': 32,
            '12': 31,
            '13': 30,
            '14': 29,
            '15': 28,
            '16': 27,
            '17': 26,
            '18': 25,
            '19': 24,
            '20': 23,
            '21': 21,
            '22': 20,
            '23': 19,
            '24': 18,
            '25': 17,
            '26': 16,
            '27': 15,
            '28': 14,
            '29': 13,
            '30': 13,
            '31': 10,
            '32': 9,
            '33': 8,
            '34': 7,
            '35': 6,
            '36': 5,
            '37': 4,
            '38': 3,
            '39': 2,
            '40': 1,
            '41': 0,
            '42': 0
        },
        'max_salary': 50000
    }
}

DATA_SITE_OPTIONS = (
    ('ma', 'Motorsports Analytics'),
    ('nascar', 'Nascar.com'),
)

RACE_SERIES = (
    (1, 'Nascar'),
    (2, 'Xfinity'),
    (3, 'Trucks'),
)

RACE_TYPES = (
    (1, 'Points Race'),
    (2, 'Exhibition Race'),
)

TRACK_TYPES = (
    (1, '550 HP'),
    (2, '750 HP'),
    (3, 'Super Speedway'),
    (4, 'Road Course'),
)

BUILD_TYPES = (
    ('h2h', 'Head-to-Head'),
    ('cash', '50/50s'),
    ('se', 'Hi-Stakes SE'),
    ('mme', 'MME'),
)

BUILD_TYPE_FILTERS = {
    'cash': {
        'total_salary__gte': 48500
    },
    'h2h': {
        'total_salary__gte': 48500
    },
    'se': {
        'total_salary__gte': 48500
    },
    'mme': {
        'total_salary__gte': 48000
    }
}

# RUNNING_STATUSES = (
#     ('Running', 'Running'),
#     ('Accident', 'Accident'),
#     ('Engine', 'Engine'),
#     ('Suspension', 'Suspension'),
#     ('Running', 'Running'),
#     ('Running', 'Running'),
# )


# Aliases

class Alias(models.Model):
    dk_name = models.CharField(max_length=255, null=True, blank=True)
    fd_name = models.CharField(max_length=255, null=True, blank=True)
    ma_name = models.CharField(max_length=255, null=True, blank=True)
    nascar_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = 'Alias'
        verbose_name_plural = 'Aliases'

    def __str__(self):
        return f'{self.nascar_name}'
    
    @classmethod
    def find_alias(clz, player_name, site):
        try:
            if site == 'draftkings':
                alias = Alias.objects.get(dk_name=player_name)
            elif site == 'fanduel':
                alias = Alias.objects.get(fd_name=player_name)
            elif site == 'motorsports':
                alias = Alias.objects.get(ma_name=player_name)
            elif site == 'nascar':
                alias = Alias.objects.get(nascar_name=player_name)
            else:
                raise Exception('{} is not a supported site yet.'.format(site))
        except Alias.MultipleObjectsReturned:
            if site == 'draftkings':
                alias = Alias.objects.filter(dk_name=player_name)[0]
            elif site == 'fanduel':
                alias = Alias.objects.filter(fd_name=player_name)[0]
            elif site == 'motorsports':
                alias = Alias.objects.filter(ma_name=player_name)[0]
            elif site == 'nascar':
                alias = Alias.objects.filter(nascar_name=player_name)[0]
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
                elif site == 'motorsports':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.ma_name.lower())
                    score = seqmatch.quick_ratio()
                elif site == 'nascar':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.nascar_name.lower())
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
        elif for_site == 'motorsports':
            return self.ma_name
        elif for_site == 'nascar':
            return self.nascar_name


class MissingAlias(models.Model):
    player_name = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS+DATA_SITE_OPTIONS, default='draftkings')
    alias_1 = models.ForeignKey(Alias, related_name='hint_1', on_delete=models.CASCADE)
    alias_2 = models.ForeignKey(Alias, related_name='hint_2', on_delete=models.CASCADE)
    alias_3 = models.ForeignKey(Alias, related_name='hint_3', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Missing Alias'
        verbose_name_plural = 'Missing Aliases'
    
    def choose_alias_1_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_nascar_choose_alias", args=[self.pk, self.alias_1.pk]), str(self.alias_1)
        )
    choose_alias_1_button.short_description = ''
    
    def choose_alias_2_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_nascar_choose_alias", args=[self.pk, self.alias_2.pk]), str(self.alias_2)
        )
    choose_alias_2_button.short_description = ''
    
    def choose_alias_3_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px; width:100px">{}</a>',
            reverse_lazy("admin:admin_nascar_choose_alias", args=[self.pk, self.alias_3.pk]), str(self.alias_3)
        )
    choose_alias_3_button.short_description = ''
    
    def create_new_alias_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #4fb2d3; font-weight: bold; padding: 10px 15px; width:100px">Add New</a>',
            reverse_lazy("admin:admin_nascar_choose_alias", args=[self.pk, 0])
        )
    create_new_alias_button.short_description = ''


# Nascar Data

class Driver(models.Model):
    nascar_driver_id = models.IntegerField(primary_key=True)
    driver_id = models.BigIntegerField(null=True, blank=True)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    full_name = models.CharField(max_length=50, null=True)
    badge = models.CharField(max_length=5, null=True)
    badge_image = models.URLField(null=True)
    manufacturer_image = models.URLField(null=True)
    manufacturer = models.CharField(max_length=100, null=True)
    team = models.CharField(max_length=100, null=True)
    driver_image = models.URLField(null=True)

    def __str__(self):
        return f'{self.full_name}'


class Track(models.Model):
    track_id = models.IntegerField(primary_key=True, db_index=True, unique=True)
    track_name = models.CharField(max_length=255, null=True)
    track_type = models.IntegerField(default=1, choices=TRACK_TYPES)

    def __str__(self):
        return f'{self.track_name}'
    

class Race(models.Model):
    race_id = models.BigIntegerField(primary_key=True, db_index=True, unique=True)
    series = models.IntegerField(default=1, choices=RACE_SERIES)
    race_season = models.IntegerField(default=2022)
    race_name = models.CharField(max_length=255, null=True)
    race_type = models.IntegerField(default=1, choices=RACE_TYPES)
    restrictor_plate = models.BooleanField(default=False)
    track = models.ForeignKey(Track, related_name='races', on_delete=models.SET_NULL, null=True)
    race_date = models.DateTimeField(null=True)
    qualifying_date = models.DateTimeField(null=True, blank=True)
    scheduled_distance = models.IntegerField(default=0)
    scheduled_laps = models.IntegerField(default=0)
    stage_1_laps = models.IntegerField(default=0)
    stage_2_laps = models.IntegerField(default=0)
    stage_3_laps = models.IntegerField(default=0)
    stage_4_laps = models.IntegerField(default=0)
    num_cars = models.IntegerField(default=0)
    num_lead_changes = models.IntegerField(default=0)
    num_leaders = models.IntegerField(default=0)
    num_cautions = models.IntegerField(default=0)
    num_caution_laps = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.race_name}'

    def num_stages(self):
        if self.stage_4_laps > 0:
            return 4
        elif self.stage_3_laps > 0:
            return 3
        elif self.stage_2_laps > 0:
            return 2
        elif self.stage_1_laps > 0:
            return 1
        return 0

    def get_laps_for_stage(self, stage=1):
        if stage == 1:
            return self.stage_1_laps
        elif stage == 2:
            return self.stage_2_laps
        elif stage == 3:
            return self.stage_3_laps
        elif stage == 4:
            return self.stage_4_laps
        return 0


class RaceResult(models.Model):
    race = models.ForeignKey(Race, related_name='results', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='results', on_delete=models.CASCADE)
    finishing_position = models.IntegerField(default=0)
    starting_position = models.IntegerField(default=0)
    laps_led = models.IntegerField(default=0)
    times_led = models.IntegerField(default=0)
    laps_completed = models.IntegerField(default=0)
    finishing_status = models.CharField(max_length=50, default='Running')
    disqualified = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.race} - {self.driver}'


class RaceCautionSegment(models.Model):
    race = models.ForeignKey(Race, related_name='cautions', on_delete=models.CASCADE)
    start_lap = models.IntegerField(default=0)
    end_lap = models.IntegerField(default=0)
    reason = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.reason}'


class RaceInfraction(models.Model):
    race = models.ForeignKey(Race, related_name='infractions', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='infractions', on_delete=models.CASCADE)
    lap = models.IntegerField(default=0)
    lap_assessed = models.IntegerField(default=0)
    infraction = models.TextField(null=True, blank=True)
    penalty = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.driver}: {self.infraction}'


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
    fd_salaries = models.FileField(upload_to='uploads/fd_salaries', blank=True, null=True)
    dk_contest_entries = models.IntegerField(default=5000)
    fd_contest_entries = models.IntegerField(default=5000)
    for_backtest = models.BooleanField(default=False)

    optimal_lineups_per_iteration = models.IntegerField(default=3, verbose_name='num_lineups')
    run_with_gto = models.BooleanField(default=True)
    run_with_lineup_rankings = models.BooleanField(default=False)
    
    # caution data
    laps_per_caution = models.FloatField(default=0.0)

    early_stage_caution_mean = models.FloatField(default=1.0)
    early_stage_caution_prob_debris = models.FloatField(default=0.1)
    early_stage_caution_prob_accident_small = models.FloatField(default=0.4)
    early_stage_caution_prob_accident_medium = models.FloatField(default=0.2)
    early_stage_caution_prob_accident_major = models.FloatField(default=0.3)

    final_stage_caution_mean = models.FloatField(default=3.0)
    final_stage_caution_prob_debris = models.FloatField(default=0.1)
    final_stage_caution_prob_accident_small = models.FloatField(default=0.4)
    final_stage_caution_prob_accident_medium = models.FloatField(default=0.2)
    final_stage_caution_prob_accident_major = models.FloatField(default=0.3)

    # variance data
    track_variance = models.FloatField(default=0.1)
    track_variance_late_restart = models.FloatField(default=0.1)

    def __str__(self):
        return f'{self.race} Sim {self.id}'

    def get_drivers(self):
        return self.race.results.all()

    def get_damage_profile(self, num_cars):
        return self.damage_profiles.get(
            min_cars_involved__lte=num_cars,
            max_cars_involved__gte=num_cars
        )

    def get_penalty_profile(self, stage, is_green):
        return self.penalty_profiles.get(
            stage=stage,
            is_green=is_green
        )

    def export_template_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #2563EB; font-weight: bold; padding: 10px 15px;">Template</a>',
            reverse_lazy("admin:nascar_admin_slate_template", args=[self.pk])
        )
    export_template_button.short_description = ''

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Run</a>',
            reverse_lazy("admin:nascar_admin_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''

    def export_all_results_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #2563EB; font-weight: bold; padding: 10px 15px;">Results</a>',
            reverse_lazy("admin:nascar_admin_slate_export_results", args=[self.pk])
        )
    export_all_results_button.short_description = ''

    def export_dk_results_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #2563EB; font-weight: bold; padding: 10px 15px;">DK</a>',
            reverse_lazy("admin:nascar_admin_slate_export_dk", args=[self.pk])
        )
    export_dk_results_button.short_description = ''


class RaceSimDamageProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='damage_profiles', on_delete=models.CASCADE)
    name = models.CharField(max_length=100, default='Small Accident')
    min_cars_involved = models.IntegerField(default=0)
    max_cars_involved = models.IntegerField(default=0)
    prob_no_damage = models.FloatField(default=0.05)
    prob_minor_damage = models.FloatField(default=0.1)
    prob_medium_damage = models.FloatField(default=0.1)
    prob_dnf = models.FloatField(default=0.75)

    def __str__(self):
        return f'Damage Profile {self.min_cars_involved} - {self.max_cars_involved} cars'


class RaceSimPenaltyProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='penalty_profiles', on_delete=models.CASCADE)
    stage = models.IntegerField(default=0)
    is_green = models.BooleanField(default=False)
    floor_impact = models.FloatField(default=0.0)
    ceiling_impact = models.FloatField(default=0.0)

    def __str__(self):
        return f'Penalty Profile: Stage {self.stage} - {self.get_flag_color()} cars'

    def get_flag_color(self):
        return 'Green' if self.is_green else 'Yellow'


class RaceSimFastestLapsProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='fl_profiles', on_delete=models.CASCADE)
    pct_fastest_laps_min = models.FloatField(default=0.0)
    pct_fastest_laps_max = models.FloatField(default=1.0)
    cum_fastest_laps_min = models.FloatField(default=0.0)
    cum_fastest_laps_max = models.FloatField(default=1.0)
    eligible_speed_min = models.IntegerField(default=1)
    eligible_speed_max = models.IntegerField(default=1)

    def __str__(self):
        return f'Fastest Laps Profile: {self.pct_fastest_laps_min * 100}% - {self.pct_fastest_laps_max * 100}%'


class RaceSimLapsLedProfile(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='ll_profiles', on_delete=models.CASCADE)
    pct_laps_led_min = models.FloatField(default=0.0)
    pct_laps_led_max = models.FloatField(default=1.0)
    cum_laps_led_min = models.FloatField(default=0.0)
    cum_laps_led_max = models.FloatField(default=1.0)
    rank_order = models.IntegerField(default=1)
    # eligible_fl_max = models.IntegerField(default=1)

    def __str__(self):
        return f'Laps Led Profile: {self.pct_laps_led_min * 100}% - {self.pct_laps_led_max * 100}%'


class RaceSimDriver(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='outcomes', on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, related_name='outcomes', on_delete=models.CASCADE)
    dk_salary = models.IntegerField(default=0)
    fd_salary = models.IntegerField(default=0)
    dk_name = models.CharField(max_length=100, blank=True, null=True)
    fd_name = models.CharField(max_length=100, blank=True, null=True)
    starting_position = models.IntegerField(default=0)
    speed_min = models.IntegerField(default=1)
    speed_max = models.IntegerField(default=5)
    crash_rate = models.FloatField(default=0.0)
    infraction_rate = models.FloatField(default=0.0)

    osr_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    sr_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    fp_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    ll_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    fl_outcomes = ArrayField(models.IntegerField(default=0), null=True, blank=True)
    crash_outcomes = ArrayField(models.CharField(max_length=5, null=True), null=True, blank=True)
    penalty_outcomes = ArrayField(models.CharField(max_length=5, null=True), null=True, blank=True)

    dk_scores = ArrayField(models.FloatField(), null=True, blank=True)
    fd_scores = ArrayField(models.FloatField(), null=True, blank=True)

    avg_fp = models.FloatField(default=0.0)
    avg_ll = models.FloatField(default=0.0)
    avg_fl = models.FloatField(default=0.0)

    avg_dk_score = models.FloatField(default=0.0)
    avg_fd_score = models.FloatField(default=0.0)

    gto = models.FloatField(default=0.0)
    dk_op = models.FloatField(default=0.0)
    fd_op = models.FloatField(default=0.0)

    def __str__(self):
        return f'{self.driver}'

    def get_teammates(self):
        return RaceSimDriver.objects.filter(
            sim=self.sim,
            driver__team=self.driver.team
        ).exclude(id=self.id)

    def get_scores(self, site):
        sp = self.starting_position

        # only calc score if starting position is set
        if sp == 0:
            return 0

        count = min(min(len(self.fp_outcomes), len(self.ll_outcomes)), len(self.fl_outcomes))

        return [(SITE_SCORING.get(site).get('place_differential') * (sp - self.fp_outcomes[index]) + SITE_SCORING.get(site).get('fastest_laps') * self.fl_outcomes[index] + SITE_SCORING.get(site).get('laps_led') * self.ll_outcomes[index] + SITE_SCORING.get(site).get('finishing_position').get(str(self.fp_outcomes[index]))) for index in range(0, count)]


class RaceSimLineup(models.Model):
    sim = models.ForeignKey(RaceSim, related_name='sim_lineups', on_delete=models.CASCADE)
    player_1 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_1', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_2', on_delete=models.CASCADE)
    player_3 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_3', on_delete=models.CASCADE)
    player_4 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_4', on_delete=models.CASCADE)
    player_5 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_5', on_delete=models.CASCADE)
    player_6 = models.ForeignKey(RaceSimDriver, related_name='sim_lineup_as_player_6', on_delete=models.CASCADE, null=True, blank=True)
    total_salary = models.IntegerField(default=0)
    sim_scores = ArrayField(models.FloatField(), null=True, blank=True)
    sim_score_ranks = ArrayField(models.IntegerField(), null=True, blank=True)
    median = models.FloatField(db_index=True, default=0.0)
    s75 = models.FloatField(db_index=True, default=0.0)
    s90 = models.FloatField(db_index=True, default=0.0)
    count = models.IntegerField(db_index=True, default=1)
    rank_median = models.FloatField(db_index=True, default=0.0)
    rank_s75 = models.FloatField(db_index=True, default=0.0)
    rank_s90 = models.FloatField(db_index=True, default=0.0)
    dup_projection = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    class Meta:
        verbose_name = 'Optimal Lineup'
        verbose_name_plural = 'Optimal Lineups'
        ordering = ['-count']

    @property
    def players(self):
        return [
            self.player_1, 
            self.player_2, 
            self.player_3, 
            self.player_4, 
            self.player_5, 
            self.player_6
        ]

    def get_percentile_sim_score(self, percentile):
        return numpy.percentile(self.sim_scores, float(percentile))

    def get_rank_percentile_sim_score(self, percentile):
        return numpy.percentile(self.sim_score_ranks, float(percentile))

    def simulate(self):
        self.sim_scores = [float(sum([p.dk_scores[i] for p in self.players])) for i in range(0, self.sim.iterations)]
        self.dup_projection = numpy.prod([x.dk_op for x in self.players]) * self.sim.dk_contest_entries
        self.median = numpy.median(self.sim_scores)
        self.s75 = self.get_percentile_sim_score(75)
        self.s90 = self.get_percentile_sim_score(90)
        self.save()


# DFS Slates

class SlateBuildConfig(models.Model):
    CLEAN_BY_CHOICES = (
        ('projected_score', 'Projected Score'),
        ('projected_rank', 'Projected Rank'),
    )
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.75)
    uniques = models.IntegerField(default=1)
    min_salary = models.IntegerField(default=0)
    optimize_by_percentile = models.IntegerField(default=50)
    lineup_multiplier = models.IntegerField(default=1)
    clean_by_percentile = models.IntegerField(default=50)
    clean_by_field = models.CharField(max_length=25, choices=CLEAN_BY_CHOICES, default='s90')
    clean_by_direction = models.CharField(max_length=25, choices=(('ascending', 'Ascending'), ('descending', 'Descending')), default='descending')
    duplicate_threshold = models.FloatField(default=5)

    class Meta:
        verbose_name = 'Build Config'
        verbose_name_plural = 'Build Configs'
        ordering = ['id']
    
    def __str__(self):
        return '{}'.format(self.name)


class Slate(models.Model):
    datetime = models.DateTimeField()
    name = models.CharField(max_length=255, verbose_name='Slate')
    race = models.ForeignKey(Race, related_name='slates', on_delete=models.SET_NULL, null=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    salaries = models.FileField(upload_to='uploads/salaries', blank=True, null=True)

    class Meta:
        ordering = ['-name']

    def __str__(self):
        return '{}'.format(self.name) if self.name is not None else '{}'.format(self.datetime)

    def make_lineups_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Make Lineups</a>',
            reverse_lazy("admin:admin_nascar_slate_make_lineups", args=[self.pk])
        )
    make_lineups_button.short_description = ''
    
    def export_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #5b80b2; font-weight: bold; padding: 10px 15px;">Export Lineups</a>',
            reverse_lazy("admin:admin_nascar_slate_export_lineups", args=[self.pk])
        )
    export_button.short_description = ''


class SlatePlayer(models.Model):
    slate_player_id = models.CharField(max_length=255, primary_key=True)
    slate = models.ForeignKey(Slate, related_name='players', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    csv_name = models.CharField(max_length=255, null=True, blank=True)
    salary = models.IntegerField()
    fantasy_points = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    ownership = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    driver = models.ForeignKey(Driver, related_name='slates', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return '{} ${}'.format(self.name, self.salary)

    class Meta:
        ordering = ['-salary', 'name']
 
        
class SlateLineup(models.Model):
    slate = models.ForeignKey(Slate, related_name='possible_lineups', on_delete=models.CASCADE)
    player_1 = models.ForeignKey(SlatePlayer, related_name='p1', on_delete=models.CASCADE, null=True, blank=True)
    player_2 = models.ForeignKey(SlatePlayer, related_name='p2', on_delete=models.CASCADE, null=True, blank=True)
    player_3 = models.ForeignKey(SlatePlayer, related_name='p3', on_delete=models.CASCADE, null=True, blank=True)
    player_4 = models.ForeignKey(SlatePlayer, related_name='p4', on_delete=models.CASCADE, null=True, blank=True)
    player_5 = models.ForeignKey(SlatePlayer, related_name='p5', on_delete=models.CASCADE, null=True, blank=True)
    player_6 = models.ForeignKey(SlatePlayer, related_name='p6', on_delete=models.CASCADE, null=True, blank=True)
    total_salary = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Slate Lineup'
        verbose_name_plural = 'Slate Lineups'
        ordering = ['-total_salary']

    def __str__(self):
        return f'{self.player_1} {self.player_2} {self.player_3} {self.player_4} {self.player_5} {self.player_6}'

    @property
    def players(self):
        return [
            self.player_1, 
            self.player_2, 
            self.player_3, 
            self.player_4, 
            self.player_5, 
            self.player_6
        ]

    def simulate(self):
        self.total_salary = sum([p.salary for p in self.players])
        self.save()


class SlateBuild(models.Model):
    slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)
    build_type = models.CharField(max_length=10, choices=BUILD_TYPES, default='cash')
    sim = models.ForeignKey(RaceSim, related_name='builds', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, related_name='builds', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    field_lineup_upload = models.FileField(upload_to='uploads/field_lineups', blank=True, null=True)

    class Meta:
        verbose_name = 'Slate Build'
        verbose_name_plural = 'Slate Builds'

    def __str__(self):
        return f'{self.slate.name}'

    def execute_build(self, user):
        self.lineups.all().delete()
        
        if self.configuration.optimize_by_percentile == 0:
            chain(
                group([
                    tasks.generate_random_lineup.si(
                        self.id,
                        list(self.projections.filter(in_play=True).values_list('id', flat=True)),
                        SITE_SCORING.get(self.slate.site).get('max_salary')
                    ) for _ in range(0, self.total_lineups * self.configuration.lineup_multiplier)
                ]),
                tasks.complete_random_lineup_creation.si(
                    self.id,
                    BackgroundTask.objects.create(
                        name='Build Lineups',
                        user=user
                    ).id
                ),
                tasks.rank_build_lineups.si(
                    self.id,
                    BackgroundTask.objects.create(
                        name=f'Rank lineups for {self}',
                        user=user
                    ).id
                )
            )()
        else:
            chain(
                tasks.build_lineups.si(
                    self.id,
                    BackgroundTask.objects.create(
                        name='Build Lineups',
                        user=user
                    ).id
                ),
                tasks.clean_lineups.si(
                    self.id,
                    BackgroundTask.objects.create(
                        name='Clean Lineups',
                        user=user
                    ).id
                )
            )()

    def num_lineups_created(self):
        return self.lineups.all().count()
    num_lineups_created.short_description = 'created'

    def num_field_lineups(self):
        return self.field_lineups.all().count()
    num_field_lineups.short_description = 'field'

    def get_exposure(self, slate_player):
        return self.lineups.filter(
            Q(
                Q(player_1__slate_player_id=slate_player.slate_player_id) | 
                Q(player_2__slate_player_id=slate_player.slate_player_id) | 
                Q(player_3__slate_player_id=slate_player.slate_player_id) | 
                Q(player_4__slate_player_id=slate_player.slate_player_id) | 
                Q(player_5__slate_player_id=slate_player.slate_player_id) | 
                Q(player_6__slate_player_id=slate_player.slate_player_id)
            )
        ).count()

    def build_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Build</a>',
            reverse_lazy("admin:admin_nascar_slatebuild_build", args=[self.pk])
        )
    build_button.short_description = ''
    
    def export_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #5b80b2; font-weight: bold; padding: 10px 15px;">Export</a>',
            reverse_lazy("admin:admin_nascar_slatebuild_export", args=[self.pk])
        )
    export_button.short_description = ''


class BuildPlayerProjection(models.Model):
    build = models.ForeignKey(SlateBuild, db_index=True, verbose_name='Build', related_name='projections', on_delete=models.CASCADE)
    slate_player = models.ForeignKey(SlatePlayer, db_index=True, related_name='builds', on_delete=models.CASCADE)
    starting_position = models.IntegerField(default=0)
    sim_scores = ArrayField(models.FloatField(), null=True, blank=True)
    projection = models.FloatField(db_index=True, default=0.0, verbose_name='Proj')
    ceiling = models.FloatField(db_index=True, default=0.0, verbose_name='Ceil')
    s75 = models.FloatField(db_index=True, default=0.0, verbose_name='s75')
    in_play = models.BooleanField(default=True)
    op = models.FloatField(default=0.0)
    gto = models.FloatField(default=0.0)
    min_exposure = models.FloatField(default=0.0, verbose_name='min')
    max_exposure = models.FloatField(default=1.0, verbose_name='max')

    class Meta:
        verbose_name = 'Player Projection'
        verbose_name_plural = 'Player Projections'
        ordering = ['-slate_player__salary']

    def __str__(self):
        return '{}'.format(str(self.slate_player))

    @property
    def name(self):
        return self.slate_player.name

    @property
    def salary(self):
        return self.slate_player.salary

    @property
    def exposure(self):
        if self.build.lineups.all().count() > 0:
            return self.build.lineups.filter(
                Q(
                    Q(slate_lineup__player_1=self.slate_player) | 
                    Q(slate_lineup__player_2=self.slate_player) | 
                    Q(slate_lineup__player_3=self.slate_player) | 
                    Q(slate_lineup__player_4=self.slate_player) | 
                    Q(slate_lineup__player_5=self.slate_player) | 
                    Q(slate_lineup__player_6=self.slate_player)
                )
            ).count() / self.build.lineups.all().count()
        return 0

    def get_percentile_projection(self, percentile):
        return numpy.percentile(self.sim_scores, float(percentile))


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
    player = models.ForeignKey(BuildPlayerProjection, related_name='groups', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Player'
        verbose_name_plural = 'Players'
    
    def __str__(self):
        return '{}'.format(self.player)
 
        
class SlateBuildLineup(models.Model):
    build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
    slate_lineup = models.ForeignKey(SlateLineup, verbose_name='Lineup', related_name='builds', on_delete=models.CASCADE)
    win_rate = models.FloatField(db_index=True, default=0.0)
    median = models.FloatField(db_index=True, default=0.0)
    s75 = models.FloatField(db_index=True, default=0.0)
    s90 = models.FloatField(db_index=True, default=0.0)

    class Meta:
        verbose_name = 'Lineup'
        verbose_name_plural = 'Lineups'
        ordering = ['-median']

    def __str__(self):
        return f'{self.slate_lineup}'

    @property
    def players(self):
        return [
            self.slate_lineup.player_1, 
            self.slate_lineup.player_2, 
            self.slate_lineup.player_3, 
            self.slate_lineup.player_4, 
            self.slate_lineup.player_5, 
            self.slate_lineup.player_6
        ]


class SlateBuildFieldLineup(models.Model):
    build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='field_lineups', on_delete=models.CASCADE)
    opponent_handle = models.CharField(max_length=100, blank=True, null=True)
    slate_lineup = models.ForeignKey(SlateLineup, verbose_name='Lineup', related_name='field_lineups', blank=True, null=True, on_delete=models.CASCADE)
    median = models.FloatField(db_index=True, default=0.0)
    s75 = models.FloatField(db_index=True, default=0.0)
    s90 = models.FloatField(db_index=True, default=0.0)

    class Meta:
        verbose_name = 'Field Lineup'
        verbose_name_plural = 'Field Lineups'
        ordering = ['-median']

    def __str__(self):
        return f'{self.slate_lineup}'

    @property
    def players(self):
        return [
            self.slate_lineup.player_1, 
            self.slate_lineup.player_2, 
            self.slate_lineup.player_3, 
            self.slate_lineup.player_4, 
            self.slate_lineup.player_5, 
            self.slate_lineup.player_6
        ]


class SlateBuildLineupMatchup(models.Model):
    build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='matchups', on_delete=models.CASCADE)
    slate_lineup = models.ForeignKey(SlateLineup, related_name='matchups', on_delete=models.CASCADE)
    field_lineup = models.ForeignKey(SlateBuildFieldLineup, related_name='matchups', on_delete=models.CASCADE)
    win_rate = models.FloatField(db_index=True, default=0.0)

    class Meta:
        verbose_name = 'Lineup Matchup'
        verbose_name_plural = 'Lineup Matchups'
        ordering = ['-win_rate']

    def __str__(self):
        return f'Lineup {self.slate_lineup.id} vs. {self.field_lineup.opponent_handle}'


# Backtesting

class Contest(models.Model):
    slate = models.ForeignKey(Slate, related_name='contests', on_delete=models.CASCADE)
    sim = models.ForeignKey(RaceSim, related_name='contests', on_delete=models.SET_NULL, null=True)
    cost = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    name = models.CharField(max_length=255, blank=True, null=True)
    num_entries = models.PositiveIntegerField(default=0)
    entries_file = models.FileField(upload_to='uploads/entries', blank=True, null=True)
    prizes_file = models.FileField(upload_to='uploads/prizes', blank=True, null=True)

    def __str__(self):
        return f'{self.name}'

    def get_payout(self, rank, rank_count):
        try:
            prize = self.prizes.filter(min_rank__lt=rank+rank_count, max_rank__gte=rank).aggregate(
                avg_prize=Avg('prize')
            ).get('avg_prize')
            return prize if prize is not None else 0.0
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


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, related_name='entries', on_delete=models.CASCADE)
    entry_id = models.CharField(max_length=50)
    entry_name = models.CharField(max_length=255, blank=True, null=True)
    lineup_str = models.TextField(blank=True, null=True)
    player_1 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_1', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_2', on_delete=models.CASCADE)
    player_3 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_3', on_delete=models.CASCADE)
    player_4 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_4', on_delete=models.CASCADE)
    player_5 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_5', on_delete=models.CASCADE)
    player_6 = models.ForeignKey(RaceSimDriver, related_name='contest_entry_as_player_6', on_delete=models.CASCADE, null=True, blank=True)
    sim_scores = ArrayField(models.FloatField(), null=True, blank=True)

    def __str__(self):
        return f'{self.entry_name}'

    class Meta:
        verbose_name_plural = 'Contest Entries'

    @property
    def players(self):
        return [
            self.player_1, 
            self.player_2, 
            self.player_3, 
            self.player_4, 
            self.player_5, 
            self.player_6
        ]

    def simulate(self):
        self.sim_scores = [float(sum([p.dk_scores[i] for p in self.players])) for i in range(0, self.contest.sim.iterations)]
        self.save()


class ContestBacktest(models.Model):
    contest = models.ForeignKey(Contest, related_name='backtests', on_delete=models.CASCADE)
    exclude_entries_by = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'{self.contest} Backtest'

    def run_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Run</a>',
            reverse_lazy("admin:nascar_admin_backtest_run", args=[self.pk])
        )
    run_button.short_description = ''


class ContestBacktestEntry(models.Model):
    entry = models.ForeignKey(ContestEntry, related_name='backtest_outcomes', on_delete=models.CASCADE)
    backtest = models.ForeignKey(ContestBacktest, related_name='entry_outcomes', on_delete=models.CASCADE)
    amount_won = models.FloatField(default=0.0)
    roi = models.FloatField(default=0.0)

    def __str__(self):
        return f'{self.entry} for {self.backtest}'
