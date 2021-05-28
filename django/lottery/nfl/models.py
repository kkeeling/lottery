# import csv
# import datetime
# import json
# import math
# import pytz
# import requests
# import statistics
# import traceback
# import uuid

# from collections import namedtuple
# from django.conf import settings
# from django.db import models, signals
# from django.db.models import Q, Sum, Value, Aggregate, FloatField, Max, Count
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.utils import timezone

# from tagulous.models import SingleTagField

# from alias.models import Alias

# from . import optimal
# from . import optimize


# BuildEval = namedtuple('BuildEval', ['top_score', 'total_cashes', 'total_one_pct', 'total_half_pct', 'binked'])

# SITE_OPTIONS = (
#     ('draftkings', 'DraftKings'),
#     ('fanduel', 'Fanduel'),
#     ('yahoo', 'Yahoo'),
# )


# class Median(Aggregate):
#     function = 'PERCENTILE_CONT'
#     name = 'median'
#     output_field = FloatField()
#     template = '%(function)s(0.5) WITHIN GROUP (ORDER BY %(expressions)s)'


# class Week(models.Model):
#     num = models.PositiveIntegerField('Week #')
#     slate_year = models.PositiveIntegerField()
#     start = models.DateField()
#     end = models.DateField()

#     class Meta:
#         ordering = ['start']

#     def __str__(self):
#         return '{} Week {}'.format(self.slate_year, self.num)

#     def update_vegas(self):
#         month = self.start.strftime('%m')
#         date = self.start.strftime('%d')
#         year = self.start.strftime('%Y')

#         url = 'https://www.fantasylabs.com/api/sportevents/1/{}_{}_{}/vegas/'.format(month, date, year)
#         response = requests.get(url)
        
#         event_details = response.json()
#         for event in event_details:
#             properties = event.get('EventDetails').get('Properties')

#             if properties.get('HomeGameSpreadCurrent', None) is not None:
#                 home_team = event.get('HomeTeamShortVar')
#                 away_team = event.get('VisitorTeamShortVar')
#                 game_date = datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S')

#                 if event.get('HomeTeamShortVar') == 'JAX':
#                     home_team = 'JAC'
#                 if event.get('HomeTeamShortVar') == 'LV' and game_date.year < 2020:
#                     home_team = 'OAK'
#                 if event.get('HomeTeamShortVar') == 'LA':
#                     home_team = 'LAR'
#                 if event.get('VisitorTeamShortVar') == 'JAX':
#                     away_team = 'JAC'
#                 if event.get('VisitorTeamShortVar') == 'LV' and game_date.year < 2020:
#                     away_team = 'OAK'
#                 if event.get('VisitorTeamShortVar') == 'LA':
#                     away_team = 'LAR'

#                 try:
#                     game = Game.objects.get(
#                         id=event.get("EventId"),
#                         week=self
#                     )
#                     game.home_team = home_team
#                     game.away_team = away_team
#                     game.game_date = datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S')
#                     game.game_total = float(event.get('OU'))
#                     game.home_spread = float(properties.get('HomeGameSpreadCurrent'))
#                     game.away_spread = float(properties.get('VisitorGameSpreadCurrent'))
#                     game.home_implied = float(properties.get('HomeVegasRuns'))
#                     game.away_implied = float(properties.get('VisitorVegasRuns'))
#                     game.save()
#                 except Game.DoesNotExist:
#                     # check if this game already exists on another week (due to rescheduling)
#                     existing_games = Game.objects.filter(id=event.get("EventId"))
#                     if existing_games.count() > 0:
#                         existing_games.delete()

#                     game = Game.objects.create(
#                         id=event.get("EventId"),
#                         week=self,
#                         home_team=home_team,
#                         away_team=away_team,
#                         game_date=datetime.datetime.strptime(event.get('EventDateTime'), '%Y-%m-%dT%H:%M:%S'),
#                         game_total=float(event.get('OU')),
#                         home_spread=float(properties.get('HomeGameSpreadCurrent')),
#                         away_spread=float(properties.get('VisitorGameSpreadCurrent')),
#                         home_implied=float(properties.get('HomeVegasRuns')),
#                         away_implied=float(properties.get('VisitorVegasRuns'))
#                     )
                
#                 home_projections = SlatePlayerProjection.objects.filter(
#                     slate_player__slate__week=self,
#                     slate_player__team=game.home_team)
#                 home_projections.update(
#                     team_total=game.home_implied,
#                     game_total=game.game_total
#                 )
#                 away_projections = SlatePlayerProjection.objects.filter(
#                     slate_player__slate__week=self,
#                     slate_player__team=game.away_team)
#                 away_projections.update(
#                     team_total=game.away_implied,
#                     game_total=game.game_total
#                 )

#                 print(game)


# class Game(models.Model):
#     week = models.ForeignKey(Week, related_name='games', on_delete=models.CASCADE)
#     home_team = models.CharField(max_length=4)
#     away_team = models.CharField(max_length=4)
#     game_date = models.DateTimeField()
#     game_total = models.DecimalField(decimal_places=2, max_digits=4)
#     home_spread = models.DecimalField(decimal_places=2, max_digits=4)
#     away_spread = models.DecimalField(decimal_places=2, max_digits=4)
#     home_implied = models.DecimalField(decimal_places=2, max_digits=4)
#     away_implied = models.DecimalField(decimal_places=2, max_digits=4)

#     def __str__(self):
#         # localtz = pytz.timezone(settings.TIME_ZONE)
#         # local_dt = self.game_date.replace(tzinfo=localtz)
#         # print(localtz, self.game_date.tzinfo)
#         return '{}: {} @ {} {}'.format(str(self.week), self.away_team, self.home_team, self.game_date.strftime('%m/%d/%y %-I:%M %p'))


# class Slate(models.Model):
#     datetime = models.DateTimeField(null=True, blank=True)
#     name = models.CharField(max_length=255, verbose_name='Slate', null=True, blank=True)
#     week = models.ForeignKey(Week, related_name='slates', verbose_name='Week', on_delete=models.SET_NULL, null=True, blank=True)
#     site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
#     is_main_slate = models.BooleanField(default=False)

#     class Meta:
#         ordering = ['-name']

#     def __str__(self):
#         return '{}'.format(self.name) if self.name is not None else '{}'.format(self.datetime)

#     @property
#     def teams(self):
#         games = self.games.all()
#         home_teams = list(games.values_list('game__home_team', flat=True))
#         away_teams = list(games.values_list('game__away_team', flat=True))

#         return home_teams + away_teams

#     def num_games(self):
#         return self.games.all().count()
#     num_games.short_description = '# games'

#     def num_contests(self):
#         return self.contests.all().count()
#     num_contests.short_description = '# contests'

#     def num_slate_players(self):
#         return self.players.all().count()
#     num_slate_players.short_description = '# Slate Players'

#     def num_projected_players(self):
#         return self.players.exclude(projection=None).count()
#     num_projected_players.short_description = '# Projected Players'

#     def num_qbs(self):
#         return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='QB').count()
#     num_qbs.short_description = '# qbs'

#     def num_in_play(self):
#         return self.players.filter(projection__in_play=True).count()
#     num_in_play.short_description = '# in play'

#     def num_stack_only(self):
#         return self.players.filter(projection__stack_only=True).count()
#     num_stack_only.short_description = '# stack only'

#     def num_rbs(self):
#         return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').count()
#     num_rbs.short_description = '# rbs'

#     def num_top_rbs(self):
#         return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB', projection__rb_group__lte=2).count()
#     num_top_rbs.short_description = '# top rbs'

#     def median_rb_projection(self):
#         return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').aggregate(median_projection=Median('projection__projection')).get('median_projection', 0.0)
#     median_rb_projection.short_description = 'median rb projection'

#     def median_rb_ao(self):
#         return self.players.filter(projection__in_play=True, projection__slate_player__site_pos='RB').aggregate(median_opp=Median('projection__adjusted_opportunity')).get('median_opp', 0.0)
#     median_rb_ao.short_description = 'median rb ao'
    
#     def group_rbs(self):
#         SlatePlayerProjection.objects.filter(slate_player__slate=self).update(rb_group=None)
#         rbs = SlatePlayerProjection.objects.filter(slate_player__slate=self, slate_player__site_pos='RB', in_play=True)

#         group_index = 1
#         top_rb = rbs.order_by('-rb_group_value')[0]

#         for rb in rbs.order_by('-rb_group_value'):
#             if rb.rb_group_value < float(top_rb.rb_group_value) * 0.95:
#                 group_index += 1
#                 top_rb = rb
            
#             rb.rb_group = group_index
#             rb.save()

#     def balance_rb_exposures(self):
#         rbs = SlatePlayerProjection.objects.filter(slate_player__slate=self, slate_player__site_pos='RB', in_play=True)
#         for rb in rbs:
#             median_value = max(statistics.median([round(float(p.adjusted_opportunity), 2) for p in rbs.filter(rb_group=rb.rb_group)]), 2.0)
#             rb.balanced_projection = median_value
#             rb.save()

