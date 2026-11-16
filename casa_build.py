# Casa de vacaciones: modelo 3D a partir de los planos (PB, P1, bajocubierta, sección y alzado).
# Uso: blender -b -P casa_build.py -- <carpeta_salida>
#
# Sistema de coordenadas (metros), igual que los planos oficiales:
#   X: de la calle (x=0) hacia el fondo (muro de piedra, x=7.80)
#   Y: del colindante sur (y=0, lado de 7.80) al colindante norte (y=4.67, lado de 7.42)
#   Z: altura. Calle y planta baja = +0.00, planta 1ª = +2.80, bajocubierta = +5.60

import bpy, bmesh, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(OUT_DIR, "Casa de vacaciones.blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

# ---------------------------------------------------------------- cotas
RIDGE_X, SLOPE, Z_RIDGE, ROOF_T = 3.51, 0.45, 8.94, 0.33
def z_top(x): return Z_RIDGE - SLOPE * abs(x - RIDGE_X)      # cara superior de cubierta
def z_under(x): return z_top(x) - ROOF_T                      # cara inferior (techo bajocubierta)

LV = {"PB": 0.0, "P1": 2.80, "BC": 5.60}
SLAB, CLEAR = 0.30, 2.50
X_OUT, X_IN = 7.80, 7.60
Y_N_OUT, Y_S_IN, Y_N_IN = 4.67, 0.25, 4.42

FA = Vector((0.0, 0.0)); FD = Vector((0.385, Y_N_OUT))      # fachada inclinada a la calle
FL = (FD - FA).length; FU = (FD - FA) / FL; FN = Vector((FU.y, -FU.x))   # FN apunta hacia dentro
FT = 0.30
def xf(y, d=0.0): return (d - FN.y * y) / FN.x               # x de la línea de fachada desplazada d hacia dentro
def F(s, d=0.0):
    p = FA + FU * s + FN * d
    return (p.x, p.y)
def fquad(s0, s1, d0, d1): return [F(s0, d0), F(s1, d0), F(s1, d1), F(s0, d1)]

# escalera en U (misma en las tres plantas)
ST_X0, ST_D = 5.30, 0.28
ST_XW = ST_X0 + 6 * ST_D
ST_XR = X_IN
ST_YL = (Y_S_IN, 1.20)
ST_YU = (1.28, 2.10)
RISER = 2.80 / 16

# ---------------------------------------------------------------- materiales
def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)

def new_mat(name):
    m = bpy.data.materials.new(name)
    try: m.use_nodes = True
    except Exception: pass
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    o = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if b is None: b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    if o is None: o = nt.nodes.new('ShaderNodeOutputMaterial')
    if not o.inputs['Surface'].is_linked: nt.links.new(b.outputs['BSDF'], o.inputs['Surface'])
    return m, nt, b

def basic(name, hexc, rough=0.6, metal=0.0, alpha=1.0):
    m, nt, b = new_mat(name); c = srgb(hexc)
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if alpha < 1.0:
        b.inputs['Alpha'].default_value = alpha
        for attr, val in (('surface_render_method', 'BLENDED'), ('blend_method', 'BLEND'), ('use_transparent_shadow', True)):
            try: setattr(m, attr, val)
            except Exception: pass
    m.diffuse_color = (*c, alpha)
    return m

def sock(node, name, typ, out=False):
    coll = node.outputs if out else node.inputs
    return next(s for s in coll if s.name == name and s.type == typ)

def mix(nt, a, b, fac, blend='MIX'):
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = blend
    for s, v in ((sock(mx, 'Factor', 'VALUE'), fac), (sock(mx, 'A', 'RGBA'), a), (sock(mx, 'B', 'RGBA'), b)):
        if isinstance(v, bpy.types.NodeSocket): nt.links.new(v, s)
        else: s.default_value = v
    return sock(mx, 'Result', 'RGBA', out=True)

def math_node(nt, op, a, b=None):
    n = nt.nodes.new('ShaderNodeMath'); n.operation = op
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, bpy.types.NodeSocket): nt.links.new(v, n.inputs[i])
        else: n.inputs[i].default_value = v
    return n.outputs[0]

