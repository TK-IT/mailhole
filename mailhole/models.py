import email
import logging

import django.core.mail
from django.core.mail import EmailMessage
from django.core.mail.message import MIMEMixin
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.files.base import ContentFile
from django.utils import html, timezone

from mailhole.utils import html_to_plain, decode_any_header
import email.utils


logger = logging.getLogger('mailhole')


class Mailbox(models.Model):
    '''
    An email user whose emails end up in our app.
    '''
    # NOTE: This requires MySQL database charset utf8 instead of utf8mb4.
    email = models.EmailField(unique=True)
    created_time = models.DateTimeField(auto_now_add=True)
    readers = models.ManyToManyField(User)

    def __str__(self):
        return self.email

    @classmethod
    def get_or_create(cls, email, peer=None):
        '''
        If peer is given and no Mailbox with email exists, readers are added
        based on peer.default_readers.
        '''
        email = email.lower()
        try:
            return cls.objects.get(email=email)
        except cls.DoesNotExist:
            mailbox = cls(email=email)
            mailbox.clean()
            mailbox.save()
            logger.info('mailbox:%s:%s created by peer:%s:%s',
                        mailbox.pk, mailbox.email, peer and peer.pk, peer)
            if peer is not None:
                for r in peer.default_readers.all():
                    mailbox.readers.add(r)
            return mailbox

    @classmethod
    def owned_by_user(cls, user):
        return cls.objects.filter(readers=user)

    @classmethod
    def visible_to_user(cls, user):
        if user.is_superuser:
            return cls.objects.all()
        else:
            return cls.objects.filter(readers=user)

    def folders(self):
        for key, label in Message.STATUS:
            url = reverse('mailbox_message_list',
                          kwargs=dict(mailbox=self.email, status=key))
            qs = self.message_set.filter(status=key)
            yield key, label, url, qs

    def get_absolute_url(self):
        return reverse('mailbox_detail',
                       kwargs=dict(mailbox=self.email))


class Peer(models.Model):
    '''
    A front-end SMTP server who receives emails for our mailboxes.
    '''
    key = models.CharField(max_length=256)
    default_readers = models.ManyToManyField(User, blank=True)
    slug = models.CharField(max_length=30)

    def __str__(self):
        return self.slug

    @classmethod
    def validate(cls, key):
        try:
            return cls.objects.get(key=key)
        except cls.DoesNotExist:
            raise ValidationError('Invalid peer key')


class DjangoMessage(MIMEMixin, email.message.Message):
    pass


def message_upload_to(message: 'Message', filename):
    return 'messages/{peer}/{mailbox}/{now}.mail'.format(
        peer=message.peer.slug,
        mailbox=message.mailbox.email,
        now=timezone.now().isoformat().replace(':', '_'),
    )


