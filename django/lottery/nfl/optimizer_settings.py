from pydfs_lineup_optimizer.sites.sites_registry import SitesRegistry
from pydfs_lineup_optimizer.sites.draftkings.classic.settings import DraftKingsSettings, LineupPosition, Sport
from pydfs_lineup_optimizer.sites.fanduel.classic.settings import FanDuelSettings, FanDuelFootballSettings


class FanduelNFLSettingsMax2PerTeam(FanDuelFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 2
    max_games = 6


class FanduelNFLSettingsMax3PerTeam(FanDuelFootballSettings):
    sport = Sport.FOOTBALL
    max_from_one_team = 3
    max_games = 6


# @SitesRegistry.register_settings
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


# @SitesRegistry.register_settings
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
        LineupPosition('FLEX', ('RB', 'WR', 'TE')),
        LineupPosition('DST', ('DST',))
    ]
