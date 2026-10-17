#!/usr/bin/env python3
"""Run in COPR's network-enabled source chroot; prepare offline RPM inputs."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tag', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--release', type=int, required=True)
    a = p.parse_args()
    if not re.fullmatch(r'v?\d+(?:\.\d+){1,3}', a.tag):
        p.error('Only numeric stable release tags are supported')
    if not re.fullmatch(r'[a-f0-9]{40}', a.commit) or a.release < 1:
        p.error('Expected a full commit SHA and a positive RPM release')
    version = a.tag.removeprefix('v')
    out = ROOT / 'results'
    out.mkdir(exist_ok=True)
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1',
               DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1')
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        src = work / 'src'
        run('git', 'init', str(src))
        run('git', '-C', str(src), 'fetch', '--depth=1',
            'https://github.com/yocksers/Wiim-Control.git', a.commit)
        run('git', '-C', str(src), 'checkout', '--detach', a.commit)
        project = ET.parse(src / 'WiimControl.csproj')
        if project.findtext('.//Version') != version:
            raise ValueError('Release tag does not match the project version')
        run('git', '-C', str(src), 'archive', '--format=tar.gz',
            f'--prefix=wiim-control-{a.commit}/',
            f'--output={out}/wiim-control-{a.commit}.tar.gz', a.commit)
        env.update(DOTNET_CLI_HOME=str(work / 'dotnet'),
                   NUGET_PACKAGES=str(work / 'packages'))
        run('dotnet', 'restore', str(src / 'WiimControl.csproj'), '-r', 'linux-x64',
            '-p:RuntimeIdentifiers=linux-x64', '-p:SelfContained=false',
            '-p:NuGetAudit=false', env=env)
        feed = work / 'nuget-feed'
        licenses = work / 'nuget-licenses'
        feed.mkdir()
        licenses.mkdir()
        packages = work / 'packages'
        for nupkg in packages.rglob('*.nupkg'):
            shutil.copy2(nupkg, feed / nupkg.name)
        for f in packages.rglob('*'):
            if f.is_file() and any(s in f.name.lower() for s in ('license', 'notice', 'copying')):
                dest = licenses / f.relative_to(packages)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
        if not list(feed.iterdir()):
            raise RuntimeError('NuGet restore produced no package archives')
        with tarfile.open(out / 'nuget-feed.tar.gz', 'w:gz') as tar:
            tar.add(feed, arcname='nuget-feed')
            tar.add(licenses, arcname='nuget-licenses')
    spec = (ROOT / 'wiim-control.spec.in').read_text()
    for key, value in {'COMMIT': a.commit, 'VERSION': version, 'RELEASE': str(a.release)}.items():
        spec = spec.replace('@' + key + '@', value)
    (out / 'wiim-control.spec').write_text(spec)
    shutil.copy2(ROOT / 'rpm-updates.patch', out)


if __name__ == '__main__':
    main()
