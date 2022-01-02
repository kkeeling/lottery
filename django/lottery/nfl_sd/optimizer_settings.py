from pydfs_lineup_optimizer.sites.sites_registry import SitesRegistry
from pydfs_lineup_optimizer.sites.draftkings.classic.settings import DraftKingsSettings, LineupPosition, Sport
from pydfs_lineup_optimizer.sites.fanduel.classic.settings import FanDuelSettings, FanDuelFootballSettings
from pydfs_lineup_optimizer.sites.yahoo.settings import YahooFootballSettings


class FanduelNFLSettingsMax2PerTeam(FanDuelFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 2
    max_games = 6


class FanduelNFLSettingsMax3PerTeam(FanDuelFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 6


class FanduelNFLSettingsMax3PerTeamMax5Games(FanDuelFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 5


class DraftKingsNFLSettingsMax2PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 2
    max_games = 6


class DraftKingsNFLSettingsMax3PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 6


class DraftKingsNFLSettingsMax3PerTeamMax5Games(DraftKingsSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 5


class DraftKingsFootballNoRBFlexSettings(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('WR', 'TE')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoRBFlexSettingsMax2PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 2
    max_games = 6
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('WR', 'TE')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoRBFlexSettingsMax3PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 3
    max_games = 6
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('WR', 'TE')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoRBFlexSettingsMax3PerTeamMax5Games(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 3
    max_games = 5
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('WR', 'TE')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoTEFlexSettings(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('RB', 'WR')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoTEFlexSettingsMax2PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 2
    max_games = 6
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('RB', 'WR')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoTEFlexSettingsMax3PerTeam(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 3
    max_games = 6
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('RB', 'WR')),
        LineupPosition('DST', ('DST',))
    ]


class DraftKingsFootballNoTEFlexSettingsMax3PerTeamMax5Games(DraftKingsSettings):
    sport = Sport.FOOTBALL
    min_games = 2
    max_from_one_team = 3
    max_games = 5
    positions = [
        LineupPosition('QB', ('QB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('RB', ('RB',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('WR', ('WR',)),
        LineupPosition('TE', ('TE',)),
        LineupPosition('FLEX', ('RB', 'WR')),
        LineupPosition('DST', ('DST',))
    ]


class YahooNFLSettingsMax2PerTeam(YahooFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 2
    max_games = 6


class YahooNFLSettingsMax3PerTeam(YahooFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 6


class YahooNFLSettingsMax3PerTeamMax5Games(YahooFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 5
