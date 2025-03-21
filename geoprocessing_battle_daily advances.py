import processing
from qgis.core import QgsProject, QgsVectorLayer, QgsProcessingFeedback, QgsField
from PyQt5.QtCore import QVariant
from datetime import date, timedelta

def generate_february_dates(year):
    """Generate a list of all dates in February for a given year."""
    start_date = date(year, 2, 1)
    end_date = date(year, 3, 1)
    delta = timedelta(days=1)
    
    return [(start_date + delta * i).strftime("%Y-%m-%d") for i in range((end_date - start_date).days)]

def fix_geometry(layer):
    """Fixes invalid geometries in a given layer before processing."""
    fixed_result = processing.run(
        "native:fixgeometries",
        {"INPUT": layer, "OUTPUT": "memory:"},
        feedback=QgsProcessingFeedback()
    )
    return fixed_result["OUTPUT"]

def dissolve_layer(layer_name):
    """Fixes geometries, dissolves all polygons, and assigns the correct date attribute."""
    
    layers = QgsProject.instance().mapLayersByName(layer_name)
    if not layers:
        print(f"❌ Error: Layer '{layer_name}' not found. Skipping.")
        return None

    layer = layers[0]
    fixed_layer = fix_geometry(layer)

    dissolved_result = processing.run(
        "native:dissolve",
        {"INPUT": fixed_layer, "FIELD": [], "OUTPUT": "memory:"},
        feedback=QgsProcessingFeedback()
    )

    dissolved_layer = dissolved_result["OUTPUT"]
    if not isinstance(dissolved_layer, QgsVectorLayer):
        print(f"❌ Error: Dissolve failed for {layer_name}. Skipping.")
        return None

    # Ensure "date" field exists
    provider = dissolved_layer.dataProvider()
    existing_fields = [field.name() for field in provider.fields()]
    
    if "date" not in existing_fields:
        provider.addAttributes([QgsField("date", QVariant.String)])
        dissolved_layer.updateFields()

    # Extract date from layer name
    try:
        date_value = layer_name.split("_")[1]  # Extract YYYY-MM-DD from 'liveuamap_YYYY-MM-DD'
    except IndexError:
        print(f"⚠️ Warning: Could not extract date from '{layer_name}'. Skipping.")
        return None

    # Assign the date field correctly using direct editing
    dissolved_layer.startEditing()
    for feature in dissolved_layer.getFeatures():
        feature.setAttribute(dissolved_layer.fields().lookupField("date"), date_value)
        dissolved_layer.updateFeature(feature)
    dissolved_layer.commitChanges()

    # Rename output layer
    new_layer_name = f"{layer_name}_merged"
    dissolved_layer.setName(new_layer_name)

    QgsProject.instance().addMapLayer(dissolved_layer)
    print(f"✅ Processed & added '{new_layer_name}' to the project.")

    return dissolved_layer

def merge_layers():
    """Finds all 'liveuamap_YYYY-MM-DD_merged' layers and merges them into one."""
    
    project = QgsProject.instance()
    all_layers = project.mapLayers().values()

    # Filter layers that match "liveuamap_YYYY-MM-DD_merged"
    layers_to_merge = [layer for layer in all_layers if layer.name().startswith("liveuamap_") and layer.name().endswith("_merged")]

    if not layers_to_merge:
        print("❌ No 'liveuamap_YYYY-MM-DD_merged' layers found.")
        return None

    print(f"🔄 Merging {len(layers_to_merge)} layers...")

    # Run Merge tool
    merged_result = processing.run(
        "native:mergevectorlayers",
        {"LAYERS": layers_to_merge, "CRS": layers_to_merge[0].crs(), "OUTPUT": "memory:"},
        feedback=QgsProcessingFeedback()
    )

    merged_layer = merged_result["OUTPUT"]

    if not isinstance(merged_layer, QgsVectorLayer):
        print("❌ Error: Merge operation failed.")
        return None

    # Rename output layer
    merged_layer.setName("liveuamap_merged_all")

    QgsProject.instance().addMapLayer(merged_layer)
    print("✅ Merged layer 'liveuamap_merged_all' added to the project.")

    return merged_layer

# 🔹 Generate a list of February dates
february_dates = generate_february_dates(2025)

# 🔄 Loop through each date and process the corresponding layer
for date_str in february_dates:
    layer_name = f"liveuamap_{date_str}"
    dissolved_layer = dissolve_layer(layer_name)

    if dissolved_layer:
        print(f"✅ Successfully processed: {layer_name}_merged")
    else:
        print(f"⚠️ Skipped '{layer_name}' due to errors.")

# 🔄 Merge all dissolved layers
merge_layers()
