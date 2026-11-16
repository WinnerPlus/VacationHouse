# Exporta una casa a GLB para el visor web.
# Uso: blender -b "<casa>.blend" -P casa_export_web.py -- <salida.glb>
#  - materiales simplificados a color plano (los procedurales no pasan a glTF; el visor pone las texturas)
#  - UV en metros proyectadas por cara (caja), para repetir texturas por material en el visor
#  - cada objeto lleva extras.grupo = PB / P1 / BC / Cubierta / Entorno, y extras.rotulo / extras.persona
import bpy, bmesh, sys, os
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
scene = bpy.context.scene
C = bpy.data.collections

def group_of(ob):
    for c in ob.users_collection:
        n = c.name
        if n in ("Planta baja", "Rótulos PB"): return "PB"
        if n in ("Planta primera", "Rótulos P1"): return "P1"
        if n in ("Bajo cubierta", "Rótulos BC"): return "BC"
        if n == "Cubierta": return "Cubierta"
        if n == "Casa": return "Casa"
        if n in ("Calle", "Edificios colindantes"): return "Entorno"
    return None

# 1) textos a malla
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(scene.objects):
    if ob.type == 'FONT':
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        new = bpy.data.objects.new(ob.name, me); new.matrix_world = ob.matrix_world.copy()
        for c in ob.users_collection: c.objects.link(new)
        bpy.data.objects.remove(ob)

# 2) materiales a color plano
for m in bpy.data.materials:
    if not m.node_tree: continue
    b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None: continue
    for name in ('Base Color', 'Normal'):
        for l in list(b.inputs[name].links): m.node_tree.links.remove(l)
    dc = m.diffuse_color
    b.inputs['Base Color'].default_value = (dc[0], dc[1], dc[2], 1.0)

# 3) UV de caja en metros
for ob in scene.objects:
    if ob.type != 'MESH': continue
    me = ob.data
    bm = bmesh.new(); bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    mw = ob.matrix_world
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for lp in f.loops:
            p = mw @ lp.vert.co
            lp[uv].uv = (p.x, p.y) if ax == 2 else (p.y, p.z) if ax == 0 else (p.x, p.z)
    bm.to_mesh(me); bm.free()

# 4) selección y extras
skip_colls = {"Comprobación escalera"}
for ob in scene.objects: ob.select_set(False)
count = 0
for ob in scene.objects:
    if ob.type != 'MESH': continue
    if any(c.name in skip_colls for c in ob.users_collection): continue
    g = group_of(ob)
    if g is None: continue
    ob["grupo"] = g
    if ob.name.startswith("Rótulo"): ob["rotulo"] = 1
    if "Personas" in ob.name: ob["persona"] = 1
    ob.select_set(True); count += 1
print("OBJETOS", count)

# .glb para otros programas; si la salida es .json, se convierte el GLB a glTF con el binario incrustado en base64
# (Blender 5 ya no exporta "GLTF_EMBEDDED" y los artifacts no sirven .glb)
target = OUT if OUT.lower().endswith('.glb') else os.path.splitext(OUT)[0] + '.tmp.glb'
bpy.ops.export_scene.gltf(filepath=target, export_format='GLB', use_selection=True, export_apply=True,
                          export_extras=True, export_cameras=False, export_lights=False, export_yup=True,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT')
if target != OUT:
    import json, struct, base64
    data = open(target, 'rb').read()
    off, doc, binc = 12, None, b''
    while off < len(data):
        ln, typ = struct.unpack_from('<II', data, off); chunk = data[off + 8: off + 8 + ln]
        if typ == 0x4E4F534A: doc = json.loads(chunk.decode('utf-8'))
        elif typ == 0x004E4942: binc = chunk
        off += 8 + ln
    doc['buffers'][0]['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(binc).decode('ascii')
    with open(OUT, 'w', encoding='utf-8') as fh: json.dump(doc, fh, separators=(',', ':'), ensure_ascii=False)
    os.remove(target)
print("EXPORTADO", OUT, os.path.getsize(OUT))
