============================================================
NOMISALUD — PROMPT DE EXTRACCIÓN DE INCAPACIDADES
Versión 2.0 | Alineado con schema JSONB final
============================================================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM PROMPT (rol del sistema)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Eres el motor de extracción y clasificación documental en Google Gemini 2.5 Flash:
analizas documentos médicos colombianos de incapacidad y devuelves solo datos
estructurados según el esquema indicado en el mensaje de usuario.
Tu única función es analizar el documento recibido y retornar un objeto JSON estructurado.
No expliques, no agregues texto fuera del JSON.
Retorna ÚNICAMENTE el objeto JSON, sin bloques de código markdown, sin comentarios.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USER PROMPT (mensaje del usuario)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analiza este documento de incapacidad médica colombiana.

El documento puede ser cualquiera de estos formatos:
- Certificado de incapacidad de EPS (Sura, Sanitas, Salud Total, Nueva EPS, SOS, Asmet, etc.)
- Certificado de incapacidad de ARL
- Certificado de médico particular o IPS privada
- Epicrisis o resumen de hospitalización con días de incapacidad
- FURIPS (formato único de reporte de incapacidades)
- Licencia de maternidad o paternidad
- Prórroga de incapacidad
- Documento escaneado, fotografiado o en PDF digital

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTEXTO ADICIONAL — TEXTO OCR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

El siguiente bloque proviene de OCR del mismo documento adjunto. Úsalo solo como
referencia complementaria si la imagen o el PDF no son legibles. No inventes datos
que no aparezcan en el documento ni en este texto.

{{OCR_TEXTO}}

Extrae los datos y retorna ÚNICAMENTE este JSON.
Si un campo no está visible, no es legible o no existe en el documento, usa null.
NUNCA inventes, supongas ni completes datos que no estén explícitamente en el documento.

Campos mínimos de negocio (equivalentes en este JSON anidado; todos deben aparecer en la
salida usando null si no aplican):
- nombre → paciente.nombre_completo
- identificacion → paciente.numero_documento (y tipo_documento cuando exista)
- dias → incapacidad.total_dias
- fecha_inicio → incapacidad.fecha_inicio
- fecha_fin → incapacidad.fecha_fin
- tipo → incapacidad.tipo (clasificación: enfermedad general, ARL, tránsito, maternidad, etc.)
- entidad → entidad (nombre / tipo / nit según corresponda)

{
  "paciente": {
    "nombre_completo": "STRING | null — nombre y apellidos completos como aparecen",
    "tipo_documento": "CC | CE | TI | PA | RC | null",
    "numero_documento": "STRING | null — solo dígitos, sin puntos ni comas",
    "fecha_nacimiento": "YYYY-MM-DD | null",
    "genero": "M | F | null",
    "ciudad_residencia": "STRING | null"
  },
  "incapacidad": {
    "tipo": "enfermedad_general | accidente_trabajo | accidente_transito | enfermedad_laboral | maternidad | paternidad | null",
    "es_prorroga": true | false,
    "numero_prorroga": "INTEGER | null — 1 si es primera prórroga, 2 si es segunda, etc. null si no es prórroga",
    "fecha_inicio": "YYYY-MM-DD | null",
    "fecha_fin": "YYYY-MM-DD | null",
    "total_dias": "INTEGER | null — días indicados explícitamente en el documento",
    "dias_acumulados": "INTEGER | null — suma total indicada si incluye prórrogas anteriores"
  },
  "diagnostico": {
    "codigo_cie10": "STRING | null — código CIE-10 si aparece, ej: J06.9, M54.5, Z34",
    "descripcion": "STRING | null — descripción del diagnóstico principal",
    "descripcion_adicional": "STRING | null — diagnóstico secundario si existe"
  },
  "entidad": {
    "nombre": "STRING | null — nombre de la EPS, ARL, IPS o médico que expide",
    "tipo": "EPS | ARL | IPS | medico_particular | hospital_publico | null",
    "nit": "STRING | null",
    "ciudad": "STRING | null"
  },
  "medico": {
    "nombre": "STRING | null",
    "registro": "STRING | null — número de registro médico o RETHUS",
    "especialidad": "STRING | null"
  },
  "documento": {
    "radicado": "STRING | null — número de radicado o consecutivo del documento",
    "fecha_expedicion": "YYYY-MM-DD | null",
    "tiene_sello": true | false,
    "tiene_firma": true | false
  },
  "validaciones": {
    "genero_tipo_ok": true | false | null,
    "fechas_ok": true | false | null,
    "dias_ok": true | false | null,
    "observaciones": []
  },
  "inconsistencias": [
    {
      "tipo": "fechas | dias | genero_tipo | identificacion | legibilidad | dato_faltante",
      "descripcion": "STRING — detalle concreto del hallazgo detectado"
    }
  ]
}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS DE VALIDACIÓN (parte del user prompt)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Aplica estas reglas al completar el campo "validaciones":

