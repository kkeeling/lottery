import numpy

from statistics import mean

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Avg
from django.utils.html import format_html
from django.urls import reverse_lazy


class Contest(models.Model):
    cost = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    name = models.CharField(max_length=255, blank=True, null=True)
    num_entries = models.PositiveIntegerField(default=0)
    entries_file = models.FileField(upload_to='uploads/entries', blank=True, null=True)
    prizes_file = models.FileField(upload_to='uploads/prizes', blank=True, null=True)
    sim_file = models.FileField(upload_to='uploads/sims', blank=True, null=True)

    num_iterations = models.IntegerField(default=0)

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


class ContestEntryPlayer(models.Model):
    contest = models.ForeignKey(Contest, related_name='player', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    scores = ArrayField(models.FloatField(), null=True, blank=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Player'
        verbose_name_plural = 'Players'


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, related_name='entries', on_delete=models.CASCADE)
    entry_id = models.CharField(max_length=50)
    entry_name = models.CharField(max_length=255, blank=True, null=True)
    lineup_str = models.TextField(blank=True, null=True)
    player_1 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_1', on_delete=models.CASCADE)
    player_2 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_2', on_delete=models.CASCADE, null=True, blank=True)
    player_3 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_3', on_delete=models.CASCADE, null=True, blank=True)
    player_4 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_4', on_delete=models.CASCADE, null=True, blank=True)
    player_5 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_5', on_delete=models.CASCADE, null=True, blank=True)
    player_6 = models.ForeignKey(ContestEntryPlayer, related_name='contest_entry_as_player_6', on_delete=models.CASCADE, null=True, blank=True)
    sim_scores = ArrayField(models.FloatField(), null=True, blank=True)

    def __str__(self):
        return f'{self.entry_name}'

    class Meta:
        verbose_name_plural = 'Contest Entries'

    @property
    def players(self):
        l = [
            self.player_1
        ]

        if self.player_2 is not None:
            l.append(self.player_2)
        if self.player_3 is not None:
            l.append(self.player_3)
        if self.player_4 is not None:
            l.append(self.player_4)
        if self.player_5 is not None:
            l.append(self.player_5)
        if self.player_6 is not None:
            l.append(self.player_6)

        return l

    def simulate(self):
        players = self.players
        total_result = None

        for p in players:
            if total_result is None:
                total_result = numpy.array(p.scores, dtype=float)
            else:
                total_result += numpy.array(p.scores, dtype=float)
        self.sim_scores = total_result.tolist()
        self.save()


class ContestBacktest(models.Model):
    contest = models.ForeignKey(Contest, related_name='backtests', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.contest} Backtest'

    def run_button(self):
        return format_html('<a href="{}" class="link" style="color: #ffffff; background-color: #30bf48; font-weight: bold; padding: 10px 15px;">Run</a>',
            reverse_lazy("admin:admin_backtest_run", args=[self.pk])
        )
    run_button.short_description = ''


class ContestBacktestEntry(models.Model):
    entry = models.ForeignKey(ContestEntry, related_name='backtest_outcomes', on_delete=models.CASCADE)
    backtest = models.ForeignKey(ContestBacktest, related_name='entry_outcomes', on_delete=models.CASCADE)
    amount_won = models.FloatField(default=0.0)
    roi = models.FloatField(default=0.0)

    def __str__(self):
        return f'{self.entry} for {self.backtest}'
