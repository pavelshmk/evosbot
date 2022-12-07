from datetime import timedelta
from decimal import Decimal

from dynamic_preferences.preferences import Section
from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.types import StringPreference, IntegerPreference, DurationPreference, BooleanPreference, \
    DecimalPreference, DateTimePreference

general = Section('general')
internal = Section('internal')
small_airdrops = Section('small_airdrops')
medium_airdrops = Section('medium_airdrops')
large_airdrops = Section('large_airdrops')
ranks = Section('ranks')
games = Section('games')


@global_preferences_registry.register
class BotToken(StringPreference):
    section = general
    default = ''
    name = 'bot_token'


@global_preferences_registry.register
class TelegramBotToken(StringPreference):
    section = general
    default = ''
    name = 'telegram_bot_token'


@global_preferences_registry.register
class TelegramChatID(StringPreference):
    section = general
    default = ''
    name = 'telegram_chat_id'


@global_preferences_registry.register
class GuildID(IntegerPreference):
    section = general
    default = -1
    name = 'guild_id'


# @global_preferences_registry.register
# class AutomaticReferralBounty(BooleanPreference):
#     section = general
#     default = True
#     name = 'automatic_referral_bounty'


@global_preferences_registry.register
class MinAccountAge(DurationPreference):
    section = general
    default = timedelta(7)
    name = 'min_account_age'


@global_preferences_registry.register
class FixedTransactionCommission(DecimalPreference):
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    section = general
    default = Decimal(0)
    name = 'transaction_commission'


@global_preferences_registry.register
class UnconfirmedUntilConfirmations(IntegerPreference):
    section = general
    default = 2
    name = 'confirmations_needed'


@global_preferences_registry.register
class StakingConfirmations(IntegerPreference):
    section = general
    default = 10
    name = 'staking_confirmations'


@global_preferences_registry.register
class MainWalletURI(StringPreference):
    section = general
    default = 'http://user4352:8934750234702fgsdfg43523@127.0.0.1:8349'
    name = 'main_wallet_uri'


@global_preferences_registry.register
class StakingWalletURI(StringPreference):
    section = general
    default = 'http://user4352:8934750234702fgsdfg43523@127.0.0.1:8350'
    name = 'staking_wallet_uri'


@global_preferences_registry.register
class StakingPoolWalletURI(StringPreference):
    section = general
    default = 'http://user4352:8934750234702fgsdfg43523@127.0.0.1:8351'
    name = 'staking_pool_wallet_uri'


@global_preferences_registry.register
class MasternodeWalletURI(StringPreference):
    section = general
    default = 'http://user4352:8934750234702fgsdfg43523@127.0.0.1:8352'
    name = 'masternode_wallet_uri'


@global_preferences_registry.register
class BitcoinWalletURI(StringPreference):
    section = general
    default = 'http://user43058230:kGL09mGjk9mG2@127.0.0.1:8333'
    name = 'bitcoin_wallet_uri'


@global_preferences_registry.register
class MasternodeServiceURI(StringPreference):
    section = general
    default = 'http://mnusername:mnpassword@155.138.220.173:8888'
    name = 'masternode_service_uri'


@global_preferences_registry.register
class UsernodeWalletURI(StringPreference):
    section = general
    default = 'http://user4352:8934750234702fgsdfg43523@127.0.0.1:8353'
    name = 'usernode_wallet_uri'


@global_preferences_registry.register
class UsernodeServiceURI(StringPreference):
    section = general
    default = 'http://mnusername:mnpassword@139.180.211.172:8888'
    name = 'usernode_service_uri'


@global_preferences_registry.register
class RewardReportChannelID(IntegerPreference):
    section = general
    default = -1
    name = 'reward_report_channel_id'


@global_preferences_registry.register
class RescueChannel(StringPreference):
    section = general
    default = ''
    name = 'rescue_channel'


@global_preferences_registry.register
class StatsInterval(IntegerPreference):
    section = general
    default = 180 * 60
    name = 'stats_interval'
    help_text = 'In seconds'


@global_preferences_registry.register
class FeederBalance(DecimalPreference):
    section = general
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'feeder_balance'