def brick_mat(name, c1, c2, cm, width, height, mortar, offset, rough, facade=False, bump=0.0, grain=0.0):
    m, nt, b = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vec = tc.outputs['Object']
    if facade:   # textura sobre plano vertical (y, z)
        sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(vec, sp.inputs[0])
        cb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(sp.outputs['Y'], cb.inputs['X']); nt.links.new(sp.outputs['Z'], cb.inputs['Y']); nt.links.new(sp.outputs['X'], cb.inputs['Z'])
        vec = cb.outputs[0]
    br = nt.nodes.new('ShaderNodeTexBrick'); br.offset = offset; br.offset_frequency = 1
    nt.links.new(vec, br.inputs['Vector'])
    br.inputs['Color1'].default_value = (*srgb(c1), 1); br.inputs['Color2'].default_value = (*srgb(c2), 1)
    br.inputs['Mortar'].default_value = (*srgb(cm), 1)
    br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = mortar
    br.inputs['Brick Width'].default_value = width; br.inputs['Row Height'].default_value = height
    col = br.outputs['Color']
    if grain > 0:
        mp = nt.nodes.new('ShaderNodeMapping'); nt.links.new(vec, mp.inputs['Vector'])
        mp.inputs['Scale'].default_value = (1.0, 30.0, 1.0)
        nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.5
        nz.inputs['Detail'].default_value = 6.0
        nt.links.new(mp.outputs['Vector'], nz.inputs['Vector'])
        col = mix(nt, col, nz.outputs['Fac'], grain, 'MULTIPLY')
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    if bump > 0:
        bp = nt.nodes.new('ShaderNodeBump'); bp.invert = True
        bp.inputs['Strength'].default_value = bump
        nt.links.new(br.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (*srgb(c1), 1)
    return m

def roof_mat():
    m, nt, b = new_mat('Cubierta chapa roja')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sp.inputs[0])
    rib = math_node(nt, 'LESS_THAN', math_node(nt, 'FRACT', math_node(nt, 'DIVIDE', sp.outputs['Y'], 0.32)), 0.09)
    col = mix(nt, (*srgb('#A23A2C'), 1), (*srgb('#7E2A20'), 1), rib)
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.45; b.inputs['Metallic'].default_value = 0.3
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.5
    nt.links.new(rib, bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (*srgb('#A23A2C'), 1)
    return m

def stone_mat():
    m, nt, b = new_mat('Muro de mampostería')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'
    vo.inputs['Scale'].default_value = 3.2
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    vc = nt.nodes.new('ShaderNodeTexVoronoi'); vc.inputs['Scale'].default_value = 3.2
    nt.links.new(tc.outputs['Object'], vc.inputs['Vector'])
    mort = math_node(nt, 'LESS_THAN', vo.outputs['Distance'], 0.045)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*srgb('#6E665C'), 1); ramp.color_ramp.elements[1].color = (*srgb('#B3A794'), 1)
    sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(vc.outputs['Color'], sp.inputs[0])
    nt.links.new(sp.outputs[0], ramp.inputs['Fac'])
    col = mix(nt, ramp.outputs['Color'], (*srgb('#3F3B36'), 1), mort)
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.95
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.9
    nt.links.new(math_node(nt, 'MINIMUM', vo.outputs['Distance'], 0.12), bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (*srgb('#8E8474'), 1)
    return m

M = {
    'pared_int': basic('Pared interior', '#F1EEE8', 0.85),
    'techo': basic('Techo', '#F6F5F1', 0.9),
    'revoco_rosa': basic('Fachada revoco rosa', '#E9AFA3', 0.85),
    'enfoscado': basic('Enfoscado exterior', '#E3DCD0', 0.9),
    'piedra_fachada': brick_mat('Fachada aplacado piedra', '#D3CFC7', '#C3BEB5', '#9C978F', 0.55, 0.28, 0.012, 0.5, 0.8, facade=True, bump=0.35),
    'teja': roof_mat(),
    'canto': basic('Canto cubierta', '#DAD7D1', 0.8),
    'parquet': brick_mat('Suelo madera', '#BC8E61', '#AA7C51', '#7A5638', 1.2, 0.19, 0.003, 0.37, 0.45, grain=0.35),
    'baldosa': brick_mat('Suelo porcelánico', '#D9D3C9', '#D0C9BE', '#A9A398', 0.6, 0.6, 0.004, 0.0, 0.35),
    'baldosa_bano': brick_mat('Suelo baño', '#CBD3D6', '#C1CACD', '#99A3A7', 0.3, 0.3, 0.004, 0.0, 0.3),
    'marco': basic('Carpintería antracita', '#2F3236', 0.4, 0.3),
    'vidrio': basic('Vidrio', '#BFD8E2', 0.05, alpha=0.2),
    'puerta_ext': basic('Puerta de entrada madera', '#6B4A30', 0.5),
    'puerta_int': basic('Puertas interiores', '#EDE9E2', 0.5),
    'escalera': basic('Peldaños madera', '#A97C50', 0.45),
    'piedra_muro': stone_mat(),
    'mueble_blanco': basic('Mueble blanco', '#F4F2EE', 0.4),
    'frente': basic('Frentes de mueble', '#E8E4DC', 0.35),
    'madera_mueble': basic('Madera mueble', '#9C7552', 0.5),
    'encimera': basic('Encimera', '#3A3A3C', 0.3),
    'metal': basic('Acero', '#B9BCBF', 0.25, 1.0),
    'negro': basic('Negro', '#151515', 0.2),
    'sofa': basic('Tela sofá', '#5D6F7E', 0.9),
    'cojin': basic('Cojines', '#D8B26E', 0.9),
    'alfombra': basic('Alfombra', '#D9CBB2', 1.0),
    'ceramica': basic('Cerámica', '#FAFAFA', 0.15),
    'colchon': basic('Ropa de cama', '#F3F1EC', 0.9),
    'almohada': basic('Almohada', '#FFFFFF', 0.9),
    'edredon1': basic('Edredón terracota', '#C0704F', 0.9),
    'edredon2': basic('Edredón verde', '#7E8F6A', 0.9),
    'edredon3': basic('Edredón azul', '#5E7FA0', 0.9),
    'espejo': basic('Espejo', '#DDE6EA', 0.02, 1.0),
    'gris_banda': basic('Panel gris fachada', '#9A9C9E', 0.6),
    'vecino': basic('Edificio colindante', '#D9D4CC', 0.9),
    'vecino_cub': basic('Cubierta colindante', '#9C8F86', 0.9),
    'ventana_vecino': basic('Ventanas colindantes', '#3B4650', 0.2),
    'acera': brick_mat('Acera', '#B9B6B0', '#AEAAA3', '#8F8B85', 0.4, 0.4, 0.004, 0.0, 0.7),
    'asfalto': basic('Asfalto', '#4A4C4F', 0.9),
    'texto': basic('Rótulos', '#2B2B2B', 0.8),
    'electro': basic('Electrodoméstico', '#E9EAEC', 0.3),
    'planta': basic('Plantas', '#5C7A45', 0.8),
}

# ---------------------------------------------------------------- utilidades de malla
def clip(poly, X, keep_less):
    def inside(p): return p[0] <= X + 1e-9 if keep_less else p[0] >= X - 1e-9
    def inter(a, b):
        t = (X - a[0]) / (b[0] - a[0]); return (X, a[1] + t * (b[1] - a[1]))
    out = []
    for i in range(len(poly)):
        cur, prev = poly[i], poly[i - 1]
        if inside(cur):
            if not inside(prev): out.append(inter(prev, cur))
            out.append(cur)
        elif inside(prev):
            out.append(inter(prev, cur))
    return out

class MB:
    """Acumula prismas en una sola malla; cada cara lleva un material o una regla(normal)->material."""
    def __init__(self): self.v, self.f, self.r = [], [], []
    def _face(self, idx, rule): self.f.append(idx); self.r.append(rule)

    def prism(self, poly, z0, ztop, rule):
        poly = [tuple(p) for p in poly]
        if callable(ztop):
            xs = [p[0] for p in poly]
            if min(xs) < RIDGE_X - 1e-6 and max(xs) > RIDGE_X + 1e-6:
                for part in (clip(poly, RIDGE_X, True), clip(poly, RIDGE_X, False)):
                    if len(part) >= 3: self.prism(part, z0, ztop, rule)
                return
        n = len(poly)
        area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
        if abs(area) < 1e-9: return
        if area < 0: poly.reverse()
        b = len(self.v)
        for x, y in poly: self.v.append((x, y, z0))
        for x, y in poly: self.v.append((x, y, ztop(x, y) if callable(ztop) else ztop))
        self._face([b + i for i in reversed(range(n))], rule)
        self._face([b + n + i for i in range(n)], rule)
        for i in range(n):
            j = (i + 1) % n; self._face([b + i, b + j, b + n + j, b + n + i], rule)

    def box(self, x0, x1, y0, y1, z0, z1, rule):
        self.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, rule)

    def xz_prism(self, prof, y0, y1, rule):
        b = len(self.v); n = len(prof)
        for x, z in prof: self.v.append((x, y0, z))
        for x, z in prof: self.v.append((x, y1, z))
        self._face([b + i for i in range(n)], rule)
        self._face([b + n + i for i in reversed(range(n))], rule)
        for i in range(n):
            j = (i + 1) % n; self._face([b + i, b + j, b + n + j, b + n + i], rule)

    def yz_prism(self, prof, x0, x1, rule):
        b = len(self.v); n = len(prof)
        for y, z in prof: self.v.append((x0, y, z))
        for y, z in prof: self.v.append((x1, y, z))
        self._face([b + i for i in range(n)], rule)
        self._face([b + n + i for i in reversed(range(n))], rule)
        for i in range(n):
            j = (i + 1) % n; self._face([b + i, b + j, b + n + j, b + n + i], rule)

    def cyl(self, cx, cy, r, z0, z1, rule, seg=28):
        self.prism([(cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], z0, z1, rule)

    def cyl_y(self, cx, cz, r, y0, y1, rule, seg=28):
        self.xz_prism([(cx + r * math.cos(2 * math.pi * k / seg), cz + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], y0, y1, rule)

    def cyl_x(self, cy, cz, r, x0, x1, rule, seg=28):
        self.yz_prism([(cy + r * math.cos(2 * math.pi * k / seg), cz + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], x0, x1, rule)

    def build(self, name, coll):
        if not self.f: return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        bm = bmesh.new(); bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        mats = []
        for f in bm.faces:
            rule = self.r[f.index]
            m = rule(f.normal) if callable(rule) else rule
            if m not in mats: mats.append(m)
            f.material_index = mats.index(m)
        bm.to_mesh(me); bm.free()
        for m in mats: me.materials.append(m)
        ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
        return ob

def ext_rule(ext, inner, d):
    dv = Vector((d[0], d[1], 0.0)).normalized()
    return lambda n: ext if n.dot(dv) > 0.7 else inner

def top_rule(top, other, bottom=None):
    return lambda n: top if n.z > 0.5 else (bottom if (bottom is not None and n.z < -0.5) else other)

def wall(mb, P, Q, d0, d1, z0, ztop, openings, rule):
    """Muro recto de P a Q (en planta), grosor de d0 a d1 sobre la normal derecha; huecos (s0, s1, z_inf, z_sup)."""
    P = Vector(P); Q = Vector(Q); L = (Q - P).length; u = (Q - P) / L; n = Vector((u.y, -u.x))
    def quad(s0, s1): return [tuple(P + u * s0 + n * d0), tuple(P + u * s1 + n * d0), tuple(P + u * s1 + n * d1), tuple(P + u * s0 + n * d1)]
    s = 0.0
    for (s0, s1, zb, zt) in sorted(openings):
        if s0 > s: mb.prism(quad(s, s0), z0, ztop, rule)
        if zb > z0 + 1e-6: mb.prism(quad(s0, s1), z0, zb, rule)
        mb.prism(quad(s0, s1), zt, ztop, rule)
        s = s1
    if s < L - 1e-6: mb.prism(quad(s, L), z0, ztop, rule)

class Local:
    """Ejes locales para piezas apoyadas en una pared: a = distancia desde la pared, b = lateral."""
    def __init__(self, wall, c, d): self.w, self.c, self.d = wall, c, d
    def pt(self, a, b):
        w, c, d = self.w, self.c, self.d
        return {'+x': (w + a, c + b), '-x': (w - a, c - b), '+y': (c - b, w + a), '-y': (c + b, w - a)}[d]
    def rect(self, a0, a1, b0, b1):
        p, q = self.pt(a0, b0), self.pt(a1, b1)
        return (min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1]))

def lbox(mb, L, a0, a1, b0, b1, z0, z1, mat):
    x0, x1, y0, y1 = L.rect(a0, a1, b0, b1); mb.box(x0, x1, y0, y1, z0, z1, mat)

# ---------------------------------------------------------------- colecciones
def new_coll(name, parent=None):
    c = bpy.data.collections.new(name); (parent or scene.collection).children.link(c); return c

C_CASA = new_coll("Casa")
C_PB = new_coll("Planta baja", C_CASA)
C_P1 = new_coll("Planta primera", C_CASA)
C_BC = new_coll("Bajo cubierta", C_CASA)
C_ROOF = new_coll("Cubierta", C_CASA)
C_LBL = {"PB": new_coll("Rótulos PB", C_PB), "P1": new_coll("Rótulos P1", C_P1), "BC": new_coll("Rótulos BC", C_BC)}
C_ENT = new_coll("Entorno")
C_CALLE = new_coll("Calle", C_ENT)
C_VEC = new_coll("Edificios colindantes", C_ENT)   # incluye el muro de piedra trasero
C_CAM = new_coll("Cámaras y luces")

def label(level, text, x, y, size=0.2, rot=0.0):
    cu = bpy.data.curves.new("Rótulo", 'FONT')
    cu.body = text; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'
    cu.space_line = 0.9
    cu.materials.append(M['texto'])
    ob = bpy.data.objects.new("Rótulo " + text.split("\n")[0], cu)
    ob.location = (x, y, LV[level] + 0.03); ob.rotation_euler = (0, 0, rot)
    C_LBL[level].objects.link(ob)

def area_light(name, coll, loc, sx, sy, watts, color=(1.0, 0.93, 0.84)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = sx; ld.size_y = sy
    ld.energy = watts; ld.color = color
    try: ld.use_shadow = False
    except Exception: pass
    ob = bpy.data.objects.new(name, ld); ob.location = loc; coll.objects.link(ob)

# ---------------------------------------------------------------- envolvente por planta
FACADE_OPEN = {
    "PB": [(0.60, 2.00, 0.70, 2.30), (2.70, 3.60, 0.00, 2.30)],   # ventana 1.40x1.60 y puerta 0.90x2.30
    "P1": [(0.60, 2.00, 2.80, 4.95), (2.70, 3.60, 2.80, 4.95)],   # balcones franceses 1.40 y 0.90 x 2.15
    "BC": [],
}

def roof_cut(x, y): return z_under(x) + 0.12

def shell(level, coll):
    z0 = LV[level]
    ztop = {"PB": LV["P1"], "P1": LV["BC"], "BC": roof_cut}[level]
    mb = MB()
    fac_ext = M['piedra_fachada'] if level == "PB" else M['revoco_rosa']
    wall(mb, FA, FD, 0.0, FT, z0, ztop, FACADE_OPEN[level], ext_rule(fac_ext, M['pared_int'], (-FN.x, -FN.y)))
    mb.prism([(0.10, 0.0), (X_OUT, 0.0), (X_OUT, Y_S_IN), (0.10, Y_S_IN)], z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (0, -1)))
    mb.prism([(0.45, Y_N_IN), (X_OUT, Y_N_IN), (X_OUT, Y_N_OUT), (0.45, Y_N_OUT)], z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (0, 1)))
    mb.box(X_IN, X_OUT, Y_S_IN, Y_N_IN, z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (1, 0)))
    mb.build(f"{level} Muros exteriores", coll)

