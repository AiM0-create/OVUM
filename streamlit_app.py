# Requirements:
# pip install streamlit geopandas pandas streamlit-folium folium shapely

import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import zipfile
import tempfile

st.set_page_config(page_title="Catchment Analysis", layout="wide")
st.title("Catchment Analysis Dashboard")

# Sidebar: File uploads
st.sidebar.header("Upload Data")
csv_file = st.sidebar.file_uploader("Upload clinic CSV", type=["csv"])
shp_zip = st.sidebar.file_uploader("Upload catchment shapefile ZIP", type=["zip"])

def load_shapefile(zip_file):
    """Extract and load a shapefile from a ZIP archive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        z = zipfile.ZipFile(zip_file)
        z.extractall(tmpdir)
        for fname in z.namelist():
            if fname.endswith('.shp'):
                return gpd.read_file(f"{tmpdir}/{fname}")
    return None

if csv_file and shp_zip:
    # Load clinics CSV into GeoDataFrame
    clinics_df = pd.read_csv(csv_file)
    clinics_gdf = gpd.GeoDataFrame(
        clinics_df,
        geometry=gpd.points_from_xy(clinics_df['long'], clinics_df['lat']),
        crs="EPSG:4326"
    )
    # Load catchment shapefile
    catchments_gdf = load_shapefile(shp_zip)
    if catchments_gdf is not None:
        catchments_gdf = catchments_gdf.to_crs(epsg=4326)

    # Create Folium map
    center = [clinics_gdf.geometry.y.iloc[0], clinics_gdf.geometry.x.iloc[0]]
    m = folium.Map(location=center, zoom_start=12)

    # Add catchment boundaries
    if catchments_gdf is not None:
        folium.GeoJson(catchments_gdf.__geo_interface__, name="Catchments").add_to(m)
    # Add clinic markers
    for _, row in clinics_gdf.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=row.get('name', 'Clinic')
        ).add_to(m)

    st.subheader("Clinic Locations & Catchment Boundaries")
    st_folium(m, width=700, height=500)

else:
    st.info("Please upload both clinic CSV and catchment shapefile ZIP to proceed.")
