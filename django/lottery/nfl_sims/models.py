import pandas

from django.db import models


SIM_TYPES = (
    ('rts', 'Run The Sims'),
    ('ben', 'Ben'),
    ('greatleaf', 'GreatLeaf'),
)


class Player(models.Model):
    draftkings_name = models.CharField(max_length=100, null=True, blank=True)
    fanduel_name = models.CharField(max_length=100, null=True, blank=True)
    yahoo_name = models.CharField(max_length=100, null=True, blank=True)
    draftkings_player_id = models.CharField(max_length=255, null=True, blank=True)
    fanduel_player_id = models.CharField(max_length=255, null=True, blank=True)
    yahoo_player_id = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        if self.draftkings_name is not None:
            return f'{self.draftkings_name}'
        elif self.fanduel_name is not None:
            return f'{self.fanduel_name}'
        else:
            return f'{self.yahoo_name}'


class Simulation(models.Model):
    week_num = models.PositiveIntegerField('Week #', default=1)
    slate_year = models.PositiveIntegerField(default=2021)
    sim_type = models.CharField(max_length=15, choices=SIM_TYPES, default='rts')
    player_outcomes = models.FileField(upload_to='uploads/sims', blank=True, null=True)

    class Meta:
        ordering = ['-slate_year', '-week_num']

    def __str__(self):
        return f'Simulation for week {self.week_num} {self.slate_year}'

    def get_player_outcomes(self, draftkings_player_id=None, fanduel_player_id=None, yahoo_player_id=None):
        df_outcomes = pandas.read_csv(self.player_outcomes.path)
        print(df_outcomes)