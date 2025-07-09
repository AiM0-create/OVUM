# Requirements:
# 
# To install dependencies:
# pip install streamlit geopandas pandas osmnx folium shapely

import streamlit as st
import geopandas as gpd
import pandas as pd
import osmnx as ox
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
                selo = f"{tmpdir}/{fname}"
                return gpd.read_file(selo)
    return None

# Load clinics and generate buffers
def load_clinics(csv_bytes):
    df = pd.read_csv(csv_bytes)
    gdf = gpd.GeoDataFrame(df,
                           geometry=gpd.points_from_xy(df['long'], df['lat']),
                           crs="EPSG:4326")
    gdf_proj = gdf.to_crs(epsg=3857)
    for meters in [3000, 5000, 6000]:
        label = meters // 1000
        gdf_proj[f'buffer_{label}km'] = gdf_proj.geometry.buffer(meters)
    return gdf_proj

# Extract spatial metrics
def extract_osm_metrics(clinics_gdf, km_label):
    records = []
    for _, row in clinics_gdf.iterrows():
        # Get metric buffer and reproject to lat/lon for OSM queries
        poly_m = row[f'buffer_{km_label}km']
        geo_series = gpd.GeoSeries([poly_m], crs=3857)
        poly_ll = geo_series.to_crs(epsg=4326).iloc[0]
        # Building count
        bldgs = ox.geometries.geometries_from_polygon(poly_ll, {'building': True})
        # Competitor count (maternity)
        comps = ox.geometries.geometries_from_polygon(poly_ll, {'amenity': 'hospital', 'healthcare': 'maternity'})
        # Road density
        G = ox.graph_from_polygon(poly_ll, network_type='drive')
        total_len_m = sum(d['length'] for _, _, d in G.edges(data=True))
        length_km = total_len_m / 1000
        area_km2 = poly_m.area / 1e6
        # Playschools count
        schools = ox.geometries.geometries_from_polygon(poly_ll, {'amenity': ['kindergarten', 'school']})
        # Public transport stops count
        pts = ox.geometries.geometries_from_polygon(poly_ll, {'public_transport': 'station'})
        records.append({
            'clinic': row['name'],
            'radius_km': km_label,
            'buildings': len(bldgs),
            'competitors': len(comps),
            'road_density': length_km / area_km2,
            'playschools': len(schools),
            'public_transport': len(pts)
        })
    return pd.DataFrame(records)

# Scoring and ranking
def compute_scores(df):
    weights = {
        'buildings': 0.2,
        'competitors': -0.3,
        'road_density': 0.2,
        'playschools': 0.1,
        'public_transport': 0.2
    }
    df2 = df.copy()
    for factor, w in weights.items():
        norm = (df2[factor] - df2[factor].min()) / (df2[factor].max() - df2[factor].min())
        df2[f'{factor}_score'] = norm * w
    df2['total_score'] = df2[[f'{f}_score' for f in weights]].sum(axis=1)
    df2['rank'] = df2['total_score'].rank(ascending=False)
    return df2

if csv_file and shp_zip:
    st.success("Data loaded successfully.")
    clinics = load_clinics(csv_file)
    catchments = load_shapefile(shp_zip)

    st.subheader("Clinic Locations on Map")
    df_map = clinics.to_crs(epsg=4326).geometry.apply(lambda p: {'lat': p.y, 'lon': p.x})
    st.map(pd.DataFrame(df_map.tolist()))

    # Compute metrics for each radius
    metrics = pd.concat([extract_osm_metrics(clinics, r) for r in [3, 5, 6]], ignore_index=True)
    scores = compute_scores(metrics)

    st.subheader("Catchment Metrics & Scores")
    st.dataframe(scores)

    # Score comparison
    st.subheader("Score Comparison by Radius & Clinic")
    pivot = scores.pivot(index='radius_km', columns='clinic', values='total_score')
    st.line_chart(pivot)

    # Factor breakdown
    st.subheader("Factor Score Breakdown per Clinic")
    for clinic in scores['clinic'].unique():
        st.markdown(f"### {clinic}")
        dfc = scores[scores['clinic'] == clinic].set_index('radius_km')
        st.bar_chart(dfc[[
            'buildings_score', 'competitors_score', 'road_density_score',
            'playschools_score', 'public_transport_score'
        ]])
else:
    st.warning("Upload both clinic CSV and shapefile ZIP to view analysis.")
