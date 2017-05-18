import logging

from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms

from mailhole.models import (
    Peer, Message, SentMessage,
)


logger = logging.getLogger('mailhole')


class AuthenticationForm(auth_forms.AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.mailbox_set.exists() and not user.is_superuser:
            raise forms.ValidationError(
                'Du har ingen registrerede emailadresser. ' +
                'Kontakt %s' % settings.MANAGER_NAME)


class SubmitForm(forms.Form):
    key = forms.CharField()
    mail_from = forms.CharField()
    rcpt_to = forms.CharField()
    message_bytes = forms.FileField()

    def clean(self):
        key = self.cleaned_data.pop('key')
        self.cleaned_data['peer'] = Peer.validate(key)


class MessageListForm(forms.Form):
    def __init__(self, **kwargs):
        self.messages = list(kwargs.pop('queryset'))
        super().__init__(**kwargs)

        for message in self.messages:
            spam_k = 'spam_%s' % message.pk
            forward_k = 'forward_%s' % message.pk
            trash_k = 'trash_%s' % message.pk
            self.fields[spam_k] = forms.BooleanField(required=False)
            self.fields[forward_k] = forms.BooleanField(required=False)
            self.fields[trash_k] = forms.BooleanField(required=False)
            message.form = dict(spam=self[spam_k], forward=self[forward_k],
                                trash=self[trash_k])

    def clean(self):
        by_pk = {}
        for k, v in self.cleaned_data.items():
            if not v:
                continue
            try:
                mode, pk = k.split('_')
                pk = int(pk)
            except ValueError:
                continue
            if by_pk.setdefault(pk, mode) != mode:
                raise forms.ValidationError(
                    'Du må ikke markere mere end én boks ved en mail (%s %s %s)' %
                    (pk, by_pk[pk], mode))

    def save(self, user):
        for message in self.messages:
            spam_k = 'spam_%s' % message.pk
            forward_k = 'forward_%s' % message.pk
            trash_k = 'trash_%s' % message.pk
            if self.cleaned_data[spam_k]:
                logger.info('user:%s (%s) message:%s marked spam',
                            user.pk, user.username, message.pk)
                message.set_status(Message.SPAM, user=user)
                message.save()
            if self.cleaned_data[trash_k]:
                logger.info('user:%s (%s) message:%s marked trash',
                            user.pk, user.username, message.pk)
                message.set_status(Message.TRASH, user=user)
                message.save()
            if self.cleaned_data[forward_k]:
                # SentMessage.create_and_send logs the action
                SentMessage.create_and_send(message=message, user=user)
                message.set_status(Message.TRASH, user=user)
                message.save()


class MessageDetailForm(forms.Form):
    recipient = forms.EmailField(label='Modtager')
    send = forms.BooleanField(required=False)
    trash = forms.BooleanField(required=False)
    spam = forms.BooleanField(required=False)
