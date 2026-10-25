"""Request metadata only: never log request bodies, cookies or credentials."""
import json
import logging
import time
import uuid

log = logging.getLogger('uvicorn.error')


class RequestLog:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        started = time.monotonic()
        status = 500

        async def logged_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message['headers'] = [*message.get('headers', []),
                                      (b'x-request-id', request_id.encode())]
            await send(message)
        try:
            await self.app(scope, receive, logged_send)
        finally:
            log.info(json.dumps({'event': 'http_request', 'request_id': request_id,
                                  'run_id': scope.get('state', {}).get('run_id'),
                                  'method': scope['method'], 'status': status,
                                  'duration_ms': int((time.monotonic() - started) * 1000)}))