def slab(level, coll, notch=True, name=None):
    z1 = LV[level]; z0 = z1 - SLAB
    e = 0.02; ys, yn, xr = Y_S_IN - e, Y_N_IN + e, X_IN + e
    if notch:
        poly = [(xf(ys, FT) - e, ys), (ST_X0, ys), (ST_X0, ST_YU[1]), (xr, ST_YU[1]), (xr, yn), (xf(yn, FT) - e, yn)]
    else:
        poly = [(xf(ys, FT) - e, ys), (xr, ys), (xr, yn), (xf(yn, FT) - e, yn)]
    floor = M['baldosa'] if level == "PB" else M['parquet']
    mb = MB(); mb.prism(poly, z0, z1, top_rule(floor, M['techo'], M['techo']))
    mb.build(name or f"{level} Forjado y suelo", coll)

def bath_floor(level, rects, coll, name):
    mb = MB(); z = LV[level]
    for (x0, x1, y0, y1) in rects: mb.box(x0, x1, y0, y1, z, z + 0.006, M['baldosa_bano'])
    mb.build(name, coll)

# ---------------------------------------------------------------- carpinterías de fachada
def facade_window(mbf, mbg, s0, s1, zb, zt, mull=True, f=0.06, d=(0.05, 0.12)):
    mbf.prism(fquad(s0, s0 + f, *d), zb, zt, M['marco'])
    mbf.prism(fquad(s1 - f, s1, *d), zb, zt, M['marco'])
    mbf.prism(fquad(s0 + f, s1 - f, *d), zb, zb + f, M['marco'])
    mbf.prism(fquad(s0 + f, s1 - f, *d), zt - f, zt, M['marco'])
    if mull:
        mid = (s0 + s1) / 2; mbf.prism(fquad(mid - 0.035, mid + 0.035, *d), zb + f, zt - f, M['marco'])
    mbg.prism(fquad(s0 + f, s1 - f, 0.08, 0.09), zb + f, zt - f, M['vidrio'])

