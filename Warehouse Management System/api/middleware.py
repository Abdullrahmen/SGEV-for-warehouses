from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token
from channels.middleware import BaseMiddleware


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope["query_string"].decode())
        token_key = query.get("token", [None])[0]
        if token_key:
            user = await self.get_user_from_token(token_key)
            if user:
                scope["user"] = user
            else:
                await send({"type": "websocket.close", "code": 4001})
                return
        else:
            await send({"type": "websocket.close", "code": 4001})
            return
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token_key):
        try:
            return Token.objects.get(key=token_key).user
        except Token.DoesNotExist:
            return None


def TokenAuthMiddlewareStack(inner):
    return TokenAuthMiddleware(inner)
