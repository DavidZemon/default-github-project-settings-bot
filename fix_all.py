import asyncio
import logging
import random

import jwt_generator
from client import Client

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


ALL_BRANCHES_NEEDING_PROTECTION = ["main", "develop", "master", "release/*"]
ALL_JIRA_KEYS = ['FW-', 'SW-', 'APP-', 'SE-']


async def main() -> None:
    async with Client(38053188) as client:
        repos = await client.get("/orgs/tokenize-inc/repos")

        for repo in repos:
            await configure_repo(client, repo["full_name"])


async def configure_repo(client: Client, repo_full_name: str) -> None:
    LOGGER.info(f"CONFIGURING REPOSITORY: '{repo_full_name}'")

    await set_branch_protections(client, repo_full_name)

    await delete_rulesets(client, repo_full_name)

    await add_autolinks(client, repo_full_name)

    await configure_repo_settings(client, repo_full_name)


async def set_branch_protections(client: Client, repo_full_name: str):
    owner, name = repo_full_name.split('/')

    # language=GraphQL
    response = await client.graphql(
        f'{{\n'
        f'  repository(owner: "{owner}", name: "{name}") {{\n'
        f'    id\n'
        f'    branchProtectionRules(first: 100) {{\n'
        f'      nodes {{\n'
        f'        id\n'
        f'        pattern\n'
        f'      }}\n'
        f'    }}\n'
        f'  }}\n'
        f'}}'
    )

    repo_id = response["repository"]["id"]

    existing_protections = [
        protection
        for protection in (response["repository"]["branchProtectionRules"]["nodes"])
        if protection["pattern"] in ALL_BRANCHES_NEEDING_PROTECTION
    ]

    client_mutation_id = random.randint(10000, 100000)
    for protection in existing_protections:
        protection_id = protection["id"]
        pattern = protection['pattern']

        if pattern in ALL_BRANCHES_NEEDING_PROTECTION:
            LOGGER.info(f"\t{repo_full_name} has existing protection on `{pattern}`. Updating settings to match standards.")
            # language=GraphQL
            await client.graphql(
                f'mutation {{\n'
                f'    updateBranchProtectionRule(\n'
                f'        input: {{\n'
                f'            clientMutationId: "{client_mutation_id}"\n'
                f'            branchProtectionRuleId: "{protection_id}"\n'
                f'            allowsDeletions: false\n'
                f'            allowsForcePushes: false\n'
                f'            bypassForcePushActorIds: []\n'
                f'            bypassPullRequestActorIds: []\n'
                f'            dismissesStaleReviews: true\n'
                f'            isAdminEnforced: true\n'
                f'            pushActorIds: []\n'
                f'            requireLastPushApproval: false\n'
                f'            requiredApprovingReviewCount: 1\n'
                f'            requiredDeploymentEnvironments: []\n'
                f'            requiresApprovingReviews: true\n'
                f'            requiresCommitSignatures: true\n'
                f'            requiresConversationResolution: true\n'
                f'            requiresDeployments: false\n'
                f'            requiresLinearHistory: false\n'
                f'            restrictsPushes: true\n'
                f'            restrictsReviewDismissals: false\n'
                f'            reviewDismissalActorIds: []\n'
                f'        }}\n'
                f'    ) {{ clientMutationId }}\n'
                f'}}'
            )

    handled_patterns = [protection["pattern"] for protection in existing_protections]
    not_handled_patterns = [pattern for pattern in ALL_BRANCHES_NEEDING_PROTECTION if pattern not in handled_patterns]

    if not_handled_patterns:
        LOGGER.info(f'\t{repo_full_name} is missing branch protections for {not_handled_patterns}. Creating them now...')
    for pattern in not_handled_patterns:
        # language=GraphQL
        await client.graphql(
            f'mutation {{\n'
            f'    createBranchProtectionRule(\n'
            f'        input: {{\n'
            f'            pattern: "{pattern}"\n'
            f'            repositoryId: "{repo_id}"\n'
            f'            clientMutationId: "{client_mutation_id}"\n'
            f'            allowsDeletions: false\n'
            f'            allowsForcePushes: false\n'
            f'            bypassForcePushActorIds: []\n'
            f'            bypassPullRequestActorIds: []\n'
            f'            dismissesStaleReviews: true\n'
            f'            isAdminEnforced: true\n'
            f'            pushActorIds: []\n'
            f'            requireLastPushApproval: false\n'
            f'            requiredApprovingReviewCount: 1\n'
            f'            requiredDeploymentEnvironments: []\n'
            f'            requiresApprovingReviews: true\n'
            f'            requiresCommitSignatures: true\n'
            f'            requiresConversationResolution: true\n'
            f'            requiresDeployments: false\n'
            f'            requiresLinearHistory: false\n'
            f'            restrictsPushes: true\n'
            f'            restrictsReviewDismissals: false\n'
            f'            reviewDismissalActorIds: []\n'
            f'        }}\n'
            f'    ) {{ clientMutationId }}\n'
            f'}}'
        )
        LOGGER.info(f'\t\tProtection created for `{pattern}`')


async def delete_rulesets(client: Client, repo_full_name: str) -> None:
    existing_rulesets = await client.get(f"/repos/{repo_full_name}/rulesets")
    if existing_rulesets:
        LOGGER.info(f"\tDeleting {len(existing_rulesets)} rulesets from {repo_full_name} cause they borked")
    for ruleset in existing_rulesets:
        await client.delete(f"/repos/{repo_full_name}/rulesets/{ruleset['id']}")


async def add_autolinks(client: Client, repo_full_name: str) -> None:
    existing_links = await client.get(f"/repos/{repo_full_name}/autolinks")

    existing_prefixes = [link["key_prefix"] for link in existing_links]
    prefixes_to_add = [prefix for prefix in ALL_JIRA_KEYS if prefix not in existing_prefixes]

    if prefixes_to_add:
        LOGGER.info(f"\tAdding autolinks to {repo_full_name}: {prefixes_to_add}")
    for prefix in prefixes_to_add:
        if prefix not in existing_prefixes:
            await client.post(f"/repos/{repo_full_name}/autolinks", {
                "key_prefix": prefix,
                "url_template": f"https://tokenring.atlassian.net/browse/{prefix}<num>",
                "is_alphanumeric": False
            })


async def configure_repo_settings(client: Client, repo_full_name: str) -> None:
    LOGGER.info(f"\tConfiguring repo-level settings for {repo_full_name}")
    await client.patch(f"/repos/{repo_full_name}", {
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


if __name__ == '__main__':
    # Check that we can find our key. Fail fast if we can't.
    jwt_generator.generate()

    asyncio.run(main())