#     def get_great_score(self):
#         if self.contests.all().count() > 0:
#             return self.contests.all()[0].great_score
#         return None

#     def get_one_pct_score(self):
#         if self.contests.all().count() > 0:
#             return self.contests.all()[0].one_pct_score
#         return None

#     def find_games(self):
#         if not self.is_main_slate:
#             return

#         self.games.all().delete()

#         games = Game.objects.filter(
#             week=self.week,
#             game_date__gte=self.datetime,
#             game_date__lt=self.datetime + datetime.timedelta(hours=5)
#         )

#         for game in games:
#             SlateGame.objects.create(
#                 slate=self,
#                 game=game
#             )


# class SlateGame(models.Model):
#     slate = models.ForeignKey(Slate, related_name='games', on_delete=models.CASCADE)
#     game = models.ForeignKey(Game, related_name='slates', on_delete=models.CASCADE)

#     class Meta:
#         verbose_name = 'Game'
#         verbose_name_plural = 'Games'

#     def __str__(self):
#         return '{}: {}'.format(str(self.slate), str(self.game))


# class Contest(models.Model):
#     slate = models.ForeignKey(Slate, related_name='contests', on_delete=models.CASCADE, null=True, blank=True)
#     cost = models.DecimalField(decimal_places=2, max_digits=10)
#     num_games = models.IntegerField(null=True, blank=True)
#     max_entrants = models.IntegerField()
#     max_entries = models.IntegerField()
#     mincash_payout = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     mincash_score = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     name = models.CharField(max_length=255)
#     places_paid = models.IntegerField(null=True, blank=True)
#     prize_pool = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     start_date = models.IntegerField(null=True, blank=False)
#     total_entrants = models.IntegerField(null=True, blank=True)
#     winning_payout = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     winning_score = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     url = models.URLField(null=True, blank=True)
#     one_pct_score = models.DecimalField('1% Score', decimal_places=2, max_digits=10, null=True, blank=True)
#     one_pct_rank = models.IntegerField('1% Rank', null=True, blank=True)
#     half_pct_score = models.DecimalField('0.5% Score', decimal_places=2, max_digits=10, null=True, blank=True)
#     half_pct_rank = models.IntegerField('0.5% Rank', null=True, blank=True)
#     great_score = models.DecimalField('Great Score', decimal_places=2, max_digits=10, null=True, blank=True)

#     def __str__(self):
#         return '{}'.format(self.name)

#     class Meta:
#         ordering = ['slate', '-prize_pool']


# class ContestImportSheet(models.Model):
#     SITE_OPTIONS = (
#         ('draftkings', 'DraftKings'),
#         ('fanduel', 'Fanduel'),
#         ('yahoo', 'Yahoo'),
#     )
#     site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
#     sheet = models.FileField(upload_to='uploads/contest')

#     def __str__(self):
#         return '{}'.format(str(self.site))


# class SlatePlayer(models.Model):
#     player_id = models.CharField(max_length=255, null=True, blank=True)
#     slate = models.ForeignKey(Slate, related_name='players', on_delete=models.CASCADE)
#     name = models.CharField(max_length=255)
#     salary = models.IntegerField()
#     site_pos = models.CharField(max_length=5)
#     team = models.CharField(max_length=4)
#     fantasy_points = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
#     game = models.CharField(max_length=10)
#     ownership = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)

#     def __str__(self):
#         if self.fantasy_points is None:
#             return '{} {} ${} (vs. {})'.format(self.team, self.name, self.salary, self.get_opponent())
#         return '{} {} ${} (vs. {}) -- {}'.format(self.team, self.name, self.salary, self.get_opponent(), self.fantasy_points)

#     def get_team_color(self):
#         return settings.TEAM_COLORS[self.team]

#     def get_opponent(self):
#         return self.game.replace(self.team, '').replace('_', '')

#     def get_slate_game(self):
#         games = self.slate.games.filter(
#             Q(Q(game__home_team=self.team) | Q(game__away_team=self.team))
#         )

#         if games.count() > 0:
#             return games[0]
#         return None

#     class Meta:
#         ordering = ['-salary', 'name']


# class SlatePlayerBuildExposure(SlatePlayer):
#     '''
#     Proxy model for viewing slate player exposures within a build
#     '''
#     class Meta:
#         proxy = True
#         ordering = ['projection__rb_group', '-salary']
#         verbose_name = 'Exposure'
#         verbose_name_plural = 'Exposures'


# class SlateProjectionSheet(models.Model):
#     slate = models.OneToOneField(Slate, related_name='projections', on_delete=models.CASCADE)
#     projection_sheet = models.FileField(upload_to='uploads/projections')

#     def __str__(self):
#         return '{}'.format(str(self.slate))


# class SlatePlayerImportSheet(models.Model):
#     SHEET_TYPES = (
#         ('site', 'Salary File'),
#         ('fantasycruncher', 'FantasyCruncher Export')
#     )
#     slate = models.OneToOneField(Slate, related_name='salaries', on_delete=models.CASCADE)
#     sheet_type = models.CharField(max_length=255, choices=SHEET_TYPES, default='site')
#     sheet = models.FileField(upload_to='uploads/salaries')

#     def __str__(self):
#         return '{}'.format(str(self.slate))


# class SlatePlayerActualsSheet(models.Model):
#     slate = models.OneToOneField(Slate, related_name='actuals', on_delete=models.CASCADE)
#     sheet = models.FileField(upload_to='uploads/actuals')

#     def __str__(self):
#         return '{}'.format(str(self.slate))


# class SlatePlayerProjection(models.Model):
#     slate_player = models.OneToOneField(SlatePlayer, related_name='projection', on_delete=models.CASCADE)
#     projection = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='Proj')
#     adjusted_opportunity = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name='AO')
#     rb_group_value = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
#     rb_group = models.PositiveIntegerField(null=True, blank=True)
#     balanced_projection = models.DecimalField(null=True, blank=True, max_digits=5, decimal_places=2, default=0.0)
#     team_total = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, verbose_name='tt')
#     game_total = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True, verbose_name='gt')
#     spread = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
#     in_play = models.BooleanField(default=True)
#     stack_only = models.BooleanField(default=False, verbose_name='SO', help_text='Player is only in pool when stacked with QB or opposing QB')
#     qb_stack_only = models.BooleanField(default=False, verbose_name='SwQB', help_text='Generate QB stacks with this player')
#     opp_qb_stack_only = models.BooleanField(default=False, verbose_name='SwOQB', help_text='Generate Opp QB stacks with this player')
#     at_most_one_in_stack = models.BooleanField(default=False, verbose_name='AM1', help_text='Generate stacks with only 1 of players with this designation')
#     at_least_one_in_lineup = models.BooleanField(default=False, verbose_name='AL1', help_text='At least one player with this designation should appear in every lineup')
#     at_least_two_in_lineup = models.BooleanField(default=False, verbose_name='AL2', help_text='At least two players with this designation should appear in every lineup')
#     locked = models.BooleanField(default=False)

#     class Meta:
#         verbose_name = 'Player Projection'
#         verbose_name_plural = 'Player Projections'
#         ordering = ['-projection']

#     def __str__(self):
#         return '{} -- Proj: {}'.format(str(self.slate_player), self.projection)

#     @property
#     def name(self):
#         return self.slate_player.name

#     @property
#     def salary(self):
#         return self.slate_player.salary

#     @property
#     def team(self):
#         return self.slate_player.team

#     @property
#     def position(self):
#         return self.slate_player.site_pos

#     @property
#     def position_rank(self):
#         aggregate = SlatePlayerProjection.objects.filter(
#             slate_player__slate=self.slate_player.slate,
#             slate_player__site_pos=self.slate_player.site_pos,
#             projection__gt=self.projection).aggregate(ranking=Count('projection'))
#         return aggregate.get('ranking') + 1

#     def get_team_color(self):
#         return self.slate_player.get_team_color()

#     def get_game(self):
#         return self.slate_player.game

#     def get_game_total(self):
#         game = self.slate_player.get_slate_game()

#         if game == None:
#             return None
        
#         return game.game.game_total

#     def get_team_total(self):
#         game = self.slate_player.get_slate_game()

#         if game == None:
#             return None
        
#         return game.game.home_implied if self.slate_player.team == game.game.home_team else game.game.away_implied

#     def get_spread(self):
#         game = self.slate_player.get_slate_game()

#         if game == None:
#             return None
        
#         return game.game.home_spread if self.slate_player.team == game.game.home_team else game.game.away_spread

#     def get_opponent(self):
#         return self.get_game().replace(self.slate_player.team, '').replace('_', '')

#     def set_rb_group_value(self):
#         self.rb_group_value = float(self.projection) * 6 + float(self.adjusted_opportunity) * 4
#         self.balanced_projection = self.rb_group_value / 10
#         self.save()

