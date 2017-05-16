from django.contrib import admin
from mailhole.models import (
    Mailbox, Peer, Message, SentMessage,
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
