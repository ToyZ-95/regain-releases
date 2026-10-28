#!/usr/bin/env python3
"""Write download/latest.json: the update manifest the Regain app reads.

Facts come from the APK itself (aapt2) and the GitHub release, so nothing is duplicated:
the versionCode formula lives only in Regain's Gradle build.

Usage: make_latest_json.py <apk> <release.json from `gh release view --json …`> <aapt2> <out>
"""
import hashlib
import json
import os
import re
import subprocess
import sys

apk_path, release_path, aapt2, out_path = sys.argv[1:5]

# 1. Version straight from the APK's manifest (what Android itself will compare)
badging = subprocess.run([aapt2, "dump", "badging", apk_path],
                         check=True, capture_output=True, text=True).stdout
match = re.search(r"versionCode='(\d+)' versionName='([^']+)'", badging)
if not match:
    sys.exit("Could not read versionCode/versionName from the APK")
version_code, version_name = int(match.group(1)), match.group(2)

# 2. Checksum + size of the exact bytes being served
with open(apk_path, "rb") as f:
    sha256 = hashlib.sha256(f.read()).hexdigest()
size_bytes = os.path.getsize(apk_path)

# 3. Release info: immutable versioned asset URL + plain-text notes
with open(release_path) as f:
    release = json.load(f)
apk_asset = next(a for a in release["assets"] if a["name"] == "regain.apk")


def plain_notes(body: str) -> str:
    """Tag message only (drop the '--- Verify your download' block), Markdown → plain text."""
    text = re.split(r"\r?\n---\r?\n", body or "", maxsplit=1)[0]
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)        # headings
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)              # bold
    text = re.sub(r"`([^`]+)`", r"\1", text)                  # code
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.M)     # bullets
    return text.strip()


manifest = {
    "versionName": version_name,
    "versionCode": version_code,
    "apkUrl": apk_asset["url"],
    "sha256": sha256,
    "sizeBytes": size_bytes,
    "publishedAt": release["publishedAt"],
    "notes": plain_notes(release["body"]),
}

# Sanity check: the tag and the APK must agree (e.g. tag v1.2.3 ↔ versionName 1.2.3)
if release["tagName"].lstrip("v") != version_name:
    sys.exit(f"Tag {release['tagName']} does not match APK versionName {version_name}")

with open(out_path, "w") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
    f.write("\n")
print(json.dumps(manifest, indent=2, ensure_ascii=False))
