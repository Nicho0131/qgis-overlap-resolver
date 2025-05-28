import os
import shutil
import zipfile

def create_plugin_package():
    # Create plugin directory
    plugin_dir = "overlap_resolver"
    if os.path.exists(plugin_dir):
        shutil.rmtree(plugin_dir)
    os.makedirs(plugin_dir)

    # List of files to include
    files_to_copy = [
        "metadata.txt",
        "__init__.py",
        "overlap_resolver.py",
        "overlap_resolver_dialog.py",
        "overlap_resolver_dialog.ui",
        "README.md",
        "requirements.txt"
    ]

    # Copy files to plugin directory
    for file in files_to_copy:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(plugin_dir, file))

    # Create ZIP file
    zip_filename = "overlap_resolver.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(plugin_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(plugin_dir))
                zipf.write(file_path, arcname)

    print(f"Plugin package created: {zip_filename}")
    print(f"Plugin directory created: {plugin_dir}")
    print("\nTo install the plugin:")
    print("1. Copy the 'overlap_resolver' folder to your QGIS plugins directory:")
    print("   - Windows: C:\\Users\\<username>\\AppData\\Roaming\\QGIS\\QGIS3\\profiles\\default\\python\\plugins\\")
    print("   - Linux: ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/")
    print("   - macOS: ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/")
    print("2. Restart QGIS")
    print("3. Enable the plugin in QGIS Plugin Manager")

if __name__ == "__main__":
    create_plugin_package() 