#     def find_in_play(self):
#         if self.slate_player.slate.site == 'fanduel':
#             self.find_in_play_fanduel()
#         elif self.slate_player.slate.site == 'draftkings':
#             self.find_in_play_draftkings()
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))
        
#         if self.slate_player.site_pos == 'RB':
#             self.set_rb_group_value()

#     def find_in_play_fanduel(self):        
#         projection_threshold = self.getPlayerThreshold(self.slate_player.site_pos, self.slate_player.slate.num_games())
#         ao_threshold = self.getAOThreshold(self.slate_player.slate.num_games())
#         if self.slate_player.site_pos == 'RB' and (self.projection >= projection_threshold or self.adjusted_opportunity >= ao_threshold):
#             self.in_play = True

#             if self.slate_player.slate.num_games() > 4 and self.projection >= 16.4:
#                 self.at_least_one_in_lineup = True
#         elif self.slate_player.site_pos == 'WR' and self.projection >= projection_threshold:
#             self.in_play = True
#         elif self.slate_player.site_pos == 'QB' and self.projection >= projection_threshold:
#             if self.team_total <= 19.5:
#                 self.in_play = False
#             elif self.game_total < 42.0:
#                 self.in_play = False
#             elif self.projection <= 19.9 and self.game_total <= 42.5:
#                 self.in_play = False
#             elif self.team_total < 24.5 and self.projection <= 15.8:
#                 self.in_play = False
#             else:
#                 self.in_play = True
#         elif self.slate_player.site_pos == 'D' or self.slate_player.site_pos == 'DST':
#             self.in_play = True
#         elif self.slate_player.site_pos == 'TE' and self.projection >= projection_threshold:
#             self.in_play = True
#         else:
#             self.in_play = False
        
#         self.save()

#     def find_in_play_draftkings(self):        
#         projection_threshold = self.getPlayerThreshold(self.slate_player.site_pos, self.slate_player.slate.num_games())
#         ao_threshold = self.getAOThreshold(self.slate_player.slate.num_games())
#         if self.slate_player.site_pos == 'RB' and (self.projection >= projection_threshold and self.adjusted_opportunity >= ao_threshold):
#             self.in_play = True
#         elif self.slate_player.site_pos == 'WR' and self.projection >= projection_threshold:
#             self.in_play = True
#         elif self.slate_player.site_pos == 'QB' and self.projection >= projection_threshold:
#             if self.team_total <= 19.5:
#                 self.in_play = False
#             elif self.game_total < 42.0:
#                 self.in_play = False
#             elif self.projection <= 19.9 and self.game_total <= 42.5:
#                 self.in_play = False
#             elif self.team_total < 24.5 and self.projection <= 15.8:
#                 self.in_play = False
#             else:
#                 self.in_play = True
#         elif self.slate_player.site_pos == 'D' or self.slate_player.site_pos == 'DST':
#             self.in_play = True
#         elif self.slate_player.site_pos == 'TE' and self.projection >= projection_threshold:
#             self.in_play = True
#         else:
#             self.in_play = False
        
#         self.save()

#     def find_al1(self):
#         if self.slate_player.slate.site == 'fanduel':
#             self.find_al1_fanduel()
#         elif self.slate_player.slate.site == 'draftkings':
#             self.find_al1_draftkings()
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def find_al1_fanduel(self):        
#         projection_threshold = self.getPlayerAL1Threshold(self.slate_player.slate.num_games())
#         self.at_least_one_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
#         self.save()

#     def find_al1_draftkings(self):        
#         projection_threshold = self.getPlayerAL1Threshold(self.slate_player.slate.num_games())
#         self.at_least_one_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
#         self.save()

#     def find_al2(self):
#         if self.slate_player.slate.site == 'fanduel':
#             self.find_al2_fanduel()
#         elif self.slate_player.slate.site == 'draftkings':
#             self.find_al2_draftkings()
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def find_al2_fanduel(self):        
#         projection_threshold = self.getPlayerAL2Threshold(self.slate_player.slate.num_games())
#         self.at_least_two_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
#         self.save()

#     def find_al2_draftkings(self):        
#         projection_threshold = self.getPlayerAL2Threshold(self.slate_player.slate.num_games())
#         self.at_least_two_in_lineup = (self.projection >= projection_threshold and self.slate_player.site_pos in ['RB', 'WR', 'TE'])
#         self.save()

#     def getPlayerThreshold(self, position, num_games):
#         if self.slate_player.slate.site == 'fanduel':
#             return self.getFanduelThreshold(position, num_games)
#         elif self.slate_player.slate.site == 'draftkings':
#             return self.getDraftKingsThreshold(position, num_games)
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def getFanduelThreshold(self, position, num_games):
#         # QB
#         if position == 'QB':
#             if num_games < 4:
#                 return 9.9
#             else:
#                 return 14.9

#         # RB
#         elif position == 'RB':
#             if num_games > 5:
#                 return 13.9
#             else:
#                 return 6.9

#         # WR
#         elif position == 'WR':
#             if num_games > 5:
#                 return 7.9
#             else:
#                 return 4.9

#         # TE
#         else:
#             if num_games > 5:
#                 return 4.9
#             else:
#                 return 4.9

#     def getDraftKingsThreshold(self, position, num_games):
#         # QB
#         if position == 'QB':
#             if num_games < 4:
#                 return 9.9
#             else:
#                 return 14.9

#         # RB
#         elif position == 'RB':
#             if num_games > 5:
#                 return 15.9
#             else:
#                 return 6.9

#         # WR
#         elif position == 'WR':
#             if num_games > 5:
#                 return 8.9
#             else:
#                 return 4.9

#         # TE
#         else:
#             if num_games > 5:
#                 return 4.9
#             else:
#                 return 4.9

#     def getAOThreshold(self, num_games):
#         if self.slate_player.slate.site == 'fanduel':
#             return self.getFanduelAOThreshold(num_games)
#         elif self.slate_player.slate.site == 'draftkings':
#             return self.getDraftKingsAOThreshold(num_games)
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def getFanduelAOThreshold(self, num_games):
#         if num_games > 4:
#             return 19.9
#         else:
#             return 9.9

#     def getDraftKingsAOThreshold(self, num_games):
#         if num_games > 4:
#             return 19.9
#         else:
#             return 17.9

#     def getPlayerAL1Threshold(self, num_games):
#         if self.slate_player.slate.site == 'fanduel':
#             return self.getFanduelAL1Threshold(num_games)
#         elif self.slate_player.slate.site == 'draftkings':
#             return self.getDraftKingsAL1Threshold(num_games)
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def getFanduelAL1Threshold(self, num_games):
#         if num_games > 4:
#             return 16.4
#         else:
#             return 16.4

#     def getDraftKingsAL1Threshold(self, num_games):
#         if num_games > 4:
#             return 16.4
#         else:
#             return 16.4

#     def getPlayerAL2Threshold(self, num_games):
#         if self.slate_player.slate.site == 'fanduel':
#             return self.getFanduelAL2Threshold(num_games)
#         elif self.slate_player.slate.site == 'draftkings':
#             return self.getDraftKingsAL2Threshold(num_games)
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(self.slate_player.slate.site))

#     def getFanduelAL2Threshold(self, num_games):
#         if num_games > 4:
#             return 16.9
#         else:
#             return 16.9

#     def getDraftKingsAL2Threshold(self, num_games):
#         if num_games > 4:
#             return 16.9
#         else:
#             return 16.9

#     def find_stack_only(self):
#         SlatePlayerProjection.objects.filter(
#             slate_player__slate=self.slate_player.slate,
#             slate_player__team=self.slate_player.team
#         ).update(stack_only=False)

#         # Get all WR/TE from team
#         pass_catchers = SlatePlayerProjection.objects.filter(
#             Q(slate_player__slate=self.slate_player.slate),
#             Q(slate_player__team=self.slate_player.team),
#             Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')
#         ).order_by('-projection')

#         for (index, pass_catcher) in enumerate(pass_catchers):
#             pass_catcher.find_in_play()

#             if not pass_catcher.in_play:
#                 pass_catcher.stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
#                 pass_catcher.in_play = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
#                 pass_catcher.qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
#                 pass_catcher.opp_qb_stack_only = index < 2 or abs(pass_catchers[1].projection - pass_catcher.projection) < 1.0
#             else:
#                 pass_catcher.stack_only = False
#                 pass_catcher.qb_stack_only = True
#                 pass_catcher.opp_qb_stack_only = True
                
#                 # if pass catcher is a TE and they are a bobo, block them from being in stacks with QB or opp QB (unless they are either the #2 option or within 1pt of the #2 option)
#                 # if pass_catcher.slate_player.site_pos == 'TE' and pass_catcher.projection <= 7.9 and index > 1 and abs(pass_catchers[1].projection - pass_catcher.projection) > 1.01:
#                 #     pass_catcher.qb_stack_only = True
#                 #     pass_catcher.opp_qb_stack_only = False
#                 # else:
#                 #     pass_catcher.qb_stack_only = True
#                 #     pass_catcher.opp_qb_stack_only = True

