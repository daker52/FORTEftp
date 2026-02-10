"""
Build script pro vytvoření .exe souboru z FORTEftp aplikace
Použití: python build_exe.py
"""

import PyInstaller.__main__
import os

# Získat cestu k aktuálnímu adresáři
current_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(current_dir, "icon.ico")  # Volitelné - pokud máte ikonu

# Parametry pro PyInstaller
params = [
    'FORTEftp.py',
    '--name=FORTEftp',
    '--onefile',
    '--windowed',
    '--clean',
    '--icon=' + icon_path,
    '--add-data=icon.ico;.',
    '--add-data=forte_environments.json;.' if os.path.exists('forte_environments.json') else '',
]

# Odstranit prázdné parametry
params = [p for p in params if p]

print("Vytvářím FORTEftp.exe...")
print("Tento proces může trvat několik minut...")

PyInstaller.__main__.run(params)

print("\n✅ Hotovo! Soubor FORTEftp.exe najdete ve složce 'dist'")
