import asyncio

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.responses import Response, StreamingResponse
from fastapi.testclient import TestClient

from etag import ETagMiddleware

name: str

origin_app = app = FastAPI()


def hello():
    return Response(f'Hello, {name}!')


async def generator():
    yield 'Hello, '
    await asyncio.sleep(0.01)
    yield name
    yield '!'


async def streaming_hello():
    await asyncio.sleep(0.01)
    return StreamingResponse(generator())


def rename(new_name: str):
    global name
    name = new_name


def error():
    return Response(f'Hello, {name}!', 500)


def app_with_middleware(middleware_class: Middleware) -> FastAPI:
    app = FastAPI(
        middleware=[middleware_class],
    )
    app.get('/hello')(hello)
    app.get('/streaming-hello')(streaming_hello)
    app.post('/rename')(rename)
    app.get('/error')(error)
    return app


class TestETagResponder:
    def test_send_with_etag(self):
        global name
        name = 'world'

        app = app_with_middleware(Middleware(ETagMiddleware))
        client = TestClient(app)

        response = client.get('/hello')
        assert response.status_code == 200
        assert response.content == b'Hello, world!'
        assert response.headers.get('ETag') is None

        response = client.post(f'/rename?new_name={"test" * 20}')
        assert response.status_code == 200

        response = client.get('/hello')
        assert response.status_code == 200
        assert response.content == f'Hello, {name}!'.encode('ascii')
        etag = response.headers['ETag']
        assert etag

        response = client.get('/hello', headers={'If-None-Match': etag})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag

        response = client.get('/hello', headers={'If-None-Match': f'W/{etag}'})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag

        name = 'test' * 21
        response = client.get('/hello', headers={'If-None-Match': etag})
        assert response.status_code == 200
        assert response.content == f'Hello, {name}!'.encode('ascii')
        etag2 = response.headers['ETag']
        assert etag2
        assert etag != etag2

        response = client.get('/hello', headers={'If-None-Match': etag2})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag2

        response = client.get('/streaming-hello', headers={'If-None-Match': etag2})
        assert response.status_code == 200
        assert response.content == f'Hello, {name}!'.encode('ascii')
        assert response.headers.get('ETag') is None

        response = client.get('/error')
        assert response.status_code == 500
        assert response.content == f'Hello, {name}!'.encode('ascii')
        assert response.headers.get('ETag') is None


class TestETagStreamingResponder:
    def test_send_with_etag(self):
        global name
        name = 'world'

        app = app_with_middleware(Middleware(ETagMiddleware, streaming=True))
        client = TestClient(app)

        response = client.get('/hello')
        assert response.status_code == 200
        assert response.content == b'Hello, world!'
        assert response.headers.get('ETag') is None

        response = client.post(f'/rename?new_name={"test" * 20}')
        assert response.status_code == 200

        response = client.get('/hello')
        assert response.status_code == 200
        assert response.content == f'Hello, {name}!'.encode('ascii')
        etag = response.headers['ETag']
        assert etag

        response = client.get('/hello', headers={'If-None-Match': etag})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag

        response = client.get('/hello', headers={'If-None-Match': f'W/{etag}'})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag

        name = 'test' * 21
        response = client.get('/hello', headers={'If-None-Match': etag})
        assert response.status_code == 200
        assert response.content == f'Hello, {name}!'.encode('ascii')
        etag2 = response.headers['ETag']
        assert etag2
        assert etag != etag2

        response = client.get('/hello', headers={'If-None-Match': etag2})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag2

        response = client.get('/streaming-hello', headers={'If-None-Match': etag2})
        assert response.status_code == 304
        assert response.content == b''
        assert response.headers['ETag'] == etag2

        response = client.get('/error')
        assert response.status_code == 500
        assert response.content == f'Hello, {name}!'.encode('ascii')
        assert response.headers.get('ETag') is None

        response = client.post('/rename?new_name=world')
        assert response.status_code == 200

        response = client.get('/streaming-hello', headers={'If-None-Match': etag})
        assert response.status_code == 200
        assert response.content == b'Hello, world!'
        assert response.headers.get('ETag') is None
