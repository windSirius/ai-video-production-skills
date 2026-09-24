#!/usr/bin/env python3
"""Deterministic Foxjiu B/C overlay cards. Requires Pillow; never rewrites input."""
from pathlib import Path
import argparse, hashlib, json, re, struct
from PIL import Image, ImageDraw, ImageFont, ImageOps

DEFAULT_STYLE = Path(__file__).resolve().parents[1]/'assets/foxjiu-evidence-card-v1.json'

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def ref(p):
    return {'path': str(Path(p).resolve()), 'sha256': digest(p)}

def font_codepoints(path):
    """Read Unicode cmap format 12/4 without a second font dependency."""
    b=Path(path).read_bytes(); n=struct.unpack_from('>H',b,4)[0]
    offsets={b[12+i*16:16+i*16]:struct.unpack_from('>I',b,20+i*16)[0] for i in range(n)}
    off=offsets[b'cmap']; count=struct.unpack_from('>H',b,off+2)[0]; points=set()
    for i in range(count):
        platform,encoding,relative=struct.unpack_from('>HHI',b,off+4+8*i)
        if platform not in (0,3): continue
        sub=off+relative; fmt=struct.unpack_from('>H',b,sub)[0]
        if fmt==12:
            groups=struct.unpack_from('>I',b,sub+12)[0]
            for k in range(groups):
                a,z,glyph=struct.unpack_from('>III',b,sub+16+k*12)
                points.update(range(a+(glyph==0),z+1))
        elif fmt==4:
            count=struct.unpack_from('>H',b,sub+6)[0]//2
            ends=sub+14; starts=ends+count*2+2; deltas=starts+count*2; ranges=deltas+count*2
            for k in range(count):
                z=struct.unpack_from('>H',b,ends+2*k)[0]; a=struct.unpack_from('>H',b,starts+2*k)[0]
                delta=struct.unpack_from('>h',b,deltas+2*k)[0]; offset=struct.unpack_from('>H',b,ranges+2*k)[0]
                for cp in range(a,min(z,65534)+1):
                    glyph=(cp+delta)&65535 if not offset else struct.unpack_from('>H',b,ranges+2*k+offset+2*(cp-a))[0]
                    if glyph: points.add(cp)
    return points

def wrap(text,font,width):
    protected=['尼伯龙根','狐斋宫','回忆与知识','世界树','新地脉','不死诅咒','月矩力','五罪人']
    rx='|'.join(map(re.escape,protected))+r'|[A-Za-z0-9]+|.'
    lines=[]
    for paragraph in text.split('\n'):
        line=''
        for token in re.findall(rx,paragraph):
            if line and font.getlength(line+token)>width:
                if token in '，。！？、；：」』）》':
                    if line: token=line[-1]+token; line=line[:-1]
                lines.append(line); line=token
            else: line+=token
        lines.append(line)
    return lines

