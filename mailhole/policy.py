import logging

from django.conf import settings


logger = logging.getLogger("mailhole")


def rewrite_from(message):
    is_deans_signup = (
        message.mailbox.name == "nova-aarhus.dk"
        and message.peer.slug == "orgmail"
        and message.parsed_headers.get("Subject") == "Nyt Signup fra Deans Challenge!"
        and message.parsed_headers.get("From")
        and not message.parsed_headers["From"].endswith("@nova-aarhus.dk")
    )
    if is_deans_signup:
        return "signup@nova-aarhus.dk"


def rewrite_message(message):
    from_address = rewrite_from(message)
    if from_address is not None:
        logger.info(
            "Policy rewrite: From: %r -> %r", message.message["From"], from_address
        )
        message.message.replace_header("From", from_address)


def allow_automatic_forward(message):
    if settings.NO_OUTGOING_EMAIL:
        return False
    if settings.REQUIRE_PLAIN_TEXT:
        if message.outgoing_content_type() != "text/plain":
            return False
    if settings.REQUIRE_FROM_REWRITING:
        outgoing_from_address = message.outgoing_from_address()
        if "," in outgoing_from_address:
            return False
        expected_domain = "@%s" % message.mailbox.name.lower()
        if not outgoing_from_address.lower().endswith(expected_domain):
            return False
    return True
