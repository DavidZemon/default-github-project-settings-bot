from typing import Optional

import aiohttp
from gidgethub.aiohttp import GitHubAPI

import jwt_generator


class Client:
    _gh: Optional[GitHubAPI]

    def __init__(self, installation_id: int):
        self._installation_id = installation_id
        self._session = aiohttp.ClientSession()

    async def get(self, url: str):
        return await self._gh.getitem(url)

    async def post(self, url: str, data: any):
        return await self._gh.post(url, data=data)

    async def patch(self, url: str, data: any):
        return await self._gh.patch(url, data=data)

    async def delete(self, url: str):
        return await self._gh.delete(url)

    async def graphql(self, query: str):
        return await self._gh.graphql(query)

    async def __aenter__(self):
        await self._session.__aenter__()
        jwt = jwt_generator.generate()

        # Need a temporary GitHubAPI object to get the access token
        token_response = await GitHubAPI(self._session, requester='token-gh-bot').post(
            f"/app/installations/{self._installation_id}/access_tokens",
            jwt=jwt,
            data=None
        )

        # Then we can create the authenticated API
        self._gh = GitHubAPI(self._session, requester='token-gh-bot', oauth_token=token_response['token'])

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.__aexit__(exc_type, exc_val, exc_tb)
