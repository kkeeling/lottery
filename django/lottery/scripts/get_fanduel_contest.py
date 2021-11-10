import numpy as np
import pandas as pd
import random
import requests
import socket   

from nfl import models


def run():
    headers = {
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

    params = (
        ('include_projections', 'false'),
        ('page', '2'),
        ('page_size', '10'),
    )

    response = requests.get('https://api.fanduel.com/contests/63955-248463555/entries', headers=headers, params=params)

    #NB. Original query string below. It seems impossible to parse and
    #reproduce query strings 100% accurately so the one below is given
    #in case the reproduced version is not "correct".
    # response = requests.get('https://api.fanduel.com/contests/63955-248463555/entries?include_projections=false&page=2&page_size=10', headers=headers)
    #NB. Original query string below. It seems impossible to parse and
    #reproduce query strings 100% accurately so the one below is given
    #in case the reproduced version is not "correct".
    # response = requests.get('https://api.fanduel.com/contests/63955-248463555/entries?include_projections=false&page=1&page_size=10', headers=headers)

    # contest_id = '63955-248463555'
    # page_size = 100
    # headers = {
    #     'authorization': 'ZWFmNzdmMTI3ZWEwMDNkNGUyNzVhM2VkMDdkNmY1Mjc6',
    #     'user-agent': user_agent,
    #     'x-auth-token': 'eyJraWQiOiIxIiwiYWxnIjoiUlMyNTYifQ.eyJzZXMiOjcyOTY4MzQwNCwic3ViIjoxNjk1MDY4NSwidXNuIjoiYnJhc2hiZWUiLCJwcmQiOiJERlMiLCJjcnQiOjE2MzY0Nzk4OTUsImVtbCI6ImJyYXNoYmVlQG1haWxkcm9wLmNjIiwic3JjIjoxLCJybHMiOlsxXSwibWZhIjpmYWxzZSwidHlwIjoxLCJleHAiOjE2MzY1MjMwOTV9.DXCuArqhBSDzrREhhdsflOtrqYhUhoTKDawnnEH9ItR9x8X83bC4MhwlJ9n_AHtkILuqie_1JsCqs5qup1uKpOLsjJHKLm40nqg3Or6KG66_F5vl1QXQlLjFuepl1-4ImHGYEezS_-9aDv5WF2goW1joyk4hfrGC0bVSXHbSMKHRLUEW_38RX8DojUf2V6-f_ULGsAk9IUCySVb4I2mN3Zt0Pqqi2RR9qee9JcyFYJd24zfCsbzId1iwny0vzSVXoetIw6nM6_Hx4HZA3o-XGivEyudaNniItKg62k5tYVeCuS-87tuZs2tUwdsmkRygQKetIyCMehZtxJF6PsDnDQ',
    #     'accept': 'application/json'
    # }
    # entries_url = f'https://api.fanduel.com/contests/{contest_id}/entries?page_size={page_size}'

    hostname = socket.gethostname()   
    IPAddr = socket.gethostbyname(hostname)   
    print("Your Computer Name is:" + hostname)   
    print("Your Computer IP Address is:" + IPAddr)   

    # response = requests.get('http://httpbin.org/headers', headers=headers) 
    # print(response.json()['headers']['User-Agent']) # Mozilla/5.0 ...

    # response = requests.get(entries_url, headers=headers)

    # print(f'{entries_url}')
    print(f'HTTP Status: {response.status_code}')
    print(response.headers)
    if response.status_code < 300:
        print(response.json())
