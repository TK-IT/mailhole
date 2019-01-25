#!/usr/bin/env python
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mailhole.settings")

import django

django.setup()

from mailhole.models import Message


def main():
    qs = Message.objects.filter(message_id=None).order_by("created_time")
    total = len(qs)
    saved = 0
    dupes = 0
    for i, message in enumerate(qs):
        message.extract_header_fields()
        if message.message_id:
            saved += 1
            message.save()
            if message.exists_earlier_identical_forwarded_message():
                dupes += 1
                print(
                    "\r%s %s %s"
                    % (message.pk, message.message_id, message.created_time),
                    flush=True,
                )
        print(
            "\r[%6d/%d] saved=%d dupes=%s" % (i + 1, total, saved, dupes),
            end="",
            flush=True,
        )
    print('', flush=True)


if __name__ == "__main__":
    main()
