from fastembed import TextEmbedding

embedding_model = TextEmbedding(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    cache_dir="../models"
)