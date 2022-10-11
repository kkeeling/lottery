import requests

from nfl import models

def run():
    login_url = 'https://www.4for4.com/user/login'
    projections_url = 'https://www.4for4.com/dfs_projections_csv/4374/0/89510'
    login_payload = {
        'form_id': 'user_login',
        'name': 'kkeeling',
        'pass': 'Taylorsdogsarecute'
    }

    with requests.Session() as s:
        # r = s.post(login_url, login_payload)

        headers = {
            'Cookie': 'Drupal.visitor.cover_blocks:selected_tab=cover; user_mode=cover; f4__Slatesfanduel={"slate_id":4203}; SSESSc40475ee089b0d4e8158fa797261c63c=GUXEysz3sYGW6OO-INMZuGFUbLNvDt-y9JJch5ioTgw; Drupal.visitor.subscriptionPlan=dfs_eb; Drupal.visitor.drupal_login=a:5:{s:16:"SESSION_USERNAME";s:8:"kkeeling";s:12:"SESSION_TYPE";i:1;s:16:"SESSION_LOGGEDIN";i:1;s:19:"SESSION_LOGINFAILED";i:0;s:11:"FULL_IMPACT";i:1;}; ff4for4uid=14878; default_page_league={"full-impact_cheatsheet_QB__ff_nflstats_early":"169091","full-impact_cheatsheet_QB__ff_nflstats_early_adp_blend":"169091","full-impact_cheatsheet_RB__ff_nflstats_early_adp_blend":"169091","full-impact_cheatsheet_WR__ff_nflstats_early_adp_blend":"169091","full-impact_cheatsheet_TE__ff_nflstats_early_adp_blend":"169091","full-impact_cheatsheet_QB__ff_nflstats":"38353","full-impact_cheatsheet_RB__ff_nflstats":"169093","full-impact_cheatsheet_WR__ff_nflstats":"169099","full-impact_cheatsheet_TE__ff_nflstats":"169099","full-impact_cheatsheet_Superflex__ff_nflstats":"169099","full-impact_cheatsheet_Flex__ff_nflstats":"169093"}; site=draftkings; f4__Slatesdraftkings={"slate_id":4374}; Drupal.lg.draftkings.salary_cap=50000; Drupal.visitor.lg_fiWeek={"5":{"cleared_draftkings":true}}; Drupal.ff.notReceiveMessage.resetPool=1; aucp13n=3h7gaq'
        }
        req = requests.Request('GET', projections_url, headers=headers)
        # s.cookies.add_cookie_header(req)
        prepped = s.prepare_request(req)
        # prepped.headers.update({
        #     'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.134 Safari/537.36',
        #     'referer': 'https://www.4for4.com/daily-fantasy-football-salaries'
        # })
        resp = s.send(prepped)
        print(resp.text)
        print(prepped.headers)
        # print(resp.status_code)     