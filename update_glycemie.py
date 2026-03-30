import pandas as pd
import subprocess
import json
import os
from datetime import datetime

# --- CONFIGURATION (Modifiez pour GitHub) ---
REPO_PATH = "/Users/benigmim/Documents/Mon_Projet_Antigravity/Analyse_glycémie/"
FOLDER_ID = "1kwOoKOrg0mACNyRq1RusjtvJd1L5eavh"
DATA_DIR = "cgm_data"
os.makedirs(os.path.join(REPO_PATH, DATA_DIR), exist_ok=True)

def run_cmd(cmd_list, cwd=REPO_PATH):
    res = subprocess.run(cmd_list, capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0: print(f"⚠️ Erreur : {res.stderr}"); return None
    return res.stdout.strip()

def fetch_files():
    print("📥 Récupération des fichiers du Google Drive...")
    query = f"'{FOLDER_ID}' in parents and trashed = false"
    res = run_cmd(["gws", "drive", "files", "list", "--params", json.dumps({"q": query, "fields": "files(id, name, mimeType)"})])
    if not res: return
    files = json.loads(res).get("files", [])
    for f in files:
        target = os.path.join(REPO_PATH, DATA_DIR, f['name'])
        if not os.path.exists(target):
            print(f"   --> Téléchargement de {f['name']}")
            if f['mimeType'] == 'application/vnd.google-apps.spreadsheet':
                run_cmd(["gws", "drive", "files", "export", "--params", json.dumps({"fileId": f['id'], "mimeType": "text/csv"}), "--output", target + ".csv"])
            else:
                run_cmd(["gws", "drive", "files", "get", "--params", json.dumps({"fileId": f['id'], "alt": "media"}), "--output", target])

def process_data():
    print("📊 Compilation des statistiques...")
    all_dfs = []
    data_path = os.path.join(REPO_PATH, DATA_DIR)
    for f in os.listdir(data_path):
        try:
            p = os.path.join(data_path, f)
            df = pd.read_csv(p) if f.endswith('.csv') else pd.read_excel(p)
            df.columns = [c.strip() for c in df.columns]
            t_col = next(c for c in df.columns if 'Temps' in c or 'Time' in c)
            g_col = next(c for c in df.columns if 'Lecture' in c or 'Glucose' in c)
            temp = df[[t_col, g_col]].copy()
            temp.columns = ['t', 'v']
            temp['t'] = pd.to_datetime(temp['t'], dayfirst=True, errors='coerce')
            temp['v'] = pd.to_numeric(temp['v'], errors='coerce')
            all_dfs.append(temp.dropna())
        except: continue
    
    if not all_dfs:
        print("⚠️ Aucune donnée valide trouvée pour construire le graphe !")
        return

    full = pd.concat(all_dfs).sort_values('t')
    stats = {
        "avg": full['v'].mean(),
        "max": int(full['v'].max()),
        "tir": (len(full[(full['v'] >= 70) & (full['v'] <= 180)]) / len(full)) * 100
    }
    # Formate les dates pour le JSON
    points = [{"t": str(row['t']), "v": row['v']} for _, row in full.iterrows()]
    
    with open(os.path.join(REPO_PATH, 'data.json'), 'w') as f:
        json.dump({"stats": stats, "points": points}, f)
    print("✅ data.json généré.")

def sync_github():
    print("🚀 Poussée vers GitHub...")
    run_cmd(["git", "add", "."])
    run_cmd(["git", "commit", "-m", f"Auto-update CGM : {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
    run_cmd(["git", "push", "origin", "main"]) # Ou 'master' selon votre config
    print("✨ Site web mis à jour !")

if __name__ == "__main__":
    fetch_files()
    process_data()
    sync_github()
