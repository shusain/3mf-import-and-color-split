import zipfile
import xml.etree.ElementTree as ET
import bpy
from mathutils import Vector
from collections import defaultdict
import colorsys
import fnmatch

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

def create_bbox(min_xyz, max_xyz, name="Color_BBox", padding=0.0):
    if padding > 0.0:
        min_xyz -= Vector((padding, padding, padding))
        max_xyz += Vector((padding, padding, padding))

    center = (min_xyz + max_xyz) / 2
    size = max_xyz - min_xyz

    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    bbox = bpy.context.active_object
    bbox.name = name
    bbox.scale = size
    bbox.select_set(False)
    
    return bbox

def apply_boolean_modifier(obj, bbox, operation, name, apply_now=False):
    result_obj = obj.copy()
    result_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(result_obj)
    result_obj.name = name

    mod = result_obj.modifiers.new(name=f"{operation}_bbox", type='BOOLEAN')
    mod.object = bbox
    mod.operation = operation

    result_obj.data.materials.clear()
    for mat in obj.data.materials:
        result_obj.data.materials.append(mat)

    for i, poly in enumerate(result_obj.data.polygons):
        orig_poly = obj.data.polygons[i] if i < len(obj.data.polygons) else None
        if orig_poly:
            poly.material_index = orig_poly.material_index

    if apply_now:
        bpy.context.view_layer.objects.active = result_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # Triangulate the result mesh
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.object.mode_set(mode='OBJECT')

    result_obj.select_set(True)
    view_layer = bpy.context.view_layer
    view_layer.objects.active = result_obj

    return result_obj

def import_3mf(filepath, apply_modifiers=False, color_similarity_threshold=10, bbox_padding=0.0001):
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001

    with zipfile.ZipFile(filepath, 'r') as archive:
        model_filenames = fnmatch.filter(archive.namelist(), '3D/Objects/*.model')

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

        ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

        for model_filename in model_filenames:
            model_data = archive.read(model_filename)
            root = ET.fromstring(model_data)

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

                for i, poly in enumerate(mesh_data.polygons):
                    rgb = face_colors[i]
                    poly.material_index = material_index_map[rgb]

                if vertex_color_assignments:
                    coords = [vertices[i] for i in vertex_color_assignments]
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
                    bbox_small = create_bbox(min_xyz.copy(), max_xyz.copy(), padding=0.0)
                    bbox_large = create_bbox(min_xyz.copy(), max_xyz.copy(), padding=bbox_padding)
                    apply_boolean_modifier(obj_data, bbox_small, 'INTERSECT', 'Colored_Region', apply_now=apply_modifiers)
                    apply_boolean_modifier(obj_data, bbox_large, 'DIFFERENCE', 'Uncolored_Region', apply_now=apply_modifiers)

                    # Auto hiding the bounding boxes if we are applying modifiers automatically or else leaving them visible
                    if apply_modifiers:
                        bbox_small.hide_viewport = True
                        bbox_small.hide_render = True
                        bbox_large.hide_viewport = True
                        bbox_large.hide_render = True

                obj_data.hide_viewport = True
                # obj_data.select_set(True)
                bpy.context.view_layer.objects.active = obj_data