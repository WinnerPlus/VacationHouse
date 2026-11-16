# Renders de la casa. Uso: blender -b "Casa de vacaciones.blend" -P casa_render.py -- <carpeta_renders> [vista ...]
import bpy, os, sys

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0]; ONLY = set(argv[1:])
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
C = bpy.data.collections

FLOORS = ["Planta baja", "Planta primera", "Bajo cubierta", "Cubierta"]
LABELS = {"Planta baja": "Rótulos PB", "Planta primera": "Rótulos P1", "Bajo cubierta": "Rótulos BC"}

def visible(floors_on, labels_of=None, neighbours=True):
    for f in FLOORS: C[f].hide_render = f not in floors_on
    for f, l in LABELS.items(): C[l].hide_render = (f != labels_of)
    C["Edificios colindantes"].hide_render = not neighbours

SHOTS = [
    ("01_calle", "Cámara calle", FLOORS, None, True, (1600, 1000)),
    ("02_aerea", "Cámara aérea", FLOORS, None, True, (1600, 1000)),
    ("03_interior_salon", "Cámara interior salón", FLOORS, None, True, (1600, 1000)),
    ("10_alzado", "Cámara alzado", FLOORS, None, True, (1600, 1000)),
    ("11_interior_dormitorio_1", "Cámara interior dormitorio 1", FLOORS, None, True, (1600, 1000)),
    ("04_planta_baja_3d", "Cámara PB 3D", FLOORS[:1], "Planta baja", False, (1600, 1000)),
    ("05_planta_primera_3d", "Cámara P1 3D", FLOORS[:2], "Planta primera", False, (1600, 1000)),
    ("06_bajo_cubierta_3d", "Cámara BC 3D", FLOORS[:3], "Bajo cubierta", False, (1600, 1000)),
    ("07_planta_baja_cenital", "Cámara PB planta", FLOORS[:1], "Planta baja", False, (1600, 1000)),
    ("08_planta_primera_cenital", "Cámara P1 planta", FLOORS[:2], "Planta primera", False, (1600, 1000)),
    ("09_bajo_cubierta_cenital", "Cámara BC planta", FLOORS[:3], "Bajo cubierta", False, (1600, 1000)),
]

for name, cam, floors, labels, neigh, res in SHOTS:
    if ONLY and name not in ONLY: continue
    visible(floors, labels, neigh)
    scene.camera = bpy.data.objects[cam]
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", name)

visible(FLOORS, None, True)   # deja todo visible
