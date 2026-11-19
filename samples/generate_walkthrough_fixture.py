from __future__ import annotations
import csv, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SAMPLES=ROOT/'samples'
PUBLIC=ROOT/'frontend'/'public'/'demo'
source=(SAMPLES/'orders_dirty.csv').open('r',encoding='utf-8',newline='')
rows=list(csv.reader(source));source.close()
header=rows[0]
assert len(rows[150])==len(header)
rows[150].append('UNEXPECTED_REVIEW_FIELD')
with (SAMPLES/'walkthrough_dirty.csv').open('w',encoding='utf-8',newline='') as f: csv.writer(f,lineterminator='\n').writerows(rows)
manifest=json.loads((SAMPLES/'orders_error_manifest.json').read_text(encoding='utf-8'))
manifest['dataset']='DataFix live walkthrough sample (synthetic)'
manifest['source_dataset']='orders_dirty.csv'
manifest['errors'].append({'error_id':'unexpected-extra-field','row_id':'row_150','column':None,'original_value':None,'injected_value':'UNEXPECTED_REVIEW_FIELD','category':'row_structure_mismatch','expected_detector':'row_structure_mismatch','expected_outcome':'preserve_and_require_review','detail':'One row contains an extra field. Preserve it as overflow metadata and require human review before removing it; never guess a destination column.'})
manifest['walkthrough_note']='The UI preview is illustrative; the live walkthrough uploads this generated fixture to the configured DataFix backend. The existing clean-truth file remains the 1,000-row reference for all original business values.'
(SAMPLES/'walkthrough_error_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
PUBLIC.mkdir(parents=True,exist_ok=True)
shutil.copyfile(SAMPLES/'walkthrough_dirty.csv',PUBLIC/'walkthrough_dirty.csv')
shutil.copyfile(SAMPLES/'walkthrough_error_manifest.json',PUBLIC/'walkthrough_error_manifest.json')
print(f'Generated {SAMPLES / "walkthrough_dirty.csv"} ({len(rows)-1} data records, {len(header)} declared columns)')
print(f'Copied live demo asset to {PUBLIC}')
