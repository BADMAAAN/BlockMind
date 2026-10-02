"""Fixed development-time reference fixtures, not runtime video ingestion."""
from collections import Counter
from dataclasses import dataclass

from .models import Bounds, BuildOperation, BuildPlan, Design, OperationKind, ProjectState, StructureComponent, Vec3i


@dataclass(frozen=True)
class ReferenceBuildFixture:
    key: str
    source: str
    title: str
    complete_reference: bool

    def legs_probe(self, origin: Vec3i) -> ProjectState:
        """Two source-sized 2×2×28 legs; uniform material is deliberately a probe."""
        bounds = Bounds(origin.offset(1,0,5),origin.offset(6,27,6))
        components = [StructureComponent("statue","reference_probe",bounds,metadata={"source":self.source,"partial":True})]
        operations = []
        for side, start in (("left",1),("right",5)):
            name = "statue.leg_"+side
            leg = Bounds(origin.offset(start,0,5),origin.offset(start+1,27,6))
            components.append(StructureComponent(name,"leg",leg,"minecraft:deepslate_bricks","statue",
                                                {"phase":0,"support_order":"below","exterior_access":True}))
            for y in range(28):
                for z in (5,6):
                    for x in (start,start+1):
                        operations.append(BuildOperation(OperationKind.PLACE,origin.offset(x,y,z),"minecraft:deepslate_bricks",name,
                                                         id=f"{self.key}:{side}:{x}:{y}:{z}"))
        design = Design(self.title+" — legs geometry probe",origin,bounds,components,
                        {"reference_fixture":self.key,"source_url":self.source,"partial_reference":True,
                         "dimensions":{"width":6,"depth":2,"height":28},
                         "deviations":["Uniform deepslate bricks test access; original surface mottling is not reconstructed.",
                                       "Torso, head, arms and vegetation are intentionally absent."]})
        plan = BuildPlan(design,operations,dict(Counter(op.block for op in operations)),bounds,bounds.expanded(6))
        return ProjectState("Partial source-sized Enderman legs; NOT whole reference acceptance",design,plan)


ENDERMAN_LEGS = ReferenceBuildFixture("vscraft-enderman-legs-v1",
                                    "https://vscraft.ru/ogromnaya-statuya-ehndermena-v-minecraft/",
                                    "Goldrobin overgrown Enderman",False)


