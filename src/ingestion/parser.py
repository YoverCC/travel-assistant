from pathlib import Path


class MarkdownParser:

    def __init__(self, knowledge_base: str):
        self.knowledge_base = Path(knowledge_base)

    def load_documents(self) -> list[dict]:
        """
        Returns:
            [
                {
                    "province": "amazonas",
                    "content": "...markdown..."
                },
                ...
            ]
        """

        documents = []

        for file in sorted(self.knowledge_base.glob("*.md")):
            slug, lang, year = file.stem.rsplit("-", 2)
            documents.append({
                "doc_id": file.stem,          # amazonas-es-2023
                "province": slug,
                "lang": lang,
                "year": int(year),
                "is_province": slug not in {"gastronomia", "lima_rutas_cortas"},
                "content": file.read_text(encoding="utf-8"),
            })

        return documents