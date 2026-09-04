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

# Configuración para conservar calidad vectorial en PDF
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Generador de Planos - Montelimar", page_icon="🗺️", layout="wide"
)

PALETA_COLORES = [
    {"nombre": "Amarillo", "hex": "#FFFF00"},
    {"nombre": "Verde", "hex": "#32CD32"},
    {"nombre": "Rojo", "hex": "#FF0000"},
    {"nombre": "Azul", "hex": "#0000FF"},
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
# INTERFAZ Y CONFIGURACIÓN DEL PLANO
# ============================================================

st.title("🗺️ Generador de Planos Oficiales")
st.divider()

fincas = sorted(gdf[COL_FINCA].dropna().astype(str).unique())
finca_seleccionada = st.selectbox("Seleccione Finca:", fincas)

st.subheader("📋 Datos del Cajetín")
c1, c2, c3, c4 = st.columns(4)
with c1:
    tipo_plano = st.text_input("Plano / Tipo", "Plano Aplicación Madurante")
    zafra_txt = st.text_input("Zafra", "Zafra 24-25")
with c2:
    responsable_txt = st.text_input("Responsable", "Ing. Kelvin Vivas")
    jefe_prod_txt = st.text_input("Jefe de Producción", "Ing. Igmar Hurtado")
with c3:
    dibujo_txt = st.text_input("Dibujo", "Ing. Kelvin Vivas")
    zona_txt = st.text_input("Zona", "1")
with c4:
    uso_txt = st.text_input("Uso", "Comercial")

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

st.subheader("🎨 Asignación de Bloques")

if "num_bloques" not in st.session_state:
    st.session_state.num_bloques = 4

df_opciones = (
    finca_gdf[["CODIGO_STR", "LABEL_OPCION"]]
    .drop_duplicates(subset=["CODIGO_STR"])
    .sort_values("LABEL_OPCION")
)

mapa_label_a_codigo = dict(zip(df_opciones["LABEL_OPCION"], df_opciones["CODIGO_STR"]))
opciones_disponibles = df_opciones["LABEL_OPCION"].tolist()

bloques_seleccionados = {}
cols_gui = st.columns(4)

for i in range(st.session_state.num_bloques):
    color_info = PALETA_COLORES[i % len(PALETA_COLORES)]

    with cols_gui[i]:
        labels_elegidos = st.multiselect(
            f"Bloque {i+1} ({color_info['nombre']}):",
            opciones_disponibles,
            key=f"bloque_madronal_{i}",
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
# RENDERIZADO DEL PLANO ESTILO MADROÑAL
# ============================================================

if generar:
    fig = plt.figure(figsize=(8.5, 11), dpi=300)
    
    # Eje Principal del Mapa
    ax = fig.add_axes([0.04, 0.16, 0.92, 0.78])
    
    # Capa Base: Blanco con borde negro fino
    finca_gdf.plot(
        ax=ax, facecolor="white", edgecolor="black", linewidth=0.7
    )

    leyenda_handles = [
        Patch(facecolor="white", edgecolor="black", label="Sin_Aplicar")
    ]
    
    lotes_en_bloques = set()
    area_total_bloques = 0.0

    # Dibujar Polígonos de Bloques Coloreados
    for num_bloque, datos in bloques_seleccionados.items():
        lotes = datos["lotes"]
        color_hex = datos["color"]

        if lotes:
            lotes_en_bloques.update(lotes)
            sub_gdf = finca_gdf[finca_gdf["CODIGO_STR"].isin(lotes)]

            sub_gdf.plot(
                ax=ax, facecolor=color_hex, edgecolor="black", linewidth=1.0
            )

            area_b = (
                sub_gdf.drop_duplicates(subset=["CODIGO_STR"])[COL_AREA]
                .fillna(0)
                .sum()
            )
            area_total_bloques += area_b

        leyenda_handles.append(
            Patch(facecolor=color_hex, edgecolor="black", label=f"{num_bloque}")
        )

    # Ubicación de Etiquetas Unificadas por Campo Asignado
    campos_unificados = finca_gdf.dissolve(
        by=["CODIGO_STR"],
        aggfunc={COL_CAMPO: "first", COL_AREA: "first"}
    ).reset_index()

    for _, row in campos_unificados.iterrows():
        codigo = row["CODIGO_STR"]
        
        # Etiquetar principalmente los campos asignados a un bloque
        if codigo in lotes_en_bloques:
            punto = row.geometry.representative_point()
            nombre_campo = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) not in ["nan", ""] else codigo
            area_ha = float(row[COL_AREA]) if row[COL_AREA] is not None else 0.0

            # Formato exacto de la imagen: "21,23  STA. ELI-01"
            area_str = f"{area_ha:,.2f}".replace(".", ",")
            etiqueta = f"{area_str}   {nombre_campo}"

            ax.annotate(
                etiqueta,
                xy=(punto.x, punto.y),
                ha="center",
                va="center",
                fontsize=7,
                fontweight="bold"
            )

    # Título Superior
    ax.set_title(
        f"FINCA {finca_seleccionada.upper()}",
        fontsize=18,
        fontweight="bold",
        loc="left",
        pad=10
    )

    # Rosa de los vientos (Superior derecha)
    ax.text(0.93, 0.93, "N\nW ┼ E\nS", transform=ax.transAxes,
            ha="center", va="center", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="black", lw=1))

    # Leyenda Estilo Madroñal (Inferior izquierda)
    leg = ax.legend(
        handles=leyenda_handles,
        title="LEYENDA\n\n─── Lineas_Eléctricas\n\nBLOQUE",
        loc="lower left",
        frameon=True,
        facecolor="white",
        edgecolor="black",
        fontsize=8,
        title_fontsize=8.5,
        box_spacing=0.8
    )
    leg.get_title().set_fontweight('bold')

    ax.axis("off")

    # Borde Exterior rectangular completo
    fig.patches.extend([
        Rectangle((0.02, 0.02), 0.96, 0.96,
                  fill=False, edgecolor='black', lw=1.5, transform=fig.transFigure)
    ])

    # ============================================================
    # CAJETÍN DE INFORMACIÓN INFERIOR (OFICIAL MONTELIMAR)
    # ============================================================
    ax_box = fig.add_axes([0.02, 0.02, 0.96, 0.12])
    ax_box.axis("off")

    # Líneas divisoras del cajetín
    ax_box.plot([0, 1], [1, 1], color="black", lw=1.5)
    ax_box.plot([0.18, 0.18], [0, 1], color="black", lw=1)
    ax_box.plot([0.45, 0.45], [0, 1], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.8, 0.8], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.6, 0.6], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.4, 0.4], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.2, 0.2], color="black", lw=1)
    ax_box.plot([0.78, 0.78], [0, 0.8], color="black", lw=1)

    # Logo Placeholder / Texto Logo
    ax_box.text(0.09, 0.5, "MONTELIMAR", ha="center", va="center", fontsize=10, fontweight="bold", color="#2E7D32")
    
    # Nombre Finca
    ax_box.text(0.315, 0.5, f"Finca: {finca_seleccionada}", ha="center", va="center", fontsize=9, fontweight="bold")

    # Encabezado Departamento
    ax_box.text(0.725, 0.9, "Departamento Producción", ha="center", va="center", fontsize=8, fontweight="bold")

    # Fila 1
    ax_box.text(0.615, 0.7, f"{tipo_plano}", ha="center", va="center", fontsize=7.5)
    ax_box.text(0.89, 0.7, f"Zona: {zona_txt}", ha="center", va="center", fontsize=7.5)

    # Fila 2
    ax_box.text(0.615, 0.5, f"{zafra_txt}", ha="center", va="center", fontsize=7.5)
    ax_box.text(0.89, 0.5, f"Uso: {uso_txt}", ha="center", va="center", fontsize=7.5)

    # Fila 3
    ax_box.text(0.615, 0.3, f"Responsable: {responsable_txt}", ha="center", va="center", fontsize=7.5)
    ax_box.text(0.89, 0.3, f"Area: {area_total_bloques:,.2f}".replace(".", ","), ha="center", va="center", fontsize=7.5, fontweight="bold")

    # Fila 4
    ax_box.text(0.615, 0.1, f"Jefe de Producción: {jefe_prod_txt}", ha="center", va="center", fontsize=7.5)
    ax_box.text(0.89, 0.1, f"Dibujo: {dibujo_txt}", ha="center", va="center", fontsize=7.5)

    # Mostrar Plano
    st.pyplot(fig, use_container_width=True)

    # Descarga PDF
    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight", dpi=300)
    pdf_buffer.seek(0)
    plt.close(fig)

    st.download_button(
        label="📥 DESCARGAR PLANO OFICIAL EN PDF",
        data=pdf_buffer,
        file_name=f"Plano_Oficial_{finca_seleccionada}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
