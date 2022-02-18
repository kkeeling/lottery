import csv
import datetime
import difflib
import math
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
        '3': {
            'match_played': 30,
            'game_won': 2.5,
            'game_lost': -2.0,
            'set_won': 6.0,
            'set_lost': -3.0,
            'match_won': 6.0,
            'ace': 0.4,
            'double_fault': -1.0,
            'break': 0.75,
            'clean_set': 4.0,
            'straight_sets': 6.0,
            'no_double_faults': 2.5,
            'aces_threshold': 10,
            'aces': 2.0
        },
        '5': {
            'match_played': 30,
            'game_won': 2.0,
            'game_lost': -1.6,
            'set_won': 5.0,
            'set_lost': -2.5,
            'match_won': 5.0,
            'ace': 0.25,
            'double_fault': -1.0,
            'break': 0.5,
            'clean_set': 2.5,
            'straight_sets': 5.0,
            'no_double_faults': 5.0,
            'aces_threshold': 15,
            'aces': 2.0
        },
    }
}

ODDS_SITES = (
    ('pinnacle', 'Pinnacle'),
)


SURFACE_CHOICES = (
    ('Hard', 'Hard'),
    ('Clay', 'Clay'),
    ('Grass', 'Grass')
)


class Player(models.Model):
    HAND_CHOICES = (
        ('r', 'R'),
        ('l', 'L'),
        ('u', 'U'),
    )
    TOUR_CHOICES = (
        ('atp', 'ATP'),
        ('wta', 'WTA'),
    )
    player_id = models.CharField(max_length=15)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    tour = models.CharField(max_length=3, choices=TOUR_CHOICES)
    hand = models.CharField(max_length=1, choices=HAND_CHOICES)
    dob = models.DateField(null=True, blank=True)
    country = models.CharField(max_length=3)

    class Meta:
        verbose_name = 'Player'
        verbose_name_plural = 'Players'

    def __str__(self):
        return '{}'.format(self.full_name)

    @property
    def full_name(self):
        return '{} {}'.format(self.first_name, self.last_name)

    @property
    def age(self):
        today = datetime.date.today() 
        age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day)) 
    
        return age 
    
    def get_num_matches(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        )

        return winning_matches.count() + losing_matches.count()

    def get_serve_points_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_svpt=None) | Q(w_1stWon=None) | Q(w_2ndWon=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_svpt=None) | Q(l_1stWon=None) | Q(l_2ndWon=None))
        )

        w_points_data = winning_matches.aggregate(
            num_points=Sum('w_svpt'),
            num_1stWon=Sum('w_1stWon'),
            num_2ndWon=Sum('w_2ndWon')
        )
        l_points_data = losing_matches.aggregate(
            num_points=Sum('l_svpt'),
            num_1stWon=Sum('l_1stWon'),
            num_2ndWon=Sum('l_2ndWon')
        )

        if (w_points_data.get('num_points') is None or w_points_data.get('num_points') == 0) and (l_points_data.get('num_points') is None or l_points_data.get('num_points') == 0):
            return None        
        elif w_points_data.get('num_points') is None or w_points_data.get('num_points') == 0:
            rate = (l_points_data.get('num_1stWon') + l_points_data.get('num_2ndWon')) / (l_points_data.get('num_points'))
        elif l_points_data.get('num_games') is None or l_points_data.get('num_games') == 0:
            rate = (w_points_data.get('num_1stWon') + w_points_data.get('num_2ndWon')) / (w_points_data.get('num_points'))
        else:
            rate = (w_points_data.get('num_1stWon') + w_points_data.get('num_2ndWon') + l_points_data.get('num_1stWon') + l_points_data.get('num_2ndWon')) / (w_points_data.get('num_points') + l_points_data.get('num_points'))

        return round(rate, 4)

    def get_return_points_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_svpt=None) | Q(l_1stWon=None) | Q(l_2ndWon=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_svpt=None) | Q(w_1stWon=None) | Q(w_2ndWon=None))
        )

        w_points_data = winning_matches.aggregate(
            num_points=Sum('l_svpt'),
            num_1stWon=Sum('l_1stWon'),
            num_2ndWon=Sum('l_2ndWon')
        )
        l_points_data = losing_matches.aggregate(
            num_points=Sum('w_svpt'),
            num_1stWon=Sum('w_1stWon'),
            num_2ndWon=Sum('w_2ndWon')
        )

        if (w_points_data.get('num_points') is None or w_points_data.get('num_points') == 0) and (l_points_data.get('num_points') is None or l_points_data.get('num_points') == 0):
            return None        
        elif w_points_data.get('num_points') is None or w_points_data.get('num_points') == 0:
            rate = (l_points_data.get('num_points') - (l_points_data.get('num_1stWon') + l_points_data.get('num_2ndWon'))) / (l_points_data.get('num_points'))
        elif l_points_data.get('num_games') is None or l_points_data.get('num_games') == 0:
            rate = (w_points_data.get('num_points') - (w_points_data.get('num_1stWon') + w_points_data.get('num_2ndWon'))) / (w_points_data.get('num_points'))
        else:
            rate = ((l_points_data.get('num_points') - (l_points_data.get('num_1stWon') + l_points_data.get('num_2ndWon'))) + (w_points_data.get('num_points') - (w_points_data.get('num_1stWon') + w_points_data.get('num_2ndWon')))) / (w_points_data.get('num_points') + l_points_data.get('num_points'))

        return round(rate, 4)

    def get_ace_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_SvGms=None) | Q(w_ace=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_SvGms=None) | Q(l_ace=None))
        )

        w_ace_data = winning_matches.aggregate(
            num_aces=Sum('w_ace'),
            num_games=Sum('w_SvGms')
        )
        l_ace_data = losing_matches.aggregate(
            num_aces=Sum('l_ace'),
            num_games=Sum('l_SvGms')
        )

        if (w_ace_data.get('num_games') is None or w_ace_data.get('num_games') == 0) and (l_ace_data.get('num_games') is None or l_ace_data.get('num_games') == 0):
            return None        
        elif w_ace_data.get('num_games') is None or w_ace_data.get('num_games') == 0:
            ace_rate = (l_ace_data.get('num_aces')) / (l_ace_data.get('num_games'))
        elif l_ace_data.get('num_games') is None or l_ace_data.get('num_games') == 0:
            ace_rate = (w_ace_data.get('num_aces')) / (w_ace_data.get('num_games'))
        else:
            ace_rate = (w_ace_data.get('num_aces') + l_ace_data.get('num_aces')) / (w_ace_data.get('num_games') + l_ace_data.get('num_games'))

        return round(ace_rate, 2)

    def get_ace_pct(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_SvGms=None) | Q(w_ace=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_SvGms=None) | Q(l_ace=None))
        )

        w_ace_data = winning_matches.aggregate(
            num_aces=Sum('w_ace'),
            num_points=Sum('w_svpt'),
        )
        l_ace_data = losing_matches.aggregate(
            num_aces=Sum('l_ace'),
            num_points=Sum('l_svpt'),
        )

        if (w_ace_data.get('num_points') is None or w_ace_data.get('num_points') == 0) and (l_ace_data.get('num_points') is None or l_ace_data.get('num_points') == 0):
            return None        
        elif w_ace_data.get('num_points') is None or w_ace_data.get('num_points') == 0:
            ace_rate = (l_ace_data.get('num_aces')) / (l_ace_data.get('num_points'))
        elif l_ace_data.get('num_points') is None or l_ace_data.get('num_points') == 0:
            ace_rate = (w_ace_data.get('num_aces')) / (w_ace_data.get('num_points'))
        else:
            ace_rate = (w_ace_data.get('num_aces') + l_ace_data.get('num_aces')) / (w_ace_data.get('num_points') + l_ace_data.get('num_points'))

        return round(ace_rate, 4)

    def get_v_ace_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_SvGms=None) | Q(w_ace=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_SvGms=None) | Q(l_ace=None))
        )

        w_ace_data = winning_matches.aggregate(
            num_aces=Sum('l_ace'),
            num_games=Sum('l_SvGms')
        )
        l_ace_data = losing_matches.aggregate(
            num_aces=Sum('w_ace'),
            num_games=Sum('w_SvGms')
        )

        if (w_ace_data.get('num_games') is None or w_ace_data.get('num_games') == 0) and (l_ace_data.get('num_games') is None or l_ace_data.get('num_games') == 0):
            return None        
        elif w_ace_data.get('num_games') is None or w_ace_data.get('num_games') == 0:
            ace_rate = (l_ace_data.get('num_aces')) / (l_ace_data.get('num_games'))
        elif l_ace_data.get('num_games') is None or l_ace_data.get('num_games') == 0:
            ace_rate = (w_ace_data.get('num_aces')) / (w_ace_data.get('num_games'))
        else:
            ace_rate = (w_ace_data.get('num_aces') + l_ace_data.get('num_aces')) / (w_ace_data.get('num_games') + l_ace_data.get('num_games'))

        return round(ace_rate, 2)

    def get_df_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_SvGms=None) | Q(w_df=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_SvGms=None) | Q(l_df=None))
        )

        w_df_data = winning_matches.aggregate(
            num_dfs=Sum('w_df'),
            num_games=Sum('w_SvGms')
        )
        l_df_data = losing_matches.aggregate(
            num_dfs=Sum('l_df'),
            num_games=Sum('l_SvGms')
        )

        if (w_df_data.get('num_games') is None or w_df_data.get('num_games') == 0) and (l_df_data.get('num_games') is None or l_df_data.get('num_games') == 0):
            return None        
        elif w_df_data.get('num_games') is None or w_df_data.get('num_games') == 0:
            df_rate = (l_df_data.get('num_dfs')) / (l_df_data.get('num_games'))
        elif l_df_data.get('num_games') is None or l_df_data.get('num_games') == 0:
            df_rate = (w_df_data.get('num_dfs')) / (w_df_data.get('num_games'))
        else:
            df_rate = (w_df_data.get('num_dfs') + l_df_data.get('num_dfs')) / (w_df_data.get('num_games') + l_df_data.get('num_games'))

        return round(df_rate, 2)

    def get_df_pct(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_SvGms=None) | Q(w_df=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_SvGms=None) | Q(l_df=None))
        )

        w_df_data = winning_matches.aggregate(
            num_dfs=Sum('w_df'),
            num_points=Sum('w_svpt'),
        )
        l_df_data = losing_matches.aggregate(
            num_dfs=Sum('l_df'),
            num_points=Sum('l_svpt'),
        )

        if (w_df_data.get('num_points') is None or w_df_data.get('num_points') == 0) and (l_df_data.get('num_points') is None or l_df_data.get('num_points') == 0):
            return None        
        elif w_df_data.get('num_points') is None or w_df_data.get('num_points') == 0:
            df_rate = (l_df_data.get('num_dfs')) / (l_df_data.get('num_points'))
        elif l_df_data.get('num_points') is None or l_df_data.get('num_points') == 0:
            df_rate = (w_df_data.get('num_dfs')) / (w_df_data.get('num_points'))
        else:
            df_rate = (w_df_data.get('num_dfs') + l_df_data.get('num_dfs')) / (w_df_data.get('num_points') + l_df_data.get('num_points'))

        return round(df_rate, 4)

    def get_first_in_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_svpt=None) | Q(w_1stIn=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_svpt=None) | Q(l_1stIn=None))
        )

        w_data = winning_matches.aggregate(
            num_1stIns=Sum('w_1stIn'),
            num_points=Sum('w_svpt')
        )
        l_data = losing_matches.aggregate(
            num_1stIns=Sum('l_1stIn'),
            num_points=Sum('l_svpt')
        )

        if (w_data.get('num_points') is None or w_data.get('num_points') == 0) and (l_data.get('num_points') is None or l_data.get('num_points') == 0):
            return None        
        elif w_data.get('num_points') is None or w_data.get('num_points') == 0:
            first_in_rate = (l_data.get('num_1stIns')) / (l_data.get('num_points'))
        elif l_data.get('num_points') is None or l_data.get('num_points') == 0:
            first_in_rate = (w_data.get('num_1stIns')) / (w_data.get('num_points'))
        else:
            first_in_rate = (w_data.get('num_1stIns') + l_data.get('num_1stIns')) / (w_data.get('num_points') + l_data.get('num_points'))

        return round(first_in_rate, 2)

    def get_first_won_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_1stIn=None) | Q(w_1stWon=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_1stIn=None) | Q(l_1stWon=None))
        )

        w_data = winning_matches.aggregate(
            num_1stWons=Sum('w_1stWon'),
            num_points=Sum('w_1stIn')
        )
        l_data = losing_matches.aggregate(
            num_1stWons=Sum('l_1stWon'),
            num_points=Sum('l_1stIn')
        )

        if (w_data.get('num_points') is None or w_data.get('num_points') == 0) and (l_data.get('num_points') is None or l_data.get('num_points') == 0):
            return None        
        elif w_data.get('num_points') is None or w_data.get('num_points') == 0:
            first_won_rate = (l_data.get('num_1stWons')) / (l_data.get('num_points'))
        elif l_data.get('num_points') is None or l_data.get('num_points') == 0:
            first_won_rate = (w_data.get('num_1stWons')) / (w_data.get('num_points'))
        else:
            first_won_rate = (w_data.get('num_1stWons') + l_data.get('num_1stWons')) / (w_data.get('num_points') + l_data.get('num_points'))

        return round(first_won_rate, 2)

    def get_second_won_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_svpt=None) | Q(w_1stIn=None) | Q(w_2ndWon=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_svpt=None) | Q(l_1stIn=None) | Q(l_2ndWon=None))
        )

        w_data = winning_matches.aggregate(
            num_2ndWons=Sum('w_2ndWon'),
            num_points=Sum('w_svpt')- Sum('w_1stIn')
        )
        l_data = losing_matches.aggregate(
            num_2ndWons=Sum('l_2ndWon'),
            num_points=Sum('l_svpt')- Sum('l_1stIn')
        )

        if (w_data.get('num_points') is None or w_data.get('num_points') == 0) and (l_data.get('num_points') is None or l_data.get('num_points') == 0):
            return None        
        elif w_data.get('num_points') is None or w_data.get('num_points') == 0:
            second_won_rate = (l_data.get('num_2ndWons')) / (l_data.get('num_points'))
        elif l_data.get('num_points') is None or l_data.get('num_points') == 0:
            second_won_rate = (w_data.get('num_2ndWons')) / (w_data.get('num_points'))
        else:
            second_won_rate = (w_data.get('num_2ndWons') + l_data.get('num_2ndWons')) / (w_data.get('num_points') + l_data.get('num_points'))

        return round(second_won_rate, 2)

    def get_hold_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_bpFaced=None) | Q(w_bpSaved=None) | Q(w_SvGms=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_bpFaced=None) | Q(l_bpSaved=None) | Q(l_SvGms=None))
        )

        w_data = winning_matches.aggregate(
            num_breaks=Sum('w_bpFaced') - Sum('w_bpSaved'),
            num_chances=Sum('w_SvGms')
        )
        l_data = losing_matches.aggregate(
            num_breaks=Sum('l_bpFaced') - Sum('l_bpSaved'),
            num_chances=Sum('l_SvGms')
        )

        if (w_data.get('num_chances') is None or w_data.get('num_chances') == 0) and (l_data.get('num_chances') is None or l_data.get('num_chances') == 0):
            return None        
        elif w_data.get('num_chances') is None or w_data.get('num_chances') == 0:
            hold_rate = 1.0 - (l_data.get('num_breaks')) / (l_data.get('num_chances'))
        elif l_data.get('num_chances') is None or l_data.get('num_chances') == 0:
            hold_rate = 1.0 - (w_data.get('num_breaks')) / (w_data.get('num_chances'))
        else:
            hold_rate = 1.0 - (w_data.get('num_breaks') + l_data.get('num_breaks')) / (w_data.get('num_chances') + l_data.get('num_chances'))

        return round(hold_rate, 2)

    def get_break_rate(self, timeframe=52, startingFrom=datetime.date.today(), on_surface='Hard'):
        endDate = startingFrom - datetime.timedelta(weeks=timeframe)
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(l_bpFaced=None) | Q(l_bpSaved=None) | Q(l_SvGms=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface
        ).exclude(
           Q(Q(w_bpFaced=None) | Q(w_bpSaved=None) | Q(w_SvGms=None))
        )

        w_data = winning_matches.aggregate(
            num_breaks=Sum('l_bpFaced') - Sum('l_bpSaved'),
            num_chances=Sum('l_SvGms')
        )
        l_data = losing_matches.aggregate(
            num_breaks=Sum('w_bpFaced') - Sum('w_bpSaved'),
            num_chances=Sum('w_SvGms')
        )

        if (w_data.get('num_chances') is None or w_data.get('num_chances') == 0) and (l_data.get('num_chances') is None or l_data.get('num_chances') == 0):
            return None        
        elif w_data.get('num_chances') is None or w_data.get('num_chances') == 0:
            break_rate = (l_data.get('num_breaks')) / (l_data.get('num_chances'))
        elif l_data.get('num_chances') is None or l_data.get('num_chances') == 0:
            break_rate = (w_data.get('num_breaks')) / (w_data.get('num_chances'))
        else:
            break_rate = (w_data.get('num_breaks') + l_data.get('num_breaks')) / (w_data.get('num_chances') + l_data.get('num_chances'))

        return round(break_rate, 2)

    def get_rank(self, as_of=datetime.date.today()):
        ranking_history = self.ranking_history.filter(ranking_date__lte=as_of).order_by('-ranking_date')

        if ranking_history.count() > 0:
            return ranking_history[0].ranking
        return None

    def get_points_won_rate(self, vs_opponent=None, timeframe_in_weeks=0, startingFrom=datetime.date.today(), on_surface='Hard'):
        if timeframe_in_weeks == 0:
            endDate = startingFrom - datetime.timedelta(years=5)
        else:
            endDate = startingFrom - datetime.timedelta(weeks=timeframe_in_weeks)
        
        winning_matches = self.winning_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface,
            w_svpt__isnull=False,
            w_svpt__gt=0,
            l_svpt__isnull=False,
            l_svpt__gt=0
        ).exclude(
           Q(Q(w_svpt=None) | Q(w_1stWon=None) | Q(w_2ndWon=None))
        )
        losing_matches = self.losing_matches.filter(
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate,
            surface=on_surface,
            w_svpt__isnull=False,
            w_svpt__gt=0,
            l_svpt__isnull=False,
            l_svpt__gt=0
        ).exclude(
           Q(Q(l_svpt=None) | Q(l_1stWon=None) | Q(l_2ndWon=None))
        )

        if vs_opponent is not None:
            winning_matches = winning_matches.filter(loser=vs_opponent)
            losing_matches = losing_matches.filter(winner=vs_opponent)

        w_points_data = winning_matches.aggregate(
            sp=Sum('w_svpt'),
            sp1w=Sum('w_1stWon'),
            sp2w=Sum('w_2ndWon'),
            rp=Sum('l_svpt'),
            rp1w=Sum('l_1stWon'),
            rp2w=Sum('l_2ndWon')
        )
        l_points_data = losing_matches.aggregate(
            sp=Sum('l_svpt'),
            sp1w=Sum('l_1stWon'),
            sp2w=Sum('l_2ndWon'),
            rp=Sum('w_svpt'),
            rp1w=Sum('w_1stWon'),
            rp2w=Sum('w_2ndWon')
        )

        if w_points_data.get('sp') is None and l_points_data.get('sp') is None:
            return None
        elif l_points_data.get('sp') is None:
            spw = (w_points_data.get('sp1w') + w_points_data.get('sp2w')) / (w_points_data.get('sp'))
            rpw = (w_points_data.get('rp1w') + w_points_data.get('rp2w')) / (w_points_data.get('rp'))
        elif w_points_data.get('sp') is None:
            spw = (l_points_data.get('sp1w') + l_points_data.get('sp2w')) / (l_points_data.get('sp'))
            rpw = (l_points_data.get('rp1w') + l_points_data.get('rp2w')) / (l_points_data.get('rp'))
        else:
            spw = (w_points_data.get('sp1w') + w_points_data.get('sp2w') + l_points_data.get('sp1w') + l_points_data.get('sp2w')) / (w_points_data.get('sp') + l_points_data.get('sp'))
            rpw = (w_points_data.get('rp1w') + w_points_data.get('rp2w') + l_points_data.get('rp1w') + l_points_data.get('rp2w')) / (w_points_data.get('rp') + l_points_data.get('rp'))

        return {
            'opponent': vs_opponent,
            'spw': round(spw, 4),
            'rpw': round(rpw, 4),
        }


