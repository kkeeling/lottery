import json
from django.db import models

GET_CONTEST_HEADERS = {
    'authority': 'api.fanduel.com',
    'pragma': 'no-cache',
    'cache-control': 'no-cache',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiMWNjYjk1NzAyNDUyZTM5ZiIsInRpbWVzdGFtcCI6IjIwMjEtMTItMDdUMTI6MzU6MTcuMDg2WiIsInVzZXJfaWQiOiIxNzAyNTc5OSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiI0NS4xMzAuODMuNDEiLCJzZXNzaW9uX2lkIjo4MDEwNDkxNDMsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.anfqA3GQ59rB9TAv56NqNLqJV8zsBZt3m8GVre4R33Twx5-2p8GlM_PDtL2ki0E5P5Ggq-bW7_JS5YXYOcGsuKLx6h3N1_JEl-4hP_3nKRtrjRPFrEZXlMVUjNZpA7a8J9EN3xe2G_hFQjxRCTQ8lngv9jinAW3MKXJabel5eb-zwQxsPT5EMEn1aNyoxXCXBW2YA9h0Chsp4JnumVnV6nK78ang4Mz4BTAW1US9w9zL5DMHB2TVRP0-GRP3izbvmDZzFAxCuNqwX0eaUpjBEY8-szK0Djf47E8_zIYKqyt3_wGOrmX_BYO9mfXoUi1eGrenbqJsYVV-DwjlGI83gw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjgwMTA0OTE0Mywic3ViIjoxNzAyNTc5OSwidXNuIjoidHdvYW50ZWxvcGVzIiwicHJkIjoiREZTIiwiY3J0IjoxNjM4ODgwNTE2LCJlbWwiOiJUd29BbnRlbG9wZUBtYWlsZHJvcC5jYyIsInNyYyI6MSwicmxzIjpbMV0sIm1mYSI6ZmFsc2UsInR5cCI6MSwiZXhwIjoxNjM4OTIzNzE2fQ.DFC1xp6QCJTP8XhAJpXM6EFYFPIk0529SQbbIGnO6ef_SR_m_YVlPQMaafXrBIMNqBp8NTfcKLJZAPAFpFjqAxJnZEs6PMjN26-qicQOhX6d8760FnOvrG4Hta49lhAfHCzA3YGADPePt-IJysSMbabQ3lGph12Rl9zMEgo-nKiEwsrRLedPtqlfsZGlc5XANHGZ0vl8W335QjT-SrFwjttdnoUCfHqNtuVgS-hZfk09HW1vejXb0oMa-ViyWj592VWwctvyDBb1W4VI4wOmKbhgE4nbJxnkyrFm5xhVKoYE205hyuuMQ5QwPBEvOCtq69bhxzU4lnvwnZGgN12WwA',
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
    'pragma': 'no-cache',
    'cache-control': 'no-cache',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiMWNjYjk1NzAyNDUyZTM5ZiIsInRpbWVzdGFtcCI6IjIwMjEtMTItMDdUMTI6MzU6MTcuMDg2WiIsInVzZXJfaWQiOiIxNzAyNTc5OSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiI0NS4xMzAuODMuNDEiLCJzZXNzaW9uX2lkIjo4MDEwNDkxNDMsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.anfqA3GQ59rB9TAv56NqNLqJV8zsBZt3m8GVre4R33Twx5-2p8GlM_PDtL2ki0E5P5Ggq-bW7_JS5YXYOcGsuKLx6h3N1_JEl-4hP_3nKRtrjRPFrEZXlMVUjNZpA7a8J9EN3xe2G_hFQjxRCTQ8lngv9jinAW3MKXJabel5eb-zwQxsPT5EMEn1aNyoxXCXBW2YA9h0Chsp4JnumVnV6nK78ang4Mz4BTAW1US9w9zL5DMHB2TVRP0-GRP3izbvmDZzFAxCuNqwX0eaUpjBEY8-szK0Djf47E8_zIYKqyt3_wGOrmX_BYO9mfXoUi1eGrenbqJsYVV-DwjlGI83gw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjgwMTA0OTE0Mywic3ViIjoxNzAyNTc5OSwidXNuIjoidHdvYW50ZWxvcGVzIiwicHJkIjoiREZTIiwiY3J0IjoxNjM4ODgwNTE2LCJlbWwiOiJUd29BbnRlbG9wZUBtYWlsZHJvcC5jYyIsInNyYyI6MSwicmxzIjpbMV0sIm1mYSI6ZmFsc2UsInR5cCI6MSwiZXhwIjoxNjM4OTIzNzE2fQ.DFC1xp6QCJTP8XhAJpXM6EFYFPIk0529SQbbIGnO6ef_SR_m_YVlPQMaafXrBIMNqBp8NTfcKLJZAPAFpFjqAxJnZEs6PMjN26-qicQOhX6d8760FnOvrG4Hta49lhAfHCzA3YGADPePt-IJysSMbabQ3lGph12Rl9zMEgo-nKiEwsrRLedPtqlfsZGlc5XANHGZ0vl8W335QjT-SrFwjttdnoUCfHqNtuVgS-hZfk09HW1vejXb0oMa-ViyWj592VWwctvyDBb1W4VI4wOmKbhgE4nbJxnkyrFm5xhVKoYE205hyuuMQ5QwPBEvOCtq69bhxzU4lnvwnZGgN12WwA',
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
    'pragma': 'no-cache',
    'cache-control': 'no-cache',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiMWNjYjk1NzAyNDUyZTM5ZiIsInRpbWVzdGFtcCI6IjIwMjEtMTItMDdUMTI6MzU6MTcuMDg2WiIsInVzZXJfaWQiOiIxNzAyNTc5OSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiI0NS4xMzAuODMuNDEiLCJzZXNzaW9uX2lkIjo4MDEwNDkxNDMsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.anfqA3GQ59rB9TAv56NqNLqJV8zsBZt3m8GVre4R33Twx5-2p8GlM_PDtL2ki0E5P5Ggq-bW7_JS5YXYOcGsuKLx6h3N1_JEl-4hP_3nKRtrjRPFrEZXlMVUjNZpA7a8J9EN3xe2G_hFQjxRCTQ8lngv9jinAW3MKXJabel5eb-zwQxsPT5EMEn1aNyoxXCXBW2YA9h0Chsp4JnumVnV6nK78ang4Mz4BTAW1US9w9zL5DMHB2TVRP0-GRP3izbvmDZzFAxCuNqwX0eaUpjBEY8-szK0Djf47E8_zIYKqyt3_wGOrmX_BYO9mfXoUi1eGrenbqJsYVV-DwjlGI83gw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjgwMTA0OTE0Mywic3ViIjoxNzAyNTc5OSwidXNuIjoidHdvYW50ZWxvcGVzIiwicHJkIjoiREZTIiwiY3J0IjoxNjM4ODgwNTE2LCJlbWwiOiJUd29BbnRlbG9wZUBtYWlsZHJvcC5jYyIsInNyYyI6MSwicmxzIjpbMV0sIm1mYSI6ZmFsc2UsInR5cCI6MSwiZXhwIjoxNjM4OTIzNzE2fQ.DFC1xp6QCJTP8XhAJpXM6EFYFPIk0529SQbbIGnO6ef_SR_m_YVlPQMaafXrBIMNqBp8NTfcKLJZAPAFpFjqAxJnZEs6PMjN26-qicQOhX6d8760FnOvrG4Hta49lhAfHCzA3YGADPePt-IJysSMbabQ3lGph12Rl9zMEgo-nKiEwsrRLedPtqlfsZGlc5XANHGZ0vl8W335QjT-SrFwjttdnoUCfHqNtuVgS-hZfk09HW1vejXb0oMa-ViyWj592VWwctvyDBb1W4VI4wOmKbhgE4nbJxnkyrFm5xhVKoYE205hyuuMQ5QwPBEvOCtq69bhxzU4lnvwnZGgN12WwA',
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
    slate_week = models.PositiveIntegerField('Week #', default=0)
    slate_year = models.PositiveIntegerField(default=0)
    is_main_slate = models.BooleanField(default=True)
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
