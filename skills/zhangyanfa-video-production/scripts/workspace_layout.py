#!/usr/bin/env python3
"""Deterministic production paths and non-destructive legacy workbenches.

Navigation is derived from existing records; never infer approval from filenames.
This module never moves/deletes source media or changes a legacy authority ledger.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone

TEMPLATE = Path(__file__).resolve().parents[1]/'assets/workspace_layout.v1.json'
DEFAULT_MEDIA = Path.home()/'Documents/视频素材/00_原始素材库'
DEFAULT_CACHE = Path.home()/'Documents/视频制作缓存'
MARKER = '<!-- generated: foxjiu-workspace-v1; navigation only -->'
ROLE_LABELS = {
    'script':'稿件','narration':'总控登记旁白','subtitle':'总控登记字幕','timing_contract':'帧时钟',
    'a_master':'A轨母版','b_master':'B轨母版','c_master':'C轨母版','bgm_master':'BGM母带',
    'integrated_proxy_720':'全长审核代理','final_video':'整合成片','split_delivery':'独立交付清单',
    'cover_16_9':'16:9封面','cover_4_3':'4:3封面','cover_3_4':'3:4封面'}


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); temp.replace(path)


def generated_text(path,text):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and not path.read_text(encoding='utf-8').startswith(MARKER):
        raise ValueError(f'refusing to replace user-authored navigation: {path}')
    path.write_text(MARKER+'\n\n'+text,encoding='utf-8')


def is_cloud(path): return 'Mobile Documents' in Path(path).parts or 'CloudStorage' in Path(path).parts


def valid_key(key):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{2,79}',key or ''):
        raise ValueError('episode_key must be 3-80 ASCII letters, digits, underscores or hyphens')
    return key


def create(root,episode_key=None,media_root=None,cache_root=None,mode='canonical',legacy_map=None):
    root=Path(root).expanduser().resolve()
    key=valid_key(episode_key or 'EP_'+hashlib.sha256(str(root).encode()).hexdigest()[:12])
    path=root/'workspace_paths.json'
    if path.exists():
        prior=load(path)
        if prior.get('episode_key')!=key or prior.get('mode')!=mode:
            raise ValueError('workspace already has another identity/mode; explicit migration is required')
        if media_root and str(Path(media_root).expanduser().resolve())!=prior['media_root']:
            raise ValueError('changing the media root requires an explicit path migration')
        if cache_root and str(Path(cache_root).expanduser().resolve())!=prior['cache_base']:
            raise ValueError('changing the cache root requires an explicit path migration')
        return prior
    media=Path(media_root or DEFAULT_MEDIA).expanduser().resolve()
    cache_base=Path(cache_root or DEFAULT_CACHE).expanduser().resolve()
    cache=cache_base/key
    if is_cloud(cache_base): raise ValueError('cache root must be local, outside iCloud/File Provider')
    if cache_base.is_relative_to(root) or root.is_relative_to(cache_base): raise ValueError('project and cache roots must be separate')
    if media.is_relative_to(cache_base) or cache_base.is_relative_to(media): raise ValueError('durable media and disposable cache must be separate')
    template=load(TEMPLATE)
    if mode not in {'canonical','legacy_indexed'}: raise ValueError('unknown layout mode')
    mapping=legacy_map or {}
    if mode=='legacy_indexed':
        for kind,targets in mapping.items():
            if kind not in template['project_dirs'] or not isinstance(targets,list): raise ValueError('invalid legacy category')
            for target in targets:
                if not (root/target).exists(): raise ValueError(f'legacy target missing: {target}')
    root.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    owner=cache/'owner.json'
    identity={'schema':'episode_cache_owner_v1','episode_key':key,'project_root':str(root)}
    try:
        with owner.open('x',encoding='utf-8') as stream: json.dump(identity,stream,ensure_ascii=False,indent=2)
    except FileExistsError:
        if load(owner)!=identity: raise ValueError('episode cache key is already owned by another project')
    media.mkdir(parents=True,exist_ok=True)
    for name in template['cache_dirs']:(cache/name).mkdir(exist_ok=True)
    if mode=='canonical':
        for directory in template['project_dirs'].values():(root/directory).mkdir(exist_ok=True)
    else:
        for kind,label in template['project_dirs'].items():
            view=root/'00_工作台'/label;view.mkdir(parents=True,exist_ok=True)
            for target in mapping.get(kind,[]):
                original=(root/target).absolute();alias=view/original.name
                if alias.exists() or alias.is_symlink():
                    if not alias.is_symlink() or alias.resolve()!=original.resolve(): raise ValueError(f'workbench link conflict: {alias}')
                else:alias.symlink_to(os.path.relpath(original,view),target_is_directory=original.is_dir())
            notes=['# '+label,'这是旧期原位置的统一导航，链接不另存一份文件。']
            notes.extend('- '+link_text for link_text in [link(str(t),(root/t).absolute()) for t in mapping.get(kind,[])])
            if not mapping.get(kind):notes.append('本次没有单独映射此类旧目录；请从总入口的登记文件或原项目目录查找，不据此推定文件不存在。')
            generated_text(view/'00_说明.md','\n\n'.join(notes)+'\n')
    value={**template,'schema':'episode_workspace_paths_v1','mode':mode,'episode_key':key,'project_root':str(root),
           'media_root':str(media),'cache_root':str(cache),'cache_base':str(cache_base),
           'template_sha256':digest(TEMPLATE),'created_at':datetime.now(timezone.utc).isoformat(),
           'legacy_map':mapping,'navigation_is_authority':False}
    catalog=root.parent.parent/'00_制作管理'/'项目索引.json'
    if catalog.is_file():value['navigation_catalog']=str(catalog)
    write_json(path,value)
    refresh(root)
    return value


def resolve(root,kind,version=None):
    root=Path(root).resolve();config=load(root/'workspace_paths.json')
    if kind=='media':base=Path(config['media_root'])
    elif kind.startswith('cache:'):
        sub=kind.partition(':')[2]
        if sub not in config['cache_dirs']:raise ValueError('unknown cache category')
        base=Path(config['cache_root'])/sub
    else:
        if kind not in config['project_dirs']:raise ValueError('unknown project category')
        if config['mode']!='canonical':raise ValueError('legacy workbench is read-navigation; do not write new production through its links')
        base=root/config['project_dirs'][kind]
    if version:
        if not re.fullmatch(config['version_pattern'],version):raise ValueError('versions must be v001, v002, ...')
        base/=version
    return base


def new_version(root,kind):
    base=resolve(root,kind);base.mkdir(parents=True,exist_ok=True)
    highest=max((int(p.name[1:]) for p in base.iterdir() if re.fullmatch(r'v[0-9]{3,}',p.name)),default=0)
    while True:
        highest+=1;path=base/f'v{highest:03d}'
        try:path.mkdir();return path
        except FileExistsError:continue


def registration_errors(root,role,path):
    root=Path(root).resolve()
    if not(root/'workspace_paths.json').is_file():return []
    config=load(root/'workspace_paths.json')
    if config.get('mode')!='canonical':return []
    kind=config['role_dirs'].get(role)
    if not kind:return [f'no workspace category for role {role}']
    base=(root/config['project_dirs'][kind]).resolve();actual=(root/path).resolve()
    if not actual.is_relative_to(base):return [f'{role} must live under {base}/vNNN/']
    parts=actual.relative_to(base).parts
    if len(parts)<2 or not re.fullmatch(config['version_pattern'],parts[0]):return [f'{role} requires a version directory such as v001']
    return []


def link(label,path):return f'[{label.replace("[","(").replace("]",")")}]({"<"+str(path)+">"})'


def bundle_references(value,prefix=''):
    """Read references from an existing bundle, without interpreting QA as approval."""
    rows=[]
    if isinstance(value,dict):
        if isinstance(value.get('path'),str) and (value.get('sha256') or value.get('bytes')):
            rows.append((prefix,value['path']))
        else:
            for key,child in value.items():
                if key in {'probe','streams','format','render_receipt','qa','authority_bindings'}:continue
                rows.extend(bundle_references(child,(prefix+'/'+key).strip('/')))
    elif isinstance(value,list):
        for i,child in enumerate(value):rows.extend(bundle_references(child,f'{prefix}/{i}'))
    return rows


def sync_catalog(root,config,title,delivery_index):
    """Update a configured navigation catalog; never discover/adopt projects implicitly."""
    if not config.get('navigation_catalog'):return
    catalog=Path(config['navigation_catalog']);management=catalog.parent
    with (management/'.catalog.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        value=load(catalog)
        if value.get('schema')!='video_project_navigation_v1':raise ValueError('unknown project catalog schema')
        rows=value['projects'];key=config['episode_key']
        prior=next((row for row in rows if row['episode_key']==key),None)
        if prior and Path(prior['original_root']).resolve()!=root:raise ValueError('catalog episode key belongs to another project')
        workbench=Path(prior['workbench']) if prior else management/'项目入口'/root.parent.name/root.name
        workbench.parent.mkdir(parents=True,exist_ok=True)
        target=root/'00_工作台' if config['mode']=='legacy_indexed' else root
        if workbench.exists() or workbench.is_symlink():
            if not workbench.is_symlink() or workbench.resolve()!=target:raise ValueError('catalog entry link conflict')
        else:workbench.symlink_to(os.path.relpath(target,workbench.parent),target_is_directory=True)
        row={'episode_key':key,'title':title,'series':root.parent.name,'original_root':str(root),
             'entry':str(root/config['entry_file']),'workbench':str(workbench),
             'delivery_index':str(delivery_index),'mode':config['mode']}
        rows=[r for r in rows if r['episode_key']!=key]+[row]
        rows.sort(key=lambda r:(r['series'],r['episode_key']))
        value['projects']=rows;write_json(catalog,value)
        lines=['# 视频制作总入口','每一期都从“开始这里”进入；工作台按同一套阶段排列。当前文件以实际登记和交付清单为准。',
               '| 系列 / 期数 | 题目 | 开始这里 | 文件索引 |','| --- | --- | --- | --- |']
        for item in rows:lines.append(f'| {item["episode_key"]} | {item["title"].replace("|","／")} | {link("打开",item["entry"])} | {link("拿文件",item["delivery_index"])} |')
        lines+=['',link('统一目录规范',management/'统一目录规范.md'),'',
                link('共用原片与旧素材位置',Path(config['media_root'])/'00_素材入口.md'),'',
                link('本地缓存索引',Path(config['cache_base'])/'00_缓存索引.md'),'',
                link('每期标准目录模板',management/'模板_每期标准目录')]
        generated_text(management/'00_开始这里.md','\n\n'.join(lines[:2])+'\n\n'+'\n'.join(lines[2:])+'\n')


def refresh(root):
    root=Path(root).resolve();config=load(root/'workspace_paths.json')
    current=load(root/'CURRENT.json') if (root/'CURRENT.json').is_file() else {}
    ledger=load(root/'deliverables.json') if (root/'deliverables.json').is_file() else {}
    items=ledger.get('items',{})
    title=current.get('title') or root.name
    body=[f'# {title}',f'项目编号：`{config["episode_key"]}`。这个页面是自动文件导航，审批与当前版本以总控登记为准。',
          '## 常用入口','','| 工作 | 打开位置 |','| --- | --- |']
    viewroot=root if config['mode']=='canonical' else root/'00_工作台'
    for kind,label in config['project_dirs'].items():body.append(f'| {label} | {link("打开",viewroot/label)} |')
    body+=['','## 素材与缓存','',f'- {link("共用原始素材库",config["media_root"])}：永久素材，不是可删除缓存。',
           f'- {link("本期本地缓存",config["cache_root"])}：中间处理目录；清理仍需核验与明确授权。',
           '- 本期引用素材的来源、实际路径与 SHA 记在素材清单；不要为每期复制同一部官方视频。']
    delivery=['# 文件索引','本页只引用已有文件，不复制母版，不授予新的审批。',
              '## 总控登记文件','','| 文件角色 | 位置 | 记录情况 |','| --- | --- | --- |']
    missing=[]
    for role,label in ROLE_LABELS.items():
        item=items.get(role)
        if not isinstance(item,dict) or not item.get('path'):continue
        path=root/item['path'];exists=path.exists()
        if not exists:missing.append(str(path))
        status='有审批ID；有效性看总控' if item.get('approval_id') else '已登记；本导航不重判批准'
        if not exists:status='路径当前不可用'
        delivery.append(f'| {label} | {link(path.name,path)} | {status} |')
    bundle=items.get('split_delivery')
    if isinstance(bundle,dict) and (root/bundle['path']).is_file():
        bundle_path=root/bundle['path']
        bundle_lines=['## 独立交付清单中列出的实际文件','','删段后的配音和字幕先从这里核对；下方总控登记保留原记录。','']
        for label,path in bundle_references(load(bundle_path)):
            target=Path(path) if Path(path).is_absolute() else root/path
            bundle_lines.append(f'- {label}：{link(target.name,target)}')
            if not target.exists():missing.append(str(target))
        delivery=delivery[:2]+bundle_lines+['']+delivery[2:]
    if config['mode']=='legacy_indexed':
        old_refs=[]
        if not items:
            for key in ('artifacts','authorities','selected_bgm','formal_masters','delivery_manifest'):
                value=current.get(key,{})
                old_refs.extend(bundle_references(value,'CURRENT/'+key))
                if isinstance(value,dict) and 'path' not in value:
                    old_refs.extend(('CURRENT/'+key+'/'+k,v) for k,v in value.items() if isinstance(v,str) and '/' in v)
        if old_refs:
            delivery+=['','## 旧结构 CURRENT 指向的文件','','保留旧记录的原意；这里不把技术通过、候选或历史状态改写为新的审批。','']
            for label,path in old_refs:
                target=root/path
                delivery.append(f'- {label}：{link(target.name,target)}'+('（路径当前不可用）' if not target.exists() else ''))
                if not target.exists():missing.append(str(target))
        delivery+=['','## 旧目录中的交付与工作文件','','以下是人工核对分类的原位置入口；目录中的多个版本仍需按原登记和交付记录区分。','']
        for kind in ('delivery','masters','covers','voice','subtitle'):
            for target in config.get('legacy_map',{}).get(kind,[]):
                delivery.append(f'- {config["project_dirs"][kind]}：{link(Path(target).name,root/target)}')
    out=viewroot/config['project_dirs']['delivery']/'00_文件索引.md'
    generated_text(out,'\n\n'.join(delivery[:2])+'\n\n'+'\n'.join(delivery[2:])+'\n')
    body+=['','## 拿文件','',link('打开成品、配音、BGM、字幕与封面索引',out)]
    if config['mode']=='legacy_indexed':
        body+=['','旧期使用统一工作台直达原位置，已登记文件保持原路径。链接依赖本机/iCloud已有目录；跨电脑应依据路径清单重新定位，不能把符号链接当成独立备份。']
    generated_text(root/config['entry_file'],'\n\n'.join(body[:2])+'\n\n'+'\n'.join(body[2:])+'\n')
    sync_catalog(root,config,title,out)
    return {'entry':str(root/config['entry_file']),'delivery_index':str(out),'missing_references':sorted(set(missing))}


def doctor(root):
    root=Path(root).resolve();config=load(root/'workspace_paths.json');errors=[];warnings=[]
    if config.get('project_root')!=str(root):errors.append('project moved without updating its workspace contract')
    owner=Path(config['cache_root'])/'owner.json'
    if not owner.is_file() or load(owner).get('project_root')!=str(root):errors.append('cache ownership mismatch')
    if is_cloud(config['cache_root']):errors.append('cache is under iCloud/File Provider')
    viewroot=root if config['mode']=='canonical' else root/'00_工作台'
    for label in config['project_dirs'].values():
        if not(viewroot/label).is_dir():errors.append('missing category: '+label)
    if config['mode']=='legacy_indexed':
        for p in (root/'00_工作台').rglob('*'):
            if p.is_symlink() and not p.exists():errors.append('broken workbench link: '+str(p))
    else:
        allowed=set(config['project_dirs'].values())|set(config['root_control_files'])|set(config['root_control_dirs'])|{config['entry_file']}
        for p in root.iterdir():
            if not p.name.startswith('.') and p.name not in allowed:warnings.append('unclassified root item: '+p.name)
        if (root/'deliverables.json').is_file():
            for role,item in load(root/'deliverables.json').get('items',{}).items():errors.extend(registration_errors(root,role,item['path']))
    return {'status':'PASS' if not errors else 'FAIL','mode':config['mode'],'episode_key':config['episode_key'],
            'errors':errors,'warnings':warnings,'media_hash_audit_performed':False,'approval_audit_performed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','adopt','resolve','new-version','refresh','doctor'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--episode-key');p.add_argument('--media-root',type=Path);p.add_argument('--cache-root',type=Path)
    p.add_argument('--mapping',type=Path);p.add_argument('--kind');p.add_argument('--version')
    a=p.parse_args()
    try:
        if a.command in {'init','adopt'}:
            if a.command=='adopt' and not a.mapping:raise ValueError('adopt requires a reviewed mapping JSON')
            result=create(a.root,a.episode_key,a.media_root,a.cache_root,'legacy_indexed' if a.command=='adopt' else 'canonical',load(a.mapping) if a.mapping else None)
        elif a.command=='resolve':result={'path':str(resolve(a.root,a.kind,a.version))}
        elif a.command=='new-version':result={'path':str(new_version(a.root,a.kind))}
        elif a.command=='refresh':result=refresh(a.root)
        else:result=doctor(a.root)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 1 if result.get('status')=='FAIL' else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
