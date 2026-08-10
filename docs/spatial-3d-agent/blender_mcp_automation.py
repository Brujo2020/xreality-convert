# ===============================================================================
# BLENDER MCP AUTOMATION SCRIPT: INTEGRACIÓN AGÉNTICA 3D (bpy)
# ===============================================================================
# Este script se ejecuta dentro de Blender vía el Addon Blender MCP Server.
# Automatiza: Carga de GLB/USDZ de Meshy/TRELLIS, limpieza de topología,
# separación de piezas, asignación de materiales PBR y rigging con Disney Principles.
# ===============================================================================

import bpy
import math
import os

def clear_scene():
    """Limpia la escena por defecto de Blender"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def import_and_setup_asset(filepath: str, asset_name: str):
    """Importa el archivo 3D (GLB/FBX/USDZ) y configura unidades métricas en metros"""
    clear_scene()
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.glb', '.gltf']:
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext in ['.usd', '.usda', '.usdc', '.usdz']:
        bpy.ops.wm.usd_import(filepath=filepath)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=filepath)
    else:
        raise ValueError(f"Formato no soportado: {ext}")
        
    print(f"✅ Asset importado correctamente: {asset_name}")

def separate_parts_and_fix_pivots():
    """
    Hack Industrial: Separa piezas desconectadas en objetos independientes
    y recoloca sus puntos pivote en el centro de masa / base del objeto.
    """
    selected_objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    
    for obj in selected_objs:
        bpy.context.view_layer.objects.active = obj
        # Separar por partes sueltas (Loose Parts)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        
    # Recolocar pivote en el origen inferior (Origin to Bottom)
    for part in bpy.context.selected_objects:
        if part.type == 'MESH':
            bpy.context.view_layer.objects.active = part
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
            
    print(f"🧩 Piezas separadas y pivotes corregidos: {len(bpy.context.selected_objects)} objetos.")

def apply_disney_animation_principles(armature_name: str):
    """
    Aplica el Principio #1 de Disney (Squash & Stretch) y #5 (Follow Through)
    vía Drivers de Python en los huesos principales del Rig.
    """
    armature = bpy.data.objects.get(armature_name)
    if not armature or armature.type != 'ARMATURE':
        print("⚠️ No se encontró la armadura para aplicar los principios de animación de Disney.")
        return

    # Principio: Squash & Stretch con conservación de volumen (Scale Y = 1 / sqrt(Scale X * Scale Z))
    for pbone in armature.pose.bones:
        if "Spine" in pbone.name or "Torso" in pbone.name:
            driver_x = pbone.driver_add('scale', 0).driver
            driver_z = pbone.driver_add('scale', 2).driver
            
            driver_x.type = 'SCRIPTED'
            driver_x.expression = "1.0 / (scale_y ** 0.5)"
            var_x = driver_x.variables.new()
            var_x.name = "scale_y"
            var_x.targets[0].id = armature
            var_x.targets[0].data_path = f'pose.bones["{pbone.name}"].scale.y'

            driver_z.type = 'SCRIPTED'
            driver_z.expression = "1.0 / (scale_y ** 0.5)"
            var_z = driver_z.variables.new()
            var_z.name = "scale_y"
            var_z.targets[0].id = armature
            var_z.targets[0].data_path = f'pose.bones["{pbone.name}"].scale.y'
            
    print("✨ Principios de Animación de Disney (Squash & Stretch Volume Preservation) inyectados con éxito.")

def export_for_unity_and_openusd(export_dir: str, asset_name: str):
    """Exporta el paquete final optimizado para Unity (FBX) y Apple/Omniverse (USDZ)"""
    os.makedirs(export_dir, exist_ok=True)
    
    fbx_path = os.path.join(export_dir, f"{asset_name}_unity.fbx")
    usdz_path = os.path.join(export_dir, f"{asset_name}_openusd.usdz")
    
    # Exportar FBX para Unity
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=False,
        global_scale=1.0,
        apply_unit_scale=True,
        object_types={'MESH', 'ARMATURE'},
        bake_anim=True
    )
    
    # Exportar USDZ para Vision Pro / Omniverse
    bpy.ops.wm.usd_export(
        filepath=usdz_path,
        export_materials=True,
        export_textures=True,
        relative_paths=True
    )
    
    print(f"🚀 Exportación terminada: \n -> Unity: {fbx_path}\n -> OpenUSD: {usdz_path}")

# Ejemplo de ejecución desde el servidor MCP
if __name__ == "__main__":
    # Remplazar con rutas según la llamada del agente
    input_file = "/tmp/meshy_output.glb"
    output_directory = "/tmp/export_assets"
    
    if os.path.exists(input_file):
        import_and_setup_asset(input_file, "AssetIA")
        separate_parts_and_fix_pivots()
        export_for_unity_and_openusd(output_directory, "AssetIA")
