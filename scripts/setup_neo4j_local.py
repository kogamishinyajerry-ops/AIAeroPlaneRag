"""
Neo4j Portable Setup Script for Windows

Downloads and configures Neo4j Community Edition for local use
without Docker Desktop.
"""
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

NEO4J_VERSION = "5.26.0"
NEO4J_URL = f"https://dist.neo4j.org/neo4j-community-{NEO4J_VERSION}-windows.zip"
INSTALL_DIR = Path("C:/neo4j")

print("=" * 60)
print(" Neo4j Community Setup for Windows")
print("=" * 60)
print(f"\nThis will install Neo4j {NEO4J_VERSION} to: {INSTALL_DIR}")
print("\nIMPORTANT: Requires Java 17+ to be installed.")
print("You can download Java from: https://adoptium.net/")
print("\nContinue? (y/n): ", end="")

if input().lower() != 'y':
    print("Cancelled.")
    sys.exit(0)

# Create install directory
INSTALL_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(INSTALL_DIR)

# Download Neo4j
print(f"\n[DOWNLOAD] Downloading Neo4j {NEO4J_VERSION}...")
zip_file = INSTALL_DIR / f"neo4j-community-{NEO4J_VERSION}-windows.zip"

if not zip_file.exists():
    try:
        urllib.request.urlretrieve(NEO4J_URL, zip_file)
        print("[OK] Download complete")
    except Exception as e:
        print(f"[ERROR] Download failed: {e}")
        print("\nPlease download manually from:")
        print(f"  {NEO4J_URL}")
        sys.exit(1)
else:
    print("[OK] Already downloaded")

# Extract
print("\n[EXTRACT] Extracting files...")
try:
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(INSTALL_DIR)
    print("[OK] Extraction complete")
except Exception as e:
    print(f"[ERROR] Extraction failed: {e}")
    sys.exit(1)

# Configure
conf_file = INSTALL_DIR / "conf" / "neo4j.conf"
if conf_file.exists():
    print("\n[CONFIG] Updating configuration...")
    with open(conf_file, "a", encoding="utf-8") as f:
        f.write("\n# Auto-generated configuration\n")
        f.write("dbms.default_listen_address=0.0.0.0\n")
        f.write("dbms.security.auth_username=neo4j\n")
        f.write("dbms.security.auth_password=aeropower_rag_2026\n")
    print("[OK] Configuration updated")
else:
    print(f"[WARN] Config file not found: {conf_file}")

# Create start script
start_script = INSTALL_DIR / "start_neo4j.bat"
with open(start_script, "w", encoding="utf-8") as f:
    f.write('@echo off\n')
    f.write('cd /d "%~dp0bin"\n')
    f.write('neo4j.bat console\n')

print(f"\n[DONE] Neo4j installed to: {INSTALL_DIR}")
print("\nNext steps:")
print("1. Ensure Java 17+ is installed")
print("2. Start Neo4j: double-click start_neo4j.bat")
print("3. Or run from command line:")
print(f"   {INSTALL_DIR}\\bin\\neo4j.bat console")
print("\n4. Access Neo4j Browser: http://localhost:7474")
print("   User: neo4j")
print("   Password: aeropower_rag_2026")

input("\nPress Enter to exit...")
