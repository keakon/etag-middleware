import asyncio

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.testclient import TestClient

from etag import ETagMiddleware

name: str


app = FastAPI(middleware=[Middleware(ETagMiddleware)])
client = TestClient(app)


@app.get('/hello')
def hello():
    return Response(f'Hello, {name}!')


async def generator():
    yield 'Hello, '
    await asyncio.sleep(0.01)
    yield name
    yield '!'


@app.get('/streaming-hello')
async def streaming_hello():
    await asyncio.sleep(0.01)
    return StreamingResponse(generator())


@app.post('/rename')
def rename(new_name: str):
    global name
    name = new_name


@app.get('/src')
def src():
    return FileResponse(__file__)


@app.get('/error')
def error():
    return Response(f'Hello, {name}!', 500)


class TestETagResponder:
    def test_send_with_etag(self):
        global name
        name = 'world'

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

        response = client.get('/src')
        assert response.status_code == 200
        etag3 = response.headers['ETag']
        assert etag3
        assert etag != etag3

        response = client.get('/src', headers={'If-None-Match': etag3})
        assert response.status_code == 304  # fix a bug that FileResponse doesn't check ETag
        etag4 = response.headers['ETag']
        assert etag3 == etag4

        chunk_size = FileResponse.chunk_size
        try:
            FileResponse.chunk_size = 64  # set it to a smaller size for testing chunked body
            response = client.get('/src', headers={'If-None-Match': etag3})
            assert response.status_code == 304
            etag5 = response.headers['ETag']
            assert etag5
            assert etag3 == etag5
        finally:
            FileResponse.chunk_size = chunk_size  # reset chunk_size

        response = client.get('/error')
        assert response.status_code == 500
        assert response.content == f'Hello, {name}!'.encode('ascii')
        assert response.headers.get('ETag') is None
