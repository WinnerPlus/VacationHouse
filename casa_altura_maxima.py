# Comprueba la cota más alta de la casa (sin entorno). Uso: blender -b "<casa>.blend" -P casa_altura_maxima.py
import bpy
casa = bpy.data.collections["Casa"]
top, quien = -1e9, None
for ob in casa.all_objects:
    if ob.type != 'MESH': continue
    for v in ob.data.vertices:
        z = (ob.matrix_world @ v.co).z
        if z > top: top, quien = z, ob.name
print(f"COTA MAXIMA {top:.3f} m en «{quien}»")
