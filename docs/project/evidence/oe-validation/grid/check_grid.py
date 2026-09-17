from pathlib import Path
import json,math
from datetime import datetime,timedelta
p=Path(__file__).resolve().parent;allchecks=[]
for day in ['2026-09-11','2023-09-11']:
 start=datetime.fromisoformat(day+'T00:00:00+10:00');end=start+timedelta(days=1)
 for kind in ['demand','flows','generation']:
  def load(interval):
   o=json.loads((p/f'{day}-{kind}-{interval}-response.json').read_text());assert o['success'];return {(s['metric'],r['name']):(s,r) for s in o['data'] for r in s['results']}
  f=load('5m');h=load('1h')
  for k,(s,r) in f.items():
   raw=r['data'];rows=[(datetime.fromisoformat(t),v) for t,v in raw if start<=datetime.fromisoformat(t)<end];ts=[t for t,v in rows];values=[v for t,v in rows if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)];hr=h[k][1]['data'];diffs=[];shift=[]
   full={datetime.fromisoformat(t):v for t,v in raw}
   for t,v in hr:
    t=datetime.fromisoformat(t)
    if not start<=t<end:continue
    for offset,acc in [(0,diffs),(1,shift)]:
     samples=[full.get(t+timedelta(minutes=5*i)) for i in range(offset,offset+12)]
     if isinstance(v,(int,float)) and all(isinstance(x,(int,float)) for x in samples):acc.append(abs(sum(samples)/12-v))
   c=dict(day=day,metric=k[0],series=k[1],columns=r.get('columns'),unit=s['unit'],raw_count=len(raw),day_grid_count=len(rows),duplicates=len(ts)-len(set(ts)),missing=len({start+timedelta(minutes=5*i) for i in range(288)}-set(ts)),invalid=len(rows)-len(values),min=min(values) if values else None,max=max(values) if values else None,negative=sum(v<0 for v in values),hourly_comparisons=len(diffs),max_hourly_floor_mean_error=max(diffs) if diffs else None,max_hourly_end_aligned_error=max(shift) if shift else None)
   allchecks.append(c)
(p/'checks.json').write_text(json.dumps(allchecks,indent=2)+'\n')
for c in allchecks:print(c['day'],c['series'],'n',c['day_grid_count'],'bad',c['missing'],c['invalid'],'range',c['min'],c['max'],'hourly',c['max_hourly_floor_mean_error'], 'shifted',c['max_hourly_end_aligned_error'])
