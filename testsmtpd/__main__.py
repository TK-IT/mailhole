import aiohttp
import argparse
import aiosmtpd.controller


class Handler:
    def __init__(self, args):
        self.url = 'http://127.0.0.1:%s/api/submit/' % args.http_port
        self.key = args.key

    async def handle_DATA(self, server, session, envelope):
        async with aiohttp.ClientSession(loop=server.loop) as session:
            for rcpt in envelope.rcpt_tos:
                try:
                    print("From %r to %r..." % (envelope.mail_from, rcpt), end='')
                    data = dict(
                        key=self.key,
                        mail_from=envelope.mail_from,
                        rcpt_to=rcpt,
                        message_bytes=envelope.content,
                    )
                    async with session.post(self.url, data=data) as response:
                        text = await response.text()
                        status = response.status
                    if status != 200 or text.strip() != '250 OK':
                        print(' HTTP %s %r' %
                              (status, text.splitlines()[0][:50]), end='')
                        return '500 Internal server error'
                    print(' OK', end='')
                finally:
                    print('')
        return '250 OK'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-P', '--smtp-port', type=int, default=1025)
    parser.add_argument('-p', '--http-port', type=int, default=8000)
    parser.add_argument('-k', '--key', required=True)
    args = parser.parse_args()

    controller = aiosmtpd.controller.Controller(Handler(args),
                                                port=args.smtp_port)
    controller.start()
    try:
        input('Listening on port %s. Press Return to stop.\n' % args.smtp_port)
    except KeyboardInterrupt:
        print('')
    except EOFError:
        pass
    finally:
        controller.stop()


if __name__ == '__main__':
    main()
