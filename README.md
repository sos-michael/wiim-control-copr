# Wiim-Control RPMs

Unofficial Fedora 44 x86_64 packages for [Wiim-Control](https://github.com/yocksers/Wiim-Control).

```sh
sudo dnf copr enable grantson/wiim-control
sudo dnf install wiim-control
```

Launch **Wiim Control** from the application menu or run `wiim-control`.
The General page configures desktop shortcuts and starting at login.
The GNOME tray icon requires AppIndicator and KStatusNotifierItem Support.
Volume shortcuts can also invoke `wiim-control --volume-up`,
`wiim-control --volume-down`, and `wiim-control --mute` while the app runs.

## Updates

[GitHub Actions](https://github.com/sos-michael/wiim-control-copr/actions/workflows/releases.yml)
checks stable upstream releases daily at 14:37 UTC. GitHub may delay scheduled jobs.
All stable releases published from v1.20 onward are considered, so releases
between daily checks are picked up. Drafts and prereleases are excluded.
Each release is pinned to its full upstream commit. Successful builds are
remembered in COPR history; failed builds retry at the next check. Recipe
changes rebuild the latest release with a higher RPM release number. An
unchanged successful build is not submitted again. Manual checks and forced
rebuilds are available in Actions. A monthly activity commit keeps the public
repository's schedule from being suspended after 60 days of inactivity.

[COPR](https://copr.fedorainfracloud.org/coprs/grantson/wiim-control/)
builds the application from source. NuGet dependencies are collected in the
source stage and included in the source RPM; the RPM build works offline.
The application uses Fedora's .NET 9 runtime rather than bundling a runtime.
The small downstream patch replaces the upstream download/update panel with
system-update instructions. No AppImage is used. SMBLibrary remains a separate
DLL, and available dependency license notices are installed with the RPM.

Maintainers: `COPR_CONFIG` is a repository Actions secret containing a COPR
client configuration with build access. Never commit credentials.
To validate decisions locally, run `python3 -m unittest -v`.
With the requirements installed, `python3 check_releases.py --dry-run`
checks upstream and COPR without submitting a build.