def facade_carpentry():
    # Planta baja
    f, g = MB(), MB()
    facade_window(f, g, 0.60, 2.00, 0.70, 2.30)
    f.prism(fquad(0.55, 2.05, -0.05, 0.05), 0.66, 0.70, M['canto'])         # vierteaguas
    f.prism(fquad(2.70, 2.76, 0.05, 0.12), 0.0, 2.30, M['marco'])           # marco puerta
    f.prism(fquad(3.54, 3.60, 0.05, 0.12), 0.0, 2.30, M['marco'])
    f.prism(fquad(2.76, 3.54, 0.05, 0.12), 2.24, 2.30, M['marco'])
    f.prism(fquad(2.76, 3.54, 0.07, 0.11), 0.0, 2.24, M['puerta_ext'])      # hoja de entrada
    for k in range(4):
        z = 0.35 + k * 0.48
        f.prism(fquad(2.86, 3.44, 0.06, 0.07), z, z + 0.36, M['puerta_ext'])   # cuarterones
    f.prism(fquad(3.42, 3.45, 0.02, 0.07), 1.0, 1.25, M['metal'])           # tirador
    f.build("PB Ventana y puerta de entrada", C_PB); g.build("PB Vidrios", C_PB)
    # Planta primera: balcones franceses con barandilla de vidrio y panel gris entre huecos
    f, g = MB(), MB()
    for (s0, s1) in ((0.60, 2.00), (2.70, 3.60)):
        facade_window(f, g, s0, s1, 2.80, 4.95, mull=True)
        g.prism(fquad(s0 + 0.03, s1 - 0.03, -0.05, -0.035), 2.86, 3.84, M['vidrio'])
        f.prism(fquad(s0, s1, -0.065, -0.025), 3.84, 3.88, M['metal'])
        f.prism(fquad(s0, s0 + 0.04, -0.065, 0.0), 2.80, 3.88, M['metal'])
        f.prism(fquad(s1 - 0.04, s1, -0.065, 0.0), 2.80, 3.88, M['metal'])
    f.prism(fquad(2.00, 2.70, -0.03, 0.0), 2.80, 4.95, M['gris_banda'])
    f.build("P1 Balcones franceses", C_P1); g.build("P1 Vidrios", C_P1)

# ---------------------------------------------------------------- escalera
def stair(level, coll, solid):
    z0 = LV[level]; mb = MB()
    rule = top_rule(M['escalera'], M['pared_int'])
    def tread(poly, i, solid_i):
        top = z0 + i * RISER
        mb.prism(poly, z0 if solid_i else top - 0.30, top, rule)
    for i in range(1, 7):
        xa = ST_X0 + (i - 1) * ST_D; xb = xa + ST_D
        tread([(xa, ST_YL[0]), (xb, ST_YL[0]), (xb, ST_YL[1]), (xa, ST_YL[1])], i, solid)
    P = (ST_XW, 1.24)
    winders = [[(ST_XW, ST_YL[0]), (ST_XR, ST_YL[0]), (ST_XR, 0.85), P],
               [P, (ST_XR, 0.85), (ST_XR, 1.65)],
               [P, (ST_XR, 1.65), (ST_XR, ST_YU[1]), (ST_XW, ST_YU[1])]]
    for k, poly in enumerate(winders): tread(poly, 7 + k, solid)
    for i in range(10, 16):
        k = i - 10; xb = ST_XW - k * ST_D; xa = xb - ST_D
        tread([(xa, ST_YU[0]), (xb, ST_YU[0]), (xb, ST_YU[1]), (xa, ST_YU[1])], i, False)
    mb.build(f"{level} Escalera", coll)
    # pasamanos
    h = MB(); hz = 0.90
    a, b = z0 + RISER + hz, z0 + 6 * RISER + hz
    h.xz_prism([(ST_X0, a), (ST_XW, b), (ST_XW, b + 0.05), (ST_X0, a + 0.05)], ST_YL[0] + 0.03, ST_YL[0] + 0.07, M['metal'])
    a, b = z0 + 10 * RISER + hz, z0 + 15 * RISER + hz
    h.xz_prism([(ST_XW, a), (ST_X0, b), (ST_X0, b + 0.05), (ST_XW, a + 0.05)], ST_YU[1] - 0.07, ST_YU[1] - 0.03, M['metal'])
    if level == "PB":   # barandilla de vidrio sobre el pasillo del lavadero
        for i in range(10, 15):
            k = i - 10; xb = ST_XW - k * ST_D; xa = xb - ST_D
            top = z0 + i * RISER
            h.box(xa, xb, ST_YU[1] - 0.02, ST_YU[1], top, min(top + 0.90, CLEAR), M['vidrio'])
    h.build(f"{level} Pasamanos", coll)

# ---------------------------------------------------------------- mobiliario
def door_leaf(mb, x0, x1, y0, y1, z, h=2.03):
    mb.box(x0, x1, y0, y1, z, z + h, M['puerta_int'])

def bed(mb, x0, x1, y0, y1, z, head, duvet):
    along_y = head in ('+y', '-y')
    Llong = (y1 - y0) if along_y else (x1 - x0)
    def part(a0, a1, c=0.0):
        return {'+y': (x0 + c, x1 - c, y1 - a1, y1 - a0), '-y': (x0 + c, x1 - c, y0 + a0, y0 + a1),
                '+x': (x1 - a1, x1 - a0, y0 + c, y1 - c), '-x': (x0 + a0, x0 + a1, y0 + c, y1 - c)}[head]
    def bx(r, za, zb, m): mb.box(r[0], r[1], r[2], r[3], z + za, z + zb, m)
    bx(part(0.10, Llong - 0.10, 0.10), 0.0, 0.10, M['negro'])
    bx(part(0.0, Llong), 0.10, 0.32, M['madera_mueble'])
    bx(part(0.0, 0.06), 0.0, 0.95, M['madera_mueble'])
    bx(part(0.06, Llong - 0.02, 0.03), 0.32, 0.52, M['colchon'])
    bx(part(0.62, Llong + 0.02, -0.02), 0.44, 0.57, duvet)
    w = (x1 - x0) if along_y else (y1 - y0)
    r = part(0.12, 0.45, 0.10)
    if w > 1.2:
        if along_y:
            mid = (r[0] + r[1]) / 2; bx((r[0], mid - 0.04, r[2], r[3]), 0.52, 0.64, M['almohada']); bx((mid + 0.04, r[1], r[2], r[3]), 0.52, 0.64, M['almohada'])
        else:
            mid = (r[2] + r[3]) / 2; bx((r[0], r[1], r[2], mid - 0.04), 0.52, 0.64, M['almohada']); bx((r[0], r[1], mid + 0.04, r[3]), 0.52, 0.64, M['almohada'])
    else:
        bx(r, 0.52, 0.64, M['almohada'])

