import re
import unicodedata


EXPECTED_TYPES = {"directa", "indirecta", "coloquial", "entidad"}

# Palabras funcionales: no aportan senal, no cuentan como copia por si solas.
FUNCTION_WORDS = {
    "de", "la", "el", "los", "las", "del", "y", "a", "en", "con", "por",
    "para", "un", "una", "al", "que", "su", "sus", "o", "e",
}

META_PHRASES = [
    "segun el texto",
    "en el fragmento",
    "el documento",
    "de acuerdo al texto",
    "que se menciona",
    "el texto dice",
]


def normalize(text: str) -> list[str]:
    """Minusculas, sin tildes, sin puntuacion -> lista de tokens."""

    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))

    return re.findall(r"\w+", text)


def ngrams(tokens: list[str], n: int) -> set[tuple]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def proper_nouns(text: str) -> set[str]:
    """Tokens que aparecen capitalizados en el texto fuente, normalizados."""

    found = set()

    for word in re.findall(r"\b[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ]*", text):
        found.update(normalize(word))

    return found


def is_leak(shared: set[tuple], proper: set[str]) -> bool:
    """
    Decide si un n-grama compartido es copia real o solo un nombre propio.

    "Virgen de la Asunción" o "templo de Santo Domingo" comparten 4 palabras con
    el fragmento, pero un usuario real escribe justamente eso: el prompt permite
    conservar nombres propios. Solo cuenta como fuga si el n-grama trae al menos
    una palabra de contenido que no sea nombre propio ni palabra funcional.
    """

    for gram in shared:

        if not all(token in proper or token in FUNCTION_WORDS for token in gram):
            return True

    return False


def validate(
    generated: list[dict],
    chunks: list[dict],
    leak_n: int = 4,
) -> tuple[list[dict], list[dict]]:
    """
    Filtra las preguntas generadas y separa las sospechosas.

    El chequeo que importa es el de fuga (`leak`): si la pregunta comparte una
    secuencia de `leak_n` palabras con su chunk, la busqueda lexica la acierta
    por copia literal y la metrica queda inflada. El modelo generador cumple la
    regla la mayor parte del tiempo, pero no siempre -- por eso se verifica en
    codigo y no se confia en el prompt.

    Devuelve (ground_truth, rechazadas).
    """

    by_id = {c["id"]: c for c in chunks}

    ground_truth = []
    rejected = []

    for item in generated:

        chunk_id = item.get("id")
        chunk = by_id.get(chunk_id)

        if chunk is None:
            rejected.append({"id": chunk_id, "motivo": "id desconocido"})
            continue

        if not item.get("apto", True):
            rejected.append({"id": chunk_id, "motivo": "marcado no apto por el generador"})
            continue

        chunk_ngrams = ngrams(normalize(chunk["content"]), leak_n)
        chunk_proper = proper_nouns(chunk["content"])
        seen_types = set()

        for entry in item.get("preguntas", []):

            question = entry.get("pregunta", "").strip()
            qtype = entry.get("tipo")

            if not question:
                continue

            tokens = normalize(question)
            shared = ngrams(tokens, leak_n) & chunk_ngrams

            # El tipo `entidad` es por diseno el nombre propio mas una o dos
            # palabras: exigirle que no coincida con el fragmento lo haria
            # imposible de generar, y es justo el tipo que mide busqueda lexica.
            if qtype != "entidad" and is_leak(shared, chunk_proper):
                rejected.append({
                    "id": chunk_id,
                    "pregunta": question,
                    "motivo": f"fuga literal: {' '.join(next(iter(shared)))}",
                })
                continue

            if any(phrase in " ".join(tokens) for phrase in META_PHRASES):
                rejected.append({
                    "id": chunk_id,
                    "pregunta": question,
                    "motivo": "meta-referencia al documento",
                })
                continue

            if qtype not in EXPECTED_TYPES:
                rejected.append({
                    "id": chunk_id,
                    "pregunta": question,
                    "motivo": f"tipo invalido: {qtype!r}",
                })
                continue

            # Un tipo repetido significa que el generador acumulo en este chunk
            # preguntas que pertenecen a otro: el id no corresponde y el ground
            # truth quedaria mal etiquetado.
            if qtype in seen_types:
                rejected.append({
                    "id": chunk_id,
                    "pregunta": question,
                    "motivo": f"tipo duplicado ({qtype}): probable mezcla de fragmentos",
                })
                continue

            seen_types.add(qtype)

            ground_truth.append({
                "question": question,
                "type": qtype,
                "chunk_id": chunk_id,
                "province": chunk["province"],
            })

        missing = EXPECTED_TYPES - seen_types

        if missing:
            rejected.append({
                "id": chunk_id,
                "motivo": f"tipos faltantes: {sorted(missing)}",
            })

    return ground_truth, rejected