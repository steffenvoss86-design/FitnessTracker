#!/usr/bin/env python3
"""Regenerate the self-contained standalone `index.html` from the editable source
`src/Workout Tracker.dc.html`.

`index.html` is a "bundler" file: the app markup+logic lives in a JSON-encoded
`<script type="__bundler/template">` string, and `support.js` + web-fonts are stored
as gzipped-base64 assets referenced by uuid (in `__bundler/manifest`). This script
keeps that wrapper and all assets intact and only rebuilds the template from the
current source, swapping the dev-time asset references for the bundled offline ones:

  * `<script src="./support.js">`            -> the support.js bundle uuid
  * the Google-Fonts stylesheet `<link>`     -> the inlined `@font-face <style>` block

Run it after editing `src/Workout Tracker.dc.html`:

    python "src/build-standalone.py"

No third-party dependencies. The source stays the single place you edit by hand.
"""
import re, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DC  = os.path.join(ROOT, "src", "Workout Tracker.dc.html")
IDX = os.path.join(ROOT, "index.html")

dc  = open(DC, encoding="utf-8").read()
idx = open(IDX, encoding="utf-8").read()

m = re.search(r'(<script type="__bundler/template">)(.*?)(</script>)', idx, re.S)
if not m:
    sys.exit("index.html has no __bundler/template script")
cur_tpl = json.loads(m.group(2))

# support.js bundled-asset uuid (the <script src> inside the current template)
sup = re.search(r'<script src="([0-9a-f-]{36})">\s*</script>', cur_tpl)
if not sup:
    sys.exit("could not find the support.js asset uuid in the current template")
support_uuid = sup.group(1)

# the inlined @font-face <style> block that replaced the Google-Fonts <link>
fs = re.search(r'<style>(?:(?!</style>).)*?@font-face.*?</style>', cur_tpl, re.S)
if not fs:
    sys.exit("could not find the inlined @font-face <style> block")
fontstyle = fs.group(0)

# --- build the new template from the edited source -------------------------
t = dc
assert t.count('<script src="./support.js"></script>') == 1, "source support.js ref missing/not unique"
t = t.replace('<script src="./support.js"></script>', '<script src="%s"></script>' % support_uuid)

lk = re.search(r'<link href="https://fonts\.googleapis\.com/css2[^>]*rel="stylesheet">', t)
assert lk, "source Google-Fonts <link> not found"
t = t[:lk.start()] + fontstyle + t[lk.end():]

# every referenced asset uuid must exist in the manifest
manifest = json.loads(re.search(r'<script type="__bundler/manifest">(.*?)</script>', idx, re.S).group(1))
used = set(re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', t))
missing = used - set(manifest)
assert not missing, "template references assets not in the manifest: %s" % sorted(missing)

# Encode. Escape every "</" as "<\/" exactly like the bundler: it keeps the outer
# <script> tag from closing early AND stops support.js's parseDcText() from finding
# a literal </x-dc> in the raw file (which would wrongly override the live render).
new_json = json.dumps(t, ensure_ascii=False).replace("</", "<\\/")
out = idx[:m.start(2)] + new_json + idx[m.end(2):]
assert json.loads(re.search(r'<script type="__bundler/template">(.*?)</script>', out, re.S).group(1)) == t

with open(IDX, "w", encoding="utf-8", newline="\n") as f:
    f.write(out)

print("Rebuilt index.html from src/Workout Tracker.dc.html (%d asset references)." % len(used))
