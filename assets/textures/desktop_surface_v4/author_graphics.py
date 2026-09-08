"""Original neutral UI/keyboard graphics; does not read reference screenshots.

Run with Python + Pillow + NumPy. A local font rasterizer is used but no font
file is redistributed. All UI words/layout and material noise are authored.
"""
from pathlib import Path
import hashlib, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

P=Path(__file__).resolve().parent
FONT=next((p for p in [Path('C:/Windows/Fonts/consola.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')]if p.is_file()),None)
HAND=Path('C:/Windows/Fonts/segoepr.ttf')
def font(size,hand=False):
    path=HAND if hand and HAND.is_file() else FONT
    return ImageFont.truetype(str(path),size)if path else ImageFont.load_default(size=size)

def key_rows():
    rows=[]
    def main(labels,widths=None):return [{'label':s,'width':w}for s,w in zip(labels,widths or [1]*len(labels))]
    rows.append(main(['Esc']+['F'+str(i)for i in range(1,13)]+['Ins','Del']))
    rows.append(main(['~','1','2','3','4','5','6','7','8','9','0','-','=','Backspace'],[1]*13+[2]))
    rows.append(main(['Tab','Q','W','E','R','T','Y','U','I','O','P','[',']','\\'],[1.5]+[1]*12+[1.5]))
    rows.append(main(['Caps','A','S','D','F','G','H','J','K','L',';',"'",'Enter'],[1.75]+[1]*11+[2.25]))
    rows.append(main(['Shift','Z','X','C','V','B','N','M',',','.','/','Shift'],[2.25]+[1]*10+[2.75]))
    rows.append(main(['Ctrl','Fn','Win','Alt','Space','Alt','Ctrl','Left','Up/Down','Right'],[1.25,1,1.25,1.25,5.25,1,1,1,1,1]))
    assert all(abs(sum(k['width']for k in row)-15)<1e-6 for row in rows)
    return rows

keys=[];row_x=[.092,.064,.036,.008,-.020,-.048];unit=.347/19.4
for row,definitions in enumerate(key_rows()):
    cursor=0
    for definition in definitions:
        width=definition['width'];label=definition['label']
        if label=='Up/Down':
            for name,offset in [('Up',.0054),('Down',-.0054)]:
                keys.append({'label':name,'x':row_x[row]+offset,'u':cursor+width/2,'width_units':width,'depth':.009})
        else:keys.append({'label':label,'x':row_x[row],'u':cursor+width/2,'width_units':width,'depth':.010 if row==0 else .021})
        cursor+=width
num_rows=[['PrtSc','Home','End','PgDn'],['Num','/','*','-'],['7','8','9'],['4','5','6'],['1','2','3']]
for row,labels in enumerate(num_rows):
    for col,label in enumerate(labels):keys.append({'label':label,'x':row_x[row],'u':15.4+col+.5,'width_units':1,'depth':.010 if row==0 else .021,'numeric':True})
keys += [{'label':'+','x':.022,'u':18.9,'width_units':1,'depth':.049,'numeric':True},{'label':'Enter','x':-.034,'u':18.9,'width_units':1,'depth':.049,'numeric':True},{'label':'0','x':-.048,'u':16.4,'width_units':2,'depth':.021,'numeric':True},{'label':'.','x':-.048,'u':17.9,'width_units':1,'depth':.021,'numeric':True}]
CELL=256
atlas=Image.new('RGB',(CELL*16,CELL*8),(52,55,60));d=ImageDraw.Draw(atlas)
def laser_legend(label,key,color,physical_height):
    # Preserve the same real legend size on wide/tall keys instead of stretching
    # a fixed square glyph image across the whole Backspace/Enter key.
    f=font(64);box=f.getbbox(label);glyph=Image.new('RGBA',(box[2]-box[0]+4,box[3]-box[1]+4),(0,0,0,0));gd=ImageDraw.Draw(glyph);gd.text((2-box[0],2-box[1]),label,font=f,fill=(*color,255))
    h=max(5,round(CELL*physical_height/key['depth']));w=max(3,round(CELL*physical_height*(glyph.width/glyph.height)/key['width']));return glyph.resize((w,h),Image.Resampling.LANCZOS)
for index,key in enumerate(keys):
    col,row=index%16,index//16;x,y=col*CELL,row*CELL;key.update(atlas_cell=[col,row],center_y=.347/2-key['u']*unit,width=key['width_units']*unit-.0015)
    label=key['label']
    # Small subdued laser legends, never bright rectangular placeholders.
    if label!='Space':
        glyph=laser_legend(label,key,(193,198,205),.0014 if key['depth']<.012 else(.0020 if len(label)==1 else .0014));atlas.paste(glyph,(x+round(CELL*.15),y+round(CELL*.16)),glyph)
    if label in ['1','2','3','4','5','6','7','8','9','0']and not key.get('numeric'):
        shift={'1':'!','2':'@','3':'#','4':'$','5':'%','6':'^','7':'&','8':'*','9':'(','0':')'}[label];glyph=laser_legend(shift,key,(157,165,177),.0012);atlas.paste(glyph,(x+round(CELL*.67),y+round(CELL*.16)),glyph)
    if label in ['F','J']:d.rounded_rectangle((x+100,y+197,x+156,y+201),radius=2,fill=(83,87,94))
