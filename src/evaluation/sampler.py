import random


MIN_CONTENT_CHARS = 200


def sample_chunks(
    chunks: list[dict],
    per_province: int = 6,
    min_chars: int = MIN_CONTENT_CHARS,
    seed: int = 42,
) -> list[dict]:
    """
    Muestreo estratificado por provincia.

    Estratificamos para que ninguna provincia domine el ground truth: sin esto,
    Cusco y Lima (que tienen mas chunks) definirian la metrica por si solos.

    Descartamos los chunks cortos porque no sostienen una pregunta distintiva
    -- 54 de los 781 tienen menos de 200 caracteres y suelen ser encabezados
    sueltos o pares "Lima-Arequipa: 1 h 15 min".
    """

    rng = random.Random(seed)

    by_province: dict[str, list[dict]] = {}

    for chunk in chunks:

        if len(chunk["content"]) < min_chars:
            continue

        by_province.setdefault(chunk["province"], []).append(chunk)

    sample = []

    for province in sorted(by_province):

        candidates = by_province[province]
        k = min(per_province, len(candidates))
        sample.extend(rng.sample(candidates, k))

    return sample


def to_prompt_batches(chunks: list[dict], batch_size: int = 15) -> list[str]:
    """
    Formatea los chunks tal como los espera prompts/generacion-preguntas-es.md.

    Devuelve una lista de strings; pega cada uno como un mensaje separado en el
    modelo generador.
    """

    batches = []

    for i in range(0, len(chunks), batch_size):

        blocks = []

        for chunk in chunks[i : i + batch_size]:

            header = (
                f"provincia: {chunk['province']}"
                f" | sección: {chunk['section'] or ''}"
                f" | título: {chunk['title'] or ''}"
            )

            blocks.append(
                f"### id: {chunk['id']}\n{header}\n---\n{chunk['content']}"
            )

        batches.append("\n\n".join(blocks))

    return batches
