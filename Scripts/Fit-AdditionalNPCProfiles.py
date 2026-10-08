"""Blender: convert inspected hand landmarks to fitted UE humanoid profiles."""
import bpy,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
# HandTop.png pixel coordinates, index/middle/ring/pinky, proximal to distal.
LANDMARKS={
 'ArmoredSentinel':(115,[(438,576,676,575),(440,490,700,487),(436,424,650,419),(407,363,552,359)],[(228,586),(315,645),(387,691),(429,716)]),
 'AstronautSentinel':(120,[(427,562,666,548),(438,493,704,487),(431,428,677,426),(434,366,620,373)],[(220,594),(303,639),(365,677),(410,693)]),
 'CrimsonVanguard':(205,[(497,552,693,558),(508,510,706,513),(504,450,685,462),(480,386,602,387)],[(263,587),(327,620),(387,635),(424,640)]),
 'MaintenanceWorker':(105,[(394,551,663,610),(405,483,704,514),(390,412,677,400),(375,347,593,330)],[(230,546),(320,592),(385,614),(416,632)]),
 'RustboundExplorer':(145,[(405,590,626,615),(419,510,704,506),(411,427,645,402),(395,355,545,342)],[(242,599),(318,656),(385,690),(421,710)]),
 'CrimsonAuthority':(203,[(470,581,687,568),(484,506,709,506),(472,431,700,431),(442,367,642,371)],[(313,601),(373,650),(453,674),(531,692)]),
 'CrusaderOperative':(150,[(441,605,665,592),(426,525,703,515),(414,444,693,423),(404,360,636,350)],[(258,614),(328,665),(383,699),(408,727)]),
 'GraySentinel':(150,[(428,558,677,535),(440,492,709,487),(428,432,670,431),(414,371,579,371)],[(254,569),(339,614),(409,640),(477,655)]),
 'RuggedSurvivor':(112,[(422,612,667,605),(434,515,705,520),(437,442,665,432),(444,372,593,372)],[(262,665),(340,687),(411,707),(468,709)])}
profiles={}
for name,(wrist_px,fingers,thumb) in LANDMARKS.items():
    folder=ROOT/'Artifacts/NPCCharacters'/name;report=json.loads((folder/'source-inspection.json').read_text());center=report['hand_center'];pixel=.34/1000
    bpy.ops.wm.open_mainfile(filepath=str(folder/'Working.blend'))
    mesh=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    coords=np.empty(len(mesh.data.vertices)*3,dtype=np.float32);mesh.data.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
    hand=coords[(coords[:,0]>center[0]-.2)&(coords[:,2]>1.15)]
    def point(px,py):
        x=center[0]+(px-500)*pixel;y=center[1]+(500-py)*pixel
        distance=(hand[:,0]-x)**2+(hand[:,1]-y)**2
        nearest=hand[np.argsort(distance)[:16]]
        z=float((np.percentile(nearest[:,2],10)+np.percentile(nearest[:,2],90))*.5)
        return [round(x,5),round(y,5),round(z,5)]
    def arm(x):
        section=coords[(abs(coords[:,0]-x)<.012)&(coords[:,2]>1.20)]
        return [x,float(np.median(section[:,1])),float(np.median(section[:,2]))]
    wrist=arm(center[0]+(wrist_px-500)*pixel)
    pairs=[point(a,b)+point(c,d) for a,b,c,d in fingers]
    knuckle=np.mean([f[:3] for f in pairs],axis=0).tolist()
    profiles[name]=dict(pelvis=.94,neck=1.505,head=1.59,shoulder=[.2,.035,max(1.435,wrist[2]+.065)],elbow=arm((wrist[0]+.2)*.5),wrist=wrist,knuckle=knuckle,hip=.115,knee=.505,ankle=.105,straight_fingers=True,fingers=pairs,thumb=[point(*p) for p in thumb])
# This source has lowered arms and curled gloves, fitted in both orthographic views.
profiles['RuggedMiner']=dict(pelvis=.945,neck=1.505,head=1.59,shoulder=[.207,.02,1.445],elbow=[.411,-.016,1.282],wrist=[.599,-.031,1.155],knuckle=[.662,-.045,1.101],hip=.116,knee=.505,ankle=.10,
 fingers=[(.660,-.080,1.102,.704,-.092,1.022),(.671,-.060,1.091,.721,-.071,1.011),(.670,-.036,1.098,.718,-.048,1.029),(.651,-.012,1.118,.704,-.024,1.051)],thumb=[(.601,-.051,1.127),(.604,-.087,1.092),(.618,-.110,1.065),(.638,-.121,1.048)])
(ROOT/'resources/NPCAdditionalProfiles.json').write_text(json.dumps(profiles,indent=2)+'\n')
print('ADDITIONAL_CHARACTER_PROFILES_FITTED',len(profiles))
