import streamlit as st
import pandas as pd
import plotly.express as px
import subprocess
import json
import os
from datetime import datetime

# --- CONFIGURATION ---
FOLDER_ID = "1kwOoKOrg0mACNyRq1RusjtvJd1L5eavh"
DATA_DIR = "cgm_data"
os.makedirs(DATA_DIR, exist_ok=True)

st.set_page_config(page_title="CGM Analysis - BVC Analytics", layout="wide")

def run_gws(cmd_list):
    try:
        result = subprocess.run(["gws"] + cmd_list, capture_output=True, text=True)
        if result.returncode != 0:
            st.error(f"Erreur GWS : {result.stderr}")
            return None
        return result.stdout.strip()
    except Exception as e:
        st.error(f"Erreur système : {e}")
        return None

def fetch_files():
    query = f"'{FOLDER_ID}' in parents"
    res = run_gws(["drive", "files", "list", "--params", json.dumps({"q": query, "fields": "files(id, name, mimeType)"})])
    if not res: return []
    files = json.loads(res).get("files", [])
    for f in files:
        target_path = os.path.join(DATA_DIR, f['name'])
        if f['mimeType'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            if not os.path.exists(target_path):
                st.info(f"📥 Téléchargement Excel: {f['name']}")
                run_gws(["drive", "files", "get", "--params", json.dumps({"fileId": f['id'], "alt": "media"}), "--output", target_path])
        elif f['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            target_csv = target_path + ".csv"
            if not os.path.exists(target_csv):
                st.info(f"📥 Export Sheet: {f['name']}")
                run_gws(["drive", "files", "export", "--params", json.dumps({"fileId": f['id'], "mimeType": "text/csv"}), "--output", target_csv])
    return True

def load_data():
    all_dfs = []
    files = [os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR) if f.endswith(('.xlsx', '.csv'))]
    for f in files:
        try:
            df = pd.read_csv(f) if f.endswith('.csv') else pd.read_excel(f)
            df.columns = [c.strip() for c in df.columns]
            time_col = next((c for c in df.columns if 'Temps' in c or 'Time' in c), None)
            glucose_col = next((c for c in df.columns if 'Lecture' in c or 'Glucose' in c), None)
            if time_col and glucose_col:
                temp_df = df[[time_col, glucose_col]].copy()
                temp_df.columns = ['Timestamp', 'Glucose']
                temp_df['Timestamp'] = pd.to_datetime(temp_df['Timestamp'], dayfirst=True, errors='coerce')
                temp_df['Glucose'] = pd.to_numeric(temp_df['Glucose'], errors='coerce')
                all_dfs.append(temp_df.dropna())
        except Exception as e: st.warning(f"Erreur sur {f} : {e}")
    if not all_dfs: return pd.DataFrame()
    return pd.concat(all_dfs).sort_values('Timestamp')

# --- LOGIQUE D'AFFICHAGE ---
st.title("📊 Dashboard CGM de Précision")

if st.sidebar.button("🔄 Actualiser depuis Google Drive"):
    fetch_files()
    st.rerun()

data = load_data()

if not data.empty:
    # --- FILTRES ---
    data['Année'] = data['Timestamp'].dt.year
    data['Mois_num'] = data['Timestamp'].dt.month
    data['Mois'] = data['Timestamp'].dt.strftime('%B')
    
    st.sidebar.header("🔍 Filtres Temporels")
    years = sorted(data['Année'].unique(), reverse=True)
    selected_year = st.sidebar.multiselect("Sélectionner l'Année", years, default=years)
    
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    available_months = [m for m in months if m in data['Mois'].unique()]
    selected_month = st.sidebar.multiselect("Sélectionner le Mois", available_months, default=available_months)

    # Filtrage du DataFrame
    filtered_data = data[(data['Année'].isin(selected_year)) & (data['Mois'].isin(selected_month))]
    
    if not filtered_data.empty:
        # Période affichée sous le titre
        start_date = filtered_data['Timestamp'].min().strftime('%d/%m/%Y')
        end_date = filtered_data['Timestamp'].max().strftime('%d/%m/%Y')
        st.markdown(f"**Période analysée :** du `{start_date}` au `{end_date}`")

        # --- KPIs MIS À JOUR ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Moyenne Glycémie", f"{filtered_data['Glucose'].mean():.1f} mg/dL")
        col2.metric("Pic Maximum", f"{filtered_data['Glucose'].max():.0f} mg/dL")
        tir = (len(filtered_data[(filtered_data['Glucose'] >= 70) & (filtered_data['Glucose'] <= 180)]) / len(filtered_data)) * 100
        col3.metric("Temps dans la cible (70-180)", f"{tir:.1f} %")

        # --- GRAPHIQUE plotly ---
        fig = px.line(filtered_data, x='Timestamp', y='Glucose', 
                      title=f"Courbe de Glycémie ({start_date} - {end_date})", 
                      template="plotly_dark")
        fig.add_hline(y=180, line_dash="dash", line_color="orange", annotation_text="Max Cible")
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Min Cible")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Aucune donnée disponible pour cette sélection d'année/mois.")
else:
    st.info("Cliquez sur 'Actualiser' pour charger vos premières données.")
