# Requirements:
# 
# To install dependencies:
# pip install streamlit geopandas pandas osmnx folium shapely

import streamlit as st
import geopandas as gpd
import pandas as pd
import osmnx as ox
import folium
from shapely.geometry import Point
import zipfile
import tempfile

st.set_page_config(page_title="Catchment Analysis", layout="wide")

st.title("Catchment Analysis Dashboard")

# Sidebar: File uploads
st.sidebar.header("Upload Data")
csv_file = st.sidebar.file_uploader("Upload clinic CSV", type=["csv"])
shp_zip = st.sidebar.file_uploader("Upload catchment shapefile ZIP", type=["zip"])

def load_shapefile(zip_file):
    with tempfile.TemporaryDirectory() as tmpdir:
        z = zipfile.ZipFile(zip_file)
        z.extractall(tmpdir)
        for fname in z.namelist():
            if fname.endswith('.shp'):
                shp_path = f"{tmpdir}/{fname}"
                return gpd.read_file(shp_path)
    return None

# Load clinics and generate buffers
# @st.cache_data  # caching disabled for simplicity
def load_clinics(csv_bytes):
    df = pd.read_csv(csv_bytes)
    gdf = gpd.GeoDataFrame(df,
                           geometry=gpd.points_from_xy(df['long'], df['lat']),
                           crs="EPSG:4326")
    gdf_proj = gdf.to_crs(epsg=3857)
    for meters in [3000, 5000, 6000]:
        label = meters//1000
        gdf_proj[f'buffer_{label}km'] = gdf_proj.geometry.buffer(meters)
    return gdf_proj

# @st.cache_data  # caching disabled for simplicity
def extract_osm_metrics(clinics_gdf, km_label):
    records = []
    for _, row in clinics_gdf.iterrows():
        poly = row[f'buffer_{km_label}km'].to_crs(epsg=4326)
        # Buildings count
        bldgs = ox.geometries.geometries_from_polygon(poly, {'building': True})
        # Competitors count
        comps = ox.geometries.geometries_from_polygon(poly, {'amenity':'hospital','healthcare':'maternity'})
        # Road density
        G = ox.graph_from_polygon(poly, network_type='drive')
        length_km = sum(d['length'] for _,_,d in G.edges(data=True)) / 1000
        area_km2 = poly.to_crs(epsg=3857).area / 1e6
        # Playschools count
        schools = ox.geometries.geometries_from_polygon(poly, {'amenity':['kindergarten','school']})
        # Public transport stops count
        pts = ox.geometries.geometries_from_polygon(poly, {'public_transport':'station'})
        records.append({
            'clinic': row['name'],
            'radius_km': km_label,
            'buildings': len(bldgs),
            'competitors': len(comps),
            'road_density': length_km/area_km2,
            'playschools': len(schools),
            'public_transport': len(pts)
        })
    return pd.DataFrame(records)

# Scoring function
# @st.cache_data  # caching disabled for simplicity
def compute_scores(df):
    weights = {
        'buildings': 0.2,
        'competitors': -0.3,
        'road_density': 0.2,
        'playschools': 0.1,
        'public_transport': 0.2
    }
    df2 = df.copy()
    for k, w in weights.items():
        norm = (df2[k] - df2[k].min()) / (df2[k].max() - df2[k].min())
        df2[f'{k}_score'] = norm * w
    df2['total_score'] = df2[[f'{k}_score' for k in weights]].sum(axis=1)
    df2['rank'] = df2['total_score'].rank(ascending=False)
    return df2

if csv_file and shp_zip:
    st.success("Data loaded successfully.")
    clinics = load_clinics(csv_file)
    gdf_catch = load_shapefile(shp_zip)

    st.subheader("Clinic Locations")
    coords = clinics.to_crs(epsg=4326).geometry.apply(lambda p: (p.y, p.x))
    st.map(pd.DataFrame(coords.tolist(), columns=['lat', 'lon']))

    # Compute metrics
    metrics = pd.concat([extract_osm_metrics(clinics, r) for r in [3,5,6]], ignore_index=True)
    scores = compute_scores(metrics)

    st.subheader("Catchment Metrics & Scores")
    st.dataframe(scores)

    # Visualize Scores
    st.subheader("Score Comparison by Catchment")
    chart = scores.pivot(index='radius_km', columns='clinic', values='total_score')
    st.line_chart(chart)

    st.subheader("Factor Breakdown for Each Clinic")
    for clinic in scores['clinic'].unique():
        st.markdown(f"**{clinic}**")
        dfc = scores[scores['clinic']==clinic].set_index('radius_km')
        st.bar_chart(dfc[[ 'buildings_score','competitors_score','road_density_score','playschools_score','public_transport_score']])

else:
    st.info("Please upload both the clinic CSV and catchment shapefile ZIP to proceed.")
