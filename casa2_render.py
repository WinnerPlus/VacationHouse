# Renders de una casa. Uso: blender -b "<casa>.blend" -P casa2_render.py -- <carpeta_renders> [vista ...]
import bpy, os, sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]; ONLY = set(argv[1:])
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
C = bpy.data.collections
FLOORS = ["Planta baja", "Planta primera", "Bajo cubierta", "Cubierta"]
LABELS = {"Planta baja": "Rótulos PB", "Planta primera": "Rótulos P1", "Bajo cubierta": "Rótulos BC"}
bg = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
sun = bpy.data.objects["Sol"].data
lights = [o.data for o in bpy.data.objects if o.type == 'LIGHT' and o.get("interior")]
base = {l.name: l.energy for l in lights}
DAY = (tuple(bg.inputs['Color'].default_value), bg.inputs['Strength'].default_value, sun.energy, tuple(sun.color))

def lighting(dusk):
    if dusk:
        bg.inputs['Color'].default_value = (0.10, 0.16, 0.32, 1); bg.inputs['Strength'].default_value = 0.35
        sun.energy = 0.25; sun.color = (1.0, 0.55, 0.3)
        for l in lights: l.energy = base[l.name] * 3.0
    else:
        bg.inputs['Color'].default_value = DAY[0]; bg.inputs['Strength'].default_value = DAY[1]
        sun.energy = DAY[2]; sun.color = DAY[3]
        for l in lights: l.energy = base[l.name]

def visible(floors_on, labels_of=None, neighbours=True):
    for f in FLOORS: C[f].hide_render = f not in floors_on
    for f, l in LABELS.items(): C[l].hide_render = (f != labels_of)
    C["Edificios colindantes"].hide_render = not neighbours

SHOTS = [
    ("01_calle", "Cámara calle", FLOORS, None, True, False),
    ("02_calle_atardecer", "Cámara calle", FLOORS, None, True, True),
    ("03_alzado", "Cámara alzado", FLOORS, None, True, False),
    ("04_aerea", "Cámara aérea", FLOORS, None, True, False),
    ("05_interior_salon", "Cámara interior salón", FLOORS, None, True, False),
    ("06_interior_escalera", "Cámara interior escalera", FLOORS, None, True, False),
    ("07_interior_planta_primera", "Cámara interior planta primera", FLOORS, None, True, False),
    ("08_interior_caseton", "Cámara interior casetón", FLOORS, None, True, False),
    ("09_planta_baja_3d", "Cámara PB 3D", FLOORS[:1], "Planta baja", False, False),
    ("10_planta_primera_3d", "Cámara P1 3D", FLOORS[:2], "Planta primera", False, False),
    ("11_bajo_cubierta_3d", "Cámara BC 3D", FLOORS[:3], "Bajo cubierta", False, False),
    ("12_planta_baja_cenital", "Cámara PB planta", FLOORS[:1], "Planta baja", False, False),
    ("13_planta_primera_cenital", "Cámara P1 planta", FLOORS[:2], "Planta primera", False, False),
    ("14_bajo_cubierta_cenital", "Cámara BC planta", FLOORS[:3], "Bajo cubierta", False, False),
    ("15_interior_dormitorio_2", "Cámara interior dormitorio 2", FLOORS, None, True, False),
    ("16_seccion_escalera_atico", "Cámara sección escalera", FLOORS, None, False, False),
]
CHK = C.get("Comprobación escalera")
for name, cam, floors, labels, neigh, dusk in SHOTS:
    if ONLY and name not in ONLY: continue
    if cam not in bpy.data.objects: continue
    visible(floors, labels, neigh); lighting(dusk)
    if CHK: CHK.hide_render = not name.startswith("16_")
    for o in bpy.data.objects:
        if o.name.endswith("Personas de referencia"): o.hide_render = name.startswith("16_")
    scene.camera = bpy.data.objects[cam]
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", name)
visible(FLOORS, None, True); lighting(False)
