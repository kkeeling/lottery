from django.db import models

GET_CONTEST_HEADERS = {
    'X-Geo-Packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiZTJkNzkzY2U3ZDU1NTY2MCIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMTdUMTQ6NDM6MjEuMTEwWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS4yMSIsInNlc3Npb25faWQiOjc0ODMzNDI5MSwiY291bnRyeV9jb2RlIjoiIiwicmVnaW9uX2NvZGUiOiIifQ.L-QqhekPTfS2CGM-hEnkDYmYPK3FJnqqfd5i87W4vDtlVfi_vK2AnkHWUy3rjsQ04VX0o78x4gJfI7Uz4N4yU5zyWuDbg-ngN8V7LquCrRFnqXS5_8gPQkhn1_VrwOCyfQRpjM8hauIhCYY_cbrsVEhS2KyyxIk7aytljSSQUpVhJojcxAjO9LH9IA1CYUstLXm6cHFLod9K5E8jZaLn53nXjgt_Lxnl48vYd4tzPUQuovN3Z0t9daOGSt5YqNAtgq9gUqxnWYy6V8bqeqqXwMXXNYSN-LivfHhxvCBTaFhNzgAdsvIfRx7LZrO9-oc9utQ7VsYVPqs-YmbnxdYVKw',
    'X-Brand': 'FANDUEL',
    'X-Currency': 'USD',
    'Authorization': 'Basic ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    'Accept': 'application/json',
    'Referer': 'https://www.fanduel.com/',
    'X-Auth-Token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzcyMDMzOTl9.B3AY2mD7iwHQJra0PxhaLco3G77knStslEsB_S_0LtXfExuyPpwx1g4pcmzZkQiHrPjLSrVIK-93KJGvffA0_8ip92GKVmd5RoheSC4pgksGXlCFr4MYRn2yhZi4nljd7DAG-7cMdej393ciyGgnTHI5Jeq3ZzLl_JeBd4KiI1t4rSHOaiRT6LQjf0liK4SKjBiumZ7Q8L83ejg48eBtuzQgnKyj9Ba4an51B7MVP7Gn36MO4Fpudo7yHS0uit43M2BsNXQ8CbEby5j3tB6pp3C46OPniPP_2pjW_zlXa0wIzT2UdooS3Bp5op-dGLRIVqurztsSaz7mKXjj6drn3A',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36',
}


GET_ENTRIES_HEADERS = {
    'authority': 'api.fanduel.com',
    'x-geo-packet': '',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzcyNzkwNjJ9.OTvKOxqLPta0V2EcgooHIbtu2fWLw3sElM6ABJosMwJ9PykHrceBwF6cIxP1q_Q-vFVa-uZ5zVisJ__vV8fFK-1XZiLRp43k65-4svY89d2wQuET-aD9KXIXDRLW1JAEu2flZAeTEG52TdEyDT-Oco8fq46_C9jV1d-RLLbB51osKv4sbXLGuLop0TCQ6Uvm80D1FHn8nvobJbu3wBMpdGCGpvjFpoRoOWvgWfmC6ubIXIkVr_LKV-v8TU2FxxUu03jWEMmlCGJuovJpMCHQfPCGava76hhXCWS5SWkgfgkSuemM71LjLszaPRURmpU5T-aXlJbuccZmnHxGMoGH5w',
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
    'x-geo-packet': 'eyJhbGciOiJSUzI1NiJ9.eyJzdGF0ZSI6Ik5KIiwicHJvZHVjdCI6IkRGUyIsImdjX3RyYW5zYWN0aW9uX2lkIjoiNzUyNDQ1MWU2OTlmM2ExNSIsInRpbWVzdGFtcCI6IjIwMjEtMTEtMThUMTE6NDQ6MjguNzExWiIsInVzZXJfaWQiOiIxNjk1MDY4NSIsInJlc3VsdCI6ZmFsc2UsImVycm9yX21lc3NhZ2UiOiJib3VuZGFyeSxwcm94eSIsInRyb3VibGVzaG9vdGVyIjpbeyJtZXNzYWdlIjoiV2UncmUgaGF2aW5nIHRyb3VibGUgY29uZmlybWluZyB5b3VyIGxvY2F0aW9uLiBNYWtlIHN1cmUgbG9jYXRpb24gc2hhcmluZyBpcyBlbmFibGVkIGZvciBGYW5EdWVsIGluIHlvdXIgYnJvd3Nlci4iLCJydWxlIjoiYm91bmRhcnkiLCJyZXRyeSI6dHJ1ZSwiaGVscCI6Imh0dHBzOi8vc3VwcG9ydC5mYW5kdWVsLmNvbS9zL2FydGljbGUvSG93LURvLUktRW5hYmxlLUxvY2F0aW9uLVNoYXJpbmcifSx7Im1lc3NhZ2UiOiJXZSBuZWVkIHRvIGNvbmZpcm0geW91J3JlIGluIGFuIGFyZWEgd2hlcmUgaXQncyBsZWdhbCB0byBwbGF5IGluIHBhaWQgY29udGVzdHMuIFBsZWFzZSBkaXNhYmxlIHByb3hpZXMsIFZQTnMsIElQIGFub255bWl6ZXJzLCBvciBvdGhlciBhcHBzIHRoYXQgbWlnaHQgb2JzY3VyZSB5b3VyIGxvY2F0aW9uLiIsInJ1bGUiOiJwcm94eSIsInJldHJ5Ijp0cnVlfV0sImlwX2FkZHJlc3MiOiIxOTIuMTA5LjIwNS45NyIsInNlc3Npb25faWQiOjc0ODMzNDI5MSwiY291bnRyeV9jb2RlIjoiIiwicmVnaW9uX2NvZGUiOiIifQ.X34NCPZT0a5F1X4xa7ZJvn-7v4P7C1QmskrVXe8ASBJuSbd6pacxlAzPyJWCuFNyPVSsR-QgLbshHdcw9ClKhF24OCISub9dShAwlSaBYA8nuYWLyAdTgRR-sBcEnd5LItNfxBubLj0p7MkhI1mWATK8fpzBjW9jZn76BxI9fvH6eJdpxYh9WXVCeaiTcUoWIiLb-vp4_sQW4tkIUW4-ANt5mDAs3kqFs2WGjCuZl_dTsL00mMM8N6VqXONykWy3CCkhcKghsft-mezjyPlrrp7VWH6yF2U1qQ0dHdqefs3qwpdh8_UrylKpbsBVmI4Chv7Etnf2x8CWMug3TqpeqA',
    'accept': 'application/json',
    'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjc0ODMzNDI5MSwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzcxNjAxOTksImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzcyNzkwNjJ9.OTvKOxqLPta0V2EcgooHIbtu2fWLw3sElM6ABJosMwJ9PykHrceBwF6cIxP1q_Q-vFVa-uZ5zVisJ__vV8fFK-1XZiLRp43k65-4svY89d2wQuET-aD9KXIXDRLW1JAEu2flZAeTEG52TdEyDT-Oco8fq46_C9jV1d-RLLbB51osKv4sbXLGuLop0TCQ6Uvm80D1FHn8nvobJbu3wBMpdGCGpvjFpoRoOWvgWfmC6ubIXIkVr_LKV-v8TU2FxxUu03jWEMmlCGJuovJpMCHQfPCGava76hhXCWS5SWkgfgkSuemM71LjLszaPRURmpU5T-aXlJbuccZmnHxGMoGH5w',
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
