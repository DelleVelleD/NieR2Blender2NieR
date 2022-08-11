import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ...utils.visibilitySwitcher import enableVisibilitySelector
from ...utils.util import setExportFieldsFromImportFile

class ImportNierMot(bpy.types.Operator, ImportHelper):
    '''Load a Nier:Automata MOT File.'''
    bl_idname = "import_scene.mot_data"
    bl_label = "Import MOT Data"
    bl_options = {'PRESET'}
    filename_ext = ".mot"
    filter_glob: StringProperty(default="*.mot", options={'HIDDEN'})

    def execute(self, context):
        setExportFieldsFromImportFile(self.filepath)
        enableVisibilitySelector()
        from . import mot_importer
        return mot_importer.main(self.filepath)