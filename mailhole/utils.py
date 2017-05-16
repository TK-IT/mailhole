from unittest.mock import patch
import html2text
import email.header
import email.errors


def html_to_plain(body):
    # From regnskab.utils
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.unicode_snob = True
    h.images_to_alt = True
    h.body_width = 0
    with patch('html2text.escape_md_section', (lambda t, snob=False: t)):
        return h.handle(str(body))


def decode_any_header(value):
    '''Wrapper around email.header.decode_header to absorb all errors.'''
    # From emailtunnel
    try:
        chunks = email.header.decode_header(value)
    except email.errors.HeaderParseError:
        chunks = [(value, None)]

    header = email.header.Header()
    for string, charset in chunks:
        if charset is not None:
            if not isinstance(charset, email.header.Charset):
                charset = email.header.Charset(charset)
        try:
            try:
                header.append(string, charset, errors='strict')
            except UnicodeDecodeError:
                header.append(string, 'latin1', errors='strict')
        except:
            header.append(string, charset, errors='replace')
    return header
