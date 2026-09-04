import glob
import io
import os
import tempfile
import zipfile

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
import streamlit as st

# Configuración para conservar la máxima calidad vectorial en el texto del PDF
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42

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

st.title("🗺️ Generador de Mapas Madurante")
st.markdown("Seleccione una finca y agregue los bloques.")
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
finca_gdf["CODIGO_STR"] = (
    finca_gdf[COL_CODIGO]
    .fillna("")
    .astype(str)
    .str.replace(".0", "", regex=False)
)
finca_gdf["CAMPO_STR"] = finca_gdf[COL_CAMPO].fillna("").astype(str)

# Etiqueta amigable para la selección: "CAMPO (CÓDIGO)" o solo "CAMPO" si son idénticos
finca_gdf["LABEL_OPCION"] = np.where(
    (finca_gdf["CAMPO_STR"] != "") & (finca_gdf["CAMPO_STR"] != finca_gdf["CODIGO_STR"]),
    finca_gdf["CAMPO_STR"] + " (" + finca_gdf["CODIGO_STR"] + ")",
    finca_gdf["CAMPO_STR"].replace("", "Sin Nombre")
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

# Obtener catálogo de campos únicos para el selector (ordenados por nombre de campo)
df_opciones = (
    finca_gdf[["CODIGO_STR", "LABEL_OPCION"]]
    .drop_duplicates(subset=["CODIGO_STR"])
    .sort_values("LABEL_OPCION")
)

# Mapa para convertir de la etiqueta mostrada al código interno
mapa_label_a_codigo = dict(zip(df_opciones["LABEL_OPCION"], df_opciones["CODIGO_STR"]))
opciones_disponibles = df_opciones["LABEL_OPCION"].tolist()

bloques_seleccionados = {}
cols_por_fila = 2
columnas_gui = st.columns(cols_por_fila)

for i in range(st.session_state.num_bloques):
    col_idx = i % cols_por_fila
    color_info = PALETA_COLORES[i % len(PALETA_COLORES)]

    with columnas_gui[col_idx]:
        st.subheader(f"Bloque {i+1}")

        labels_elegidos = st.multiselect(
            f"Campos Bloque {i+1} ({color_info['nombre']}):",
            opciones_disponibles,
            key=f"bloque_dinamico_{i}",
        )

        # Mapear los nombres/etiquetas seleccionadas a sus códigos correspondientes
        codigos_elegidos = [mapa_label_a_codigo[lbl] for lbl in labels_elegidos]

        bloques_seleccionados[f"Bloque {i+1}"] = {
            "lotes": codigos_elegidos,
            "color": color_info["hex"],
            "nombre_color": color_info["nombre"],
        }

        # Excluir de la lista las opciones ya seleccionadas
        opciones_disponibles = [
            lbl for lbl in opciones_disponibles if lbl not in labels_elegidos
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

    # Capa base con TODOS los polígonos
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

            # Tomar 1 solo valor de área por campo para evitar sumas duplicadas
            area_b = (
                sub_gdf.drop_duplicates(subset=["CODIGO_STR"])[COL_AREA]
                .fillna(0)
                .sum()
            )

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
    # UNIFICACIÓN DE GEOMETRÍAS Y UBICACIÓN CENTRADA DE ETIQUETAS
    # ========================================================
    # Agrupar (dissolve) las geometrías tomando sólo el primer valor de HA (sin sumar)
    campos_unificados = finca_gdf.dissolve(
        by=["CODIGO_STR"],
        aggfunc={COL_CAMPO: "first", COL_AREA: "first"}
    ).reset_index()

    campos_unificados["_TOTAL_GEOM_AREA"] = campos_unificados.geometry.area
    min_geom_area = campos_unificados["_TOTAL_GEOM_AREA"].min()
    max_geom_area = campos_unificados["_TOTAL_GEOM_AREA"].max()

    for _, row in campos_unificados.iterrows():
        punto = row.geometry.representative_point()
        codigo = row["CODIGO_STR"]

        geom_area = row["_TOTAL_GEOM_AREA"]
        if max_geom_area > min_geom_area:
            factor_escala = (np.sqrt(geom_area) - np.sqrt(min_geom_area)) / (
                np.sqrt(max_geom_area) - np.sqrt(min_geom_area)
            )
        else:
            factor_escala = 0.5

        if codigo in lotes_en_bloques:
            # Tamaño adaptativo para campos asignados (min 3.5pt, max 6.0pt)
            font_size = 2.5 + (factor_escala * 2.5)
            
            nombre_campo = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) != "nan" and str(row[COL_CAMPO]) != "" else codigo
            area_ha = float(row[COL_AREA]) if row[COL_AREA] is not None else 0.0
            etiqueta = f"{nombre_campo}\n{area_ha:,.2f} ha"
            font_weight = "bold"

            box_style = dict(
                boxstyle="round,pad=0.12",
                fc="white",
                ec="none",
                alpha=0.65
            )
        else:
            # Tamaño adaptativo para campos sin asignar (min 2.5pt, max 4.5pt)
            font_size = 2.5 + (factor_escala * 2.0)
            etiqueta = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) != "nan" and str(row[COL_CAMPO]) != "" else codigo
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
    # Área total tomando 1 valor por campo único
    area_total_finca = (
        finca_gdf.drop_duplicates(subset=["CODIGO_STR"])[COL_AREA]
        .fillna(0)
        .sum()
    )

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

    plt.close(fig)

    st.divider()
    st.download_button(
        label="📥 DESCARGAR MAPA EN PDF",
        data=pdf_buffer,
        file_name=f"Mapa_Bloques_{finca_seleccionada}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
