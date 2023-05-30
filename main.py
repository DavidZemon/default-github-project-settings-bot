import logging
import os

import aiohttp
from aiohttp import web
from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

import jwt_generator

router = routing.Router()

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


async def produce_access_token(gh: GitHubAPI, install_id: int) -> str:
    jwt = jwt_generator.generate()
    url = f"/app/installations/{install_id}/access_tokens"
    response = await gh.post(url, jwt=jwt, data=None)
    return response['token']


async def get(installation_id: int, url: str) -> any:
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "token-gh-bot")
        access_token = await produce_access_token(gh, installation_id)
        return await gh.getitem(
            url,
            oauth_token=access_token,
        )


async def post(installation_id: int, url: str, data: any) -> any:
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "token-gh-bot")
        access_token = await produce_access_token(gh, installation_id)
        return await gh.post(
            url,
            oauth_token=access_token,
            data=data
        )


async def patch(installation_id: int, url: str, data: any) -> any:
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "token-gh-bot")
        access_token = await produce_access_token(gh, installation_id)
        return await gh.patch(
            url,
            oauth_token=access_token,
            data=data
        )


@router.register(event_type="repository", action="created")
async def handle_new_repository_event(event: sansio.Event):
    repo_full_name = event.data['repository']['full_name']
    installation_id = event.data['installation']['id']

    await post(installation_id, f"/repos/{repo_full_name}/rulesets", {
        "name": "Protected branch",
        "target": "branch",
        "source_type": "Repository",
        "source": "protocol",
        "enforcement": "active",
        "bypass_mode": "none",
        "bypass_actors": [],
        "conditions": {
            "ref_name": {
                "exclude": [],
                "include": [
                    "~DEFAULT_BRANCH",
                    "refs/heads/main",
                    "refs/heads/develop",
                    "refs/heads/release/**/*"
                ]
            }
        },
        "rules": [
            {
                "type": "deletion"
            },
            {
                "type": "non_fast_forward"
            },
            {
                "type": "pull_request",
                "parameters": {
                    "require_code_owner_review": False,
                    "require_last_push_approval": True,
                    "dismiss_stale_reviews_on_push": True,
                    "required_approving_review_count": 2,
                    "required_review_thread_resolution": True
                }
            }
        ],
    })

    for prefix in ['FW', 'SW', 'APP', 'SE']:
        prefix = prefix.upper()  # Just in case someone screws up the list
        await post(installation_id, f"/repos/{repo_full_name}/autolinks", {
            "key_prefix": f"{prefix}-",
            "url_template": f"https://tokenring.atlassian.net/browse/{prefix}-<num>",
            "is_alphanumeric": False
        })

    await patch(installation_id, f"/repos/{repo_full_name}", {
        "has_issues": False,
        "has_projects": True,
        "has_downloads": True,
        "has_wiki": False,
        "has_pages": False,
        "has_discussions": False,
        "allow_rebase_merge": False,
        "allow_squash_merge": False,
        "allow_update_branch": True,
        "allow_auto_merge": True,
        "delete_branch_on_merge": True,
        "web_commit_signoff_required": False,
    })


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
