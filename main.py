import flet as ft
import json
import os
import sys
import datetime
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# -------------------------------------------------------------
# Resolución de rutas compatible con PyInstaller (.exe) y Web (Pyodide)
# -------------------------------------------------------------
def resource_path(relative_path):
    """Obtener ruta absoluta al recurso, compatible con PyInstaller y Pyodide."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# Asegurar la existencia de directorios clave (Seguro para Web/Pyodide)
try:
    os.makedirs(resource_path("assets"), exist_ok=True)
except Exception as e:
    print(f"Aviso: No se pudo crear la carpeta assets (esperable en entornos web de sólo lectura): {e}")


# -------------------------------------------------------------
# Carga de Datos Clínicos (Con soporte para Pyodide Web-Safe y Local)
# -------------------------------------------------------------
def get_executable_dir():
    """Obtiene la carpeta donde se encuentra el script/ejecutable."""
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def cargar_datos_clinicos():
    # 1. Intentar cargar desde el sistema de archivos virtual o físico (Pyodide virtual, modo desarrollo o desktop)
    rutas = [
        os.path.join(get_executable_dir(), "datos_clinicos.json"),
        os.path.join(get_executable_dir(), "..", "datos_clinicos.json"),
        "assets/datos_clinicos.json",
        "../assets/datos_clinicos.json",
        "datos_clinicos.json",
        resource_path("datos_clinicos.json"),
        resource_path(os.path.join("..", "datos_clinicos.json"))
    ]
    for path in rutas:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    print(f"Cargado datos_clinicos.json localmente desde {path}")
                    return json.load(f)
            except Exception as e:
                print(f"Error al cargar {path}: {e}")

    # 2. Si no se encuentra en el sistema de archivos virtual, intentar fetch HTTP (Pyodide en web)
    try:
        import urllib.request
        import js
        base_url = js.window.location.origin + js.window.location.pathname
        if base_url.endswith("index.html"):
            base_url = "/".join(base_url.split("/")[:-1])
        if not base_url.endswith("/"):
            base_url += "/"
        url = base_url + "datos_clinicos.json"
        print(f"Fetch HTTP datos_clinicos.json desde: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error al descargar datos_clinicos.json vía HTTP: {e}")

    return {}


datos_clinicos = cargar_datos_clinicos()


# -------------------------------------------------------------
# Cargador del Logo de la UNNE (Soporte Local y Web-Safe)
# -------------------------------------------------------------
def load_logo_image():
    # 1. Intentar cargar desde rutas del sistema de archivos local / virtual de Pyodide
    rutas = [
        resource_path(os.path.join("assets", "logo.png")),
        os.path.join("assets", "logo.png"),
        os.path.join("..", "assets", "logo.png"),
        os.path.join("web_version", "assets", "logo.png"),
        "assets/logo.png"
    ]
    for path in rutas:
        if os.path.exists(path):
            try:
                from reportlab.platypus import Image
                return Image(path, width=50, height=60, kind='proportional')
            except Exception as e:
                print(f"Error al cargar logo de ruta {path}: {e}")
                
    # 2. Si no se encuentra, intentar fetch HTTP en Pyodide
    try:
        import urllib.request
        import js
        base_url = js.window.location.origin + js.window.location.pathname
        if base_url.endswith("index.html"):
            base_url = "/".join(base_url.split("/")[:-1])
        if not base_url.endswith("/"):
            base_url += "/"
        url = base_url + "assets/logo.png"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            image_data = response.read()
            return Image(io.BytesIO(image_data), width=50, height=60, kind='proportional')
    except Exception as e:
        print(f"Error al descargar logo vía HTTP: {e}")
        
    return None


# -------------------------------------------------------------
# Helper: Discriminator between leaf param and organ container
# -------------------------------------------------------------
def is_leaf_param(data):
    """Check if data is a leaf clinical parameter (has 'Normal' key directly)."""
    return isinstance(data, dict) and 'Normal' in data


# -------------------------------------------------------------
# Estructura del Estado de Sesión Temporal
# -------------------------------------------------------------
session_state = {
    "especie": "",
    "paciente": {
        "nombre": "", "edad": "", "sexo": "", "estado_reproductivo": "", "practicante": "",
        "raza": "", "peso": "", "propietario": "",
        "establecimiento": "", "renspa": "", "marcas": "", "aptitud": ""
    },
    "anamnesis": {"motivo": "", "preguntas": ""},
    "evaluaciones": {},
    "observaciones": {},
    "active_region": ""
}


# -------------------------------------------------------------
# Función de Generación de PDF (ReportLab)
# Soporta tanto buffers en memoria (BytesIO) como rutas físicas
# -------------------------------------------------------------
def generar_pdf(state, target):
    # Crear documento A4 con márgenes de 40pt
    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Paleta de colores institucional de la UNNE (Azul Marino y Gris)
    c_primary = colors.HexColor('#003366')      # Azul Marino UNNE
    c_secondary = colors.HexColor('#555555')    # Gris Oscuro
    c_text_dark = colors.HexColor('#212121')    # Texto Principal
    
    # Estilos de Párrafos Personalizados
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=19,
        textColor=c_primary,
        alignment=TA_LEFT
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=c_text_dark
    )
    
    label_style = ParagraphStyle(
        'LabelBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_primary
    )
    
    normal_style = ParagraphStyle(
        'StateNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#2E7D32')  # Verde Clínico (NORMAL)
    )
    
    alterado_style = ParagraphStyle(
        'StateAltered',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#C62828')  # Rojo Clínico (ALTERADO)
    )
    
    header_table_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    
    cell_style = ParagraphStyle(
        'TableCellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=c_text_dark
    )
    
    obs_style = ParagraphStyle(
        'ObsText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#424242')
    )

    story = []
    
    # 1. Carga Segura y Adaptada del Logo
    logo_img = load_logo_image()
                    
    # Párrafos del encabezado institucional
    inst_title_style = ParagraphStyle(
        'InstTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=19,
        textColor=c_primary,
        spaceAfter=2
    )
    inst_subtitle_style = ParagraphStyle(
        'InstSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=15,
        textColor=c_secondary,
        spaceAfter=2
    )
    inst_doc_style = ParagraphStyle(
        'InstDocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=c_primary,
        spaceAfter=2
    )
    
    text_col = [
        Paragraph("UNIVERSIDAD NACIONAL DEL NORDESTE", inst_title_style),
        Paragraph("Facultad de Ciencias Veterinarias", inst_subtitle_style),
        Paragraph("Historia Clínica Académica - Práctica de Semiología", inst_doc_style)
    ]
    
    if logo_img:
        header_table = Table([[logo_img, text_col]], colWidths=[60, 450])
    else:
        header_table = Table([[text_col]], colWidths=[510])
        
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(header_table)
    
    # Línea divisoria en color azul marino institucional
    divider = Table([['']], colWidths=[510])
    divider.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1.5, c_primary),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 4))
    
    # Fecha de emisión del reporte
    date_text = Paragraph(f"Fecha de Emisión: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                          ParagraphStyle('DateText', parent=body_style, alignment=TA_RIGHT, fontSize=8, textColor=colors.HexColor('#555555')))
    story.append(date_text)
    story.append(Spacer(1, 8))
    
    # 2. Ficha de Datos del Paciente (Diseño Dinámico)
    paciente = state["paciente"]
    
    label_map = {
        "nombre": "Paciente",
        "propietario": "Propietario / Tutor",
        "raza": "Raza",
        "edad": "Edad",
        "peso": "Peso (kg)",
        "sexo": "Sexo",
        "estado_reproductivo": "Estado Reproductivo",
        "practicante": "Practicante / Evaluador",
        "establecimiento": "Establecimiento",
        "renspa": "RENSPA",
        "marcas": "Marcas / Señales",
        "aptitud": "Aptitud"
    }

    info_pairs = [("Especie", state["especie"])]
    for key, lbl in label_map.items():
        val = paciente.get(key, "").strip()
        if val and val != "No especificado":
            info_pairs.append((lbl, val))

    # Construir filas de 2 pares por fila
    info_data = []
    for i in range(0, len(info_pairs), 2):
        row = []
        row.append(Paragraph(info_pairs[i][0] + ":", label_style))
        row.append(Paragraph(info_pairs[i][1], body_style))
        if i + 1 < len(info_pairs):
            row.append(Paragraph(info_pairs[i+1][0] + ":", label_style))
            row.append(Paragraph(info_pairs[i+1][1], body_style))
        else:
            row.extend([Paragraph("", body_style), Paragraph("", body_style)])
        info_data.append(row)

    info_table = Table(info_data, colWidths=[80, 160, 140, 130])
    info_table.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,0), 0.75, c_primary),
        ('LINEBELOW', (0,-1), (-1,-1), 0.75, c_primary),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))
    
    # 2.5 Anamnesis (si existe)
    anamnesis = state.get("anamnesis", {})
    motivo = anamnesis.get("motivo", "").strip()
    preguntas = anamnesis.get("preguntas", "").strip()
    
    if motivo or preguntas:
        story.append(Paragraph("Anamnesis Clínica", section_style))
        
        anamnesis_data = []
        if motivo:
            anamnesis_data.append([Paragraph("Motivo de Consulta:", label_style), Paragraph(motivo.replace("\n", "<br/>"), body_style)])
        if preguntas:
            anamnesis_data.append([Paragraph("Historial / Preguntas al tutor:", label_style), Paragraph(preguntas.replace("\n", "<br/>"), body_style)])
            
        anamnesis_table = Table(anamnesis_data, colWidths=[150, 360])
        anamnesis_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(anamnesis_table)
        story.append(Spacer(1, 10))
    
    # 3. Hallazgos Clínicos por Región (Particular y General)
    evaluaciones = state["evaluaciones"]
    observaciones = state["observaciones"]
    especie_data = state["datos_especie"]
    
    has_any_eval = False
    
    # Helper to check visibility conditions for a parameter
    def check_condicion_visible(condicion, paciente):
        """Returns True if the parameter should be visible given the patient data."""
        if condicion == "Siempre":
            return True
        if isinstance(condicion, dict):
            sexo_req = condicion.get("sexo")
            repro_req = condicion.get("estado_reproductivo")
            if sexo_req and paciente.get("sexo") != sexo_req:
                return False
            if repro_req and paciente.get("estado_reproductivo") != repro_req:
                return False
        return True

    # Estilo para la columna de referencia (gris claro, cursiva, pequeño)
    ref_style = ParagraphStyle(
        'RefGray',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#AAAAAA')
    )

    # Mapa de unidades por nombre de parámetro para auto-completar (legacy qualitative params)
    unit_map = {
        "Temperatura": "°C",
        "Frecuencia Cardíaca": "lpm",
        "Frecuencia Respiratoria": "rpm",
        "Frecuencia y Ritmo Cardíaco": "lpm",
    }

    def format_value_with_unit(p_name, raw_value):
        """Agrega unidad al valor si el alumno puso solo un número."""
        if not raw_value:
            return raw_value
        unit = unit_map.get(p_name, "")
        if not unit:
            return raw_value
        val_stripped = raw_value.strip()
        import re
        if re.match(r'^[\d.,\s\-/]+$', val_stripped):
            return f"{val_stripped} {unit}"
        return raw_value

    def render_qualitative_row(p_name, p_data, eval_info, table_data):
        """Renders a qualitative (Normal/Alterado) parameter row into table_data."""
        estado = eval_info["estado"]
        desc_text = p_data["Normal"]
        ref_para = Paragraph(desc_text, ref_style)

        if estado == "Normal":
            custom_text = eval_info.get("custom", "").strip()
            custom_text = format_value_with_unit(p_name, custom_text)
            if custom_text:
                result_text = f"<font color='#2E7D32'><b>NORMAL</b></font> &mdash; <font color='#212121'>{custom_text}</font>"
            else:
                result_text = "<font color='#2E7D32'><b>NORMAL</b></font>"
        else:
            detalles_list = eval_info.get("detalles", [])
            custom_text = eval_info.get("custom", "").strip()
            custom_text = format_value_with_unit(p_name, custom_text)
            parts = []
            if detalles_list:
                parts.append(", ".join(detalles_list))
            if custom_text:
                parts.append(custom_text)
            detalles_str = " | ".join(parts) if parts else "Alteración no detallada"
            result_text = f"<font color='#C62828'><b>ALTERADO</b></font> &mdash; <font color='#212121'>{detalles_str}</font>"

        table_data.append([
            Paragraph(p_name, cell_style),
            Paragraph(result_text, cell_style),
            ref_para
        ])

    # Estilo para organ sub-header rows in PDF
    organ_header_style = ParagraphStyle(
        'OrganHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=c_primary
    )

    for region, parametros in especie_data.items():
        region_rows = []  # Collected table rows for this region
        has_region_content = False

        for p_name, p_data in parametros.items():
            if is_leaf_param(p_data):
                # Flat leaf parameter (EOG style)
                condicion = p_data.get("condicion_visible", "Siempre")
                if not check_condicion_visible(condicion, paciente):
                    continue

                if p_data.get("tipo_input") == "numerico":
                    # Numeric parameter
                    if p_name in evaluaciones:
                        valor = evaluaciones[p_name].get("valor_numerico", "").strip()
                        if valor:
                            has_region_content = True
                            unidad = p_data.get("unidad", "")
                            rango = p_data.get("rango_referencia", "")
                            result_text = f"<font color='#003366'><b>{valor}</b> {unidad}</font>"
                            ref_text = f"{rango} {unidad}" if rango else ""
                            region_rows.append([
                                Paragraph(p_name, cell_style),
                                Paragraph(result_text, cell_style),
                                Paragraph(ref_text, ref_style)
                            ])
                else:
                    # Qualitative parameter
                    if p_name in evaluaciones and evaluaciones[p_name].get("estado") in ["Normal", "Alterado"]:
                        has_region_content = True
                        render_qualitative_row(p_name, p_data, evaluaciones[p_name], region_rows)
            else:
                # Nested organ container (Region → Organ → Method → param_data)
                organ_name = p_name
                organ_data = p_data
                organ_has_content = False
                organ_rows = []

                # Check organ-level visibility by inspecting first method's condicion_visible
                first_method_data = next(iter(organ_data.values()), None)
                if first_method_data and isinstance(first_method_data, dict):
                    organ_condicion = first_method_data.get("condicion_visible", "Siempre")
                    if not check_condicion_visible(organ_condicion, paciente):
                        continue

                for method_name, method_data in organ_data.items():
                    if not isinstance(method_data, dict):
                        continue
                    condicion = method_data.get("condicion_visible", "Siempre")
                    if not check_condicion_visible(condicion, paciente):
                        continue

                    composite_key = f"{organ_name} > {method_name}"
                    if composite_key in evaluaciones and evaluaciones[composite_key].get("estado") in ["Normal", "Alterado"]:
                        organ_has_content = True
                        render_qualitative_row(composite_key, method_data, evaluaciones[composite_key], organ_rows)

                if organ_has_content:
                    has_region_content = True
                    # Add organ sub-header row spanning all 3 columns
                    region_rows.append([
                        Paragraph(f"<b>{organ_name}</b>", organ_header_style),
                        Paragraph("", cell_style),
                        Paragraph("", cell_style)
                    ])
                    region_rows.extend(organ_rows)

        region_obs = observaciones.get(region, "").strip()

        if has_region_content or region_obs:
            has_any_eval = True
            story.append(Paragraph(region, section_style))

            if has_region_content and region_rows:
                table_data = [
                    [
                        Paragraph("Parámetro", header_table_style),
                        Paragraph("Resultado del Examen", header_table_style),
                        Paragraph("Ref.", header_table_style)
                    ]
                ]
                table_data.extend(region_rows)

                param_table = Table(table_data, colWidths=[110, 290, 110])
                param_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), c_primary),
                    ('GRID', (0,0), (-1,-1), 0.5, c_primary),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F4F6F9')]),
                    ('ALIGN', (0,0), (1,-1), 'LEFT'),
                    ('ALIGN', (2,0), (2,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(param_table)
                story.append(Spacer(1, 8))

            if region_obs:
                obs_box_data = [
                    [Paragraph("Observaciones adicionales de la región:", label_style)],
                    [Paragraph(region_obs.replace("\n", "<br/>"), obs_style)]
                ]
                obs_table = Table(obs_box_data, colWidths=[510])
                obs_table.setStyle(TableStyle([
                    ('LINEABOVE', (0,0), (-1,0), 0.5, colors.HexColor('#CCCCCC')),
                    ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor('#CCCCCC')),
                    ('PADDING', (0,0), (-1,-1), 5),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ]))
                story.append(obs_table)
                story.append(Spacer(1, 10))
                
    if not has_any_eval:
        story.append(Spacer(1, 20))
        story.append(Paragraph("No se registraron parámetros evaluados en esta sesión de revisión.", 
                               ParagraphStyle('NoEval', parent=body_style, alignment=TA_CENTER, fontName='Helvetica-Oblique')))
        
    # 4. Sección de Firma
    story.append(Spacer(1, 40))
    signature_data = [
        [
            Paragraph("________________________________________", ParagraphStyle('Line', parent=body_style, alignment=TA_CENTER)),
        ],
        [
            Paragraph("Firma del Médico Veterinario de Turno", ParagraphStyle('SubSign', parent=body_style, alignment=TA_CENTER, fontName='Helvetica-Bold')),
        ]
    ]
    signature_table = Table(signature_data, colWidths=[510])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    
    # Agrupar firma para evitar que quede huérfana en una nueva página
    story.append(KeepTogether([signature_table]))
    
    doc.build(story)


# -------------------------------------------------------------
# Trigger de Descarga Seguro en Web (JS Interop) y Desktop (Local)
# -------------------------------------------------------------
def download_file_web(page: ft.Page, bytes_data: bytes, filename: str, content_type: str):
    """Fuerza la descarga de un buffer de bytes en el navegador del usuario usando Data URI si es web, o guarda en local."""
    if page.web:
        b64 = base64.b64encode(bytes_data).decode('utf-8')
        page.launch_url(f"data:{content_type};base64,{b64}")
    else:
        try:
            import os
            # Fallback en modo desarrollo local o desktop (guarda en Descargas)
            descargas_path = os.path.join(os.path.expanduser("~"), "Downloads")
            if os.path.exists(descargas_path):
                out_path = os.path.join(descargas_path, filename)
            else:
                out_path = filename
                
            with open(out_path, "wb") as f:
                f.write(bytes_data)
                
            # Abrir automáticamente si es un PDF generado en modo local
            if filename.endswith(".pdf"):
                try:
                    os.startfile(out_path)
                except AttributeError:
                    import platform
                    import subprocess
                    if platform.system() == "Darwin":
                        subprocess.Popen(["open", out_path])
                    else:
                        subprocess.Popen(["xdg-open", out_path])
        except Exception as e:
            # Si falla guardar en Descargas, guardar en el directorio de trabajo
            with open(filename, "wb") as f:
                f.write(bytes_data)


# -------------------------------------------------------------
# Aplicación Principal en Flet
# -------------------------------------------------------------
def main(page: ft.Page):
    import json

    def force_web_download(filename, b64_data, mime_type):
        """Fuerza la descarga nativa en el navegador saltándose los bloqueos de popup."""
        import js
        document = js.document
        link = document.createElement('a')
        link.href = f"data:{mime_type};base64,{b64_data}"
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)

    def trigger_web_upload(on_success_callback):
        """Usa el input nativo del DOM para leer archivos en memoria (Pyodide Static Web)."""
        import js
        from pyodide.ffi import create_proxy

        def on_file_loaded(event):
            json_str = event.target.result
            on_success_callback(json_str)
            
        def on_file_selected(event):
            file = event.target.files.item(0)
            if file:
                reader = js.FileReader.new()
                reader.onload = create_proxy(on_file_loaded)
                reader.readAsText(file)

        input_elem = js.document.createElement("input")
        input_elem.type = "file"
        input_elem.accept = ".json"
        input_elem.addEventListener("change", create_proxy(on_file_selected))
        input_elem.click()

    def procesar_json_cargado(json_str):
        try:
            data = json.loads(json_str)
            global session_state
            session_state["especie"] = data.get("especie", "")
            session_state["paciente"] = data.get("paciente", {
                "nombre": "", "edad": "", "sexo": "", "estado_reproductivo": "", "practicante": "",
                "raza": "", "peso": "", "propietario": "",
                "establecimiento": "", "renspa": "", "marcas": "", "aptitud": ""
            })
            session_state["anamnesis"] = data.get("anamnesis", {"motivo": "", "preguntas": ""})
            session_state["evaluaciones"] = data.get("evaluaciones", {})
            session_state["observaciones"] = data.get("observaciones", {})
            session_state["active_region"] = data.get("active_region", "")
            
            snack = ft.SnackBar(ft.Text("¡Ficha clínica cargada con éxito!"), bgcolor=ft.Colors.GREEN_700)
            page.open(snack)
            
            if session_state["especie"]:
                show_evaluation_screen()
            else:
                show_patient_data_screen(clear_state=False)
            page.update()
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"Error al leer/procesar ficha: {str(ex)}"), bgcolor=ft.Colors.RED_600))

    # 1. Instanciar vacío 
    file_picker = ft.FilePicker()
    
    # Manejador del FilePicker (Solo ejecutado en Desktop/modo local)
    def on_file_picker_result(e):
        if not e.files or len(e.files) == 0: 
            return
        
        try:
            with open(e.files[0].path, "r", encoding="utf-8") as f:
                procesar_json_cargado(f.read())
        except Exception as ex:
            page.open(ft.SnackBar(ft.Text(f"Error: {str(ex)}"), bgcolor=ft.Colors.RED_600))

    # 3. Asignar la función y agregarlo a la capa invisible (overlay) (como indicó el usuario)
    file_picker.on_result = on_file_picker_result
    page.overlay.append(file_picker)

    page.title = "Registro Clínico Veterinario - Historia Académica"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window_width = 1000
    page.window_height = 850
    page.window_min_width = 850
    page.window_min_height = 650
    
    # ---------------------------------------------------------
    # Inyección de Compatibilidad page.open / page.close para Flet 0.85.3
    # ---------------------------------------------------------
    if not hasattr(page, "open"):
        def page_open(control):
            if isinstance(control, ft.AlertDialog):
                page.dialog = control
                control.open = True
            elif isinstance(control, ft.SnackBar):
                page.snack_bar = control
                control.open = True
            page.update()
        page.open = page_open

    if not hasattr(page, "close"):
        def page_close(control):
            control.open = False
            page.update()
        page.close = page_close

    # ---------------------------------------------------------
    # Controles de Tema
    # ---------------------------------------------------------
    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            theme_btn.icon = ft.Icons.DARK_MODE
            theme_btn.tooltip = "Activar Modo Oscuro"
        else:
            page.theme_mode = ft.ThemeMode.DARK
            theme_btn.icon = ft.Icons.LIGHT_MODE
            theme_btn.tooltip = "Activar Modo Claro"
        page.update()
        
    theme_btn = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        tooltip="Activar Modo Oscuro",
        on_click=toggle_theme,
        icon_color=ft.Colors.WHITE
    )
    
    # Contenedor principal donde se cargan dinámicamente las pantallas
    main_container = ft.Container(expand=True)
    page.add(main_container)

    # ---------------------------------------------------------
    # Importar y Exportar Sesión (JSON)
    # ---------------------------------------------------------
    def export_session_click(e):
        try:
            # Sincronizar campos del formulario antes de exportar si están activos en pantalla 1
            if hasattr(page, "_form_fields") and page._form_fields:
                fields = page._form_fields
                is_grande = session_state.get("especie") in ("Equino", "Bovino", "Porcino")
                session_state["paciente"] = {
                    "nombre": fields["nombre"].value.strip() if fields["nombre"].value else "",
                    "raza": fields["raza"].value.strip() if fields["raza"].value else "",
                    "edad": fields["edad"].value.strip() if fields["edad"].value else "",
                    "peso": fields["peso"].value.strip() if fields["peso"].value else "",
                    "sexo": fields["sexo"].value if fields["sexo"].value else "",
                    "estado_reproductivo": fields["estado_repro"].value if fields["estado_repro"].value else "",
                    "propietario": fields["propietario"].value.strip() if fields["propietario"].value else "No especificado",
                    "practicante": fields["practicante"].value.strip() if fields["practicante"].value else "No especificado",
                    "establecimiento": fields["establecimiento"].value.strip() if is_grande and fields["establecimiento"].value else "",
                    "renspa": fields["renspa"].value.strip() if is_grande and fields["renspa"].value else "",
                    "marcas": fields["marcas"].value.strip() if is_grande and fields["marcas"].value else "",
                    "aptitud": fields["aptitud"].value.strip() if is_grande and fields["aptitud"].value else "",
                }

            if session_state.get("especie"):
                session_state["datos_especie"] = datos_clinicos.get(session_state["especie"])

            # Exportar como JSON binario
            json_str = json.dumps(session_state, indent=4, ensure_ascii=False)
            json_bytes = json_str.encode('utf-8')
            
            patient_name = session_state["paciente"].get("nombre", "Paciente").strip().replace(" ", "_")
            if not patient_name:
                patient_name = "Paciente"
            especie = session_state.get("especie", "SinEspecie")
            fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Ficha_{patient_name}_{especie}_{fecha}.json"
            
            import base64
            b64_json = base64.b64encode(json_bytes).decode('utf-8')
            if page.web:
                force_web_download(filename, b64_json, "application/json")
            else:
                download_file_web(page, json_bytes, filename, "application/json")
            
            snack = ft.SnackBar(
                ft.Text(f"¡Progreso guardado! Se descargó '{filename}'."),
                bgcolor=ft.Colors.GREEN_700
            )
            page.open(snack)
        except Exception as ex:
            snack = ft.SnackBar(
                ft.Text(f"Error al guardar progreso: {str(ex)}"),
                bgcolor=ft.Colors.RED_600
            )
            page.open(snack)

    # Nota: FilePicker y su callback fueron inicializados al inicio de main() para compatibilidad web

    # Manejador del botón Visual de Importar
    def handle_import_click(e):
        if page.web:
            trigger_web_upload(procesar_json_cargado)
        else:
            file_picker.pick_files(allowed_extensions=["json"])

    # ---------------------------------------------------------
    # Configuración del AppBar Global
    # ---------------------------------------------------------
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.LOCAL_HOSPITAL_ROUNDED, color=ft.Colors.WHITE),
        leading_width=40,
        title=ft.Text("VetClinic UNNE - Ficha Clínica", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
        center_title=False,
        bgcolor=ft.Colors.TEAL_900,
        actions=[
            ft.IconButton(ft.Icons.SAVE_ALT, tooltip="Guardar Progreso (Exportar)", on_click=export_session_click, icon_color=ft.Colors.WHITE),
            ft.IconButton(ft.Icons.UPLOAD_FILE, tooltip="Cargar Ficha (Importar)", on_click=handle_import_click, icon_color=ft.Colors.WHITE),
            theme_btn,
        ],
    )

    # ---------------------------------------------------------
    # PANTALLA 1: Selección de Especie y Formulario Dinámico
    # ---------------------------------------------------------
    def show_patient_data_screen(clear_state=True):
        if clear_state:
            # Inicializar y limpiar estado anterior
            session_state["paciente"] = {
                "nombre": "", "edad": "", "sexo": "", "estado_reproductivo": "", "practicante": "",
                "raza": "", "peso": "", "propietario": "",
                "establecimiento": "", "renspa": "", "marcas": "", "aptitud": ""
            }
            session_state["anamnesis"] = {"motivo": "", "preguntas": ""}
            session_state["especie"] = ""
            session_state["evaluaciones"] = {}
            session_state["observaciones"] = {}
            session_state["active_region"] = ""
            
        # Restaurar AppBar
        page.appbar.title = ft.Text("VetClinic UNNE - Ficha Clínica", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        page.appbar.leading = ft.Icon(ft.Icons.LOCAL_HOSPITAL_ROUNDED, color=ft.Colors.WHITE)
        page.update()
        
        # Contenedor donde se renderizará el formulario dinámico
        form_container = ft.Container(visible=False)
        
        # Variable para rastrear la especie seleccionada y las tarjetas
        selected_species_ref = {"value": session_state["especie"]}
        species_card_refs = {}  # { species_name: container_control }
        
        # ----- Campos de formulario (se crean aquí para reutilizarlos) -----
        # Campos comunes
        nombre_field = ft.TextField(
            label="Nombre del Paciente *" if not session_state["especie"] or session_state["especie"] not in ("Equino", "Bovino", "Porcino") else "Nombre / ID del Paciente *",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            text_style=ft.TextStyle(weight=ft.FontWeight.W_500),
            value=session_state["paciente"].get("nombre", ""),
            col={"sm": 12, "md": 6}
        )
        raza_field = ft.TextField(
            label="Raza",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("raza", ""),
            col={"sm": 12, "md": 6}
        )
        edad_field = ft.TextField(
            label="Edad (ej. 3 años)",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("edad", ""),
            col={"sm": 12, "md": 6}
        )
        peso_field = ft.TextField(
            label="Peso (kg)",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            keyboard_type=ft.KeyboardType.NUMBER,
            value=session_state["paciente"].get("peso", ""),
            col={"sm": 12, "md": 6}
        )
        propietario_field = ft.TextField(
            label="Propietario / Tutor",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("propietario", ""),
            col={"sm": 12, "md": 6}
        )
        practicante_field = ft.TextField(
            label="Practicante / Evaluador",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("practicante", ""),
            col={"sm": 12, "md": 6}
        )
        
        # Campos exclusivos de grandes
        establecimiento_field = ft.TextField(
            label="Establecimiento",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("establecimiento", ""),
            col={"sm": 12, "md": 6}
        )
        renspa_field = ft.TextField(
            label="RENSPA",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("renspa", ""),
            col={"sm": 12, "md": 6}
        )
        marcas_field = ft.TextField(
            label="Marcas / Señales",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("marcas", ""),
            col={"sm": 12, "md": 6}
        )
        aptitud_field = ft.TextField(
            label="Aptitud",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["paciente"].get("aptitud", ""),
            col={"sm": 12, "md": 6}
        )
        
        # Dropdown de Estado Reproductivo (dinámico según sexo)
        estado_repro_dropdown = ft.Dropdown(
            label="Estado Reproductivo",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            options=[],
            col={"sm": 12, "md": 6},
            visible=False  # Inicialmente oculto
        )
        
        # Restaurar valores si existen
        sexo_val = session_state["paciente"].get("sexo", "")
        repro_val = session_state["paciente"].get("estado_reproductivo", "")
        if sexo_val == "Macho":
            estado_repro_dropdown.options = [
                ft.dropdown.Option(key="Entero", text="No Castrado (Entero)"),
                ft.dropdown.Option(key="Castrado", text="Castrado"),
            ]
            estado_repro_dropdown.value = repro_val if repro_val in ("Entero", "Castrado") else None
            estado_repro_dropdown.visible = True
        elif sexo_val == "Hembra":
            estado_repro_dropdown.options = [
                ft.dropdown.Option(key="Entera", text="No Castrada (Entera)"),
                ft.dropdown.Option(key="Castrada", text="Castrada"),
            ]
            estado_repro_dropdown.value = repro_val if repro_val in ("Entera", "Castrada") else None
            estado_repro_dropdown.visible = True
        
        # Función que escucha el cambio de Sexo
        def on_sexo_changed(e):
            sexo_changed_val = e.control.value
            
            # Cargamos las opciones según el sexo y hacemos visible el campo
            if sexo_changed_val == "Macho":
                estado_repro_dropdown.options = [
                    ft.dropdown.Option(key="Entero", text="No Castrado (Entero)"),
                    ft.dropdown.Option(key="Castrado", text="Castrado"),
                ]
                estado_repro_dropdown.visible = True
            elif sexo_changed_val == "Hembra":
                estado_repro_dropdown.options = [
                    ft.dropdown.Option(key="Entera", text="No Castrada (Entera)"),
                    ft.dropdown.Option(key="Castrada", text="Castrada"),
                ]
                estado_repro_dropdown.visible = True
            else:
                estado_repro_dropdown.options = []
                estado_repro_dropdown.visible = False
                
            estado_repro_dropdown.value = None
            estado_repro_dropdown.update()
            form_container.update()
        
        # Dropdown de Sexo
        sexo_dropdown = ft.Dropdown(
            label="Sexo",
            border_color=ft.Colors.TEAL_400,
            focused_border_color=ft.Colors.TEAL_700,
            options=[
                ft.dropdown.Option("Macho"),
                ft.dropdown.Option("Hembra"),
            ],
            value=sexo_val if sexo_val else None,
            on_select=on_sexo_changed,
            col={"sm": 12, "md": 6}
        )
        
        # Registrar referencias de campos para exportación rápida
        page._form_fields = {
            "nombre": nombre_field,
            "raza": raza_field,
            "edad": edad_field,
            "peso": peso_field,
            "sexo": sexo_dropdown,
            "estado_repro": estado_repro_dropdown,
            "propietario": propietario_field,
            "practicante": practicante_field,
            "establecimiento": establecimiento_field,
            "renspa": renspa_field,
            "marcas": marcas_field,
            "aptitud": aptitud_field
        }
        
        # ----- Botón de iniciar evaluación -----
        def on_start_evaluation(e):
            # Validar nombre
            if not nombre_field.value or not nombre_field.value.strip():
                nombre_field.error_text = "El nombre es obligatorio"
                nombre_field.update()
                snack = ft.SnackBar(
                    ft.Text("Por favor, ingrese el nombre del paciente"),
                    bgcolor=ft.Colors.RED_600
                )
                page.open(snack)
                return
            
            species_name = selected_species_ref["value"]
            is_grande = species_name in ("Equino", "Bovino", "Porcino")
            
            # Guardar datos del paciente
            session_state["especie"] = species_name
            session_state["paciente"] = {
                "nombre": nombre_field.value.strip(),
                "raza": raza_field.value.strip() if raza_field.value else "",
                "edad": edad_field.value.strip() if edad_field.value else "No especificada",
                "peso": peso_field.value.strip() if peso_field.value else "",
                "sexo": sexo_dropdown.value if sexo_dropdown.value else "",
                "estado_reproductivo": estado_repro_dropdown.value if estado_repro_dropdown.value else "",
                "propietario": propietario_field.value.strip() if propietario_field.value else "No especificado",
                "practicante": practicante_field.value.strip() if practicante_field.value else "No especificado",
                "establecimiento": establecimiento_field.value.strip() if is_grande and establecimiento_field.value else "",
                "renspa": renspa_field.value.strip() if is_grande and renspa_field.value else "",
                "marcas": marcas_field.value.strip() if is_grande and marcas_field.value else "",
                "aptitud": aptitud_field.value.strip() if is_grande and aptitud_field.value else "",
            }
            
            # Limpiar referencias temporales del form al iniciar
            page._form_fields = None
            
            # Cargar pantalla de exploración
            show_evaluation_screen()
        
        start_eval_btn = ft.ElevatedButton(
            "Iniciar Evaluación Clínica",
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            bgcolor=ft.Colors.TEAL_800,
            color=ft.Colors.WHITE,
            height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=on_start_evaluation
        )
        
        # ----- Función para construir el formulario según especie -----
        def build_dynamic_form(species_name, reset_values=True):
            is_grande = species_name in ("Equino", "Bovino", "Porcino")
            
            if reset_values:
                # Resetear campos
                nombre_field.value = ""
                nombre_field.error_text = None
                raza_field.value = ""
                edad_field.value = ""
                peso_field.value = ""
                sexo_dropdown.value = None
                estado_repro_dropdown.value = None
                estado_repro_dropdown.options = []
                estado_repro_dropdown.visible = False
                propietario_field.value = ""
                practicante_field.value = ""
                establecimiento_field.value = ""
                renspa_field.value = ""
                marcas_field.value = ""
                aptitud_field.value = ""
            
            nombre_field.label = "Nombre / ID del Paciente *" if is_grande else "Nombre del Paciente *"
            
            if is_grande:
                form_controls = [
                    nombre_field, establecimiento_field,
                    renspa_field, marcas_field,
                    aptitud_field, sexo_dropdown,
                    estado_repro_dropdown, edad_field,
                    practicante_field
                ]
            else:
                form_controls = [
                    nombre_field, raza_field,
                    edad_field, peso_field,
                    sexo_dropdown, estado_repro_dropdown,
                    propietario_field, practicante_field
                ]
            
            responsive_form = ft.ResponsiveRow(form_controls, spacing=15, run_spacing=15)
            
            form_card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(
                            f"Ficha de Ingreso — {species_name}",
                            size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_700
                        ),
                        ft.Container(height=5),
                        responsive_form,
                        ft.Container(height=10),
                        ft.Row([start_eval_btn], alignment=ft.MainAxisAlignment.CENTER),
                    ], spacing=10),
                    padding=ft.Padding.all(20)
                ),
                elevation=2,
            )
            
            form_container.content = form_card
            form_container.visible = True
            form_container.update()
        
        # ----- Callback de selección de especie -----
        def make_species_card_click(species_name):
            def on_click(e):
                selected_species_ref["value"] = species_name
                
                # Actualizar resaltado visual de tarjetas
                for sname, card_ctrl in species_card_refs.items():
                    if sname == species_name:
                        card_ctrl.border = ft.Border.all(3, ft.Colors.TEAL_700)
                        card_ctrl.shadow = ft.BoxShadow(
                            spread_radius=1,
                            blur_radius=8,
                            color=ft.Colors.with_opacity(0.25, ft.Colors.TEAL_400),
                            offset=ft.Offset(0, 2)
                        )
                    else:
                        card_ctrl.border = ft.Border.all(1.5, ft.Colors.TEAL_200)
                        card_ctrl.shadow = None
                    card_ctrl.update()
                
                # Mostrar formulario dinámico
                build_dynamic_form(species_name, reset_values=True)
                
            return on_click
            
        # Generador de Tarjetas estéticas
        def build_species_card(name, emoji, bg_color, hover_color):
            is_selected = (name == selected_species_ref["value"])
            card_content = ft.Container(
                content=ft.Column([
                    ft.Text(emoji, size=46),
                    ft.Text(name, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_900)
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                width=140,
                height=125,
                bgcolor=bg_color,
                border_radius=ft.BorderRadius.all(15),
                border=ft.Border.all(3, ft.Colors.TEAL_700) if is_selected else ft.Border.all(1.5, ft.Colors.TEAL_200),
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.25, ft.Colors.TEAL_400),
                    offset=ft.Offset(0, 2)
                ) if is_selected else None,
                on_click=make_species_card_click(name),
                alignment=ft.Alignment(0, 0),
                on_hover=lambda e, bg=bg_color, hbg=hover_color: setattr(e.control, "bgcolor", hbg if e.data == "true" else bg) or e.control.update()
            )
            species_card_refs[name] = card_content
            return card_content
            
        # Diccionario de emojis y colores pasteles para especies dinámicas
        species_emojis = {
            "Canino": "🐶",
            "Felino": "🐱",
            "Equino": "🐴",
            "Bovino": "🐄",
            "Porcino": "🐖"
        }
        
        species_colors = {
            "Canino": ("#E3F2FD", "#BBDEFB"),
            "Felino": ("#F3E5F5", "#E1BEE7"),
            "Equino": ("#E8F5E9", "#C8E6C9"),
            "Bovino": ("#FFF3E0", "#FFE0B2"),
            "Porcino": ("#FCE4EC", "#F8BBD0")
        }
        
        # Cargar especies dinámicamente desde el archivo JSON
        species_list = list(datos_clinicos.keys())
        species_cards = []
        for spec in species_list:
            emoji = species_emojis.get(spec, "🐾")
            bg, hbg = species_colors.get(spec, ("#F5F5F5", "#E0E0E0"))
            species_cards.append(build_species_card(spec, emoji, bg, hbg))
        
        # Montaje inicial
        patient_form = ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.LOCAL_HOSPITAL_ROUNDED, size=40, color=ft.Colors.TEAL_800),
                ft.Text("VET CLINIC ACADEMIC MVP", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800)
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=5),
            ft.Text(
                "Seleccione la especie del paciente para completar la ficha de ingreso.",
                size=13, color=ft.Colors.GREY_600, text_align=ft.TextAlign.CENTER
            ),
            ft.Container(height=10),
            
            # Selector de especies
            ft.Text("Seleccione la Especie del Paciente:", size=14, weight=ft.FontWeight.W_500, color=ft.Colors.TEAL_800, text_align=ft.TextAlign.CENTER),
            ft.Row(
                species_cards,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=15,
                wrap=True
            ),
            ft.Container(height=10),
            
            # Formulario dinámico
            form_container,
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, spacing=8, scroll=ft.ScrollMode.ALWAYS)
        
        # Contenedor centralizado para la pantalla inicial de 900px (max_width para responsive)
        main_container.content = ft.Container(
            content=ft.Container(
                content=patient_form,
                width=min(900, page.width - 30) if page.width else 900,
            ),
            alignment=ft.Alignment(0, 0),
            padding=ft.Padding.all(15)
        )
        
        # Si ya hay una especie seleccionada de la sesión cargada, mostrar el formulario sin resetear valores
        if session_state["especie"]:
            build_dynamic_form(session_state["especie"], reset_values=False)
            
        page.update()

    # ---------------------------------------------------------
    # PANTALLA 2: Espacio de Trabajo de Exploración Clínica (Tabs)
    # ---------------------------------------------------------
    def show_evaluation_screen():
        species = session_state["especie"]
        
        # Configurar el AppBar para la pantalla de evaluación
        page.appbar.title = ft.Text(f"Evaluación: {session_state['paciente']['nombre']} ({session_state['especie']})", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        page.appbar.leading = ft.IconButton(
            ft.Icons.ARROW_BACK,
            tooltip="Regresar a Paciente",
            on_click=lambda e: on_back_click(e),
            icon_color=ft.Colors.WHITE
        )
        page.update()
        
        # 1. Campos de Anamnesis
        motivo_field = ft.TextField(
            label="Motivo de Consulta",
            multiline=True,
            min_lines=3,
            max_lines=5,
            border_color=ft.Colors.TEAL_300,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["anamnesis"]["motivo"],
            on_change=lambda e: save_anamnesis_motivo(e.control.value)
        )
        
        anamnesis_field = ft.TextField(
            label="Anamnesis (Preguntas al tutor sobre historia previa)",
            multiline=True,
            min_lines=5,
            max_lines=8,
            border_color=ft.Colors.TEAL_300,
            focused_border_color=ft.Colors.TEAL_700,
            value=session_state["anamnesis"]["preguntas"],
            on_change=lambda e: save_anamnesis_preguntas(e.control.value)
        )
        
        def save_anamnesis_motivo(val):
            session_state["anamnesis"]["motivo"] = val
            
        def save_anamnesis_preguntas(val):
            session_state["anamnesis"]["preguntas"] = val
            
        # Pestaña 1: Contenido de Anamnesis
        anamnesis_content = ft.Container(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("Anamnesis Clínica", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800),
                    ft.Text("Complete la recopilación subjetiva previa del paciente mediante interrogatorio.", size=12, color=ft.Colors.GREY_600),
                    ft.Container(height=10),
                    motivo_field,
                    ft.Container(height=10),
                    anamnesis_field
                ], scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                width=900
            ),
            alignment=ft.Alignment(0, 0),
            padding=ft.Padding.all(15)
        )
        
        tab_headers = [
            ft.Tab(label="Anamnesis")
        ]
        tab_contents = [
            anamnesis_content
        ]
        
        # 2. Parámetros y Renderizado Condicional por Región
        def build_numeric_card(param_name, param_data):
            """Builds a styled card for numeric clinical parameters (e.g., heart rate, temperature)."""
            if param_name not in session_state["evaluaciones"]:
                session_state["evaluaciones"][param_name] = {"valor_numerico": ""}

            num_state = session_state["evaluaciones"][param_name]

            def on_numeric_change(e):
                num_state["valor_numerico"] = e.control.value

            numeric_field = ft.TextField(
                keyboard_type=ft.KeyboardType.NUMBER,
                label=f"{param_name} ({param_data.get('unidad', '')})",
                hint_text=f"Rango normal: {param_data.get('rango_referencia', '')} {param_data.get('unidad', '')}",
                border_color=ft.Colors.TEAL_400,
                focused_border_color=ft.Colors.TEAL_700,
                on_change=on_numeric_change,
                value=num_state["valor_numerico"],
                text_style=ft.TextStyle(weight=ft.FontWeight.W_500),
            )

            card = ft.Container(
                content=ft.Column([
                    ft.Text(param_name, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        f"Referencia: {param_data.get('rango_referencia', '')} {param_data.get('unidad', '')}",
                        size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True
                    ),
                    numeric_field,
                ], spacing=10),
                padding=ft.Padding.all(15),
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(12),
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                shadow=ft.BoxShadow(
                    spread_radius=0.5,
                    blur_radius=3,
                    color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                    offset=ft.Offset(0, 1)
                )
            )
            return card

        def build_parameter_card(region_name, param_name, param_data):
            if param_name not in session_state["evaluaciones"]:
                session_state["evaluaciones"][param_name] = {
                    "estado": "No Evaluado",
                    "detalles": [],
                    "custom": ""
                }
                
            param_state = session_state["evaluaciones"][param_name]
            
            # Lógica de estados y colores
            def update_card_styles(estado):
                if estado == "Normal":
                    btn_normal.bgcolor = ft.Colors.GREEN_700
                    btn_normal.color = ft.Colors.WHITE
                    btn_normal.elevation = 2
                    
                    btn_alterado.bgcolor = None
                    btn_alterado.color = ft.Colors.RED_700
                    btn_alterado.elevation = 0
                    
                    btn_no_eval.bgcolor = None
                    btn_no_eval.color = ft.Colors.GREY_600
                    btn_no_eval.elevation = 0
                    
                    # Mostrar panel de detalles con notas de Normal
                    details_panel.visible = True
                    details_panel.bgcolor = ft.Colors.SURFACE_CONTAINER
                    details_panel.border = ft.Border.all(1, ft.Colors.GREEN_400)
                    chip_title.visible = False
                    chip_row.visible = False
                    custom_comment_field.label = "Valor / Observación"
                    
                elif estado == "Alterado":
                    btn_normal.bgcolor = None
                    btn_normal.color = ft.Colors.GREEN_700
                    btn_normal.elevation = 0
                    
                    btn_alterado.bgcolor = ft.Colors.RED_700
                    btn_alterado.color = ft.Colors.WHITE
                    btn_alterado.elevation = 2
                    
                    btn_no_eval.bgcolor = None
                    btn_no_eval.color = ft.Colors.GREY_600
                    btn_no_eval.elevation = 0
                    
                    # Mostrar panel de detalles con alteración
                    details_panel.visible = True
                    details_panel.bgcolor = ft.Colors.SURFACE_CONTAINER
                    details_panel.border = ft.Border.all(1, ft.Colors.RED_400)
                    chip_title.visible = True
                    chip_row.visible = True
                    custom_comment_field.label = "Describa el hallazgo clínico específico"
                    
                else:  # No Evaluado
                    btn_normal.bgcolor = None
                    btn_normal.color = ft.Colors.GREEN_700
                    btn_normal.elevation = 0
                    
                    btn_alterado.bgcolor = None
                    btn_alterado.color = ft.Colors.RED_700
                    btn_alterado.elevation = 0
                    
                    btn_no_eval.bgcolor = ft.Colors.GREY_500
                    btn_no_eval.color = ft.Colors.WHITE
                    btn_no_eval.elevation = 2
                    
                    details_panel.visible = False
                    
            def click_normal(e):
                param_state["estado"] = "Normal"
                update_card_styles("Normal")
                
            def click_alterado(e):
                param_state["estado"] = "Alterado"
                update_card_styles("Alterado")
                
            def click_no_eval(e):
                param_state["estado"] = "No Evaluado"
                update_card_styles("No Evaluado")
                
            # Botones
            btn_no_eval = ft.ElevatedButton(
                "No Evaluado",
                on_click=click_no_eval,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            btn_normal = ft.ElevatedButton(
                "Normal",
                on_click=click_normal,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            btn_alterado = ft.ElevatedButton(
                "Alterado",
                on_click=click_alterado,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
            )
            
            # Chips de opciones
            chips = []
            def toggle_chip_event(chip_control, name):
                def on_select(e):
                    is_sel = e.control.selected
                    if is_sel:
                        if name not in param_state["detalles"]:
                            param_state["detalles"].append(name)
                        chip_control.label.color = ft.Colors.WHITE
                    else:
                        if name in param_state["detalles"]:
                            param_state["detalles"].remove(name)
                        chip_control.label.color = ft.Colors.ON_SURFACE
                    chip_control.update()
                return on_select
                
            for opt in param_data["Alterado"]:
                is_selected = opt in param_state["detalles"]
                chip = ft.Chip(
                    label=ft.Text(
                        opt, 
                        size=11, 
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.WHITE if is_selected else ft.Colors.ON_SURFACE
                    ),
                    selected=is_selected,
                    selected_color=ft.Colors.RED_900,
                    check_color=ft.Colors.WHITE,
                    show_checkmark=True
                )
                chip.on_select = toggle_chip_event(chip, opt)
                chips.append(chip)
                
            custom_comment_field = ft.TextField(
                label="Describa el hallazgo clínico específico",
                value=param_state["custom"],
                text_size=12,
                height=45,
                content_padding=ft.Padding.all(10),
                border_color=ft.Colors.GREY_400,
                focused_border_color=ft.Colors.TEAL_600,
                on_change=lambda e: save_custom_comment(e.control.value)
            )
            
            def save_custom_comment(val):
                param_state["custom"] = val
                
            chip_title = ft.Text("Opciones específicas de alteración:", size=11, color=ft.Colors.RED_300, weight=ft.FontWeight.BOLD)
            chip_row = ft.Row(wrap=True, controls=chips, spacing=5)
            
            details_panel = ft.Container(
                content=ft.Column([
                    chip_title,
                    chip_row,
                    custom_comment_field
                ], spacing=8),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                padding=ft.Padding.all(12),
                border_radius=ft.BorderRadius.all(10),
                border=ft.Border.all(1, ft.Colors.RED_400),
                visible=False
            )
            
            update_card_styles(param_state["estado"])
            
            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(param_name, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(f"Normal: {param_data['Normal']}", size=11, color=ft.Colors.ON_SURFACE_VARIANT, italic=True),
                    ft.Row([
                        btn_no_eval,
                        btn_normal,
                        btn_alterado,
                    ], spacing=10, wrap=True),
                    details_panel
                ], spacing=10),
                padding=ft.Padding.all(15),
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(12),
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                shadow=ft.BoxShadow(
                    spread_radius=0.5,
                    blur_radius=3,
                    color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                    offset=ft.Offset(0, 1)
                )
            )
            return card

        # Generador de contenido para las pestañas de regiones (Centrado y estirado a 900px)
        def build_region_tab_content(region_name):
            region_data = datos_clinicos[species][region_name]
            controls = []
            
            controls.append(
                ft.Text(f"Región: {region_name}", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_800)
            )
            controls.append(ft.Container(height=5))
            
            for param_name, param_data in region_data.items():
                if is_leaf_param(param_data):
                    condicion = param_data.get("condicion_visible", "Siempre")
                    if condicion != "Siempre" and isinstance(condicion, dict):
                        sexo_req = condicion.get("sexo")
                        repro_req = condicion.get("estado_reproductivo")
                        paciente = session_state["paciente"]
                        if sexo_req and paciente.get("sexo") != sexo_req:
                            continue
                        if repro_req and paciente.get("estado_reproductivo") != repro_req:
                            continue

                    if param_data.get("tipo_input") == "numerico":
                        card = build_numeric_card(param_name, param_data)
                        controls.append(card)
                    else:
                        card = build_parameter_card(region_name, param_name, param_data)
                        controls.append(card)
                else:
                    # Nested organ container (Organ → Method → param_data)
                    organ_name = param_name
                    organ_data = param_data

                    # Check organ-level visibility via first method's condicion_visible
                    first_method_data = next(iter(organ_data.values()), None)
                    if first_method_data and isinstance(first_method_data, dict):
                        organ_condicion = first_method_data.get("condicion_visible", "Siempre")
                        if organ_condicion != "Siempre" and isinstance(organ_condicion, dict):
                            sexo_req = organ_condicion.get("sexo")
                            repro_req = organ_condicion.get("estado_reproductivo")
                            paciente = session_state["paciente"]
                            if sexo_req and paciente.get("sexo") != sexo_req:
                                continue
                            if repro_req and paciente.get("estado_reproductivo") != repro_req:
                                continue

                    # Add organ sub-header
                    controls.append(ft.Container(
                        content=ft.Text(organ_name, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.TEAL_700),
                        padding=ft.Padding.only(top=15, bottom=5, left=5),
                    ))

                    for method_name, method_data in organ_data.items():
                        if not isinstance(method_data, dict):
                            continue
                        condicion = method_data.get("condicion_visible", "Siempre")
                        if condicion != "Siempre" and isinstance(condicion, dict):
                            sexo_req = condicion.get("sexo")
                            repro_req = condicion.get("estado_reproductivo")
                            paciente = session_state["paciente"]
                            if sexo_req and paciente.get("sexo") != sexo_req:
                                continue
                            if repro_req and paciente.get("estado_reproductivo") != repro_req:
                                continue

                        composite_key = f"{organ_name} > {method_name}"
                        card = build_parameter_card(region_name, composite_key, method_data)
                        controls.append(card)
                
            controls.append(ft.Container(height=5))
            
            # Campo de observaciones
            region_obs_field = ft.TextField(
                label=f"Observaciones adicionales de la región {region_name}",
                multiline=True,
                min_lines=3,
                max_lines=4,
                border_color=ft.Colors.TEAL_300,
                focused_border_color=ft.Colors.TEAL_700,
                value=session_state["observaciones"].get(region_name, ""),
                on_change=lambda e, r=region_name: save_region_obs(r, e.control.value)
            )
            controls.append(region_obs_field)
            
            return ft.Container(
                content=ft.Container(
                    content=ft.Column(controls, scroll=ft.ScrollMode.ALWAYS, expand=True, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                    width=min(900, page.width - 30) if page.width else 900
                ),
                alignment=ft.Alignment(0, 0),
                padding=ft.Padding.all(10)
            )
            
        def save_region_obs(region_name, val):
            session_state["observaciones"][region_name] = val

        # 3. Cargar dinámicamente todas las regiones del JSON como pestañas
        regions = list(datos_clinicos[species].keys())
        for region in regions:
            tab_name = "Examen General (EOG)" if region == "Examen Objetivo General (EOG)" else region
            tab_headers.append(ft.Tab(label=tab_name))
            tab_contents.append(build_region_tab_content(region))
            
        # Crear controlador de Tabs con alineación centrada
        tabs = ft.Tabs(
            length=len(tab_headers),
            content=ft.Column([
                ft.TabBar(tabs=tab_headers, tab_alignment=ft.TabAlignment.CENTER),
                ft.TabBarView(controls=tab_contents, expand=True)
            ], expand=True),
            expand=True
        )

        # Botón Volver
        def on_back_click(e):
            def back_confirmed(e):
                page.close(dialog_back)
                page._form_fields = None
                show_patient_data_screen(clear_state=True)
                
            def back_cancelled(e):
                page.close(dialog_back)

            dialog_back = ft.AlertDialog(
                title=ft.Text("Advertencia"),
                content=ft.Text("Si regresa a la pantalla de registro, se perderán las evaluaciones clínicas capturadas en esta sesión. ¿Desea continuar?"),
                actions=[
                    ft.TextButton("No, continuar evaluación", on_click=back_cancelled),
                    ft.ElevatedButton("Sí, descartar y salir", bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE, on_click=back_confirmed)
                ],
                actions_alignment=ft.MainAxisAlignment.END
            )
            page.open(dialog_back)
            
        # Botón Finalizar — Genera PDF en memoria y dispara descarga en el navegador
        def on_finish_click(e):
            session_state["datos_especie"] = datos_clinicos[species]
            
            patient_name_clean = session_state["paciente"]["nombre"].replace(" ", "_")
            if not patient_name_clean:
                patient_name_clean = "Paciente"
            especie_clean = session_state["especie"]
            fecha = datetime.datetime.now().strftime("%d-%m-%Y_%H%M")
            pdf_filename = f"Historia_Clinica_{patient_name_clean}_{especie_clean}_{fecha}.pdf"
            
            try:
                # 1. Crear un archivo en memoria (Buffer) en vez de en el disco
                pdf_buffer = io.BytesIO()
                
                # 2. Generar el PDF adentro del buffer
                generar_pdf(session_state, pdf_buffer)
                
                # 3. Obtener los bytes del PDF generado
                pdf_bytes = pdf_buffer.getvalue()
                
                import base64
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                if page.web:
                    force_web_download(pdf_filename, b64_pdf, "application/pdf")
                else:
                    download_file_web(page, pdf_bytes, pdf_filename, "application/pdf")
                
                snack = ft.SnackBar(
                    ft.Text(f"¡Reporte PDF generado con éxito! Iniciada la descarga de '{pdf_filename}'."),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=5000
                )
                page.open(snack)
                show_patient_data_screen()
            except Exception as ex:
                snack = ft.SnackBar(
                    ft.Text(f"Error al generar PDF: {str(ex)}"),
                    bgcolor=ft.Colors.RED_600
                )
                page.open(snack)

        # Barra de Finalización Persistente al Fondo
        bottom_bar = ft.Container(
            content=ft.Container(
                content=ft.Row([
                    ft.ElevatedButton(
                        "Finalizar Revisión",
                        icon=ft.Icons.PICTURE_AS_PDF,
                        bgcolor=ft.Colors.TEAL_800,
                        color=ft.Colors.WHITE,
                        on_click=on_finish_click,
                        height=45,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))
                    )
                ], alignment=ft.MainAxisAlignment.END),
                width=min(900, page.width - 30) if page.width else 900
            ),
            alignment=ft.Alignment(0, 0),
            padding=ft.Padding.only(left=20, right=20, bottom=15, top=5),
            border=ft.Border(top=ft.BorderSide(1, ft.Colors.GREY_300))
        )
        
        # Layout Completo con el menú de Tabs superior y Barra de Acciones persistente
        main_container.content = ft.Column([
            ft.Divider(height=1, color=ft.Colors.GREY_300),
            tabs,
            bottom_bar
        ], expand=True, spacing=10)

    # Inicializar la pantalla del formulario
    show_patient_data_screen()


# Ejecución de la aplicación
if __name__ == "__main__":
    ft.app(target=main)
