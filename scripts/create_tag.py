import os
import sys
import re
from typing import List, Optional
from packaging import version as packaging_version
from github import Github

# Helpers -------------------------------------------------

def log(msg: str):
    print(msg, flush=True)


def get_bool(env_name: str, default: bool = False) -> bool:
    val = os.getenv(env_name, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def increment_semver(current: str, bump: str, prerelease: bool, prerelease_identifier: str) -> str:
    # current expected like v1.2.3 or 1.2.3 or v1.2.3-alpha.1
    cur = current.lstrip('v')
    parsed = packaging_version.parse(cur)

    # packaging.version does not let us simply bump; we parse manually
    # Extract base numeric part and any pre-release
    m = re.match(r"(\d+)\.(\d+)\.(\d+)(?:[-.]?([0-9A-Za-z.-]+))?", cur)
    if not m:
        raise ValueError(f"Invalid semantic version: {current}")
    major, minor, patch, pre = m.groups()
    major, minor, patch = int(major), int(minor), int(patch)

    if bump == 'major':
        major += 1; minor = 0; patch = 0; pre = None
    elif bump == 'minor':
        minor += 1; patch = 0; pre = None
    elif bump == 'patch':
        patch += 1; pre = None
    elif bump == 'prerelease':
        if pre and prerelease_identifier in pre:
            # increment last numeric component
            parts = pre.split('.')
            if parts and parts[-1].isdigit():
                parts[-1] = str(int(parts[-1]) + 1)
            else:
                parts.append('1')
            pre = '.'.join(parts)
        else:
            if prerelease:
                pre = f"{prerelease_identifier}.1"
            else:
                # If prerelease flag false, treat as patch bump
                patch += 1
                pre = None
    else:
        # default fallback patch
        patch += 1; pre = None

    base = f"{major}.{minor}.{patch}"
    return f"v{base}-{pre}" if pre else f"v{base}"


def coerce_tag_name(tag: str) -> Optional[str]:
    # Accept things like v1.2.3, 1.2.3, refs/tags/v1.2.3
    tag = tag.strip()
    if tag.startswith('refs/tags/'):
        tag = tag[len('refs/tags/'):]
    tag_no_v = tag.lstrip('v')
    m = re.match(r"(\d+)\.(\d+)\.(\d+)(?:[-.]?([0-9A-Za-z.-]+))?", tag_no_v)
    if not m:
        return None
    major, minor, patch, pre = m.groups()
    base = f"{int(major)}.{int(minor)}.{int(patch)}"
    return f"v{base}-{pre}" if pre else f"v{base}"


def sort_versions_desc(tags: List[str]) -> List[str]:
    def key(t: str):
        t_clean = t.lstrip('v')
        return packaging_version.parse(t_clean)
    return sorted(tags, key=key, reverse=True)

# Core logic ---------------------------------------------

def fetch_all_repo_tags(gh: Github, owner_repo: str, fetch_all: bool) -> List[str]:
    """Fetch tags using PyGithub. If fetch_all is False, limit to first 100 coerced tags."""
    repo = gh.get_repo(owner_repo)
    tags = []
    for t in repo.get_tags():  # PaginatedList iterates automatically
        coerced = coerce_tag_name(t.name)
        if coerced:
            tags.append(coerced)
        if not fetch_all and len(tags) >= 100:
            break
    return tags


def determine_new_tag(existing_tags: List[str], default_bump: str, prerelease_identifier: str, prerelease_flag: bool) -> str:
    if not existing_tags:
        return 'v1.0.0'
    sorted_tags = sort_versions_desc(existing_tags)
    latest = sorted_tags[0]
    return increment_semver(latest, default_bump, prerelease_flag, prerelease_identifier)


def main():
    try:
        log('Python Tag Action Started..')
        user_tag = os.getenv('INPUT_USER_TAG', '').strip()
        default_bump = os.getenv('INPUT_DEFAULT_BUMP', 'patch').strip()
        tag_suffix = os.getenv('INPUT_TAG_SUFFIX', '').strip()
        tag_prefix = os.getenv('INPUT_TAG_PREFIX', '').strip()
        prerelease_identifier_raw = os.getenv('INPUT_PRERELEASEIDENTIFIER', 'true').strip()
        # If user passes 'true' or 'false' we treat as flag controlling numbering; default identifier is 'prerelease'
        if prerelease_identifier_raw.lower() in ('true', 'false'):
            prerelease_flag = prerelease_identifier_raw.lower() == 'true'
            prerelease_identifier = 'prerelease'
        else:
            prerelease_identifier = prerelease_identifier_raw
            prerelease_flag = True
        github_token = os.getenv('INPUT_GITHUB_TOKEN')
        fetch_all_tags = get_bool('INPUT_FETCH_ALL_TAGS', False)
        is_dry_run = get_bool('INPUT_IS_DRY_RUN', False)
        repository = os.getenv('GITHUB_REPOSITORY')
        commit_sha = os.getenv('GITHUB_SHA')

        if not github_token:
            raise ValueError('GitHub token not provided')
        if not repository:
            raise ValueError('GITHUB_REPOSITORY env var missing')
        if not commit_sha:
            raise ValueError('GITHUB_SHA env var missing')

        gh = Github(github_token)

        if user_tag:
            new_tag = user_tag
        else:
            tags = fetch_all_repo_tags(gh, repository, fetch_all_tags)
            new_tag = determine_new_tag(tags, default_bump, prerelease_identifier, prerelease_flag)

        if tag_suffix and tag_suffix != 'prerelease':
            new_tag = f"{new_tag}-{tag_suffix}"

        version_value = new_tag[1:] if new_tag.startswith('v') else new_tag

        if tag_prefix:
            new_tag = f"{tag_prefix}-{new_tag}"
            version_value = f"{tag_prefix}-{version_value}"

        log(f"New tag computed: {new_tag}")

        if is_dry_run:
            log('Dry run enabled. Tag not pushed.')
        else:
            owner, repo = repository.split('/')
            ref = f"refs/tags/{new_tag}"
            gh.get_repo(repository).create_git_ref(ref=ref, sha=commit_sha)
            log('Tag created successfully')

        # Set outputs
        github_output = os.getenv('GITHUB_OUTPUT')
        if not github_output:
            # Fallback path (unlikely in GitHub runners but useful for local tests)
            github_output = os.path.join(os.getcwd(), 'GITHUB_OUTPUT.txt')
        with open(github_output, 'a', encoding='utf-8') as fh:
            fh.write(f"tag={new_tag}\n")
            fh.write(f"version={version_value}\n")

        log('Python Tag Action Completed Successfully')
    except Exception as e:
        log(f"::error::{e}")
        # Also fail the action
    # ::set-output deprecated; using exit code only.
        sys.exit(1)


if __name__ == '__main__':
    main()
