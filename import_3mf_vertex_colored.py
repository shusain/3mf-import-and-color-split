import zipfile
import xml.etree.ElementTree as ET
import bpy
from mathutils import Vector
from collections import defaultdict
import colorsys

CONST_FILAMENTS = [
    "", "4", "8", "0C", "1C", "2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "AC", "BC", "CC", "DC",
    "EC", "0FC", "1FC", "2FC", "3FC", "4FC", "5FC", "6FC", "7FC", "8FC", "9FC", "AFC", "BFC", "CFC", "DFC", "EFC",
]

def blend_colors(colors):
    r = sum(c[0] for c in colors) / len(colors)
    g = sum(c[1] for c in colors) / len(colors)
    b = sum(c[2] for c in colors) / len(colors)
    return (r, g, b)

def rgb_distance(c1, c2):
    return ((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2) ** 0.5

def find_similar_color(color, color_list, threshold):
    for existing in color_list:
        if rgb_distance(existing, color) <= threshold:
            return existing
    return None

def create_material_from_rgb(rgb):
    name = f"RGBColor_{rgb}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = [v / 255 for v in rgb] + [1.0]
    return mat

def create_bbox(min_xyz, max_xyz, name="Color_BBox"):
    center = (min_xyz + max_xyz) / 2
    size = max_xyz - min_xyz

    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    bbox = bpy.context.active_object
    bbox.name = name
    bbox.scale = size
    return bbox

def apply_boolean_modifier(obj, bbox, operation, name, apply_now=False):
    result_obj = obj.copy()
    result_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(result_obj)
    result_obj.name = name

    mod = result_obj.modifiers.new(name=f"{operation}_bbox", type='BOOLEAN')
    mod.object = bbox
    mod.operation = operation


    # Transfer materials
    result_obj.data.materials.clear()
    for mat in obj.data.materials:
        result_obj.data.materials.append(mat)

    if apply_now:
        bpy.context.view_layer.objects.active = result_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # Triangulate the result mesh
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.object.mode_set(mode='OBJECT')
        
    return result_obj

def import_3mf(filepath, apply_modifiers=False, color_similarity_threshold=10):
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001

    with zipfile.ZipFile(filepath, 'r') as archive:
        model_data = archive.read('3D/Objects/object_2.model')
        try:
            slice_config = archive.read('Metadata/slice_info.config')
            config_root = ET.fromstring(slice_config)
            filament_map = {}
            for filament in config_root.findall('.//filament'):
                idx = filament.attrib['id']
                color_hex = filament.attrib['color'].lstrip('#')
                rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
                filament_map[idx] = rgb
        except KeyError:
            filament_map = {}

    root = ET.fromstring(model_data)
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

    for obj in root.findall('.//m:object', ns):
        vertices = []
        faces = []
        face_colors = []
        vertex_color_assignments = defaultdict(list)

        mesh = obj.find('./m:mesh', ns)
        for v in mesh.findall('./m:vertices/m:vertex', ns):
            vertices.append(Vector((float(v.attrib['x']), float(v.attrib['y']), float(v.attrib['z']))))

        color_palette = []
        merged_color_map = {}

        for tri in mesh.findall('./m:triangles/m:triangle', ns):
            idxs = [int(tri.attrib[k]) for k in ('v1', 'v2', 'v3')]
            color_id = tri.attrib.get('paint_color')
            rgb = (255, 0, 255)

            if color_id:
                segments = [color_id[i:i+2] for i in range(0, len(color_id), 2)]
                filament_ids = [str(CONST_FILAMENTS.index(s)) for s in segments if s in CONST_FILAMENTS]
                rgbs = [filament_map.get(fid, (255, 0, 255)) for fid in filament_ids]
                rgb = blend_colors(rgbs) if rgbs else (255, 0, 255)

                for i in idxs:
                    vertex_color_assignments[i].append(rgb)

            merged = find_similar_color(rgb, color_palette, color_similarity_threshold)
            if merged:
                rgb = merged
            else:
                color_palette.append(rgb)

            face_colors.append(rgb)
            faces.append(idxs)

        mesh_data = bpy.data.meshes.new("ImportedMesh")
        mesh_data.from_pydata(vertices, [], faces)
        obj_data = bpy.data.objects.new("ImportedObject", mesh_data)
        bpy.context.collection.objects.link(obj_data)

        mesh_data.materials.clear()
        material_index_map = {}

        for rgb in color_palette:
            mat = create_material_from_rgb(rgb)
            mesh_data.materials.append(mat)
            material_index_map[rgb] = len(mesh_data.materials) - 1

        color_verts = set()
        for i, poly in enumerate(mesh_data.polygons):
            rgb = face_colors[i]
            poly.material_index = material_index_map[rgb]
            color_verts.update(mesh_data.vertices[v] for v in poly.vertices if v.index in vertex_color_assignments)

        if color_verts:
            coords = [v.co for v in color_verts]
            min_xyz = Vector((
                min(v.x for v in coords),
                min(v.y for v in coords),
                min(v.z for v in coords),
            ))
            max_xyz = Vector((
                max(v.x for v in coords),
                max(v.y for v in coords),
                max(v.z for v in coords),
            ))
            bbox = create_bbox(min_xyz, max_xyz)
            apply_boolean_modifier(obj_data, bbox, 'INTERSECT', 'Colored_Region', apply_now=apply_modifiers)
            apply_boolean_modifier(obj_data, bbox, 'DIFFERENCE', 'Uncolored_Region', apply_now=apply_modifiers)
            bbox.hide_viewport = True
            bbox.hide_render = True

        obj_data.select_set(True)
        bpy.context.view_layer.objects.active = obj_data