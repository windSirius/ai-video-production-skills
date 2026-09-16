#!/usr/bin/env python3
"""Register durable originals by actual SHA; never move, copy or delete media."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
from pathlib import Path


def register(library,path,source_id,game,title='',origin=''):
    library=Path(library).expanduser().resolve();path=Path(path).expanduser().resolve()
    if not path.is_file():raise ValueError('source file is missing')
    if not source_id.strip() or not game.strip():raise ValueError('source ID and game are required')
    before=path.stat()
    with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('source changed during hashing')
    library.mkdir(parents=True,exist_ok=True)
    with (library/'.registry.lock').open('a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        index=library/'registry.json'
        data=json.loads(index.read_text()) if index.exists() else {'schema':'durable_media_registry_v1','assets':{}}
        for existing in data['assets'].values():
            if {'game':game,'source_id':source_id} in existing['aliases'] and existing['sha256']!=sha:
                raise ValueError('source ID already describes different bytes; use a new explicit source version')
        reused=sha in data['assets']
        entry=data['assets'].setdefault(sha,{'asset_id':'SHA256_'+sha[:20],'sha256':sha,'bytes':after.st_size,
               'primary_path':str(path),'locations':[],'aliases':[],'title':title,'origins':[],
               'created_at':datetime.now(timezone.utc).isoformat(),'rights_status':'not_assessed'})
        alias={'game':game,'source_id':source_id}
        if alias not in entry['aliases']:entry['aliases'].append(alias)
        if str(path) not in entry['locations']:entry['locations'].append(str(path))
        if origin and origin not in entry['origins']:entry['origins'].append(origin)
        entry['last_verified_path']=str(path);entry['last_verified_at']=datetime.now(timezone.utc).isoformat()
        temp=index.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(index)
        return {'asset':entry,'reused_existing_identity':reused,'media_copied':False,'rights_approval_created':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--path',type=Path,required=True)
    p.add_argument('--source-id',required=True);p.add_argument('--game',required=True);p.add_argument('--title',default='');p.add_argument('--origin',default='')
    a=p.parse_args()
    try:print(json.dumps(register(a.library,a.path,a.source_id,a.game,a.title,a.origin),ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError) as exc:print(json.dumps({'error':str(exc)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
