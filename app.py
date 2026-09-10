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

# Configuración para conservar máxima calidad vectorial en exportación PDF
mpl.rcParams["pdf.fonttype"] = 42
mpl.rcParams["ps.fonttype"] = 42

# ============================================================
# CONFIGURACIÓN GENERAL Y PALETA DE COLORES FIJA
# ============================================================

st.set_page_config(
    page_title="Generador de Planos - Montelimar", page_icon="🗺️", layout="wide"
)

# Paleta fija de 6 bloques
PALETA_BLOQUES = [
    {"bloque": "1", "nombre": "1 (Amarillo)", "hex": "#FFFF00"},
    {"bloque": "2", "nombre": "2 (Verde)", "hex": "#32CD32"},
    {"bloque": "3", "nombre": "3 (Rojo)", "hex": "#FF0000"},
    {"bloque": "4", "nombre": "4 (Azul)", "hex": "#0000FF"},
    {"bloque": "5", "nombre": "5 (Celeste)", "hex": "#87CEEB"},
    {"bloque": "6", "nombre": "6 (Rosa)", "hex": "#FFB6C1"},
]


# ============================================================
# CARGAR BASE GEOGRÁFICA DE DATOS
# ============================================================

@st.cache_data
def cargar_datos():
    ruta_zip = "data/SHAPE_FILE_OFICIAL_ZAFRA_2627.zip"

    if not os.path.exists(ruta_zip):
        archivos_zip = glob.glob("*.zip") + glob.glob("data/*.zip")
        if archivos_zip:
            ruta_zip = archivos_zip[0]
        else:
            raise FileNotFoundError(f"No se encontró el archivo ZIP en {ruta_zip}")

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(ruta_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        archivos_shp = glob.glob(
            os.path.join(temp_dir, "**", "*.shp"), recursive=True
        )

        if not archivos_shp:
            raise FileNotFoundError("No se encontró ningún archivo .shp")

        return gpd.read_file(archivos_shp[0])


try:
    gdf = cargar_datos()
except Exception as e:
    st.error("Error al cargar la base geográfica")
    st.exception(e)
    st.stop()


# Mapeo dinámico de nombres de columnas presentes en la capa vectorial
COL_FINCA = next((col for col in ["FINCA", "finca", "Finca", "NOM_FINCA"] if col in gdf.columns), gdf.columns[0])
COL_CODIGO = next((col for col in ["COD_CAM", "CODIGO", "COD_CAMPO", "CODIGO_CAM"] if col in gdf.columns), gdf.columns[1])
COL_CAMPO = next((col for col in ["CAMPO", "campo", "NOM_CAMPO", "NOMBRE_CAM"] if col in gdf.columns), gdf.columns[2])
COL_AREA = next((col for col in ["HA", "HECTAREAS", "AREA_HA", "AREA", "ha"] if col in gdf.columns), None)
COL_ZONA = next((col for col in ["ZONA", "zona", "Zona", "NUM_ZONA"] if col in gdf.columns), None)


# ============================================================
# INTERFAZ DE USUARIO (STREAMLIT)
# ============================================================

st.title("🗺️ Generador de Planos Oficiales - Montelimar")
st.divider()

col_finca, col_semana = st.columns([2, 1])
with col_finca:
    fincas = sorted(gdf[COL_FINCA].dropna().astype(str).unique())
    finca_seleccionada = st.selectbox("Seleccione Finca:", fincas)
with col_semana:
    num_semana = st.text_input("Número de Semana:", "SEMANA 03")

# Filtrar geodatos por la finca seleccionada
finca_gdf = gdf[gdf[COL_FINCA].astype(str) == finca_seleccionada].copy()

# Detección automática de la Zona según la finca seleccionada
if COL_ZONA and not finca_gdf[COL_ZONA].dropna().empty:
    zona_auto = str(finca_gdf[COL_ZONA].dropna().iloc[0]).replace(".0", "")
else:
    zona_auto = "2"

st.subheader("📋 Datos del Cajetín")
c1, c2, c3, c4 = st.columns(4)
with c1:
    tipo_plano = st.text_input("Plano / Tipo", "Plano Aplicación Madurante")
    zafra_txt = st.text_input("Zafra", "Zafra 26-27")
with c2:
    responsable_txt = st.text_input("Responsable", "Ing.Kelvin Vivas")
    jefe_prod_txt = st.text_input("Jefe de Producción", "Ing.Igmar Hurtado")
with c3:
    dibujo_txt = st.text_input("Dibujo", "Ing.Kelvin Vivas")
    zona_txt = st.text_input("Zona (Automatizada)", zona_auto)
with c4:
    uso_txt = st.text_input("Uso", "Comercial")

# Preparación de etiquetas de selección
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

# Cálculo preciso del área en hectáreas
if COL_AREA:
    finca_gdf["AREA_HA_CALC"] = finca_gdf[COL_AREA].fillna(0).astype(float)
else:
    finca_gdf["AREA_HA_CALC"] = finca_gdf.geometry.area / 10000.0


# ============================================================
# ASIGNACIÓN DINÁMICA DE BLOQUES
# ============================================================

st.subheader("🎨 Asignación de Bloques")

if "num_bloques" not in st.session_state:
    st.session_state.num_bloques = 1

col_btn1, col_btn2, _ = st.columns([1, 1, 4])
with col_btn1:
    if st.button("➕ Agregar Bloque"):
        if st.session_state.num_bloques < len(PALETA_BLOQUES):
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
cols_por_fila = 2
columnas_gui = st.columns(cols_por_fila)

for i in range(st.session_state.num_bloques):
    col_idx = i % cols_por_fila
    color_info = PALETA_BLOQUES[i]

    with columnas_gui[col_idx]:
        st.write(f"**Bloque {i+1}** ({color_info['nombre']})")

        labels_elegidos = st.multiselect(
            f"Seleccione campos para Bloque {i+1}:",
            opciones_disponibles,
            default=opciones_disponibles if i == 0 else [],
            key=f"bloque_sel_{i}",
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
generar = st.button("🗺️ GENERAR PLANO EN PDF", use_container_width=True, type="primary")


# ============================================================
# DIBUJO Y EXPORTACIÓN DEL MAPA
# ============================================================

if generar:
    fig = plt.figure(figsize=(8.5, 11), dpi=300)

    # Ventana espacial del mapa
    ax = fig.add_axes([0.04, 0.15, 0.92, 0.79])

    # Capa base en blanco (Sin_Aplicar / No Aplica)
    finca_gdf.plot(
        ax=ax, facecolor="white", edgecolor="black", linewidth=0.8
    )

    lotes_en_bloques = set()
    area_total_bloques = 0.0

    # Representación de polígonos coloreados por bloque
    for num_bloque, datos in bloques_seleccionados.items():
        lotes = datos["lotes"]
        color_hex = datos["color"]

        if lotes:
            lotes_en_bloques.update(lotes)
            sub_gdf = finca_gdf[finca_gdf["CODIGO_STR"].isin(lotes)]

            sub_gdf.plot(
                ax=ax, facecolor=color_hex, edgecolor="black", linewidth=0.8
            )

            area_b = (
                sub_gdf.drop_duplicates(subset=["CODIGO_STR"])["AREA_HA_CALC"]
                .sum()
            )
            area_total_bloques += area_b

    # LEYENDA SIEMPRE CON LOS 6 COLORES EXACTOS Y "No Aplica"
    leyenda_handles = [
        Patch(facecolor="white", edgecolor="black", label="No Aplica")
    ]
    for b_item in PALETA_BLOQUES:
        leyenda_handles.append(
            Patch(facecolor=b_item["hex"], edgecolor="black", label=b_item["bloque"])
        )

    # Ubicación de Etiquetas (Negrita con punto decimal y sombreado blanco)
    campos_unificados = finca_gdf.dissolve(
        by=["CODIGO_STR"],
        aggfunc={COL_CAMPO: "first", "AREA_HA_CALC": "first"}
    ).reset_index()

    for _, row in campos_unificados.iterrows():
        codigo = row["CODIGO_STR"]

        if codigo in lotes_en_bloques:
            punto = row.geometry.representative_point()
            nombre_campo = str(row[COL_CAMPO]) if str(row[COL_CAMPO]) not in ["nan", ""] else codigo
            area_ha = float(row["AREA_HA_CALC"]) if row["AREA_HA_CALC"] is not None else 0.0

            # Formato con PUNTOS para los decimales
            area_str = f"{area_ha:.6f}"
            etiqueta = f"{area_str}\n{nombre_campo}"

            # Etiqueta con letra NEGRITA y sombreado/halo blanco
            ax.annotate(
                etiqueta,
                xy=(punto.x, punto.y),
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                linespacing=1.2,
                bbox=dict(
                    boxstyle="round,pad=0.2",
                    fc="white",
                    ec="none",
                    alpha=0.85
                )
            )

    # TÍTULO PRINCIPAL (Siempre en la esquina superior izquierda)
    titulo_completo = f"FINCA {finca_seleccionada.upper()}"
    if num_semana.strip():
        titulo_completo += f" {num_semana.strip().upper()}"

    ax.set_title(
        titulo_completo,
        fontsize=16,
        fontweight="bold",
        loc="left",
        pad=12
    )

    # Rosa de los vientos
    ax.text(
        0.93, 0.93, "N\nW ┼ E\nS", transform=ax.transAxes,
        ha="center", va="center", fontsize=9.5, fontweight="bold",
        bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="black", lw=1)
    )

    # Leyenda gráfica
    leg = ax.legend(
        handles=leyenda_handles,
        title="LEYENDA\n\n─── Lineas_Eléctricas\n\nBLOQUE",
        loc="lower right",
        frameon=True,
        facecolor="white",
        edgecolor="black",
        fontsize=7.5,
        title_fontsize=8
    )
    leg.get_title().set_fontweight("bold")

    ax.axis("off")

    # Borde marco exterior
    fig.patches.extend([
        Rectangle((0.02, 0.02), 0.96, 0.96,
                  fill=False, edgecolor="black", lw=1.5, transform=fig.transFigure)
    ])

    # ============================================================
    # ESTRUCTURA Y DATOS DEL CAJETÍN INFERIOR
    # ============================================================
    ax_box = fig.add_axes([0.02, 0.02, 0.96, 0.11])
    ax_box.axis("off")

    # División de celdas
    ax_box.plot([0, 1], [1, 1], color="black", lw=1.5)
    ax_box.plot([0.18, 0.18], [0, 1], color="black", lw=1)
    ax_box.plot([0.45, 0.45], [0, 1], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.8, 0.8], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.6, 0.6], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.4, 0.4], color="black", lw=1)
    ax_box.plot([0.45, 1.00], [0.2, 0.2], color="black", lw=1)
    ax_box.plot([0.75, 0.75], [0, 0.8], color="black", lw=1)

    # Logo / Identificación
    ax_box.text(0.09, 0.35, "MONTELIMAR", ha="center", va="center", fontsize=9, fontweight="bold", color="#388E3C")

    # Finca Seleccionada por Defecto
    ax_box.text(0.315, 0.5, f"Finca: {finca_seleccionada}", ha="center", va="center", fontsize=8.5, fontweight="bold")

    # Encabezado Departamento
    ax_box.text(0.725, 0.9, "Departamento Producción", ha="center", va="center", fontsize=8, fontweight="bold")

    # Filas con Datos Automatizados y Fijos
    ax_box.text(0.60, 0.7, f"{tipo_plano}", ha="center", va="center", fontsize=7.5, fontweight="bold")
    ax_box.text(0.875, 0.7, f"Zona: {zona_txt}", ha="center", va="center", fontsize=7.5, fontweight="bold")

    ax_box.text(0.60, 0.5, "Zafra 26-27", ha="center", va="center", fontsize=7.5)
    ax_box.text(0.875, 0.5, f"Uso: {uso_txt}", ha="center", va="center", fontsize=7.5)

    ax_box.text(0.60, 0.3, "Responsable: Ing.Kelvin Vivas", ha="center", va="center", fontsize=7.5, fontweight="bold")
    ax_box.text(0.875, 0.3, f"Area: {area_total_bloques:.2f}", ha="center", va="center", fontsize=7.5, fontweight="bold")

    ax_box.text(0.60, 0.1, "Jefe de Producción: Ing.Igmar Hurtado", ha="center", va="center", fontsize=7.5, fontweight="bold")
    ax_box.text(0.875, 0.1, "Dibujo: Ing.Kelvin Vivas", ha="center", va="center", fontsize=7.5, fontweight="bold")

    st.pyplot(fig, use_container_width=True)

    # Generación del archivo PDF para descarga
    pdf_buffer = io.BytesIO()
    fig.savefig(pdf_buffer, format="pdf", bbox_inches="tight", dpi=300)
    pdf_buffer.seek(0)
    plt.close(fig)

    st.download_button(
        label="📥 DESCARGAR PLANO PDF",
        data=pdf_buffer,
        file_name=f"Plano_{finca_seleccionada.replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