#             pass_catcher.save()


# class SlateBuildConfig(models.Model):
#     name = models.CharField(max_length=255)
#     site = models.CharField(max_length=50, choices=SITE_OPTIONS, default='fanduel')
#     game_stack_size = models.IntegerField(default=4)
#     num_players_vs_dst = models.IntegerField(default=0)
#     max_dst_exposure = models.DecimalField(decimal_places=2, max_digits=2, default=0.15)
#     allow_rbs_from_same_game = models.BooleanField(default=False)
#     allow_rb_qb_from_same_team = models.BooleanField(default=False)
#     allow_rb_qb_from_opp_team = models.BooleanField(default=False)
#     allow_dst_rb_stack = models.BooleanField(default=True)
#     randomness = models.DecimalField(decimal_places=2, max_digits=2, default=0.3)
#     use_similarity_scores = models.BooleanField(default=False)
#     use_iseo = models.BooleanField(default=True, help_text='When true, players within a stack are exposed proportional to their projection relative to total stack projection')
#     use_iseo_plus = models.BooleanField(default=True, help_text='When true, stacks will be pre-made and balanced such that the number of lineups for each stack is proportional to the stack projection relative to all stacks')
#     use_iseo_rbs = models.BooleanField(default=True, help_text='When true, rbs exposure will be balanced by using adjusted opportunity and running back groups')
#     uniques = models.IntegerField(default=1)
#     min_salary = models.IntegerField(default=59000)
#     allow_rb_as_flex = models.BooleanField(default=True)
#     allow_wr_as_flex = models.BooleanField(default=True)
#     allow_te_as_flex = models.BooleanField(default=False)
#     allow_rb_in_qb_stack = models.BooleanField(default=True)
#     allow_wr_in_qb_stack = models.BooleanField(default=True)
#     allow_te_in_qb_stack = models.BooleanField(default=True)
#     allow_rb_in_opp_qb_stack = models.BooleanField(default=True)
#     allow_wr_in_opp_qb_stack = models.BooleanField(default=True)
#     allow_te_in_opp_qb_stack = models.BooleanField(default=True)

#     class Meta:
#         verbose_name = 'Build Config'
#         verbose_name_plural = 'Build Configs'
#         ordering = ['id']
    
#     def __str__(self):
#         return '{}'.format(self.name)

#     @property
#     def flex_positions(self):
#         f_pos = []

#         if self.allow_rb_as_flex:
#             f_pos.append('RB')

#         if self.allow_wr_as_flex:
#             f_pos.append('WR')

#         if self.allow_te_as_flex:
#             f_pos.append('TE')
#         return f_pos

#     @property
#     def qb_stack_positions(self):
#         f_pos = []

#         if self.allow_rb_in_qb_stack:
#             f_pos.append('RB')

#         if self.allow_wr_in_qb_stack:
#             f_pos.append('WR')

#         if self.allow_te_in_qb_stack:
#             f_pos.append('TE')
#         return f_pos

#     @property
#     def opp_qb_stack_positions(self):
#         f_pos = []

#         if self.allow_rb_in_opp_qb_stack:
#             f_pos.append('RB')

#         if self.allow_wr_in_opp_qb_stack:
#             f_pos.append('WR')

#         if self.allow_te_in_opp_qb_stack:
#             f_pos.append('TE')
#         return f_pos


# class SlateBuild(models.Model):
#     slate = models.ForeignKey(Slate, related_name='builds', on_delete=models.CASCADE)
#     created = models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     used_in_contests = models.BooleanField(default=False, verbose_name='Used')
#     configuration = models.ForeignKey(SlateBuildConfig, related_name='builds', verbose_name='Config', on_delete=models.SET_NULL, null=True)
#     balance_rbs = models.BooleanField(default=False)
#     lineup_start_number = models.IntegerField(default=1)
#     top_score = models.DecimalField(verbose_name='top', decimal_places=2, max_digits=5, blank=True, null=True)
#     total_lineups = models.PositiveIntegerField(verbose_name='total')
#     total_cashes = models.PositiveIntegerField(verbose_name='cashes', blank=True, null=True)
#     total_one_pct = models.PositiveIntegerField(verbose_name='1%', blank=True, null=True)
#     total_half_pct = models.PositiveIntegerField(verbose_name='0.5%', blank=True, null=True)
#     great_build = models.BooleanField(verbose_name='gb', default=False)
#     binked = models.BooleanField(verbose_name='bink', help_text='Finished 1st, 2nd, or 3rd', default=False)
#     notes = models.TextField(blank=True, null=True)
#     tag = SingleTagField(force_lowercase=True, null=True, blank=True)

#     class Meta:
#         verbose_name = 'Slate Build'
#         verbose_name_plural = 'Slate Builds'

#     def __str__(self):
#         return '{} ({}) @ {}'.format(self.slate.name, self.configuration, self.created.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None).strftime('%Y-%m-%d %H:%M'))

#     def create_stacks(self):
#         if not self.configuration.use_iseo_plus:
#             raise Exception('Cannot pre-create stacks unless using ISEO+')

#         # Delete existing stacks for this build
#         SlateBuildStack.objects.filter(build=self).delete()

#         # get all qbs in play
#         qbs = self.slate.players.filter(site_pos='QB', projection__in_play=True)
#         total_qb_projection = qbs.aggregate(total_projection=Sum('projection__balanced_projection')).get('total_projection')
        
#         # for each qb, create all possible stacking configurations
#         for qb in qbs:
#             qb_lineup_count = round(qb.projection.balanced_projection/total_qb_projection * self.total_lineups)

#             print('Making stacks for {} {} lineups...'.format(qb_lineup_count, qb.name))
#             stack_players = self.slate.players.filter(
#                 Q(Q(site_pos__in=self.configuration.qb_stack_positions) | Q(site_pos__in=self.configuration.opp_qb_stack_positions))
#             ).filter(
#                 Q(Q(projection__qb_stack_only=True, team=qb.team) | Q(projection__opp_qb_stack_only=True, team=qb.get_opponent()))
#             )

#             # team_players includes all in-play players on same team as qb, including stack-only players
#             team_players = stack_players.filter(team=qb.team, site_pos__in=self.configuration.qb_stack_positions).order_by('-projection__balanced_projection')
#             # opp_players includes all in-play players on opposing team, including stack-only players that are allowed in opponent stack
#             opp_players = stack_players.filter(game=qb.game, site_pos__in=self.configuration.opp_qb_stack_positions).exclude(team=qb.team).order_by('-projection__balanced_projection')

#             am1_players = team_players.filter(
#                 Q(Q(projection__stack_only=True) | Q(projection__at_most_one_in_stack=True))
#             )
#             team_has_all_stack_only = (am1_players.count() == team_players.count())

#             if self.configuration.game_stack_size == 3:
#                 # For each player, loop over opposing player to make a group for each possible stack combination
#                 count = 0
#                 for (index, player) in enumerate(team_players):
#                     for opp_player in opp_players:
#                         count += 1
#                         stack = SlateBuildStack.objects.create(
#                             build=self,
#                             build_order=count,
#                             qb=qb.projection,
#                             player_1=player.projection,
#                             opp_player=opp_player.projection,
#                             salary=sum(p.salary for p in [qb, player, opp_player]),
#                             projection=sum(p.projection.balanced_projection for p in [qb, player, opp_player])
#                         )

#             elif self.configuration.game_stack_size == 4:
#                 count = 0
#                 # For each player, loop over opposing player to make a group for each possible stack combination
#                 for (index, player) in enumerate(team_players):
#                     if team_has_all_stack_only or not player.projection.stack_only:
#                         for (index2, player2) in enumerate(team_players[index+1:]):
#                             if player2 != player:  # don't include the pivot player
#                                 for opp_player in opp_players:
#                                     if player.site_pos == 'TE' and player2.site_pos == 'TE' and opp_player.site_pos == 'TE':  # You can't have stacks with 3 TEs
#                                         continue
#                                     elif player.projection.at_most_one_in_stack and player2.projection.at_most_one_in_stack:
#                                         continue  # You can't have stacks with 2 same team bobos
#                                     else:
#                                         count += 1
#                                         stack = SlateBuildStack.objects.create(
#                                             build=self,
#                                             build_order=count,
#                                             qb=qb.projection,
#                                             player_1=player.projection,
#                                             player_2=player2.projection,
#                                             opp_player=opp_player.projection,
#                                             salary=sum(p.salary for p in [qb, player, player2, opp_player]),
#                                             projection=sum(p.projection.balanced_projection for p in [qb, player, player2, opp_player])
#                                         )

#             total_stack_projection = SlateBuildStack.objects.filter(build=self, qb=qb.projection).aggregate(total_projection=Sum('projection')).get('total_projection')
#             for stack in SlateBuildStack.objects.filter(build=self, qb=qb.projection):
#                 print(stack, stack.projection/total_stack_projection, round(stack.projection/total_stack_projection * qb_lineup_count, 0))
#                 stack.count = round(stack.projection/total_stack_projection * qb_lineup_count, 0)
#                 stack.save()

