import json
from django.db import models

GET_CONTEST_HEADERS = {
}


GET_ENTRIES_HEADERS = {
}


GET_LINEUP_HEADERS = {
}


class Contest(models.Model):
    contest_id = models.CharField(max_length=64)
    slate_week = models.PositiveIntegerField('Week #', default=0)
    slate_year = models.PositiveIntegerField(default=0)
    is_main_slate = models.BooleanField(default=True)
    cost = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    name = models.CharField(max_length=255, blank=True, null=True)
    num_entries = models.PositiveIntegerField(default=0)
    contest_json = models.TextField(blank=True, null=True)
    last_page_processed = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.name}'

    @property
    def url(self):
        return f'https://dfyql-ro.sports.yahoo.com/v2/contest/{self.contest_id}?lang=en-US&region=US&device=desktop'

    def entries_url(self, for_page=0):
        return f'https://dfyql-ro.sports.yahoo.com/v2/contestEntries?lang=en-US&region=US&device=desktop&sort=rank&contestId={self.contest_id}&start={(for_page)*50}&limit=50'

    def get_payout(self, rank):
        try:
            prize = self.prizes.get(min_rank__lte=rank, max_rank__gte=rank)
            return prize.prize
        except ContestPrize.DoesNotExist:
            return 0.0

    def get_lineups_as_json(self):
        entries = []

        for entry in self.entries.all().iterator():
            if entry.entry_json is None:
                print(f'Entry {entry.username} has no lineup data.')
                continue

            raw_json = json.loads(entry.entry_json)
            if len(raw_json) > 0:
                entry_dict = {
                    'username': entry.username
                }
                
                pos_count = 1
                for lineup_player in raw_json:
                    pos = lineup_player.get('lineupSlot').get('abbr')

                    if pos == 'FLEX':
                        entry_dict['flex_pos'] = lineup_player.get('player').get('primaryPosition')

                    lineup_pos = pos
                    if 'player' in lineup_player:
                        player_id = lineup_player.get('player').get('playerGameCode')
                        while lineup_pos in entry_dict:
                            pos_count += 1
                            lineup_pos = f'{pos}{pos_count}'
                        entry_dict[lineup_pos] = player_id
                        pos_count = 1
                    else:
                        print(f'No player field found.')
                        print(lineup_player)
                        entry_dict = None
                        continue
                if entry_dict is not None:
                    entries.append(entry_dict)
        return entries


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, related_name='entries', on_delete=models.CASCADE)
    entry_id = models.CharField(max_length=50)
    username = models.CharField(max_length=255, blank=True, null=True)
    entry_json = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.username}'

    @property
    def entry_url(self):
        return f'https://dfyql-ro.sports.yahoo.com/v2/contestEntry/{self.entry_id}?lang=en-US&region=US&device=desktop&slateTypes=SINGLE_GAME&slateTypes=MULTI_GAME'


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
