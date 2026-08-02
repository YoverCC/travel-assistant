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

            with open(file, "r", encoding="utf-8") as f:

                documents.append(
                    {
                        "province": file.stem.split("-")[0],
                        "content": f.read(),
                    }
                )

        return documents