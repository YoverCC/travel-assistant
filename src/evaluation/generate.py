import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel


PROMPT_PATH = Path("prompts/generacion-preguntas-es.md")
RAW_DIR = Path("data/eval/raw")

# Cambialo por el modelo que quieras usar.
MODEL = "gpt-5.4-mini"


TIPOS = ("directa", "indirecta", "coloquial", "entidad")


class ChunkPreguntas(BaseModel):
    """
    Un campo por tipo en vez de una lista de preguntas.

    Con una lista, el modelo mezcla lotes: en las pruebas metio las 4 preguntas
    del chunk A y las 4 del chunk B dentro del objeto de A, dejando preguntas
    atribuidas al id equivocado. Campos fijos hacen que eso sea imposible de
    representar, en lugar de algo que hay que detectar despues.
    """

    id: str
    apto: bool
    motivo: str  # cadena vacia cuando apto=True
    directa: str
    indirecta: str
    coloquial: str
    entidad: str


class Lote(BaseModel):
    resultados: list[ChunkPreguntas]


def _to_validator_shape(resultado: ChunkPreguntas) -> dict:
    """Pasa del esquema de campos fijos al formato que espera `validate()`."""

    return {
        "id": resultado.id,
        "apto": resultado.apto,
        "motivo": resultado.motivo,
        "preguntas": [
            {"tipo": tipo, "pregunta": getattr(resultado, tipo)}
            for tipo in TIPOS
            if getattr(resultado, tipo).strip()
        ],
    }


def generate_batch(
    batch: str,
    index: int,
    model: str = MODEL,
    prompt_path: Path = PROMPT_PATH,
    client: OpenAI | None = None,
    force: bool = False,
) -> list[dict]:
    """
    Genera un solo lote y lo cachea en disco.

    Cacheamos por lote para que un fallo a mitad de camino (rate limit, corte de
    red) no obligue a volver a pagar los lotes que ya salieron bien: al reejecutar,
    los que ya existen se leen del disco. Pasa `force=True` para regenerar uno que
    no te haya convencido.
    """

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    cached = RAW_DIR / f"lote-{index:02d}.json"

    if cached.exists() and not force:
        return json.loads(cached.read_text(encoding="utf-8"))

    client = client or OpenAI()

    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": prompt_path.read_text(encoding="utf-8")},
            {"role": "user", "content": batch},
        ],
        response_format=Lote,
    )

    resultados = [
        _to_validator_shape(r) for r in completion.choices[0].message.parsed.resultados
    ]

    cached.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return resultados


def load_cached() -> list[dict]:
    """Junta todos los lotes ya generados que hay en disco, en orden."""

    generated = []

    for path in sorted(RAW_DIR.glob("lote-*.json")):
        generated.extend(json.loads(path.read_text(encoding="utf-8")))

    return generated


def preview(resultados: list[dict]) -> None:
    """Imprime un lote de forma legible para revisarlo a ojo."""

    for r in resultados:
        estado = "apto" if r["apto"] else f"NO APTO ({r['motivo']})"
        print(f"\n[{r['id']}]  {estado}")

        for p in r["preguntas"]:
            print(f"   {p['tipo']:<10} {p['pregunta']}")


def generate_questions(
    batches: list[str],
    model: str = MODEL,
    max_workers: int = 4,
    prompt_path: Path = PROMPT_PATH,
) -> list[dict]:
    """
    Corre los lotes contra OpenAI y devuelve la lista cruda de resultados.

    La salida alimenta directamente a `src.evaluation.validate.validate()`, que es
    quien decide que preguntas entran al ground truth -- el modelo se salta la
    regla anti-copia cada tanto, asi que la verificacion va en codigo aparte.
    """

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    client = OpenAI()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = pool.map(
            lambda args: generate_batch(
                args[1], args[0], model=model, prompt_path=prompt_path, client=client
            ),
            enumerate(batches, start=1),
        )

    generated = []

    for batch_results in results:
        generated.extend(batch_results)

    return generated


if __name__ == "__main__":
    from dotenv import load_dotenv

    from src.evaluation.sampler import sample_chunks, to_prompt_batches
    from src.ingestion.chunker import MarkdownChunker
    from src.ingestion.parser import MarkdownParser

    load_dotenv()

    documents = MarkdownParser("data/markdown").load_documents()
    chunker = MarkdownChunker()

    chunks = []

    for document in documents:
        chunks.extend(
            chunker.split(
                document["doc_id"],
                document["province"],
                document["lang"],
                document["year"],
                document["is_province"],
                document["content"],
            )
        )

    batches = to_prompt_batches(sample_chunks(chunks, per_province=6), batch_size=15)
    generated = generate_questions(batches)

    out = Path("data/eval/generated.json")
    out.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(generated)} fragmentos procesados -> {out}")