import json
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
    'X-Geo-Packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiN2M1MjgwZDNlY2M2ZDJiMCIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMjNUMTc6MjM6MDEuNzY1WiIsInVzZXJfaWQiOiIxNzAyNTc5OSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiI0NS4xMzAuODMuMjQ2Iiwic2Vzc2lvbl9pZCI6NzYyNjQwODY5LCJjb3VudHJ5X2NvZGUiOiIiLCJyZWdpb25fY29kZSI6IiJ9.AB40fycV-sLIoNo-dsOkd0pxS3c_59lFnPPlTGsGkSfgmfhywbMoQcrLcCNh2LtY5PXrd5Qu30dmeWJu-D2UffiykuJpJrDx_osluXiVcJG9pS7U9hHnr0nyG5MMrOKCyQKowE3JQZQDKnrX4C1SeA_1V4_FLxxEIWE-L5YD6-ixo77iJRgxO32IIRFByVtRbRZqzf7PLdMDYwykwOPi7USCd0_uXB69OvltCHpgbPzUieU5B1OG-Eb9Vxt1LZLXXhUvLpD7pf4na-UuIysdieTC1wVKz7tDFtTc5D0vPC9eU43vv8kuMI69AniOdNJAXL3TXutrKJAVsjmGK7_5MA',
    'X-Brand': 'FANDUEL',
    'X-Currency': 'USD',
    'Authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'Accept': 'application/json',
    'Referer': 'https://www.fanduel.com/',
    'X-Auth-Token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc2MjY0MDg2OSwic3ViIjoxNzAyNTc5OSwidXNuIjoidHdvYW50ZWxvcGVzIiwicHJkIjoiREZTIiwiY3J0IjoxNjM3Njg4MTgwLCJlbWwiOiJUd29BbnRlbG9wZUBtYWlsZHJvcC5jYyIsInNyYyI6MSwicmxzIjpbMV0sIm1mYSI6ZmFsc2UsInR5cCI6MSwiZXhwIjoxNjM3NzMxMzgwfQ.a-HDjgojZ--gyQy20eOgrl2M3L_Ma4GXH3n2BBZNqiPHKppBEyW4D0jW5yqoY1eBFmoTcjMGLHaSOXp0QahZNeWaalm1cSrC9l4_2lSjfkyc3JszM6aEcas0RxmIeDijlbiAJloAyU1uSIPMZp5fnsh3oymXvn9LUrisWoZNQptH95a7ATwl8beDseTSOdB6RgycrZaigzzfaq9w1603g8YWs0w_mfMVxAR6iUUVFjskOI5cG2CNOhxeAmsKlNBC8NHjk6zX9Ag0-m09PXrcXrl6HbY37MVJHzZCLeixP_PPdHXBlHDdd5eZz-0XnjZbA5NLOgGLha11iXCcC8tWeA',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
}


GET_LINEUP_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiN2M1MjgwZDNlY2M2ZDJiMCIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMjNUMTc6MjM6MDEuNzY1WiIsInVzZXJfaWQiOiIxNzAyNTc5OSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiI0NS4xMzAuODMuMjQ2Iiwic2Vzc2lvbl9pZCI6NzYyNjQwODY5LCJjb3VudHJ5X2NvZGUiOiIiLCJyZWdpb25fY29kZSI6IiJ9.AB40fycV-sLIoNo-dsOkd0pxS3c_59lFnPPlTGsGkSfgmfhywbMoQcrLcCNh2LtY5PXrd5Qu30dmeWJu-D2UffiykuJpJrDx_osluXiVcJG9pS7U9hHnr0nyG5MMrOKCyQKowE3JQZQDKnrX4C1SeA_1V4_FLxxEIWE-L5YD6-ixo77iJRgxO32IIRFByVtRbRZqzf7PLdMDYwykwOPi7USCd0_uXB69OvltCHpgbPzUieU5B1OG-Eb9Vxt1LZLXXhUvLpD7pf4na-UuIysdieTC1wVKz7tDFtTc5D0vPC9eU43vv8kuMI69AniOdNJAXL3TXutrKJAVsjmGK7_5MA',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc2MjY0MDg2OSwic3ViIjoxNzAyNTc5OSwidXNuIjoidHdvYW50ZWxvcGVzIiwicHJkIjoiREZTIiwiY3J0IjoxNjM3Njg4MTgwLCJlbWwiOiJUd29BbnRlbG9wZUBtYWlsZHJvcC5jYyIsInNyYyI6MSwicmxzIjpbMV0sIm1mYSI6ZmFsc2UsInR5cCI6MSwiZXhwIjoxNjM3NzMxMzgwfQ.a-HDjgojZ--gyQy20eOgrl2M3L_Ma4GXH3n2BBZNqiPHKppBEyW4D0jW5yqoY1eBFmoTcjMGLHaSOXp0QahZNeWaalm1cSrC9l4_2lSjfkyc3JszM6aEcas0RxmIeDijlbiAJloAyU1uSIPMZp5fnsh3oymXvn9LUrisWoZNQptH95a7ATwl8beDseTSOdB6RgycrZaigzzfaq9w1603g8YWs0w_mfMVxAR6iUUVFjskOI5cG2CNOhxeAmsKlNBC8NHjk6zX9Ag0-m09PXrcXrl6HbY37MVJHzZCLeixP_PPdHXBlHDdd5eZz-0XnjZbA5NLOgGLha11iXCcC8tWeA',
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

    def get_lineups_as_json(self):
        entries = []

        for entry in self.entries.all().iterator():
            raw_json = json.loads(entry.entry_json)
            if len(raw_json) > 0:
                entry_dict = {
                    'username': entry.username,
                    'qb_id': raw_json[0].get("id"),
                    'rb1_id': raw_json[1].get("id"),
                    'rb2_id': raw_json[2].get("id"),
                    'wr1_id': raw_json[3].get("id"),
                    'wr2_id': raw_json[4].get("id"),
                    'wr3_id': raw_json[5].get("id"),
                    'te_id': raw_json[6].get("id"),
                    'flex_id': raw_json[7].get("id"),
                    'dst_id': raw_json[8].get("id"),
                }
                entries.append(entry_dict)
        return entries


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
