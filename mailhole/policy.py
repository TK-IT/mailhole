import logging


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
