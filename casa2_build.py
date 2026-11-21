# Casa de vacaciones, segunda versión (planos "PLANOS BARRO OCT 26").
# Uso: blender -b -P casa2_build.py -- <carpeta_salida> <A|B>
#   A = planta baja V.1 (despensa) + planta primera V.1 (sin terraza)
#   B = planta baja V.2 (sin despensa) + planta primera V.2 (galería/terraza)
#   Bajocubierta común, con casetón.
#
# Coordenadas (metros): X de la calle (0) al fondo (7.80); Y del colindante sur (0, lado 7.80)
# al norte (4.67, lado 7.42); Z altura (PB 0.00, P1 2.80, BC 5.60).

import bpy, bmesh, math, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
VAR = (argv[1] if len(argv) > 1 else "A").upper()
NAME = {"A": "Casa A - con despensa", "B": "Casa B - con terraza", "C": "Casa C - atico replanteado", "D": "Casa D - diseño final",
        "E": "Casa D - sin terraza"}[VAR]
# E = casa D con la planta primera V.1 (dormitorio con cristalera a la calle y baño en suite, sin galería)
# C = plantas baja y primera de la B + bajocubierta replanteada (2 dormitorios + baño) y escalera con altura libre.
# D = diseño final (planos "PLANOS casa.pdf"): base B con comedor movido, baño de P1 de un seno, galería y
#     bajocubierta del padre con casetón delantero y trasero; se mantienen los arreglos de altura libre.
# A partir de aquí VAR solo decide las plantas inferiores.
NEW_ATTIC = VAR == "C"
HOUSE_D = VAR in ("D", "E")
ASYM = VAR == "E"                           # tejado asimétrico (cumbrera retrasada) solo en la casa sin terraza
P1V = "A" if VAR == "E" else None          # planta primera: "A" (sin terraza) o "B" (galería)
if VAR in ("C", "D", "E"): VAR = "B"
P1V = P1V or VAR
BLEND = os.path.join(OUT_DIR, NAME + ".blend")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

# ---------------------------------------------------------------- cotas
RIDGE_X, SLOPE, Z_RIDGE, ROOF_T = 3.51, 0.45, 8.94, 0.33
SLOPE_F = SLOPE_R = SLOPE                   # pendiente del faldón delantero (calle) y trasero
EAVE_F = -0.80                              # vuelo del alero a la calle
if ASYM:
    # Según el croquis sobre la sección: la fachada sube hasta ~7,97, faldón largo y tendido (~8,5°) hasta la
    # cumbrera en x≈5,74 a ~8,81, y faldón corto y empinado hasta ~7,0 sobre el muro del fondo.
    RIDGE_X, Z_RIDGE, SLOPE_F, SLOPE_R, EAVE_F = 5.74, 8.81, 0.15, 1.03, -0.40
def z_top(x): return Z_RIDGE - (SLOPE_F * (RIDGE_X - x) if x < RIDGE_X else SLOPE_R * (x - RIDGE_X))
def z_under(x): return z_top(x) - ROOF_T

LV = {"PB": 0.0, "P1": 2.80, "BC": 5.60}
SLAB, CLEAR = 0.30, 2.50
X_OUT, X_IN = 7.80, 7.60
Y_N_OUT, Y_S_IN, Y_N_IN = 4.67, 0.25, 4.42
FA = Vector((0.0, 0.0)); FD = Vector((0.385, Y_N_OUT))
FL = (FD - FA).length; FU = (FD - FA) / FL; FN = Vector((FU.y, -FU.x))
FT = 0.30
def xf(y, d=0.0): return (d - FN.y * y) / FN.x
def F(s, d=0.0):
    p = FA + FU * s + FN * d
    return (p.x, p.y)
def fquad(s0, s1, d0, d1): return [F(s0, d0), F(s1, d0), F(s1, d1), F(s0, d1)]
def s_of_y(y): return y / FU.y      # posición a lo largo de la fachada para una y dada

# Escalera PB -> P1: recta, volada desde el muro norte, sube hacia el fondo
S1_X0, S1_N, S1_D, S1_R = 3.30, 13, 0.258, 0.20
S1_Y = (3.52, Y_N_IN)
# Hueco del forjado de P1 sobre la escalera. El plano lo dibuja de 5.40 a 6.65, pero así la escalera
# pasa bajo el forjado con ~0.90 m libres; se amplía hasta 3.80 para dar 2.00 m sobre cada peldaño.
HOLE1 = (3.80, 6.65)
GLASS_FLOOR = (5.40, 6.65, 1.25, 2.29)         # suelo de cristal en P1
# Escalera P1 -> BC: en U por el fondo y el lateral sur, peldaños volados
S2_R, S2_D = 0.20, 0.27
S2_XB = 6.70                                   # borde interior del tramo del fondo
S2_YS = 1.20                                   # borde interior del tramo sur
S2_Y0 = 2.60                                   # arranque del primer peldaño
BC_HOLE_Y = 1.89                               # hueco en BC: x 5.35..7.60, y 0.25..1.89

# Casetón (buhardilla) delantero
DY0, DY1 = (1.85, 4.20) if NEW_ATTIC else (1.05, 3.80) if HOUSE_D else (1.10, 3.68)   # en C se centra en el dormitorio 1
DYC = (DY0 + DY1) / 2
DR, DS, DT = 8.45, 0.54, 0.20                  # cumbrera, pendiente y grosor de su cubierta
def zd_top(y): return DR - DS * abs(y - DYC)
def zd_under(y): return zd_top(y) - DT
def valley_x(y): return RIDGE_X - (Z_RIDGE - zd_top(y)) / SLOPE

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

