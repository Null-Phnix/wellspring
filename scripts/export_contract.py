"""Generate JSON contract and a real-fixture example from the shared vocabulary."""
import json
from pathlib import Path
from wellspring.ingest.models import EventType, TEXT_FIELDS, NUMBER_FIELDS, LicenceEvent
from wellspring.ingest.parser import parse_report
from wellspring.geo import enrich_event
from wellspring.api.handler import _ask_refusal

ROOT=Path(__file__).resolve().parents[1]
def obj(props): return {'type':'object','additionalProperties':False,'required':list(props),'properties':props}
text={'type':'string'}
nullable_text={'type':['string','null']}
nullable_number={'type':['number','null']}
source=obj({'url':text,'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},'retrieved_at':{'type':'string','format':'date-time'},'parser_version':text})
occurrence=obj({'ordinal':{'type':'integer','minimum':0},'well_name':nullable_text,'uwi':nullable_text,'changes':{'type':'array','items':obj({'field':text,'label':text,'value':text})},'source_line_start':{'type':'integer','minimum':1},'source_line_end':{'type':'integer','minimum':1},'raw_text':text})
dls=obj({name:{'type':'integer','minimum':low,'maximum':high} for name,low,high in [('lsd',1,16),('section',1,36),('township',1,126),('range',1,30),('meridian',4,6)]})
props={'schema_version':{'const':1},'id':{'type':'string','pattern':'^[a-f0-9]{64}$'},'report_date':{'type':'string','format':'date'},'event_type':{'enum':[x.value for x in EventType]},'licence_number':{'type':'string','pattern':'^[0-9]{7}$'},**{x:nullable_text for x in TEXT_FIELDS},**{x:nullable_number for x in NUMBER_FIELDS},'dls':{'anyOf':[dls,{'type':'null'}]},'latitude':{'type':['number','null'],'minimum':-90,'maximum':90},'longitude':{'type':['number','null'],'minimum':-180,'maximum':180},'coordinate_method':nullable_text,'location_reason':nullable_text,'location_accuracy':{'enum':['approximate',None]},'occurrence_count':{'type':'integer','minimum':1},'occurrences':{'type':'array','minItems':1,'items':occurrence},'source':source}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','title':'Wellspring LicenceEvent v1',**obj(props)}
report=parse_report((ROOT/'fixtures/WELLS0925.TXT').read_bytes(),source_url='https://static.aer.ca/prd/data/well-lic/WELLS0925.TXT',retrieved_at='2026-09-27T00:00:00Z')
record=enrich_event(report.events[0].to_dict())
missing=enrich_event(next(e for e in report.events if e.event_type==EventType.CANCELLED).to_dict())
meta={'schema_version':1,'data_as_of':None,'date_from':'2026-09-25','date_to':'2026-09-25','event_type':'all','coverage':{'reports_loaded':1,'loaded_dates':['2026-09-25'],'empty_dates':[],'missing_dates':[],'failed_dates':[],'parse_issue_count':0}}
files={'licence-event.schema.json':schema,'licences.example.json':{'items':[record,missing],'total':len(report.events),'page':1,'page_size':2,'meta':meta},'ask-refusal.example.json':_ask_refusal(None)}
for name,data in files.items(): (ROOT/'contracts'/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
