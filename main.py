import logging
import os

import aiohttp
from aiohttp import web
from gidgethub import routing
from gidgethub import sansio

import fix_all
import jwt_generator
from client import Client

router = routing.Router()

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


@router.register(event_type="repository", action="created")
async def handle_new_repository_event(event: sansio.Event):
    async with Client(event.data['installation']['id']) as client:
        await fix_all.configure_repo(client, event.data['repository']['full_name'])


async def gh_event_handler(request: aiohttp.web.Request):
    body = await request.read()
    event = sansio.Event.from_http(request.headers, body)
    if event.event:
        await router.dispatch(event)
        return web.Response(status=200)
    else:
        return web.Response(status=404)


if __name__ == "__main__":
    # Check that we can find our key. Fail fast if we can't.
    jwt_generator.generate()

    app = web.Application()
    app.router.add_post("/gh-hook", gh_event_handler)
    web.run_app(app, port=int(os.getenv('PORT', '7593')))
