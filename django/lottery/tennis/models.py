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

from django.db import models, signals
from django.db.models import Q, Sum
from django.db.models.signals import post_save
from django.utils.html import format_html
from django.urls import reverse_lazy
from django.dispatch import receiver

from tagulous.models import SingleTagField

from . import optimize


SITE_OPTIONS = (
    ('draftkings', 'DraftKings'),
    ('fanduel', 'Fanduel'),
)


ODDS_SITES = (
    ('pinnacle', 'Pinnacle'),
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
    name = models.CharField(max_length=255)
    site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='draftkings')
    randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.75)
    uniques = models.IntegerField(default=1)
    min_salary = models.IntegerField(default=0)

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
        self.matches.all().delete()

        matches = PinnacleMatch.objects.filter(
            start_time__gte=self.datetime,
            start_time__lt=self.datetime + datetime.timedelta(hours=12) if self.last_match_datetime is None else self.last_match_datetime
        ).exclude(
            Q(Q(home_participant__contains='/') | Q(away_participant__contains='/'))
        )

        for match in matches.iterator():
            player1 = match.home_participant
            player2 = match.away_participant

            if self.is_pinn_player_in_slate(player1) or self.is_pinn_player_in_slate(player2):
                SlateMatch.objects.create(
                    slate=self,
                    match=match
                )

    def create_projections(self):
        for slate_player in self.players.all():
            (projection, _) = SlatePlayerProjection.objects.get_or_create(
                slate_player=slate_player
            )
            
            match = slate_player.find_pinn_match()
            if match is not None:
                projection.pinnacle_odds = match.get_odds_for_player(slate_player.player)
                projection.spread = match.get_spread_for_player(slate_player.player)
                projection.calc_implied_win_pct()

            print(projection, match)

    def find_opponents(self):
        for slate_player in self.players.all():
            if slate_player.opponent is None:
                slate_player.find_opponent()

    def project_players(self):
        for slate_player in self.players.all():
            projection = slate_player.projection
            projection.calc_implied_win_pct()

        for slate_player in self.players.all():
            projection = slate_player.projection
            if projection.implied_win_pct > 0.0:
                projection.get_projection_from_ml()

    def project_ownership(self):
        players = self.players.exclude(withdrew=True).exclude(is_replacement_player=True)
        start = datetime.datetime.now()

        num_lineups = 500 if players.count() < 40 else 1000

        print('Building {} lineups...'.format(num_lineups))
        op = optimize.optimize_for_ownership(players, num_lineups=num_lineups)

        for id in op:
            slate_player = SlatePlayer.objects.get(slate_player_id=id)
            slate_player.projection.projected_exposure = op[id]/num_lineups
            slate_player.projection.save()
            
        print('elapsed time:', datetime.datetime.now() - start)

    def find_in_play(self):
        projections = SlatePlayerProjection.objects.filter(
            slate_player__slate=self).exclude(
                slate_player__withdrew=True).exclude(
                    slate_player__opponent=None)
        total_exp = 0
        for projection in projections:
            projection.find_in_play()

            if projection.in_play:
                total_exp += projection.optimal_exposure

    def create_build(self):
        if self.builds.all().count() == 0:
            SlateBuild.objects.create(
                slate=self,
                used_in_contests=True,
                configuration=SlateBuildConfig.objects.get(id=1),
                total_lineups=self.num_lineups
            )

    def sim_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Sim</a>',
            reverse_lazy("admin:tennis_admin_slate_simulate", args=[self.pk])
        )
    sim_button.short_description = ''