@global_preferences_registry.register
class CREX24Instrument(StringPreference):
    section = general
    default = 'SOVE-BTC'
    name = 'crex24_instrument'


@global_preferences_registry.register
class TelegramAirdropMultiplier(DecimalPreference):
    section = general
    field_kwargs = {
        'max_digits': 5,
        'decimal_places': 2,
    }
    default = Decimal(1)
    name = 'telegram_airdrop_multiplier'


# internal


@global_preferences_registry.register
class LastStakingPoolBlock(StringPreference):
    section = internal
    default = ''
    name = 'last_staking_pool_block'


@global_preferences_registry.register
class LastMasternodeBlock(StringPreference):
    section = internal
    default = ''
    name = 'last_masternode_block'


@global_preferences_registry.register
class StakingPoolAddress(StringPreference):
    section = internal
    default = ''
    name = 'staking_pool_address'


@global_preferences_registry.register
class MasternodeAddress(StringPreference):
    section = internal
    default = ''
    name = 'masternode_address'


@global_preferences_registry.register
class MasternodeLock(BooleanPreference):
    section = internal
    default = False
    name = 'masternode_lock'


@global_preferences_registry.register
class UsernodeLock(BooleanPreference):
    section = internal
    default = False
    name = 'usernode_lock'


@global_preferences_registry.register
class LotteryLastHeight(IntegerPreference):
    section = internal
    default = 0
    name = 'lottery_last_height'


