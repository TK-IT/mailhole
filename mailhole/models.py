import re
import email
import logging

import django.core.mail
from django.core.mail import EmailMessage
from django.core.mail.message import MIMEMixin
from django.db import models
from django.db.models import Max
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.files.base import ContentFile
from django.utils import html, timezone

from mailhole.utils import html_to_plain, decode_any_header
import mailhole.policy
import email.utils


logger = logging.getLogger('mailhole')


class Mailbox(models.Model):
    '''
    An email user whose emails end up in our app.
    '''

    HOLD = 'hold'
    FORWARD = 'forward'
    ACTION = [
        (HOLD, 'Tilbagehold'),
        (FORWARD, 'Videresend'),
    ]

    name = models.CharField(max_length=100, null=True)
    created_time = models.DateTimeField(auto_now_add=True)
    readers = models.ManyToManyField(User)
    default_action = models.CharField(max_length=10, choices=ACTION,
                                      default=HOLD)

    def __str__(self):
        return self.name

    @classmethod
    def get_or_create(cls, orig_rcpt_tos, peer=None):
        '''
        If peer is given and no Mailbox with email exists, readers are added
        based on peer.default_readers.
        '''
        if not isinstance(orig_rcpt_tos, list):
            raise ValueError('orig_rcpt_tos must be a list, not a %r' %
                             (type(orig_rcpt_tos),))
        if not all(r.count('@') == 1 for r in orig_rcpt_tos):
            raise ValueError('Invalid email addresses: %r' % (orig_rcpt_tos,))
        domains = set(domain.lower() for r in orig_rcpt_tos
                      for localpart, domain in [r.split('@')])
        if len(domains) != 1:
            raise ValueError(domains)
        domain, = domains
        try:
            return cls.objects.get(name=domain)
        except cls.DoesNotExist:
            mailbox = cls(name=domain)
            mailbox.clean()
            mailbox.save()
            logger.info('mailbox:%s:%s created by peer:%s:%s',
                        mailbox.pk, mailbox.name, peer and peer.pk, peer)
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
                          kwargs=dict(mailbox=self.name, status=key))
            qs = self.message_set.filter(status=key)
            yield key, label, url, qs

    def get_absolute_url(self):
        return reverse('mailbox_detail',
                       kwargs=dict(mailbox=self.name))


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


class FilterRule(models.Model):
    SUBJECT_MATCH = 'subject_match'
    SENDER_MATCH = 'sender_match'
    HEADER_MATCH = 'header_match'

    KIND = [
        (SUBJECT_MATCH, 'Subject regex search'),
        (SENDER_MATCH, 'Sender regex search'),
        (HEADER_MATCH, 'Header regex match'),
    ]

    MARK_SPAM = 'spam'
    FORWARD = 'forward'

    ACTION = [
        (MARK_SPAM, 'Markér som spam'),
        (FORWARD, 'Videresend'),
    ]

    order = models.IntegerField()
    peer = models.ForeignKey(Peer, on_delete=models.CASCADE,
                             blank=True, null=True,
                             help_text='Blank betyder "alle servere"')
    kind = models.CharField(max_length=30, choices=KIND)
    pattern = models.CharField(max_length=200)
    examples = models.TextField(
        help_text='Eksempel-matches, én per linje. Linjer der starter med ' +
                  'udråbstegn (!) er negative eksempler. Kommentarer ' +
                  'starter med hegn (#).')
    action = models.CharField(max_length=30, choices=ACTION)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   blank=False, null=True)
    created_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return '%s (%s)' % (self.pattern, self.get_kind_display())

    class Meta:
        ordering = ['order']

    def clean(self):
        if self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as exn:
                raise ValidationError('Ugyldig pattern: %s' % (exn,))
            failed = []
            for line in self.examples.splitlines():
                if not line or line.startswith('#'):
                    continue
                if line.startswith('!'):
                    example = line[1:]
                    expect = False
                else:
                    example = line
                    expect = True
                got = self.match_string(example)
                if got is not expect:
                    failed.append(line)
            if failed:
                raise ValidationError('Eksempel fejlede: %r' % (failed,))

    @classmethod
    def filter_message(cls, filters, message):
        '''
        messages is a Message object. filters is a sequence of FilterRules.

        Returns the first filter that matches, if any.

        Filters are applied in the order given and stops at first match.
        '''
        sender = message.orig_mail_from
        headers = message.parsed_headers
        subject = headers.get('Subject') or ''
        header_strs = ['%s: %s' % (k, decode_any_header(v))
                       for k, v in headers.items()]
        for filter in filters:
            if filter._match_message(sender, subject, header_strs):
                return filter

    def _match_message(self, sender, subject, header_strs):
        if self.kind == FilterRule.SUBJECT_MATCH:
            return self.match_string(subject)
        elif self.kind == FilterRule.SENDER_MATCH:
            return self.match_string(sender)
        elif self.kind == FilterRule.HEADER_MATCH:
            return any(map(self.match_string, header_strs))
        else:
            raise Exception(self.kind)

    def match_string(self, text):
        return bool(re.search(self.pattern, text, re.I))

    @classmethod
    def whitelist_from(cls, message, user):
        max_order = cls.objects.all().aggregate(order=Max('order'))['order']
        if max_order is None:
            # No objects exist yet
            max_order = 0
        order = max_order + 1
        from_ = message.from_()
        filter = cls(order=order,
                     kind=FilterRule.HEADER_MATCH,
                     pattern='^From: %s$' % re.escape(from_),
                     examples='From: %s' % (from_,),
                     action=FilterRule.FORWARD,
                     created_by=user)
        test = FilterRule.filter_message([filter], message)
        if test is None:
            raise Exception('FilterRule.filter_message failed')
        filter.save()
        logger.info('user:%s (%s) filter:%s whitelisted %r',
                    user.pk, user.username, filter.pk, from_)


