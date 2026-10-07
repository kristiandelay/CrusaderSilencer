"""Fitted source-space landmarks; builds portable UE humanoid and finger rigs."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BLENDER=r'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
# Points are metres in the original Meshy mesh, facing -Y. Hands are fitted
# individually: the three guards have bent fingers, Urban has an open T pose.
PROFILES={
 'ObsidianSentinel':dict(pelvis=.94,neck=1.51,head=1.59,shoulder=(.215,.025,1.46),elbow=(.411,.012,1.285),wrist=(.596,.006,1.173),knuckle=(.674,-.005,1.134),hip=.116,knee=.52,ankle=.105,
  fingers=[(.677,-.090,1.135,.713,-.108,1.035),(.690,-.061,1.127,.726,-.076,1.028),(.684,-.031,1.13,.727,-.042,1.038),(.667,-.006,1.14,.714,-.008,1.058)],thumb=[(.611,-.036,1.153),(.614,-.076,1.133),(.620,-.102,1.106),(.626,-.118,1.084)]),
 'RegalCommander':dict(pelvis=.94,neck=1.51,head=1.595,shoulder=(.204,.035,1.445),elbow=(.405,.040,1.273),wrist=(.596,.045,1.142),knuckle=(.661,.044,1.086),hip=.112,knee=.49,ankle=.093,
  fingers=[(.659,.003,1.086,.702,.002,.988),(.669,.031,1.083,.712,.030,.987),(.665,.059,1.089,.706,.058,1.003),(.651,.084,1.105,.698,.081,1.026)],thumb=[(.607,.010,1.109),(.603,-.014,1.079),(.609,-.027,1.049),(.614,-.032,1.030)]),
 'TheSteadfastOfficer':dict(pelvis=.955,neck=1.52,head=1.60,shoulder=(.207,.048,1.45),elbow=(.416,.050,1.271),wrist=(.607,.067,1.14),knuckle=(.679,.057,1.077),hip=.114,knee=.485,ankle=.095,
  fingers=[(.676,.029,1.079,.726,.026,.995),(.689,.058,1.072,.744,.056,.987),(.685,.083,1.083,.735,.086,1.007),(.657,.096,1.078,.710,.102,1.015)],thumb=[(.618,.020,1.114),(.626,-.012,1.085),(.639,-.047,1.059),(.646,-.066,1.041)]),
 'UrbanTrailblazer':dict(pelvis=.915,neck=1.505,head=1.595,shoulder=(.193,.031,1.445),elbow=(.447,.044,1.39),wrist=(.695,.039,1.383),knuckle=(.777,.035,1.375),hip=.116,knee=.48,ankle=.095,
  fingers=[(.781,.020,1.375,.870,.012,1.357),(.789,.049,1.374,.884,.051,1.357),(.781,.077,1.377,.870,.083,1.365),(.766,.100,1.382,.850,.107,1.374)],thumb=[(.717,.003,1.358),(.749,-.015,1.329),(.773,-.027,1.322),(.790,-.032,1.322)])
}

def skeleton(c):
    result=[]
    def bone(name,a,b,parent=None): result.append(dict(name=name,head=a,tail=b,parent=parent))
    bone('root',(0,0,0),(0,0,.1))
    base=c['pelvis']; top=c['neck']; yy=.035
    bone('pelvis',(0,yy,base),(0,yy,base+.10),'root')
    for i in range(1,6):
        a=base+.1+(top-base-.1)*(i-1)/5; b=base+.1+(top-base-.1)*i/5
        bone(f'spine_{i:02}',(0,yy,a),(0,yy,b),'pelvis' if i==1 else f'spine_{i-1:02}')
    middle=(top+c['head'])/2
    bone('neck_01',(0,yy,top),(0,yy,middle),'spine_05')
    bone('neck_02',(0,yy,middle),(0,yy,c['head']),'neck_01')
    bone('head',(0,yy,c['head']),(0,yy,1.76),'neck_02')
    for side,sign in [('l',1),('r',-1)]:
        def p(v): return (v[0]*sign,v[1],v[2])
        def limb(n,a,b,parent): bone(n+'_'+side,p(a),p(b),parent if parent in ['pelvis','spine_05'] else parent+'_'+side)
        limb('clavicle',(.025,yy,c['shoulder'][2]),c['shoulder'],'spine_05')
        limb('upperarm',c['shoulder'],c['elbow'],'clavicle')
        limb('lowerarm',c['elbow'],c['wrist'],'upperarm')
        limb('hand',c['wrist'],c['knuckle'],'lowerarm')
        hip=c['hip']; knee=(hip+.011,.015,c['knee']); ankle=(hip+.018,.037,c['ankle']); toe=(hip+.018,-.12,.045)
        limb('thigh',(hip,yy,base-.02),knee,'pelvis')
        limb('calf',knee,ankle,'thigh');limb('foot',ankle,toe,'calf');limb('ball',toe,(hip+.018,-.182,.04),'foot')
        for digit,coords in zip(['index','middle','ring','pinky'],c['fingers']):
            a=coords[:3];b=coords[3:]
            # Curled source fingers bend more at the first joint than the tip.
            if c is PROFILES['UrbanTrailblazer']:
                points=[tuple(a[k]+(b[k]-a[k])*t for k in range(3)) for t in [0,.44,.76,1]]
            else:
                points=[a,(a[0]+(b[0]-a[0])*.70,a[1]+(b[1]-a[1])*.38,a[2]+(b[2]-a[2])*.37),(a[0]+(b[0]-a[0])*.94,a[1]+(b[1]-a[1])*.73,a[2]+(b[2]-a[2])*.75),b]
            meta=digit+'_metacarpal_'+side
            start=tuple(c['wrist'][k]+(a[k]-c['wrist'][k])*.24 for k in range(3))
            bone(meta,p(start),p(a),'hand_'+side)
            for j in range(3): bone(f'{digit}_{j+1:02}_{side}',p(points[j]),p(points[j+1]),meta if j==0 else f'{digit}_{j:02}_{side}')
        for j in range(3):bone(f'thumb_{j+1:02}_{side}',p(c['thumb'][j]),p(c['thumb'][j+1]),'hand_'+side if j==0 else f'thumb_{j:02}_{side}')
    return result

if __name__=='__main__':
    config={name:dict(bones=skeleton(c)) for name,c in PROFILES.items()}
    (ROOT/'resources/NPCCharacterRigs.json').write_text(json.dumps(config,indent=2))
    for name in __import__('sys').argv[1:] or PROFILES:
        folder=ROOT/'Artifacts/NPCCharacters'/name;folder.mkdir(parents=True,exist_ok=True)
        for script in ['Rig-NPCCharacter.py','Validate-NPCRig.py']:
            with (folder/(script+'.log')).open('w') as log:
                subprocess.run([BLENDER,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'Scripts'/script),'--',name],stdout=log,stderr=subprocess.STDOUT,check=True)
        print('NPC_RIG_READY',name,flush=True)
