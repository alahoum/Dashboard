import streamlit as st
import pandas as pd
import plotly.express as px
import requests # Nécessaire pour appeler l'API

# --- CONFIGURATION ---
st.set_page_config(page_title="Dashboard RATP (API Direct)", page_icon="🚽", layout="wide")

# --- 1. CHARGEMENT DES DONNÉES VIA API ---
@st.cache_data
def load_data_from_api():
    # URL officielle de l'API Open Data RATP pour les sanitaires
    # On demande 1000 résultats (rows=1000) pour être sûr de tout avoir
    url = "https://data.ratp.fr/api/records/1.0/search/?dataset=sanitaires-reseau-ratp&rows=1000"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # L'API renvoie une liste d'objets dans 'records'. Chaque objet a ses infos dans 'fields'
            records = data.get('records', [])
            # On extrait juste la partie 'fields' pour faire notre tableau
            clean_records = [r['fields'] for r in records]
            return pd.DataFrame(clean_records)
        else:
            st.error("Erreur de connexion à l'API RATP.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Erreur technique : {e}")
        return pd.DataFrame()

def clean_data(df):
    if df.empty: return df
    df = df.copy()
    
    # 1. Gestion des coordonnées (L'API renvoie souvent une liste [lat, lon] ou séparés)
    # Dans ce dataset spécifique, l'API renvoie souvent 'coord_geo' sous forme [lat, lon] ou string.
    # On vérifie les colonnes disponibles.
    
    if 'coord_geo' in df.columns:
        # Si c'est une liste [lat, lon], on sépare
        # Parfois pandas le voit comme une string, parfois une liste.
        # On assure le coup :
        try:
            # On extrait lat/lon depuis la colonne coord_geo qui est souvent une liste [48.xxx, 2.xxx]
            # Si c'est déjà une liste :
            df['lat'] = df['coord_geo'].apply(lambda x: x[0] if isinstance(x, list) and len(x)==2 else None)
            df['lon'] = df['coord_geo'].apply(lambda x: x[1] if isinstance(x, list) and len(x)==2 else None)
        except:
            pass
            
    # Suppression des sans-GPS
    df = df.dropna(subset=['lat', 'lon'])

    # 2. Renommage et nettoyage des colonnes pour faire propre
    # Les noms de l'API sont souvent longs (ex: 'tarif_gratuit_payant')
    mapping = {
        'ligne': 'Ligne',
        'station': 'Station',
        'tarif_gratuit_payant': 'Tarif',
        'acces_bouton_poussoir': 'Accessibilité',
        'en_zone_controlee_ou_hors_zone_controlee_station': 'Zone'
    }
    df = df.rename(columns=mapping)
    
    # Standardisation
    if 'Tarif' in df.columns:
        df['Tarif'] = df['Tarif'].fillna('Inconnu')
    else:
        df['Tarif'] = 'Inconnu'

    if 'Ligne' in df.columns:
        df['Ligne'] = df['Ligne'].astype(str)
    else:
        df['Ligne'] = 'Inconnue'

    # Couleur rouge pour la carte
    df['color'] = '#FF0000' 

    return df

# --- CHARGEMENT ---
with st.spinner('Chargement des données depuis data.ratp.fr...'):
    raw_df = load_data_from_api()
    df = clean_data(raw_df)

# --- 2. NAVIGATION ---
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Aller à", ["Accueil", "Statistiques", "Carte", "Données"])

st.sidebar.markdown("---")
st.sidebar.header("Filtres")

if not df.empty and 'Ligne' in df.columns:
    lignes_dispo = sorted(df['Ligne'].unique())
    choix_lignes = st.sidebar.multiselect("Filtrer par ligne", lignes_dispo, default=lignes_dispo)
    if choix_lignes:
        df_filtre = df[df['Ligne'].isin(choix_lignes)]
    else:
        df_filtre = df
else:
    df_filtre = df

# --- 3. PAGES ---

# === ACCUEIL ===
if menu == "Accueil":
    st.title("🚾 Dashboard RATP (API En direct)")
    st.success("✅ Données récupérées avec succès depuis l'API officielle !")
    
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Stations trouvées", len(df_filtre))
        with col2:
            gratuit = len(df_filtre[df_filtre['Tarif'] == 'Gratuit'])
            st.metric("Toilettes Gratuites", gratuit)
            
        st.markdown("---")
        st.subheader("💰 Répartition Gratuit / Payant")
        fig_pie = px.pie(df_filtre, names='Tarif', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_pie, use_container_width=True)

# === STATISTIQUES ===
elif menu == "Statistiques":
    st.title("📊 Statistiques")
    if not df_filtre.empty:
        st.subheader("Top des Lignes les mieux équipées")
        df_count = df_filtre['Ligne'].value_counts().reset_index()
        df_count.columns = ['Ligne', 'Nombre']
        
        fig_bar = px.bar(
            df_count, x='Ligne', y='Nombre', 
            color='Nombre', color_continuous_scale='Blues', text='Nombre'
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("Pas de données.")

# === CARTE ===
elif menu == "Carte":
    st.title("📍 Carte en direct")
    if not df_filtre.empty:
        st.map(df_filtre, latitude='lat', longitude='lon', color='color')
    else:
        st.warning("Pas de données GPS.")

# === DONNÉES ===
elif menu == "Données":
    st.title("📋 Données Brutes API")
    st.dataframe(df_filtre)