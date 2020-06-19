import os
import argparse
import datetime
import textwrap
from django.utils import timezone
from django.core.mail import EmailMessage, get_connection


SYSTEM_NAME = 'mailhole'
URL = 'https://mail.tket.dk/'
MAX_SIZE = 10
MAX_DAYS = 2
SUBJECT = '[%s] Emails pending moderation' % SYSTEM_NAME
FROM_EMAIL = 'mailhole@prodekanus.studorg.au.dk'


parser = argparse.ArgumentParser()
parser.add_argument('-n', '--dry-run', action='store_true')


def make_monitor_message(to, messages):
    message_format = textwrap.dedent('''
    Date: {date}
    From: {sender}
    To: {recipients}
    Subject: {subject}
    ''').strip()

    messages_text = '\n\n'.join(
        message_format.format(sender=message.from_(),
                              recipients=message.to_as_text(),
                              subject=message.subject(),
                              date=message.parsed_headers.get('Date'))
        for message in messages)

    body = textwrap.dedent("""
    This is {SYSTEM_NAME}. The following messages are waiting for you.
    Please visit {URL} at your next convenience.

    {messages_text}
    """).format(SYSTEM_NAME=SYSTEM_NAME, URL=URL, messages_text=messages_text)

    return EmailMessage(
        subject=SUBJECT,
        body=body,
        from_email=FROM_EMAIL,
        to=[to],
    )


def main(dry_run):
    from django.conf import settings
    from django.contrib.auth.models import User
    from mailhole.models import Message, Mailbox, MonitorMessage

    if settings.NO_OUTGOING_EMAIL and not dry_run:
        print("NO_OUTGOING_EMAIL is set - don't send anything")
        return

    inbox_by_mailbox_id = {}
    for message in Message.objects.filter(status=Message.INBOX):
        inbox_by_mailbox_id.setdefault(message.mailbox_id, []).append(message)

    users = {}
    readers = Mailbox.readers.through.objects.all()
    readers = readers.filter(mailbox_id__in=inbox_by_mailbox_id)
    for e in readers:
        users.setdefault(e.user_id, []).append(
            inbox_by_mailbox_id[e.mailbox_id])

    monitor_messages = []
    monitor_message_models = []

    for user_id, inboxes in users.items():
        inbox = [message for i in inboxes for message in i]
        inbox_size = len(inbox)
        oldest = min(inbox, key=lambda m: m.created_time)
        age = timezone.now() - oldest.created_time
        age_days = age / datetime.timedelta(1)

        if inbox_size < MAX_SIZE and age_days < MAX_DAYS:
            print("user_id=%s inbox_size=%s age_days=%s " %
                  (user_id, inbox_size, age_days) +
                  'No need to report anything')
            continue

        # Did we already send a report with the newest message?
        newest = max(inbox, key=lambda m: m.created_time)
        already_reported = MonitorMessage.objects.filter(
            user_id=user_id, created_time__gt=newest.created_time)
        if already_reported.exists():
            print("user_id=%s inbox_size=%s age_days=%s " %
                  (user_id, inbox_size, age_days) +
                  'Already sent a report')
            continue

        monitor_message_model = MonitorMessage(
            inbox_size=inbox_size, age_days=age_days)
        monitor_message_model.user_id = user_id

        user = User.objects.get(id=user_id)
        if not user.email:
            print("user_id=%s inbox_size=%s age_days=%s " %
                  (user_id, inbox_size, age_days) +
                  'User has no email address!')
            continue
        monitor_message = make_monitor_message(user.email, inbox)
        monitor_message_model.body = monitor_message.body
        monitor_messages.append(monitor_message)
        monitor_message_models.append(monitor_message_model)
        print("user_id=%s inbox_size=%s age_days=%s " %
              (user_id, inbox_size, age_days) +
              'Send report')
    if dry_run:
        print('--dry-run: Want to send %s message(s)' % len(monitor_messages))
        for e in monitor_messages:
            print(e)
    else:
        if monitor_messages:
            get_connection().send_messages(monitor_messages)
            MonitorMessage.objects.bulk_create(
                monitor_message_models)


if __name__ == '__main__':
    # Parse args before calling Django setup.
    # This makes --help much faster.
    _args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mailhole.settings')
    from django import setup as _s
    _s()
    main(**vars(_args))
