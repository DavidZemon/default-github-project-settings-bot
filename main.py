import logging

import aiohttp
import gidgethub
from aiohttp import web
from gidgethub import routing
from gidgethub import sansio
from gidgethub.aiohttp import GitHubAPI

import jwt_generator

router = routing.Router()

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)
SNOW_GATE_PASS = False


async def produce_access_token(gh: GitHubAPI, install_id: int) -> str:
    jwt = jwt_generator.generate()
    url = f"/app/installations/{install_id}/access_tokens"
    response = await gh.post(url, jwt=jwt, data=None)
    return response['token']


async def get_branch_protection(repo_full_name: str, installation_id: int):
    url = f"/repos/{repo_full_name}/branches/main/protection"
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "katiesamplebot")
        access_token = await produce_access_token(gh, installation_id)
        try:
            response = await gh.getitem(
                url,
                oauth_token=access_token
            )
        except gidgethub.BadRequest as e:
            LOGGER.debug("Main Branch is not protected. Need to add a main branch protection")
            return None

    return response


async def update_branch_protection(repo_full_name: str, installation_id: int):
    url = f"/repos/{repo_full_name}/branches/main/protection"
    async with aiohttp.ClientSession() as session:
        gh = GitHubAPI(session, "katiesamplebot")
        access_token = await produce_access_token(gh, installation_id)
        response = await gh.put(
            url,
            oauth_token=access_token,
            data={
                'required_status_checks': {
                    'strict': True,
                    'contexts': [
                        'ServiceNow Check',
                        'Twistlock Check'
                    ]
                },
                'enforce_admins': True,
                'restrictions': None,
                'required_pull_request_reviews': {
                    'required_approving_review_count': 1
                }
            }
        )
    return response


def is_branch_protection_valid(response) -> bool:
    if 'required_pull_request_reviews' in response and 'required_status_checks' in response:
        checks = response['required_status_checks']['checks']
        if len(checks) >= 2 and \
                any(check['context'] == 'ServiceNow Check' for check in checks) and \
                any(check['context'] == 'Twistlock Check' for check in checks) and \
                response['required_pull_request_reviews']['required_approving_review_count'] >= 1:
            return True

    return False


# If someone modifies the branch protection rule or removes a required check, add it back
@router.register(event_type="branch_protection_rule", action="deleted")
@router.register(event_type="branch_protection_rule", action="edited")
@router.register(event_type="branch_protection_rule", action="created")
async def handle_branch_protection_rule_event(event: sansio.Event):
    repo_full_name = event.data['repository']['full_name']
    installation_id = event.data['installation']['id']
    branch_protection = await get_branch_protection(repo_full_name, installation_id)
    if branch_protection is None:
        LOGGER.debug("There is no branch protection on main")
        # TBD create new branch protection
    elif is_branch_protection_valid(branch_protection):
        LOGGER.debug("Branch protection looks good!")
    else:
        LOGGER.debug("Branch protection is invalid. Updating it")
        await update_branch_protection(repo_full_name, installation_id)


async def gh_event_handler(request: aiohttp.web.Request):
    body = await request.read()
    event = sansio.Event.from_http(request.headers, body)
    if event.event:
        await router.dispatch(event)
        return web.Response(status=200)
    else:
        return web.Response(status=404)


if __name__ == "__main__":
    app = web.Application()
    app.router.add_post("/gh-hook", gh_event_handler)
    web.run_app(app, port=9684)
