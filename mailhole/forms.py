import json
import logging

from django import forms
from django.conf import settings
from django.contrib.auth import forms as auth_forms

from mailhole.models import (
    Peer, Message, SentMessage, FilterRule,
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
    rcpt_tos = forms.CharField()
    message_bytes = forms.FileField()
    orig_mail_from = forms.CharField()
    orig_rcpt_to = forms.CharField()
    orig_message_bytes = forms.FileField()

    def clean_orig_rcpt_to(self):
        v = self.cleaned_data['orig_rcpt_to']
        try:
            orig_rcpt_to = json.loads(v)
        except ValueError:
            raise forms.ValidationError('Invalid JSON')
        if not isinstance(orig_rcpt_to, list):
            raise forms.ValidationError('JSON is not a list')
        if not all(isinstance(r, str) for r in orig_rcpt_to):
            raise forms.ValidationError('JSON is not a list of strs')
        return orig_rcpt_to

    def clean(self):
        key = self.cleaned_data.pop('key')
        self.cleaned_data['peer'] = Peer.validate(key)

    def save(self):
        self.cleaned_data['message_bytes'].open('rb')
        message_bytes = self.cleaned_data['message_bytes'].read()
        self.cleaned_data['orig_message_bytes'].open('rb')
        orig_message_bytes = self.cleaned_data['orig_message_bytes'].read()
        message = Message.create(
            peer=self.cleaned_data['peer'],
            mail_from=self.cleaned_data['mail_from'],
            rcpt_tos=self.cleaned_data['rcpt_tos'],
            message_bytes=message_bytes,
            orig_mail_from=self.cleaned_data['orig_mail_from'],
            orig_rcpt_to=self.cleaned_data['orig_rcpt_to'],
            orig_message_bytes=orig_message_bytes,
        )
        return message


class MessageListForm(forms.Form):
    def __init__(self, **kwargs):
        self.messages = list(kwargs.pop('queryset'))
        super().__init__(**kwargs)

        for message in self.messages:
            spam_k = 'spam_%s' % message.pk
            forward_k = 'forward_%s' % message.pk
            whitelist_k = 'whitelist_%s' % message.pk
            trash_k = 'trash_%s' % message.pk
            self.fields[spam_k] = forms.BooleanField(required=False)
            self.fields[forward_k] = forms.BooleanField(required=False)
            self.fields[whitelist_k] = forms.BooleanField(required=False)
            self.fields[trash_k] = forms.BooleanField(required=False)
            message.form = dict(
                spam=self[spam_k],
                forward=self[forward_k],
                whitelist=self[whitelist_k],
                trash=self[trash_k],
            )

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
                    'Du må ikke markere mere end én boks ved en mail ' +
                    '(%s %s %s)' % (pk, by_pk[pk], mode))

    def save(self, user):
        for message in self.messages:
            spam_k = 'spam_%s' % message.pk
            forward_k = 'forward_%s' % message.pk
            whitelist_k = 'whitelist_%s' % message.pk
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
            if self.cleaned_data[forward_k] or self.cleaned_data[whitelist_k]:
                # SentMessage.create_and_send logs the action
                SentMessage.create_and_send(message=message, user=user)
                message.set_status(Message.TRASH, user=user)
                message.save()
            if self.cleaned_data[whitelist_k]:
                # FilterRule.whitelist_from logs the action
                FilterRule.whitelist_from(message, user)


class MessageDetailForm(forms.Form):
    recipient = forms.EmailField(label='Modtager')
    send = forms.BooleanField(required=False)
    trash = forms.BooleanField(required=False)
    spam = forms.BooleanField(required=False)
