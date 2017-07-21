from django.contrib import admin
from django.db.models import Count, Max
from django.utils import html
from django.core.urlresolvers import reverse
from mailhole.models import (
    Mailbox, Peer, Message, SentMessage, FilterRule,
    MonitorMessage,
)


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    list_display = ('name', 'reader_count', 'messages',
                    'most_recent_message', 'created_time')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            messages=Count('message', distinct=True),
            most_recent_message=Max('message__created_time'),
            reader_count=Count('readers', distinct=True),
        )
        return qs

    def reader_count(self, o):
        return o.reader_count

    def messages(self, o):
        return html.format_html(
            '<a href="{}">{}</a>',
            reverse('mailbox_detail', kwargs=dict(mailbox=o.name)),
            o.messages)

    def most_recent_message(self, o):
        return o.most_recent_message

    reader_count.admin_order_field = 'reader_count'
    messages.admin_order_field = 'messages'
    most_recent_message.admin_order_field = 'most_recent_message'


@admin.register(Peer)
class PeerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'default_reader_count')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            default_reader_count=Count('default_readers'),
        )
        return qs

    def default_reader_count(self, o):
        return o.default_reader_count

    default_reader_count.admin_order_field = 'default_reader_count'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'created_time', 'get_status', 'from_', 'to_as_html')
    list_display_links = ('subject',)

    list_filter = ('status_by',)

    def get_status(self, o):
        by = o.status_by or o.filtered_by
        s = [o.get_status_display(),
             o.status_on,
             by and 'af %s' % by]
        return ' '.join(map(str, filter(None, s)))


@admin.register(SentMessage)
class SentMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'recipient', 'created_time', 'created_by')

    list_filter = ('created_by',)

    def subject(self, o):
        return o.message.subject()


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


@admin.register(MonitorMessage)
class MonitorMessageAdmin(admin.ModelAdmin):
    list_display = ('created_time', 'user', 'inbox_size', 'age_days')