def nightstand(mb, x0, x1, y0, y1, z, lamp=True):
    mb.box(x0, x1, y0, y1, z, z + 0.48, M['madera_mueble'])
    if lamp:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        mb.cyl(cx, cy, 0.05, z + 0.48, z + 0.72, M['ceramica'], 16)
        mb.cyl(cx, cy, 0.12, z + 0.72, z + 0.90, M['almohada'], 20)

def wardrobe(mb, x0, x1, y0, y1, z, h, front, ndoors=2):
    mb.box(x0, x1, y0, y1, z, z + h, M['mueble_blanco'])
    if front in ('+y', '-y'):
        yf = y1 if front == '+y' else y0; s = 1 if front == '+y' else -1
        w = (x1 - x0) / ndoors
        for i in range(ndoors):
            a, b = x0 + i * w + 0.006, x0 + (i + 1) * w - 0.006
            mb.box(a, b, min(yf, yf + s * 0.018), max(yf, yf + s * 0.018), z + 0.02, z + h - 0.02, M['frente'])
            hx = b - 0.06 if i % 2 == 0 else a + 0.03
            mb.box(hx, hx + 0.03, min(yf, yf + s * 0.04), max(yf, yf + s * 0.04), z + 0.9, z + 1.25, M['metal'])
    else:
        xf_ = x1 if front == '+x' else x0; s = 1 if front == '+x' else -1
        w = (y1 - y0) / ndoors
        for i in range(ndoors):
            a, b = y0 + i * w + 0.006, y0 + (i + 1) * w - 0.006
            mb.box(min(xf_, xf_ + s * 0.018), max(xf_, xf_ + s * 0.018), a, b, z + 0.02, z + h - 0.02, M['frente'])
            hy = b - 0.06 if i % 2 == 0 else a + 0.03
            mb.box(min(xf_, xf_ + s * 0.04), max(xf_, xf_ + s * 0.04), hy, hy + 0.03, z + 0.9, z + 1.25, M['metal'])

def toilet(mb, wall_c, c, z, d):
    L = Local(wall_c, c, d)
    lbox(mb, L, 0.0, 0.18, -0.19, 0.19, z + 0.40, z + 0.80, M['ceramica'])
    lbox(mb, L, 0.12, 0.34, -0.12, 0.12, z, z + 0.38, M['ceramica'])
    x, y = L.pt(0.44, 0.0)
    mb.cyl(x, y, 0.19, z + 0.12, z + 0.40, M['ceramica'], 24)
    mb.cyl(x, y, 0.20, z + 0.40, z + 0.43, M['ceramica'], 24)

def basin(mb, wall_c, c, z, d, width=0.6):
    L = Local(wall_c, c, d); w = width / 2
    lbox(mb, L, 0.0, 0.45, -w, w, z + 0.12, z + 0.80, M['madera_mueble'])
    lbox(mb, L, 0.0, 0.47, -w, w, z + 0.80, z + 0.84, M['ceramica'])
    x, y = L.pt(0.27, 0.0); mb.cyl(x, y, 0.17, z + 0.84, z + 0.96, M['ceramica'], 24)
    lbox(mb, L, 0.03, 0.09, -0.015, 0.015, z + 0.84, z + 1.08, M['metal'])
    lbox(mb, L, 0.0, 0.02, -w * 0.9, w * 0.9, z + 1.10, z + 1.85, M['espejo'])

def shower(mb, x0, x1, y0, y1, z, glass):
    mb.box(x0, x1, y0, y1, z, z + 0.04, M['ceramica'])
    for g in glass: mb.box(*g, z + 0.04, z + 2.0, M['vidrio'])

def chair(mb, cx, cy, z, face):
    mb.box(cx - 0.21, cx + 0.21, cy - 0.21, cy + 0.21, z + 0.43, z + 0.47, M['madera_mueble'])
    for sx in (-0.18, 0.15):
        for sy in (-0.18, 0.15):
            mb.box(cx + sx, cx + sx + 0.03, cy + sy, cy + sy + 0.03, z, z + 0.43, M['madera_mueble'])
    back = {'+x': (cx - 0.21, cx - 0.18, cy - 0.21, cy + 0.21), '-x': (cx + 0.18, cx + 0.21, cy - 0.21, cy + 0.21),
            '+y': (cx - 0.21, cx + 0.21, cy - 0.21, cy - 0.18), '-y': (cx - 0.21, cx + 0.21, cy + 0.18, cy + 0.21)}[face]
    mb.box(*back, z + 0.47, z + 0.90, M['madera_mueble'])