#     def clean_stacks(self, num_stacks):
#         '''
#         Will remove all but {num_stacks} stacks, and then redistribute the removed lineups evenly
#         '''
#         ordered_stacks = self.stacks.all().order_by('-projection')[:num_stacks]

#         # delete stacks not in this queryset
#         self.stacks.exclude(id__in=list(ordered_stacks.values_list('id', flat=True))).update(count=0)

#         num_lineups_to_distribute = self.total_lineups - sum(s.count for s in ordered_stacks)
#         for stack in ordered_stacks:
#             stack.count += math.ceil(num_lineups_to_distribute/num_stacks)
#             stack.save()

#     def build(self):
#         self.lineups.all().delete()

#         if self.configuration.use_iseo_plus:
#             print('Building {} lineups; {} unique stacks...'.format(self.total_lineups, self.stacks.all().count()))
    
#             slate_players = self.slate.players.filter(projection__isnull=False)

#             last_qb = None
#             stacks = self.stacks.all().order_by('-qb__projection', 'qb__slate_player', 'build_order')
#             for (index2, stack) in enumerate(stacks):
#                 qb = stack.qb.id
#                 num_qb_stacks = self.stacks.filter(qb__id=qb).count()
#                 if last_qb is None or qb != last_qb:
#                     lineup_number = 1
#                 else:
#                     lineup_number += 1

#                 lineups = optimize.optimize_for_stack(
#                     self.slate.site,
#                     stack,
#                     slate_players,
#                     self.slate.teams,
#                     self.configuration,
#                     stack.count
#                 )

#                 for (index, lineup) in enumerate(lineups):
#                     SlateBuildLineup.objects.create(
#                         build=self,
#                         stack=stack,
#                         order_number=lineup_number + (num_qb_stacks * index),
#                         qb=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[0].id),
#                         rb1=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[1].id),
#                         rb2=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[2].id),
#                         wr1=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[3].id),
#                         wr2=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[4].id),
#                         wr3=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[5].id),
#                         te=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[6].id),
#                         flex=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[7].id),
#                         dst=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[8].id),
#                         salary=lineup.salary_costs,
#                         projection=lineup.fantasy_points_projection
#                     )

#                 stack.times_used = len(lineups)
#                 stack.save()

#                 last_qb = qb
#         else:
#             raise Exception('Cannot make lineups without iseo+')

#     def num_lineups_created(self):
#         return self.lineups.all().count()
#     num_lineups_created.short_description = 'created'
    
#     def num_stacks_created(self):
#         return self.stacks.all().count()

#     def get_actual_scores(self):
#         contest = self.slate.contests.all()[0]

#         top_score = 0
#         total_cashes = 0
#         total_one_pct = 0
#         total_half_pct = 0
#         binked = False
#         great_build = False

#         for stack in self.stacks.all():
#             stack.calc_actual_score()

#         for lineup in self.lineups.all():
#             score = lineup.calc_actual_score()
#             top_score = max(top_score, score)
#             if score >= contest.mincash_score:
#                 total_cashes += 1
#             if score >= contest.one_pct_score:
#                 total_one_pct += 1
#             if score >= contest.half_pct_score:
#                 total_half_pct += 1
#             if score >= contest.winning_score:
#                 binked = True
#             if score >= contest.great_score:
#                 great_build = True

#         self.top_score = top_score
#         self.total_cashes = total_cashes
#         self.total_one_pct = total_one_pct
#         self.total_half_pct = total_half_pct
#         self.great_build = great_build
#         self.binked = binked
#         self.save()

#     def num_actuals_created(self):
#         return self.actuals.all().count()

#     def get_exposure(self, slate_player):
#         return self.lineups.filter(
#             Q(
#                 Q(qb__slate_player__id=slate_player.id) | 
#                 Q(rb1__slate_player__id=slate_player.id) |
#                 Q(rb2__slate_player__id=slate_player.id) |
#                 Q(wr1__slate_player__id=slate_player.id) |
#                 Q(wr2__slate_player__id=slate_player.id) |
#                 Q(wr3__slate_player__id=slate_player.id) |
#                 Q(te__slate_player__id=slate_player.id) |
#                 Q(flex__slate_player__id=slate_player.id) |
#                 Q(dst__slate_player__id=slate_player.id)
#             )
#         ).count()

#     def build_optimals(self):
#         self.actuals.all().delete()

#         # First, find all stacks with at least 1 optimal lineup
#         stacks_with_optimals = []
#         for stack in self.stacks.all().order_by('-qb__projection', 'qb'):
#             has_possible_optimals = stack.has_possible_optimals()
#             print(stack, has_possible_optimals)
#             if has_possible_optimals:
#                 stacks_with_optimals.append(stack)
        
#         print('**********')
#         # Next, for each stack with optimals, make 100 optimal lineups
#         for stack in stacks_with_optimals:
#             print(stack)
#             num_lineups = 50
#             lineups = stack.build_optimals(num_lineups=num_lineups)
#             print('  built', len(lineups), 'lineups.')

#             # Store optimals in list until optimal threshold is reached
#             for lineup in lineups:
#                 if lineup.fantasy_points_projection < self.slate.get_great_score():
#                     break

#                 SlateBuildActualsLineup.objects.create(
#                     build=self,
#                     stack=stack,
#                     qb=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[0].id),
#                     rb1=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[1].id),
#                     rb2=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[2].id),
#                     wr1=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[3].id),
#                     wr2=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[4].id),
#                     wr3=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[5].id),
#                     te=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[6].id),
#                     flex=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[7].id),
#                     dst=SlatePlayerProjection.objects.get(slate_player__player_id=lineup.players[8].id),
#                     salary=lineup.salary_costs,
#                     actual=lineup.fantasy_points_projection
#                 )

#     def top_optimal_score(self):
#         return self.actuals.all().aggregate(top_score=Max('actual')).get('top_score')
#     top_optimal_score.short_description = 'Top Opt'


# class SlateBuildStack(models.Model):
#     build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='stacks', on_delete=models.CASCADE)
#     build_order = models.PositiveIntegerField(default=1)
#     rank = models.PositiveIntegerField(null=True, blank=True)
#     qb = models.ForeignKey(SlatePlayerProjection, related_name='qb_stacks', on_delete=models.CASCADE)
#     player_1 = models.ForeignKey(SlatePlayerProjection, related_name='p1_stacks', on_delete=models.CASCADE)
#     player_2 = models.ForeignKey(SlatePlayerProjection, related_name='p2_stacks', on_delete=models.CASCADE, blank=True, null=True)
#     opp_player = models.ForeignKey(SlatePlayerProjection, related_name='opp_stacks', on_delete=models.CASCADE)
#     salary = models.PositiveIntegerField()
#     projection = models.DecimalField(max_digits=5, decimal_places=2)
#     count = models.PositiveIntegerField(default=0, help_text='# of lineups in which this stack should appear')
#     times_used = models.PositiveIntegerField(default=0)
#     actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

#     class Meta:
#         verbose_name = 'Stack'
#         verbose_name_plural = 'Stacks'
#         ordering = ['-qb__projection', '-count', '-projection']
        
#     def __str__(self):
#         return '{} Stack {}'.format(self.qb.name, self.build_order)

#     @property
#     def players(self):
#         if self.player_2 is None:
#             return [
#                 self.qb, 
#                 self.player_1,
#                 self.opp_player
#             ]
#         else:
#             return [
#                 self.qb, 
#                 self.player_1,
#                 self.player_2,
#                 self.opp_player
#             ]

#     def contains_top_projected_pass_catcher(self):
#         pass_catchers = SlatePlayerProjection.objects.filter(
#             Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
#             slate_player__slate=self.build.slate,
#             slate_player__team=self.qb.slate_player.team
#         ).order_by('-projection')

#         if pass_catchers.count() > 0:
#             top_projection = pass_catchers[0].projection
#             top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

#             return self.player_1 in top_projected_players or self.player_2 in top_projected_players
#         return False
#     contains_top_projected_pass_catcher.short_description = '#1 PC?'
#     contains_top_projected_pass_catcher.boolean = True

#     def contains_slate_player(self, slate_player):
#         return self.qb.slate_player == slate_player or self.player_1.slate_player == slate_player or (self.player_2 is not None and self.player_2.slate_player == slate_player) or self.opp_player.slate_player == slate_player

#     def calc_salary(self):
#         slate_player_ids = [p.slate_player.id for p in self.players]
#         salary = sum(p.salary for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
#         self.salary = salary
#         self.save()

#         return salary        

#     def calc_projection(self):
#         slate_player_ids = [p.slate_player.id for p in self.players]
#         projection = sum(p.projection for p in SlatePlayerProjection.objects.filter(slate_player__id__in=slate_player_ids))
#         self.actual = projection
#         self.save()

#         return projection        

