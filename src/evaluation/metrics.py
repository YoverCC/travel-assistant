from collections import defaultdict


def _ids(results) -> list[str]:
    """Acepta search_fn que devuelva ids, dicts o filas con clave 'id'."""

    out = []

    for r in results:
        out.append(r if isinstance(r, str) else r["id"])

    return out


def evaluate(search_fn, ground_truth: list[dict], k: int = 5) -> dict:
    """
    Corre `search_fn(question, num_results=k)` sobre todo el ground truth.

    hit_rate = fraccion de preguntas cuyo chunk correcto aparece en el top-k.
    mrr      = media de 1/posicion del chunk correcto (0 si no aparece).

    El desglose por tipo es lo que mas informa: `entidad` y `coloquial` miden
    el motor lexico, `indirecta` mide el vectorial. Un promedio global esconde
    justo la asimetria que hay que corregir.
    """

    hits = 0
    rr = 0.0
    per_type = defaultdict(lambda: {"n": 0, "hits": 0, "rr": 0.0})
    failures = []

    for item in ground_truth:

        question = item["question"]
        expected = item["chunk_id"]
        qtype = item.get("type", "?")

        ranked = _ids(search_fn(question, num_results=k))

        bucket = per_type[qtype]
        bucket["n"] += 1

        if expected in ranked:
            position = ranked.index(expected) + 1
            hits += 1
            rr += 1 / position
            bucket["hits"] += 1
            bucket["rr"] += 1 / position
        else:
            failures.append({
                "question": question,
                "type": qtype,
                "expected": expected,
                "got": ranked[:3],
            })

    n = len(ground_truth) or 1

    breakdown = {
        qtype: {
            "n": b["n"],
            "hit_rate": b["hits"] / b["n"],
            "mrr": b["rr"] / b["n"],
        }
        for qtype, b in sorted(per_type.items())
    }

    return {
        "n": len(ground_truth),
        "k": k,
        "hit_rate": hits / n,
        "mrr": rr / n,
        "by_type": breakdown,
        "failures": failures,
    }


def report(name: str, result: dict) -> None:
    """Imprime una tabla legible de un resultado de `evaluate`."""

    print(f"\n{name}  (n={result['n']}, k={result['k']})")
    print(f"  hit_rate {result['hit_rate']:.3f}   mrr {result['mrr']:.3f}")
    print(f"  {'tipo':<12}{'n':>5}{'hit_rate':>11}{'mrr':>9}")

    for qtype, m in result["by_type"].items():
        print(f"  {qtype:<12}{m['n']:>5}{m['hit_rate']:>11.3f}{m['mrr']:>9.3f}")


def compare(results: dict[str, dict]) -> None:
    """Tabla comparativa de varios motores: compare({'lexico': r1, 'vector': r2})."""

    types = sorted({t for r in results.values() for t in r["by_type"]})

    print(f"\n{'motor':<14}{'hit_rate':>10}{'mrr':>8}   " +
          "".join(f"{t:>12}" for t in types))

    for name, r in results.items():
        cells = "".join(f"{r['by_type'].get(t, {}).get('hit_rate', 0):>12.3f}" for t in types)
        print(f"{name:<14}{r['hit_rate']:>10.3f}{r['mrr']:>8.3f}   {cells}")