class RankingHistory(models.Model):
    FILES = [
        ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_current.csv'),
        ('wta', 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_current.csv'),
        ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_10s.csv'),
        ('wta', 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_10s.csv'),
        ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_00s.csv'),
        ('wta', 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_00s.csv'),
        # ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_90s.csv'),
        # ('wta', 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_90s.csv'),
        # ('wta', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_80s.csv'),
        # ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master/wta_rankings_80s.csv'),
        # ('atp', 'https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master/atp_rankings_70s.csv')
    ]
    ranking_date = models.DateField()
    ranking = models.PositiveIntegerField()
    player = models.ForeignKey(Player, related_name='ranking_history', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Ranking History'
        verbose_name_plural = 'Ranking Histories'

    def __str__(self):
        return '{} Ranking on {}'.format(self.player, self.ranking_date)


    @classmethod
    def update_rankings(cls):
        # cls.objects.all().delete()

        for tup in cls.FILES:
            tour = tup[0]
            url = tup[1]
            with requests.Session() as s:
                download = s.get(url)
                decoded_content = download.content.decode('latin-1')

                cr = csv.reader(decoded_content.splitlines(), delimiter=',')
                rows = list(cr)
                for row in rows:
                    try:
                        ranking_date = datetime.datetime.strptime(row[0], '%Y%m%d').date()
                    except:
                        continue
                    
                    try:
                        ranking = cls.objects.get(
                            ranking_date=ranking_date,
                            player=Player.objects.get(
                                player_id=row[2],
                                tour=tour
                            )
                        )
                        # ranking.ranking = int(row[1])
                        # ranking.save()
                        print('Found {}.'.format(str(ranking)))
                    except cls.DoesNotExist:
                        ranking = cls.objects.create(
                            ranking_date=ranking_date,
                            player=Player.objects.get(
                                player_id=row[2],
                                tour=tour
                            ),
                            ranking=int(row[1])
                        )
                        print('Created {}.'.format(str(ranking)))
                    except Player.DoesNotExist:
                        pass


class Match(models.Model):
    tourney_id = models.CharField(max_length=255, null=True, blank=True)
    tourney_name = models.CharField(max_length=255, null=True, blank=True)
    surface = models.CharField(max_length=255, null=True, blank=True)
    draw_size = models.IntegerField(null=True, blank=True)
    tourney_level = models.CharField(max_length=255, null=True, blank=True)
    tourney_date = models.DateField(null=True, blank=True)
    match_num = models.IntegerField(null=True, blank=True)
    winner = models.ForeignKey(Player, related_name='winning_matches', on_delete=models.CASCADE)
    winner_seed = models.CharField(max_length=255, null=True, blank=True)
    winner_entry = models.CharField(max_length=255, null=True, blank=True)
    winner_name = models.CharField(max_length=255, null=True, blank=True)
    winner_hand = models.CharField(max_length=255, null=True, blank=True)
    winner_ht = models.IntegerField(null=True, blank=True)
    winner_ioc = models.CharField(max_length=255, null=True, blank=True)
    winner_age = models.DecimalField(decimal_places=10, max_digits=15, null=True, blank=True)
    loser = models.ForeignKey(Player, related_name='losing_matches', on_delete=models.CASCADE)
    loser_seed = models.CharField(max_length=255, null=True, blank=True)
    loser_entry = models.CharField(max_length=255, null=True, blank=True)
    loser_name = models.CharField(max_length=255, null=True, blank=True)
    loser_hand = models.CharField(max_length=255, null=True, blank=True)
    loser_ht = models.IntegerField(null=True, blank=True)
    loser_ioc = models.CharField(max_length=255, null=True, blank=True)
    loser_age = models.DecimalField(decimal_places=10, max_digits=15, null=True, blank=True)
    score = models.CharField(max_length=255, null=True, blank=True)
    best_of = models.IntegerField(null=True, blank=True)
    round = models.CharField(max_length=255, null=True, blank=True)
    minutes = models.IntegerField(null=True, blank=True)
    w_ace = models.IntegerField(null=True, blank=True)
    w_df = models.IntegerField(null=True, blank=True)
    w_svpt = models.IntegerField(null=True, blank=True)
    w_1stIn = models.IntegerField(null=True, blank=True)
    w_1stWon = models.IntegerField(null=True, blank=True)
    w_2ndWon = models.IntegerField(null=True, blank=True)
    w_SvGms = models.IntegerField(null=True, blank=True)
    w_bpSaved = models.IntegerField(null=True, blank=True)
    w_bpFaced = models.IntegerField(null=True, blank=True)
    l_ace = models.IntegerField(null=True, blank=True)
    l_df = models.IntegerField(null=True, blank=True)
    l_svpt = models.IntegerField(null=True, blank=True)
    l_1stIn = models.IntegerField(null=True, blank=True)
    l_1stWon = models.IntegerField(null=True, blank=True)
    l_2ndWon = models.IntegerField(null=True, blank=True)
    l_SvGms = models.IntegerField(null=True, blank=True)
    l_bpSaved = models.IntegerField(null=True, blank=True)
    l_bpFaced = models.IntegerField(null=True, blank=True)
    winner_rank = models.IntegerField(null=True, blank=True)
    winner_rank_points = models.IntegerField(null=True, blank=True)
    loser_rank = models.IntegerField(null=True, blank=True)
    loser_rank_points = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'

    def __str__(self):
        return '{}: {} d. {} {}'.format(self.tourney_name, self.winner, self.loser, self.score)

    @property
    def tour(self):
        return self.winner.tour

    @property
    def winner_games_won(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            return sum([int(re.sub(r"[\(\[].*?[\)\]]", "", x)) for x in games_won[::2]])
        except:
            return 0

    @property
    def winner_games_lost(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_lost = self.score.replace(' ', '-').split('-')

            if 'RET' in games_lost:
                games_lost.pop()
            return sum([int(re.sub(r"[\(\[].*?[\)\]]", "", x)) for x in games_lost[1::2]])
        except:
            return 0

    @property
    def winner_sets_won(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            sets_won = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                sets_won += 1 if score1 >= 6 and score1 > score2 else 0
            return sets_won
        except:
            return 0

    @property
    def winner_sets_lost(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            sets_lost = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                sets_lost += 1 if score2 >= 6 and score1 < score2 else 0
            return sets_lost
        except:
            return 0

    @property
    def winner_breaks(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        return self.l_bpFaced - self.l_bpSaved if self.l_bpFaced is not None and self.l_bpSaved is not None else 0

    @property
    def winner_clean_sets(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            num_clean_sets = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                num_clean_sets += 1 if score1 >= 6 and score2 == 0 else 0

            return num_clean_sets
        except:
            return 0

    @property
    def winner_straight_sets(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        games_won = self.score.replace(' ', '-').split('-')

        if 'RET' in games_won:
            games_won.pop()
            games_won.pop()
            games_won.pop()

        return 1 if (len(games_won) / 2) == (math.ceil(self.best_of / 2)) else 0
    
    @property
    def winner_df_bonus(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        if self.w_df == 0:
            return 2.5 if self.best_of == 3 else 5.0
        return 0.0

    @property
    def winner_ace_bonus(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        if self.best_of == 3:
            return 2.0 if self.w_ace >= 10 else 0.0
        return 2.0 if self.w_ace >= 15 else 0.0

    @property
    def winner_retirement_bonus(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        if self.loser_retired:
            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()
                games_won.pop()
                games_won.pop()
            
            sets_complete = len(games_won) / 2
            if self.best_of == 3:
                if sets_complete == 0:
                    return 20.0
                elif sets_complete == 1:
                    return 15.0
                elif sets_complete == 2:
                    return 10.0
            else:
                if sets_complete == 0:
                    return 20.0
                elif sets_complete == 1:
                    return 16.0
                elif sets_complete == 2:
                    return 12.0
                elif sets_complete == 3:
                    return 8.0
                elif sets_complete == 4:
                    return 8.0

        return 0.0

    @property
    def loser_retired(self):
        return 'RET' in self.score

    @property
    def winner_dk_points(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 30        
        
        if self.w_ace is None or self.w_df is None:
            return None

        if self.best_of == 3:
            if self.loser_retired:
                return 30 + (2.5 * self.winner_games_won) + (-2.0 * self.winner_games_lost) + (6 * self.winner_sets_won) + (-3 * self.winner_sets_lost) + (0.4 * self.w_ace) + (-1 * self.w_df) + (0.75 * self.winner_breaks) + (4 * self.winner_clean_sets) + self.winner_ace_bonus + self.winner_retirement_bonus
            else:
                return 30 + (2.5 * self.winner_games_won) + (-2.0 * self.winner_games_lost) + (6 * self.winner_sets_won) + (-3 * self.winner_sets_lost) + 6 + (0.4 * self.w_ace) + (-1 * self.w_df) + (0.75 * self.winner_breaks) + (4 * self.winner_clean_sets) + (6 * self.winner_straight_sets) + self.winner_df_bonus + self.winner_ace_bonus
        elif self.best_of == 5:
            if self.loser_retired:
                return 30 + (2.0 * self.winner_games_won) + (-1.6 * self.winner_games_lost) + (5 * self.winner_sets_won) + (-2.5 * self.winner_sets_lost) + (0.25 * self.w_ace) + (-1 * self.w_df) + (0.5 * self.winner_breaks) + (2.5 * self.winner_clean_sets) + self.winner_ace_bonus + self.winner_retirement_bonus
            else:
                return 30 + (2.0 * self.winner_games_won) + (-1.6 * self.winner_games_lost) + (5 * self.winner_sets_won) + (-2.5 * self.winner_sets_lost) + 6 + (0.25 * self.w_ace) + (-1 * self.w_df) + (0.5 * self.winner_breaks) + (2.5 * self.winner_clean_sets) + (5 * self.winner_straight_sets) + self.winner_df_bonus + self.winner_ace_bonus
        else:
            return None

    @property
    def loser_games_won(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            return sum([int(re.sub(r"[\(\[].*?[\)\]]", "", x)) for x in games_won[1::2]])
        except:
            return 0

    @property
    def loser_games_lost(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_lost = self.score.replace(' ', '-').split('-')

            if 'RET' in games_lost:
                games_lost.pop()
            return sum([int(re.sub(r"[\(\[].*?[\)\]]", "", x)) for x in games_lost[::2]])
        except:
            return 0

    @property
    def loser_sets_won(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            sets_lost = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                sets_lost += 1 if score2 >= 6 and score1 < score2 else 0
            return sets_lost
        except:
            return 0

    @property
    def loser_sets_lost(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            sets_won = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                sets_won += 1 if score1 >= 6 and score1 > score2 else 0
            return sets_won
        except:
            return 0

    @property
    def loser_breaks(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        return self.w_bpFaced - self.w_bpSaved if self.w_bpFaced is not None and self.w_bpSaved is not None else 0

    @property
    def loser_clean_sets(self):
        try:
            if self.score == 'W/O' or self.score is None or self.best_of == 1:
                return 0

            games_won = self.score.replace(' ', '-').split('-')

            if 'RET' in games_won:
                games_won.pop()

            num_clean_sets = 0
            for i in range(0,len(games_won),2):
                score1 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i]))
                score2 = int(re.sub(r"[\(\[].*?[\)\]]", "", games_won[i+1]))

                num_clean_sets += 1 if score2 >= 6 and score1 == 0 else 0

            return num_clean_sets
        except:
            return 0
    
    @property
    def loser_df_bonus(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        if self.l_df == 0:
            return 2.5 if self.best_of == 3 else 5.0
        return 0.0

    @property
    def loser_ace_bonus(self):
        if self.score == 'W/O' or self.score is None or self.best_of == 1:
            return 0

        if self.best_of == 3:
            return 2.0 if self.l_ace >= 10 else 0.0
        return 2.0 if self.l_ace >= 15 else 0.0

    @property
    def loser_dk_points(self):
        if self.l_ace is None or self.l_df is None:
            return None

        if self.best_of == 3:
            return 30 + (2.5 * self.loser_games_won) + (-2.0 * self.loser_games_lost) + (6 * self.loser_sets_won) + (-3 * self.loser_sets_lost) + (0.4 * self.l_ace) + (-1 * self.l_df) + (0.75 * self.loser_breaks) + (4 * self.loser_clean_sets) + self.loser_df_bonus + self.loser_ace_bonus
        elif self.best_of == 5:
            return 30 + (2.0 * self.loser_games_won) + (-1.6 * self.loser_games_lost) + (5 * self.loser_sets_won) + (-2.5 * self.loser_sets_lost) + (0.25 * self.l_ace) + (-1 * self.l_df) + (0.5 * self.loser_breaks) + (2.5 * self.loser_clean_sets) + self.loser_df_bonus + self.loser_ace_bonus
        else:
            return None
            
    def get_winner_num_matches(self, timeframe=52):
        return self.winner.get_num_matches(timeframe=timeframe, startingFrom=self.tourney_date)

    def get_winner_ace_rate(self, timeframe=52):
        return self.winner.get_ace_rate(timeframe=timeframe, startingFrom=self.tourney_date)

    def get_winner_v_ace_rate(self, timeframe=52):
        return self.winner.get_v_ace_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_df_rate(self, timeframe=52):
        return self.winner.get_df_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_first_in_rate(self, timeframe=52):
        return self.winner.get_first_in_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_first_won_rate(self, timeframe=52):
        return self.winner.get_first_won_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_second_won_rate(self, timeframe=52):
        return self.winner.get_second_won_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_hold_rate(self, timeframe=52):
        return self.winner.get_hold_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_winner_break_rate(self, timeframe=52):
        return self.winner.get_break_rate(timeframe=timeframe, startingFrom=self.tourney_date)        
        
    def get_loser_num_matches(self, timeframe=52):
        return self.loser.get_num_matches(timeframe=timeframe, startingFrom=self.tourney_date)

    def get_loser_ace_rate(self, timeframe=52):
        return self.loser.get_ace_rate(timeframe=timeframe, startingFrom=self.tourney_date)

    def get_loser_v_ace_rate(self, timeframe=52):
        return self.loser.get_v_ace_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_df_rate(self, timeframe=52):
        return self.loser.get_df_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_first_in_rate(self, timeframe=52):
        return self.loser.get_first_in_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_first_won_rate(self, timeframe=52):
        return self.loser.get_first_won_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_second_won_rate(self, timeframe=52):
        return self.loser.get_second_won_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_hold_rate(self, timeframe=52):
        return self.loser.get_hold_rate(timeframe=timeframe, startingFrom=self.tourney_date)
        
    def get_loser_break_rate(self, timeframe=52):
        return self.loser.get_break_rate(timeframe=timeframe, startingFrom=self.tourney_date)        


class Alias(models.Model):
    dk_name = models.CharField(max_length=255, null=True, blank=True)
    fd_name = models.CharField(max_length=255, null=True, blank=True)
    pinn_name = models.CharField(max_length=255, null=True, blank=True)
    player = models.ForeignKey(Player, related_name='aliases', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Alias'
        verbose_name_plural = 'Aliases'

    def __str__(self):
        if self.player is None:
            return self.dk_name
        return '{}'.format(self.player)
    
    @classmethod
    def find_alias(clz, player_name, site):
        try:
            if site == 'draftkings':
                alias = Alias.objects.get(dk_name=player_name)
            elif site == 'fanduel':
                alias = Alias.objects.get(fd_name=player_name)
            elif site == 'pinnacle':
                alias = Alias.objects.get(pinn_name=player_name)
            else:
                raise Exception('{} is not a supported site yet.'.format(site))
        except Alias.MultipleObjectsReturned:
            if site == 'draftkings':
                alias = Alias.objects.filter(dk_name=player_name)[0]
            elif site == 'fanduel':
                alias = Alias.objects.filter(fd_name=player_name)[0]
            elif site == 'pinnacle':
                alias = Alias.objects.filter(pinn_name=player_name)[0]
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
                elif site == 'pinnacle':
                    seqmatch = difflib.SequenceMatcher(None, normal_name.lower(), possible_match.pinn_name.lower())
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
            print(a)

            return None

        return alias

    def get_alias(self, for_site):
        if for_site == 'fanduel':
            return self.fd_name
        elif for_site == 'draftkings':
            return self.dk_name
        elif for_site == 'pinnacle':
            return self.pinn_name


class MissingAlias(models.Model):
    player_name = models.CharField(max_length=255, null=True, blank=True)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS+ODDS_SITES, default='draftkings')
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


class SlateBuildConfig(models.Model):
    OPTIMIZE_CHOICES = (
        ('implied_win_pct', 'Implied Win %'),
        ('sim_win_pct', 'Simulated Win %'),
        ('projection', 'Median Projection'),
        ('s90', 'Ceiling Projection'),
    )
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.75)
    uniques = models.IntegerField(default=1)
    min_salary = models.IntegerField(default=0)
    optimize_by = models.CharField(max_length=50, choices=OPTIMIZE_CHOICES, default='implied_win_pct')
    lineup_multiplier = models.IntegerField(default=1)
    clean_lineups_by = models.CharField(max_length=15, choices=OPTIMIZE_CHOICES, default='implied_win_pct')

    class Meta:
        verbose_name = 'Build Config'
        verbose_name_plural = 'Build Configs'
        ordering = ['id']
    
    def __str__(self):
        return '{}'.format(self.name)


class PinnacleMatch(models.Model):
    id = models.BigIntegerField(primary_key=True, unique=True)
    event = models.CharField(max_length=255, default='foo')
    home_participant = models.CharField(max_length=255)
    away_participant = models.CharField(max_length=255)
    start_time = models.DateTimeField()

    def __str__(self):
        return '{} vs {}'.format(self.home_participant, self.away_participant)

    class Meta:
        verbose_name = 'Pinnacle Match'
        verbose_name_plural = 'Pinnacle Matches'

    def get_odds_for_player(self, player):
        alias = player.aliases.all()[0]
        return self.odds.all().order_by('-create_at')[0].home_price if self.home_participant == alias.pinn_name else self.odds.all().order_by('-create_at')[0].away_price

    def get_spread_for_player(self, player):
        alias = player.aliases.all()[0]
        return self.odds.all().order_by('-create_at')[0].home_spread if self.home_participant == alias.pinn_name else self.odds.all().order_by('-create_at')[0].away_spread


class PinnacleMatchOdds(models.Model):
    create_at = models.DateTimeField()
    match = models.ForeignKey(PinnacleMatch, related_name='odds', on_delete=models.CASCADE)
    home_price = models.IntegerField(default=0)
    away_price = models.IntegerField(default=0)
    home_spread = models.DecimalField(decimal_places=2, max_digits=4, default=0.0)
    away_spread = models.DecimalField(decimal_places=2, max_digits=4, default=0.0)

    def __str__(self):
        return '{} ({}) vs {} ({})'.format(self.match.home_participant, self.home_price, self.match.away_participant, self.away_price)

    def get_event(self):
        return self.match.event


class Slate(models.Model):
    datetime = models.DateTimeField()
    name = models.CharField(max_length=255, verbose_name='Slate')
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    is_main_slate = models.BooleanField(default=False)
    last_match_datetime = models.DateTimeField(blank=True, null=True)
    salaries = models.FileField(upload_to='uploads/salaries', blank=True, null=True)
    entries = models.FileField(upload_to='uploads/entries', blank=True, null=True)
    target_score = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Target')
    top_score = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Top')

    class Meta:
        ordering = ['-name']

    def __str__(self):
        return '{}'.format(self.name) if self.name is not None else '{}'.format(self.datetime)

    @property
    def best_fit_line(self):
        xs = numpy.array(self.players.all().values_list('salary', flat=True), dtype=numpy.float64)
        ys = numpy.array(SlatePlayerProjection.objects.filter(slate_player__in=self.players.all()).values_list('implied_win_pct', flat=True), dtype=numpy.float64)
        m = (((mean(xs)*mean(ys)) - mean(xs*ys)) /
            ((mean(xs)**2) - mean(xs**2)))
        b = mean(ys) - m*mean(xs)

        return (m, b)
        
    def is_pinn_player_in_slate(self, player):
        try:
            alias = Alias.objects.get(pinn_name=player)
            _ = SlatePlayer.objects.get(
                slate=self,
                name=alias.get_alias(self.site)
            )
            return True
        except Alias.DoesNotExist:
            print(f'{player} does not have an alias.')
            return False
        except SlatePlayer.DoesNotExist:
            print(f'{player} does not have a matching slate player.')
            return False

    def find_matches(self):
        matches = PinnacleMatch.objects.filter(
            start_time__gte=self.datetime,
            start_time__lt=self.datetime + datetime.timedelta(hours=12) if self.last_match_datetime is None else self.last_match_datetime
        ).exclude(
            Q(Q(home_participant__contains='/') | Q(away_participant__contains='/'))
        )

        for match in matches.iterator():
            player1 = match.home_participant
            player2 = match.away_participant

            if self.is_pinn_player_in_slate(player1) and self.is_pinn_player_in_slate(player2):
                slate_match, _ = SlateMatch.objects.get_or_create(
                    slate=self,
                    match=match
                )

                common_opponents = Player.objects.filter(
                    id__in=slate_match.common_opponents(slate_match.surface)
                )

                print(player1)
                alias = Alias.objects.get(pinn_name=player1)
                slate_player1 = SlatePlayer.objects.get(
                    slate=self,
                    name=alias.get_alias(self.site)
                )
                projection1, _ = SlatePlayerProjection.objects.get_or_create(
                    slate_player=slate_player1
                )
                projection1.slate_match = slate_match
                pinnacle_odds = slate_match.match.get_odds_for_player(alias.player)
                projection1.pinnacle_odds = pinnacle_odds
                projection1.spread = slate_match.match.get_spread_for_player(alias.player)
                
                if pinnacle_odds > 0:
                    projection1.implied_win_pct = 100/(100+pinnacle_odds)
                elif pinnacle_odds < 0:
                    projection1.implied_win_pct = -pinnacle_odds/(-pinnacle_odds+100)

                projection1.save()

                print(player2)
                alias = Alias.objects.get(pinn_name=player2)
                slate_player2 = SlatePlayer.objects.get(
                    slate=self,
                    name=alias.get_alias(self.site)
                )
                projection2, _ = SlatePlayerProjection.objects.get_or_create(
                    slate_player=slate_player2
                )
                projection2.slate_match = slate_match
                pinnacle_odds = slate_match.match.get_odds_for_player(alias.player)
                projection2.pinnacle_odds = pinnacle_odds
                projection2.spread = slate_match.match.get_spread_for_player(alias.player)
                
                if pinnacle_odds > 0:
                    projection2.implied_win_pct = 100/(100+pinnacle_odds)
                elif pinnacle_odds < 0:
                    projection2.implied_win_pct = -pinnacle_odds/(-pinnacle_odds+100)

                projection2.save()

                # data for sims
                if common_opponents.count() >= 3:
                    a_points_won = [
                        slate_player1.player.get_points_won_rate(
                            vs_opponent=common_opponent,
                            timeframe_in_weeks=52*2,
                            on_surface=slate_match.surface
                        ) for common_opponent in common_opponents        
                    ]
                    b_points_won = [
                        slate_player2.player.get_points_won_rate(
                            vs_opponent=common_opponent,
                            timeframe_in_weeks=52*2,
                            on_surface=slate_match.surface
                        ) for common_opponent in common_opponents        
                    ]

                    spw_a = [d.get('spw') for d in a_points_won if d is not None]
                    spw_b = [d.get('spw') for d in b_points_won if d is not None]
                    rpw_a = [d.get('rpw') for d in a_points_won if d is not None]
                    rpw_b = [d.get('rpw') for d in b_points_won if d is not None]

                    a = numpy.average(spw_a)
                    b = numpy.average(spw_b)
                    a_r = numpy.average(rpw_a)
                    b_r = numpy.average(rpw_b)
                else:
                    data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52,
                        on_surface=slate_match.surface
                    )

                    if data_a is None:
                        data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52*2,
                        on_surface=slate_match.surface
                    )

                    if data_a is None:
                        data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52*3,
                        on_surface=slate_match.surface
                    )

                    if data_a is None:
                        data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52*.5
                    )

                    if data_a is None:
                        data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52
                    )

                    if data_a is None:
                        data_a = slate_player1.player.get_points_won_rate(
                        timeframe_in_weeks=52*2
                    )

                    if data_a is None:
                        a = 0.0
                        a_r = 0.0
                    else:
                        a = data_a.get('spw')
                        a_r = data_a.get('rpw')

                    data_b = slate_player2.player.get_points_won_rate(
                        timeframe_in_weeks=52,
                        on_surface=slate_match.surface
                    )

                    if data_b is None:
                        data_b = slate_player2.player.get_points_won_rate(
                            timeframe_in_weeks=52*2,
                            on_surface=slate_match.surface
                        )

                    if data_b is None:
                        data_b = slate_player2.player.get_points_won_rate(
                        timeframe_in_weeks=52*3,
                        on_surface=slate_match.surface
                    )

                    if data_b is None:
                        data_b = slate_player2.player.get_points_won_rate(
                        timeframe_in_weeks=52*.5
                    )

                    if data_b is None:
                        data_b = slate_player2.player.get_points_won_rate(
                        timeframe_in_weeks=52
                    )

                    if data_b is None:
                        data_b = slate_player2.player.get_points_won_rate(
                        timeframe_in_weeks=52*2
                    )

                    if data_b is None:
                        b = 0.0
                        b_r = 0.0
                    else:
                        b = data_b.get('spw')
                        b_r = data_b.get('rpw')

                p1_ace = slate_player1.player.get_ace_pct(timeframe=52, on_surface=slate_match.surface)
                if p1_ace is None:
                    p1_ace = slate_player1.player.get_ace_pct(timeframe=52*2, on_surface=slate_match.surface)
                if p1_ace is None:
                    p1_ace = slate_player1.player.get_ace_pct(timeframe=52*3, on_surface=slate_match.surface)
                if p1_ace is None:
                    p1_ace = slate_player1.player.get_ace_pct(timeframe=52*.5)
                if p1_ace is None:
                    p1_ace = slate_player1.player.get_ace_pct(timeframe=52)
                if p1_ace is None:
                    p1_ace = slate_player1.player.get_ace_pct(timeframe=52*2)
                    
                p2_ace = slate_player2.player.get_ace_pct(timeframe=52, on_surface=slate_match.surface)
                if p2_ace is None:
                    p2_ace = slate_player2.player.get_ace_pct(timeframe=52*2, on_surface=slate_match.surface)
                if p2_ace is None:
                    p2_ace = slate_player2.player.get_ace_pct(timeframe=52*3, on_surface=slate_match.surface)
                if p2_ace is None:
                    p2_ace = slate_player2.player.get_ace_pct(timeframe=52*.5)
                if p2_ace is None:
                    p2_ace = slate_player2.player.get_ace_pct(timeframe=52)
                if p2_ace is None:
                    p2_ace = slate_player2.player.get_ace_pct(timeframe=52*2)

                p1_df = slate_player1.player.get_df_pct(timeframe=52, on_surface=slate_match.surface)
                if p1_df is None:
                    p1_df = slate_player1.player.get_df_pct(timeframe=52*2, on_surface=slate_match.surface)
                if p1_df is None:
                    p1_df = slate_player1.player.get_df_pct(timeframe=52*3, on_surface=slate_match.surface)
                if p1_df is None:
                    p1_df = slate_player1.player.get_df_pct(timeframe=52*.5)
                if p1_df is None:
                    p1_df = slate_player1.player.get_df_pct(timeframe=52)
                if p1_df is None:
                    p1_df = slate_player1.player.get_df_pct(timeframe=52*2)

                p2_df = slate_player2.player.get_df_pct(timeframe=52, on_surface=slate_match.surface)
                if p2_df is None:
                    p2_df = slate_player2.player.get_df_pct(timeframe=52*2, on_surface=slate_match.surface)
                if p2_df is None:
                    p2_df = slate_player2.player.get_df_pct(timeframe=52*3, on_surface=slate_match.surface)
                if p2_df is None:
                    p2_df = slate_player2.player.get_df_pct(timeframe=52*.5)
                if p2_df is None:
                    p2_df = slate_player2.player.get_df_pct(timeframe=52)
                if p2_df is None:
                    p2_df = slate_player2.player.get_df_pct(timeframe=52*2)

                if projection1.spw_rate == 0.0:
                    projection1.spw_rate = a
                    projection1.save()

                if projection1.rpw_rate == 0.0:
                    projection1.rpw_rate = a_r
                    projection1.save()

                if projection1.ace_rate == 0.0:
                    projection1.ace_rate = p1_ace if p1_ace is not None else 0.0
                    projection1.save()

                if projection1.df_rate == 0.0:
                    projection1.df_rate = p1_df if p1_df is not None else 0.0
                    projection1.save()

                if projection2.spw_rate == 0.0:
                    projection2.spw_rate = b
                    projection2.save()

                if projection2.rpw_rate == 0.0:
                    projection2.rpw_rate = b_r
                    projection2.save()

                if projection2.ace_rate == 0.0:
                    projection2.ace_rate = p2_ace if p2_ace is not None else 0.0
                    projection2.save()

                if projection2.df_rate == 0.0:
                    projection2.df_rate = p2_df if p2_df is not None else 0.0
                    projection2.save()

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Sim</a>',
            reverse_lazy("admin:tennis_admin_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''


class SlateMatch(models.Model):
    slate = models.ForeignKey(Slate, related_name='matches', on_delete=models.CASCADE)
    match = models.ForeignKey(PinnacleMatch, related_name='slates', on_delete=models.CASCADE)
    surface = models.CharField(max_length=255, default='Hard', choices=SURFACE_CHOICES)
    best_of = models.IntegerField(choices=[(3, '3'), (5, '5')], default=3)

    class Meta:
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'

    def __str__(self):
        return '{}: {}'.format(str(self.slate), str(self.match))

    def common_opponents(self, surface, timeframe_in_weeks=52):
        alias1 = Alias.objects.get(pinn_name=self.match.home_participant)
        alias2 = Alias.objects.get(pinn_name=self.match.away_participant)
        startingFrom = datetime.date.today()
        endDate = startingFrom - datetime.timedelta(weeks=timeframe_in_weeks)
        
        matches1 = Match.objects.filter(
            Q(Q(winner=alias1.player) | Q(loser=alias1.player)),
            surface=surface,
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate
        )
        matches2 = Match.objects.filter(
            Q(Q(winner=alias2.player) | Q(loser=alias2.player)),
            surface=surface,
            tourney_date__lte=startingFrom,
            tourney_date__gte=endDate
        )

        winners1 = list(matches1.values_list('winner', flat=True))
        losers1 = list(matches1.values_list('loser', flat=True))
        opponents1 = numpy.unique(winners1 + losers1)
        winners2 = list(matches2.values_list('winner', flat=True))
        losers2 = list(matches2.values_list('loser', flat=True))
        opponents2 = numpy.unique(winners2 + losers2)

        return numpy.intersect1d(opponents1, opponents2)


class SlatePlayer(models.Model):
    slate_player_id = models.CharField(max_length=255)
    slate = models.ForeignKey(Slate, related_name='players', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    surface = models.CharField(max_length=255, default='Hard', choices=SURFACE_CHOICES)
    best_of = models.IntegerField(default=3)
    salary = models.IntegerField()
    fantasy_points = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    ownership = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    player = models.ForeignKey(Player, related_name='slates', null=True, blank=True, on_delete=models.SET_NULL)
    opponent = models.ForeignKey(Player, related_name='slates_as_opponent', null=True, blank=True, on_delete=models.SET_NULL)
    withdrew = models.BooleanField(default=False)
    is_replacement_player = models.BooleanField(default=False)

    def __str__(self):
        if self.opponent is not None:
            return '{} ${} vs. {}'.format(self.name, self.salary, self.opponent)
        return '{} ${}'.format(self.name, self.salary)

    class Meta:
        ordering = ['-salary', 'name']
    
    @property
    def implied_salary(self):
        return (float(self.projection.implied_win_pct) - self.slate.best_fit_line[1]) / self.slate.best_fit_line[0]

    @property
    def value(self):
        return self.implied_salary - self.salary

    def find_pinn_match(self):
        alias = self.player.aliases.all()[0]
        pinnacle_matches = PinnacleMatch.objects.filter(
            Q(Q(home_participant__iexact=alias.pinn_name) | Q(away_participant__iexact=alias.pinn_name)),
            start_time__gte=self.slate.datetime,
            start_time__lte=self.slate.last_match_datetime + datetime.timedelta(hours=2)
        ).order_by('-start_time')

        if len(pinnacle_matches) > 0:
            return pinnacle_matches[0]
        return None
        
    def find_opponent(self):
        if self.player.aliases.count() > 0:
            alias = self.player.aliases.all()[0]
            match = self.find_pinn_match()

            try:
                if match is not None:
                    if match.home_participant == alias.pinn_name:
                        opponent_alias = Alias.objects.get(pinn_name=match.away_participant)
                    else:
                        print(match.home_participant)
                        opponent_alias = Alias.objects.get(pinn_name=match.home_participant)
                    
                    self.opponent = opponent_alias.player
                    self.save()
                    return opponent_alias.player
            except Alias.DoesNotExist:
                pass
        
        return None

    def withdraw_player(self):
        self.withdrew = True
        self.save()

        opponent = self.opponent.slates.get(slate=self.slate)
        opponent.opponent = None
        opponent.projection.clear()
        opponent.save()

    def get_num_matches(self, timeframe=52):
        return self.player.get_num_matches(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_ace_rate(self, timeframe=52):
        return self.player.get_ace_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_v_ace_rate(self, timeframe=52):
        return self.player.get_v_ace_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_df_rate(self, timeframe=52):
        return self.player.get_df_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_first_in_rate(self, timeframe=52):
        return self.player.get_first_in_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_first_won_rate(self, timeframe=52):
        return self.player.get_first_won_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_second_won_rate(self, timeframe=52):
        return self.player.get_second_won_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_hold_rate(self, timeframe=52):
        return self.player.get_hold_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_break_rate(self, timeframe=52):
        return self.player.get_break_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_rank(self):
        return self.player.get_rank(
            as_of=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_num_matches(self, timeframe=52):
        return self.opponent.get_num_matches(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_ace_rate(self, timeframe=52):
        return self.opponent.get_ace_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_v_ace_rate(self, timeframe=52):
        return self.opponent.get_v_ace_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_df_rate(self, timeframe=52):
        return self.opponent.get_df_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_first_in_rate(self, timeframe=52):
        return self.opponent.get_first_in_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_first_won_rate(self, timeframe=52):
        return self.opponent.get_first_won_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_second_won_rate(self, timeframe=52):
        return self.opponent.get_second_won_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_hold_rate(self, timeframe=52):
        return self.opponent.get_hold_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_break_rate(self, timeframe=52):
        return self.opponent.get_break_rate(
            timeframe=timeframe,
            startingFrom=self.slate.datetime.date(),
            on_surface=self.surface
        )

    def get_opponent_rank(self):
        return self.opponent.get_rank(
            as_of=self.slate.datetime.date()
        )

    def get_best_num_matches(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_num_matches(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_num_matches(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_num_matches(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_num_matches(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_num_matches(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_num_matches(timeframe=104)
        
        return None

    def get_best_ace_rate(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_ace_rate(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_ace_rate(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_ace_rate(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_ace_rate(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_ace_rate(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_ace_rate(timeframe=104)
        
        return None

    def get_best_v_ace_rate(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_v_ace_rate(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_v_ace_rate(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_v_ace_rate(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_v_ace_rate(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_v_ace_rate(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_v_ace_rate(timeframe=104)
        
        return None

    def get_best_opponent_v_ace_rate(self):
        if self.get_opponent_num_matches(timeframe=2) > 3:
            return self.get_opponent_v_ace_rate(timeframe=2)
        elif self.get_opponent_num_matches(timeframe=4) > 3:
            return self.get_opponent_v_ace_rate(timeframe=4)
        elif self.get_opponent_num_matches(timeframe=13) > 3:
            return self.get_opponent_v_ace_rate(timeframe=13)
        elif self.get_opponent_num_matches(timeframe=26) > 3:
            return self.get_opponent_v_ace_rate(timeframe=26)
        elif self.get_opponent_num_matches(timeframe=52) > 3:
            return self.get_opponent_v_ace_rate(timeframe=52)
        elif self.get_opponent_num_matches(timeframe=104) > 3:
            return self.get_opponent_v_ace_rate(timeframe=104)
        
        return None

    def get_best_df_rate(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_df_rate(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_df_rate(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_df_rate(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_df_rate(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_df_rate(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_df_rate(timeframe=104)
        
        return None

    def get_best_hold_rate(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_hold_rate(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_hold_rate(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_hold_rate(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_hold_rate(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_hold_rate(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_hold_rate(timeframe=104)
        
        return None

    def get_best_opponent_hold_rate(self):
        if self.get_opponent_num_matches(timeframe=2) > 3:
            return self.get_opponent_hold_rate(timeframe=2)
        elif self.get_opponent_num_matches(timeframe=4) > 3:
            return self.get_opponent_hold_rate(timeframe=4)
        elif self.get_opponent_num_matches(timeframe=13) > 3:
            return self.get_opponent_hold_rate(timeframe=13)
        elif self.get_opponent_num_matches(timeframe=26) > 3:
            return self.get_opponent_hold_rate(timeframe=26)
        elif self.get_opponent_num_matches(timeframe=52) > 3:
            return self.get_opponent_hold_rate(timeframe=52)
        elif self.get_opponent_num_matches(timeframe=104) > 3:
            return self.get_opponent_hold_rate(timeframe=104)
        
        return None

    def get_best_break_rate(self):
        if self.get_num_matches(timeframe=2) > 3:
            return self.get_break_rate(timeframe=2)
        elif self.get_num_matches(timeframe=4) > 3:
            return self.get_break_rate(timeframe=4)
        elif self.get_num_matches(timeframe=13) > 3:
            return self.get_break_rate(timeframe=13)
        elif self.get_num_matches(timeframe=26) > 3:
            return self.get_break_rate(timeframe=26)
        elif self.get_num_matches(timeframe=52) > 3:
            return self.get_break_rate(timeframe=52)
        elif self.get_num_matches(timeframe=104) > 3:
            return self.get_break_rate(timeframe=104)
        
        return None


class SlatePlayerProjection(models.Model):
    slate_player = models.OneToOneField(SlatePlayer, related_name='projection', on_delete=models.CASCADE)
    slate_match = models.ForeignKey(SlateMatch, related_name='projections', on_delete=models.CASCADE, null=True, blank=True)
    pinnacle_odds = models.IntegerField(default=0)
    implied_win_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name='iwin')
    game_total = models.DecimalField(max_digits=3, decimal_places=1, default=0.0, verbose_name='gt')
    spread = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    spw_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    rpw_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    ace_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    df_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)
    w_sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)
    sim_win_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name='sim_win')
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Proj')
    ceiling = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Ceil')
    s75 = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='s75')
    optimal_exposure = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name='opt')
    in_play = models.BooleanField(default=True)
    min_exposure = models.DecimalField(max_digits=3, decimal_places=2, default=0.0, verbose_name='min')
    max_exposure = models.DecimalField(max_digits=3, decimal_places=2, default=1.0, verbose_name='max')

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
    def opponent(self):
        return self.slate_player.opponent
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
    def odds_for_target(self):
        target_score = self.slate_player.slate.target_score

        if target_score is not None and target_score > 0.0:
            a = numpy.asarray(self.w_sim_scores)
            za = round((a > float(target_score)).sum()/a.size, ndigits=4)
            return za
        return None

    @property
    def odds_for_target_value(self):
        oft = self.odds_for_target

        if oft is None:
            return None
        return (self.salary / 100) / oft

    def calc_implied_win_pct(self):
        if self.pinnacle_odds > 0:
            self.implied_win_pct = 100/(100+self.pinnacle_odds)
        elif self.pinnacle_odds < 0:
            self.implied_win_pct = -self.pinnacle_odds/(-self.pinnacle_odds+100)
        self.save()

    def is_underdog(self):
        return self.implied_win_pct <= 0.4499999


class SlateBuild(models.Model):
    slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    used_in_contests = models.BooleanField(default=False, verbose_name='Used')
    configuration = models.ForeignKey(SlateBuildConfig, related_name='builds', verbose_name='Config', on_delete=models.SET_NULL, null=True)
    lineup_start_number = models.IntegerField(default=1)
    top_score = models.DecimalField(verbose_name='top', decimal_places=2, max_digits=5, blank=True, null=True)
    total_lineups = models.PositiveIntegerField(verbose_name='total', default=0)
    total_cashes = models.PositiveIntegerField(verbose_name='cashes', blank=True, null=True)
    total_one_pct = models.PositiveIntegerField(verbose_name='1%', blank=True, null=True)
    total_half_pct = models.PositiveIntegerField(verbose_name='0.5%', blank=True, null=True)
    binked = models.BooleanField(verbose_name='bink', help_text='Finished 1st, 2nd, or 3rd', default=False)

    class Meta:
        verbose_name = 'Slate Build'
        verbose_name_plural = 'Slate Builds'

    def __str__(self):
        return '{} ({}) @ {}'.format(self.slate.name, self.configuration, self.created.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %H:%M'))

    def execute_build(self, user):
        self.lineups.all().delete()
        
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
            ),
            tasks.calculate_exposures.si(
                self.id,
                BackgroundTask.objects.create(
                    name='Calculate Exposures',
                    user=user
                ).id
            )
        )()

    def num_lineups_created(self):
        return self.lineups.all().count()
    num_lineups_created.short_description = 'created'

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
            reverse_lazy("admin:admin_tennis_slatebuild_build", args=[self.pk])
        )
    build_button.short_description = ''
    
    def export_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #5b80b2; font-weight: bold; padding: 10px 15px;">Export</a>',
            reverse_lazy("admin:admin_tennis_slatebuild_export", args=[self.pk])
        )
    export_button.short_description = ''


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
 
        
class SlateBuildLineup(models.Model):
    build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
    player_1 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_1', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_2', on_delete=models.CASCADE)
    player_3 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_3', on_delete=models.CASCADE)
    player_4 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_4', on_delete=models.CASCADE)
    player_5 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_5', on_delete=models.CASCADE)
    player_6 = models.ForeignKey(SlatePlayerProjection, related_name='lineup_as_player_6', on_delete=models.CASCADE)
    total_salary = models.IntegerField(default=0)
    sim_scores = ArrayField(models.DecimalField(max_digits=5, decimal_places=2), null=True, blank=True)
    implied_win_pct = models.DecimalField(max_digits=10, decimal_places=9, default=0.0000, verbose_name='iwin')
    sim_win_pct = models.DecimalField(max_digits=10, decimal_places=9, default=0.0000, verbose_name='sim_win')
    roi = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, db_index=True)
    median = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s75 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    s90 = models.DecimalField(db_index=True, max_digits=10, decimal_places=2, default=0.0)
    actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = 'Lineup'
        verbose_name_plural = 'Lineups'

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

    def simulate(self):
        self.sim_win_pct = self.player_1.sim_win_pct * self.player_2.sim_win_pct * self.player_3.sim_win_pct * self.player_4.sim_win_pct * self.player_5.sim_win_pct * self.player_6.sim_win_pct
        self.sim_scores = [float(sum([p.sim_scores[i] for p in self.players])) for i in range(0, 10000)]
        self.median = numpy.median(self.sim_scores)
        self.s75 = self.get_percentile_sim_score(75)
        self.s90 = self.get_percentile_sim_score(90)
        self.save()


class SlateBuildPlayerExposure(models.Model):
    build = models.ForeignKey(SlateBuild, related_name='exposures', on_delete=models.CASCADE)
    player = models.ForeignKey(SlatePlayerProjection, related_name='exposures', on_delete=models.CASCADE)
    exposure = models.DecimalField(max_digits=5, decimal_places=4, default=0.0)
