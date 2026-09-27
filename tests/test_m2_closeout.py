"""Regressions for merged M2 review findings, with labelled real-fixture mutations."""
import json
import runpy
from pathlib import Path
from wellspring.ingest.parser import parse_report
from wellspring.ingest.store import connect,import_report,events
from wellspring.geo import enrich_event

ROOT=Path(__file__).resolve().parents[1]
URL='https://static.aer.ca/prd/data/well-lic/WELLS0925.TXT'


def unsupported_surface_raw():
    # Only the surface meridian of the first real issued block changes. W3 is
    # outside this Alberta converter; the surrounding well record remains valid.
    raw=(ROOT/'fixtures/WELLS0925.TXT').read_bytes()
    assert b'16-12-066-03W4' in raw
    return raw.replace(b'16-12-066-03W4',b'16-12-066-03W3',1)


def test_unsupported_surface_dls_keeps_whole_day_and_reason(tmp_path):
    report=parse_report(unsupported_surface_raw(),source_url=URL)
    assert report.status=='loaded'
    assert report.issues==[]
    assert len(report.events)==48
    first=report.events[0]
    assert first.dls is None and first.location_reason=='invalid_surface_dls'
    assert first.surface_location=='16-12-066-03W3'
    enriched=enrich_event(first.to_dict())
    assert enriched['latitude'] is None and enriched['longitude'] is None
    assert enriched['location_reason']=='invalid_surface_dls'
    conn=connect(tmp_path/'events.sqlite3')
    try:
        assert import_report(conn,report)['status']=='imported'
        assert len(events(conn))==48
        saved=events(conn)
        target=next(x for x in saved if x['id']==first.id)
        assert target['location_reason']=='invalid_surface_dls'
    finally:conn.close()


def test_generated_ask_example_matches_stub():
    runpy.run_path(str(ROOT/'scripts/export_contract.py'))
    from wellspring.api.handler import _ask_refusal
    example=json.loads((ROOT/'contracts/ask-refusal.example.json').read_text())
    actual=_ask_refusal(None)
    assert example['status']==actual['status']=='refused'
    assert example['refusal']==actual['refusal']
    assert example['sql'] is None and example['rows']==[]


def test_generated_licences_examples_show_enriched_and_null_cases():
    runpy.run_path(str(ROOT/'scripts/export_contract.py'))
    example=json.loads((ROOT/'contracts/licences.example.json').read_text())
    assert example['page_size']==len(example['items'])==2
    mapped,missing=example['items']
    assert mapped['latitude'] is not None and mapped['longitude'] is not None
    assert mapped['location_accuracy']=='approximate' and mapped['location_reason'] is None
    assert missing['latitude'] is None and missing['longitude'] is None
    assert missing['location_reason'] is not None


def test_stale_prior_year_cache_is_refetched_without_losing_bytes(tmp_path,monkeypatch):
    import importlib.util,hashlib
    from datetime import date
    from types import SimpleNamespace
    spec=importlib.util.spec_from_file_location('build_data_under_test',ROOT/'scripts/build_data.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    current=(ROOT/'fixtures/WELLS0925.TXT').read_bytes()
    old=current.replace(b'2026',b'2025',1)
    (tmp_path/'2026-09-25.txt').write_bytes(old)
    called=[]
    def download(url):
        called.append(url);return SimpleNamespace(status='downloaded',raw=current)
    monkeypatch.setattr(module,'download',download)
    result=module.get_day(date(2026,9,25),tmp_path)
    assert result[2]==current and len(called)==1
    assert (tmp_path/f'{hashlib.sha256(old).hexdigest()}.txt').read_bytes()==old
    called.clear()
    assert module.get_day(date(2026,9,25),tmp_path)[2]==current
    assert called==[]
