Purgatory for hot mails
=======================

Hotmail har blokeret pulerau.

prodekanus kan sende mails til Hotmail via AU ITs mailservere.
Vi har ikke lyst til blindt at videresende via AU ITs mailservere,
da vi under ingen omstændigheder må sende spam ud fra disse.

Når pulerau modtager en mail til en TK-adresse eller tutor-adresse,
og denne mail skal viderestilles til en Hotmail-adresse,
sendes den i stedet til

    POST https://mailhole.tket.dk/api/submit/
    key=mailserver-private-api-token
    mail_from=nude.celebs@for.free
    rcpt_to=mathiasrav@hotmail.dk
    message_bytes=RFC2822 message data...

En bruger kan logge ind og se mails til sine designerede mailbokse
og markere hver som "spam" eller "videresend":

    | ⦻ | → | Fra            | Til           | Emne               |
    |[ ]|[ ]| ....           | ....          | ....               |
    |[ ]|[ ]| ....           | ....          | ....               |
    ...
    [Udfør]
