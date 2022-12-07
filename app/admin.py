from admin_views.admin import AdminViews
from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin
from django.shortcuts import redirect

from .models import ServerMember, Broadcast, Masternode, MasternodeWithdraw, Unstaking, UserNode, MasternodeBalanceLog


@admin.register(ServerMember)
class ServerMemberAdmin(admin.ModelAdmin):
    list_display = 'id', 'name', 'xp', 'rank', 'confirmed_referrals'
    search_fields = 'name', 'id',


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = 'content', 'display_progress', 'finished', 'id',
    readonly_fields = 'progress', 'user_list', 'finished'


@admin.register(Masternode)
class MasterNodeAdmin(SortableAdminMixin, AdminViews):
    list_display = 'alias', 'address', 'active'
    admin_views = (
        ('Masternode monitor', 'mn_monitor'),
        ('Preferences', 'preferences'),
    )

    def mn_monitor(self, request, *args, **kwargs):
        return redirect('mn_monitor')

    def preferences(self, request, *args, **kwargs):
        return redirect('dp:global')


admin.site.register(MasternodeWithdraw)


@admin.register(UserNode)
class UserNodeAdmin(admin.ModelAdmin):
    list_display = 'id', 'member', 'address', 'pending',


@admin.register(Unstaking)
class UnstakingAdmin(admin.ModelAdmin):
    list_display = 'id', 'member', 'amount', 'fulfilled',


@admin.register(MasternodeBalanceLog)
class MasternodeBalanceLog(admin.ModelAdmin):
    ordering = '-datetime',
    list_display = 'member', 'delta', 'balance', 'datetime',
    search_fields = 'member__name', 'member__pk',
    date_hierarchy = 'datetime'
