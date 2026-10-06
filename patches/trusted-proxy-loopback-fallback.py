#!/usr/bin/env python3
"""Patch openclaw's ingress-attribution to accept loopback / null X-Forwarded-For
values when the request arrives from a configured trusted proxy.

Why we need it
--------------
openclaw's gateway `auth.mode = "trusted-proxy"` depends on the client-IP
attribution logic in `resolveGatewayIngressAttribution`. Vanilla logic:

    if (isTrustedProxyAddress(remoteAddress, params.trustedProxies)) {
        const clientIp = resolveRequestClientIpFromHeaders(
            req, params.trustedProxies, params.allowRealIpFallback === true,
        );
        if (!clientIp || isLoopbackAddress(clientIp))
            return unattributableProxy(remoteAddress);
        return attributed("trusted-proxy", clientIp);
    }

That rejects any proxy forward where the X-Forwarded-For chain only contains
loopback (or the proxy's own IP). Which is exactly what happens when
Home Assistant talks to its own nginx add-on at `wss://ai.koshi.de`: nginx on
`192.168.81.211` forwards to the openclaw backend with `X-Forwarded-For:
127.0.0.1` because HA reaches nginx via localhost — the chain walker returns
nothing non-loopback, and the authenticated-user path 403s with
`proxy_attribution_required`.

The patch replaces the hard reject with a fallback: if the chain produces no
non-loopback client, attribute the connection to the proxy address itself.
That's safe here because the proxy address *is* already known-and-trusted
(it only got into this branch at all via `isTrustedProxyAddress`), and it
restores the behaviour `trusted-proxy` is supposed to give — "trust the hop
in front of me and don't demand it prove the identity further."

Reversible via the `.bak-trusted-proxy-loopback` sibling file.

Usage
-----
    python3 patches/trusted-proxy-loopback-fallback.py [--openclaw /path/to/openclaw]
                                                       [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# openclaw releases this patch is known-good on. If package.json reports a
# version outside this allow-list, the script refuses to apply — bump the list
# after re-verifying the patch against the newer bundle.
SUPPORTED_VERSION_PREFIXES = ("2026.9.",)

OLD_SNIPPET = (
    "if (isTrustedProxyAddress(remoteAddress, params.trustedProxies)) {\n"
    "\t\tconst clientIp = resolveRequestClientIpFromHeaders(req, params.trustedProxies, params.allowRealIpFallback === true);\n"
    "\t\tif (!clientIp || isLoopbackAddress(clientIp)) return unattributableProxy(remoteAddress);"
)

NEW_SNIPPET = (
    "if (isTrustedProxyAddress(remoteAddress, params.trustedProxies)) {\n"
    "\t\tlet clientIp = resolveRequestClientIpFromHeaders(req, params.trustedProxies, params.allowRealIpFallback === true);\n"
    "\t\tif (!clientIp || isLoopbackAddress(clientIp)) clientIp = remoteAddress;"
)

BACKUP_SUFFIX = ".bak-trusted-proxy-loopback"


def find_target_file(openclaw_root: pathlib.Path) -> pathlib.Path:
    dist = openclaw_root / "dist"
    if not dist.is_dir():
        raise SystemExit(f"not a valid openclaw install: {dist} is missing")
    candidates = sorted(dist.glob("ingress-attribution-*.mjs"))
    # Exclude existing backups.
    candidates = [c for c in candidates if not c.name.endswith(BACKUP_SUFFIX)]
    if not candidates:
        raise SystemExit(
            f"no ingress-attribution-*.mjs under {dist}; "
            "openclaw layout may have changed"
        )
    if len(candidates) > 1:
        raise SystemExit(
            "ambiguous: multiple ingress-attribution-*.mjs files, cannot pick: "
            + ", ".join(c.name for c in candidates)
        )
    return candidates[0]


def check_version(openclaw_root: pathlib.Path) -> str:
    pkg = openclaw_root / "package.json"
    if not pkg.is_file():
        raise SystemExit(f"no package.json at {pkg}")
    data = json.loads(pkg.read_text())
    version = data.get("version") or "?"
    if not any(version.startswith(p) for p in SUPPORTED_VERSION_PREFIXES):
        raise SystemExit(
            f"openclaw {version} is outside the tested window "
            f"({', '.join(SUPPORTED_VERSION_PREFIXES)}); re-verify the patch "
            "manually against the new bundle before bumping "
            "SUPPORTED_VERSION_PREFIXES in this script."
        )
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--openclaw",
        type=pathlib.Path,
        default=pathlib.Path.home() / ".npm-global/lib/node_modules/openclaw",
        help="openclaw npm install root (default: ~/.npm-global/lib/node_modules/openclaw)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen without writing anything",
    )
    args = parser.parse_args()

    version = check_version(args.openclaw)
    target = find_target_file(args.openclaw)
    original = target.read_text()

    if NEW_SNIPPET in original and OLD_SNIPPET not in original:
        print(f"[ok] already patched: {target}  (openclaw {version})")
        return 0

    if OLD_SNIPPET not in original:
        raise SystemExit(
            f"neither original nor patched snippet found in {target}; "
            "manual inspection required"
        )

    patched = original.replace(OLD_SNIPPET, NEW_SNIPPET, 1)
    backup = target.with_name(target.name + BACKUP_SUFFIX)

    if args.dry_run:
        print(f"[dry-run] would backup to {backup}")
        print(f"[dry-run] would patch {target}  (openclaw {version})")
        return 0

    if not backup.exists():
        backup.write_text(original)
        print(f"[backup] wrote {backup}")
    else:
        print(f"[backup] already exists, leaving: {backup}")

    target.write_text(patched)
    print(f"[patched] {target}  (openclaw {version})")
    print("Restart the openclaw gateway service to pick up the change:")
    print("  openclaw gateway restart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
