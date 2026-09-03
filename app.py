import glob
import io
import os
import tempfile
import zipfile

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
import streamlit as st

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Generador Dinámico de Bloques", page_icon="🗺️", layout="wide"
)

# Paleta de colores predefinida para bloques dinámicos
PALETA_COLORES = [
    {"nombre": "Amarillo", "hex": "#FFD700"},
    {"nombre": "Verde", "hex": "#32CD32"},
    {"nombre": "Azul", "hex": "#1E90FF"},
    {"nombre": "Naranja", "hex": "#FF8C00"},
    {"nombre": "Púrpura", "hex": "#9370DB"},
    {"nombre": "Rojo", "hex": "#FF4500"},
    {"nombre": "Turquesa", "hex": "#00CED1"},
    {"nombre": "Rosa", "hex": "#FF69B4"},
]


# ============================================================
# CARGAR SHAPEFILE
# ============================================================


@st.cache_data
def cargar_datos():
    ruta_zip = "data/SHAPE_FILE_OFICIAL_ZAFRA_2627.zip"

    if not os.path.exists(ruta_zip):
        raise FileNotFoundError(f"No se encontró el archivo ZIP en {ruta_zip}")

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(ruta_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        archivos_shp = glob.glob(
            os.path.join(temp_dir, "**", "*.shp"), recursive=True
        )

        if not archivos_shp:
            raise FileNotFoundError("No se encontró archivo .shp")

        return gpd.read_file(archivos_shp[0])


try:
    gdf = cargar_datos()
except Exception as e:
    st.error("Error cargando la base geográfica")
    st.exception(e)
    st.stop()


COL_FINCA = "FINCA"
COL_CODIGO = "COD_CAM"
COL_CAMPO = "CAMPO"
COL_AREA = "HA"


# ============================================================
# ENCABEZADO
# ============================================================

st.title("🗺️ Generador de Mapas por Bloques Dinámicos")
st.markdown("Seleccione una finca y agregue tantos bloques como necesite.")
st.divider()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Información")
st.sidebar.success(f"Base cargada: {len(gdf):,} registros")
st.sidebar.write("Columnas utilizadas:")
st.sidebar.write("• FINCA")
st.sidebar.write("• COD_CAM")
st.sidebar.write("• CAMPO")
st.sidebar.write("• HA")


# ============================================================
# SELECCIONAR FINCA
# ============================================================

st.header("1️⃣ Selección de Finca")
fincas = sorted(gdf[COL_FINCA].dropna().astype(str).unique())
finca_seleccionada = st.selectbox("Seleccione la finca", fincas)

# Filtrar geodatos para la finca elegida
finca_gdf = gdf[gdf[COL_FINCA].astype(str) == finca_seleccionada].copy()

# ------------------------------------------------------------
# REMOVER DUPLICADOS (Conserva solo 1 valor por CAMPO y HA)
# ------------------------------------------------------------
finca_gdf = finca_gdf.drop_duplicates(subset=[COL_CAMPO, COL_AREA], keep="first")

finca_gdf["CODIGO_STR"] = (
    finca_gdf[COL_CODIGO]
    .fillna("")
    .astype(str)
    .str.replace(".0", "", regex=False)
)


# ============================================================
# GESTIÓN DE BLOQUES DINÁMICOS
# ============================================================

st.header("2️⃣ Organización de Bloques")

if "num_bloques" not in st.session_state:
    st.session_state.num_bloques = 2

col_btn1, col_btn2, _ = st.columns([1, 1, 4])
with col_btn1:
    if st.button("➕ Agregar Bloque"):
        if st.session_state.num_bloques < len(PALETA_COLORES):
            st.session_state.num_bloques += 1
        else:
            st.warning("Límite máximo de bloques alcanzado.")

with col_btn2:
    if st.button("➖ Quitar Bloque"):
        if st.session_state.num_bloques > 1:
            st.session_state.num_bloques -= 1

st.write(f"**Bloques configurados:** {st.session_state.num_bloques}")

opciones_disponibles = (
    finca_gdf.sort_values("CODIGO_STR")["CODIGO_STR"].unique().tolist()
)

bloques_seleccionados = {}
cols_por_fila = 2
columnas_gui = st.columns(cols_por_fila)

for i in range(st.session_state.num_bloques):
    col_idx = i % cols_por_fila
    color_info = PALETA_COLORES[i % len(PALETA_COLORES)]

    with columnas_gui[col_idx]:
        st.subheader(f"Bloque {i+1}")

        lotes_elegidos = st.multiselect(
            f"Campos Bloque {i+1} ({color_info['nombre']}):",
            opciones_disponibles,
            key=f"bloque_dinamico_{i}",
        )

        bloques_seleccionados[f"Bloque {i+1}"] = {
            "lotes": lotes_elegidos,
            "color": color_info["hex"],
            "nombre_color": color_info["nombre"],
        }

        opciones_disponibles = [
            c for c in opciones_disponibles if c not in lotes_elegidos
        ]


# ============================================================
# BOTÓN GENERAR
# ============================================================

st.divider()
generar = st.button(
    "🗺️ GENERAR MAPA Y RESUMEN", use_container_width=True, type="primary"
)


# ============================================================
# GENERACIÓN DEL MAPA Y REPORTES
# ============================================================

if generar:

    fig, ax = plt.subplots(figsize=(12, 9))

    # Capa base (Gris Claro)
    finca_gdf.plot(
        ax=ax, facecolor="#F5F5F5", edgecolor="black", linewidth=0.7
    )

    leyenda_handles = []
    resumen_areas = []
    lotes_en_bloques = set()

    for nombre_bloque, datos in bloques_seleccionados.items():
        lotes = datos["lotes"]
        color_hex = datos["color"]

        if lotes:
            lotes_en_bloques.update(lotes)
            sub_gdf = finca_gdf[finca_gdf["CODIGO_STR"].isin(lotes)]

            sub_gdf.plot(
                ax=ax, facecolor=color_hex, edgecolor="black", linewidth=1.2
            )

            area_b = sub_gdf[COL_AREA].fillna(0).sum()
            resumen_areas.append(
                {
                    "Bloque": nombre_bloque,
                    "Campos": len(lotes),
                    "Área (ha)": area_b,
                }
            )

            leyenda_handles.append(
                Patch(
                    facecolor=color_hex,
                    edgecolor="black",
                    label=f"{nombre_bloque} ({len(lotes)} campos)",
                )
            )

    leyenda_handles.append(
        Patch(
            facecolor="#F5F5F5",
            edgecolor="black",
            label="Sin asignar / Otros",
        )
    )

    # ========================================================
    # ESCALA ADAPTATIVA DE FUENTE SEGÚN EL ÁREA DEL POLÍGONO
    # ========================================================
    areas_geometria = finca_gdf.geometry.area
    min_geom_area = areas_geometria.min()
    max_geom_area = areas_geometria.max()

    for _, row in finca_gdf.iterrows():
        punto = row.geometry.representative_point()
        codigo = row["CODIGO_STR"]

        # Calcular tamaño dinámico de fuente proporcional al área del polígono
        geom_area = row.geometry.area
        if max_geom_area > min_geom_area:
            factor_escala = (np.sqrt(geom_area) - np.sqrt(min_geom_area)) / (
                np.sqrt(max_geom_area) - np.sqrt(min_geom_area)
            )
        else:
            factor_escala = 0.5

        if codigo in lotes_en_bloques:
            # Fuente adaptativa para campos asignados a un bloque (min 4.5pt, max 7.5pt)
            font_size = 4.5 + (factor_escala * 3.0)
            
            nombre_campo = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) != "nan" else codigo
            area_ha = float(row[COL_AREA]) if row[COL_AREA] is not None else 0.0
            etiqueta = f"{nombre_campo}\n{area_ha:,.2f} ha"
            font_weight = "bold"

            box_style = dict(
                boxstyle="round,pad=0.15",
                fc="white",
                ec="none",
                alpha=0.65
            )
        else:
            # Fuente adaptativa para campos no asignados (min 3.5pt, max 5.5pt)
            font_size = 3.5 + (factor_escala * 2.0)
            etiqueta = codigo
            font_weight = "normal"
            box_style = None

        ax.annotate(
            etiqueta,
            xy=(punto.x, punto.y),
            ha="center",
            va="center",
            fontsize=font_size,
            fontweight=font_weight,
            bbox=box_style,
            wrap=True
        )

    ax.set_title(
        f"MAPA DE BLOQUES - FINCA: {finca_seleccionada}",
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    ax.legend(
        handles=leyenda_handles,
        loc="lower right",
        frameon=True,
        fontsize="small",
    )
    ax.axis("off")

    # ========================================================
    # VISTA PREVIA
    # ========================================================

    st.header("3️⃣ Vista previa")
    st.pyplot(fig, use_container_width=True)

    # ========================================================
    # MÉTRICAS DINÁMICAS
    # ========================================================

    st.header("4️⃣ Resumen de Áreas")
    area_total_finca = finca_gdf[COL_AREA].fillna(0).sum()

    if resumen_areas:
        cols_metricas = st.columns(len(resumen_areas) + 1)
        cols_metricas[0].metric("Área Finca", f"{area_total_finca:,.2f} ha")

        area_total_seleccionada = 0
        for idx, item in enumerate(resumen_areas):
            cols_metricas[idx + 1].metric(
                item["Bloque"], f"{item['Área (ha)']:,.2f} ha"
            )
            area_total_seleccionada += item["Área (ha)"]

        st.info(
            f"**Área Total Seleccionada:** {area_total_seleccionada:,.2f} ha de {area_total_finca:,.2f} ha"
        )
    else:
        st.metric("Área Finca", f"{area_total_finca:,.2f} ha")
        st.warning("No has asignado lotes a ningún bloque.")

    # ========================================================
    # GENERAR PDF Y DESCARGA
    # ========================================================

    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight", dpi=300)
    pdf_buffer.seek(0)

    # Liberar memoria de matplotlib
    plt.close(fig)

    st.divider()
    st.download_button(
        label="📥 DESCARGAR MAPA EN PDF",
        data=pdf_buffer,
        file_name=f"Mapa_Bloques_{finca_seleccionada}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
