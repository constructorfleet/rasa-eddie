import json

from sanic import Sanic, Request, HTTPResponse, response
from .library import PlexLibrary


class Plex:

    def __int__(self, sanic_app_name: str, host: str, token: str):
        """Initialize a new Plex class."""
        self._libraries = PlexLibrary(host, token)
        self._setup_webhook(sanic_app_name)

    def _setup_webhook(self, sanic_app_name: str):
        app = Sanic.get_app(sanic_app_name)
        app.add_route(
            self._handle_webhook,
            '/media/plex_webhook',
            methods=['GET', 'POST']
        )

    async def load_libraries(self):
        await self._libraries.load()

    async def _handle_webhook(self, request: Request) -> HTTPResponse:
        payload = request.form.get("payload", None)
        if not payload:
            return response.empty(204)
        payload = json.loads(payload)
        event = payload.get("event", None)
        if event == "library.new":
            await self._libraries.add_media_item(payload.get("Metadata"), True)
        return response.json("OK", 200)