atlas.save(P/'keycap-legends.png')
(P/'keyboard-layout.json').write_text(json.dumps({'unit_m':unit,'rows':6,'keys':keys,'layout':'Authored full-size compact laptop layout with numeric cluster; not an exact product identification.'},indent=2))

im=Image.new('RGB',(1920,1200),(15,18,23));d=ImageDraw.Draw(im)
d.rectangle((0,0,1919,52),fill=(24,28,35));d.text((26,15),'WORKSPACE     FILE  EDIT  VIEW',font=font(19),fill=(144,155,171));d.text((1500,15),'Local notes  /  offline',font=font(16),fill=(111,121,136))
d.rectangle((0,53,260,1159),fill=(20,24,31));d.line((260,53,260,1159),fill=(42,48,59),width=1);d.text((27,82),'EXPLORER',font=font(16),fill=(147,158,174))
for i,name in enumerate(['study','  scene.py','  materials.py','  camera.json','  notes.md','  assets/','  references/']):d.text((28,126+i*31),name,font=font(18),fill=(122,136,155) if i!=4 else(172,184,198))
d.rectangle((270,55,500,100),fill=(30,35,44));d.text((291,68),'notes.md',font=font(21),fill=(174,183,194));d.text((315,144),'Room study',font=font(33),fill=(167,182,199));d.text((315,201),'A small space, recorded in light and proportion.',font=font(22),fill=(143,156,176))
paragraphs=[('01  Space',['Keep the original arrangement of the furniture.','Read silhouettes before adding surface detail.','Window light and overhead light remain separate.']),('02  Materials',['Oak grain follows each manufactured panel.','A worn finish varies gently across the surface.','Fabric catches light differently at every fold.']),('03  Observations',['Compare more than one camera before editing.','Keep uncertain dimensions easy to change.','Use neutral sample content on every display.'])]
y=279
for title,lines in paragraphs:
    d.text((315,y),title,font=font(25),fill=(151,167,191));y+=54
    for line in lines:d.text((334,y),line,font=font(21),fill=(143,151,165));y+=34
    y+=39
d.rectangle((1485,101,1919,1159),fill=(18,21,28));d.line((1485,101,1485,1159),fill=(35,40,50),width=1);d.text((1520,140),'OUTLINE',font=font(17),fill=(118,132,151))
for i,s in enumerate(['Room study','  Space','  Materials','  Observations']):d.text((1519,182+34*i),s,font=font(18),fill=(118,131,148))
d.rectangle((0,1160,1919,1199),fill=(27,35,45));d.text((26,1171),'Plain text    UTF-8                         Saved locally',font=font(17),fill=(134,150,168))
im.save(P/'laptop-neutral-workspace.png')

im=Image.new('RGB',(1470,1000),(86,124,179));d=ImageDraw.Draw(im)
d.rectangle((0,0,1469,68),fill=(99,139,191));d.line((0,68,1470,68),fill=(61,100,150),width=2)
for i in range(17):
    x=40+i*80;d.ellipse((x,23,x+15,38),outline=(48,77,122),width=2)
d.text((1055,25),'Notes  /  01',font=font(17),fill=(51,86,135))
for y in range(145,1000,85):d.line((450,y,1470,y),fill=(45,80,131),width=2)
d.line((450,68,450,1000),fill=(47,85,136),width=2)
d.text((515,114),'Light study',font=font(46,True),fill=(20,44,79));d.text((521,286),'colour & texture',font=font(43,True),fill=(22,47,83))
im.save(P/'tablet-neutral-notes.png')

rng=np.random.default_rng(2718);noise=rng.normal(0,1,(512,512));yy,xx=np.mgrid[:512,:512];rough=.42+.009*noise
for cx,cy,sx,sy,amp in [(140,180,62,47,-.055),(332,346,90,58,-.045),(228,190,84,115,.018)]:rough+=amp*np.exp(-((xx-cx)/sx)**2-((yy-cy)/sy)**2)
Image.fromarray(np.rint(np.clip(rough,0,1)*255).astype('uint8')).filter(ImageFilter.GaussianBlur(.6)).save(P/'anodized-handwear-roughness.png')
rough=.24+.003*noise-.035*np.exp(-((xx-130)/98)**2-((yy-380)/70)**2)
Image.fromarray(np.rint(np.clip(rough,0,1)*255).astype('uint8')).filter(ImageFilter.GaussianBlur(1)).save(P/'display-subtle-roughness.png')
files={f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}for f in P.iterdir()if f.suffix in ['.png','.json']and f.name!='PROVENANCE.json'}
report={'authorship':'Original scripted neutral UI and material graphics; no reference-screen pixels or text copied, no generative model used.','reference_use':'Supplied photos12/2/9 informed relative detail scale and device finish only. Device placement is inherited unchanged from the calibrated native model.','font_rasterizer':{'file_used':FONT.name if FONT else 'Pillow default','sha256':hashlib.sha256(FONT.read_bytes()).hexdigest()if FONT else None,'hand_font':HAND.name if HAND.is_file() else 'same mono fallback','font_file_redistributed':False},'license':'Project-authored graphics and layout; no third-party photo textures in this set. Font files are not bundled.','limitations':'Generic authored content replaces personal display content. Compact keyboard is photograph-informed, not a measured product CAD layout. Noise/handwear is subtle authored variation, not captured wear.','files':files}
(P/'PROVENANCE.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('AUTHORED_DESKTOP_ASSETS',len(keys),len(files))
