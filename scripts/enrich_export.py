"""Enrich the prepared source export with independently checked display coordinates."""
import json
from collections import Counter
from pathlib import Path
from wellspring.geo import enrich_event
from wellspring.ingest.publish import snapshot,write_local
root=Path('output/source-data')
m=json.loads((root/'manifest.json').read_text())
rows=[enrich_event(json.loads(line)) for line in (root/m['export_file']).read_text().splitlines() if line]
raw,out=snapshot(rows,m['dates'],now=m['data_as_of'])
write_local(Path('output/published'),raw,out)
print(json.dumps({'events':len(rows),'plotted':sum(r['latitude'] is not None for r in rows),'unplotted_reasons':dict(Counter(r['location_reason'] for r in rows if r['latitude'] is None)),'sha256':out['export_sha256']}))
