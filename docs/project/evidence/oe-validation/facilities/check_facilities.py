from pathlib import Path
import json,math
from datetime import datetime,timedelta
p=Path(__file__).resolve().parent;meta=json.loads((p/'nsw-metadata-response.json').read_text())['data'];units={u['code']:(f['code'],u['fueltech_id'],u['dispatch_type']) for f in meta for u in f['units']}; checks=[];overlap=[]
for day in ['2026-09-11','2023-09-11']:
 start=datetime.fromisoformat(day+'T00:00:00+10:00');end=start+timedelta(days=1);expected={start+timedelta(minutes=5*i) for i in range(288)}
 obj=json.loads((p/f'{day}-unit-power-response.json').read_text());series=obj['data'][0]['results'];maps={}
 for s in series:
  code=s['columns']['unit_code'];assert code in units
  rows=[(datetime.fromisoformat(t),v) for t,v in s['data'] if start<=datetime.fromisoformat(t)<end];maps[code]=dict(rows);valid=[v for t,v in rows if isinstance(v,(int,float)) and math.isfinite(v)]
  c=dict(day=day,code=code,facility=units[code][0],fueltech=units[code][1],dispatch_type=units[code][2],points=len(rows),missing=len(expected-set(t for t,v in rows)),invalid=len(rows)-len(valid),duplicates=len(rows)-len(maps[code]),minimum=min(valid) if valid else None,maximum=max(valid) if valid else None,zeros=sum(v==0 for v in valid));checks.append(c);print(c)
 for base,g,l in [('WALGRV1','WALGRVG1','WALGRVL1'),('WTAHB1','WTAHB1G1','WTAHB1L1')]:
  if all(c in maps for c in [base,g,l]):
   shared=set(maps[base])&set(maps[g])&set(maps[l]);errs=[abs(maps[base][t]-(maps[g][t]-maps[l][t])) for t in shared if all(isinstance(maps[c][t],(int,float)) for c in [base,g,l])];overlap.append(dict(day=day,base=base,common_points=len(errs),max_net_difference=max(errs) if errs else None))
 for metric in ['renewable_proportion','curtailment_solar_utility','curtailment_wind']:
  o=json.loads((p/f'{day}-{metric}-response.json').read_text());s=o['data'][0];rows=[(datetime.fromisoformat(t),v) for t,v in s['results'][0]['data'] if start<=datetime.fromisoformat(t)<end];valid=[v for t,v in rows if isinstance(v,(int,float)) and math.isfinite(v)];c=dict(day=day,metric=metric,unit=s['unit'],points=len(rows),missing=len(expected-set(t for t,v in rows)),invalid=len(rows)-len(valid),minimum=min(valid) if valid else None,maximum=max(valid) if valid else None);checks.append(c);print(c)
(p/'checks.json').write_text(json.dumps(dict(series=checks,battery_overlap=overlap),indent=2)+'\n');print('BATTERY',overlap)