REGLA 1 — genero_tipo_ok:
  - false si tipo = "maternidad" Y genero = "M"
  - false si tipo = "paternidad" Y genero = "F"
  - true en todos los demás casos donde ambos datos existen
  - null si genero o tipo son null

REGLA 2 — fechas_ok:
  - false si fecha_fin <= fecha_inicio
  - false si alguna fecha es posterior a la fecha de hoy sin que el documento sea una licencia de maternidad futura (lo cual es válido)
  - false si fecha_expedicion es posterior a fecha_inicio
  - true si todas las fechas son lógicamente consistentes
  - null si alguna de las fechas requeridas es null

REGLA 3 — dias_ok:
  - Calcula: (fecha_fin - fecha_inicio) + 1
  - false si ese resultado NO coincide con total_dias
  - true si coincide exactamente
  - null si fecha_inicio, fecha_fin o total_dias son null

REGLA 4 — observaciones:
  - Lista de strings describiendo cada problema encontrado
  - Incluye UNA entrada por cada validación en false
  - Incluye advertencias de legibilidad si el documento es de baja calidad
  - Incluye si el documento parece ser una prórroga pero no tiene indicado el número
  - Array vacío [] si no hay observaciones
  - Ejemplos de mensajes:
    "Licencia de maternidad asignada a paciente de género masculino"
    "fecha_fin (2024-01-10) es anterior a fecha_inicio (2024-01-15)"
    "Total de días declarado (10) no coincide con el calculado (11)"
    "Documento de baja calidad — algunos campos pueden ser imprecisos"
    "Parece prórroga pero numero_prorroga no está indicado"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INCONSISTENCIAS ESTRUCTURADAS (obligatorio)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Además de "validaciones", debes evaluar el documento y llenar SIEMPRE el array
"inconsistencias". Cada elemento es un objeto con "tipo" y "descripcion".

Evalúa obligatoriamente estas categorías (mínimo tres tipos distintos cuando aplique):

1. tipo = "fechas" — fechas incoherentes, futuras sin justificación, expedición posterior al inicio, fin <= inicio.
2. tipo = "dias" — total_dias no coincide con (fecha_fin - fecha_inicio) + 1, o días declarados contradictorios.
3. tipo = "genero_tipo" — incompatibilidad entre incapacidad.tipo y paciente.genero (maternidad/paternidad).
4. tipo = "identificacion" — documento inválido, longitud atípica, caracteres no numéricos, tipo vs número incoherente.
5. tipo = "legibilidad" — documento escaneado ilegible, campos críticos no legibles, baja calidad que impide certeza.
6. tipo = "dato_faltante" — campo crítico de negocio ausente cuando debería estar visible (nombre, identificación, fechas, días, entidad).

Reglas del array "inconsistencias":
- Incluye UNA entrada por cada anomalía real detectada (puede haber varias del mismo tipo si son hechos distintos).
- Usa solo los valores de "tipo" listados arriba (en minúsculas, sin espacios).
- "descripcion" debe ser específica y citar valores o campos involucrados.
- Si no hay ninguna anomalía tras revisar las seis categorías, devuelve "inconsistencias": [].
- No dupliques en "inconsistencias" lo que ya quedó solo como observación en "validaciones"; prioriza el reporte estructurado aquí cuando sea una anomalía de negocio.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASOS ESPECIALES COLOMBIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Licencia de maternidad: 18 semanas (126 días) es lo normal por ley. No marques dias_ok=false si el documento indica ese valor aunque te parezca alto.
- Licencia de paternidad: 2 semanas (14 días hábiles). También es válido.
- Prórroga: el campo fecha_inicio puede ser el día siguiente al fin de la incapacidad anterior. Es correcto.
- Accidente de tránsito: puede ser expedido por médico de urgencias, no necesariamente por la EPS. entidad.tipo = "IPS" o "hospital_publico" es válido.
- FURIPS: formulario estándar del Ministerio de Trabajo para accidentes laborales. tipo = "accidente_trabajo" o "enfermedad_laboral".
- Si el documento es una epicrisis: extrae lo que puedas. Es válido que muchos campos queden null.
- Documentos del SOAT o pólizas: tipo = "accidente_transito", entidad.tipo = "ARL" o la aseguradora.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IMPLEMENTACIÓN EN CÓDIGO (Python)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import json
import base64
from datetime import date

SYSTEM_PROMPT = """
Eres un extractor especializado en documentos médicos colombianos de incapacidad.
Tu única función es analizar el documento recibido y retornar un objeto JSON estructurado.
No expliques, no agregues texto fuera del JSON.
Retorna ÚNICAMENTE el objeto JSON, sin bloques de código markdown, sin comentarios.
"""

