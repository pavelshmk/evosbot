import random
from decimal import getcontext

from django.db import transaction
from telegram.utils.helpers import mention_markdown

from app.models import TGRainTask, ServerMember
from evosbot.celery import app
from evosbot.utils import tx_logger, fd


@app.task(name='app.tasks.execute_tgrain')
def execute_tgrain(task_id):
    from app.bot.telegram import get_bot
    getcontext().prec = 8
    with transaction.atomic():
        t = TGRainTask.objects.filter(finished=False).select_for_update().get(pk=task_id)  # type: TGRainTask
        if not t.users:
            t.finished = True
            t.save()
            t.member.balance += t.amount
            t.member.save(update_fields=('balance',))
            tx_logger.warning('TGRAIN_RETURN,{},{:.8f}'.format(t.member, t.amount))
            get_bot().edit_message_text(chat_id=t.chat_id,
                                        message_id=t.message_id,
                                        text='Nobody participated in this rain', reply_markup=None)
            return t.member.send_message('No users registered, funds were returned to your balance')
        users = set(t.users.split('|'))
        users -= {''}
        users = list(users)
        if len(users) > t.users_cnt:
            users = random.choices(users, k=t.users_cnt)
        reward_each = t.amount / len(users)
        awarded_users = []
        for uid in users:
            try:
                sm = ServerMember.objects.select_for_update().get(pk=int(uid) - 10**10)
                sm.balance += reward_each
                sm.save(update_fields=('balance',))
                awarded_users.append(mention_markdown(int(uid), sm.name))
                tx_logger.warning('TGRAIN,{},{:.8f}'.format(sm, reward_each))
                not sm.noinform and sm.send_message('You have been rained the amount of {} SOVE'.format(fd(reward_each)))
            except:
                pass
        get_bot().edit_message_text(chat_id=t.chat_id, message_id=t.message_id,
                                    text='Rain was finished\n\nAwarded users:\n' + '\n'.join(awarded_users),
                                    reply_markup=None, parse_mode='markdown')
        t.finished = True
        t.save()