def basic(name, hexc, rough=0.6, metal=0.0, alpha=1.0, emit=0.0):
    m, nt, b = new_mat(name); c = srgb(hexc)
    b.inputs['Base Color'].default_value = (*c, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit > 0:
        b.inputs['Emission Color'].default_value = (*c, 1); b.inputs['Emission Strength'].default_value = emit
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

def remap(nt, vec, order):
    sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(vec, sp.inputs[0])
    cb = nt.nodes.new('ShaderNodeCombineXYZ')
    for dst, src in zip('XYZ', order): nt.links.new(sp.outputs[src], cb.inputs[dst])
    return cb.outputs[0]

def brick_mat(name, c1, c2, cm, width, height, mortar, offset, rough, order=None, bump=0.0, grain=0.0):
    m, nt, b = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vec = tc.outputs['Object']
    if order: vec = remap(nt, vec, order)
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

def stone_mat(name, scale, c0, c1, cm, edge=0.045, bump=0.9):
    m, nt, b = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'
    vo.inputs['Scale'].default_value = scale
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    vc = nt.nodes.new('ShaderNodeTexVoronoi'); vc.inputs['Scale'].default_value = scale
    nt.links.new(tc.outputs['Object'], vc.inputs['Vector'])
    mort = math_node(nt, 'LESS_THAN', vo.outputs['Distance'], edge)
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*srgb(c0), 1); ramp.color_ramp.elements[1].color = (*srgb(c1), 1)
    sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(vc.outputs['Color'], sp.inputs[0])
    nt.links.new(sp.outputs[0], ramp.inputs['Fac'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale * 8
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    col = mix(nt, ramp.outputs['Color'], nz.outputs['Fac'], 0.25, 'MULTIPLY')
    col = mix(nt, col, (*srgb(cm), 1), mort)
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.9
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump
    nt.links.new(math_node(nt, 'MINIMUM', vo.outputs['Distance'], 0.12), bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = (*srgb(c1), 1)
    return m

M = {
    'pared_int': basic('Pared interior', '#F1EEE8', 0.85),
    'techo': basic('Techo', '#F6F5F1', 0.9),
    'enfoscado': basic('Enfoscado exterior', '#E3DCD0', 0.9),
    'piedra_fachada': stone_mat('Fachada de piedra', 5.0, '#8C8274', '#D2C7B5', '#6B645B', 0.04, 0.6),
    'teja': brick_mat('Teja cerámica', '#B5543B', '#9E4630', '#5A281C', 0.24, 0.32, 0.018, 0.5, 0.7, order='YXZ', bump=0.5),
    'madera_ext': brick_mat('Madera exterior', '#7A5434', '#6B482C', '#3E2A1A', 2.4, 0.15, 0.004, 0.3, 0.6, order='YZX', grain=0.35),
    'madera_techo': brick_mat('Madera techo casetón', '#C49A6C', '#B58A5C', '#7E5B3B', 2.4, 0.12, 0.003, 0.3, 0.6, order='XYZ', grain=0.3),
    'canto': basic('Canto', '#DAD7D1', 0.8),
    'parquet': brick_mat('Suelo madera', '#BC8E61', '#AA7C51', '#7A5638', 1.2, 0.19, 0.003, 0.37, 0.45, grain=0.35),
    'tarima_ext': brick_mat('Tarima terraza', '#8A6544', '#7D5A3B', '#4A3523', 1.8, 0.14, 0.006, 0.5, 0.6, grain=0.3),
    'baldosa': brick_mat('Suelo porcelánico', '#D9D3C9', '#D0C9BE', '#A9A398', 0.6, 0.6, 0.004, 0.0, 0.35),
    'baldosa_bano': brick_mat('Suelo baño', '#CBD3D6', '#C1CACD', '#99A3A7', 0.3, 0.3, 0.004, 0.0, 0.3),
    'marco': basic('Carpintería negra', '#25272A', 0.4, 0.3),
    'vidrio': basic('Vidrio', '#BFD8E2', 0.05, alpha=0.18),
    'vidrio_suelo': basic('Suelo de vidrio', '#CFE3E8', 0.05, alpha=0.35),
    'vidrio_mate': basic('Vidrio mate baño', '#E8EEF0', 0.4, alpha=0.75),
    'puerta_ext': brick_mat('Puerta de entrada madera', '#8A5E36', '#7E5531', '#4F351F', 0.14, 3.0, 0.004, 0.0, 0.5, order='YZX', grain=0.3),
    'puerta_int': basic('Puertas interiores', '#EDE9E2', 0.5),
    'escalera': basic('Peldaños de roble', '#B98C5A', 0.45),
    'piedra_muro': stone_mat('Muro de mampostería', 3.2, '#6E665C', '#B3A794', '#3F3B36'),
    'mueble_blanco': basic('Mueble blanco', '#F4F2EE', 0.4),
    'frente': basic('Frentes de mueble', '#E8E4DC', 0.35),
    'cocina': basic('Muebles de cocina azul marino', '#1C2B45', 0.45),
    'cocina_frente': basic('Frentes de cocina azul marino', '#24375A', 0.35),
    'madera_mueble': basic('Madera mueble', '#9C7552', 0.5),
    'listones': basic('Listones separador', '#A87C52', 0.5),
    'encimera': basic('Encimera', '#3A3A3C', 0.3),
    'metal': basic('Acero', '#B9BCBF', 0.25, 1.0),
    'negro': basic('Negro', '#151515', 0.2),
    'sofa': basic('Tela sofá', '#8C8F86', 0.9),
    'cojin': basic('Cojines', '#C9874E', 0.9),
    'alfombra': basic('Alfombra', '#D9CBB2', 1.0),
    'ceramica': basic('Cerámica', '#FAFAFA', 0.15),
    'colchon': basic('Ropa de cama', '#F3F1EC', 0.9),
    'almohada': basic('Almohada', '#FFFFFF', 0.9),
    'edredon1': basic('Edredón terracota', '#C0704F', 0.9),
    'edredon2': basic('Edredón verde', '#7E8F6A', 0.9),
    'edredon3': basic('Edredón azul', '#5E7FA0', 0.9),
    'espejo': basic('Espejo', '#DDE6EA', 0.02, 1.0),
    'vecino': basic('Edificio colindante', '#D9D4CC', 0.9),
    'vecino_cub': basic('Cubierta colindante', '#9C5A44', 0.9),
    'ventana_vecino': basic('Ventanas colindantes', '#3B4650', 0.2),
    'acera': brick_mat('Acera', '#B9B6B0', '#AEAAA3', '#8F8B85', 0.4, 0.4, 0.004, 0.0, 0.7),
    'asfalto': basic('Asfalto', '#4A4C4F', 0.9),
    'texto': basic('Rótulos', '#2B2B2B', 0.8),
    'electro': basic('Electrodoméstico', '#E9EAEC', 0.3),
    'inox': basic('Frigorífico inox', '#C7C9CB', 0.3, 0.8),
    'planta': basic('Plantas', '#5C7A45', 0.8),
    'radiador': basic('Radiador', '#F2F2F2', 0.4),
    'difusor': basic('Difusor solatube', '#FFF8EC', 0.3, emit=6.0),
}

# ---------------------------------------------------------------- mallas
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

def zval(z, x, y): return z(x, y) if callable(z) else z

class MB:
    def __init__(self): self.v, self.f, self.r = [], [], []
    def _face(self, idx, rule): self.f.append(idx); self.r.append(rule)

    def prism(self, poly, z0, ztop, rule, split=True):
        poly = [tuple(p) for p in poly]
        if split and (callable(ztop) or callable(z0)):
            xs = [p[0] for p in poly]
            if min(xs) < RIDGE_X - 1e-6 and max(xs) > RIDGE_X + 1e-6:
                for part in (clip(poly, RIDGE_X, True), clip(poly, RIDGE_X, False)):
                    if len(part) >= 3: self.prism(part, z0, ztop, rule, split)
                return
        n = len(poly)
        area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
        if abs(area) < 1e-9: return
        if area < 0: poly.reverse()
        b = len(self.v)
        for x, y in poly: self.v.append((x, y, zval(z0, x, y)))
        for x, y in poly: self.v.append((x, y, zval(ztop, x, y)))
        self._face([b + i for i in reversed(range(n))], rule)
        self._face([b + n + i for i in range(n)], rule)
        for i in range(n):
            j = (i + 1) % n; self._face([b + i, b + j, b + n + j, b + n + i], rule)

    def box(self, x0, x1, y0, y1, z0, z1, rule):
        self.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, rule)

    def _extrude(self, pts0, pts1, rule):
        b = len(self.v); n = len(pts0)
        self.v.extend(pts0); self.v.extend(pts1)
        self._face([b + i for i in range(n)], rule)
        self._face([b + n + i for i in reversed(range(n))], rule)
        for i in range(n):
            j = (i + 1) % n; self._face([b + i, b + j, b + n + j, b + n + i], rule)

    def xz_prism(self, prof, y0, y1, rule):
        self._extrude([(x, y0, z) for x, z in prof], [(x, y1, z) for x, z in prof], rule)
    def yz_prism(self, prof, x0, x1, rule):
        self._extrude([(x0, y, z) for y, z in prof], [(x1, y, z) for y, z in prof], rule)
    def sz_prism(self, prof, d0, d1, rule):
        """Perfil (s, z) sobre el plano de fachada, extruido en profundidad d0..d1."""
        self._extrude([(*F(s, d0), z) for s, z in prof], [(*F(s, d1), z) for s, z in prof], rule)

    def cyl(self, cx, cy, r, z0, z1, rule, seg=28):
        self.prism([(cx + r * math.cos(2 * math.pi * k / seg), cy + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], z0, z1, rule)
    def cyl_y(self, cx, cz, r, y0, y1, rule, seg=28):
        self.xz_prism([(cx + r * math.cos(2 * math.pi * k / seg), cz + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], y0, y1, rule)
    def cyl_x(self, cy, cz, r, x0, x1, rule, seg=28):
        self.yz_prism([(cy + r * math.cos(2 * math.pi * k / seg), cz + r * math.sin(2 * math.pi * k / seg)) for k in range(seg)], x0, x1, rule)

    def ellipsoid(self, c, r, rule, seg=16, rings=10):
        b = len(self.v); cx, cy, cz = c; rx, ry, rz = r
        self.v.append((cx, cy, cz - rz))
        for i in range(1, rings):
            th = math.pi * i / rings
            for k in range(seg):
                ph = 2 * math.pi * k / seg
                self.v.append((cx + rx * math.sin(th) * math.cos(ph), cy + ry * math.sin(th) * math.sin(ph), cz - rz * math.cos(th)))
        top = len(self.v); self.v.append((cx, cy, cz + rz))
        ring = lambda i, k: b + 1 + (i - 1) * seg + (k % seg)
        for k in range(seg): self._face([b, ring(1, k + 1), ring(1, k)], rule)
        for i in range(1, rings - 1):
            for k in range(seg): self._face([ring(i, k), ring(i, k + 1), ring(i + 1, k + 1), ring(i + 1, k)], rule)
        for k in range(seg): self._face([ring(rings - 1, k), ring(rings - 1, k + 1), top], rule)

    def frustum(self, cx, cy, z0, z1, r0, r1, rule, seg=14):
        b = len(self.v)
        for (z, r) in ((z0, r0), (z1, r1)):
            for k in range(seg):
                a = 2 * math.pi * k / seg; self.v.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        self._face([b + k for k in reversed(range(seg))], rule)
        self._face([b + seg + k for k in range(seg)], rule)
        for k in range(seg):
            j = (k + 1) % seg; self._face([b + k, b + j, b + seg + j, b + seg + k], rule)

    def merge(self, other, fn):
        off = len(self.v)
        self.v.extend(fn(*p) for p in other.v)
        for f, r in zip(other.f, other.r): self._face([i + off for i in f], r)

    def build(self, name, coll, first=()):
        if not self.f: return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        bm = bmesh.new(); bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        mats = list(first)
        for f in bm.faces:
            rule = self.r[f.index]
            m = rule(f.normal) if callable(rule) else rule
            if m not in mats: mats.append(m)
            f.material_index = mats.index(m)
        bm.to_mesh(me); bm.free()
        for m in mats: me.materials.append(m)
        ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
        return ob

def boolean_cut(obj, cutter_mb):
    cutter = cutter_mb.build("_corte", scene.collection)
    mod = obj.modifiers.new("corte", 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.object = cutter
    try: mod.solver = 'EXACT'
    except Exception: pass
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear(); old = obj.data; obj.data = me; bpy.data.meshes.remove(old)
    cme = cutter.data; bpy.data.objects.remove(cutter); bpy.data.meshes.remove(cme)

def ext_rule(ext, inner, d):
    dv = Vector((d[0], d[1], 0.0)).normalized()
    return lambda n: ext if n.dot(dv) > 0.7 else inner
def top_rule(top, other, bottom=None):
    return lambda n: top if n.z > 0.5 else (bottom if (bottom is not None and n.z < -0.5) else other)

def wall(mb, P, Q, d0, d1, z0, ztop, openings, rule):
    P = Vector(P); Q = Vector(Q); L = (Q - P).length; u = (Q - P) / L; n = Vector((u.y, -u.x))
    def quad(s0, s1): return [tuple(P + u * s0 + n * d0), tuple(P + u * s1 + n * d0), tuple(P + u * s1 + n * d1), tuple(P + u * s0 + n * d1)]
    s = 0.0
    for (s0, s1, zb, zt) in sorted(openings):
        if s0 > s + 1e-6: mb.prism(quad(s, s0), z0, ztop, rule)
        if zb > z0 + 1e-6: mb.prism(quad(s0, s1), z0, zb, rule)
        if zt is not None: mb.prism(quad(s0, s1), zt, ztop, rule)
        s = s1
    if s < L - 1e-6: mb.prism(quad(s, L), z0, ztop, rule)

class Local:
    def __init__(self, wall, c, d): self.w, self.c, self.d = wall, c, d
    def pt(self, a, b):
        w, c, d = self.w, self.c, self.d
        return {'+x': (w + a, c + b), '-x': (w - a, c - b), '+y': (c - b, w + a), '-y': (c + b, w - a)}[d]
    def rect(self, a0, a1, b0, b1):
        p, q = self.pt(a0, b0), self.pt(a1, b1)
        return (min(p[0], q[0]), max(p[0], q[0]), min(p[1], q[1]), max(p[1], q[1]))
def lbox(mb, L, a0, a1, b0, b1, z0, z1, mat):
    x0, x1, y0, y1 = L.rect(a0, a1, b0, b1); mb.box(x0, x1, y0, y1, z0, z1, mat)

# ---------------------------------------------------------------- colecciones y utilidades
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
C_VEC = new_coll("Edificios colindantes", C_ENT)
C_CAM = new_coll("Cámaras y luces")

def label(level, text, x, y, size=0.18, rot=0.0):
    cu = bpy.data.curves.new("Rótulo", 'FONT')
    cu.body = text; cu.size = size; cu.align_x = 'CENTER'; cu.align_y = 'CENTER'; cu.space_line = 0.9
    cu.materials.append(M['texto'])
    ob = bpy.data.objects.new("Rótulo " + text.split("\n")[0], cu)
    ob.location = (x, y, LV[level] + 0.03); ob.rotation_euler = (0, 0, rot)
    C_LBL[level].objects.link(ob)

def area_light(name, coll, loc, sx, sy, watts, color=(1.0, 0.9, 0.78)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = sx; ld.size_y = sy
    ld.energy = watts; ld.color = color
    try: ld.use_shadow = False
    except Exception: pass
    ob = bpy.data.objects.new(name, ld); ob.location = loc; coll.objects.link(ob)
    ob["interior"] = 1

def door_leaf(mb, x0, x1, y0, y1, z, h=2.03): mb.box(x0, x1, y0, y1, z, z + h, M['puerta_int'])

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

def basin(mb, wall_c, c, z, d, width=0.6, sinks=1):
    L = Local(wall_c, c, d); w = width / 2
    lbox(mb, L, 0.0, 0.45, -w, w, z + 0.12, z + 0.80, M['madera_mueble'])
    lbox(mb, L, 0.0, 0.47, -w, w, z + 0.80, z + 0.84, M['ceramica'])
    for k in range(sinks):
        b = -w + width * (k + 0.5) / sinks
        x, y = L.pt(0.27, b); mb.cyl(x, y, 0.17, z + 0.84, z + 0.96, M['ceramica'], 24)
        lbox(mb, L, 0.03, 0.09, b - 0.015, b + 0.015, z + 0.84, z + 1.08, M['metal'])
    lbox(mb, L, 0.0, 0.02, -w * 0.92, w * 0.92, z + 1.10, z + 1.85, M['espejo'])

def shower(mb, x0, x1, y0, y1, z, glass, head):
    mb.box(x0, x1, y0, y1, z, z + 0.04, M['ceramica'])
    for g in glass: mb.box(*g, z + 0.04, z + 2.0, M['vidrio'])
    hx, hy = head
    mb.cyl(hx, hy, 0.012, z + 1.0, z + 2.0, M['metal'], 10)
    mb.cyl(hx, hy, 0.10, z + 2.0, z + 2.02, M['metal'], 20)

def chair(mb, cx, cy, z, face):
    mb.box(cx - 0.21, cx + 0.21, cy - 0.21, cy + 0.21, z + 0.43, z + 0.47, M['madera_mueble'])
    for sx in (-0.18, 0.15):
        for sy in (-0.18, 0.15):
            mb.box(cx + sx, cx + sx + 0.03, cy + sy, cy + sy + 0.03, z, z + 0.43, M['madera_mueble'])
    back = {'+x': (cx - 0.21, cx - 0.18, cy - 0.21, cy + 0.21), '-x': (cx + 0.18, cx + 0.21, cy - 0.21, cy + 0.21),
            '+y': (cx - 0.21, cx + 0.21, cy - 0.21, cy - 0.18), '-y': (cx - 0.21, cx + 0.21, cy + 0.18, cy + 0.21)}[face]
    mb.box(*back, z + 0.47, z + 0.90, M['madera_mueble'])

# ---------------------------------------------------------------- personas de referencia
PIEL = [basic(f'Piel {i + 1}', h, 0.6) for i, h in enumerate(('#E6B796', '#C99572', '#F0C8A8', '#A8714F'))]
ROPA = [basic(f'Ropa {i + 1}', h, 0.85) for i, h in enumerate(('#3E6E8E', '#B8483A', '#E2C25B', '#5F7F5A', '#E8E4DC', '#7A4E7E', '#D98C5F', '#4E5D6C'))]
PANT = [basic(f'Pantalón {i + 1}', h, 0.85) for i, h in enumerate(('#2F3A4F', '#C8B79A', '#3A3A3A', '#6B5A48'))]
PELO = [basic(f'Pelo {i + 1}', h, 0.7) for i, h in enumerate(('#3B2A1E', '#1E1A17', '#8A6A44', '#B9B2A8'))]
ZAP = basic('Zapatos', '#2A2622', 0.5)
_pid = [0]

def person(mb, x, y, z, ang, sex):
    """Figura de pie: hombre 1.75 m / mujer 1.63 m. ang = hacia dónde mira, en grados (0 = +X)."""
    i = _pid[0]; _pid[0] += 1
    s = (1.75 if sex == 'h' else 1.63) / 1.75
    skin, top, bot, hair = PIEL[i % 4], ROPA[(i * 3) % 8], PANT[(i * 5 + 1) % 4], PELO[(i * 7) % 4]
    p = MB()
    for sy in (-0.095, 0.095):
        p.box(-0.06 * s, 0.20 * s, (sy - 0.05) * s, (sy + 0.05) * s, 0.0, 0.07 * s, ZAP)
        p.frustum(0.0, sy * s, 0.07 * s, 0.90 * s, 0.050 * s, 0.078 * s, bot)
    p.ellipsoid((0, 0, 0.93 * s), (0.11 * s, 0.17 * s, 0.12 * s), bot)
    p.ellipsoid((0, 0, 1.20 * s), (0.12 * s, 0.19 * s, 0.30 * s), top)
    for sy in (-0.225, 0.225):
        p.frustum(0.0, sy * s, 0.80 * s, 1.42 * s, 0.038 * s, 0.052 * s, top)
        p.ellipsoid((0, sy * s, 0.77 * s), (0.04 * s, 0.035 * s, 0.06 * s), skin)
    p.frustum(0, 0, 1.42 * s, 1.53 * s, 0.05 * s, 0.05 * s, skin)
    p.ellipsoid((0, 0, 1.625 * s), (0.105 * s, 0.085 * s, 0.12 * s), skin)
    if sex == 'h': p.ellipsoid((-0.015 * s, 0, 1.665 * s), (0.10 * s, 0.089 * s, 0.092 * s), hair)
    else: p.ellipsoid((-0.03 * s, 0, 1.60 * s), (0.10 * s, 0.093 * s, 0.16 * s), hair)
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    mb.merge(p, lambda px, py, pz: (x + px * ca - py * sa, y + px * sa + py * ca, z + pz))

def personas():
    """Dos personas por estancia (sin despensa, aseos ni baños). En las casas D, una por planta."""
    pb, p1, bc = MB(), MB(), MB()
    z1, z2 = LV["P1"], LV["BC"]
    if HOUSE_D:
        person(pb, 1.45, 2.50, 0.0, 25, 'h')                                     # salón
        if P1V == "A": person(p1, 1.10, 2.05, z1, 10, 'm')                       # dormitorio principal
        else: person(p1, 1.85, 2.58, z1, 0, 'm')
        person(bc, 2.30, 1.50, z2, 180, 'h')                                     # dormitorio delantero
        pb.build("PB Personas de referencia", C_PB); p1.build("P1 Personas de referencia", C_P1); bc.build("BC Personas de referencia", C_BC)
        return
    # salón
    person(pb, 1.45, 2.50, 0.0, 25, 'h'); person(pb, 2.30, 2.88, 0.0, 205, 'm')
    # cocina-comedor
    if VAR == "A":
        person(pb, 4.25, 1.40, 0.0, -90, 'm'); person(pb, 5.38, 1.55, 0.0, 200, 'h')
    else:
        person(pb, 6.05, 1.38, 0.0, -90, 'm'); person(pb, 6.15, 2.35, 0.0, 250, 'h')
    # dormitorio principal (+ galería en B)
    if P1V == "A":
        person(p1, 1.10, 2.05, z1, 10, 'm'); person(p1, 3.75, 1.98, z1, 175, 'h')
    else:
        person(p1, 1.85, 2.58, z1, 0, 'm'); person(p1, 3.45, 2.62, z1, 180, 'h')
        person(p1, 0.85, 3.30, z1, 190, 'h'); person(p1, 0.85, 0.60, z1, 165, 'm')
    # bajocubierta: dormitorio del casetón y dormitorio trasero (donde hay altura)
    if NEW_ATTIC:
        person(bc, 0.95, 2.90, z2, -20, 'm'); person(bc, 1.10, 2.12, z2, 50, 'h')
        person(bc, 4.35, 2.10, z2, 20, 'h'); person(bc, 5.00, 2.22, z2, 200, 'm')
    elif HOUSE_D:
        person(bc, 2.30, 1.50, z2, 180, 'h'); person(bc, 1.45, 1.65, z2, 0, 'm')
        person(bc, 4.80, 2.08, z2, 20, 'm'); person(bc, 5.28, 2.18, z2, 190, 'h')
    else:
        person(bc, 2.30, 1.45, z2, 180, 'h'); person(bc, 1.45, 1.62, z2, 0, 'm')
        person(bc, 5.55, 2.62, z2, 60, 'm'); person(bc, 5.65, 3.40, z2, -110, 'h')
    pb.build("PB Personas de referencia", C_PB); p1.build("P1 Personas de referencia", C_P1); bc.build("BC Personas de referencia", C_BC)

def radiator(mb, x0, x1, y0, y1, z):
    mb.box(x0, x1, y0, y1, z + 0.15, z + 0.75, M['radiador'])

def counter(mb, x0, x1, y0, y1, front, z=0.0):
    """Bancada baja de cocina. front = lado de las puertas."""
    mb.box(x0, x1, y0, y1, z + 0.87, z + 0.91, M['encimera'])
    ix0, ix1, iy0, iy1 = x0, x1, y0, y1
    if front == '+y': iy1 -= 0.03
    elif front == '-y': iy0 += 0.03
    elif front == '+x': ix1 -= 0.03
    else: ix0 += 0.03
    mb.box(ix0, ix1, iy0, iy1, z + 0.10, z + 0.87, M['cocina'])
    pl = {'+y': (ix0, ix1, iy0, iy1 - 0.06), '-y': (ix0, ix1, iy0 + 0.06, iy1), '+x': (ix0, ix1 - 0.06, iy0, iy1), '-x': (ix0 + 0.06, ix1, iy0, iy1)}[front]
    mb.box(*pl, z, z + 0.10, M['negro'])
    if front in ('+y', '-y'):
        yf = iy1 if front == '+y' else iy0; s = 1 if front == '+y' else -1
        x = ix0
        while x < ix1 - 0.05:
            xb = min(x + 0.60, ix1)
            mb.box(x + 0.004, xb - 0.004, min(yf, yf + s * 0.015), max(yf, yf + s * 0.015), z + 0.12, z + 0.85, M['cocina_frente'])
            xc = (x + xb) / 2
            mb.box(xc - 0.09, xc + 0.09, min(yf, yf + s * 0.035), max(yf, yf + s * 0.035), z + 0.78, z + 0.80, M['metal'])
            x = xb
    else:
        xfr = ix1 if front == '+x' else ix0; s = 1 if front == '+x' else -1
        y = iy0
        while y < iy1 - 0.05:
            yb = min(y + 0.60, iy1)
            mb.box(min(xfr, xfr + s * 0.015), max(xfr, xfr + s * 0.015), y + 0.004, yb - 0.004, z + 0.12, z + 0.85, M['cocina_frente'])
            yc = (y + yb) / 2
            mb.box(min(xfr, xfr + s * 0.035), max(xfr, xfr + s * 0.035), yc - 0.09, yc + 0.09, z + 0.78, z + 0.80, M['metal'])
            y = yb

def wall_cab(mb, x0, x1, y0, y1, front, za=1.50, zb=2.20):
    """Armario alto de cocina, azul marino, con frentes de 60 cm."""
    mb.box(x0, x1, y0, y1, za, zb, M['cocina'])
    if front in ('+y', '-y'):
        yf = y1 if front == '+y' else y0; s = 1 if front == '+y' else -1
        x = x0
        while x < x1 - 0.05:
            xb = min(x + 0.60, x1)
            mb.box(x + 0.004, xb - 0.004, min(yf, yf + s * 0.015), max(yf, yf + s * 0.015), za + 0.01, zb - 0.01, M['cocina_frente'])
            x = xb
    else:
        xfr = x1 if front == '+x' else x0; s = 1 if front == '+x' else -1
        y = y0
        while y < y1 - 0.05:
            yb = min(y + 0.60, y1)
            mb.box(min(xfr, xfr + s * 0.015), max(xfr, xfr + s * 0.015), y + 0.004, yb - 0.004, za + 0.01, zb - 0.01, M['cocina_frente'])
            y = yb

def sink(mb, x0, x1, y0, y1, z=0.0):
    mb.box(x0, x1, y0, y1, z + 0.905, z + 0.915, M['metal'])
def hob(mb, x0, x1, y0, y1, z=0.0):
    mb.box(x0, x1, y0, y1, z + 0.91, z + 0.917, M['negro'])

# ---------------------------------------------------------------- envolvente
def roof_cut(x, y): return z_under(x) + 0.12
FACADE_OPEN = {
    "PB": [(0.60, 2.00, 1.00, 2.45), (2.70, 3.60, 0.00, 2.30)],
    "P1A": [(0.60, 1.30, 3.85, 4.95), (1.75, 3.60, 2.80, 5.30)],
    "P1B": [(0.60, 3.60, 2.80, 5.30)],
}
S_D0, S_D1 = s_of_y(DY0), s_of_y(DY1)
BC_W0, BC_W1, BC_WZ = s_of_y(1.30), s_of_y(3.55), (LV["BC"] + 0.45, 7.45)   # ventanal de bajocubierta (tejado asimétrico)

def shell(level, coll):
    z0 = LV[level]
    ztop = {"PB": LV["P1"], "P1": LV["BC"], "BC": roof_cut}[level]
    mb = MB()
    fr = ext_rule(M['piedra_fachada'], M['pared_int'], (-FN.x, -FN.y))
    if level == "BC":
        if ASYM:   # fachada alta con ventanal en vez de casetón
            wall(mb, FA, FD, 0.0, FT, z0, ztop, [(BC_W0, BC_W1, BC_WZ[0], BC_WZ[1])], fr)
        else:
            wall(mb, FA, FD, 0.0, FT, z0, ztop, [(S_D0, S_D1, z0, None)], fr)
    else:
        key = "PB" if level == "PB" else "P1" + P1V
        wall(mb, FA, FD, 0.0, FT, z0, ztop, FACADE_OPEN[key], fr)
    mb.prism([(0.10, 0.0), (X_OUT, 0.0), (X_OUT, Y_S_IN), (0.10, Y_S_IN)], z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (0, -1)))
    mb.prism([(0.45, Y_N_IN), (X_OUT, Y_N_IN), (X_OUT, Y_N_OUT), (0.45, Y_N_OUT)], z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (0, 1)))
    mb.box(X_IN, X_OUT, Y_S_IN, Y_N_IN, z0, ztop, ext_rule(M['enfoscado'], M['pared_int'], (1, 0)))
    mb.build(f"{level} Muros exteriores", coll)

def slab(level, coll, rects_after_front, xcut, floor_mat, name):
    """Forjado: banda delantera (con fachada inclinada) hasta xcut, más rectángulos detrás."""
    z1 = LV[level]; z0 = z1 - SLAB; e = 0.02
    ys, yn = Y_S_IN - e, Y_N_IN + e
    mb = MB(); r = top_rule(floor_mat, M['techo'], M['techo'])
    mb.prism([(xf(ys, FT) - e, ys), (xcut, ys), (xcut, yn), (xf(yn, FT) - e, yn)], z0, z1, r)
    for (x0, x1, y0, y1) in rects_after_front:
        mb.box(x0, x1, max(y0, ys), min(y1, yn), z0, z1, r)
    mb.build(name, coll)

def bath_floor(level, rects, coll, name):
    mb = MB(); z = LV[level]
    for (x0, x1, y0, y1) in rects: mb.box(x0, x1, y0, y1, z, z + 0.006, M['baldosa_bano'])
    mb.build(name, coll)

# ---------------------------------------------------------------- carpinterías
def glazing(mbf, mbg, s0, s1, zb, zt, panes=2, f=0.06, d=(0.05, 0.12), glass=None, sill=False):
    g = glass or M['vidrio']
    mbf.prism(fquad(s0, s0 + f, *d), zb, zt, M['marco'])
    mbf.prism(fquad(s1 - f, s1, *d), zb, zt, M['marco'])
    mbf.prism(fquad(s0 + f, s1 - f, *d), zb, zb + f, M['marco'])
    mbf.prism(fquad(s0 + f, s1 - f, *d), zt - f, zt, M['marco'])
    for k in range(1, panes):
        sm = s0 + (s1 - s0) * k / panes
        mbf.prism(fquad(sm - 0.03, sm + 0.03, *d), zb + f, zt - f, M['marco'])
    mbg.prism(fquad(s0 + f, s1 - f, 0.08, 0.09), zb + f, zt - f, g)
    if sill:
        mbf.prism(fquad(s0 - 0.05, s1 + 0.05, -0.05, 0.05), zb - 0.04, zb, M['canto'])

def glass_rail(mbf, mbg, s0, s1, z):
    mbg.prism(fquad(s0 + 0.03, s1 - 0.03, -0.05, -0.035), z + 0.06, z + 1.0, M['vidrio'])
    mbf.prism(fquad(s0, s1, -0.065, -0.025), z + 1.0, z + 1.04, M['marco'])
    mbf.prism(fquad(s0, s0 + 0.04, -0.065, 0.0), z, z + 1.04, M['marco'])
    mbf.prism(fquad(s1 - 0.04, s1, -0.065, 0.0), z, z + 1.04, M['marco'])

def facade_carpentry():
    f, g = MB(), MB()
    # Planta baja: puerta de madera y cristalera sobre murete de 1 m hasta el techo
    f.prism(fquad(0.0, 2.70, -0.03, 0.0), 0.0, 0.25, M['canto'])                # zócalo
    f.prism(fquad(3.60, FL, -0.03, 0.0), 0.0, 0.25, M['canto'])
    glazing(f, g, 0.60, 2.00, 1.00, 2.45, panes=2, sill=True)
    for (a, b) in ((2.70, 2.76), (3.54, 3.60)): f.prism(fquad(a, b, 0.05, 0.12), 0.0, 2.30, M['marco'])
    f.prism(fquad(2.76, 3.54, 0.05, 0.12), 2.24, 2.30, M['marco'])
    if not HOUSE_D:   # en D la puerta queda abierta (hoja girada hacia dentro) para poder entrar en la visita virtual
        f.prism(fquad(2.76, 3.54, 0.07, 0.11), 0.0, 2.24, M['puerta_ext'])
        f.prism(fquad(3.42, 3.45, 0.02, 0.07), 0.9, 1.5, M['metal'])
    f.prism(fquad(3.62, 3.70, -0.04, 0.0), 2.05, 2.15, M['metal'])           # aplique
    f.build("PB Carpinterías de fachada", C_PB); g.build("PB Vidrios de fachada", C_PB)
    # bandas de madera en los cantos de forjado (van con la planta de encima)
    for (zb, coll, lv) in ((LV["P1"] - SLAB, C_P1, "P1"), (LV["BC"] - SLAB, C_BC, "BC")):
        bnd = MB(); bnd.prism(fquad(0.0, FL, -0.04, 0.0), zb, zb + SLAB, M['madera_ext']); bnd.build(f"{lv} Banda de madera en fachada", coll)
    # Planta primera
    f, g = MB(), MB()
    z = LV["P1"]
    if P1V == "A":
        glazing(f, g, 1.75, 3.60, z, z + CLEAR, panes=2)
        glass_rail(f, g, 1.75, 3.60, z)
        glazing(f, g, 0.60, 1.30, z + 1.05, z + 2.15, panes=1, glass=M['vidrio_mate'], sill=True)
    else:
        glazing(f, g, 0.60, 3.60, z, z + CLEAR, panes=4)
        glass_rail(f, g, 0.60, 3.60, z)
    f.build("P1 Carpinterías de fachada", C_P1); g.build("P1 Vidrios de fachada", C_P1)

# ---------------------------------------------------------------- escaleras voladas
def stair_pb(coll):
    mb, gl = MB(), MB()
    rule = top_rule(M['escalera'], M['escalera'])
    for i in range(1, S1_N + 1):
        x0 = S1_X0 + (i - 1) * S1_D; top = i * S1_R
        mb.box(x0, x0 + S1_D + 0.02, S1_Y[0], S1_Y[1], top - 0.07, top, rule)
    x1 = S1_X0 + S1_N * S1_D
    gl.xz_prism([(S1_X0, 0.04), (x1, S1_N * S1_R + 0.05), (x1, S1_N * S1_R + 1.0), (S1_X0, 0.95)], S1_Y[0] - 0.03, S1_Y[0] - 0.01, M['vidrio'])
    for k in range(4):   # pinzas de acero
        x = S1_X0 + 0.3 + k * (x1 - S1_X0 - 0.6) / 3; zz = (x - S1_X0) / (x1 - S1_X0) * S1_N * S1_R
        gl.box(x - 0.03, x + 0.03, S1_Y[0] - 0.05, S1_Y[0] + 0.01, zz + 0.10, zz + 0.16, M['metal'])
    mb.build("PB Escalera volada", coll); gl.build("PB Barandilla de vidrio escalera", coll)

def stair_p1(coll):
    z1 = LV["P1"]; mb, gl = MB(), MB()
    rule = top_rule(M['escalera'], M['escalera'])
    def tread(poly, i): top = z1 + i * S2_R; mb.prism(poly, top - 0.07, top, rule)
    for i in range(1, 6):                       # tramo del fondo, hacia el sur
        ya = S2_Y0 - i * S2_D; yb = ya + S2_D
        tread([(S2_XB, ya), (X_IN, ya), (X_IN, yb), (S2_XB, yb)], i)
    P = (S2_XB, S2_YS + 0.05)
    yk = S2_Y0 - 5 * S2_D
    for k, poly in enumerate([[P, (X_IN, yk), (X_IN, 0.70)], [P, (X_IN, 0.70), (X_IN, Y_S_IN), (7.15, Y_S_IN)],
                              [P, (7.15, Y_S_IN), (S2_XB, Y_S_IN)]]):
        tread(poly, 6 + k)
    for i in range(9, 14):                      # tramo sur, hacia la calle
        xb = S2_XB - (i - 9) * S2_D; xa = xb - S2_D
        tread([(xa, Y_S_IN), (xb, Y_S_IN), (xb, S2_YS), (xa, S2_YS)], i)
    gl.yz_prism([(S2_Y0, z1 + 0.04), (yk, z1 + 5 * S2_R + 0.05), (yk, z1 + 5 * S2_R + 1.0), (S2_Y0, z1 + 0.95)], S2_XB - 0.03, S2_XB - 0.01, M['vidrio'])
    xs = S2_XB - 5 * S2_D
    gl.xz_prism([(S2_XB, z1 + 8 * S2_R + 0.05), (xs, z1 + 13 * S2_R + 0.05), (xs, z1 + 13 * S2_R + 1.0), (S2_XB, z1 + 8 * S2_R + 1.0)], S2_YS + 0.01, S2_YS + 0.03, M['vidrio'])
    mb.build("P1 Escalera volada", coll); gl.build("P1 Barandillas de vidrio escalera", coll)

# ================================================================= PLANTA BAJA
def planta_baja():
    z = 0.0; W = M['pared_int']
    shell("PB", C_PB)
    slab("PB", C_PB, [(5.0, X_IN + 0.02, 0, 9)], 5.0, M['baldosa'], "PB Solera y suelo")
    stair_pb(C_PB)
    t, d, k, s = MB(), MB(), MB(), MB()
    if VAR == "A":
        # despensa y aseo al fondo
        t.box(6.33, 6.43, 2.92, S1_Y[0], z, CLEAR, W)
        t.box(6.33, 6.43, S1_Y[0], Y_N_IN, z, 2.30, W)                          # bajo el final de la escalera
        wall(t, (6.33, 2.97), (X_IN, 2.97), -0.05, 0.05, z, CLEAR, [(0.52, 1.22, z, 2.05)], W)
        t.box(6.33, 6.43, Y_S_IN, 2.03, z, CLEAR, W)
        wall(t, (6.33, 1.98), (X_IN, 1.98), -0.05, 0.05, z, CLEAR, [(0.52, 1.22, z, 2.05)], W)
        door_leaf(d, 7.51, 7.55, 3.02, 3.72, z); door_leaf(d, 7.51, 7.55, 1.23, 1.93, z)
        sh = MB()
        for zz in (0.45, 0.85, 1.25, 1.65, 2.05):
            sh.box(6.45, 7.58, 4.05, Y_N_IN, zz, zz + 0.025, M['madera_mueble'])
            if zz < 2.0: sh.box(6.43, 6.78, 3.05, 4.05, zz, zz + 0.025, M['madera_mueble'])
        sh.build("PB Estantes despensa", C_PB)
        a = MB(); toilet(a, Y_S_IN, 6.95, z, '+y'); basin(a, 6.43, 1.35, z, '+x', 0.5); a.build("PB Aseo", C_PB)
        bath_floor("PB", [(6.43, X_IN, Y_S_IN, 1.93)], C_PB, "PB Suelo aseo")
        # cocina: bloque con fregadero contra el aseo + bancada sur con vitro
        counter(k, 5.75, 6.33, Y_S_IN, 2.00, '-x'); sink(k, 5.85, 6.25, 1.10, 1.70)
        k.box(6.24, 6.28, 1.38, 1.42, 0.91, 1.20, M['metal'])
        counter(k, 3.57, 5.75, Y_S_IN, 0.87, '+y'); hob(k, 3.95, 4.55, 0.33, 0.80)
        wall_cab(k, 3.57, 5.70, Y_S_IN, 0.60, '+y')
        k.box(3.95, 4.55, Y_S_IN, 0.75, 1.55, 1.70, M['metal'])
        sep_x = 3.48
        # comedor 6 plazas
        k.box(3.95, 5.05, 2.25, 3.10, 0.72, 0.76, M['madera_mueble'])
        for (lx, ly) in ((4.0, 2.30), (5.0, 2.30), (4.0, 3.05), (5.0, 3.05)): k.box(lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, 0, 0.72, M['madera_mueble'])
        chair(k, 3.72, 2.67, z, '+x'); chair(k, 5.25, 2.67, z, '-x')
        for cx in (4.22, 4.78): chair(k, cx, 3.30, z, '-y'); chair(k, cx, 2.03, z, '+y')
        table_c = (4.5, 2.67)
    else:
        # aseo al fondo norte y cocina en L (fondo + lateral sur)
        t.box(6.33, 6.43, S1_Y[0], Y_N_IN, z, 2.30, W)
        wall(t, (6.38, 2.60), (6.38, S1_Y[0]), -0.05, 0.05, z, CLEAR, [(0.12, 0.88, z, 2.05)], W)
        t.box(6.33, X_IN, 2.60, 2.70, z, CLEAR, W)
        door_leaf(d, 6.43, 7.13, 2.72, 2.76, z)
        a = MB(); toilet(a, Y_N_IN, 6.95, z, '-y'); basin(a, X_IN, 3.12, z, '-x', 0.5); a.build("PB Aseo", C_PB)
        bath_floor("PB", [(6.43, X_IN, 2.70, Y_N_IN)], C_PB, "PB Suelo aseo")
        counter(k, 7.00, X_IN, Y_S_IN, 2.60, '-x'); hob(k, 7.08, 7.52, 1.10, 1.70)
        wall_cab(k, 7.25, X_IN, 0.87, 2.60, '-x')
        k.box(7.15, X_IN, 1.10, 1.70, 1.55, 1.70, M['metal'])
        counter(k, 3.82, 7.00, Y_S_IN, 0.87, '+y'); sink(k, 5.75, 6.45, 0.38, 0.75)
        k.box(6.08, 6.12, 0.27, 0.33, 0.91, 1.20, M['metal'])
        wall_cab(k, 3.82, 7.00, Y_S_IN, 0.60, '+y')
        sep_x = 3.70
        tx0, tx1, ty0, ty1 = (4.83, 5.62, 1.87, 2.88) if HOUSE_D else (4.32, 5.10, 1.77, 2.77)   # en D el comedor va más al fondo
        k.box(tx0, tx1, ty0, ty1, 0.72, 0.76, M['madera_mueble'])
        for (lx, ly) in ((tx0 + 0.05, ty0 + 0.05), (tx1 - 0.05, ty0 + 0.05), (tx0 + 0.05, ty1 - 0.05), (tx1 - 0.05, ty1 - 0.05)):
            k.box(lx - 0.03, lx + 0.03, ly - 0.03, ly + 0.03, 0, 0.72, M['madera_mueble'])
        tcx, tcy = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        for cy in (tcy - 0.25, tcy + 0.25): chair(k, tx1 + 0.20, cy, z, '-x'); chair(k, tx0 - 0.20, cy, z, '+x')
        chair(k, tcx, ty1 + 0.21, z, '-y'); chair(k, tcx, ty0 - 0.21, z, '+y')
        table_c = (tcx, tcy)
    # frigorífico bajo la escalera
    k.box(5.70, 6.30, 3.72, Y_N_IN - 0.02, 0.0, 1.85, M['inox'])
    k.box(5.68, 5.70, 3.80, 3.84, 0.9, 1.6, M['metal'])
    # separador de listones de madera (deja pasar la luz)
    for i in range(12):
        yy = Y_S_IN + 0.02 + i * 0.09
        s.box(sep_x, sep_x + 0.05, yy, yy + 0.04, 0.0, CLEAR, M['listones'])
    s.box(sep_x - 0.01, sep_x + 0.06, Y_S_IN, Y_S_IN + 1.07, CLEAR - 0.04, CLEAR, M['listones'])
    # salón (común a las dos versiones)
    s.box(0.95, 2.75, 1.05, 2.30, 0.0, 0.012, M['alfombra'])
    s.box(0.66, 2.47, Y_S_IN, 0.90, 0.06, 0.42, M['sofa'])
    s.box(0.66, 2.47, Y_S_IN, 0.45, 0.42, 0.85, M['sofa'])
    s.box(0.66, 0.84, 0.45, 0.90, 0.42, 0.62, M['sofa']); s.box(2.29, 2.47, 0.45, 0.90, 0.42, 0.62, M['sofa'])
    s.box(0.95, 1.30, 0.45, 0.57, 0.52, 0.82, M['cojin']); s.box(1.85, 2.20, 0.45, 0.57, 0.52, 0.82, M['cojin'])
    s.box(1.30, 2.20, 1.25, 1.68, 0.0, 0.36, M['madera_mueble']); s.box(1.24, 2.24, 1.20, 1.72, 0.36, 0.40, M['madera_mueble'])
    s.box(2.50, 3.16, 0.95, 1.68, 0.06, 0.42, M['sofa'])                       # butaca mirando a la calle
    s.box(3.00, 3.16, 0.95, 1.68, 0.42, 0.85, M['sofa'])
    s.box(2.50, 3.00, 0.95, 1.08, 0.42, 0.62, M['sofa']); s.box(2.50, 3.00, 1.55, 1.68, 0.42, 0.62, M['sofa'])
    s.cyl(2.87, 0.58, 0.21, 0.0, 0.55, M['madera_mueble'], 24)
    s.box(1.32, 2.74, 3.95, Y_N_IN, 0.0, 0.45, M['madera_mueble'])             # mueble TV y TV 55"
    s.box(1.40, 2.66, 4.20, 4.25, 0.60, 1.31, M['negro'])
    s.cyl(0.85, 4.10, 0.16, 0.0, 0.40, M['ceramica'], 20); s.cyl(0.85, 4.10, 0.30, 0.40, 1.10, M['planta'], 12)
    s.prism(fquad(0.75, 1.85, 0.32, 0.39), 0.15, 0.75, M['radiador'])
    d.box(0.64, 1.36, 3.55, 3.59, z, z + 2.24, M['puerta_ext'])               # hoja de entrada abierta
    t.build("PB Tabiques", C_PB); d.build("PB Puertas", C_PB); k.build("PB Cocina y comedor", C_PB); s.build("PB Salón y separador", C_PB)
    area_light("PB Luz salón", C_PB, (1.9, 1.5, CLEAR - 0.02), 2.0, 1.6, 150)
    area_light("PB Luz cocina", C_PB, (5.0, 1.2, CLEAR - 0.02), 2.4, 0.8, 110)
    area_light("PB Luz comedor", C_PB, (*table_c, CLEAR - 0.02), 1.0, 0.8, 80)
    area_light("PB Luz aseo", C_PB, (7.0, 1.2 if VAR == "A" else 3.5, CLEAR - 0.02), 0.6, 0.6, 30)
    label("PB", "Salón", 1.70, 2.75, 0.2)
    label("PB", "Cocina", 4.6, 1.35 if VAR == "A" else 1.25, 0.16)
    label("PB", "Aseo", 7.0, 1.05 if VAR == "A" else 3.6, 0.13)
    if VAR == "A": label("PB", "Despensa", 7.05, 3.28, 0.12)
    label("PB", "Frigorífico\nbajo la escalera", 6.0, 3.30, 0.10)

# ================================================================= PLANTA PRIMERA
def planta_primera():
    z = LV["P1"]; zt = z + CLEAR; W = M['pared_int']
    shell("P1", C_P1)
    gx0, gx1, gy0, gy1 = GLASS_FLOOR
    slab("P1", C_P1, [(HOLE1[0], gx0, 0, S1_Y[0]), (gx0, HOLE1[1], 0, gy0), (gx0, HOLE1[1], gy1, S1_Y[0]), (HOLE1[1], X_IN + 0.02, 0, 9)],
         HOLE1[0], M['parquet'], "P1 Forjado y suelo")
    g = MB()
    g.box(gx0 + 0.04, gx1 - 0.04, gy0 + 0.04, gy1 - 0.04, z - 0.05, z, M['vidrio_suelo'])
    for (a, b, c, e) in ((gx0, gx1, gy0, gy0 + 0.04), (gx0, gx1, gy1 - 0.04, gy1), (gx0, gx0 + 0.04, gy0, gy1), (gx1 - 0.04, gx1, gy0, gy1)):
        g.box(a, b, c, e, z - 0.12, z, M['metal'])
    g.build("P1 Suelo de vidrio", C_P1)
    stair_p1(C_P1)
    t, d, f, b = MB(), MB(), MB(), MB()
    r = MB()
    WX = 4.70 if (HOUSE_D and P1V == "B") else 4.50    # línea del tabique dormitorio / distribuidor
    r.box(WX + 0.05, HOLE1[1], S1_Y[0] - 0.09, S1_Y[0] - 0.07, z, z + 1.0, M['vidrio'])        # barandilla hueco escalera PB
    r.box(WX + 0.05, HOLE1[1], S1_Y[0] - 0.10, S1_Y[0] - 0.06, z + 1.0, z + 1.04, M['metal'])
    r.build("P1 Barandilla de vidrio", C_P1)
    # muros que cierran el hueco ampliado por el lado del dormitorio/baño (común)
    t.box(3.75, WX + 0.05, 3.42, 3.52, z, zt, W)
    t.box(3.70, 3.80, 3.42, Y_N_IN, z, zt, W)
    # caldera en el hueco bajo el tramo que sube a la bajocubierta, con puertas hacia el suelo de vidrio
    f.cyl(6.00, 0.70, 0.25, z, z + 1.10, M['electro'], 28)
    for (p0, p1) in ((5.42, 6.04), (6.06, 6.68)):
        d.box(p0, p1, 1.15, 1.19, z, z + 1.70, M['puerta_int'])
        hx = p1 - 0.08 if p0 < 6.0 else p0 + 0.05
        d.box(hx, hx + 0.03, 1.19, 1.22, z + 0.85, z + 1.15, M['metal'])
    d.box(6.66, 6.70, Y_S_IN, 1.15, z, z + 1.70, M['puerta_int'])
    if P1V == "A":
        t.box(5.30, 5.40, Y_S_IN, 2.48, z, zt, W)                                   # fondo del armario
        t.box(4.47, 5.40, 2.38, 2.48, z, zt, W)
        wall(t, (4.50, 2.48), (4.50, 3.42), -0.05, 0.05, z, zt, [(0.08, 0.89, z, z + 2.03)], W)
        door_leaf(d, 3.75, 4.45, 2.56, 2.60, z)
        wardrobe(f, 4.62, 5.30, Y_S_IN, 2.38, z, 2.35, '-x', ndoors=3)
        # baño en suite
        wall(t, (xf(1.475, FT) - 0.02, 1.475), (3.70, 1.475), -0.045, 0.045, z, zt, [(2.92 - xf(1.475, FT) + 0.02, 3.58 - xf(1.475, FT) + 0.02, z, z + 2.03)], W)
        t.box(3.60, 3.70, Y_S_IN, 1.52, z, zt, W)
        door_leaf(d, 3.54, 3.58, 0.75, 1.43, z)
        shower(b, xf(0.3, FT), 1.08, Y_S_IN, 1.43, z, [(1.06, 1.08, 0.62, 1.43)], (0.70, 0.29))
        toilet(b, Y_S_IN, 1.53, z, '+y')
        basin(b, Y_S_IN, 2.66, z, '+y', 1.38, sinks=2)
        bath_floor("P1", [(xf(0.8, FT), 3.60, Y_S_IN, 1.43)], C_P1, "P1 Suelo baño")
        b.box(1.88, 2.73, 1.52, 1.56, z + 1.05, z + 1.60, M['negro'])             # TV
        b.box(0.58, 1.50, 1.52, 1.60, z + 0.15, z + 0.75, M['radiador'])
        b.box(3.82, 4.40, Y_S_IN, 0.27, z + 0.6, z + 2.0, M['espejo'])            # espejo
        bed(f, 1.68, 3.18, 2.40, Y_N_IN, z, '+y', M['edredon1'])
        nightstand(f, 1.20, 1.60, 4.00, 4.40, z); nightstand(f, 3.25, 3.65, 4.00, 4.40, z)
        area_light("P1 Luz dormitorio", C_P1, (2.4, 2.9, zt - 0.02), 1.6, 1.2, 90)
        area_light("P1 Luz baño", C_P1, (2.0, 0.9, zt - 0.02), 1.4, 0.6, 50)
        label("P1", "Dormitorio principal", 2.40, 1.95, 0.17)
        label("P1", "Baño", 2.4, 1.0, 0.14)
        label("P1", "Vestidor", 4.1, 0.95, 0.11)
    else:
        XG = 1.47 if HOUSE_D else 1.37
        t.box(5.30, 5.40, Y_S_IN, 2.35, z, zt, W)
        t.box(4.70, 5.40, 2.25, 2.35, z, zt, W)
        if HOUSE_D:
            wall(t, (WX, 2.35), (WX, 3.42), -0.05, 0.05, z, zt, [(0.07, 0.82, z, z + 2.03)], W)
            door_leaf(d, 4.00, 4.65, 3.13, 3.17, z)
        else:
            wall(t, (4.50, 2.29), (4.50, 3.42), -0.05, 0.05, z, zt, [(0.06, 0.71, z, z + 2.03)], W)
            door_leaf(d, 3.80, 4.45, 2.96, 3.00, z)
        wardrobe(f, 4.70, 5.30, Y_S_IN, 2.25, z, 2.35, '-x', ndoors=3)
        # baño junto al muro norte (acortado hasta el hueco ampliado de la escalera)
        if HOUSE_D:   # un solo seno; la puerta abre hacia el dormitorio
            BY = 3.25
            wall(t, (XG, BY), (3.80, BY), -0.05, 0.05, z, zt, [(1.58 - XG, 2.27 - XG, z, z + 2.03)], W)
            door_leaf(d, 1.58, 1.62, BY - 0.74, BY - 0.05, z)
            shower(b, 3.05, 3.70, BY + 0.05, Y_N_IN, z, [(3.03, 3.05, BY + 0.05, 3.95)], (3.63, 4.38))
            toilet(b, Y_N_IN, 2.65, z, '-y')
            basin(b, Y_N_IN, 1.95, z, '-y', 0.70, sinks=1)
            bath_floor("P1", [(XG + 0.05, 3.70, BY + 0.05, Y_N_IN)], C_P1, "P1 Suelo baño")
        else:
            BY = 3.10
            wall(t, (XG, BY), (3.80, BY), -0.05, 0.05, z, zt, [(0.18, 0.91, z, z + 2.03)], W)
            door_leaf(d, 1.55, 1.59, 3.15, 3.88, z)
            shower(b, 3.00, 3.70, 3.15, Y_N_IN, z, [(2.98, 3.00, 3.15, 3.85)], (3.63, 3.80))
            toilet(b, Y_N_IN, 2.68, z, '-y')
            basin(b, Y_N_IN, 1.93, z, '-y', 1.00, sinks=2)
            bath_floor("P1", [(XG + 0.05, 3.70, 3.15, Y_N_IN)], C_P1, "P1 Suelo baño")
        # cerramiento interior acristalado entre dormitorio/baño y la galería
        gi, gg = MB(), MB()
        gi.box(XG - 0.05, XG + 0.05, Y_S_IN, 0.52, z, zt, W)
        gi.box(XG - 0.05, XG + 0.05, 3.02, 3.37, z, zt, W)
        gi.box(XG - 0.05, XG + 0.05, 3.37, Y_N_IN, z, z + 1.05, W)
        gi.box(XG - 0.05, XG + 0.05, 3.37, Y_N_IN, z + 2.15, zt, W)
        for (ya, yb, za, zb, m) in ((0.52, 3.02, z, zt, M['vidrio']), (3.37, Y_N_IN, z + 1.05, z + 2.15, M['vidrio_mate'])):
            fr = 0.05
            gi.box(XG - 0.04, XG + 0.04, ya, ya + fr, za, zb, M['marco']); gi.box(XG - 0.04, XG + 0.04, yb - fr, yb, za, zb, M['marco'])
            gi.box(XG - 0.04, XG + 0.04, ya, yb, za, za + fr, M['marco']); gi.box(XG - 0.04, XG + 0.04, ya, yb, zb - fr, zb, M['marco'])
            gg.box(XG - 0.005, XG + 0.005, ya + fr, yb - fr, za + fr, zb - fr, m)
        for ym in (1.15, 1.77, 2.40): gi.box(XG - 0.04, XG + 0.04, ym - 0.03, ym + 0.03, z, zt, M['marco'])
        gi.build("P1 Cristalera interior", C_P1); gg.build("P1 Vidrios interiores", C_P1)
        # galería asturiana (terraza acristalada)
        tz = MB()
        tz.prism([(xf(Y_S_IN, FT), Y_S_IN), (XG - 0.05, Y_S_IN), (XG - 0.05, Y_N_IN), (xf(Y_N_IN, FT), Y_N_IN)], z, z + 0.02, M['tarima_ext'])
        tz.cyl(0.83, 1.66, 0.30, z + 0.72, z + 0.75, M['madera_mueble'], 32); tz.cyl(0.83, 1.66, 0.04, z, z + 0.72, M['metal'], 12)
        chair(tz, 0.83, 2.33, z, '-y'); chair(tz, 0.83, 1.00, z, '+y')
        tz.cyl(0.70, 3.90, 0.15, z, z + 0.35, M['ceramica'], 20); tz.cyl(0.70, 3.90, 0.26, z + 0.35, z + 0.95, M['planta'], 12)
        tz.build("P1 Galería terraza", C_P1)
        bed(f, 2.37, 3.89, Y_S_IN, 2.25, z, '-y', M['edredon1'])
        nightstand(f, 3.94, 4.34, 0.29, 0.69, z); nightstand(f, 1.89, 2.29, 0.29, 0.69, z)
        b.box(2.74, 3.68, BY - 0.10, BY - 0.05, z + 0.15, z + 0.75, M['radiador'])
        area_light("P1 Luz dormitorio", C_P1, (3.0, 1.6, zt - 0.02), 1.6, 1.2, 90)
        area_light("P1 Luz baño", C_P1, (2.9, 3.75, zt - 0.02), 1.6, 0.6, 50)
        area_light("P1 Luz galería", C_P1, (0.85, 2.3, zt - 0.02), 0.6, 2.4, 50)
        label("P1", "Dormitorio\nprincipal", 2.65, 2.85, 0.12)
        label("P1", "Baño", 2.6, 3.55, 0.14)
        label("P1", "Galería\n(terraza)", 0.85, 2.88, 0.11)
    label("P1", "Caldera (bajo la escalera)", 6.03, 1.42, 0.075)
    label("P1", "Suelo de vidrio", (gx0 + gx1) / 2, 1.90, 0.11)
    label("P1", "Hueco escalera", 5.2, 3.97, 0.11)
    area_light("P1 Luz distribuidor", C_P1, (6.0, 2.9, zt - 0.02), 1.0, 0.8, 50)
    t.build("P1 Tabiques", C_P1); d.build("P1 Puertas", C_P1); f.build("P1 Dormitorio", C_P1); b.build("P1 Baño", C_P1)

# ================================================================= BAJOCUBIERTA (común)
D_HOLE_Y = 1.72          # D: borde del hueco junto al dormitorio trasero
D_REAR_Y = 2.33          # D: el tramo del fondo queda abierto hasta aquí (peldaño 1 con 2.30 m libres)

def bajo_cubierta_d():
    """Bajocubierta del diseño final: dormitorio con casetón delante, baño en el centro, dormitorio trasero
    con casetón trasero y escritorio, pasillo con solatube. El tramo del fondo de la escalera queda abierto."""
    z = LV["BC"]; W = M['pared_int']
    zr = lambda x, y: z_under(x) + 0.02
    shell("BC", C_BC)
    slab("BC", C_BC, [(5.35, S2_XB, D_HOLE_Y, 9), (S2_XB, X_IN + 0.02, D_REAR_Y, 9)], 5.35, M['parquet'], "BC Forjado y suelo")
    if ASYM:   # ventanal en la fachada alta, con barandilla de vidrio
        wf, wg = MB(), MB()
        glazing(wf, wg, BC_W0, BC_W1, BC_WZ[0], BC_WZ[1], panes=3, sill=True)
        glass_rail(wf, wg, BC_W0, BC_W1, BC_WZ[0])
        wf.build("BC Ventanal de fachada", C_BC); wg.build("BC Vidrios del ventanal", C_BC)
    t, d, f, b = MB(), MB(), MB(), MB()
    wall(t, (3.05, Y_S_IN), (3.05, Y_N_IN), -0.05, 0.05, z, zr, [(0.20, 1.00, z, z + 2.0)], W)       # dormitorio delantero
    wall(t, (3.10, 1.765), (4.42, 1.765), -0.045, 0.045, z, zr, [(0.02, 0.68, z, z + 2.0)], W)      # baño (puerta 3.12-3.78)
    t.box(4.33, 4.42, 1.72, Y_N_IN, z, zr, W)
    wall(t, (4.42, 1.765), (S2_XB, 1.765), -0.045, 0.045, z, zr, [(0.03, 0.78, z, z + 2.0)], W)     # dormitorio trasero (4.45-5.20)
    t.box(S2_XB - 0.05, S2_XB + 0.05, 1.72, D_REAR_Y + 0.10, z, zr, W)
    t.box(S2_XB - 0.05, X_IN, D_REAR_Y, D_REAR_Y + 0.10, z, zr, W)
    t.build("BC Tabiques", C_BC)
    door_leaf(d, 2.30, 3.00, 0.45, 0.49, z, 2.0)        # dormitorio delantero
    door_leaf(d, 3.74, 3.78, 1.81, 2.45, z, 2.0)        # baño
    door_leaf(d, 4.42, 4.46, 1.81, 2.56, z, 2.0)        # dormitorio trasero
    d.build("BC Puertas", C_BC)
    r = MB()
    r.box(5.33, 5.35, 1.22, D_HOLE_Y, z, z + 1.0, M['vidrio'])
    r.box(5.32, 5.36, 1.20, D_HOLE_Y, z + 1.0, z + 1.04, M['metal'])
    r.build("BC Barandilla de vidrio", C_BC)
    # dormitorio delantero (casetón)
    bed(f, 0.95, 2.97, 2.05, 3.41, z, '+x', M['edredon3'])
    nightstand(f, 2.57, 2.97, 3.45, 3.85, z); nightstand(f, 2.57, 2.97, 1.61, 2.01, z)
    wardrobe(f, xf(0.56, FT) + 0.02, 1.98, Y_S_IN, 0.87, z, 1.55, '+y', ndoors=2)
    f.box(1.47, 2.14, 4.33, Y_N_IN - 0.01, z + 0.15, z + 0.75, M['radiador'])
    f.box(1.0, 2.6, 0.95, 1.95, z, z + 0.012, M['alfombra'])
    # dormitorio trasero: cama de 105, escritorio y armario bajo junto al muro del fondo
    bed(f, 4.47, 6.25, 3.10, 4.15, z, '-x', M['edredon2'])
    nightstand(f, 4.47, 4.80, 2.70, 3.05, z)
    f.box(5.49, 6.49, 1.81, 2.31, z + 0.72, z + 0.76, M['madera_mueble'])
    for lx in (5.53, 6.45): f.box(lx - 0.02, lx + 0.02, 1.85, 2.27, z, z + 0.72, M['madera_mueble'])
    chair(f, 5.95, 2.45, z, '-y')
    wardrobe(f, 7.00, 7.50, 2.53, Y_N_IN, z, 1.15, '-x', ndoors=3)
    f.build("BC Dormitorios", C_BC)
    # baño central
    shower(b, 3.10, 4.30, 3.69, Y_N_IN, z, [(3.10, 3.70, 3.67, 3.69)], (3.70, 4.38))
    toilet(b, 4.33, 3.27, z, '-x')
    basin(b, 4.33, 2.43, z, '-x', 0.75)
    b.box(3.10, 3.15, 2.56, 3.00, z + 0.15, z + 0.75, M['radiador'])
    b.build("BC Baño", C_BC)
    bath_floor("BC", [(3.10, 4.33, 1.81, Y_N_IN)], C_BC, "BC Suelo baño")
    area_light("BC Luz dormitorio delantero", C_BC, (1.8, 2.4, 7.6), 1.4, 1.4, 120)
    area_light("BC Luz dormitorio trasero", C_BC, (5.3, 3.0, z_under(5.3) - 0.05), 1.4, 1.0, 80)
    area_light("BC Luz baño", C_BC, (3.7, 2.9, z_under(3.7) - 0.05), 0.8, 0.8, 35)
    area_light("BC Luz pasillo", C_BC, (4.2, 1.0, z_under(4.2) - 0.05), 0.8, 0.8, 35)
    label("BC", "Dormitorio" if ASYM else "Dormitorio\n(casetón)", 1.40, 1.20, 0.14)
    label("BC", "Baño", 3.55, 2.85, 0.12)
    label("BC", "Dormitorio\ntrasero" if ASYM else "Dormitorio\n(casetón trasero)", 5.85, 2.80, 0.09)
    label("BC", "Pasillo", 4.2, 0.95, 0.12)
    label("BC", "Hueco", 6.0, 1.48, 0.10)

def bajo_cubierta():
    if NEW_ATTIC: return bajo_cubierta_c()
    if HOUSE_D: return bajo_cubierta_d()
    z = LV["BC"]; W = M['pared_int']
    zr = lambda x, y: z_under(x) + 0.02
    shell("BC", C_BC)
    slab("BC", C_BC, [(5.35, X_IN + 0.02, BC_HOLE_Y, 9)], 5.35, M['parquet'], "BC Forjado y suelo")
    t, d, f, b = MB(), MB(), MB(), MB()
    wall(t, (3.07, Y_S_IN), (3.07, Y_N_IN), -0.05, 0.05, z, zr, [(0.30, 1.15, z, z + 2.0)], W)       # dormitorio delantero
    wall(t, (3.12, 1.57), (4.47, 1.57), -0.05, 0.05, z, zr, [(0.0, 0.64, z, z + 2.0)], W)            # baño
    t.box(4.42, 4.52, 1.52, Y_N_IN, z, zr, W)
    wall(t, (4.47, 1.94), (X_IN, 1.94), -0.05, 0.05, z, zr, [(0.13, 0.86, z, z + 2.0)], W)           # dormitorio trasero
    t.build("BC Tabiques", C_BC)
    door_leaf(d, 2.32, 3.02, 0.55, 0.59, z, 2.0)
    door_leaf(d, 3.72, 3.76, 1.62, 2.26, z, 2.0)
    door_leaf(d, 5.29, 5.33, 1.99, 2.72, z, 2.0)
    d.build("BC Puertas", C_BC)
    r = MB()
    r.box(5.33, 5.35, 1.25, BC_HOLE_Y, z, z + 1.0, M['vidrio'])
    r.box(5.32, 5.36, 1.20, BC_HOLE_Y, z + 1.0, z + 1.04, M['metal'])
    r.build("BC Barandilla de vidrio", C_BC)
    # dormitorio bajo el casetón
    bed(f, 0.97, 2.97, 2.08, 3.42, z, '+x', M['edredon3'])
    nightstand(f, 2.57, 2.97, 3.48, 3.88, z); nightstand(f, 2.57, 2.97, 1.62, 2.02, z)
    wardrobe(f, xf(0.92, FT) + 0.02, 2.12, Y_S_IN, 0.88, z, 1.60, '+y', ndoors=3)
    f.box(1.0, 2.6, 0.95, 1.95, z, z + 0.012, M['alfombra'])
    # dormitorio trasero (velux)
    bed(f, 6.29, 7.15, 2.62, Y_N_IN, z, '+y', M['edredon2'])
    nightstand(f, 5.55, 5.95, 4.00, 4.40, z)
    wardrobe(f, 4.52, 5.06, 3.22, Y_N_IN, z, 2.0, '+x', ndoors=2)
    f.build("BC Dormitorios", C_BC)
    shower(b, 3.12, 4.42, 3.56, Y_N_IN, z, [(3.12, 3.80, 3.54, 3.56)], (3.80, 4.38))
    toilet(b, 4.42, 3.14, z, '-x')
    basin(b, 4.42, 2.36, z, '-x', 0.6)
    b.build("BC Baño", C_BC)
    bath_floor("BC", [(3.12, 4.42, 1.62, Y_N_IN)], C_BC, "BC Suelo baño")
    area_light("BC Luz dormitorio delantero", C_BC, (1.8, 2.4, 7.6), 1.4, 1.4, 120)
    area_light("BC Luz dormitorio trasero", C_BC, (6.0, 3.2, z_under(6.0) - 0.05), 1.2, 1.0, 60)
    area_light("BC Luz baño", C_BC, (3.8, 2.9, z_under(3.8) - 0.05), 0.8, 0.8, 35)
    area_light("BC Luz distribuidor", C_BC, (4.3, 1.0, z_under(4.3) - 0.05), 0.8, 0.8, 35)
    label("BC", "Dormitorio\n(casetón)", 1.8, 1.45, 0.16)
    label("BC", "Baño", 3.75, 2.75, 0.13)
    label("BC", "Dormitorio", 6.0, 2.25, 0.14)
    label("BC", "Hueco de luz", 6.0, 1.56, 0.10)

def bajo_cubierta_c():
    """Bajocubierta replanteada: dormitorio 1 (casetón) + dormitorio 2 (velux) + baño, y la escalera sin techo encima.
    El hueco del forjado cubre todo el tramo que sube por el fondo, así que sobre cada peldaño queda la cubierta (> 3 m)."""
    z = LV["BC"]; W = M['pared_int']
    zr = lambda x, y: z_under(x) + 0.02
    shell("BC", C_BC)
    slab("BC", C_BC, [(5.35, S2_XB, BC_HOLE_Y, 9), (S2_XB, X_IN + 0.02, 2.70, 9)], 5.35, M['parquet'], "BC Forjado y suelo")
    t, d, f, b = MB(), MB(), MB(), MB()
    x0 = xf(1.70, FT) - 0.02
    # muro corrido norte del baño y del pasillo, con las puertas de los dos dormitorios
    wall(t, (x0, 1.70), (5.40, 1.70), -0.05, 0.05, z, zr, [(2.70 - x0, 3.30 - x0, z, z + 2.0), (4.55 - x0, 5.25 - x0, z, z + 2.0)], W)
    wall(t, (2.60, Y_S_IN), (2.60, 1.65), -0.05, 0.05, z, zr, [(0.02, 0.72, z, z + 2.0)], W)        # baño, puerta al pasillo
    t.box(3.40, 3.50, 1.75, Y_N_IN, z, zr, W)                                                         # entre dormitorios
    # dormitorio 2 alrededor del hueco de la escalera
    t.box(5.35, 5.45, 1.75, 1.99, z, zr, W)
    t.box(5.35, 6.70, 1.89, 1.99, z, zr, W)
    t.box(6.60, 6.70, 1.99, 2.80, z, zr, W)
    t.box(6.60, X_IN, 2.70, 2.80, z, zr, W)
    t.build("BC Tabiques", C_BC)
    door_leaf(d, 1.88, 2.55, 0.27, 0.31, z, 2.0)        # baño
    door_leaf(d, 3.26, 3.30, 1.75, 2.35, z, 2.0)        # dormitorio 1
    door_leaf(d, 5.21, 5.25, 1.75, 2.45, z, 2.0)        # dormitorio 2
    d.build("BC Puertas", C_BC)
    r = MB()
    r.box(5.33, 5.35, 1.22, 1.65, z, z + 1.0, M['vidrio'])
    r.box(5.32, 5.36, 1.20, 1.65, z + 1.0, z + 1.04, M['metal'])
    r.build("BC Barandilla de vidrio", C_BC)
    # dormitorio 1, bajo el casetón
    bed(f, 1.40, 3.40, 2.35, 3.70, z, '+x', M['edredon3'])
    nightstand(f, 3.00, 3.40, 3.75, 4.15, z)
    wardrobe(f, 1.50, 2.85, 3.87, Y_N_IN, z, 2.0, '-y', ndoors=2)
    f.box(1.0, 2.6, 1.95, 2.30, z, z + 0.012, M['alfombra'])
    # dormitorio 2, con velux
    bed(f, 4.60, 5.95, 2.52, Y_N_IN, z, '+y', M['edredon2'])
    nightstand(f, 4.15, 4.55, 4.00, 4.40, z); nightstand(f, 6.00, 6.40, 4.00, 4.40, z)
    wardrobe(f, 3.50, 4.10, 2.00, 3.60, z, 2.30, '+x', ndoors=2)
    f.box(6.75, 7.55, 2.85, 4.40, z, z + 0.55, M['madera_mueble'])                   # arcón en la parte baja
    f.build("BC Dormitorios", C_BC)
    # baño en la esquina delantera sur
    shower(b, 1.75, 2.55, 0.95, 1.65, z, [(1.75, 2.25, 0.93, 0.95)], (2.15, 1.62))
    toilet(b, Y_S_IN, 1.15, z, '+y')
    basin(b, 1.65, 1.33, z, '-y', 0.70)
    b.box(xf(0.6, FT) + 0.02, 0.85, 0.30, 1.60, z, z + 0.45, M['madera_mueble'])     # banco/toallero en la zona baja
    b.build("BC Baño", C_BC)
    bath_floor("BC", [(xf(0.25, FT), 2.55, Y_S_IN, 1.65)], C_BC, "BC Suelo baño")
    area_light("BC Luz dormitorio 1", C_BC, (2.1, 3.0, 7.75), 1.4, 1.4, 120)
    area_light("BC Luz dormitorio 2", C_BC, (4.9, 3.1, z_under(4.9) - 0.05), 1.4, 1.0, 90)
    area_light("BC Luz baño", C_BC, (1.8, 0.95, z_under(1.8) - 0.05), 0.8, 0.8, 40)
    area_light("BC Luz pasillo", C_BC, (4.0, 0.95, z_under(4.0) - 0.05), 1.2, 0.6, 45)
    label("BC", "Dormitorio 1\n(casetón)", 0.82, 3.62, 0.11)
    label("BC", "Dormitorio\n2", 6.33, 3.30, 0.12)
    label("BC", "Baño", 1.35, 0.95, 0.12)
    label("BC", "Pasillo", 4.0, 0.95, 0.12)
    label("BC", "Hueco de escalera", 6.0, 1.56, 0.10)

# ================================================================= CUBIERTA, CASETÓN, VELUX Y SOLATUBES
VELUX = (5.82, 6.88, 2.80, 3.60)
SOLATUBES = [(6.30, 1.14), (1.95, 0.80)] if NEW_ATTIC else [(4.70, 0.96), (3.75, 2.96)] if HOUSE_D else [(6.30, 1.14), (3.78, 2.98)]
# Casetón trasero (D): sustituye al velux del dormitorio del fondo
RDY0, RDY1 = 2.86, 3.86
RYC = (RDY0 + RDY1) / 2
RXF, RR, RS, RT = 6.92, 8.30, 0.50, 0.18
def rz_top(y): return RR - RS * abs(y - RYC)
def rz_under(y): return rz_top(y) - RT
def rvalley_x(y): return RIDGE_X + (Z_RIDGE - rz_top(y)) / SLOPE

def caseton_trasero():
    rule = lambda n: M['teja'] if n.z > 0.3 else M['madera_techo'] if n.z < -0.3 else M['madera_ext']
    k, kg = MB(), MB()
    xe = RXF + 0.15
    for sgn in (-1, 1):
        ye = RYC + sgn * 0.65
        k.prism([(xe, RYC), (rvalley_x(RYC), RYC), (rvalley_x(ye), ye), (xe, ye)], lambda x, y: rz_top(y) - RT, lambda x, y: rz_top(y), rule, split=False)
        k.yz_prism([(RYC, rz_top(RYC) - RT - 0.06), (ye, rz_top(ye) - RT - 0.06), (ye, rz_top(ye) + 0.02), (RYC, rz_top(RYC) + 0.02)], xe, xe + 0.05, M['madera_ext'])
    k.box(rvalley_x(RYC) + 0.15, xe + 0.05, RYC - 0.06, RYC + 0.06, RR - 0.02, RR + 0.07, M['teja'])
    xv = rvalley_x(RDY0) - 0.02
    for (y0, y1, out) in ((RDY0, RDY0 + 0.10, (0, -1)), (RDY1 - 0.10, RDY1, (0, 1))):
        k.prism([(xv, y0), (RXF, y0), (RXF, y1), (xv, y1)], lambda x, y: z_under(x) - 0.01, lambda x, y: rz_under(y) + 0.05,
                ext_rule(M['madera_ext'], M['pared_int'], out), split=False)
    # frente con ventana hacia el fondo
    fx0 = RXF - 0.12; sill = z_top(RXF) + 0.07; top = sill + 0.38
    wy0, wy1 = RDY0 + 0.10, RDY1 - 0.10
    k.prism([(fx0, RDY0), (RXF, RDY0), (RXF, RDY1), (fx0, RDY1)], lambda x, y: z_under(x) - 0.01, sill, ext_rule(M['madera_ext'], M['pared_int'], (1, 0)), split=False)
    for (a, b_) in ((wy0, wy0 + 0.05), (wy1 - 0.05, wy1)): k.box(fx0 + 0.04, RXF - 0.02, a, b_, sill, top, M['marco'])
    k.box(fx0 + 0.04, RXF - 0.02, wy0, wy1, sill, sill + 0.05, M['marco'])
    k.box(fx0, RXF, RDY0, RDY1, top, top + 0.07, M['madera_ext'])
    kg.box(fx0 + 0.06, fx0 + 0.07, wy0 + 0.05, wy1 - 0.05, sill + 0.05, top, M['vidrio'])
    kg.yz_prism([(wy0, top + 0.07), (wy1, top + 0.07), (wy1, rz_under(wy1) - 0.01), (RYC, rz_under(RYC) - 0.02), (wy0, rz_under(wy0) - 0.01)], fx0 + 0.06, fx0 + 0.07, M['vidrio'])
    k.box(fx0 + 0.04, RXF - 0.02, RYC - 0.025, RYC + 0.025, top + 0.07, rz_under(RYC), M['marco'])
    k.build("Casetón trasero", C_ROOF); kg.build("Casetón trasero vidrios", C_ROOF)

def cubierta():
    rule = lambda n: M['teja'] if n.z > 0.3 else (M['madera_techo'] if n.z < -0.3 else M['canto'])
    Y0, Y1 = -0.10, Y_N_OUT + 0.10
    front = MB()
    front.xz_prism([(EAVE_F, z_under(EAVE_F)), (RIDGE_X, z_under(RIDGE_X)), (RIDGE_X, z_top(RIDGE_X)), (EAVE_F, z_top(EAVE_F))], Y0, Y1, rule)
    fo = front.build("Cubierta faldón delantero", C_ROOF, first=[M['madera_techo']])
    if not ASYM:   # hueco del casetón (por dentro)
        cut = MB()
        yi0, yi1 = DY0 + 0.12, DY1 - 0.12
        cut.yz_prism([(yi0, 4.0), (yi1, 4.0), (yi1, zd_under(yi1)), (DYC, zd_under(DYC)), (yi0, zd_under(yi0))], -1.5, 2.6, M['madera_ext'])
        boolean_cut(fo, cut)

    rear = MB(); vx0, vx1, vy0, vy1 = VELUX
    def piece(xa, xb, ya, yb):
        rear.xz_prism([(xa, z_under(xa)), (xb, z_under(xb)), (xb, z_top(xb)), (xa, z_top(xa))], ya, yb, rule)
    if HOUSE_D:
        piece(RIDGE_X, 7.86, Y0, Y1)
    else:
        piece(RIDGE_X, vx0, Y0, Y1); piece(vx1, 7.86, Y0, Y1)
        piece(vx0, vx1, Y0, vy0); piece(vx0, vx1, vy1, Y1)
    ra, rb = RIDGE_X - 0.15, RIDGE_X + 0.15
    rear.xz_prism([(ra, z_top(ra) - 0.01), (rb, z_top(rb) - 0.01), (rb, z_top(rb) + 0.03), (RIDGE_X, Z_RIDGE + 0.08), (ra, z_top(ra) + 0.03)], Y0, Y1, M['teja'])
    ro = rear.build("Cubierta faldón trasero", C_ROOF, first=[M['madera_techo']])
    if HOUSE_D and not ASYM:   # con el tejado asimétrico el casetón trasero quedaría por debajo de la cubierta
        cut = MB(); a0, a1 = RDY0 + 0.10, RDY1 - 0.10
        cut.yz_prism([(a0, 4.0), (a1, 4.0), (a1, rz_under(a1)), (RYC, rz_under(RYC)), (a0, rz_under(a0))], 3.6, RXF - 0.12, M['madera_ext'])
        boolean_cut(ro, cut)
        caseton_trasero()

    # canecillos de madera bajo el alero
    a = MB()
    y = 0.15
    e = EAVE_F
    while y < Y_N_OUT:
        if ASYM or not (DY0 - 0.1 < y < DY1 + 0.1):
            a.xz_prism([(e + 0.02, z_under(e + 0.02) - 0.14), (0.0, z_under(0.0) - 0.14), (0.0, z_under(0.0)), (e + 0.02, z_under(e + 0.02))], y - 0.05, y + 0.05, M['madera_ext'])
        y += 0.55
    ze = z_top(e)
    tramos = [(Y0, Y1)] if ASYM else [(Y0, DY0 - 0.02), (DY1 + 0.02, Y1)]   # sin casetón el alero es corrido
    for (ya, yb) in tramos:
        a.box(e - 0.04, e, ya, yb, ze - 0.36, ze + 0.02, M['madera_ext'])
        a.box(e - 0.17, e - 0.04, ya, yb, ze - 0.32, ze - 0.18, M['marco'])                 # canalón
    a.box(e - 0.12, -0.04, 0.05, 0.13, ze - 0.38, ze - 0.30, M['marco']); a.box(-0.12, -0.04, 0.05, 0.13, 0.0, ze - 0.30, M['marco'])
    a.build("Alero de madera y canalón", C_ROOF)

    # ---- casetón
    k, kg = MB(), MB()
    dr = lambda n: M['teja'] if n.z > 0.3 else M['madera_techo'] if n.z < -0.3 else M['madera_ext']
    XF = -0.35
    ov = 1.62
    for sgn in (-1, 1):
        ye = DYC + sgn * ov
        poly = [(XF, DYC), (valley_x(DYC), DYC), (valley_x(ye), ye), (XF, ye)]
        k.prism(poly, lambda x, y: zd_top(y) - DT, lambda x, y: zd_top(y), dr, split=False)
        # tabla de remate frontal
        k.yz_prism([(DYC, zd_top(DYC) - DT - 0.06), (ye, zd_top(ye) - DT - 0.06), (ye, zd_top(ye) + 0.02), (DYC, zd_top(DYC) + 0.02)], XF - 0.05, XF, M['madera_ext'])
    k.box(XF - 0.05, valley_x(DYC) - 0.2, DYC - 0.06, DYC + 0.06, DR - 0.02, DR + 0.08, M['teja'])
    # muros laterales del casetón, revestidos de madera por fuera
    for (y0, y1, out) in ((DY0, DY0 + 0.12, (0, -1)), (DY1 - 0.12, DY1, (0, 1))):
        xe = valley_x(DY0) + 0.02
        k.prism([(xf(y0), y0), (xe, y0), (xe, y1), (xf(y1), y1)], lambda x, y: z_under(x) - 0.01, lambda x, y: zd_under(y) + 0.05,
                ext_rule(M['madera_ext'], M['pared_int'], out), split=False)
    # frente: peto bajo el ventanal, jambas, dintel de madera y hastial acristalado
    fr = ext_rule(M['piedra_fachada'], M['pared_int'], (-FN.x, -FN.y))
    sw0, sw1 = s_of_y(DY0 + 0.25), s_of_y(DY1 - 0.25)
    zs, zl = LV["BC"] + 0.45, 7.50
    k.prism(fquad(S_D0, S_D1, 0.0, FT), LV["BC"], zs, fr)
    for (a0, a1) in ((S_D0, sw0), (sw1, S_D1)):
        ya, yb = F(a0)[1], F(a1)[1]
        k.sz_prism([(a0, zs), (a1, zs), (a1, zd_under(yb) + 0.05), (a0, zd_under(ya) + 0.05)], 0.0, FT, fr)
    k.prism(fquad(sw0, sw1, -0.02, FT), zl, zl + 0.12, M['madera_ext'])
    glazing(k, kg, sw0, sw1, zs, zl, panes=3)
    sc = s_of_y(DYC)
    gpts = [(sw0, zl + 0.12), (sw1, zl + 0.12), (sw1, zd_under(F(sw1)[1]) - 0.02), (sc, zd_under(DYC) - 0.02), (sw0, zd_under(F(sw0)[1]) - 0.02)]
    kg.sz_prism(gpts, 0.08, 0.09, M['vidrio'])
    k.sz_prism([(sw0, zl + 0.12), (sw0 + 0.06, zl + 0.12), (sw0 + 0.06, zd_under(F(sw0)[1])), (sw0, zd_under(F(sw0)[1]))], 0.05, 0.12, M['marco'])
    k.sz_prism([(sw1 - 0.06, zl + 0.12), (sw1, zl + 0.12), (sw1, zd_under(F(sw1)[1])), (sw1 - 0.06, zd_under(F(sw1)[1]))], 0.05, 0.12, M['marco'])
    k.sz_prism([(sc - 0.03, zl + 0.12), (sc + 0.03, zl + 0.12), (sc + 0.03, zd_under(DYC)), (sc - 0.03, zd_under(DYC))], 0.05, 0.12, M['marco'])
    if not ASYM:   # con el tejado asimétrico la fachada sube hasta arriba y lleva un ventanal en su lugar
        k.build("Casetón", C_ROOF); kg.build("Casetón vidrios", C_ROOF)

    # velux del faldón trasero
    v, vg = MB(), MB()
    def slope(xa, xb, d0, d1, ya, yb, m, tgt):
        tgt.xz_prism([(xa, z_top(xa) + d0), (xb, z_top(xb) + d0), (xb, z_top(xb) + d1), (xa, z_top(xa) + d1)], ya, yb, m)
    if not HOUSE_D:
        slope(vx0 - 0.06, vx1 + 0.06, -0.02, 0.11, vy0 - 0.06, vy0, M['marco'], v)
        slope(vx0 - 0.06, vx1 + 0.06, -0.02, 0.11, vy1, vy1 + 0.06, M['marco'], v)
        slope(vx0 - 0.06, vx0, -0.02, 0.11, vy0, vy1, M['marco'], v)
        slope(vx1, vx1 + 0.06, -0.02, 0.11, vy0, vy1, M['marco'], v)
        slope(vx0, vx1, 0.07, 0.08, vy0, vy1, M['vidrio'], vg)
    # solatubes: cúpula en cubierta, tubo y difusor en el techo
    for (sx, sy) in SOLATUBES:
        v.cyl(sx, sy, 0.17, z_under(sx) - 0.02, z_top(sx) + 0.10, M['metal'], 24)
        vg.cyl(sx, sy, 0.21, z_top(sx) + 0.10, z_top(sx) + 0.24, M['vidrio'], 24)
        v.cyl(sx, sy, 0.19, z_under(sx) - 0.05, z_under(sx) - 0.02, M['difusor'], 24)
    for cx in (7.22, 7.37, 7.52):
        v.cyl(cx, 4.27, 0.065, z_under(cx) - 0.05, 8.05, M['metal'], 16)
    v.build("Velux, solatubes y ventilaciones", C_ROOF); vg.build("Velux y solatubes vidrios", C_ROOF)

# ================================================================= ENTORNO
def entorno():
    Ya, Yb = -16.0, 20.0
    s = MB()
    s.prism([(xf(Ya) - 1.6, Ya), (xf(Ya), Ya), (xf(Yb), Yb), (xf(Yb) - 1.6, Yb)], -0.15, 0.0, M['acera'])
    s.prism([(-14.0, Ya), (xf(Ya) - 1.6, Ya), (xf(Yb) - 1.6, Yb), (-14.0, Yb)], -0.35, -0.15, M['asfalto'])
    s.prism([(-15.6, Ya), (-14.0, Ya), (-14.0, Yb), (-15.6, Yb)], -0.15, 0.0, M['acera'])
    s.cyl(*F(0.30, -0.35), 0.22, 0.0, 0.50, M['puerta_ext'], 20); s.cyl(*F(0.30, -0.35), 0.30, 0.5, 1.2, M['planta'], 12)
    s.build("Calle y aceras", C_CALLE)
    p = MB(); p.box(X_OUT, 8.40, -6.0, 11.0, 0.0, 5.60, M['piedra_muro']); p.build("Muro de piedra trasero", C_VEC)
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
    r = MB(); r.box(8.40, 14.0, -6.0, 11.0, 0.0, 5.60, top_rule(M['vecino_cub'], M['vecino'])); r.build("Colindante trasero", C_VEC)

# ================================================================= cámaras y render
def camera(name, loc, target=None, lens=28, ortho=None):
    cd = bpy.data.cameras.new(name); cd.clip_end = 300; cd.sensor_width = 36
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    else: cd.lens = lens
    ob = bpy.data.objects.new(name, cd); ob.location = loc
    if target is not None: ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    C_CAM.objects.link(ob); return ob

def setup_render():
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try: scene.render.engine = eng; break
        except Exception: pass
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    for attr, val in (('taa_render_samples', 48), ('shadow_pool_size', '1024'), ('use_raytracing', True)):
        try: setattr(scene.eevee, attr, val)
        except Exception: pass
    try: scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception: pass
    w = bpy.data.worlds.new("Cielo"); scene.world = w
    try: w.use_nodes = True
    except Exception: pass
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs['Color'].default_value = (*srgb('#C4D3E0'), 1); bg.inputs['Strength'].default_value = 0.65
    sd = bpy.data.lights.new("Sol", 'SUN'); sd.energy = 4.5; sd.angle = math.radians(1.5); sd.color = (1.0, 0.96, 0.9)
    so = bpy.data.objects.new("Sol", sd)
    so.rotation_euler = Vector((0.55, 0.40, -0.75)).to_track_quat('-Z', 'Y').to_euler()
    C_CAM.objects.link(so)
    cx, cy = 3.9, 2.33
    fx, fy = F(FL / 2, -25.0)
    scene.camera = camera("Cámara calle", (-12.5, -3.2, 1.70), (0.6, 2.5, 4.9), lens=24)
    camera("Cámara alzado", (fx, fy, 4.8), (fx + FN.x, fy + FN.y, 4.8), ortho=13.0)
    camera("Cámara aérea", (-10.5, -9.5, 14.0), (3.6, 2.3, 4.0), lens=32)
    camera("Cámara interior salón", (0.70, 1.15, 1.60), (6.4, 3.9, 1.0), lens=15)
    camera("Cámara interior escalera", (3.0, 1.9, 1.25), (6.3, 4.0, 2.0), lens=18)
    camera("Cámara interior planta primera", (0.75, 0.75 if P1V == "B" else 2.0, LV["P1"] + 1.55), (5.4, 3.6, LV["P1"] + 0.9), lens=15)
    if NEW_ATTIC:
        camera("Cámara interior casetón", (2.95, 1.95, LV["BC"] + 1.55), (0.1, 3.1, LV["BC"] + 1.2), lens=16)
        camera("Cámara interior dormitorio 2", (6.45, 2.25, LV["BC"] + 1.45), (3.9, 3.9, LV["BC"] + 0.95), lens=16)
    elif HOUSE_D:
        camera("Cámara interior casetón", (2.92, 1.30, LV["BC"] + 1.55), (0.1, 2.5, LV["BC"] + 1.25), lens=16)
        camera("Cámara interior dormitorio 2", (4.85, 2.70, LV["BC"] + 1.50), (6.9, 3.36, LV["BC"] + 1.55), lens=15)
    else:
        camera("Cámara interior casetón", (2.92, 1.25, LV["BC"] + 1.55), (0.1, 2.5, LV["BC"] + 1.25), lens=16)
        camera("Cámara interior dormitorio 2", (4.9, 2.2, LV["BC"] + 1.55), (6.9, 4.1, LV["BC"] + 0.8), lens=16)
    # sección por la escalera al ático: mira hacia -X y recorta el muro del fondo
    sec = camera("Cámara sección escalera", (9.0, 1.75, 4.55), (8.0, 1.75, 4.55), ortho=4.6)
    sec.data.clip_start = 9.0 - 7.45
    for lv in ("PB", "P1", "BC"):
        z = LV[lv]
        camera(f"Cámara {lv} 3D", (2.9, -3.6, z + 11.0), (3.9, 2.3, z + 0.3), lens=26)
        camera(f"Cámara {lv} planta", (cx, cy, z + 25.0), None, ortho=9.2)
    comprobacion_escalera()

def comprobacion_escalera():
    """Persona de 1.75 m en el peldaño 3 del tramo del fondo y cota de altura libre (solo para la sección)."""
    c = new_coll("Comprobación escalera", C_CAM)
    if HOUSE_D:   # en D el canto del forjado queda sobre el peldaño 1
        z3 = LV["P1"] + 1 * S2_R; yc = S2_Y0 - 0.5 * S2_D; techo = LV["BC"] - SLAB
    else:
        z3 = LV["P1"] + 3 * S2_R; yc = S2_Y0 - 2.5 * S2_D
        techo = (LV["BC"] - SLAB) if not NEW_ATTIC else z_under(X_IN)
    p = MB(); person(p, 7.15, yc, z3, -90, 'h'); p.build("Persona en el peldaño 3", c)
    red = basic('Cota', '#D23C2C', 0.5)
    k = MB(); k.box(7.20, 7.24, yc + 0.32, yc + 0.35, z3, techo, red)
    for zz in (z3, techo): k.box(7.20, 7.24, yc + 0.24, yc + 0.43, zz - 0.01, zz + 0.01, red)
    k.build("Cota altura libre", c)
    cu = bpy.data.curves.new("Cota", 'FONT')
    cu.body = f"{techo - z3:.2f} m libres".replace('.', ','); cu.size = 0.16; cu.align_y = 'CENTER'
    cu.materials.append(red)
    ob = bpy.data.objects.new("Texto cota", cu)
    ob.location = (7.30, yc + 0.47, (z3 + techo) / 2); ob.rotation_euler = (math.pi / 2, 0, math.pi / 2)
    c.objects.link(ob)
    c.hide_render = True

planta_baja()
planta_primera()
bajo_cubierta()
facade_carpentry()
cubierta()
entorno()
personas()
setup_render()
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print("GUARDADO", BLEND)