# ================================================================= PLANTA BAJA
def planta_baja():
    z = LV["PB"]; W = M['pared_int']
    shell("PB", C_PB)
    slab("PB", C_PB, notch=False, name="PB Solera y suelo")
    t = MB()
    t.box(5.30, 5.40, ST_YU[0], 2.95, z, CLEAR, W)                                         # tabique lavadero (1.75)
    wall(t, (6.35, 2.10), (6.35, Y_N_IN), -0.05, 0.05, z, CLEAR, [(0.10, 0.85, z, 2.05)], W)  # tabique aseo con puerta
    t.box(6.30, 6.40, ST_YU[0], 2.10, z, 1.80, W)                                          # bajo la escalera
    t.box(ST_X0, ST_XW, 1.20, 1.28, z, LV["P1"], W)                                         # muro entre tramos
    t.build("PB Tabiques", C_PB)
    stair("PB", C_PB, solid=True)
    bath_floor("PB", [(6.40, X_IN, 2.10, Y_N_IN), (6.40, ST_XW, ST_YU[0], 2.10)], C_PB, "PB Suelo aseo")
    d = MB(); door_leaf(d, 6.40, 7.13, 2.91, 2.95, z); d.build("PB Puerta aseo", C_PB)

    # cocina lineal de 5.64 m
    k = MB()
    k.box(0.70, 1.30, 3.80, Y_N_IN, z, z + 2.05, M['electro'])                             # frigorífico
    k.box(0.72, 1.28, 3.78, 3.80, z + 1.2, z + 1.22, M['metal'])
    k.box(1.30, 6.30, 3.92, Y_N_IN, z, z + 0.10, M['negro'])                               # zócalo
    k.box(1.30, 6.30, 3.85, Y_N_IN, z + 0.10, z + 0.87, M['mueble_blanco'])
    x = 1.30
    while x < 6.29:
        xb = min(x + 0.60, 6.30)
        k.box(x + 0.004, xb - 0.004, 3.835, 3.85, z + 0.12, z + 0.85, M['frente'])
        x = xb
    k.box(1.30, 6.30, 3.80, Y_N_IN, z + 0.87, z + 0.91, M['encimera'])
    k.box(1.92, 2.42, 3.95, 4.32, z + 0.905, z + 0.915, M['metal'])                        # fregadero
    k.box(2.15, 2.19, 4.30, 4.36, z + 0.91, z + 1.20, M['metal'])
    k.box(3.38, 3.96, 3.92, 4.35, z + 0.91, z + 0.917, M['negro'])                         # placa
    for (cx, cy, r) in ((3.52, 4.03, 0.08), (3.52, 4.24, 0.07), (3.80, 4.13, 0.10)):
        k.cyl(cx, cy, r, z + 0.917, z + 0.919, M['metal'], 20)
    k.box(1.30, 3.25, 4.07, Y_N_IN, z + 1.45, z + 2.20, M['mueble_blanco'])                # altos
    k.box(4.10, 5.30, 4.07, Y_N_IN, z + 1.45, z + 2.20, M['mueble_blanco'])
    k.box(3.37, 3.97, 4.02, Y_N_IN, z + 1.55, z + 1.70, M['metal'])                        # campana
    k.box(3.52, 3.82, 4.17, Y_N_IN, z + 1.70, CLEAR, M['metal'])
    k.build("PB Cocina", C_PB)

    s = MB()
    s.box(0.95, 3.45, 0.85, 2.35, z, z + 0.012, M['alfombra'])
    s.box(1.31, 3.12, 1.94, 2.63, z + 0.06, z + 0.42, M['sofa'])                           # sofá mirando a la TV
    s.box(1.31, 3.12, 2.43, 2.63, z + 0.42, z + 0.85, M['sofa'])
    s.box(1.31, 1.49, 1.94, 2.43, z + 0.42, z + 0.62, M['sofa'])
    s.box(2.94, 3.12, 1.94, 2.43, z + 0.42, z + 0.62, M['sofa'])
    for i in range(3):
        a = 1.50 + i * 0.48
        s.box(a + 0.01, a + 0.47, 1.96, 2.42, z + 0.42, z + 0.52, M['sofa'])
    s.box(1.60, 1.95, 2.30, 2.42, z + 0.52, z + 0.82, M['cojin'])
    s.box(2.48, 2.83, 2.30, 2.42, z + 0.52, z + 0.82, M['cojin'])
    s.box(1.70, 2.75, 1.10, 1.50, z, z + 0.36, M['madera_mueble'])                         # mesa de centro
    s.box(1.65, 2.80, 1.05, 1.55, z + 0.36, z + 0.40, M['madera_mueble'])
    s.box(1.41, 3.25, 0.30, 0.70, z, z + 0.45, M['madera_mueble'])                         # mueble TV
    s.box(2.20, 2.50, 0.42, 0.55, z + 0.45, z + 0.48, M['negro'])
    s.box(1.75, 2.95, 0.46, 0.50, z + 0.55, z + 1.25, M['negro'])
    s.cyl(0.95, 0.75, 0.16, z, z + 0.40, M['ceramica'], 20)                               # maceta
    s.cyl(0.95, 0.75, 0.30, z + 0.40, z + 1.10, M['planta'], 12)
    s.build("PB Salón", C_PB)

    c = MB(); cx, cy = 4.40, 2.20
    c.cyl(cx, cy, 0.45, z + 0.72, z + 0.75, M['madera_mueble'], 40)
    c.cyl(cx, cy, 0.06, z + 0.03, z + 0.72, M['madera_mueble'], 16)
    c.cyl(cx, cy, 0.25, z, z + 0.03, M['madera_mueble'], 28)
    chair(c, cx - 0.62, cy, z, '+x'); chair(c, cx + 0.62, cy, z, '-x')
    chair(c, cx, cy - 0.62, z, '+y'); chair(c, cx, cy + 0.62, z, '-y')
    c.build("PB Comedor", C_PB)

    a = MB()
    toilet(a, X_IN, 3.35, z, '-x')
    basin(a, X_IN, 2.60, z, '-x', 0.55)
    a.build("PB Aseo", C_PB)

    l = MB()   # lavadora y secadora en columna, bajo la escalera
    for zb in (z + 0.0, z + 0.86):
        l.box(5.55, 6.15, 1.35, 1.95, zb, zb + 0.84, M['electro'])
        l.cyl_y(5.85, zb + 0.42, 0.20, 1.95, 1.97, M['vidrio'] if zb > 0.1 else M['metal'], 24)
    l.build("PB Lavadora y secadora", C_PB)

    area_light("PB Luz salón", C_PB, (2.3, 1.6, CLEAR - 0.02), 2.5, 1.8, 190)
    area_light("PB Luz cocina", C_PB, (3.6, 3.5, CLEAR - 0.02), 3.0, 0.8, 120)
    area_light("PB Luz comedor", C_PB, (4.4, 2.2, CLEAR - 0.02), 1.0, 1.0, 90)
    area_light("PB Luz aseo", C_PB, (7.0, 3.2, CLEAR - 0.02), 0.8, 0.8, 35)

    label("PB", "Salón-comedor-cocina\n23,00 m²", 3.05, 3.25, 0.19)
    label("PB", "Aseo\n3,65 m²", 6.80, 3.75, 0.13)
    label("PB", "Lavadero", 5.85, 2.50, 0.11)

# ================================================================= PLANTA PRIMERA
def planta_primera():
    z = LV["P1"]; zt = z + CLEAR; W = M['pared_int']
    shell("P1", C_P1)
    slab("P1", C_P1)
    t = MB()
    t.prism([(xf(2.24, FT) - 0.02, 2.24), (4.33, 2.24), (4.33, 2.33), (xf(2.33, FT) - 0.02, 2.33)], z, zt, W)   # entre dormitorios
    wall(t, (4.28, 1.35), (4.28, Y_N_IN), -0.05, 0.05, z, zt, [(0.07, 0.82, z, z + 2.03), (1.07, 1.80, z, z + 2.03)], W)
    t.box(3.63, 3.73, Y_S_IN, 1.35, z, zt, W)                     # armario del pasillo
    t.box(3.63, 4.33, 1.25, 1.35, z, zt, W)
    t.box(4.81, 4.91, 3.30, Y_N_IN, z, zt, W)                     # baño 1
    t.box(4.81, 5.30, 3.20, 3.30, z, zt, W)
    wall(t, (5.25, 2.20), (5.25, 3.20), -0.05, 0.05, z, zt, [(0.15, 0.90, z, z + 2.03)], W)
    t.box(5.20, X_IN, 2.10, 2.20, z, zt, W)
    t.box(ST_X0, ST_XW, 1.20, 1.28, z, LV["BC"], W)               # muro entre tramos
    t.build("P1 Tabiques", C_P1)
    stair("P1", C_P1, solid=False)
    bath_floor("P1", [(5.30, X_IN, 2.20, 3.30), (4.91, X_IN, 3.30, Y_N_IN)], C_P1, "P1 Suelo baño")
    d = MB()
    door_leaf(d, 3.50, 4.23, 2.42, 2.46, z)        # dormitorio 2
    door_leaf(d, 3.50, 4.23, 2.13, 2.17, z)        # dormitorio 3
    door_leaf(d, 5.30, 6.03, 3.06, 3.10, z)        # baño 1
    d.build("P1 Puertas", C_P1)

    f = MB()
    bed(f, 1.15, 3.05, 3.47, Y_N_IN, z, '+x', M['edredon1'])          # dormitorio 2 (cama 90)
    nightstand(f, 3.10, 3.50, 3.97, 4.40, z)
    bed(f, 1.15, 3.05, Y_S_IN, 1.20, z, '+x', M['edredon2'])          # dormitorio 3 (cama 90)
    nightstand(f, 3.10, 3.50, 0.27, 0.70, z)
    wardrobe(f, 3.73, 4.30, Y_S_IN, 1.25, z, 2.30, '+x')              # armario 0.60 x 1.00
    wardrobe(f, 4.33, 4.81, 3.22, Y_N_IN, z, 2.30, '-y', ndoors=1)    # armario 0.60 x 1.03
    f.build("P1 Dormitorios", C_P1)

    b = MB()
    shower(b, 6.40, X_IN, 3.72, Y_N_IN, z, [(6.40, 7.00, 3.70, 3.72)])
    b.cyl(7.30, 4.38, 0.012, z + 1.0, z + 2.0, M['metal'], 10)
    b.cyl(7.30, 4.30, 0.10, z + 2.0, z + 2.02, M['metal'], 20)
    toilet(b, X_IN, 2.70, z, '-x')
    basin(b, Y_N_IN, 5.95, z, '-y', 0.6)
    b.build("P1 Baño 1", C_P1)

    area_light("P1 Luz dormitorio 2", C_P1, (2.2, 3.35, zt - 0.02), 1.4, 1.0, 60)
    area_light("P1 Luz dormitorio 3", C_P1, (2.2, 1.25, zt - 0.02), 1.4, 1.0, 60)
    area_light("P1 Luz baño", C_P1, (6.3, 3.3, zt - 0.02), 1.0, 0.8, 45)
    area_light("P1 Luz pasillo", C_P1, (4.8, 1.8, zt - 0.02), 0.6, 1.2, 30)

    label("P1", "Dormitorio 2\n8,05 m²", 2.05, 2.90, 0.17)
    label("P1", "Dormitorio 3\n7,55 m²", 2.05, 1.70, 0.17)
    label("P1", "Baño 1\n5,50 m²", 6.25, 2.70, 0.15)
    label("P1", "Pasillo\n2,65 m²", 4.80, 1.45, 0.12, math.pi / 2)

