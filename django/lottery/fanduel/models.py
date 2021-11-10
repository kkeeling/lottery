from django.db import models

GET_CONTEST_HEADERS = {
    'X-Geo-Packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiZWM0MjUxM2JhOWZjMmIwNCIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMDlUMTc6NDQ6NTcuNjYxWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS40MiIsInNlc3Npb25faWQiOjcyOTY4MzQwNCwiY291bnRyeV9jb2RlIjoiIiwicmVnaW9uX2NvZGUiOiIifQ.fp2TE4JWbjqx2_fSDUGYutwwbxgfkjcAIufR7EiIxcNDEq1EAgt4p6O1a7R4uBfQL_VhP7AvhqUqn-aCWLSiaJScRpWiYUR5tQHeC4FuxW3fwhsduFvOa9NZkqIog65_U1DFZFP8oBWg2U9BuPkEUM-PLuKV8AoM673sI3Nr6ci6LxL7LbxFqn9aPz464DyQ_Z7h0UOhuVEatJ5GwNHpzH4Kmo8x9S2lDYYdwwu-k8U7gPoLF2mKP58yhP9weJex1Ir9w5QXn9O0FyP7I9exzmLIKLECJi9s0DTJjolVYLldzzLs_ed_6vSPn6kBfgPerNhaoFhZyJliVSGxqJGQUw',
    'X-Brand': 'FANDUEL',
    'X-Currency': 'USD',
    'Authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'Accept': 'application/json',
    'Referer': 'https://www.fanduel.com/',
    'X-Auth-Token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjcyOTY4MzQwNCwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzY0Nzk4OTUsImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzY1MjMwOTV9.DXCuArqhBSDzrREhhdsflOtrqYhUhoTKDawnnEH9ItR9x8X83bC4MhwlJ9n_AHtkILuqie_1JsCqs5qup1uKpOLsjJHKLm40nqg3Or6KG66_F5vl1QXQlLjFuepl1-4ImHGYEezS_-9aDv5WF2goW1joyk4hfrGC0bVSXHbSMKHRLUEW_38RX8DojUf2V6-f_ULGsAk9IUCySVb4I2mN3Zt0Pqqi2RR9qee9JcyFYJd24zfCsbzId1iwny0vzSVXoetIw6nM6_Hx4HZA3o-XGivEyudaNniItKg62k5tYVeCuS-87tuZs2tUwdsmkRygQKetIyCMehZtxJF6PsDnDQ',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36',
}


GET_ENTRIES_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiZWM0MjUxM2JhOWZjMmIwNCIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMDlUMTc6NDQ6NTcuNjYxWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS40MiIsInNlc3Npb25faWQiOjcyOTY4MzQwNCwiY291bnRyeV9jb2RlIjoiIiwicmVnaW9uX2NvZGUiOiIifQ.fp2TE4JWbjqx2_fSDUGYutwwbxgfkjcAIufR7EiIxcNDEq1EAgt4p6O1a7R4uBfQL_VhP7AvhqUqn-aCWLSiaJScRpWiYUR5tQHeC4FuxW3fwhsduFvOa9NZkqIog65_U1DFZFP8oBWg2U9BuPkEUM-PLuKV8AoM673sI3Nr6ci6LxL7LbxFqn9aPz464DyQ_Z7h0UOhuVEatJ5GwNHpzH4Kmo8x9S2lDYYdwwu-k8U7gPoLF2mKP58yhP9weJex1Ir9w5QXn9O0FyP7I9exzmLIKLECJi9s0DTJjolVYLldzzLs_ed_6vSPn6kBfgPerNhaoFhZyJliVSGxqJGQUw',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjcyOTY4MzQwNCwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzY0Nzk4OTUsImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzY1MjMwOTV9.DXCuArqhBSDzrREhhdsflOtrqYhUhoTKDawnnEH9ItR9x8X83bC4MhwlJ9n_AHtkILuqie_1JsCqs5qup1uKpOLsjJHKLm40nqg3Or6KG66_F5vl1QXQlLjFuepl1-4ImHGYEezS_-9aDv5WF2goW1joyk4hfrGC0bVSXHbSMKHRLUEW_38RX8DojUf2V6-f_ULGsAk9IUCySVb4I2mN3Zt0Pqqi2RR9qee9JcyFYJd24zfCsbzId1iwny0vzSVXoetIw6nM6_Hx4HZA3o-XGivEyudaNniItKg62k5tYVeCuS-87tuZs2tUwdsmkRygQKetIyCMehZtxJF6PsDnDQ',
    'authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'x-brand': 'FANDUEL',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36',
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
