import json
from django.db import models

GET_CONTEST_HEADERS = {
    'authority': 'api.fanduel.com',
    'pragma': 'no-cache',
    'cache-control': 'no-cache',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiNzVhN2ZhNzAyOTRjMjhlYSIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMzBUMTg6MzY6MTEuNjE0WiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS41OCIsInNlc3Npb25faWQiOjc4MTI5MzIwNywiY291bnRyeV9jb2RlIjoiIiwicmVnaW9uX2NvZGUiOiIifQ.Q5fKh7P1V66_LMpxDYi9Jc-Px_ZUiY-6YhmNCAgGEuHQHyDR2ukXp674YkvpzrD9p6EUYxwvwLkJVSFXt39ZcDJ2WnGfXOudZdxjYmTIqkSGE9UoOQszbnTJ1rnozInUe_ctwSpgkj1mNEtsaUAM95xeyv5sqs-LRV4RkZxnpDSx1OF-94jo2bKGmKRG8GWErn8HFTk6AaW6Q1hDZkr_qoP8HmLIgGNIYm7ZuJ2dPt5qS5ZMf9W35pHM_f3LzDQiqYB-iDedJN00JUNYz55fAxIS6x1gyNvCC_SkAJhdPPsaQ-GMF6qUjQInEonyA32saj4GhVzJcmMJalKz6JPKYw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc4MTI5MzIwNywic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzgyOTczNjgsImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzgzNDA1Njh9.f0zfePLFSWlIRaLleVAsFwKbW4QpsGNefRD_TKaaAd23j_EArUaEmH_fCQHZke6vKjNB4agiSgJNg3rvgwIcAtyhfJxYfX5HQ32M4BfvnMN8pkPjLQDpK-D4UIHB7SI3EATSBQDRtnZrtvEcXqE47Utvz7UL0QV2FMB8-Hdb4q98Y4rpYKfhUII74gokxLTWSyO8etOmnFTPHv4R3Ul8RJOOjQu2MZYEe-vMohvRPcK4FS3jClJVA-xK0oX9fDxuFoYcYV4nj3ZDnDsW82GELhyWQ4ab9By8O180Fq3v9TjkzDrGbUJZRZTWQpVYcwwfDFsn3hmk4tq0gbjhFf4sDw',
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
    'x-geo-packet': '',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc4MTI5MzIwNywic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzgyOTczNjksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2Mzg0MDQ5NjR9.VXCQf561oZwqLYE37TB92oUuvBnuTbt4I4m7cSfNdnsBvdc2rg1ID2pGEETTF921iPkWV5iPVgiQwgyoQZrCqEsEy9n3utFKXQHQ-5QDB5O3zbV8MlY_xHVF0Y3qLmcMAlDbDCuQsxLtYmY4xR8gIrU82OkU68U9r0qowxOnfiFOj2lvblq1AR_wA02uET1B2xGCGyKcedFu_ebpmyLIvXtIpWfodfp-gnIsk_gHyCJLWWSgCXgO-XJDriOnz_R0IO1J4ZZ6jf6JhT4NAiy5JIjWAVTR4EmTP3yzq7-9Jm83mh7W-ll4Csj3FUEZMJus9PT6CINj79-yjpfyP93onQ',
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
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiMmRlMzBhYWIyMjkxYmIwYyIsInRpbWVzdGFtcCI6IjIwMjEtMTItMDFUMTI6Mjk6MzMuMjAyWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS4xNzUiLCJzZXNzaW9uX2lkIjo3ODEyOTMyMDcsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.a2C-PWkC_UeMuYiuUycVQ_c6M9K6Zwrb5v157gASywvli2P_I1iMhV6VEQNncn1F44m3u86yXbJpxZ41Zz3zr7oOxzFkziDcPwyRg0FGY2CYnUDxGuat53lOlY0if72IMmb4HtAKrtDm4CNOwL4hiWxP9uF2IG7TQaYJkeJ1Q12WqIRylk0YDWDhQzcUw_vuijviIe0gn8NUoKrd17cNnhuayMj8ZKsvkc2iGa2fZNgbMXoAdBH0sbgrd2nocqdO66Rz7nv0XwbykpmFdqF-u7jqoVAC4xdHV7YUHd_xBmllE5JZsbXKJZ_DOH05HISaitcit1Rq4CNVT2pVUD0RHw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc4MTI5MzIwNywic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzgyOTczNjksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2Mzg0MDQ5NjR9.VXCQf561oZwqLYE37TB92oUuvBnuTbt4I4m7cSfNdnsBvdc2rg1ID2pGEETTF921iPkWV5iPVgiQwgyoQZrCqEsEy9n3utFKXQHQ-5QDB5O3zbV8MlY_xHVF0Y3qLmcMAlDbDCuQsxLtYmY4xR8gIrU82OkU68U9r0qowxOnfiFOj2lvblq1AR_wA02uET1B2xGCGyKcedFu_ebpmyLIvXtIpWfodfp-gnIsk_gHyCJLWWSgCXgO-XJDriOnz_R0IO1J4ZZ6jf6JhT4NAiy5JIjWAVTR4EmTP3yzq7-9Jm83mh7W-ll4Csj3FUEZMJus9PT6CINj79-yjpfyP93onQ',
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
