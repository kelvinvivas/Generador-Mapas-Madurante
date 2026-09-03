import streamlit as st
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from io import BytesIO
import zipfile
import tempfile
import glob
import os


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Generador de Bloques",
    page_icon="🗺️",
    layout="wide"
)


# ============================================================
# ESTILOS CSS
# ============================================================

st.markdown("""
<style>

.main {
    background-color: #f7f9f7;
}

h1 {
    color: #1B5E20;
}

div[data-testid="stMetric"] {
    background-color: white;
    border: 1px solid #e0e0e0;
    padding: 15px;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CARGAR SHAPEFILE
# ============================================================

@st.cache_data
def cargar_datos():

    ruta_zip = "data/SHAPE_FILE_OFICIAL_ZAFRA_2627.zip"

    with tempfile.TemporaryDirectory() as temp_dir:

        # Extraer archivos
        with zipfile.ZipFile(ruta_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # Buscar archivo SHP
        archivos_shp = glob.glob(
            os.path.join(
                temp_dir,
                "**",
                "*.shp"
            ),
            recursive=True
        )

        if not archivos_shp:
            raise FileNotFoundError(
                "No se encontró archivo .shp"
            )

        # Leer shapefile
        gdf = gpd.read_file(
            archivos_shp[0]
        )

        return gdf


# ============================================================
# CARGAR INFORMACIÓN
# ============================================================

try:

    gdf = cargar_datos()

except Exception as e:

    st.error("Error cargando la base geográfica")

    st.exception(e)

    st.stop()


# ============================================================
# COLUMNAS DEL SHAPEFILE
# ============================================================

COL_FINCA = "FINCA"
COL_CODIGO = "COD_CAM"
COL_CAMPO = "CAMPO"
COL_AREA = "HA"


# ============================================================
# ENCABEZADO
# ============================================================

st.title("🗺️ Generador de Mapas por Bloques")

st.markdown("""
Seleccione una finca y agrupe sus campos en bloques
para generar automáticamente un mapa en PDF.
""")

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("⚙️ Información")

st.sidebar.success(
    f"Base cargada: {len(gdf):,} campos"
)

st.sidebar.write("Columnas utilizadas:")

st.sidebar.write("• FINCA")
st.sidebar.write("• COD_CAM")
st.sidebar.write("• CAMPO")
st.sidebar.write("• HA")


# ============================================================
# SELECCIONAR FINCA
# ============================================================

st.header("1️⃣ Selección de Finca")

fincas = sorted(
    gdf[COL_FINCA]
    .dropna()
    .astype(str)
    .unique()
)

finca_seleccionada = st.selectbox(
    "Seleccione la finca",
    fincas
)


# ============================================================
# FILTRAR FINCA
# ============================================================

finca_gdf = gdf[
    gdf[COL_FINCA].astype(str)
    == finca_seleccionada
].copy()


# ============================================================
# CONVERTIR CÓDIGO A TEXTO
# ============================================================

finca_gdf["CODIGO_STR"] = (
    finca_gdf[COL_CODIGO]
    .fillna("")
    .astype(str)
    .str.replace(".0", "", regex=False)
)


# ============================================================
# LISTA DE CAMPOS
# ============================================================

campos_opciones = (
    finca_gdf
    .sort_values("CODIGO_STR")["CODIGO_STR"]
    .unique()
    .tolist()
)


# ============================================================
# BLOQUES
# ============================================================

st.header("2️⃣ Organización de Bloques")

col1, col2 = st.columns(2)


# ============================================================
# BLOQUE 1
# ============================================================

with col1:

    st.markdown("## 🟨 Bloque 1")

    bloque1 = st.multiselect(
        "Seleccione los códigos de campo",
        campos_opciones,
        key="bloque_1"
    )


# ============================================================
# BLOQUE 2
# ============================================================

with col2:

    st.markdown("## 🟩 Bloque 2")

    bloque2 = st.multiselect(
        "Seleccione los códigos de campo",
        campos_opciones,
        key="bloque_2"
    )


# ============================================================
# VALIDAR DUPLICADOS
# ============================================================

duplicados = set(bloque1).intersection(
    set(bloque2)
)

if duplicados:

    st.warning(
        "⚠️ Los siguientes campos están repetidos: "
        + ", ".join(duplicados)
    )


# ============================================================
# BOTÓN GENERAR
# ============================================================

st.divider()

generar = st.button(
    "🗺️ GENERAR MAPA",
    use_container_width=True,
    type="primary"
)


# ============================================================
# GENERACIÓN DEL MAPA
# ============================================================

if generar:

    if duplicados:

        st.error(
            "Corrija los campos duplicados antes de generar el mapa."
        )

        st.stop()


    # ========================================================
    # FILTRAR BLOQUES
    # ========================================================

    gdf_bloque1 = finca_gdf[
        finca_gdf["CODIGO_STR"].isin(bloque1)
    ]

    gdf_bloque2 = finca_gdf[
        finca_gdf["CODIGO_STR"].isin(bloque2)
    ]


    # ========================================================
    # CREAR FIGURA
    # ========================================================

    fig, ax = plt.subplots(
        figsize=(14, 10)
    )


    # ========================================================
    # TODOS LOS CAMPOS DE LA FINCA
    # ========================================================

    finca_gdf.plot(
        ax=ax,
        facecolor="#F5F5F5",
        edgecolor="black",
        linewidth=0.7
    )


    # ========================================================
    # BLOQUE 1 - AMARILLO
    # ========================================================

    if not gdf_bloque1.empty:

        gdf_bloque1.plot(
            ax=ax,
            facecolor="#FFD700",
            edgecolor="black",
            linewidth=1.2
        )


    # ========================================================
    # BLOQUE 2 - VERDE
    # ========================================================

    if not gdf_bloque2.empty:

        gdf_bloque2.plot(
            ax=ax,
            facecolor="#32CD32",
            edgecolor="black",
            linewidth=1.2
        )


    # ========================================================
    # ETIQUETAS DE LOS CAMPOS
    # ========================================================

    for _, row in finca_gdf.iterrows():

        punto = row.geometry.representative_point()

        codigo = row["CODIGO_STR"]

        ax.annotate(
            codigo,
            xy=(punto.x, punto.y),
            ha="center",
            va="center",
            fontsize=7,
            fontweight="bold"
        )


    # ========================================================
    # TÍTULO DEL MAPA
    # ========================================================

    ax.set_title(
        f"MAPA DE BLOQUES\nFINCA: {finca_seleccionada}",
        fontsize=18,
        fontweight="bold",
        pad=20
    )


    # ========================================================
    # LEYENDA
    # ========================================================

    leyenda = [

        Patch(
            facecolor="#FFD700",
            edgecolor="black",
            label=f"Bloque 1 ({len(bloque1)} campos)"
        ),

        Patch(
            facecolor="#32CD32",
            edgecolor="black",
            label=f"Bloque 2 ({len(bloque2)} campos)"
        ),

        Patch(
            facecolor="#F5F5F5",
            edgecolor="black",
            label="Otros campos"
        )

    ]

    ax.legend(
        handles=leyenda,
        loc="lower right",
        frameon=True,
        fontsize=10
    )


    # ========================================================
    # OCULTAR EJES
    # ========================================================

    ax.axis("off")


    # ========================================================
    # MOSTRAR MAPA
    # ========================================================

    st.header("3️⃣ Vista previa")

    st.pyplot(
        fig,
        use_container_width=True
    )


    # ========================================================
    # CALCULAR ÁREAS
    # ========================================================

    area_total = (
        finca_gdf[COL_AREA]
        .fillna(0)
        .sum()
    )

    area_bloque1 = (
        gdf_bloque1[COL_AREA]
        .fillna(0)
        .sum()
    )

    area_bloque2 = (
        gdf_bloque2[COL_AREA]
        .fillna(0)
        .sum()
    )


    # ========================================================
    # MÉTRICAS
    # ========================================================

    st.header("4️⃣ Resumen de Áreas")

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Área Finca",
        f"{area_total:,.2f} ha"
    )

    m2.metric(
        "🟨 Bloque 1",
        f"{area_bloque1:,.2f} ha"
    )

    m3.metric(
        "🟩 Bloque 2",
        f"{area_bloque2:,.2f} ha"
    )

    m4.metric(
        "Área Seleccionada",
        f"{area_bloque1 + area_bloque2:,.2f} ha"
    )


    # ========================================================
    # GENERAR PDF
    # ========================================================

    pdf_buffer = BytesIO()

    fig.savefig(
        pdf_buffer,
        format="pdf",
        bbox_inches="tight",
        dpi=300
    )

    pdf_buffer.seek(0)


    # ========================================================
    # BOTÓN DESCARGAR PDF
    # ========================================================

    st.divider()

    st.download_button(
        label="📥 DESCARGAR MAPA EN PDF",
        data=pdf_buffer,
        file_name=f"Mapa_Bloques_{finca_seleccionada}.pdf",
        mime="application/pdf",
        use_container_width=True
    )
