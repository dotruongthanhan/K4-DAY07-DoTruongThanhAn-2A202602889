from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        if self.store.get_collection_size() == 0:
            return "Knowledge base is empty. No documents available to answer the question."

        chunks = self.store.search(question, top_k=top_k)
        if not chunks:
            return "No relevant context found to answer the question."

        context_parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source = (
                chunk.get("metadata", {}).get("source")
                or chunk.get("metadata", {}).get("doc_id")
                or chunk.get("id")
                or f"doc_{i}"
            )
            context_parts.append(f"[{i}] (Source: {source})\n{chunk.get('content', '')}")

        context_str = "\n\n".join(context_parts)

        prompt = (
            "You are a helpful knowledge base assistant about return, exchange, and warranty policies, or regulations governing sellers and buyers on e-commerce platforms.\n"
            "Answer the question based ONLY on the provided context below.\n"
            "If the answer cannot be found in the context, state clearly that the information is not available.\n"
            "Cite the source references (e.g. [1], [2]) when using facts from the context.\n\n"
            f"Context:\n{context_str}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

        return self.llm_fn(prompt)
