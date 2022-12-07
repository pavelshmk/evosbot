from django.views.generic import TemplateView

from app.models import Masternode
from evosbot.utils import client


class MasternodeMonitor(TemplateView):
    template_name = 'masternode_monitor.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mns_raw = {m['txhash']: m for m in client.api.masternode('list')}
        mns = Masternode.objects.filter(active=True)
        for mn in mns:
            try:
                mn.raw = mns_raw[mn.output_txid]
            except KeyError:
                mn.raw = {'status': 'NOT_FOUND'}
        ctx['mns'] = mns
        return ctx
