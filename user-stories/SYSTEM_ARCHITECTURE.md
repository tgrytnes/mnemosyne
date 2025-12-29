- ### What Could Be More Advanced 🤔

  1. **Chunking Strategy**
     - **Current**: Fixed 400 chars with 100 overlap using LangChain's RecursiveCharacterTextSplitter
     - **State-of-art**:
       - Semantic chunking (chunk by topic/meaning, not character count)
       - Agentic chunking (LLM decides chunk boundaries)
       - Late chunking (embed full context, chunk afterward)
     - **Assessment**: Our approach is pragmatic and works well, but semantic chunking would preserve meaning better
  2. **Metadata Extraction**
     - **Current**: Basic metadata (file path, chunk index, timestamps)
     - **State-of-art**:
       - LLM-extracted keywords, entities, topics
       - Hierarchical document structure preservation
       - Cross-reference resolution (wiki-links → actual connections)
     - **Assessment**: We clean away structure; advanced systems preserve and enhance it
  3. **Quality Assurance**
     - **Current**: Basic tests, no embedding quality validation
     - **State-of-art**:
       - Embedding quality metrics (cosine similarity distributions)
       - Retrieval evaluation (recall@k, NDCG)
       - A/B testing different chunking strategies
     - **Assessment**: We trust the pipeline works, but don't measure quality