#     def calc_actual_score(self):
#         slate_player_ids = [p.slate_player.id for p in self.players]
#         score = sum(p.fantasy_points for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
#         self.actual = score
#         self.save()

#         return score                

#     def has_possible_optimals(self):
#         '''
#         Returns true if this stack can make at least 1 lineup in the top 1% of the milly
#         '''
#         lineups = self.build_optimals(1)
#         return len(lineups) > 0 and lineups[0].fantasy_points_projection  >= self.build.slate.get_great_score()

#     def build_optimals(self, num_lineups=1):    
#         slate_players = self.build.slate.players.filter(projection__isnull=False)

#         qb = self.qb.id

#         lineups = optimal.optimize_for_stack(
#             self.build.slate.site,
#             self,
#             slate_players,
#             self.build.slate.teams,
#             self.build.configuration,
#             num_lineups
#         )

#         return lineups

#     def num_tes(self):
#         count = 0
#         for p in self.players():
#             if p.slate_player.site_pos == 'TE':
#                 count += 1
#         return count


# class SlateBuildLineup(models.Model):
#     build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='lineups', on_delete=models.CASCADE)
#     stack = models.ForeignKey(SlateBuildStack, verbose_name='Stack', related_name='lineups', on_delete=models.CASCADE, null=True, blank=True)
#     order_number = models.IntegerField(default=0)
#     expected_lineup_order = models.PositiveIntegerField(default=0)
#     qb = models.ForeignKey(SlatePlayerProjection, related_name='qb', on_delete=models.CASCADE)
#     rb1 = models.ForeignKey(SlatePlayerProjection, related_name='rb1', on_delete=models.CASCADE)
#     rb2 = models.ForeignKey(SlatePlayerProjection, related_name='rb2', on_delete=models.CASCADE)
#     wr1 = models.ForeignKey(SlatePlayerProjection, related_name='wr1', on_delete=models.CASCADE)
#     wr2 = models.ForeignKey(SlatePlayerProjection, related_name='wr2', on_delete=models.CASCADE)
#     wr3 = models.ForeignKey(SlatePlayerProjection, related_name='wr3', on_delete=models.CASCADE)
#     te = models.ForeignKey(SlatePlayerProjection, related_name='te', on_delete=models.CASCADE)
#     flex = models.ForeignKey(SlatePlayerProjection, related_name='flex', on_delete=models.CASCADE)
#     dst = models.ForeignKey(SlatePlayerProjection, related_name='dst', on_delete=models.CASCADE)
#     salary = models.PositiveIntegerField()
#     projection = models.DecimalField(max_digits=5, decimal_places=2)
#     actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

#     class Meta:
#         verbose_name = 'Lineup'
#         verbose_name_plural = 'Lineups'
#         ordering = ['-actual', 'order_number', '-qb__projection']

#     @property
#     def players(self):
#         return [
#             self.qb, 
#             self.rb1,
#             self.rb2,
#             self.wr1,
#             self.wr2,
#             self.wr3,
#             self.te,
#             self.flex,
#             self.dst
#         ]

#     def contains_top_projected_pass_catcher(self):
#         pass_catchers = SlatePlayerProjection.objects.filter(
#             Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
#             slate_player__slate=self.build.slate,
#             slate_player__team=self.qb.slate_player.team
#         ).order_by('-projection')

#         if pass_catchers.count() > 0:
#             top_projection = pass_catchers[0].projection
#             top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]
#             print(top_projected_players)

#             return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
#         return False
#     contains_top_projected_pass_catcher.short_description = '#1 PC?'
#     contains_top_projected_pass_catcher.boolean = True

#     def get_num_rbs(self):
#         if self.flex.slate_player.site_pos == 'RB':
#             return 3
#         return 2

#     def get_num_wrs(self):
#         if self.flex.slate_player.site_pos == 'WR':
#             return 4
#         return 3

#     def get_num_tes(self):
#         if self.flex.slate_player.site_pos == 'TE':
#             return 2
#         return 1

#     def get_rbs(self):
#         rbs = [self.rb1, self.rb2]
#         if self.get_num_rbs() > 2:
#             rbs.append(self.flex)
#         return rbs

#     def get_rbs_by_salary(self):
#         rbs = self.get_rbs()       
#         rbs.sort(key=lambda p: p.slate_player.salary, reverse=True)
#         return rbs

#     def get_wrs(self):
#         wrs = [self.wr1, self.wr2, self.wr3]
#         if self.get_num_wrs() > 3:
#             wrs.append(self.flex)        
#         return wrs

#     def get_wrs_by_salary(self):
#         wrs = self.get_wrs()
#         wrs.sort(key=lambda p: p.slate_player.salary, reverse=True)
#         return wrs

#     def get_tes(self):
#         tes = [self.te]
#         if self.get_num_tes() > 1:
#             tes.append(self.flex)
#         return tes

#     def get_tes_by_salary(self):
#         tes = self.get_tes()
#         tes.sort(key=lambda  p: p.slate_player.salary, reverse=True)
#         return tes
        
#     def calc_actual_score(self):
#         slate_player_ids = [p.slate_player.id for p in self.players]
#         for p in SlatePlayer.objects.filter(id__in=slate_player_ids):
#             print(p)
#         score = sum(p.fantasy_points for p in SlatePlayer.objects.filter(id__in=slate_player_ids))
#         self.actual = score
#         self.save()

#         return score        


# class SlateBuildActualsLineup(models.Model):
#     build = models.ForeignKey(SlateBuild, verbose_name='Build', related_name='actuals', on_delete=models.CASCADE)
#     stack = models.ForeignKey(SlateBuildStack, verbose_name='Stack', related_name='actuals', on_delete=models.CASCADE, null=True, blank=True)
#     expected_lineup_order = models.PositiveIntegerField(default=0)
#     qb = models.ForeignKey(SlatePlayerProjection, related_name='actuals_qb', on_delete=models.CASCADE)
#     rb1 = models.ForeignKey(SlatePlayerProjection, related_name='actuals_rb1', on_delete=models.CASCADE)
#     rb2 = models.ForeignKey(SlatePlayerProjection, related_name='actuals_rb2', on_delete=models.CASCADE)
#     wr1 = models.ForeignKey(SlatePlayerProjection, related_name='actuals_wr1', on_delete=models.CASCADE)
#     wr2 = models.ForeignKey(SlatePlayerProjection, related_name='actuals_wr2', on_delete=models.CASCADE)
#     wr3 = models.ForeignKey(SlatePlayerProjection, related_name='actuals_wr3', on_delete=models.CASCADE)
#     te = models.ForeignKey(SlatePlayerProjection, related_name='actuals_te', on_delete=models.CASCADE)
#     flex = models.ForeignKey(SlatePlayerProjection, related_name='actuals_flex', on_delete=models.CASCADE)
#     dst = models.ForeignKey(SlatePlayerProjection, related_name='actuals_dst', on_delete=models.CASCADE)
#     salary = models.PositiveIntegerField()
#     actual = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

#     class Meta:
#         verbose_name = 'Actuals Lineup'
#         verbose_name_plural = 'Actuals Lineups'
#         ordering = ['-actual', '-qb__projection']

#     @property
#     def players(self):
#         return [
#             self.qb, 
#             self.rb1,
#             self.rb2,
#             self.wr1,
#             self.wr2,
#             self.wr3,
#             self.te,
#             self.flex,
#             self.dst
#         ]

#     def contains_top_projected_pass_catcher(self):
#         pass_catchers = SlatePlayerProjection.objects.filter(
#             Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
#             slate_player__slate=self.build.slate,
#             slate_player__team=self.qb.slate_player.team
#         ).order_by('-projection')

#         if pass_catchers.count() > 0:
#             top_projection = pass_catchers[0].projection
#             top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

#             return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
#         return False
#     contains_top_projected_pass_catcher.short_description = '#1 PC?'
#     contains_top_projected_pass_catcher.boolean = True

#     def contains_opp_top_projected_pass_catcher(self):
#         pass_catchers = SlatePlayerProjection.objects.filter(
#             Q(Q(slate_player__site_pos='WR') | Q(slate_player__site_pos='TE')),
#             slate_player__slate=self.build.slate,
#             slate_player__team=self.qb.slate_player.get_opponent()
#         ).order_by('-projection')

#         if pass_catchers.count() > 0:
#             top_projection = pass_catchers[0].projection
#             top_projected_players = [p for p in pass_catchers if top_projection - p.projection <= 2.0]

#             return self.wr1 in top_projected_players or self.wr2 in top_projected_players or self.wr3 in top_projected_players or self.te in top_projected_players or self.flex in top_projected_players
#         return False
#     contains_opp_top_projected_pass_catcher.short_description = '#1 OPP PC?'
#     contains_opp_top_projected_pass_catcher.boolean = True

#     def get_num_rbs(self):
#         if self.flex.slate_player.site_pos == 'RB':
#             return 3
#         return 2

#     def get_num_wrs(self):
#         if self.flex.slate_player.site_pos == 'WR':
#             return 4
#         return 3

