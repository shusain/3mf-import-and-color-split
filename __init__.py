bl_info = {
    "name": "Bambu 3MF Importer",
    "author": "Shaun",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "location": "File > Import",
    "description": "Import 3MF files from Bambu Studio with vertex or material coloring",
    "category": "Import-Export",
}

import bpy
from . import import_3_mf_color, import_3mf_vertex_colored

class ImportBambu3MFMaterial(bpy.types.Operator):
    bl_idname = "import_scene.bambu_3mf_material"
    bl_label = "Import Bambu 3MF (Material Coloring)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        import_3_mf_color.import_3mf(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class ImportBambu3MFVertexColor(bpy.types.Operator):
    bl_idname = "import_scene.bambu_3mf_vertex"
    bl_label = "Import Bambu 3MF (Vertex Coloring)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        import_3mf_vertex_colored.import_3mf_vertex_colored(self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_func_import(self, context):
    self.layout.operator(ImportBambu3MFMaterial.bl_idname, text="Bambu 3MF (.3mf) - Material Colors")
    self.layout.operator(ImportBambu3MFVertexColor.bl_idname, text="Bambu 3MF (.3mf) - Vertex Colors")


classes = (
    ImportBambu3MFMaterial,
    ImportBambu3MFVertexColor,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
