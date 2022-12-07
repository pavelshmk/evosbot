import logging
import json
import traceback
from time import sleep
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember, AirdropTask
from evosbot.celery import app
from evosbot.utils import tx_logger, fd, get_member

global_preferences = global_preferences_registry.manager()


@app.task(name='app.tasks.airdrop')
def airdrop(size):
    AIRDROP_COUNTS = {
        'small': global_preferences['small_airdrops__count'],
        'medium': global_preferences['medium_airdrops__count'],
        'large': global_preferences['large_airdrops__count'],
    }

    AIRDROP_AMOUNTS = {
        'small': {
            ServerMember.Rank.JUNIOR: global_preferences['small_airdrops__junior'],
            ServerMember.Rank.EXPERIENCED: global_preferences['small_airdrops__experienced'],
            ServerMember.Rank.VETERAN: global_preferences['small_airdrops__veteran'],
            ServerMember.Rank.GURU: global_preferences['small_airdrops__guru'],
            ServerMember.Rank.SADHU: global_preferences['small_airdrops__sadhu'],
        },
        'medium': {
            ServerMember.Rank.JUNIOR: global_preferences['medium_airdrops__junior'],
            ServerMember.Rank.EXPERIENCED: global_preferences['medium_airdrops__experienced'],
            ServerMember.Rank.VETERAN: global_preferences['medium_airdrops__veteran'],
            ServerMember.Rank.GURU: global_preferences['medium_airdrops__guru'],
            ServerMember.Rank.SADHU: global_preferences['medium_airdrops__sadhu'],
        },
        'large': {
            ServerMember.Rank.JUNIOR: global_preferences['large_airdrops__junior'],
            ServerMember.Rank.EXPERIENCED: global_preferences['large_airdrops__experienced'],
            ServerMember.Rank.VETERAN: global_preferences['large_airdrops__veteran'],
            ServerMember.Rank.GURU: global_preferences['large_airdrops__guru'],
            ServerMember.Rank.SADHU: global_preferences['large_airdrops__sadhu'],
        },
    }

    HOLD_FACTOR = {
        'amount': {
            ServerMember.Rank.JUNIOR: global_preferences['ranks__junior_hold'],
            ServerMember.Rank.EXPERIENCED: global_preferences['ranks__experienced_hold'],
            ServerMember.Rank.VETERAN: global_preferences['ranks__veteran_hold'],
            ServerMember.Rank.GURU: global_preferences['ranks__guru_hold'],
            ServerMember.Rank.SADHU: global_preferences['ranks__sadhu_hold'],
        },
        'factor': {
            ServerMember.Rank.JUNIOR: Decimal(1),
            ServerMember.Rank.EXPERIENCED: Decimal(.5),
            ServerMember.Rank.VETERAN: Decimal(.4),
            ServerMember.Rank.GURU: Decimal(.6),
            ServerMember.Rank.SADHU: Decimal(.4),
        },
    }

    try:
        tasks = []

        with open('/tmp/evos_online_with_roles.json') as f:
            members = json.load(f)  # type: dict
        # remove muted users
        for mid, roles in members.copy().items():
            if global_preferences['ranks__muted_role_id'] in roles:
                del members[mid]
        for rank in [ServerMember.Rank.JUNIOR, ServerMember.Rank.EXPERIENCED, ServerMember.Rank.VETERAN,
                     ServerMember.Rank.GURU, ServerMember.Rank.SADHU]:
            amount = AIRDROP_AMOUNTS[size][rank]
            if not amount:
                continue
            rank_qs = ServerMember.objects.filter(Q(pk__in=members.keys()) | Q(pk__lt=0), rank=rank).distinct()\
                .order_by('?')[:AIRDROP_COUNTS[size]].values_list('pk', flat=True)
            for pk in rank_qs:
                holding_factor = Decimal(1.0)
                if amount > global_preferences['general__feeder_balance']:
                    continue
                with transaction.atomic():
                    sm = ServerMember.objects.select_for_update().get(pk=pk)
                    if sm.staking_balance + sm.balance + sm.masternode_balance < HOLD_FACTOR['amount'][rank]:
                        holding_factor = HOLD_FACTOR['factor'][rank]
                    delta = amount * holding_factor
                    if pk < 0:
                        delta *= global_preferences['general__telegram_airdrop_multiplier']
                    tasks.append(AirdropTask(member=sm, amount=delta))
        AirdropTask.objects.bulk_create(tasks)
    except:
        traceback.print_exc()