#     def get_num_tes(self):
#         if self.flex.slate_player.site_pos == 'TE':
#             return 2
#         return 1

#     def get_rbs_by_salary(self):
#         rbs = [self.rb1, self.rb2]
#         if self.get_num_rbs() > 2:
#             rbs.append(self.flex)
        
#         rbs.sort(key=lambda p: p.slate_player.salary, reverse=True)
#         return rbs

#     def get_wrs_by_salary(self):
#         wrs = [self.wr1, self.wr2, self.wr3]
#         if self.get_num_wrs() > 3:
#             wrs.append(self.flex)
        
#         wrs.sort(key=lambda p: p.slate_player.salary, reverse=True)
#         return wrs

#     def get_tes_by_salary(self):
#         tes = [self.te]
#         if self.get_num_tes() > 1:
#             tes.append(self.flex)
        
#         tes.sort(key=lambda  p: p.slate_player.salary, reverse=True)
#         return tes


# @receiver(post_save, sender=SlateProjectionSheet)
# def process_projection_sheet(sender, instance, **kwargs):
#     SlatePlayerProjection.objects.filter(slate_player__slate=instance.slate).update(projection=0.0, in_play=False, stack_only=False)

#     if instance.slate.site == 'fanduel':
#         process_fanduel_projection_sheet(instance)
#         # for projection in SlatePlayerProjection.objects.filter(slate_player__site_pos='D'):
#         #     projection.find_stack_only()
#     elif instance.slate.site == 'draftkings':
#         process_draftkings_projection_sheet(instance)
#         # for projection in SlatePlayerProjection.objects.filter(slate_player__site_pos='DST'):
#         #     projection.find_stack_only()
#     else:
#         raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))
    
#     # instance.slate.group_rbs()
#     # instance.slate.balance_rb_exposures()


# def process_fanduel_projection_sheet(instance):
#     with open(instance.projection_sheet.url, mode='r') as projection_file:
#         csv_reader = csv.reader(projection_file, delimiter=',')
#         row_count = 0
#         missing_players = []

#         for row in csv_reader:
#             if row_count > 0:
#                 player_name= row[3].replace('Oakland', 'Las Vegas').replace('Washington Redskins', 'Washington Football Team')
#                 alias = None

#                 if player_name == '#N/A':
#                     continue
#                 try:
#                     alias = Alias.objects.get(four4four_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(fd_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(fc_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
             
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             slate=instance.slate,
#                             name__in=[alias.fc_name, alias.tda_name, alias.fd_name, alias.four4four_name, alias.awesemo_name],
#                             team='JAC' if row[5] == 'JAX' else row[5]
#                         )

#                         print('Found {} on slate.'.format(slate_player), row[40])
#                         if row[40] != '':
#                             try:
#                                 projection = SlatePlayerProjection.objects.get(
#                                     slate_player=slate_player
#                                 )
#                                 projection.projection=float(row[40])
#                                 projection.balanced_projection=float(row[40]) #if slate_player.site_pos != 'RB' else projection.balanced_projection
#                                 projection.adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0
#                                 projection.save()
#                             except SlatePlayerProjection.DoesNotExist:
#                                 try:
#                                     projection = SlatePlayerProjection.objects.create(
#                                         slate_player=slate_player,
#                                         projection=float(row[40]),
#                                         balanced_projection=float(row[40]),
#                                         adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0,
#                                         in_play=False,
#                                         stack_only=False
#                                     )
#                                 except:
#                                     traceback.print_exc()
                            
#                             # projection.find_in_play()
#                     except SlatePlayer.DoesNotExist:
#                         print('{} is not on slate.'.format(player_name))
#             row_count += 1

#         if len(missing_players) > 0:
#             print()
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)


# def process_draftkings_projection_sheet(instance):
#     with open(instance.projection_sheet.url, mode='r') as projection_file:
#         csv_reader = csv.reader(projection_file, delimiter=',')
#         row_count = 0
#         missing_players = []

#         for row in csv_reader:
#             if row_count > 0:
#                 player_name= row[3].replace('Oakland', 'Las Vegas').replace('Washington Redskins', 'Washington Football Team')
#                 alias = None

#                 if player_name == '#N/A':
#                     continue
#                 try:
#                     alias = Alias.objects.get(four4four_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(dk_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(fc_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
             
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             slate=instance.slate,
#                             name__in=[alias.fc_name, alias.tda_name, alias.dk_name, alias.four4four_name, alias.awesemo_name],
#                             team='JAC' if row[5] == 'JAX' else row[5]
#                         )

#                         in_play = True
#                         stack_only = False

#                         if row[28] != '':
#                             try:
#                                 projection = SlatePlayerProjection.objects.get(
#                                     slate_player=slate_player
#                                 )
#                                 projection.projection=float(row[28])
#                                 projection.balanced_projection=float(row[28]) #if slate_player.site_pos != 'RB' else projection.balanced_projection
#                                 projection.adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0
#                                 projection.game_total=float(row[63])
#                                 projection.team_total=float(row[65])
#                                 projection.spread=float(row[64])
#                                 projection.save()
#                             except SlatePlayerProjection.DoesNotExist:
#                                 projection = SlatePlayerProjection.objects.create(
#                                     slate_player=slate_player,
#                                     projection=float(row[28]),
#                                     balanced_projection=float(row[28]),
#                                     adjusted_opportunity=float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0,
#                                     game_total=float(row[63]),
#                                     team_total=float(row[65]),
#                                     spread=float(row[64]),
#                                     in_play=False,
#                                     stack_only=False
#                                 )
                            
#                             # projection.find_in_play()
#                             print(player_name, float(row[18])*2.0+float(row[15]) if slate_player.site_pos == 'RB' else 0.0)
#                     except:
#                         pass
#             row_count += 1

#         if len(missing_players) > 0:
#             print()
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)


# @receiver(post_save, sender=SlatePlayerImportSheet)
# def process_slate_player_sheet(sender, instance, **kwargs):
#     if instance.sheet_type == 'site':
#         if instance.slate.site == 'fanduel':
#             process_fanduel_slate_player_sheet(instance)
#         elif instance.slate.site == 'draftkings':
#             process_draftkings_slate_player_sheet(instance)
#         else:
#             raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))
#     elif instance.sheet_type == 'fantasycruncher':
#         process_fantasycruncher_slate_player_sheet(instance)
#     else:
#         raise Exception('{} is nto a valid sheet type.'.format(instance.sheet_type))


# def process_fanduel_slate_player_sheet(instance):
#     with open(instance.sheet.url, mode='r') as actuals_file:
#         csv_reader = csv.reader(actuals_file, delimiter=',')
#         row_count = 0
#         missing_players = []

#         for row in csv_reader:
#             if row_count > 0:
#                 player_id = row[0]
#                 site_pos = row[1]
#                 player_name = row[3].replace('Oakland Raiders', 'Las Vegas Raiders').replace('Washington Redskins', 'Washington Football Team')
#                 salary = row[7]
#                 game = row[8].replace('@', '_').replace('JAX', 'JAC')
#                 team = row[9]

#                 alias = None

#                 try:
#                     alias = Alias.objects.get(fd_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(tda_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(four4four_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
                
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             name=alias.fd_name,
#                             team=team
#                         )
#                     except SlatePlayer.DoesNotExist:
#                         slate_player = SlatePlayer(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             team=team,
#                             name=player_name
#                         )

#                     slate_player.salary = salary
#                     slate_player.site_pos = site_pos
#                     slate_player.game = game
#                     slate_player.save()
                    
#                     print(slate_player)
#             row_count += 1

#         if len(missing_players) > 0:
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)


# def process_draftkings_slate_player_sheet(instance):
#     with open(instance.sheet.url, mode='r') as actuals_file:
#         csv_reader = csv.reader(actuals_file, delimiter=',')
#         row_count = 0
#         missing_players = []

#         for row in csv_reader:
#             if row_count > 7:
#                 player_id = row[13]
#                 site_pos = row[10]
#                 player_name = row[12].strip()
#                 salary = row[15]
#                 game = row[16].replace('@', '_').replace('JAX', 'JAC')
#                 game = game[:game.find(' ')]
#                 team = 'JAC' if row[17] == 'JAX' else row[17]

#                 alias = None

#                 try:
#                     alias = Alias.objects.get(dk_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(tda_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(four4four_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
                
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             name=alias.dk_name,
#                             team=team
#                         )
#                     except SlatePlayer.DoesNotExist:
#                         slate_player = SlatePlayer(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             team=team,
#                             name=player_name
#                         )

#                     slate_player.salary = salary
#                     slate_player.site_pos = site_pos
#                     slate_player.game = game
#                     slate_player.save()
                    
#                     print(slate_player)
#             row_count += 1

#         if len(missing_players) > 0:
#             print()
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)


# def process_fantasycruncher_slate_player_sheet(instance):
#     with open(instance.sheet.url, mode='r') as actuals_file:
#         csv_reader = csv.reader(actuals_file, delimiter=',')
#         row_count = 0
#         missing_players = []

