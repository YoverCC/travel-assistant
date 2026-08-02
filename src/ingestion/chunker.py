from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

class MarkdownChunker:

    def __init__(self):

        self.header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "province"),
                ("##", "section"),
                ("###", "title"),
            ]
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )

    def split(self, province: str, markdown: str):

        header_docs = self.header_splitter.split_text(markdown)

        chunks = []
        
        i = 0
        for doc in header_docs:
            
            if len(doc.page_content) <= 1500:
                chunks.append(
                    {
                        "id": f"{province}_{i:04d}",
                        "province": province,
                        "section": doc.metadata.get("section"),
                        "title": doc.metadata.get("title"),
                        "content": doc.page_content,
                    }
                )
                
                i = i + 1
                continue
            
            # If the content is too long, split it into smaller chunks
            small_chunks = self.text_splitter.split_text(
                doc.page_content
            )
            
            for chunk in small_chunks:
                
                chunks.append(
                    {
                        "id": f"{province}_{i:04d}",
                        "province": province,
                        "section": doc.metadata.get("section"),
                        "title": doc.metadata.get("title"),
                        "content": chunk,
                    }
                )
                i = i + 1
                
        return chunks