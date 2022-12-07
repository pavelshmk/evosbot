from app.models import TrackedMasternode
from evosbot.celery import app
from evosbot.utils import client, send_discord_message


@app.task(name='app.tasks.check_tracked_mns')
def check_tracked_mns():
    mns_raw = {m['addr']: m for m in client.api.masternode('list')}
    for mn in TrackedMasternode.objects.all():
        new_status = mns_raw.get(mn.addr, {'status': 'NOT_FOUND'})['status']
        if mn.last_check_status != new_status:  # mn.last_check_status != 'NOT_FOUND' and new_status == 'NOT_FOUND'
            mn.member.send_message('Status of masternode {} has changed to {}'.format(mn.addr, new_status))
        mn.last_check_status = new_status
        mn.save()