#         for row in csv_reader:
#             if row_count > 0:
#                 player_id = uuid.uuid4()
#                 site_pos = row[1]
#                 player_name = row[0].replace('Redskins', 'Washington Football Team')
#                 salary = row[6]
#                 game = '{}_{}'.format(row[2].replace('JAX', 'JAC'), row[3].replace('@ ', '').replace('JAX', 'JAC')) if '@' in row[3] else '{}_{}'.format(row[3].replace('vs ', '').replace('JAX', 'JAC'), row[2].replace('JAX', 'JAC'))
#                 team = row[2]

#                 alias = None

#                 try:
#                     alias = Alias.objects.get(fc_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(tda_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(four4four_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
                
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             name=alias.fd_name if instance.slate.site == 'fanduel' else alias.dk_name,
#                             team=team
#                         )
#                     except SlatePlayer.DoesNotExist:
#                         slate_player = SlatePlayer(
#                             player_id=player_id,
#                             slate=instance.slate,
#                             team=team,
#                             name=alias.fd_name if instance.slate.site == 'fanduel' else alias.dk_name
#                         )

#                     slate_player.salary = salary
#                     slate_player.site_pos = site_pos
#                     slate_player.game = game
#                     slate_player.save()
                    
#                     print(slate_player)
#             row_count += 1

#         if len(missing_players) > 0:
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)


# @receiver(post_save, sender=SlatePlayerActualsSheet)
# def process_slate_player_actuals_sheet(sender, instance, **kwargs):
#     if instance.slate.site == 'fanduel':
#         process_fanduel_slate_player_actuals_sheet(instance)
#     elif instance.slate.site == 'draftkings':
#         process_draftkings_slate_player_actuals_sheet(instance)
#     else:
#         raise Exception('{} is not a supported dfs site.'.format(instance.slate.site))


# def process_fanduel_slate_player_actuals_sheet(instance):
#     with open(instance.sheet.url, mode='r') as actuals_file:
#         csv_reader = csv.reader(actuals_file, delimiter=',')
#         row_count = 0

#         failed_rows = []
#         missing_players = []
#         for row in csv_reader:
#             if row_count > 0:
#                 player_name = row[0].replace('Redskins', 'Washington Football Team')
#                 print(player_name, row[22])

#                 try:
#                     alias = Alias.objects.get(fc_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(fd_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(four4four_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
                
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             slate=instance.slate,
#                             name=alias.fd_name,
#                             team=row[2]
#                         )

#                         if row[12] is not None and row[12] != '':
#                             ownership = float(row[12].replace('%', ''))
#                         else:
#                             ownership = None

#                         slate_player.fantasy_points = float(row[22]) if row[22] is not None and row[22] != '' else 0.0
#                         slate_player.ownership = ownership
#                         slate_player.save()
#                     except SlatePlayer.DoesNotExist:
#                         failed_rows.append(row)
                    
#             row_count += 1

#         print()
#         if len(missing_players) > 0:
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)
#         if len(failed_rows) > 0:
#             print('Failed rows:')
#             for r in failed_rows:
#                 print(r)   


# def process_draftkings_slate_player_actuals_sheet(instance):
#     with open(instance.sheet.url, mode='r') as actuals_file:
#         csv_reader = csv.reader(actuals_file, delimiter=',')
#         row_count = 0

#         failed_rows = []
#         missing_players = []
#         for row in csv_reader:
#             if row_count > 0:
#                 player_name = row[0]
#                 print(player_name, row[22])

#                 try:
#                     alias = Alias.objects.get(fc_name=player_name)
#                 except Alias.DoesNotExist:
#                     try:
#                         alias = Alias.objects.get(dk_name=player_name)
#                     except Alias.DoesNotExist:
#                         try:
#                             alias = Alias.objects.get(four4four_name=player_name)
#                         except Alias.DoesNotExist:
#                             missing_players.append(player_name)
                
#                 if alias is not None:
#                     try:
#                         slate_player = SlatePlayer.objects.get(
#                             slate=instance.slate,
#                             name__in=[alias.dk_name, alias.tda_name, alias.fc_name, alias.four4four_name, alias.awesemo_name],
#                             team=row[2]
#                         )

#                         if row[12] is not None and row[12] != '':
#                             ownership = float(row[12].replace('%', ''))
#                         else:
#                             ownership = None

#                         slate_player.fantasy_points = float(row[22]) if row[22] is not None and row[22] != '' else 0.0
#                         slate_player.ownership = ownership
#                         slate_player.save()
#                     except SlatePlayer.DoesNotExist:
#                         failed_rows.append(row)
                    
#             row_count += 1

#         print()
#         if len(missing_players) > 0:
#             print('Missing players:')
#             for p in missing_players:
#                 print(p)
#         if len(failed_rows) > 0:
#             print('Failed rows:')
#             for r in failed_rows:
#                 print(r)   


# @receiver(post_save, sender=ContestImportSheet)
# def process_contest_sheet(sender, instance, **kwargs):
#     with open(instance.sheet.url, mode='r') as f:
#         csv_reader = csv.reader(f, delimiter=',')
#         row_count = 0

#         for row in csv_reader:
#             if row_count > 0:
#                 try:
#                     site = 'DK' if instance.site == 'draftkings' else 'FanDuel'
#                     week = int(row[1].replace(',', ''))
#                     slate_type = row[2]
#                     dt = datetime.datetime.strptime('{} {}'.format(row[3], row[4]), '%m/%d/%Y %H:%M')
#                     num_games = int(row[5].replace(',', ''))
#                     name = row[6]
#                     cost = float(row[7].replace('$', '').replace(',', ''))
#                     prize_pool = float(row[8].replace('$', '').replace(',', ''))
#                     max_entries = int(row[9].replace(',', ''))
#                     max_entrants = int(row[10].replace(',', ''))
#                     total_entrants = int(row[11].replace(',', ''))
#                     winning_score = float(row[13].replace('$', '').replace(',', ''))
#                     top_payout = float(row[14].replace('$', '').replace(',', ''))
#                     min_cash_score = float(row[15].replace('$', '').replace(',', ''))
#                     min_cash_payout = float(row[16].replace('$', '').replace(',', ''))
#                     places_paid = int(row[17].replace(',', ''))
#                     one_pct_rank = int(row[18].replace(',', ''))
#                     one_pct_score = float(row[19].replace('$', '').replace(',', ''))
#                     half_pct_rank = int(row[20].replace(',', ''))
#                     half_pct_score = float(row[21].replace('$', '').replace(',', ''))

#                     # get or create slate
#                     try:
#                         slate = Slate.objects.get(
#                             datetime=dt,
#                             week=week,
#                             site=instance.site,
#                             is_main_slate=slate_type.lower()=='main'
#                         )
#                     except Slate.DoesNotExist:
#                         slate = Slate.objects.create(
#                             datetime=dt,
#                             name='{}-{}-{}-{}'.format(row[0][2:], site, str(week).zfill(2), slate_type),
#                             week=week,
#                             site=instance.site,
#                             num_games=num_games,
#                             is_main_slate=slate_type.lower()=='main'
#                         )

#                     print(slate)
#                     try:
#                         contest = Contest.objects.get(
#                             slate=slate
#                         )

#                         contest.name = name
#                         contest.num_games = num_games
#                         contest.cost = cost
#                         contest.max_entrants = max_entrants
#                         contest.max_entries = max_entries
#                         contest.mincash_payout = min_cash_payout
#                         contest.mincash_score = min_cash_score
#                         contest.places_paid = places_paid
#                         contest.prize_pool = prize_pool
#                         contest.start_date = 0
#                         contest.total_entrants = total_entrants
#                         contest.winning_payout = top_payout
#                         contest.winning_score = winning_score
#                         contest.url = None
#                         contest.one_pct_score = one_pct_score
#                         contest.one_pct_rank = one_pct_rank
#                         contest.half_pct_score = half_pct_score
#                         contest.half_pct_rank = half_pct_rank
#                         contest.save()
#                     except Contest.DoesNotExist:
#                         contest = Contest.objects.create(
#                             slate=slate,
#                             name=name,
#                             num_games=num_games,
#                             cost=cost,
#                             max_entrants=max_entrants,
#                             max_entries=max_entries,
#                             mincash_payout=min_cash_payout,
#                             mincash_score=min_cash_score,
#                             places_paid=places_paid,
#                             prize_pool=prize_pool,
#                             start_date=0,
#                             total_entrants=total_entrants,
#                             winning_payout=top_payout,
#                             winning_score=winning_score,
#                             url=None,
#                             one_pct_score=one_pct_score,
#                             one_pct_rank=one_pct_rank,
#                             half_pct_score=half_pct_score,
#                             half_pct_rank=half_pct_rank
#                         )
                    
#                     print(contest)
#                 except:
#                     traceback.print_exc()
#                     break
#             row_count += 1
