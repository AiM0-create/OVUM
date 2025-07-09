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

        # Create a full-width Folium map with a clean basemap
    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles='CartoDB positron',
        control_scale=True
    )

    # Style and add catchment boundaries (buffer zones)
    if catchments_gdf is not None:
        # Define colors for different radius zones if attribute exists
        def style_function(feature):
            props = feature['properties']
            # If shapefile has a 'radius_km' field, color by value
            radius = props.get('radius_km')
            if radius == 3:
                color = '#FF5733'  # Orange-red
            elif radius == 5:
                color = '#33C3FF'  # Light blue
            elif radius == 6:
                color = '#75FF33'  # Light green
            else:
                color = '#338AFF'  # Default blue
            return {
                'color': color,
                'weight': 2,
                'fillOpacity': 0.1,
            }

        folium.GeoJson(
            catchments_gdf.__geo_interface__,
            name="Catchments",
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(fields=['radius_km'], aliases=['Radius (km):'])
        ).add_to(m)

    # Add clinic markers with circle markers and labels
    colors = ['#FF3333', '#33FF57', '#FF33F6', '#33FFF2']
    for idx, row in clinics_gdf.iterrows():
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=7,
            color=colors[idx % len(colors)],
            fill=True,
            fill_color=colors[idx % len(colors)],
            fill_opacity=0.8,
            popup=folium.Popup(str(row.get('name', 'Clinic')), parse_html=True),
            tooltip=str(row.get('name', 'Clinic'))
        ).add_to(m)

    # Display the map full-width
    st.subheader("Clinic Locations & Catchment Boundaries")
    st_folium(m, width="100%", height=600)

else:
    st.info("Please upload both clinic CSV and catchment shapefile ZIP to proceed.")
