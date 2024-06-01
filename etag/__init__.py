from base64 import b64encode
from hashlib import md5
from io import BytesIO
from typing import NoReturn

from starlette.datastructures import Headers, MutableHeaders
from starlette.status import HTTP_200_OK, HTTP_304_NOT_MODIFIED
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__version__ = '0.1.0'


class ETagMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 80, streaming=False) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.streaming = streaming

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http' and scope['method'] == 'GET':
            responder: ETagResponder
            if self.streaming:
                responder = ETagStreamingResponder(self.app, scope, self.minimum_size)
            else:
                responder = ETagResponder(self.app, scope, self.minimum_size)
            await responder(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class ETagResponder:
    def __init__(self, app: ASGIApp, scope: Scope, minimum_size: int) -> None:
        self.app = app
        self.scope = scope
        self.minimum_size = minimum_size
        self.send: Send = unattached_send
        self.initial_message: Message = {}
        self.headers: MutableHeaders | None = None
        self.status_code: int | None = None
        self.delay_sending: bool = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.send_with_etag)

    async def send_with_etag(self, message: Message) -> None:
        if self.status_code is None:
            self.status_code = message.get('status')
        if self.status_code != HTTP_200_OK:
            await self.send(message)
            return

        message_type = message['type']
        if message_type == 'http.response.start':
            self.headers = MutableHeaders(raw=message['headers'])
            content_length = self.headers.get('content-length')
            if content_length:
                size = int(content_length)
                if size >= self.minimum_size:
                    # Don't send the initial message until we've determined how to
                    # modify the outgoing headers correctly.
                    self.initial_message = message
                    return
                # else we should not send Etag
                self.delay_sending = False
                await self.send(message)
                return
            # else it's a streamming response
            await self.handle_initial_message(message)
        elif message_type == 'http.response.body':
            await self.handle_body(message)

    async def handle_initial_message(self, message: Message) -> None:
        self.delay_sending = False
        await self.send(message)

    async def handle_body(self, message: Message) -> None:
        if not self.delay_sending:
            await self.send(message)
            return

        more_body = message.get('more_body', False)
        if more_body:  # pragma: no cover, it's a streamming response, but should be checked before
            self.delay_sending = False
            await self.send(self.initial_message)
            await self.send(message)
            return

        body = message.get('body', b'')
        if len(body) >= self.minimum_size:
            self.handle_etag(body, message)
        await self.send(self.initial_message)
        await self.send(message)

    def handle_etag(self, body: bytes, message: Message) -> None:
        etag = f'''"{b64encode(md5(body).digest())[:-2].decode('ascii')}"'''  # remove trailing '=='
        assert self.headers is not None
        self.headers['ETag'] = etag
        if_none_match = Headers(scope=self.scope).get('if-none-match')
        if if_none_match:
            if if_none_match[:2] == 'W/':  # nginx will add 'W/' prefix to ETag for gzipped content
                if_none_match = if_none_match[2:]
            if if_none_match == etag:
                del self.headers['content-length']
                self.initial_message['status'] = HTTP_304_NOT_MODIFIED
                message['body'] = b''


class ETagStreamingResponder(ETagResponder):
    def __init__(self, app: ASGIApp, scope: Scope, minimum_size: int) -> None:
        super().__init__(app, scope, minimum_size)
        self.buffer: BytesIO | None = None

    async def handle_initial_message(self, message: Message) -> None:
        self.initial_message = message

    async def handle_body(self, message: Message) -> None:
        if not self.delay_sending:
            await self.send(message)
            return

        body = message.get('body', b'')
        more_body = message.get('more_body', False)
        if self.buffer:
            if body:
                self.buffer.write(body)
        elif more_body:
            self.buffer = BytesIO(body)
            self.buffer.seek(len(body))
            return
        if not more_body:
            if self.buffer:
                body = self.buffer.getvalue()
                self.buffer.close()
            if len(body) < self.minimum_size:
                message['body'] = body
            else:
                self.handle_etag(body, message)
            await self.send(self.initial_message)
            await self.send(message)
        # else the body is already written to the buffer, waiting for the next body


async def unattached_send(message: Message) -> NoReturn:
    raise RuntimeError('send awaitable not set')  # pragma: no cover
