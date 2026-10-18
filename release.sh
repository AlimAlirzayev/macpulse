#!/bin/bash
# Produce the verifiable-release artifacts for the macpulse files in this directory.
#
#   ./release.sh
#
# SHA256SUMS    shasum format, one line per shipped file. COMMIT this file: install.sh
#               downloads it from the repo next to the files it verifies.
# sbom.cdx.json CycloneDX 1.5 SBOM, one "file" component per shipped file with its
#               SHA-256, and no dependencies (macpulse is stdlib-only). NOT committed:
#               it is attached to the GitHub release as an asset.
#
# Run it after the last edit and before the release commit; the sums describe the tree
# as it is at this moment. The checksums catch corruption and tampering in transit; they
# are not an Apple signature or notarisation.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FILES=(macpulse)
for f in macpulse_*.py; do [ -f "$f" ] && FILES+=("$f"); done
FILES+=(menubar.m install.sh LICENSE README.md)

for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "release.sh: missing shipped file: $f" >&2; exit 1; }
done

grep -q '^VERSION = "' macpulse || { echo "release.sh: no VERSION line in macpulse" >&2; exit 1; }

shasum -a 256 "${FILES[@]}" > SHA256SUMS

python3 - "${FILES[@]}" <<'PY'
import hashlib, json, re, sys, uuid

files = sys.argv[1:]
version = re.search(r'^VERSION = "([^"]+)"', open("macpulse", encoding="utf-8").read(), re.M).group(1)

def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

bom = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "serialNumber": "urn:uuid:" + str(uuid.uuid4()),
    "version": 1,
    "metadata": {
        "component": {
            "type": "application",
            "name": "macpulse",
            "version": version,
            "licenses": [{"license": {"id": "MIT"}}],
        },
    },
    "components": [
        {"type": "file", "name": f, "version": version,
         "hashes": [{"alg": "SHA-256", "content": sha256(f)}]}
        for f in files
    ],
}
with open("sbom.cdx.json", "w", encoding="utf-8") as out:
    json.dump(bom, out, indent=2)
    out.write("\n")
PY

echo "release.sh: wrote SHA256SUMS ($(wc -l < SHA256SUMS | tr -d ' ') files) and sbom.cdx.json"
echo "  commit SHA256SUMS; attach sbom.cdx.json and SHA256SUMS to the GitHub release."
