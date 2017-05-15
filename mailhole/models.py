from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Mailbox(models.Model):
    '''
    An email user whose emails end up in our app.
    '''
    email = models.EmailField(unique=True)
    created_time = models.DateTimeField(auto_now_add=True)
    readers = models.ManyToManyField(User)

    def get_or_create(self, email):
        try:
            return Mailbox.objects.get(email=email)
        except Mailbox.DoesNotExist:
            mailbox = Mailbox(email=email)
            mailbox.clean()
            mailbox.save()
            return mailbox


class Peer(models.Model):
    '''
    A front-end SMTP server who receives emails for our mailboxes.
    '''
    key = models.CharField(max_length=256)

    @classmethod
    def validate(cls, key):
        try:
            return cls.objects.get(key=key)
        except cls.DoesNotExist:
            raise ValidationError('Invalid peer key')


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
    message_bytes = models.BinaryField()
    created_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS,
                              default=INBOX)

    @classmethod
    def create(cls, peer, mail_from, rcpt_to, message_bytes):
        # TODO how to get raw POST bytes in Django?
        mailbox = Mailbox.get_or_create(rcpt_to)
        message = cls(mailbox=mailbox, peer=peer,
                      mail_from=mail_from,
                      rcpt_to=rcpt_to,
                      message_bytes=message_bytes,
                      status=cls.INBOX)
        message.clean()
        message.save()
        return message


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
    def create_and_send(cls, message, user):
        sent_message = SentMessage(message=message,
                                   recipient=message.rcpt_to,
                                   created_by=user)
        sent_message.clean()
        TODO  # Connect to SMTP server and send message
        sent_message.save()
