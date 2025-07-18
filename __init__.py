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
    apply_modifiers: bpy.props.BoolProperty(
        name="Apply Boolean Modifiers",
        description="Apply bounding box and boolean modifiers immediately",
        default=True,
    )
    color_similarity_threshold: bpy.props.IntProperty(
        name="Color Similarity Threshold",
        description="Merge filament colors within this RGB distance (0–100)",
        default=20,
        min=0,
        max=100,
    )

    def execute(self, context):
        import_3_mf_color.import_3mf(
            self.filepath,
            apply_modifiers=self.apply_modifiers,
            color_similarity_threshold=self.color_similarity_threshold
        )
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "apply_modifiers")
        layout.prop(self, "color_similarity_threshold")


class ImportBambu3MFVertexColor(bpy.types.Operator):
    bl_idname = "import_scene.bambu_3mf_vertex"
    bl_label = "Import Bambu 3MF (Vertex Coloring)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    apply_boolean: bpy.props.BoolProperty(
        name="Apply Boolean Modifiers",
        description="Apply bounding box and boolean modifiers immediately",
        default=True,
    )

    def execute(self, context):
        import_3mf_vertex_colored.import_3mf_vertex_colored(
            self.filepath,
            apply_boolean=self.apply_boolean
        )
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "apply_boolean")


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
