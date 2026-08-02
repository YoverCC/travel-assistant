from fastembed import TextEmbedding

embedding_model = TextEmbedding(
    "jinaai/jina-embeddings-v2-base-es", 
    cache_dir="../models"
    )
