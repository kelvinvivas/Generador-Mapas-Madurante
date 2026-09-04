import glob
import io
import os
import tempfile
import zipfile

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle
import streamlit as st

# Configuración para conservar máxima calidad vectorial en PDF
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Generador de Planos de Aplicación", page_icon="🗺️", layout="wide"
)

PALETA_COLORES = [
    {"nombre": "Amarillo", "hex": "#FFFF00"},
    {"nombre": "Verde", "hex": "#32CD32"},
    {"nombre": "Rojo", "hex": "#FF0000"},
    {"nombre": "Azul", "hex": "#0000FF"},
    {"nombre": "Menta", "hex": "#E0FFFF"},
    {"nombre": "Rosa", "hex": "#FFC0CB"},
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
# INTERFAZ
# ============================================================

st.title("🗺️ Generador de Planos Geográficos")
st.markdown("Herramienta para generar mapas estilo plano de producción con cajetín y leyenda oficial.")
st.divider()

# SELECCIÓN DE FINCA
fincas = sorted(gdf[COL_FINCA].dropna().astype(str).unique())
finca_seleccionada = st.selectbox("Seleccione la finca", fincas)

# DATOS ADICIONALES PARA CAJETÍN
col_c1, col_c2, col_c3, col_c4 = st.columns(4)
with col_c1:
    semana_txt = st.text_input("Semana", "SEMANA 02")
with col_c2:
    zafra_txt = st.text_input("Zafra", "Zafra 24-25")
with col_c3:
    responsable_txt = st.text_input("Responsable", "Ing. Kelvin Vivas")
with col_c4:
    tipo_plano = st.text_input("Tipo de Plano", "Plano Aplicación Inhibidor")

finca_gdf = gdf[gdf[COL_FINCA].astype(str) == finca_seleccionada].copy()
finca_gdf["CODIGO_STR"] = (
    finca_gdf[COL_CODIGO]
    .fillna("")
    .astype(str)
    .str.replace(".0", "", regex=False)
)
finca_gdf["CAMPO_STR"] = finca_gdf[COL_CAMPO].fillna("").astype(str)

finca_gdf["LABEL_OPCION"] = np.where(
    (finca_gdf["CAMPO_STR"] != "") & (finca_gdf["CAMPO_STR"] != finca_gdf["CODIGO_STR"]),
    finca_gdf["CAMPO_STR"] + " (" + finca_gdf["CODIGO_STR"] + ")",
    finca_gdf["CAMPO_STR"].replace("", "Sin Nombre")
)

# SELECCIÓN DE BLOQUES
st.header("Organización de Bloques")

if "num_bloques" not in st.session_state:
    st.session_state.num_bloques = 6

col_btn1, col_btn2, _ = st.columns([1, 1, 4])
with col_btn1:
    if st.button("➕ Agregar Bloque"):
        if st.session_state.num_bloques < len(PALETA_COLORES):
            st.session_state.num_bloques += 1
with col_btn2:
    if st.button("➖ Quitar Bloque"):
        if st.session_state.num_bloques > 1:
            st.session_state.num_bloques -= 1

df_opciones = (
    finca_gdf[["CODIGO_STR", "LABEL_OPCION"]]
    .drop_duplicates(subset=["CODIGO_STR"])
    .sort_values("LABEL_OPCION")
)

mapa_label_a_codigo = dict(zip(df_opciones["LABEL_OPCION"], df_opciones["CODIGO_STR"]))
opciones_disponibles = df_opciones["LABEL_OPCION"].tolist()

bloques_seleccionados = {}
cols_gui = st.columns(3)

for i in range(st.session_state.num_bloques):
    col_idx = i % 3
    color_info = PALETA_COLORES[i % len(PALETA_COLORES)]

    with cols_gui[col_idx]:
        labels_elegidos = st.multiselect(
            f"Bloque {i+1} ({color_info['nombre']}):",
            opciones_disponibles,
            key=f"bloque_dinamico_{i}",
        )

        codigos_elegidos = [mapa_label_a_codigo[lbl] for lbl in labels_elegidos]

        bloques_seleccionados[f"{i+1}"] = {
            "lotes": codigos_elegidos,
            "color": color_info["hex"],
        }

        opciones_disponibles = [
            lbl for lbl in opciones_disponibles if lbl not in labels_elegidos
        ]

st.divider()
generar = st.button("🗺️ GENERAR PLANO", use_container_width=True, type="primary")

# ============================================================
# RENDERIZADO DEL MAPA ESTILO PLANO DE PRODUCCIÓN
# ============================================================

if generar:
    # Crear Figura
    fig = plt.figure(figsize=(10, 13), dpi=300)
    
    # Subplot principal para la cartografía (deja espacio abajo para cajetín)
    ax = fig.add_axes([0.05, 0.18, 0.90, 0.77])
    
    # 1. Capa Base (Sin Aplicar / Blanco con borde negro)
    finca_gdf.plot(
        ax=ax, facecolor="white", edgecolor="black", linewidth=0.8
    )

    leyenda_handles = [
        Patch(facecolor="white", edgecolor="black", label="Sin_Aplicar")
    ]
    
    lotes_en_bloques = set()
    area_total_bloques = 0.0

    # 2. Dibujar Bloques Coloreados
    for num_bloque, datos in bloques_seleccionados.items():
        lotes = datos["lotes"]
        color_hex = datos["color"]

        if lotes:
            lotes_en_bloques.update(lotes)
            sub_gdf = finca_gdf[finca_gdf["CODIGO_STR"].isin(lotes)]

            # Pintar polígonos
            sub_gdf.plot(
                ax=ax, facecolor=color_hex, edgecolor="black", linewidth=1.0
            )

            # Sumar área (1 valor por campo único)
            area_b = (
                sub_gdf.drop_duplicates(subset=["CODIGO_STR"])[COL_AREA]
                .fillna(0)
                .sum()
            )
            area_total_bloques += area_b

            leyenda_handles.append(
                Patch(facecolor=color_hex, edgecolor="black", label=f"{num_bloque}")
            )
        else:
            # Mantener el bloque en la leyenda aunque esté vacío (como en la imagen)
            leyenda_handles.append(
                Patch(facecolor=color_hex, edgecolor="black", label=f"{num_bloque}")
            )

    # 3. Etiquetas unificadas por Campo
    campos_unificados = finca_gdf.dissolve(
        by=["CODIGO_STR"],
        aggfunc={COL_CAMPO: "first", COL_AREA: "first"}
    ).reset_index()

    for _, row in campos_unificados.iterrows():
        punto = row.geometry.representative_point()
        codigo = row["CODIGO_STR"]
        nombre_campo = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) not in ["nan", ""] else codigo
        area_ha = float(row[COL_AREA]) if row[COL_AREA] is not None else 0.0

        # Texto estilo imagen: Nombre arriba, Área abajo
        etiqueta = f"{nombre_campo}\n{area_ha:,.2f}".replace(",", ".")

        ax.annotate(
            etiqueta,
            xy=(punto.x, punto.y),
            ha="center",
            va="center",
            fontsize=5.5,
            fontweight="bold" if codigo in lotes_en_bloques else "normal",
        )

    # 4. Título Principal
    ax.set_title(
        f"FINCA {finca_seleccionada.upper()} {semana_txt.upper()}",
        fontsize=16,
        fontweight="bold",
        loc="left",
        pad=10
    )

    # 5. Rosa de los vientos (N, S, E, O)
    ax.text(0.95, 0.95, "N\nW ┼ E\nS", transform=ax.transAxes,
            ha="center", va="center", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="circle,pad=0.3", fc="white", ec="black", lw=1))

    # 6. Leyenda estilo cuadro flotante
    leg = ax.legend(
        handles=leyenda_handles,
        title="BLOQUE",
        loc="lower right",
        frameon=True,
        facecolor="white",
        edgecolor="black",
        fontsize=9,
        title_fontsize=10
    )
    leg.get_title().set_fontweight('bold')

    ax.axis("off")

    # 7. Marco Externo
    fig.patches.extend([
        Rectangle((0.02, 0.02), 0.96, 0.96,
                  fill=False, edgecolor='black', lw=1.5, transform=fig.transFigure)
    ])

    # 8. Cajetín Inferior de Información
    ax_box = fig.add_axes([0.02, 0.02, 0.96, 0.13])
    ax_box.axis("off")

    # Rejilla del cajetín
    ax_box.plot([0, 1], [1, 1], color="black", lw=1.5)
    ax_box.plot([0.25, 0.25], [0, 1], color="black", lw=1)
    ax_box.plot([0.48, 0.48], [0, 1], color="black", lw=1)
    ax_box.plot([0.48, 1.00], [0.5, 0.5], color="black", lw=1)

    # Texto Cajetín
    ax_box.text(0.125, 0.5, f"Finca: {finca_seleccionada}", ha="center", va="center", fontsize=9, fontweight="bold")
    
    # Columna Central
    ax_box.text(0.74, 0.8, "Departamento Producción", ha="center", va="center", fontsize=8, fontweight="bold")
    ax_box.text(0.61, 0.25, f"{tipo_plano}", ha="center", va="center", fontsize=8)
    ax_box.text(0.87, 0.25, "Zona: 1", ha="center", va="center", fontsize=8)

    # Columna Derecha / Datos
    ax_box.text(0.61, -0.2, f"{zafra_txt}", ha="center", va="center", fontsize=8)
    ax_box.text(0.87, -0.2, f"Área Bloques: {area_total_bloques:,.2f} ha", ha="center", va="center", fontsize=8, fontweight="bold")

    # Vista previa
    st.pyplot(fig, use_container_width=True)

    # Descarga PDF
    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight", dpi=300)
    pdf_buffer.seek(0)
    plt.close(fig)

    st.download_button(
        label="📥 DESCARGAR PLANO EN PDF",
        data=pdf_buffer,
        file_name=f"Plano_{finca_seleccionada}_{semana_txt}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
