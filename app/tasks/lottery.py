from random import randint

from decimal import Decimal
from celery_once import QueueOnce
from django.db import transaction
from dynamic_preferences.registries import global_preferences_registry

from app.models import LotteryTicket, ServerMember
from evosbot.celery import app
from evosbot.utils import client, send_discord_message, tx_logger, fd, RPCClient

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.lottery', base=QueueOnce, once={'graceful': True})
def lottery():
    # if not global_preferences['internal__lottery_last_height']:
    #     global_preferences['internal__lottery_last_height'] = client.api.getblockcount()
    interval = global_preferences['games__lottery_block_interval']

    try:
        block_hash = client.api.getblockhash(global_preferences['internal__lottery_last_height'] + interval)
    except RPCClient.RPCException:
        return

    tickets = LotteryTicket.objects.all()
    if tickets.count():
        bots = []
        tickets_in_jackpot = int(global_preferences['internal__lottery_jackpot'] // global_preferences['games__lottery_ticket_price'])
        if tickets_in_jackpot < 10:
            for i in range(10 - tickets_in_jackpot):
                if global_preferences['general__feeder_balance'] < global_preferences['games__lottery_ticket_price']:
                    break
                global_preferences['general__feeder_balance'] -= global_preferences['games__lottery_ticket_price']
                global_preferences['internal__lottery_jackpot'] += global_preferences['games__lottery_ticket_price']
                bots.append(randint(0, 255))

        hex_value = block_hash[-2:]
        value = bytes.fromhex(hex_value)[0]
        winning_tickets = tickets.filter(value=value)
        winners = winning_tickets.count()
        bot_winners = len(list(filter(lambda i: i == value, bots)))
        if not winners and not bot_winners:
            send_discord_message(global_preferences['games__games_channel_id'],
                                 'Lottery results\n'
                                 'Block hash: `{}`\n'
                                 'Winning value: 0x{} = {}    '
                                 '**No winners**\n'
                                 'Jackpot of {} was preserved'.format(block_hash, hex_value, value,
                                                                      fd(global_preferences['internal__lottery_jackpot'])))
        else:
            win_amount = global_preferences['internal__lottery_jackpot'] / (winners + bot_winners)
            winner_members = set()
            for ticket in winning_tickets:  # type: LotteryTicket
                with transaction.atomic():
                    member = ServerMember.objects.select_for_update().get(pk=ticket.member_id)
                    member.balance += win_amount
                    member.save(update_fields=('balance',))
                    tx_logger.warning('LOTTERY,{},+{:.8f}'.format(member, win_amount))
                    winner_members.add(member)
            global_preferences['general__feeder_balance'] += bot_winners * win_amount

            send_discord_message(global_preferences['games__games_channel_id'],
                                 'Lottery results\n'
                                 'Block hash: `{}`\n'
                                 'Winning value: 0x{} = {}    '
                                 '{} **winners:** {}\n'
                                 'Win amounts: {} SOVE'.format(
                                     block_hash, hex_value, value, winners + bot_winners,
                                     ', '.join([t.member.name for t in winning_tickets] + (['Bot'] * bot_winners)),
                                     fd(win_amount)
                                 ))

            global_preferences['internal__lottery_jackpot'] = Decimal(0)
        tickets.delete()
    global_preferences['internal__lottery_last_height'] = client.api.getblockcount()
