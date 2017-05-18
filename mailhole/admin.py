from django.contrib import admin
from django.db.models import Count
from mailhole.models import (
    Mailbox, Peer, Message, SentMessage, FilterRule,
)


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    pass


@admin.register(Peer)
class PeerAdmin(admin.ModelAdmin):
    pass


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass


@admin.register(SentMessage)
class SentMessageAdmin(admin.ModelAdmin):
    pass


@admin.register(FilterRule)
class FilterRuleAdmin(admin.ModelAdmin):
    list_display = ('order', 'kind', 'pattern', 'action', 'message_count')
    list_display_links = ('pattern',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(message_count=Count('message'))
        return qs

    def message_count(self, o):
        return o.message_count

    message_count.admin_order_field = 'message_count'