def render(card,style,font_path):
    c=dict(card); old=Image.open(c['alpha']['path']) if c.get('alpha') else None
    box=c.get('geometry')
    if box is None and old is not None:
        x,y,right,bottom=old.getbbox()
        box=dict(x=x,y=y,width=right-x-1,height=bottom-y-1)
    if box is None:
        preset=c.get('layout','C_relation' if c['track']=='C' else 'B_native')
        box=style['geometry'][preset]
    c['geometry']=box
    x,y,w,h=[box[k] for k in ['x','y','width','height']]
    if x<0 or y<0 or x+w>=style['canvas'][0] or y+h>=style['canvas'][1]:
        raise ValueError(f'{c["id"]}: card outside canvas')
    palette=style['palette']; tp=style['typography']; font=lambda n: ImageFont.truetype(str(font_path),n)
    rgba=tuple(int(palette['panel'][i:i+2],16) for i in (1,3,5))+(palette['panel_alpha'],)
    im=Image.new('RGBA',tuple(style['canvas']),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rounded_rectangle((x,y,x+w,y+h),radius=10,fill=rgba,outline=palette['line'],width=2)
    # Inset registry rules: visual structure, never an invented official stamp.
    for xx,yy,dx,dy in [(x+15,y+15,1,1),(x+w-15,y+15,-1,1),(x+15,y+h-15,1,-1),(x+w-15,y+h-15,-1,-1)]:
        d.line([(xx,yy+dy*18),(xx,yy),(xx+dx*36,yy)],fill=palette['line'],width=2)
    placements=[]
    def txt(t,xy,size,color,maxwidth):
        f=font(size);parts=re.split(r'([→＋])',t)
        width=sum(size*1.2 if part in ('→','＋') else f.getlength(part) for part in parts)
        bbox=(xy[0],xy[1],xy[0]+width,xy[1]+size)
        if width>maxwidth+1:raise ValueError(f'{c["id"]}: horizontal text overflow: {t}')
        if not(x+24<=bbox[0] and bbox[2]<=x+w-24 and y+15<=bbox[1] and bbox[3]<=y+h-18):
            raise ValueError(f'{c["id"]}: text outside safe card region {bbox}')
        px,py=xy
        for part in parts:
            if part in ('→','＋'):
                mid=py+size*.46;left=px+size*.18;right=px+size*1.02;pen=max(3,round(size*.075))
                d.line((left,mid,right,mid),fill=color,width=pen)
                if part=='→':d.line([(right-size*.25,mid-size*.22),(right,mid),(right-size*.25,mid+size*.22)],fill=color,width=pen)
                else:d.line((px+size*.6,mid-size*.3,px+size*.6,mid+size*.3),fill=color,width=pen)
                px+=size*1.2
            else:d.text((px,py),part,font=f,fill=color,anchor='lt');px+=f.getlength(part)
        placements.append(dict(text=t,size=size,bbox=list(bbox),vector_symbols=[x for x in parts if x in ('→','＋')]))
    if c['track']=='C':
        d.rectangle((x+26,y+31,x+32,y+h-31),fill=palette['accent'])
        txt(c['title']+' · 本期推测',(x+52,y+27),tp['C_title_px'],palette['title'],w-108)
        txt(c['body'],(x+52,y+100),tp['C_body_px'],palette['text'],w-108)
    else:
        d.rectangle((x+29,y+35,x+35,y+88),fill=palette['accent'])
        txt(c['title'],(x+53,y+36),tp['B_title_px'],palette['title'],w-105)
        d.line((x+48,y+106,x+w-48,y+106),fill=palette['line'],width=2)
        portrait=h>=600 and c.get('original')
        original=c.get('original')
        if portrait:
            image_box=(x+48,y+142,780,439);tx=x+882;tw=w-930;ty=y+165;fs=66;footer_y=y+h-107
        else:
            image_box=(x+w-568,y+142,520,292) if original else None
            tx=x+48;tw=w-664 if original else w-96;ty=y+143;fs=tp['B_body_px'];footer_y=y+h-65
        if original:
            p=Path(original['path'])
            if digest(p)!=original['sha256']:raise ValueError('Source screenshot changed: '+str(p))
            ix,iy,iw,ih=image_box;pic=ImageOps.contain(Image.open(p).convert('RGBA'),(iw,ih),Image.Resampling.LANCZOS)
            im.alpha_composite(pic,(ix+(iw-pic.width)//2,iy+(ih-pic.height)//2))
            d.rectangle((ix-2,iy-2,ix+iw+1,iy+ih+1),outline=palette['line'],width=2)
        lines=wrap(c['body'],font(fs),tw)
        while (ty+len(lines)*int(fs*1.30)>footer_y-26 or len(lines)>3) and fs>tp['B_body_min_px']:
            fs-=2;lines=wrap(c['body'],font(fs),tw)
        if ty+len(lines)*int(fs*1.30)>footer_y-26:raise ValueError(c['id']+': body needs editorial shortening or more active pages')
        for j,line in enumerate(lines):txt(line,(tx,ty+j*int(fs*1.30)),fs,palette['text'],tw)
        d.line((tx,footer_y-22,tx+min(tw,900),footer_y-22),fill=palette['line'],width=2)
        footer=wrap(c['source_label'],font(tp['B_source_px']),tw)
        if len(footer)> (2 if portrait else 1):raise ValueError(c['id']+': source footer too long')
        for j,line in enumerate(footer):txt(line,(tx,footer_y+j*44),tp['B_source_px'],palette['source'],tw)
    c.update(language='zh-Hans',font_family=style['font']['family'],font_style=style['font']['style'],font=ref(font_path),
        style_id=style['style_id'],style=ref(DEFAULT_STYLE),review_status='awaiting_actual_overlay_review',
        typography_qa=dict(status='PASS',placements=placements,text_overflow_count=0,missing_glyph_count=0),
        geometry_preserved=True,output_mode='green_screen_master')
    if old is not None and im.getbbox()!=old.getbbox():raise ValueError(c['id']+': approved outer bounds changed')
    return im,c

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cards',required=True,type=Path);ap.add_argument('--output-dir',required=True,type=Path)
    ap.add_argument('--font',type=Path,default=Path.home()/'Library/Fonts/WenYue_XinQingNianTi_J-W8.otf');ap.add_argument('--style',type=Path,default=DEFAULT_STYLE)
    a=ap.parse_args();style=json.loads(a.style.read_text());cards=json.loads(a.cards.read_text())
    if digest(a.font)!=style['font']['sha256']:raise SystemExit('Font identity differs from the selected Xinqingnian face; inspect and explicitly update the font contract, never silently substitute.')
    texts=''.join(c['title']+c['body']+c['source_label']+' · 本期推测' for c in cards)
    available=font_codepoints(a.font)
    missing={ch for ch in texts if not ch.isspace() and ch not in '→＋' and ord(ch) not in available}
    if missing:raise SystemExit('Missing glyphs in selected font: '+''.join(sorted(missing)))
    a.output_dir.mkdir(parents=True,exist_ok=True);folder=a.output_dir/'assets';folder.mkdir(exist_ok=True);out=[]
    for c in cards:
        im,row=render(c,style,a.font)
        alpha=folder/(c['id']+'_alpha.png');green=folder/(c['id']+'_green.png');im.save(alpha)
        gi=Image.new('RGBA',im.size,'#00ff00');gi.alpha_composite(im);gi.convert('RGB').save(green)
        row.update(alpha=ref(alpha),green=ref(green),style=ref(a.style),alpha_url=f'/asset/{c["track"]}/{alpha.name}',green_url=f'/asset/{c["track"]}/{green.name}')
        out.append(row)
    (a.output_dir/'cards.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',count=len(out),font=ref(a.font),style=ref(a.style),input=ref(a.cards)),ensure_ascii=False))

if __name__=='__main__':main()
