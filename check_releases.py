#!/usr/bin/env python3
"""Build stable upstream releases in COPR, remembering results in COPR history."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
OWNER, PROJECT = 'grantson', 'wiim-control'
UPSTREAM = 'yocksers/Wiim-Control'
START = '2026-10-17T17:24:01Z'
FINISHED = {'succeeded', 'failed', 'canceled', 'skipped'}
RECIPE_FILES = ('prepare.py', 'wiim-control.spec.in', 'rpm-updates.patch')


def github(endpoint):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'wiim-control-copr'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    request = urllib.request.Request('https://api.github.com/repos/' + UPSTREAM + '/' + endpoint, headers=headers)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def releases():
    found = []
    page = 1
    while True:
        batch = github(f'releases?per_page=100&page={page}')
        for release in batch:
            if release['draft'] or release['prerelease'] or release['published_at'] < START:
                continue
            if not re.fullmatch(r'v?\d+(?:\.\d+){1,3}', release['tag_name']):
                raise ValueError('Review unsupported stable tag: ' + release['tag_name'])
            found.append(release)
        if len(batch) < 100:
            break
        page += 1
    return sorted(found, key=lambda r: tuple(int(n) for n in r['tag_name'].removeprefix('v').split('.')))


def recipe_hash():
    digest = hashlib.sha256()
    for name in RECIPE_FILES:
        digest.update(name.encode() + b'\0' + (ROOT / name).read_bytes() + b'\0')
    return digest.hexdigest()


def decision(records, tag, commit, recipe, latest=True, force=False):
    """Return (build-needed, pending-build, next-RPM-release)."""
    same_tag = [r for r in records if r['meta']['tag'] == tag]
    serial = max((r['meta']['release'] for r in same_tag), default=0) + 1
    pending = [r for r in same_tag if r['state'] not in FINISHED]
    if pending:
        return False, pending[0]['id'], serial
    for r in same_tag:
        m = r['meta']
        if (r['state'] == 'succeeded' and m['commit'] == commit and
                (not latest or (m['recipe'] == recipe and not force))):
            return False, None, serial
    return True, None, serial


def history(client):
    records = []
    offset = 0
    while True:
        batch = list(client.build_proxy.get_list(OWNER, PROJECT, pagination={'limit': 100, 'offset': offset}))
        for build in batch:
            config = client.build_proxy.get_source_build_config(build['id'])
            script = config.get('source_dict', {}).get('script', '')
            match = re.search(r'^# wiim-copr: (.+)$', script, re.M)
            if match:
                records.append({'id': build['id'], 'state': build['state'], 'meta': json.loads(match[1])})
        if len(batch) < 100:
            return records
        offset += 100


def source_script(meta, packaging_commit):
    if not re.fullmatch(r'[a-f0-9]{40}', packaging_commit):
        raise ValueError('Expected a pinned packaging commit')
    return f'''#!/bin/bash
set -euo pipefail
# wiim-copr: {json.dumps(meta, sort_keys=True)}
git init packaging
git -C packaging fetch --depth=1 https://github.com/sos-michael/wiim-control-copr.git {packaging_commit}
git -C packaging checkout --detach {packaging_commit}
python3 packaging/prepare.py --tag {meta['tag']} --commit {meta['commit']} --release {meta['release']}
'''


def watch(build_id):
    cmd = [str(Path(sys.executable).with_name('copr-cli'))]
    if os.environ.get('COPR_CONFIG_FILE'):
        cmd += ['--config', os.environ['COPR_CONFIG_FILE']]
    subprocess.run(cmd + ['watch-build', str(build_id)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--force', action='store_true', help='Rebuild the latest stable release')
    args = parser.parse_args()
    from copr.v3 import Client
    client = Client.create_from_config_file(os.environ.get('COPR_CONFIG_FILE'))
    all_releases = releases()
    if not all_releases:
        raise RuntimeError('No stable releases found at or after the initial release')
    recipe = recipe_hash()
    packaging_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    records = history(client)
    for release in all_releases:
        tag = release['tag_name']
        commit = github('commits/' + urllib.parse.quote(tag, safe=''))['sha']
        if not re.fullmatch(r'[a-f0-9]{40}', commit):
            raise ValueError('Invalid upstream commit SHA')
        latest = release == all_releases[-1]
        needed, pending, serial = decision(records, tag, commit, recipe, latest, args.force)
        if pending:
            print(f'{tag}: build {pending} is still active', flush=True)
            if args.wait and not args.dry_run:
                watch(pending)
                records = history(client)
                needed, pending, serial = decision(records, tag, commit, recipe, latest, args.force)
            else:
                continue
        if not needed:
            print(f'{tag}: already built successfully', flush=True)
            continue
        meta = {'tag': tag, 'commit': commit, 'recipe': recipe, 'release': serial}
        script = source_script(meta, packaging_commit)
        print(f'{tag}: build {commit} as RPM release {serial}', flush=True)
        if args.dry_run:
            continue
        build = client.build_proxy.create_from_custom(
            OWNER, PROJECT, script, script_chroot='fedora-44-x86_64',
            script_builddeps=['git-core', 'python3', 'dotnet-sdk-9.0'],
            script_resultdir='packaging/results')
        print(f'https://copr.fedorainfracloud.org/coprs/{OWNER}/{PROJECT}/build/{build.id}/', flush=True)
        records.insert(0, {'id': build.id, 'state': 'pending', 'meta': meta})
        if args.wait:
            watch(build.id)


if __name__ == '__main__':
    main()
