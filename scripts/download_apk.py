#!/usr/bin/env python3
"""
Simple APK downloader for JioHotstar.
Reads the direct APK download URL from apk_url.txt and downloads it.
Handles XAPK/APKS bundles by extracting base.apk + arm64 split.
"""
import sys, os, subprocess, zipfile, shutil

APK_URL_FILE = "apk_url.txt"
OUTPUT = "jiohotstar.apk"

def main():
    if not os.path.exists(APK_URL_FILE):
        print(f"::error::Missing {APK_URL_FILE}. Create it and paste your direct APK download URL inside.", flush=True)
        sys.exit(1)

    with open(APK_URL_FILE, 'r') as f:
        url = f.read().strip()

    if not url or not url.startswith('http'):
        print(f"::error::{APK_URL_FILE} does not contain a valid URL", flush=True)
        sys.exit(1)

    print(f"=== Downloading APK ===", flush=True)
    print(f"  URL: {url[:80]}...", flush=True)

    # Download
    result = subprocess.run(
        ['curl', '-sS', '-L', '--max-time', '600', '-o', 'downloaded.bin', url],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"::error::curl failed: {result.stderr}", flush=True)
        sys.exit(1)

    if not os.path.exists('downloaded.bin') or os.path.getsize('downloaded.bin') < 1000000:
        size = os.path.getsize('downloaded.bin') if os.path.exists('downloaded.bin') else 0
        print(f"::error::Download too small ({size} bytes). URL may be expired or invalid.", flush=True)
        sys.exit(1)

    size_mb = os.path.getsize('downloaded.bin') / 1024 / 1024
    print(f"  Downloaded {size_mb:.1f} MB", flush=True)

    # Check file type
    with open('downloaded.bin', 'rb') as f:
        magic = f.read(4)

    if magic == b'PK\x03\x04':
        # It's a ZIP — could be a standalone APK or an XAPK/APKS bundle
        print("  File is ZIP-format, checking contents...", flush=True)

        # Check if it's a standalone APK (has AndroidManifest.xml at root)
        # or a bundle (has base.apk/splits inside)
        with zipfile.ZipFile('downloaded.bin', 'r') as z:
            names = z.namelist()
            has_manifest = 'AndroidManifest.xml' in names
            has_base_apk = any(n == 'base.apk' or n.endswith('/base.apk') for n in names)
            has_splits = any('splits/' in n or n.endswith('.apk') for n in names if n != 'AndroidManifest.xml')

        if has_manifest:
            # Standalone APK
            print("  ✓ Standalone APK detected", flush=True)
            shutil.move('downloaded.bin', OUTPUT)
        elif has_base_apk:
            # XAPK or APKS bundle — extract base.apk
            print("  ✓ XAPK/APKS bundle detected — extracting base.apk...", flush=True)
            with zipfile.ZipFile('downloaded.bin', 'r') as z:
                # Extract base.apk
                z.extract('base.apk', '.')
                shutil.move('base.apk', OUTPUT)

                # Try to extract arm64 split for native libs
                arm64_split = None
                for name in names:
                    if 'arm64' in name.lower() and name.endswith('.apk'):
                        arm64_split = name
                        break
                if arm64_split:
                    print(f"  ✓ Found arm64 split: {arm64_split}", flush=True)
                    z.extract(arm64_split, '.')
                    # Rename to arm64_split.apk for the build pipeline
                    extracted_path = os.path.join('.', arm64_split)
                    if os.path.exists(extracted_path):
                        shutil.move(extracted_path, 'arm64_split.apk')
                else:
                    print("  ⚠ No arm64 split found (native libs may be missing)", flush=True)

            os.remove('downloaded.bin')
        else:
            # Unknown ZIP format — try using it as-is
            print("  ⚠ Unknown ZIP format, trying as APK...", flush=True)
            shutil.move('downloaded.bin', OUTPUT)
    else:
        # Not a ZIP — might be a raw binary
        print(f"  ⚠ Unexpected file format (magic: {magic.hex()}), trying anyway...", flush=True)
        shutil.move('downloaded.bin', OUTPUT)

    # Verify final APK
    if not os.path.exists(OUTPUT) or os.path.getsize(OUTPUT) < 5000000:
        size = os.path.getsize(OUTPUT) if os.path.exists(OUTPUT) else 0
        print(f"::error::Final APK too small ({size} bytes)", flush=True)
        sys.exit(1)

    final_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"✅ Ready: {OUTPUT} ({final_mb:.1f} MB)", flush=True)

if __name__ == '__main__':
    main()