def enderman_project(origin: Vec3i, grass_block: str = 'minecraft:short_grass') -> ProjectState:
    """Authorized reconstruction, NOT the author's undisclosed schematic.

    Every cell has a deterministic ID and an already-planned adjacent support.
    Dimensions explicitly labelled in the video are distinguished from inferred
    dimensions. Decorative texture and foliage are recreated with permission.
    """
    if grass_block not in {'minecraft:grass','minecraft:short_grass'}:
        raise ValueError('unsupported grass version alias')
    source = ENDERMAN_LEGS.source
    cells = {}
    components = []
    operations = []
    neighbors = ((0,-1,0),(0,1,0),(-1,0,0),(1,0,0),(0,0,-1),(0,0,1))

    def bounds(points):
        return Bounds(Vec3i(*(min(getattr(p,a) for p in points) for a in ('x','y','z'))),
                      Vec3i(*(max(getattr(p,a) for p in points) for a in ('x','y','z'))))

    def stone(p):
        # Coordinate-only stable mottling, deliberately not a hidden-block copy.
        value = (p.x*17+p.y*31+p.z*13+(p.y//3)*19) % 100
        if p.y >= 37 and value < 28:
            return 'minecraft:moss_block' if value < 15 else 'minecraft:green_wool'
        return 'minecraft:deepslate_bricks' if value < 49 else 'minecraft:mud' if value < 79 else 'minecraft:smooth_basalt'

    def add(name, points, phase, material=stone, properties=None, descending=False):
        pending = {p for p in points if p not in cells}
        if not pending:
            return
        component_bounds = bounds([origin.offset(p.x,p.y,p.z) for p in pending])
        exterior_volume = (Bounds(origin.offset(0,28,4),origin.offset(7,39,7)) if name.startswith('statue.torso_')
                           else Bounds(origin.offset(0,40,0),origin.offset(7,47,7)) if name.startswith('statue.head_')
                           else component_bounds)
        components.append(StructureComponent(name,name.split('.')[-1],component_bounds,parent_id='statue',
            metadata={'phase':phase,'support_order':'explicit','exterior_access':True,
                      'open_top_access':name == 'statue.head_base',
                      'exterior_volume':exterior_volume.to_dict()}))
        while pending:
            ready = sorted((p for p in pending if p.y == 0 or any(p.offset(*d) in cells for d in neighbors)),
                           key=lambda p: (-p.y if descending else p.y,p.z,p.x))
            if not ready:
                raise ValueError(f'disconnected reference component: {name}')
            for p in ready:
                support = next((cells[p.offset(*d)] for d in neighbors if p.offset(*d) in cells),None)
                block = material(p) if callable(material) else material
                op = BuildOperation(OperationKind.PLACE,origin.offset(p.x,p.y,p.z),block,name,
                    id=f'vscraft-enderman-v2:{p.x}:{p.y}:{p.z}',properties=dict(properties or {}),
                    depends_on=[support.id] if support else [])
                cells[p]=op; operations.append(op); pending.remove(p)

    def box(x1,x2,y1,y2,z1,z2):
        return [Vec3i(x,y,z) for y in range(y1,y2+1) for z in range(z1,z2+1) for x in range(x1,x2+1)]

    for side,x in (('left',1),('right',5)):
        add('statue.leg_'+side,box(x,x+1,0,27,5,6),0)
    add('statue.torso_base',box(0,7,28,28,4,7),1)
    for side,points in (
        ('north',box(0,7,29,38,4,4)),('east',box(7,7,29,38,5,6)),
        ('south',box(0,7,29,38,7,7)),('west',box(0,0,29,38,5,6))):
        add('statue.torso_'+side,points,2)
    add('statue.torso_cap',box(0,7,39,39,4,7),3)
    for side,x in (('left',-2),('right',8)):
        add('statue.arm_'+side,box(x,x+1,6,39,5,6),4,
            material=lambda p: 'minecraft:moss_block' if p.y==39 else stone(p),descending=True)
    add('statue.head_base',box(0,7,40,40,0,7),5)
    def face(p):
        if p.y==43 and p.x in (0,1,2,5,6,7):
            return 'minecraft:purple_concrete' if p.x in (1,6) else 'minecraft:magenta_wool'
        return stone(p)
    add('statue.head_front',box(0,7,41,46,0,0),6,face)
    add('statue.head_east',box(7,7,41,46,1,6),6)
    add('statue.head_back',box(0,7,41,46,7,7),6)
    add('statue.head_west',box(0,0,41,46,1,6),6)
    add('statue.head_roof',box(0,7,47,47,0,7),7,'minecraft:moss_block')
    # Final video also shows a small tree on the left shoulder. Trunk heights
    # and crown cells are authorized decorative approximations, not measurements.
    trees = (('head_left',1,3,48,5),('head_right',5,5,48,8),('shoulder',-2,5,40,2))
    for name,x,z,base,height in trees:
        add('statue.tree_'+name,box(x,x,base,base+height-1,z,z),8,'minecraft:oak_log',{'axis':'y'})
    for name,x,z,base,height in trees:
        foliage=[]
        for y in (base+height-2,base+height-1):
            foliage.extend(Vec3i(x+dx,y,z+dz) for dx in range(-2,3) for dz in range(-2,3)
                           if abs(dx)!=2 or abs(dz)!=2)
        foliage.extend(Vec3i(x+dx,base+height,z+dz) for dx in range(-1,2) for dz in range(-1,2))
        foliage.append(Vec3i(x,base+height+1,z))
        add('statue.canopy_'+name,foliage,9,'minecraft:oak_leaves',{'persistent':'true','waterlogged':'false'})
    # Plants stay on verified moss substrate and out of trunks/crowns.
    plant_sites = [Vec3i(x,48,z) for z in range(8) for x in range(8)
                   if Vec3i(x,48,z) not in cells and Vec3i(x,49,z) not in cells]
    for i,p in enumerate(plant_sites[:20]):
        tall = i < 8
        block = 'minecraft:rose_bush' if i<4 else 'minecraft:tall_grass' if i<8 else grass_block
        add('statue.garden', [p], 10, block, {'half':'lower'} if tall else {})
        if tall:
            lower=cells[p]
            upper=p.offset(dy=1)
            companion=BuildOperation(OperationKind.PLACE,origin.offset(upper.x,upper.y,upper.z),block,'statue.garden',
                id=f'vscraft-enderman-v2:{upper.x}:{upper.y}:{upper.z}',properties={'half':'upper'},
                verify_only=True,depends_on=[lower.id])
            cells[upper]=companion; operations.append(companion)
    # One semantic garden zone, encompassing all companion cells.
    components = [c for c in components if c.id != 'statue.garden']
    garden=[op.position for op in operations if op.component_id=='statue.garden']
    if garden:
        components.append(StructureComponent('statue.garden','plants',bounds(garden),parent_id='statue',
            metadata={'phase':10,'support_order':'explicit','exterior_access':True}))
    area=bounds([op.position for op in operations])
    components.insert(0,StructureComponent('statue','reference_reconstruction',area,metadata={'source':source}))
    design=Design('Goldrobin overgrown Enderman — authorized reconstruction',origin,area,components,
        {'reference_fixture':'vscraft-enderman-v2','source_url':source,'partial_reference':False,
         'approximation_authorized':True,'grass_version_alias':grass_block,'body_dimensions':{'width':12,'depth':8,'height':48},
         'dimensions':{'width':area.maximum.x-area.minimum.x+1,'depth':area.maximum.z-area.minimum.z+1,
                       'height':area.maximum.y-area.minimum.y+1},
         'measured':{'leg_height':28,'leg_cross_section':[2,2],'leg_gap':2,'torso':[8,12,4]},
         'inferred':{'head':[8,8,8],'head_forward_offset':4,'arm_cross_section':[2,2],
                     'arm_height':34,'arm_bottom_above_feet':6},
         'deviations':['Surface mottling is deterministic reconstruction, not author cell data.',
                       'Three tree crowns and trunk heights are recreated from final views.',
                       'Plant distribution is reconstructed on the roof; shoulder plant positions differ.',
                       'Hidden shell cells and inferred head/arm dimensions are not a bit-exact schematic.']})
    materials=dict(Counter(op.block for op in operations if not op.verify_only))
    return ProjectState('Build the VScraft Enderman by the approved visual example',design,
                        BuildPlan(design,operations,materials,area,area.expanded(6)))