class Message(models.Model):
    '''
    A message received by a Peer for one of our mailboxes.
    '''
    INBOX = 'inbox'
    SPAM = 'spam'
    TRASH = 'trash'

    STATUS = [
        (INBOX, 'Indbakke'),
        (SPAM, 'Spam'),
        (TRASH, 'Slettet'),
    ]
    mailbox = models.ForeignKey(Mailbox, on_delete=models.CASCADE)
    peer = models.ForeignKey(Peer, on_delete=models.CASCADE)
    # RFC 5321 §4.5.3.1.3 Max sender/recipient length is 256 octets
    mail_from = models.CharField(max_length=256)
    rcpt_to = models.CharField(max_length=256)
    message_file = models.FileField(upload_to=message_upload_to)
    headers = models.TextField()
    body_text_bytes = models.BinaryField(null=True)
    created_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS,
                              default=INBOX)
    status_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                  blank=True, null=True)
    status_on = models.DateTimeField(blank=True, null=True)

    @classmethod
    def create(cls, peer, mail_from, rcpt_to, message_bytes):
        # Mailbox.get_or_create logs the create_mailbox action
        mailbox = Mailbox.get_or_create(rcpt_to, peer)
        message = cls(mailbox=mailbox, peer=peer,
                      mail_from=mail_from,
                      rcpt_to=rcpt_to,
                      message_file=ContentFile(message_bytes),
                      status=cls.INBOX)
        message.extract_message_data()
        message.clean()
        message.save()
        return message

    @property
    def parsed_headers(self):
        try:
            return self._parsed_headers
        except AttributeError:
            self._parsed_headers = (
                email.message_from_string(self.headers, DjangoMessage))
            return self._parsed_headers

    @property
    def message(self):
        try:
            return self._message
        except AttributeError:
            self.message_file.open('rb')
            self._message = (
                email.message_from_binary_file(self.message_file, DjangoMessage))
            self.message_file.close()
            return self._message

    @staticmethod
    def _extract_message_data(self):
        '''
        Set self.headers and self.body_text from self.message_file.
        '''
        self.message_file.open('rb')
        message_bytes = self.message_file.read()
        try:
            header_end = message_bytes.index(b'\r\n\r\n') + 4
        except ValueError:
            raise ValidationError('Message must contain CR LF CR LF')
        try:
            self.headers = message_bytes[:header_end].decode('ascii')
        except UnicodeDecodeError:
            raise ValidationError('Message headers must be ASCII')
        try:
            message = email.message_from_bytes(message_bytes, DjangoMessage)
        except Exception:
            raise ValidationError('Could not parse message')
        self.body_text = Message._get_body_text(self, message)
        self.message_file.close()

    def extract_message_data(self):
        self._extract_message_data(self)

    @property
    def body_text(self):
        if self.body_text_bytes is not None:
            return self.body_text_bytes.decode('utf8')

    @body_text.setter
    def body_text(self, value):
        self.body_text_bytes = None if value is None else value.encode('utf8')

    def from_(self):
        return str(decode_any_header(self.parsed_headers.get('From') or ''))

    def to_people(self):
        keys = ('To', 'Cc')
        values = [v for k in keys
                  for v in (self.parsed_headers.get_all(k) or ())]
        parsed = email.utils.getaddresses(values)
        for realname, address in parsed:
            realname = str(decode_any_header(realname))
            if realname:
                abbreviated = realname.split()[0]
            else:
                abbreviated = address.split('@')[0]
            formatted = '%s <%s>' % (realname, address)
            yield formatted, abbreviated

    def to_as_html(self):
        return html.format_html_join(', ', '<span title="{}">{}</span>',
                                     self.to_people())

    def subject(self):
        return str(decode_any_header(self.parsed_headers.get('Subject') or ''))

    def get_absolute_url(self):
        return reverse('message_detail',
                       kwargs=dict(mailbox=self.mailbox.email,
                                   pk=self.pk))

    @staticmethod
    def _get_body_text(self, message):
        try:
            text_part = next(part for part in message.walk()
                             if part.get_content_maintype() == 'text')
        except StopIteration:
            return
        payload_bytes = text_part.get_payload(decode=True)
        charset = text_part.get_content_charset('utf8')
        try:
            payload = payload_bytes.decode(charset, errors='replace')
        except Exception:
            return 'Failed to decode as %r' % (charset,)
        if text_part.get_content_subtype() == 'html':
            payload = html_to_plain(payload)
        return payload

    @classmethod
    def status_display(cls, status):
        o = cls(status=status)
        return o.get_status_display()

    def set_status(self, status, user):
        self.status = status
        self.status_by = user
        self.status_on = timezone.now()


class UnsafeEmailMessage(EmailMessage):
    def __init__(self, message, recipient):
        if not isinstance(message, email.message.Message):
            raise TypeError(type(message))
        super().__init__()
        self._recipient = recipient
        self._message = message

    def message(self):
        return self._message

    def recipients(self):
        return (self._recipient,)


class SentMessage(models.Model):
    '''
    This object logs the fact that a message was forwarded to our user.
    '''
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    recipient = models.CharField(max_length=256)
    created_time = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=False)

    @classmethod
    def create_and_send(cls, message, user, recipient=None):
        if recipient is None:
            recipient = message.rcpt_to
        logger.info('user:%s (%s) message:%s forwarded to <%s>',
                    user.pk, user.username, message.pk, recipient)
        sent_message = SentMessage(message=message,
                                   recipient=recipient,
                                   created_by=user)
        sent_message.clean()
        email_backend = django.core.mail.get_connection()
        email_message = UnsafeEmailMessage(message.message, recipient)
        email_backend.send_messages([email_message])
        sent_message.save()