USER_PROMPT = """
[PEGAR AQUÍ EL USER PROMPT COMPLETO DE ARRIBA, incluyendo el JSON template y las reglas]
"""

# ── Gemini 2.5 Flash (principal) ──────────────────────────
def extract_gemini(file_path: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key="GEMINI_API_KEY")
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
    ext = file_path.split(".")[-1].lower()
    mime = "application/pdf" if ext == "pdf" else f"image/{ext}"
    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    response = model.generate_content([
        {"mime_type": mime, "data": data},
        USER_PROMPT
    ])
    return _parse_json(response.text)


# ── Claude Haiku (fallback) ───────────────────────────────
def extract_claude(file_path: str, ocr_text: str = None) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key="CLAUDE_API_KEY")
    ext = file_path.split(".")[-1].lower()
    mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    prompt = USER_PROMPT
    if ocr_text:
        prompt += f"\n\nTexto extraído por OCR como contexto adicional:\n{ocr_text}"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    return _parse_json(response.content[0].text)


# ── Parser robusto ────────────────────────────────────────
def _parse_json(text: str) -> dict:
    text = text.strip()
    # Quitar bloques markdown si la IA los metió igual
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    # Buscar el JSON aunque haya texto alrededor
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("La IA no retornó un JSON válido")
    return json.loads(text[start:end])


# ── Servicio principal con fallback y métricas ────────────
async def extract_incapacidad(
    file_path: str,
    incapacidad_id: str,
    ocr_text: str = None
) -> dict:
    import time
    start = time.time()
    api_usada = "gemini-2.5-flash"

    try:
        result = extract_gemini(file_path)
    except Exception as e:
        print(f"[Nomisalud] Gemini falló ({e}), usando Claude Haiku")
        api_usada = "claude-haiku-4-5-20251001"
        result = extract_claude(file_path, ocr_text)

    tiempo_ms = int((time.time() - start) * 1000)
    nulos = sum(1 for v in _flatten(result).values() if v is None)

    # Estructura lista para guardar en extraccion_ia
    return {
        "incapacidad_id": incapacidad_id,
        "datos_extraidos": {               # → columna JSONB datos_extraidos
            "paciente":    result.get("paciente", {}),
            "incapacidad": result.get("incapacidad", {}),
            "diagnostico": result.get("diagnostico", {}),
            "entidad":     result.get("entidad", {}),
            "medico":      result.get("medico", {}),
            "documento":   result.get("documento", {}),
        },
        "validaciones":    result.get("validaciones", {}),   # → JSONB validaciones
        "campos_corregidos": None,                           # → JSONB, se llena cuando RRHH edita
        "api_usada":       api_usada,                        # → VARCHAR
        "modelo":          api_usada,                        # → VARCHAR
        "calidad_doc":     _calidad(nulos),                  # → ENUM
        "tiempo_ms":       tiempo_ms,                        # referencia, no se guarda en DB
    }

def _flatten(d, parent=""):
    items = {}
    for k, v in d.items():
        if isinstance(v, dict):
            items.update(_flatten(v, k))
        else:
            items[f"{parent}.{k}" if parent else k] = v
    return items

def _calidad(nulos: int) -> str:
    if nulos <= 3:  return "buena"
    if nulos <= 8:  return "regular"
    return "mala"


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESPUESTA DE EJEMPLO (documento real)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "paciente": {
    "nombre_completo": "CARLOS ANDRES MARTINEZ LOPEZ",
    "tipo_documento": "CC",
    "numero_documento": "1098765432",
    "fecha_nacimiento": "1985-03-22",
    "genero": "M",
    "ciudad_residencia": "Bucaramanga"
  },
  "incapacidad": {
    "tipo": "enfermedad_general",
    "es_prorroga": false,
    "numero_prorroga": null,
    "fecha_inicio": "2026-05-01",
    "fecha_fin": "2026-05-07",
    "total_dias": 7,
    "dias_acumulados": null
  },
  "diagnostico": {
    "codigo_cie10": "J06.9",
    "descripcion": "Infeccion aguda de las vias respiratorias superiores, no especificada",
    "descripcion_adicional": null
  },
  "entidad": {
    "nombre": "EPS Sanitas",
    "tipo": "EPS",
    "nit": "800251440",
    "ciudad": "Bucaramanga"
  },
  "medico": {
    "nombre": "DRA. PATRICIA GOMEZ REYES",
    "registro": "145623",
    "especialidad": "Medicina General"
  },
  "documento": {
    "radicado": "20260501-0394",
    "fecha_expedicion": "2026-05-01",
    "tiene_sello": true,
    "tiene_firma": true
  },
  "validaciones": {
    "genero_tipo_ok": true,
    "fechas_ok": true,
    "dias_ok": true,
    "observaciones": []
  }
}