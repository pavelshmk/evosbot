import logging
from time import sleep
from datetime import timedelta

from celery_once import QueueOnce
from django.db.models import F, Q
from django.utils.timezone import now
from dynamic_preferences.registries import global_preferences_registry

from app.models import ServerMember, UpdateRoleTask
from evosbot.celery import app
from evosbot.utils import set_roles, get_member, tx_logger, rank_logger, send_discord_message

global_preferences = global_preferences_registry.manager()
Rank = ServerMember.Rank


@app.task(name='app.tasks.update_ranks', base=QueueOnce, once={'graceful': True})
def update_ranks():
    new_promotes = {}
    new_demotes = {}

    telegram_multiplier = global_preferences['ranks__telegram_rank_multiplier']

    # promote
    qs = ServerMember.objects.filter(
        pk__gte=0,
        rank=Rank.BRAND_NEW,
        xp__gt=0,
        activity_counter__gte=60*24 * telegram_multiplier
    ) | ServerMember.objects.filter(
        pk__lt=0,
        rank=Rank.BRAND_NEW,
        xp__gt=0,
        activity_counter__gte=60*24 * telegram_multiplier
    )
    for sm in qs:
        referrer = sm.referrer
        if referrer:
            lvl1_bonus = global_preferences['ranks__referrer_lvl1_bonus']
            if lvl1_bonus and global_preferences['general__feeder_balance'] >= lvl1_bonus:
                global_preferences['general__feeder_balance'] -= lvl1_bonus
                referrer.balance += lvl1_bonus
                referrer.save(update_fields=('balance',))
                tx_logger.warning('REFERRER_LVL1,{},+{:.8f}'.format(sm, lvl1_bonus))
                sm.send_message('You have been awarded {:.8f} for inviting a user (level 1)'.format(lvl1_bonus))
            if referrer.referrer:
                lvl2_bonus = global_preferences['ranks__referrer_lvl2_bonus']
                if lvl2_bonus and global_preferences['general__feeder_balance'] >= lvl2_bonus:
                    global_preferences['general__feeder_balance'] -= lvl2_bonus
                    referrer.referrer.balance += lvl2_bonus
                    referrer.referrer.save(update_fields=('balance',))
                    tx_logger.warning('REFERRER_LVL2,{},+{:.8f}'.format(sm, lvl2_bonus))
                    sm.send_message('You have been awarded {:.8f} for inviting a user (level 2)'.format(lvl2_bonus))
                if referrer.referrer.referrer:
                    lvl3_bonus = global_preferences['ranks__referrer_lvl3_bonus']
                    if lvl3_bonus and global_preferences['general__feeder_balance'] >= lvl3_bonus:
                        global_preferences['general__feeder_balance'] -= lvl3_bonus
                        referrer.referrer.referrer.balance += lvl3_bonus
                        referrer.referrer.referrer.save(update_fields=('balance',))
                        tx_logger.warning('REFERRER_LVL3,{},+{:.8f}'.format(sm, lvl3_bonus))
                        sm.send_message('You have been awarded {:.8f} for inviting a user (level 3)'.format(lvl3_bonus))
    new_promotes.setdefault(Rank.NEWBIE, []).extend(qs)
    qs.update(
        rank=Rank.NEWBIE,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        pk__gte=0,
        rank=Rank.NEWBIE,
        xp__gte=global_preferences['ranks__junior_xp'],
        activity_counter__gte=60*24*3
    )
    qs_tg = ServerMember.objects.filter(
        pk__lt=0,
        rank=Rank.NEWBIE,
        xp__gte=global_preferences['ranks__junior_xp'] * telegram_multiplier,
        activity_counter__gte=60*24*3 * telegram_multiplier
    )
    new_promotes.setdefault(Rank.JUNIOR, []).extend(qs | qs_tg)
    qs.update(
        rank=Rank.JUNIOR,
        xp=F('xp') - global_preferences['ranks__junior_xp'],
        activity_counter=F('activity_counter') - 60*24*3,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )
    qs_tg.update(
        rank=Rank.JUNIOR,
        xp=F('xp') - global_preferences['ranks__junior_xp'] * telegram_multiplier,
        activity_counter=F('activity_counter') - 60*24*3 * telegram_multiplier,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        pk__gte=0,
        rank=Rank.JUNIOR,
        xp__gte=global_preferences['ranks__experienced_xp'],
        activity_counter__gte=60*24*5
    )
    qs_tg = ServerMember.objects.filter(
        pk__lt=0,
        rank=Rank.JUNIOR,
        xp__gte=global_preferences['ranks__experienced_xp'] * telegram_multiplier,
        activity_counter__gte=60*24*5 * telegram_multiplier
    )
    new_promotes.setdefault(Rank.EXPERIENCED, []).extend(qs | qs_tg)
    qs.update(
        rank=Rank.EXPERIENCED,
        xp=F('xp') - global_preferences['ranks__experienced_xp'],
        activity_counter=F('activity_counter') - 60*24*5,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )
    qs_tg.update(
        rank=Rank.EXPERIENCED,
        xp=F('xp') - global_preferences['ranks__experienced_xp'] * telegram_multiplier,
        activity_counter=F('activity_counter') - 60*24*5 * telegram_multiplier,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        pk__gte=0,
        rank=Rank.EXPERIENCED,
        xp__gte=global_preferences['ranks__veteran_xp'],
        activity_counter__gte=60*24*8
    )
    qs_tg = ServerMember.objects.filter(
        pk__lt=0,
        rank=Rank.EXPERIENCED,
        xp__gte=global_preferences['ranks__veteran_xp'] * telegram_multiplier,
        activity_counter__gte=60*24*8 * telegram_multiplier
    )
    new_promotes.setdefault(Rank.VETERAN, []).extend(qs | qs_tg)
    qs.update(
        rank=Rank.VETERAN,
        xp=F('xp') - global_preferences['ranks__veteran_xp'],
        activity_counter=F('activity_counter') - 60*24*8,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )
    qs_tg.update(
        rank=Rank.VETERAN,
        xp=F('xp') - global_preferences['ranks__veteran_xp'] * telegram_multiplier,
        activity_counter=F('activity_counter') - 60*24*8 * telegram_multiplier,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        pk__gte=0,
        rank=Rank.VETERAN,
        xp__gte=global_preferences['ranks__guru_xp'],
        activity_counter__gte=60*24*14
    )
    qs_tg = ServerMember.objects.filter(
        pk__lt=0,
        rank=Rank.VETERAN,
        xp__gte=global_preferences['ranks__guru_xp'] * telegram_multiplier,
        activity_counter__gte=60*24*14 * telegram_multiplier
    )
    new_promotes.setdefault(Rank.GURU, []).extend(qs | qs_tg)
    qs.update(
        rank=Rank.GURU,
        xp=F('xp') - global_preferences['ranks__guru_xp'],
        activity_counter=F('activity_counter') - 60*24*14,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )
    qs_tg.update(
        rank=Rank.GURU,
        xp=F('xp') - global_preferences['ranks__guru_xp'] * telegram_multiplier,
        activity_counter=F('activity_counter') - 60*24*14 * telegram_multiplier,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    # demote
    qs = ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__experienced_xp'] / 5) | Q(activity_counter__lt=60*24),
        pk__gte=0,
        rank=Rank.JUNIOR,
        last_rank_change__lt=now() - timedelta(4)
    ) | ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__experienced_xp'] * telegram_multiplier / 5) | Q(activity_counter__lt=60*24 * telegram_multiplier),
        pk__lt=0,
        rank=Rank.JUNIOR,
        last_rank_change__lt=now() - timedelta(4)
    )
    new_demotes.setdefault(Rank.NEWBIE, []).extend(qs)
    qs.update(
        rank=Rank.NEWBIE,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__veteran_xp'] / 6) | Q(activity_counter__lt=60*24),
        pk__gte=0,
        rank=Rank.EXPERIENCED,
        last_rank_change__lt=now() - timedelta(6)
    ) | ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__veteran_xp'] * telegram_multiplier / 6) | Q(activity_counter__lt=60*24 * telegram_multiplier),
        pk__lt=0,
        rank=Rank.EXPERIENCED,
        last_rank_change__lt=now() - timedelta(6)
    )
    new_demotes.setdefault(Rank.JUNIOR, []).extend(qs)
    qs.update(
        rank=Rank.JUNIOR,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__guru_xp'] / 10) | Q(activity_counter__lt=60*24),
        pk__gte=0,
        rank=Rank.VETERAN,
        last_rank_change__lt=now() - timedelta(8)
    ) | ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__guru_xp'] * telegram_multiplier / 10) | Q(activity_counter__lt=60*24 * telegram_multiplier),
        pk__lt=0,
        rank=Rank.VETERAN,
        last_rank_change__lt=now() - timedelta(8)
    )
    new_demotes.setdefault(Rank.EXPERIENCED, []).extend(qs)
    qs.update(
        rank=Rank.EXPERIENCED,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    qs = ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__sadhu_xp'] / 20) | Q(activity_counter__lt=60*24),
        pk__gte=0,
        rank=Rank.GURU,
        last_rank_change__lt=now() - timedelta(10)
    ) | ServerMember.objects.filter(
        Q(xp__lt=global_preferences['ranks__sadhu_xp'] * telegram_multiplier / 20) | Q(activity_counter__lt=60*24 * telegram_multiplier),
        pk__lt=0,
        rank=Rank.GURU,
        last_rank_change__lt=now() - timedelta(10)
    )
    new_demotes.setdefault(Rank.VETERAN, []).extend(qs)
    qs.update(
        rank=Rank.VETERAN,
        last_rank_change=now(),
        last_forced_activity_update=now()
    )

    ServerMember.objects\
        .filter(rank=Rank.NEWBIE, last_forced_activity_update__lt=now() - timedelta(30))\
        .update(last_forced_activity_update=now(), activity_counter=F('activity_counter') / 2, xp=F('xp') / 2)

    ServerMember.objects\
        .filter(rank=Rank.JUNIOR, last_forced_activity_update__lt=now() - timedelta(30))\
        .update(last_forced_activity_update=now(), activity_counter=F('activity_counter') / 2, xp=F('xp') / 2)

    ServerMember.objects\
        .filter(rank=Rank.EXPERIENCED, last_forced_activity_update__lt=now() - timedelta(30))\
        .update(last_forced_activity_update=now(), activity_counter=F('activity_counter') / 2, xp=F('xp') / 2)

    ServerMember.objects\
        .filter(rank=Rank.VETERAN, last_forced_activity_update__lt=now() - timedelta(30))\
        .update(last_forced_activity_update=now(), activity_counter=F('activity_counter') / 2, xp=F('xp') / 2)

    role_ids = {
        Rank.NEWBIE: global_preferences['ranks__newbie_role_id'],
        Rank.JUNIOR: global_preferences['ranks__junior_role_id'],
        Rank.EXPERIENCED: global_preferences['ranks__experienced_role_id'],
        Rank.VETERAN: global_preferences['ranks__veteran_role_id'],
        Rank.GURU: global_preferences['ranks__guru_role_id'],
    }

    for is_promote, d in ((True, new_promotes), (False, new_demotes)):
        for rank, members in d.items():
            if not role_ids[rank]:
                continue
            for member in members:  # type: ServerMember
                member.refresh_from_db(fields=('rank',))
                if member.pk > 0:
                    UpdateRoleTask.objects.create(member=member,
                                                  remove_roles='|'.join(role_ids.values()),
                                                  add_roles=role_ids[rank])
                if is_promote:
                    rank_logger.info('PROMOTE,{},{},{},{}'.format(
                        member.pk,
                        member.get_rank_display(),
                        member.activity_counter,
                        member.xp
                    ))
                    send_discord_message(
                        global_preferences['ranks__rank_channel'],
                        '<@{}> has been promoted to rank "{}" (activity: {} hrs, xp: {})'.format(
                            member.pk,
                            member.get_rank_display(),
                            int(member.activity_counter / 60),
                            member.xp
                        )
                    )
                else:
                    rank_logger.info('DEMOTE,{},{},{},{}'.format(
                        member.pk,
                        member.get_rank_display(),
                        member.activity_counter,
                        member.xp
                    ))
                    send_discord_message(
                        global_preferences['ranks__rank_channel'],
                        '<@{}> has been demoted to rank "{}" (activity: {} hrs, xp: {})'.format(
                            member.pk,
                            member.get_rank_display(),
                            int(member.activity_counter / 60),
                            member.xp
                        )
                    )
