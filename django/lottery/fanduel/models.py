from django.db import models

GET_CONTEST_HEADERS = {
    'X-Geo-Packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiNjEwYWU2OGJhMWE5MWJlZiIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMTlUMTQ6NTY6MTYuNzAwWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS4xMTMiLCJzZXNzaW9uX2lkIjo3NDgzMzQyOTEsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.bJ1Wo8jEMhQPy5ARZ6LIN9M7tubZ7R-wWlRw4OzxxGhtc_O_XDz8sVorAlV9im3pWnX3z2uBptgub65svOR0yXPlHne5MwZca6Qm7fH__ThINUmkIx7ZORsnFqnRqAzrLufHEny9XBRKX3cTXjF0aS7pQ17thOGKW0o2QgHXQpgZj_nOuUxmKMuhl0Y_4OBOTd8ahL8P3wm-2KeDAC5zXtTf_vHBdH5fntRIYMjiHuQvR_GsZvLY2htDWS1evICpc7KNTlt3L7ntOc0HJm2EFv1KrqtDvDVXj9qr5WBTFQP9EpWB2EUoNdY3rmRsPZ5qqkTofX_4AxSP2YkDFeE5SA',
    'X-Brand': 'FANDUEL',
    'X-Currency': 'USD',
    'Authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'Accept': 'application/json',
    'Referer': 'https://www.fanduel.com/',
    'X-Auth-Token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzczNzY5NzF9.PpLwY6VhTfFLEdF4MLCT6xsOn55ZUsl9YGN8E5JeRhd-tCNjiPwoDo7WE3WyjCI7dEvobkH5MrUGbPiuXflP59smjB9_RONWQ8PQ9CoKmyRHehkvB4LajT_pLNOkdS1jpOJmv_e7hwIFeZX7vtm5dqOD2IcLKxW6ReVV5N1HNnYR6DXYiE2s5zuh1XT3T_uyN5ruaP4EZV8aYKLll551HpIClgAdr8Sf08dQwN8AQQx_WYcz-L0VxFgPzmzG0pgEO5tVUir-PNFQbeVeg_tzsu6x2dtGzXYpsNl8Tg6hgg6R3j4KHIVeCW0FvBj85PpPW40IzgNCzTANF39W0LXMRA',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
}


GET_ENTRIES_HEADERS = {
    'X-Geo-Packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiNjEwYWU2OGJhMWE5MWJlZiIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMTlUMTQ6NTY6MTYuNzAwWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS4xMTMiLCJzZXNzaW9uX2lkIjo3NDgzMzQyOTEsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.bJ1Wo8jEMhQPy5ARZ6LIN9M7tubZ7R-wWlRw4OzxxGhtc_O_XDz8sVorAlV9im3pWnX3z2uBptgub65svOR0yXPlHne5MwZca6Qm7fH__ThINUmkIx7ZORsnFqnRqAzrLufHEny9XBRKX3cTXjF0aS7pQ17thOGKW0o2QgHXQpgZj_nOuUxmKMuhl0Y_4OBOTd8ahL8P3wm-2KeDAC5zXtTf_vHBdH5fntRIYMjiHuQvR_GsZvLY2htDWS1evICpc7KNTlt3L7ntOc0HJm2EFv1KrqtDvDVXj9qr5WBTFQP9EpWB2EUoNdY3rmRsPZ5qqkTofX_4AxSP2YkDFeE5SA',
    'X-Brand': 'FANDUEL',
    'X-Currency': 'USD',
    'Authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'Accept': 'application/json',
    'Referer': 'https://www.fanduel.com/',
    'X-Auth-Token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzczNzY5NzF9.PpLwY6VhTfFLEdF4MLCT6xsOn55ZUsl9YGN8E5JeRhd-tCNjiPwoDo7WE3WyjCI7dEvobkH5MrUGbPiuXflP59smjB9_RONWQ8PQ9CoKmyRHehkvB4LajT_pLNOkdS1jpOJmv_e7hwIFeZX7vtm5dqOD2IcLKxW6ReVV5N1HNnYR6DXYiE2s5zuh1XT3T_uyN5ruaP4EZV8aYKLll551HpIClgAdr8Sf08dQwN8AQQx_WYcz-L0VxFgPzmzG0pgEO5tVUir-PNFQbeVeg_tzsu6x2dtGzXYpsNl8Tg6hgg6R3j4KHIVeCW0FvBj85PpPW40IzgNCzTANF39W0LXMRA',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
}


GET_LINEUP_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiNjEwYWU2OGJhMWE5MWJlZiIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMTlUMTQ6NTY6MTYuNzAwWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS4xMTMiLCJzZXNzaW9uX2lkIjo3NDgzMzQyOTEsImNvdW50cnlfY29kZSI6IiIsInJlZ2lvbl9jb2RlIjoiIn0.bJ1Wo8jEMhQPy5ARZ6LIN9M7tubZ7R-wWlRw4OzxxGhtc_O_XDz8sVorAlV9im3pWnX3z2uBptgub65svOR0yXPlHne5MwZca6Qm7fH__ThINUmkIx7ZORsnFqnRqAzrLufHEny9XBRKX3cTXjF0aS7pQ17thOGKW0o2QgHXQpgZj_nOuUxmKMuhl0Y_4OBOTd8ahL8P3wm-2KeDAC5zXtTf_vHBdH5fntRIYMjiHuQvR_GsZvLY2htDWS1evICpc7KNTlt3L7ntOc0HJm2EFv1KrqtDvDVXj9qr5WBTFQP9EpWB2EUoNdY3rmRsPZ5qqkTofX_4AxSP2YkDFeE5SA',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzczNzY5NzF9.PpLwY6VhTfFLEdF4MLCT6xsOn55ZUsl9YGN8E5JeRhd-tCNjiPwoDo7WE3WyjCI7dEvobkH5MrUGbPiuXflP59smjB9_RONWQ8PQ9CoKmyRHehkvB4LajT_pLNOkdS1jpOJmv_e7hwIFeZX7vtm5dqOD2IcLKxW6ReVV5N1HNnYR6DXYiE2s5zuh1XT3T_uyN5ruaP4EZV8aYKLll551HpIClgAdr8Sf08dQwN8AQQx_WYcz-L0VxFgPzmzG0pgEO5tVUir-PNFQbeVeg_tzsu6x2dtGzXYpsNl8Tg6hgg6R3j4KHIVeCW0FvBj85PpPW40IzgNCzTANF39W0LXMRA',
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
