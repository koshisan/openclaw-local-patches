# openclaw-local-patches

Local patches applied to **installed** openclaw npm bundles that are not (yet) upstreamed.

The openclaw CLI/gateway is distributed as a pre-compiled bundle under
`node_modules/openclaw/dist/*.mjs`. Any patch we apply there is in-place and gets
overwritten on `npm update openclaw`. This repo tracks those patches as committed,
reviewable artefacts and ships a re-apply script so a routine upgrade doesn't
silently revert them.

## Current patches

| Patch | Script | Minimum openclaw version | Target |
|---|---|---|---|
| Trusted-proxy loopback fallback | [`patches/trusted-proxy-loopback-fallback.py`](patches/trusted-proxy-loopback-fallback.py) | 2026.9.4 | `dist/ingress-attribution-*.mjs` |

See each patch script's docstring for the exact behavioural change and why we
need it locally.

## Usage

Dry-run (shows what would change, writes nothing):

```
./apply-all.sh --dry-run
```

Apply against the npm install at `~/.npm-global/lib/node_modules/openclaw`:

```
./apply-all.sh
```

Point at a different install root:

```
./apply-all.sh --openclaw /opt/openclaw
```

Each patch script is idempotent — running it a second time is a no-op if the
patch is already in place.

## After `npm update openclaw`

Re-run `./apply-all.sh`. The scripts verify the version in `package.json` and
refuse to apply if openclaw has been updated past the "minimum" window the
patch was tested against; bump the version check in the script when you've
verified the patch still makes sense on the new release.

## Backup convention

Before overwriting any bundle file, each patch script writes a backup next to
the original with a suffix identifying the patch (e.g.
`ingress-attribution-XYZ.mjs.bak-trusted-proxy-loopback`). The script will not
overwrite an existing backup.
