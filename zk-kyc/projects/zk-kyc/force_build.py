"""
Force build by removing read-only attributes from artifacts directory.
Solves Windows PermissionError: [WinError 5] Access is denied.
"""
import os
import stat
import shutil
from pathlib import Path

def remove_readonly(func, path, excinfo):
    """Error handler for shutil.rmtree to handle read-only files on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

# Remove credential_manager artifacts with force
artifact_dir = Path(__file__).parent / "smart_contracts/artifacts/credential_manager"
if artifact_dir.exists():
    print(f"Removing {artifact_dir} (forcing read-only removal)...")
    shutil.rmtree(artifact_dir, onerror=remove_readonly)
    print("✓ Removed successfully")

# Now run the build
print("\nRunning build...")
os.system("algokit project run build")
