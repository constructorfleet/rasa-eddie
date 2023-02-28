import json
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


class PlexLibrary:
    _library_df = None
    _library_count = 0
    _library: Dict = {}
    _keys_seen = []

    def __init__(self, host: str, token: str):
        self._token = token
        self._host = host

    @property
    def _token_header(self):
        return {
            X_PLEX_TOKEN: self._token
        }

    @property
    def _headers(self):
        return {
            'Accept': 'application/json'
        }

    def _get_url(self, endpoint, params=None):
        if not params:
            params = {}
        params = {
            **params,
            "includeChildren": 1,
            "includeAdvanced": 1
        }
        return f"{urljoin(self._host, endpoint)}{join_args({**params, **self._token_header})}"

    def has_seen(self, key: str) -> bool:
        return key is None or key in self._keys_seen

    async def add_media_item(self, metadata: dict, check_parent: bool = False):
        if metadata is None:
            return
        if check_parent and not self.has_seen(metadata.get("parentKey", None)):
            await self.add_media_item(await self._get_parent(metadata), True)
        key = metadata["key"]
        if key in self._keys_seen:
            return
        self._keys_seen.append(key)
        self._library[metadata["type"]] = self._library.setdefault(
            metadata["type"], []
        ) + [_flatten_tags(metadata)]

    async def load(self):
        [
            await self.add_media_item(metadata)
            for metadata
            in await self._get_libraries()
        ]

    async def _get_libraries(self) -> List[Dict]:
        url = "/library/sections"
        async with aiohttp.ClientSession(headers=self._headers) as session:
            sections = await (await session.get(self._get_url(url))).json()
            children = await asyncio.gather(*[
                self._get_children(
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

    async def _get_children(self, session: aiohttp.ClientSession, metadata: Dict) -> List[Dict]:
        if "children" not in metadata.get("key", "") and "all" not in metadata.get("key", ""):
            return [metadata]
        items = await (await session.get(self._get_url(metadata.get("key", None)))).json()
        children = await asyncio.gather(*[
            self._get_children(
                session,
                child
            )
            for child
            in items["MediaContainer"]["Metadata"]
        ], return_exceptions=False)
        return flatten(children) + [metadata]

    async def _get_parent(self, metadata: Dict) -> Dict | None:
        if "parentKey" not in metadata:
            return None
        async with aiohttp.ClientSession(headers=self._headers) as session:
            parent_resp = await session.get(self._get_url(metadata.get("parentKey", None)))
            parent_container = await parent_resp.json()
            return parent_container["MediaContainer"]["Metadata"][0]
