import zipfile
import xml.etree.ElementTree as ET
import bpy
import bmesh
from mathutils import Vector
from collections import defaultdict


def create_material(rgb):
    name = f"Color_{rgb}"
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = [v/255 for v in rgb] + [1.0]
    return mat


def create_bbox(min_xyz, max_xyz, name="Color_BBox"):
    center = (min_xyz + max_xyz) / 2
    size = max_xyz - min_xyz
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    bbox = bpy.context.active_object
    bbox.name = name
    bbox.scale = size / 2
    return bbox


def import_3mf(filepath):
    with zipfile.ZipFile(filepath, 'r') as archive:
        model_data = archive.read('3D/3dmodel.model')

    root = ET.fromstring(model_data)
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

    objects = {}
    colors = {}

    # Parse color groups
    for res in root.findall('.//m:resources/*', ns):
        if res.tag.endswith('color') or res.tag.endswith('colorgroup'):
            group_id = res.attrib['id']
            colors[group_id] = []
            for col in res:
                rgb = tuple(int(col.attrib['color'][i:i+2], 16) for i in (1, 3, 5))
                colors[group_id].append(rgb)

    # Parse objects and build geometry
    for obj in root.findall('.//m:object', ns):
        vertices = []
        faces = []
        face_colors = []

        mesh = obj.find('./m:mesh', ns)
        for v in mesh.findall('./m:vertices/m:vertex', ns):
            vertices.append(Vector((float(v.attrib['x']), float(v.attrib['y']), float(v.attrib['z']))) )

        for tri in mesh.findall('./m:triangles/m:triangle', ns):
            idxs = [int(tri.attrib[k]) for k in ('v1', 'v2', 'v3')]
            color = None
            if 'pid' in tri.attrib and 'p1' in tri.attrib:
                group_id = tri.attrib['pid']
                color_idx = int(tri.attrib['p1'])
                color = colors.get(group_id, [])[color_idx]
            faces.append(idxs)
            face_colors.append(color)

        # Create mesh
        mesh_data = bpy.data.meshes.new("ImportedMesh")
        mesh_data.from_pydata(vertices, [], faces)
        obj_data = bpy.data.objects.new("ImportedObject", mesh_data)
        bpy.context.collection.objects.link(obj_data)

        # Assign materials and color faces
        mat_slots = {}
        mesh_data.materials.clear()
        for color in filter(None, set(face_colors)):
            mat = create_material(color)
            mesh_data.materials.append(mat)
            mat_slots[color] = len(mesh_data.materials) - 1

        color_verts = set()
        for i, poly in enumerate(mesh_data.polygons):
            color = face_colors[i]
            if color:
                poly.material_index = mat_slots[color]
                color_verts.update(mesh_data.vertices[v] for v in poly.vertices)

        if color_verts:
            coords = [v.co for v in color_verts]
            min_xyz = Vector(map(min, zip(*coords)))
            max_xyz = Vector(map(max, zip(*coords)))
            create_bbox(min_xyz, max_xyz)

        obj_data.select_set(True)
        bpy.context.view_layer.objects.active = obj_data
