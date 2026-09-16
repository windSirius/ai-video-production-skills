#!/usr/bin/env python3
"""Audit the entire selected plan, including explicit aliases and parent ranges.

Input is a JSON list of selected segments. Crops never alter family identity.
Optional source_origins maps source_id to {parent_sha256, offset_s}; optional
aliases maps a visual_family_id to a reviewed canonical family. Perceptual
similarity still requires a separate frame-based review; this tool does not
invent visual identities from hashes or certify that manual review happened.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path

def audit(segments,origins=None,aliases=None,max_groups=4,max_occurrences=2):
 if not segments:raise ValueError('selected plan must not be empty')
 if max_groups<0 or max_occurrences<1:raise ValueError('invalid reuse limits')
 if len({s['segment_id'] for s in segments})!=len(segments):raise ValueError('duplicate segment IDs')
 for s in segments:
  if not s.get('visual_family_id') or s['source_out']<=s['source_in'] or s['end_frame']<=s['start_frame']:raise ValueError('invalid physical shot or interval')
 origins=origins or {};aliases=aliases or {};n=len(segments);parent=list(range(n))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):parent[find(a)]=find(b)
 by_family={};by_origin=defaultdict(list);overlaps=[];adjacent=[]
 def canonical(f):
  seen=set()
  while f in aliases and aliases[f]!=f:
   if f in seen:raise ValueError('cycle in visual family aliases')
   seen.add(f);f=aliases[f]
  return f
 for i,s in enumerate(segments):
  fam=canonical(s['visual_family_id'])
  if fam in by_family:union(i,by_family[fam])
  else:by_family[fam]=i
  origin=origins.get(s['source_id'],{});key=origin.get('parent_sha256') or s.get('source_sha256') or s['source_id'];offset=origin.get('offset_s',0)
  a=s['source_in']+offset;b=s['source_out']+offset
  for j,c,d in by_origin[key]:
   amount=min(b,d)-max(a,c)
   if amount>1/120:
    union(i,j);overlaps.append({'a':segments[j]['segment_id'],'b':s['segment_id'],'seconds':round(amount,6),'parent':key})
  by_origin[key].append((i,a,b))
  if i:
   prev=segments[i-1]
   if prev['end_frame']!=s['start_frame']:adjacent.append({'type':'gap_or_overlap','a':prev['segment_id'],'b':s['segment_id']})
   if canonical(prev['visual_family_id'])==fam:adjacent.append({'type':'same_physical_shot','a':prev['segment_id'],'b':s['segment_id']})
 groups=defaultdict(list)
 for i,s in enumerate(segments):groups[find(i)].append(s)
 repeated=[]
 for batch in groups.values():
  if len(batch)>1:
   repeated.append({'family_ids':sorted({s['visual_family_id'] for s in batch}),'count':len(batch),'occurrences':[{k:s[k] for k in ['segment_id','cue_id','source_id','source_in','source_out','start_frame','end_frame']} for s in batch]})
 repeated.sort(key=lambda x:-x['count'])
 return {'status':'pass' if len(repeated)<=max_groups and not adjacent and all(x['count']<=max_occurrences for x in repeated) else 'fail','scope':'full selected plan; physical family aliases and original source interval intersections','selected_segment_count':n,'unique_physical_groups':len(groups),'repeated_group_count':len(repeated),'extra_occurrences':sum(x['count']-1 for x in repeated),'max_group_occurrences':max((x['count'] for x in repeated),default=1),'max_repeated_groups':max_groups,'max_allowed_occurrences':max_occurrences,'repeated_groups':repeated,'source_overlap_pairs':overlaps,'adjacent_violations':adjacent,'near_visual_review':'separate required receipt; not certified by this program'}

def main():
 p=argparse.ArgumentParser();p.add_argument('segments',type=Path);p.add_argument('--origins',type=Path);p.add_argument('--aliases',type=Path);p.add_argument('--max-groups',type=int,default=4);p.add_argument('--max-occurrences',type=int,default=2);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 result=audit(json.loads(a.segments.read_text()),json.loads(a.origins.read_text()) if a.origins else None,json.loads(a.aliases.read_text()) if a.aliases else None,a.max_groups,a.max_occurrences)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ['status','selected_segment_count','repeated_group_count','extra_occurrences','max_group_occurrences']},ensure_ascii=False));raise SystemExit(0 if result['status']=='pass' else 1)
if __name__=='__main__':main()
