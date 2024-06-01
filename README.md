# ETag Middleware

[![Build Status](https://github.com/keakon/etag-middleware/actions/workflows/python.yml/badge.svg)](https://github.com/keakon/etag-middleware/actions)
[![Coverage](https://codecov.io/gh/keakon/etag-middleware/graph/badge.svg)](https://codecov.io/gh/keakon/etag-middleware)

A middleware to handle ETag for Starlette or FastAPI.

# Installation

```bash
pip install etag-middleware
```

# Usage

## FastAPI

```python
from etag import ETagMiddleware
from fastapi import FastAPI
from fastapi.middleware import Middleware

app = FastAPI(middleware=[Middleware(ETagMiddleware)])
```

## Starlette

```python
from etag import ETagMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware

app = Starlette(middleware=[Middleware(ETagMiddleware)])
```

# Notice

1. It won't compute `ETag` for requests with body size less than 80 bytes by default. Beacause `ETag` and `If-None-Match` increase more than 70 bytes to the response header, and computing `ETag` consumes CPU. You can adjust it by setting `minimum_size`:
    ```python
    app = FastAPI(middleware=[Middleware(ETagMiddleware, minimum_size=0)])
    ```

2. It won't compute `ETag` for `StreamingResponse` by default. Because it will delay sending the response until collected all its body and consumes more memory. You can enable it by setting `streaming=True`:
    ```python
    app = FastAPI(middleware=[Middleware(ETagMiddleware, streaming=True)])
    ```
