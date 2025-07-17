import zipfile
import xml.etree.ElementTree as ET
import bpy
from mathutils import Vector
from collections import defaultdict

CONST_FILAMENTS = [
    "", "4", "8", "0C", "1C", "2C", "3C", "4C", "5C", "6C", "7C", "8C", "9C", "AC", "BC", "CC", "DC",
    "EC", "0FC", "1FC", "2FC", "3FC", "4FC", "5FC", "6FC", "7FC", "8FC", "9FC", "AFC", "BFC", "CFC", "DFC", "EFC",
]

def assign_vertex_color_material(obj, vcol_name="Col"):
    mat_name = "VertexColorMaterial"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        # Build node setup
        output = nodes.new(type="ShaderNodeOutputMaterial")
        shader = nodes.new(type="ShaderNodeBsdfPrincipled")
        vcol = nodes.new(type="ShaderNodeVertexColor")
        vcol.layer_name = vcol_name

        links.new(vcol.outputs["Color"], shader.inputs["Base Color"])
        links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    # Assign the material
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def blend_colors(colors):
    r = sum(c[0] for c in colors) / len(colors)
    g = sum(c[1] for c in colors) / len(colors)
    b = sum(c[2] for c in colors) / len(colors)
    return (r, g, b)

def create_bbox(min_xyz, max_xyz, name="Color_BBox"):
    center = (min_xyz + max_xyz) / 2
    size = max_xyz - min_xyz
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    bbox = bpy.context.active_object
    bbox.name = name
    bbox.scale = size
    
    return bbox


def apply_boolean_with_vcol(source_obj, bbox_obj, operation, name, fallback_color=(1.0, 0.0, 1.0, 1.0)):
    # Duplicate mesh
    result_obj = source_obj.copy()
    result_obj.data = source_obj.data.copy()
    bpy.context.collection.objects.link(result_obj)
    result_obj.name = name

    # Add and configure Boolean modifier
    mod = result_obj.modifiers.new(name=f"{operation}_bbox", type='BOOLEAN')
    mod.object = bbox_obj
    mod.operation = operation
    bpy.context.view_layer.objects.active = result_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)

    return result_obj




def import_3mf_vertex_colored(filepath):
    with zipfile.ZipFile(filepath, 'r') as archive:
        model_data = archive.read('3D/Objects/object_2.model')
        try:
            slice_config = archive.read('Metadata/slice_info.config')
            config_root = ET.fromstring(slice_config)
            filament_map = {}
            for filament in config_root.findall('.//filament'):
                idx = filament.attrib['id']
                hex_code = filament.attrib['color'].lstrip('#')
                filament_map[idx] = tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
        except KeyError:
            filament_map = {}

    root = ET.fromstring(model_data)
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

    vertices = []
    faces = []
    vertex_color_assignments = defaultdict(list)

    mesh_node = root.find('.//m:object/m:mesh', ns)
    for v in mesh_node.findall('./m:vertices/m:vertex', ns):
        vertices.append(Vector((float(v.attrib['x']), float(v.attrib['y']), float(v.attrib['z']))))

    for tri in mesh_node.findall('./m:triangles/m:triangle', ns):
        idxs = [int(tri.attrib[k]) for k in ('v1', 'v2', 'v3')]
        faces.append(idxs)

        color_id = tri.attrib.get('paint_color')
        if not color_id:
            continue

        segments = [color_id[i:i+2] for i in range(0, len(color_id), 2)]
        filament_ids = [str(CONST_FILAMENTS.index(s)) for s in segments if s in CONST_FILAMENTS]
        rgbs = [filament_map.get(fid, (255, 0, 255)) for fid in filament_ids]
        avg_rgb = blend_colors(rgbs) if rgbs else (1.0, 0.0, 1.0)

        for i in idxs:
            vertex_color_assignments[i].append(avg_rgb)

    mesh_data = bpy.data.meshes.new("ImportedMesh")
    mesh_data.from_pydata(vertices, [], faces)
    mesh_data.update()

    obj_data = bpy.data.objects.new("ImportedObject", mesh_data)
    bpy.context.collection.objects.link(obj_data)

    color_layer = mesh_data.vertex_colors.new(name="Col")

    color_data = color_layer.data
    for poly in mesh_data.polygons:
        for li, loop_index in enumerate(poly.loop_indices):
            vi = poly.vertices[li]
            if vi in vertex_color_assignments:
                r, g, b = blend_colors(vertex_color_assignments[vi])
                color_data[loop_index].color = (r / 255, g / 255, b / 255, 1.0)
            else:
                color_data[loop_index].color = (1.0, 0.0, 1.0, 1.0)

    if vertex_color_assignments:
        coords = [vertices[i] for i in vertex_color_assignments]
        min_xyz = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
        max_xyz = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
        bbox = create_bbox(min_xyz, max_xyz)


    obj_data.select_set(True)
    bpy.context.view_layer.objects.active = obj_data
    colored = apply_boolean_with_vcol(obj_data, bbox, 'INTERSECT', 'Colored_Region')
    uncolored = apply_boolean_with_vcol(obj_data, bbox, 'DIFFERENCE', 'Uncolored_Region')
    assign_vertex_color_material(obj_data)
    assign_vertex_color_material(colored)
    assign_vertex_color_material(uncolored)


    bbox.hide_viewport = True
    bbox.hide_render = True
    obj_data.hide_viewport = True
    obj_data.hide_render = True




# import_3mf_vertex_colored("/home/shaun/Development/convert-bambu-3mf-to-ply/Mew_3MF.3mf")