class SlateMatch(models.Model):
    slate = models.ForeignKey(Slate, related_name='matches', on_delete=models.CASCADE)
    match = models.ForeignKey(PinnacleMatch, related_name='slates', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Match'
        verbose_name_plural = 'Matches'

    def __str__(self):
        return '{}: {}'.format(str(self.slate), str(self.match))


class SlatePlayer(models.Model):
    SURFACE_CHOICES = (
        ('Hard', 'Hard'),
        ('Clay', 'Clay'),
        ('Grass', 'Grass')
    )
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
    pinnacle_odds = models.IntegerField(default=0)
    implied_win_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name='iwin')
    game_total = models.DecimalField(max_digits=3, decimal_places=1, default=0.0, verbose_name='gt')
    spread = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Proj')

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

    def calc_implied_win_pct(self):
        if self.pinnacle_odds > 0:
            self.implied_win_pct = 100/(100+self.pinnacle_odds)
        elif self.pinnacle_odds < 0:
            self.implied_win_pct = -self.pinnacle_odds/(-self.pinnacle_odds+100)
        self.save()


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

    def build(self):
        start = datetime.datetime.now()

        self.lineups.all().delete()

        players = self.slate.players.filter(withdrew=False, projection__in_play=True).order_by('projection__pinnacle_odds')

        print('Building {} lineups...'.format(self.total_lineups))
        lineups = optimize.optimize(players, self.configuration, self.groups.filter(active=True), num_lineups=self.total_lineups)
        
        for (index, lineup) in enumerate(lineups):
            player_ids = [p.id for p in lineup.players]

            slate_lineup = SlateBuildLineup.objects.create(
                build=self,
                player_1=SlatePlayer.objects.get(slate_player_id=lineup.players[0].id, slate=self.slate),
                player_2=SlatePlayer.objects.get(slate_player_id=lineup.players[1].id, slate=self.slate),
                player_3=SlatePlayer.objects.get(slate_player_id=lineup.players[2].id, slate=self.slate),
                player_4=SlatePlayer.objects.get(slate_player_id=lineup.players[3].id, slate=self.slate),
                player_5=SlatePlayer.objects.get(slate_player_id=lineup.players[4].id, slate=self.slate),
                player_6=SlatePlayer.objects.get(slate_player_id=lineup.players[5].id, slate=self.slate)
            )

            slate_lineup.six_win_odds = numpy.prod([
                slate_lineup.player_1.projection.implied_win_pct,
                slate_lineup.player_2.projection.implied_win_pct,
                slate_lineup.player_3.projection.implied_win_pct,
                slate_lineup.player_4.projection.implied_win_pct,
                slate_lineup.player_5.projection.implied_win_pct,
                slate_lineup.player_6.projection.implied_win_pct,
            ])
            slate_lineup.total_salary = lineup.salary_costs
            slate_lineup.save()
            
        print('elapsed time:', datetime.datetime.now() - start)

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


class BuildPlayerProjection(models.Model):
    build = models.ForeignKey(SlateBuild, related_name='projections', on_delete=models.CASCADE)
    slate_player = models.OneToOneField(SlatePlayer, related_name='build_projection', on_delete=models.CASCADE)
    pinnacle_odds = models.IntegerField(default=0)
    implied_win_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0.0000, verbose_name='iwin')
    game_total = models.DecimalField(max_digits=3, decimal_places=1, default=0.0, verbose_name='gt')
    spread = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    projection = models.DecimalField(max_digits=5, decimal_places=2, db_index=True, default=0.0, verbose_name='Proj')
    in_play = models.BooleanField(default=True)

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
    player_1 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_1', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_2', on_delete=models.CASCADE)
    player_3 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_3', on_delete=models.CASCADE)
    player_4 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_4', on_delete=models.CASCADE)
    player_5 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_5', on_delete=models.CASCADE)
    player_6 = models.ForeignKey(BuildPlayerProjection, related_name='lineup_as_player_6', on_delete=models.CASCADE)
    total_salary = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Lineup'
        verbose_name_plural = 'Lineups'


def process_slate_player_sheet(sender, instance, **kwargs):
    if instance.sheet_type == 'site':
        if instance.slate.site == 'fanduel':
            process_fanduel_slate_player_sheet(instance)
        elif instance.slate.site == 'draftkings':
            process_draftkings_slate_player_sheet(instance)
        else:
            raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))
    else:
        raise Exception('{} is nto a valid sheet type.'.format(instance.sheet_type))


def process_fanduel_slate_player_sheet(instance):
    pass


def process_draftkings_slate_player_sheet(instance):
    with open(instance.sheet.url, mode='r') as players_file:
        csv_reader = csv.reader(players_file, delimiter=',')
        row_count = 0
        missing_players = []

        for row in csv_reader:
            if row_count > 0:
                player_id = row[3]
                site_pos = row[4]
                player_name = row[2].strip()
                salary = row[5]
                opponent_last_name = row[6].replace(row[7], '').replace('@', '')

                alias = None

                try:
                    alias = Alias.objects.get(dk_name__iexact=player_name)
                except Alias.DoesNotExist:
                    missing_players.append(player_name)
                
                if alias is not None:
                    try:
                        slate_player = SlatePlayer.objects.get(
                            slate_player_id=player_id,
                            slate=instance.slate,
                            name=alias.dk_name
                        )
                    except SlatePlayer.DoesNotExist:
                        slate_player = SlatePlayer(
                            slate_player_id=player_id,
                            slate=instance.slate,
                            name=alias.dk_name
                        )

                    slate_player.salary = salary
                    slate_player.player = alias.player
                    slate_player.save()
                    
                    print(slate_player)
            row_count += 1

        if len(missing_players) > 0:
            print()
            print('Missing players:')
            for p in missing_players:
                print(p)

