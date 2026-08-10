#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;

namespace MeshyAgenticPipeline
{
    /// <summary>
    /// Importer de Editor C# para Unity que automatiza la ingesta de modelos 3D
    /// procedentes de Meshy API / OpenUSD / TRELLIS en la arquitectura agéntica.
    /// </summary>
    public class MeshyUnityAssetImporter : AssetPostprocessor
    {
        private static readonly string MeshyImportFolder = "Assets/MeshyGeneratedAssets/";

        [MenuItem("Meshy AI/Import Pending 3D Assets")]
        public static void ImportPendingAssets()
        {
            if (!Directory.Exists(MeshyImportFolder))
            {
                Directory.CreateDirectory(MeshyImportFolder);
            }

            AssetDatabase.Refresh();
            string[] files = Directory.GetFiles(MeshyImportFolder, "*.glb", SearchOption.AllDirectories);

            foreach (string file in files)
            {
                ProcessMeshyAsset(file);
            }
        }

        private static void ProcessMeshyAsset(string assetPath)
        {
            GameObject importedObj = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (importedObj == null) return;

            string prefabPath = Path.ChangeExtension(assetPath, ".prefab");
            
            // Crear una instancia temporal en la escena para configurar el Prefab
            GameObject instance = Object.Instantiate(importedObj);
            instance.name = Path.GetFileNameWithoutExtension(assetPath);

            // Configurar LODGroup si existen submallas de LOD
            SetupLODGroup(instance);

            // Generar los colliders convexos para VR
            SetupVRColliders(instance);

            // Guardar Prefab optimizado
            PrefabUtility.SaveAsPrefabAsset(instance, prefabPath);
            Object.DestroyImmediate(instance);

            Debug.Log($"✅ Prefab de Unity VR-Ready generado exitosamente: {prefabPath}");
        }

        private static void SetupLODGroup(GameObject rootObj)
        {
            LODGroup lodGroup = rootObj.GetComponent<LODGroup>();
            if (lodGroup == null)
            {
                lodGroup = rootObj.AddComponent<LODGroup>();
            }

            Transform lod0Trans = rootObj.transform.Find("Mesh_LOD0");
            Transform lod1Trans = rootObj.transform.Find("Mesh_LOD1");

            if (lod0Trans != null && lod1Trans != null)
            {
                LOD[] lods = new LOD[2];
                lods[0] = new LOD(0.6f, lod0Trans.GetComponentsInChildren<Renderer>());
                lods[1] = new LOD(0.15f, lod1Trans.GetComponentsInChildren<Renderer>());
                lodGroup.SetLODs(lods);
                lodGroup.RecalculateBounds();
            }
        }

        private static void SetupVRColliders(GameObject rootObj)
        {
            MeshFilter[] meshFilters = rootObj.GetComponentsInChildren<MeshFilter>();
            foreach (MeshFilter mf in meshFilters)
            {
                if (mf.gameObject.GetComponent<Collider>() == null)
                {
                    MeshCollider mc = mf.gameObject.AddComponent<MeshCollider>();
                    mc.convex = true; // Convex hull para física eficiente en VR (Meta Quest / OpenXR)
                }
            }
        }
    }
}
#endif