class DjangoMessage(MIMEMixin, email.message.Message):
    pass


def message_upload_to(message: 'Message', filename, suffix=''):
    return 'messages/{peer}/{mailbox}/{now}{suffix}.mail'.format(
        peer=message.peer.slug,
        mailbox=message.mailbox.name,
        now=timezone.now().isoformat().replace(':', '_'),
        suffix=suffix,
    )


def orig_message_upload_to(message: 'Message', filename):
    return message_upload_to(message, filename, '_orig')


class Message(models.Model):
    '''
    A message received by a Peer for one of our mailboxes.
    '''
    RECIPIENT_SEP = ','

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
    rcpt_tos = models.TextField(blank=False)
    orig_mail_from = models.CharField(max_length=256,
                                      blank=False, null=True)
    orig_rcpt_tos = models.TextField(blank=False, null=True)
    message_file = models.FileField(upload_to=message_upload_to)
    orig_message_file = models.FileField(upload_to=orig_message_upload_to,
                                         blank=False, null=True)
    headers = models.TextField()
    # Unfortunately, MySQL makes it difficult to index more than 190 bytes :-(
    message_id = models.CharField(max_length=190, db_index=True, blank=True, null=True)
    body_text_bytes = models.BinaryField(null=True)
    created_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS,
                              default=INBOX)
    status_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                  blank=True, null=True)
    filtered_by = models.ForeignKey(FilterRule, on_delete=models.SET_NULL,
                                    blank=True, null=True)
    status_on = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return '<Message %s %r>' % (self.created_time.isoformat(),
                                    self.subject())

    @classmethod
    def create(cls, peer, mail_from, rcpt_tos, message_bytes,
               orig_mail_from, orig_rcpt_tos, orig_message_bytes):
        if not isinstance(rcpt_tos, list):
            raise ValueError('rcpt_tos must be a list, not a %r' %
                             (type(rcpt_tos),))
        if not isinstance(orig_rcpt_tos, list):
            raise ValueError('orig_rcpt_tos must be a list, not a %r' %
                             (type(orig_rcpt_tos),))
        # Mailbox.get_or_create logs the create_mailbox action
        mailbox = Mailbox.get_or_create(orig_rcpt_tos, peer)
        message = cls(mailbox=mailbox, peer=peer,
                      mail_from=mail_from,
                      rcpt_tos=Message.RECIPIENT_SEP.join(rcpt_tos),
                      status=cls.INBOX,
                      orig_mail_from=orig_mail_from,
                      orig_rcpt_tos=Message.RECIPIENT_SEP.join(orig_rcpt_tos))
        message.message_file.save('message.msg', ContentFile(message_bytes))
        message.orig_message_file.save('orig_message.msg',
                                       ContentFile(orig_message_bytes))
        message.extract_message_data()
        message.clean()
        message.save()
        logger.info("message:%s msgid:%s peer:%s Subject: %r From: %s To: %s",
                    message.pk, message.message_id, peer.slug, str(message.subject()),
                    message.from_address(), message.orig_rcpt_tos)
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
    def orig_message(self):
        try:
            return self._orig_message
        except AttributeError:
            if self.orig_message_file is None:
                self._orig_message = self.message
            else:
                self.orig_message_file.open('rb')
                self._orig_message = email.message_from_binary_file(
                    self.orig_message_file, DjangoMessage)
                self.orig_message_file.close()
            return self._orig_message

    @property
    def message(self):
        try:
            return self._message
        except AttributeError:
            self.message_file.open('rb')
            self._message = email.message_from_binary_file(self.message_file,
                                                           DjangoMessage)
            self.message_file.close()
            return self._message

    @staticmethod
    def _extract_message_data(self):
        '''
        Set self.headers and self.body_text from self.orig_message_file.
        '''
        self.orig_message_file.open('rb')
        message_bytes = self.orig_message_file.read()
        try:
            header_end = message_bytes.index(b'\r\n\r\n') + 4
        except ValueError:
            if message_bytes.endswith(b'\r\n'):
                header_end = len(message_bytes)
            else:
                raise ValidationError('Message must contain CR LF CR LF')
        self.headers = message_bytes[:header_end].decode(
            'ascii', errors='replace')
        try:
            message = email.message_from_bytes(message_bytes, DjangoMessage)
        except Exception:
            raise ValidationError('Could not parse message')
        self.body_text = Message._get_body_text(self, message)
        self.orig_message_file.close()
        self.extract_header_fields()

    def extract_message_data(self):
        self._extract_message_data(self)

    def extract_header_fields(self):
        self.message_id = self.parsed_headers.get("Message-ID")

    @property
    def body_text(self):
        if self.body_text_bytes is not None:
            return self.body_text_bytes.decode('utf8')

    @body_text.setter
    def body_text(self, value):
        self.body_text_bytes = None if value is None else value.encode('utf8')

    def from_(self):
        return str(decode_any_header(self.parsed_headers.get('From') or ''))

    def from_address(self):
        '''
        Returns the address portion of the From:-header.

        If the message contains an invalid number of From:-headers,
        returns the addresses joined with commas
        (or the empty string in case of no From:-header).
        '''
        parsed = email.utils.getaddresses(self.parsed_headers.get_all('From'))
        return ','.join(address for realname, address in parsed)

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

    def to_as_text(self):
        return ', '.join(formatted
                         for formatted, abbreviated in self.to_people())

    def to_as_html(self):
        return html.format_html_join(
            ', ', '<span title="{}">{}</span>', self.to_people())

    def unsubscribe_links(self):
        header = str(decode_any_header(
            self.parsed_headers.get('List-Unsubscribe') or ''))
        hrefs = [h.strip().strip('<>') for h in header.split(',')]
        return html.format_html_join(', ', '<a href="{0}">{0}</a>', zip(hrefs))

    def subject(self):
        return str(decode_any_header(self.parsed_headers.get('Subject') or ''))

    def get_absolute_url(self):
        return reverse('message_detail',
                       kwargs=dict(mailbox=self.mailbox.name,
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

    def set_status(self, status, *, user=None, filter=None):
        self.status = status
        self.status_by = user
        self.filtered_by = filter
        self.status_on = timezone.now()

    def exists_earlier_identical_forwarded_message(self):
        if self.message_id is None:
            return False
        qs = Message.objects.filter(
            message_id=self.message_id,
            created_time__lt=self.created_time,
            status=Message.TRASH,
        )
        # Filter on orig_rcpt_tos since we split up multi-domain messages
        # in SubmitForm.save() using mailhole.forms.split_by_domain.
        qs = qs.filter(
            orig_rcpt_tos=self.orig_rcpt_tos,
        )
        return qs.exists()

    def filter_incoming(self):
        '''
        Apply any applicable FilterRules to message.
        '''
        filters = (FilterRule.objects.filter(peer=None) |
                   FilterRule.objects.filter(peer=self.peer))
        filters = filters.order_by('order')
        filter = FilterRule.filter_message(filters, self)
        if filter is None:
            if self.mailbox.default_action == Mailbox.FORWARD:
                if self.exists_earlier_identical_forwarded_message():
                    logger.info('message:%s has already been forwarded before => don\'t forward (mailbox)',
                                self.pk)
                    return
                logger.info('message:%s from peer:%s:%s => forward (mailbox)',
                            self.pk, self.peer_id, self.peer.slug)
                self.set_status(Message.TRASH, filter=filter)
                self.save()
                SentMessage.create_and_send(self, user=None)
            return
        logger.info('message:%s from peer:%s:%s matches filter:%s => %s',
                    self.pk, self.peer_id, self.peer.slug,
                    filter.pk, filter.action)
        if filter.action == FilterRule.MARK_SPAM:
            self.set_status(Message.SPAM, filter=filter)
            self.save()
        elif filter.action == FilterRule.FORWARD:
            if self.exists_earlier_identical_forwarded_message():
                logger.info('message:%s has already been forwarded before => don\'t forward (filter)',
                            self.pk)
                return
            self.set_status(Message.TRASH, filter=filter)
            self.save()
            SentMessage.create_and_send(self, user=None)
        else:
            raise Exception(filter.action)

    def recipients(self):
        return self.rcpt_tos.split(Message.RECIPIENT_SEP)


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
                                   null=True, blank=True)

    def __str__(self):
        return '<SentMessage %s %s>' % (self.created_time.isoformat(),
                                        self.message.subject())

    @classmethod
    def create_and_send(cls, message, user, recipient=None):
        try:
            mailhole.policy.rewrite_message(message)
        except Exception:
            logger.exception("Could not apply policy")
        if recipient is None:
            recipients = message.recipients()
        else:
            recipients = [recipient]
        for r in recipients:
            logger.info('user:%s (%s) message:%s forwarded to <%s>',
                        user and user.pk, user and user.username,
                        message.pk, r)
            sent_message = SentMessage(message=message,
                                       recipient=r,
                                       created_by=user)
            sent_message.clean()
            email_backend = django.core.mail.get_connection()
            email_message = UnsafeEmailMessage(message.message, r)
            email_backend.send_messages([email_message])
            sent_message.save()


class MonitorMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_time = models.DateTimeField(auto_now_add=True)
    inbox_size = models.IntegerField()
    age_days = models.FloatField()
