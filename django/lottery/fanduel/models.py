from django.db import models

GET_CONTEST_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': '',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc1MzY4NzgwMCwic3ViIjoxNzAyNTA4OCwidXNuIjoiY29kbWNjb2RmaXNoIiwicHJkIjoiREZTIiwiY3J0IjoxNjM3NDEyNDM1LCJlbWwiOiJ2aW9sZW50Y29kQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2Mzc2MzI0Njh9.e61kVCC8zbEVAPijH0J-qRif-Yj0rus7KmHVLWe17vmaJaDt7_86HVMWB4aMqY3dFX0Y2WUDPMww6R9-oDnU_TWW3r7ABZtfCatZ-iZlW7GtPvX1ev2lmV_r1rAAzUqbRh8G012iwVhdntWAQk5-TmsW8yixSBE0A3uWowKD38XPpfLUmJoELgHCj4PDJYTYTEmaZDYTKGRtRNnzZbKf7BnKxmT8COeZqgt2rImezN2hdocvdWKWxv6NZQEbYlCjBWJerMoxlAoE52tTrmrUP0E78CkGPflgR3Bl_gN0MCQu-yk6PrY2weizJ6rH4O5t_aktCxFu2zYuQ1HVFRvxZA',
    'authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'x-brand': 'FANDUEL',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
    'x-currency': 'USD',
    'sec-gpc': '1',
    'origin': 'https://www.fanduel.com',
    'sec-fetch-site': 'same-site',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://www.fanduel.com/',
    'accept-language': 'en-US,en;q=0.9',
}


GET_ENTRIES_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': '',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc1MzY4NzgwMCwic3ViIjoxNzAyNTA4OCwidXNuIjoiY29kbWNjb2RmaXNoIiwicHJkIjoiREZTIiwiY3J0IjoxNjM3NDEyNDM1LCJlbWwiOiJ2aW9sZW50Y29kQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2Mzc2MzI0Njh9.e61kVCC8zbEVAPijH0J-qRif-Yj0rus7KmHVLWe17vmaJaDt7_86HVMWB4aMqY3dFX0Y2WUDPMww6R9-oDnU_TWW3r7ABZtfCatZ-iZlW7GtPvX1ev2lmV_r1rAAzUqbRh8G012iwVhdntWAQk5-TmsW8yixSBE0A3uWowKD38XPpfLUmJoELgHCj4PDJYTYTEmaZDYTKGRtRNnzZbKf7BnKxmT8COeZqgt2rImezN2hdocvdWKWxv6NZQEbYlCjBWJerMoxlAoE52tTrmrUP0E78CkGPflgR3Bl_gN0MCQu-yk6PrY2weizJ6rH4O5t_aktCxFu2zYuQ1HVFRvxZA',
    'authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'x-brand': 'FANDUEL',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
    'x-currency': 'USD',
    'sec-gpc': '1',
    'origin': 'https://www.fanduel.com',
    'sec-fetch-site': 'same-site',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://www.fanduel.com/',
    'accept-language': 'en-US,en;q=0.9',
}


GET_LINEUP_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiN2ZkMWVhNDkwMWY5NjNkOSIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMjJUMTM6NTU6MDEuMTc3WiIsInVzZXJfaWQiOiIxNzAyNTA4OCIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxNTQuNi4yOC4yMTMiLCJzZXNzaW9uX2lkIjo3NTM2ODc4MDAsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.UtkvyVBsgXDpUyNeyXAGl6ODtM-wXoKAhgQ5aNJrtKXUdiIjP6LvWdibo9IjqKS4tw5M2GZ4WUkoqy62qxypdCgBcZQjRn4vShXxnj98eTL2jc_PUfL21geCZNZw07rlx3EwgTb_T9MoWKQVG9xpAJsKWzbqCIL86CcpYUwqQD5tD6XP4kUzQeCrf4YMAsoVD8f9lN8xMYSn-fDWuiF6iHiRI1dxFJyFhm7rBd-RQVpAekTRJ13rTZw2ri3pynbPazUEGYH4n5DlaAuOld7lyjuOl3KnDgQzT5rWUlY1hXy3742v9GMCTRdG72p3JjNo-c97UmaggtWR7vgcM-YycA',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc1MzY4NzgwMCwic3ViIjoxNzAyNTA4OCwidXNuIjoiY29kbWNjb2RmaXNoIiwicHJkIjoiREZTIiwiY3J0IjoxNjM3NDEyNDM1LCJlbWwiOiJ2aW9sZW50Y29kQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2Mzc2MzI0Njh9.e61kVCC8zbEVAPijH0J-qRif-Yj0rus7KmHVLWe17vmaJaDt7_86HVMWB4aMqY3dFX0Y2WUDPMww6R9-oDnU_TWW3r7ABZtfCatZ-iZlW7GtPvX1ev2lmV_r1rAAzUqbRh8G012iwVhdntWAQk5-TmsW8yixSBE0A3uWowKD38XPpfLUmJoELgHCj4PDJYTYTEmaZDYTKGRtRNnzZbKf7BnKxmT8COeZqgt2rImezN2hdocvdWKWxv6NZQEbYlCjBWJerMoxlAoE52tTrmrUP0E78CkGPflgR3Bl_gN0MCQu-yk6PrY2weizJ6rH4O5t_aktCxFu2zYuQ1HVFRvxZA',
    'authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'x-brand': 'FANDUEL',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
    'x-currency': 'USD',
    'sec-gpc': '1',
    'origin': 'https://www.fanduel.com',
    'sec-fetch-site': 'same-site',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
    'referer': 'https://www.fanduel.com/',
    'accept-language': 'en-US,en;q=0.9',
}


class Contest(models.Model):
    url = models.URLField(help_text='https://api.fanduel.com/contests/63955-248463555')
    cost = models.DecimalField(decimal_places=2, max_digits=10, default=0.00)
    name = models.CharField(max_length=255, blank=True, null=True)
    contest_id = models.CharField(max_length=64, blank=True, null=True)
    entries_url = models.URLField(null=True, blank=True, help_text='https://api.fanduel.com/contests/63955-248463555/entries')
    num_entries = models.PositiveIntegerField(default=0)
    contest_json = models.TextField(blank=True, null=True)
    last_page_processed = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.name}'

    def get_payout(self, rank):
        try:
            prize = self.prizes.get(min_rank__lte=rank, max_rank__gte=rank)
            return prize.prize
        except ContestPrize.DoesNotExist:
            return 0.0


class ContestEntry(models.Model):
    contest = models.ForeignKey(Contest, related_name='entries', on_delete=models.CASCADE)
    entry_id = models.CharField(max_length=50)
    entry_url = models.URLField(help_text='https://api.fanduel.com/entries/2632507443')
    username = models.CharField(max_length=255, blank=True, null=True)
    entry_json = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.username}'


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