@global_preferences_registry.register
class LotteryJackpot(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'lottery_jackpot'


@global_preferences_registry.register
class DiceJackpot(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'dice_jackpot'


@global_preferences_registry.register
class StackMedian(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'stack_median'


@global_preferences_registry.register
class CREX24Volume(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'crex24_volume'


@global_preferences_registry.register
class CREX24Price(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 2,
    }
    default = Decimal(0)
    name = 'crex24_price'


@global_preferences_registry.register
class CryptoBridgeVolume(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'cryptobridge_volume'


@global_preferences_registry.register
class CryptoBridgePrice(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 2,
    }
    default = Decimal(0)
    name = 'cryptobridge_price'


@global_preferences_registry.register
class GraviexVolume(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'graviex_volume'


@global_preferences_registry.register
class GraviexPrice(DecimalPreference):
    section = internal
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 2,
    }
    default = Decimal(0)
    name = 'graviex_price'


# airdrops


@global_preferences_registry.register
class SmallAirdropCount(IntegerPreference):
    section = small_airdrops
    default = 48
    name = 'count'


@global_preferences_registry.register
class SmallAirdropJunior(DecimalPreference):
    section = small_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('.25')
    name = 'junior'


@global_preferences_registry.register
class SmallAirdropExperienced(DecimalPreference):
    section = small_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('.25')
    name = 'experienced'


@global_preferences_registry.register
class SmallAirdropVeteran(DecimalPreference):
    section = small_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('.25')
    name = 'veteran'


@global_preferences_registry.register
class SmallAirdropGuru(DecimalPreference):
    section = small_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('.25')
    name = 'guru'


@global_preferences_registry.register
class SmallAirdropSadhu(DecimalPreference):
    section = small_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('.25')
    name = 'sadhu'


@global_preferences_registry.register
class MediumAirdropCount(IntegerPreference):
    section = medium_airdrops
    default = 24
    name = 'count'


@global_preferences_registry.register
class MediumAirdropJunior(DecimalPreference):
    section = medium_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('1')
    name = 'junior'


@global_preferences_registry.register
class MediumAirdropExperienced(DecimalPreference):
    section = medium_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('1.25')
    name = 'experienced'


@global_preferences_registry.register
class MediumAirdropVeteran(DecimalPreference):
    section = medium_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('1.5')
    name = 'veteran'


@global_preferences_registry.register
class MediumAirdropGuru(DecimalPreference):
    section = medium_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('1.75')
    name = 'guru'


@global_preferences_registry.register
class MediumAirdropSadhu(DecimalPreference):
    section = medium_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('2')
    name = 'sadhu'


@global_preferences_registry.register
class LargeAirdropCount(IntegerPreference):
    section = large_airdrops
    default = 2
    name = 'count'


@global_preferences_registry.register
class LargeAirdropJunior(DecimalPreference):
    section = large_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('5')
    name = 'junior'


@global_preferences_registry.register
class LargeAirdropExperienced(DecimalPreference):
    section = large_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('7')
    name = 'experienced'


@global_preferences_registry.register
class LargeAirdropVeteran(DecimalPreference):
    section = large_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('9')
    name = 'veteran'


@global_preferences_registry.register
class LargeAirdropGuru(DecimalPreference):
    section = large_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('11')
    name = 'guru'


@global_preferences_registry.register
class LargeAirdropSadhu(DecimalPreference):
    section = large_airdrops
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal('13')
    name = 'sadhu'


# ranks


@global_preferences_registry.register
class RankChannel(StringPreference):
    section = ranks
    default = ''
    name = 'rank_channel'


@global_preferences_registry.register
class JuniorXP(IntegerPreference):
    section = ranks
    default = 30
    name = 'junior_xp'


@global_preferences_registry.register
class ExperiencedXP(IntegerPreference):
    section = ranks
    default = 60
    name = 'experienced_xp'


@global_preferences_registry.register
class VeteranXP(IntegerPreference):
    section = ranks
    default = 120
    name = 'veteran_xp'


@global_preferences_registry.register
class GuruXP(IntegerPreference):
    section = ranks
    default = 240
    name = 'guru_xp'


@global_preferences_registry.register
class SadhuXP(IntegerPreference):
    section = ranks
    default = 480
    name = 'sadhu_xp'


@global_preferences_registry.register
class NewbieRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'newbie_role_id'


@global_preferences_registry.register
class JuniorRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'junior_role_id'


@global_preferences_registry.register
class ExperiencedRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'experienced_role_id'


@global_preferences_registry.register
class VeteranRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'veteran_role_id'


@global_preferences_registry.register
class GuruRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'guru_role_id'


@global_preferences_registry.register
class MutedRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'muted_role_id'    


@global_preferences_registry.register
class ReferrerLVL1Bonus(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'referrer_lvl1_bonus'


@global_preferences_registry.register
class ReferrerLVL2Bonus(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'referrer_lvl2_bonus'


@global_preferences_registry.register
class ReferrerLVL3Bonus(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'referrer_lvl3_bonus'


@global_preferences_registry.register
class JuniorHold(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'junior_hold'


@global_preferences_registry.register
class ExperiencedHold(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'experienced_hold'


@global_preferences_registry.register
class VeteranHold(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'veteran_hold'


@global_preferences_registry.register
class GuruHold(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'guru_hold'


@global_preferences_registry.register
class SadhuHold(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(0)
    name = 'sadhu_hold'


@global_preferences_registry.register
class IgnoredChannels(StringPreference):
    section = ranks
    default = ''
    name = 'ignored_channels'


@global_preferences_registry.register
class InvestorRoleID(StringPreference):
    section = ranks
    default = ''
    name = 'investor_role_id'


@global_preferences_registry.register
class TelegramRankMultiplier(DecimalPreference):
    section = ranks
    field_kwargs = {
        'max_digits': 5,
        'decimal_places': 2,
    }
    default = Decimal(1)
    name = 'telegram_rank_multiplier'


# games


@global_preferences_registry.register
class GamesChannelID(IntegerPreference):
    section = games
    default = -1
    name = 'games_channel_id'


@global_preferences_registry.register
class LotteryBlockInterval(IntegerPreference):
    section = games
    default = 1
    name = 'lottery_block_interval'


@global_preferences_registry.register
class LotteryTicketPrice(DecimalPreference):
    section = games
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(10)
    name = 'lottery_ticket_price'


@global_preferences_registry.register
class DiceJackpotRefill(DecimalPreference):
    section = games
    field_kwargs = {
        'max_digits': 16,
        'decimal_places': 8,
    }
    default = Decimal(1)
    name = 'dice_jackpot_refill'
