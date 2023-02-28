from typing import List, Dict
from urllib.parse import quote, urljoin

import aiohttp
import asyncio

from actions import join_args
from actions.media.plex.const import X_PLEX_TOKEN
from actions.utils import flatten


def _flatten_tags(data):
    if not isinstance(data, dict):
        return data
    tagged = {}
    for key, value in data.items():
        if not isinstance(value, list):
            continue
        tags = [
            i["tag"]
            for i
            in value
            if isinstance(i, dict) and "tag" in i
        ]
        if len(tags) != len(value):
            continue
        tagged[key] = tags

    return {
        **data,
        **tagged
    }


class PlexLibraries:
    _library_df = None
    _library_count = 0
    _library = {}

    def __init__(self, host: str, token: str):
        self._token = token
        self._host = host

    @property
    def token(self):
        return {
            X_PLEX_TOKEN: self._token
        }

    @property
    def headers(self):
        return {
            'Accept': 'application/json'
        }

    def get_url(self, endpoint, params=None):
        if not params:
            params = {}
        params = {
            **params,
            "includeChildren": 1,
            "includeAdvanced": 1
        }
        return f"{urljoin(self._host, endpoint)}{join_args({**params, **self.token})}"

    def add_media_item(self, media_type, metadata):
        self._library = self._library.setdefault(media_type, []) + [metadata]

    async def load(self):
        [
            self.add_media_item(metadata["type"], metadata)
            for metadata
            in await self.get_libraries()
        ]

    async def get_libraries(self) -> List[Dict]:
        url = "/library/sections"
        async with aiohttp.ClientSession(headers=self.headers) as session:
            sections = await (await session.get(self.get_url(url))).json()
            children = await asyncio.gather(*[
                self.get_children(
                    session,
                    {
                        **directory,
                        "key": f"/library/sections/{directory['key']}/all"
                    }
                )
                for directory
                in sections["MediaContainer"]["Directory"]
            ], return_exceptions=False)
            return flatten(children)

    async def get_children(self, session: aiohttp.ClientSession, metadata: Dict) -> List[Dict]:
        if "children" not in metadata.get("key", "") and "all" not in metadata.get("key", ""):
            return [metadata]
        items = await (await session.get(self.get_url(metadata.get("key", None)))).json()
        children = await asyncio.gather(*[
            self.get_children(
                session,
                child
            )
            for child
            in items["MediaContainer"]["Metadata"]
        ], return_exceptions=False)
        return flatten(children) + [metadata]