# ================================================================= BAJOCUBIERTA
def bajo_cubierta():
    z = LV["BC"]; W = M['pared_int']
    zr = lambda x, y: z_under(x) + 0.02
    shell("BC", C_BC)
    slab("BC", C_BC)
    t = MB()
    wall(t, (1.53, Y_S_IN), (1.53, Y_N_IN), -0.05, 0.05, z, zr, [(0.75, 1.47, z, z + 1.90)], W)   # instalaciones
    t.box(4.28, 4.38, 2.10, Y_N_IN, z, zr, W)                                                    # baño 2
    wall(t, (4.28, 2.15), (6.10, 2.15), -0.05, 0.05, z, zr, [(0.17, 0.87, z, z + 2.0)], W)
    t.box(6.10, X_IN, 2.10, 2.20, z, zr, W)
    t.box(6.00, 6.10, 2.20, 3.70, z, zr, W)
    t.box(5.28, 6.10, 3.60, 3.70, z, zr, W)
    t.box(5.28, 5.38, 3.70, Y_N_IN, z, zr, W)
    t.build("BC Tabiques", C_BC)
    bath_floor("BC", [(4.38, 5.28, 2.20, Y_N_IN), (5.28, 6.00, 2.20, 3.60)], C_BC, "BC Suelo baño")

    r = MB()   # barandilla del hueco de escalera
    r.box(5.28, 5.30, Y_S_IN, 1.20, z, z + 1.0, M['vidrio'])
    r.box(5.26, 5.32, Y_S_IN, 1.24, z + 1.0, z + 1.04, M['metal'])
    r.box(5.30, ST_XW, 1.22, 1.26, z, z + 1.0, M['vidrio'])
    r.box(5.26, ST_XW, 1.21, 1.27, z + 1.0, z + 1.04, M['metal'])
    r.build("BC Barandilla escalera", C_BC)

    d = MB()
    door_leaf(d, 1.58, 2.28, 1.00, 1.04, z, 1.88)     # instalaciones
    door_leaf(d, 4.45, 4.49, 2.20, 2.90, z, 1.98)     # baño 2
    d.build("BC Puertas", C_BC)

    f = MB()
    bed(f, 2.10, 3.66, 2.42, Y_N_IN, z, '+y', M['edredon3'])      # cama de matrimonio
    nightstand(f, 1.65, 2.05, 4.00, 4.40, z)
    nightstand(f, 3.71, 4.11, 4.00, 4.40, z)
    wardrobe(f, 3.09, 5.17, Y_S_IN, 0.85, z, 2.10, '+y', ndoors=4)  # armario 2.00 x 0.60
    f.box(2.15, 2.75, 0.30, 0.85, z, z + 0.42, M['sofa'])          # butaca
    f.box(2.15, 2.75, 0.30, 0.45, z + 0.42, z + 0.80, M['sofa'])
    f.box(1.90, 3.90, 1.25, 2.30, z, z + 0.012, M['alfombra'])
    f.build("BC Dormitorio 1", C_BC)

    b = MB()
    shower(b, 4.42, 5.24, 3.62, 4.40, z, [(4.42, 4.95, 3.60, 3.62)])
    b.cyl(4.83, 4.38, 0.012, z + 1.0, z + 1.95, M['metal'], 10)
    b.cyl(4.83, 4.30, 0.09, z + 1.95, z + 1.97, M['metal'], 20)
    toilet(b, 6.00, 3.25, z, '-x')
    basin(b, 6.00, 2.62, z, '-x', 0.5)
    b.build("BC Baño 2", C_BC)

    i = MB()   # cuarto de instalaciones
    i.cyl(0.95, 3.55, 0.25, z, z + 1.40, M['electro'], 28)
    i.box(0.80, 1.40, 2.40, 2.80, z, z + 0.90, M['electro'])
    i.box(1.40, 1.48, 1.85, 2.20, z + 1.0, z + 1.50, M['marco'])
    i.build("BC Instalaciones", C_BC)

    area_light("BC Luz dormitorio", C_BC, (3.0, 1.9, z_under(3.0) - 0.05), 1.6, 1.4, 180)
    area_light("BC Luz baño", C_BC, (5.0, 2.9, z_under(5.0) - 0.05), 0.8, 0.8, 35)

    label("BC", "Dormitorio 1\n12,65 m²", 3.00, 1.70, 0.19)
    label("BC", "Baño 2\n2,90 m²", 4.85, 2.85, 0.13)
    label("BC", "Instalaciones\n3,85 m²", 1.05, 1.85, 0.12, math.pi / 2)

# ================================================================= CUBIERTA
SKY = [(0.97, 1.63), (2.84, 3.50)]      # velux sobre el dormitorio 1
SKY_X = (1.65, 2.75)

def cubierta():
    rule = lambda n: M['teja'] if n.z > 0.3 else (M['techo'] if n.z < -0.3 else M['canto'])
    mb = MB()
    Y0, Y1 = -0.10, Y_N_OUT + 0.10
    def piece(xa, xb, ya, yb):
        mb.xz_prism([(xa, z_under(xa)), (xb, z_under(xb)), (xb, z_top(xb)), (xa, z_top(xa))], ya, yb, rule)
    xs0, xs1 = SKY_X
    piece(-0.80, xs0, Y0, Y1); piece(xs1, RIDGE_X, Y0, Y1)
    ys = [Y0, SKY[0][0], SKY[0][1], SKY[1][0], SKY[1][1], Y1]
    for k in (0, 2, 4): piece(xs0, xs1, ys[k], ys[k + 1])
    piece(RIDGE_X, 7.86, Y0, Y1)
    mb.xz_prism([(3.36, z_top(3.36) - 0.01), (3.66, z_top(3.66) - 0.01), (3.66, z_top(3.66) + 0.03), (RIDGE_X, Z_RIDGE + 0.08), (3.36, z_top(3.36) + 0.03)], Y0, Y1, M['teja'])
    mb.build("Cubierta a dos aguas", C_ROOF)

    v, g = MB(), MB()
    def slope(xa, xb, d0, d1, ya, yb, m, tgt):
        tgt.xz_prism([(xa, z_top(xa) + d0), (xb, z_top(xb) + d0), (xb, z_top(xb) + d1), (xa, z_top(xa) + d1)], ya, yb, m)
    for (ya, yb) in SKY:
        slope(xs0 - 0.06, xs1 + 0.06, -0.02, 0.11, ya - 0.06, ya, M['marco'], v)
        slope(xs0 - 0.06, xs1 + 0.06, -0.02, 0.11, yb, yb + 0.06, M['marco'], v)
        slope(xs0 - 0.06, xs0, -0.02, 0.11, ya, yb, M['marco'], v)
        slope(xs1, xs1 + 0.06, -0.02, 0.11, ya, yb, M['marco'], v)
        slope(xs0, xs1, 0.07, 0.08, ya, yb, M['vidrio'], g)
    v.build("Ventanas de tejado", C_ROOF); g.build("Vidrios de tejado", C_ROOF)

    o = MB()   # canalón, bajante y chimeneas de ventilación
    ze = z_top(-0.80)
    o.box(-0.93, -0.80, Y0, Y1, ze - 0.30, ze - 0.16, M['marco'])
    o.box(-0.88, -0.02, 0.05, 0.13, ze - 0.36, ze - 0.28, M['marco'])
    o.box(-0.10, -0.02, 0.05, 0.13, 0.0, ze - 0.28, M['marco'])
    for cx in (7.22, 7.37, 7.52):
        o.cyl(cx, 4.27, 0.065, z_under(cx) - 0.05, 8.05, M['metal'], 16)
        o.cyl(cx, 4.27, 0.09, 8.05, 8.12, M['metal'], 16)
    o.build("Canalón y ventilaciones", C_ROOF)

# ================================================================= ENTORNO
def entorno():
    Ya, Yb = -16.0, 20.0
    s = MB()
    s.prism([(xf(Ya) - 1.6, Ya), (xf(Ya), Ya), (xf(Yb), Yb), (xf(Yb) - 1.6, Yb)], -0.15, 0.0, M['acera'])
    s.prism([(-14.0, Ya), (xf(Ya) - 1.6, Ya), (xf(Yb) - 1.6, Yb), (-14.0, Yb)], -0.35, -0.15, M['asfalto'])
    s.prism([(-15.6, Ya), (-14.0, Ya), (-14.0, Yb), (-15.6, Yb)], -0.15, 0.0, M['acera'])
    s.build("Calle y aceras", C_CALLE)
    p = MB()
    p.box(X_OUT, 8.40, -6.0, 11.0, 0.0, 5.60, M['piedra_muro'])
    p.build("Muro de piedra trasero", C_VEC)

    def neighbour(name, poly, h, wins):
        n = MB()
        n.prism(poly, 0.0, h, top_rule(M['vecino_cub'], M['vecino']))
        n.prism([(p[0] - 0.12 if i in (0, 3) else p[0], p[1]) for i, p in enumerate(poly)], h - 0.25, h, M['canto'])
        for (s0, s1, z0, z1) in wins:
            n.prism(fquad(s0, s1, -0.03, 0.0), z0, z1, M['ventana_vecino'])
            n.prism(fquad(s0 - 0.08, s1 + 0.08, -0.06, 0.0), z0 - 0.06, z0, M['canto'])
        n.build(name, C_VEC)
    L = FL
    neighbour("Colindante norte (h 5.80)", [(xf(Y_N_OUT), Y_N_OUT), (X_OUT, Y_N_OUT), (X_OUT, 11.0), (xf(11.0), 11.0)], 5.80,
              [(L + 1.0, L + 2.2, 0.0, 2.2), (L + 3.4, L + 4.6, 0.9, 2.2), (L + 1.0, L + 2.2, 3.3, 4.7), (L + 3.4, L + 4.6, 3.3, 4.7)])
    neighbour("Colindante sur (h 5.27)", [(xf(-6.0), -6.0), (X_OUT, -6.0), (X_OUT, 0.0), (xf(0.0), 0.0)], 5.27,
              [(-1.9, -0.8, 0.0, 2.2), (-4.6, -3.4, 0.9, 2.2), (-1.9, -0.8, 3.1, 4.4), (-4.6, -3.4, 3.1, 4.4)])
    r = MB()
    r.box(8.40, 14.0, -6.0, 11.0, 0.0, 5.60, top_rule(M['vecino_cub'], M['vecino']))
    r.build("Colindante trasero", C_VEC)

# ================================================================= cámaras, luz y render
def camera(name, loc, target=None, lens=28, ortho=None):
    cd = bpy.data.cameras.new(name); cd.clip_end = 300; cd.sensor_width = 36
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else: cd.lens = lens
    ob = bpy.data.objects.new(name, cd); ob.location = loc
    if target is not None:
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    C_CAM.objects.link(ob); return ob

def setup_render():
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try: scene.render.engine = eng; break
        except Exception: pass
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    try: scene.eevee.taa_render_samples = 48
    except Exception: pass
    try: scene.eevee.shadow_pool_size = '1024'
    except Exception: pass
    try: scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    w = bpy.data.worlds.new("Cielo"); scene.world = w
    try: w.use_nodes = True
    except Exception: pass
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (*srgb('#C4D3E0'), 1); bg.inputs['Strength'].default_value = 0.65
    try: scene.eevee.use_raytracing = True
    except Exception: pass
    sd = bpy.data.lights.new("Sol", 'SUN'); sd.energy = 4.5; sd.angle = math.radians(1.5)
    sd.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("Sol", sd)
    so.rotation_euler = Vector((0.55, 0.40, -0.75)).to_track_quat('-Z', 'Y').to_euler()
    C_CAM.objects.link(so)

    cx, cy = 3.9, 2.33
    scene.camera = camera("Cámara calle", (-12.5, -3.2, 1.70), (0.6, 2.5, 4.6), lens=24)
    camera("Cámara aérea", (-10.5, -9.5, 14.0), (3.6, 2.3, 3.6), lens=32)
    camera("Cámara interior salón", (0.85, 0.50, 1.65), (6.0, 3.4, 0.95), lens=15)
    camera("Cámara interior dormitorio 1", (4.95, 1.05, LV["BC"] + 1.60), (2.3, 3.6, LV["BC"] + 0.75), lens=16)
    fx, fy = F(FL / 2, -25.0)
    camera("Cámara alzado", (fx, fy, 4.6), (fx + FN.x, fy + FN.y, 4.6), ortho=13.0)
    for lv in ("PB", "P1", "BC"):
        z = LV[lv]
        camera(f"Cámara {lv} 3D", (2.9, -3.6, z + 11.0), (3.9, 2.3, z + 0.3), lens=26)
        camera(f"Cámara {lv} planta", (cx, cy, z + 25.0), None, ortho=9.2)

# ================================================================= construir
planta_baja()
planta_primera()
bajo_cubierta()
facade_carpentry()
cubierta()
entorno()
setup_render()

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GUARDADO", BLEND)
