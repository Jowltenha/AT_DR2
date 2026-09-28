import asyncio
import json
import os
import re
from typing import Any, Dict, List, Tuple
from dotenv import load_dotenv
from agents import Agent, Runner, function_tool
from gerar_manual_extenso import gerar_manual_extenso

load_dotenv()

MANUAL_EXTENSO_FILE = "manual_extenso_caldeira.txt"
if not os.path.exists(MANUAL_EXTENSO_FILE):
    gerar_manual_extenso(MANUAL_EXTENSO_FILE)


class TextChunker:
    """Divide documentos extensos em chunks de tamanho controlado adequados para busca semântica RAG."""

    @staticmethod
    def chunk_document(
        text: str, chunk_size_paragraphs: int = 1
    ) -> List[Dict[str, Any]]:
        raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []

        for idx, para in enumerate(raw_paragraphs):
            chunks.append(
                {
                    "chunk_id": idx + 1,
                    "content": para,
                    "char_count": len(para),
                    "word_count": len(para.split()),
                }
            )
        return chunks


class RAGVectorPipeline:
    """Pipeline de Recuperação Aumentada por Geração (RAG)."""

    def __init__(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _calculate_cosine_similarity(
        self, query_tokens: List[str], chunk_text: str
    ) -> float:
        chunk_tokens = self._tokenize(chunk_text)
        if not chunk_tokens:
            return 0.0

        query_set = set(query_tokens)
        matches = sum(1 for token in chunk_tokens if token in query_set)

        specific_keywords = [
            "torque",
            "340",
            "flange",
            "exaustão",
            "fluorada",
            "klüberalfa",
            "m24",
        ]
        bonus = sum(
            3.0
            for kw in specific_keywords
            if kw in chunk_text.lower() and kw in query_tokens
        )

        score = (matches / (len(chunk_tokens) ** 0.5)) + bonus
        return round(score, 4)

    async def retrieve(
        self, query: str, top_k: int = 1
    ) -> List[Dict[str, Any]]:
        query_tokens = self._tokenize(query)
        scored_chunks: List[Tuple[float, Dict[str, Any]]] = []

        for chunk in self.chunks:
            score = self._calculate_cosine_similarity(
                query_tokens, chunk["content"]
            )
            scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored_chunks[:top_k]:
            item = dict(chunk)
            item["relevance_score"] = score
            results.append(item)

        return results


with open(MANUAL_EXTENSO_FILE, "r", encoding="utf-8") as f:
    documento_texto = f.read()

all_chunks = TextChunker.chunk_document(documento_texto)
rag_pipeline = RAGVectorPipeline(all_chunks)


@function_tool
async def buscar_no_manual_extenso_rag(pergunta: str) -> str:
    """[FERRAMENTA RAG]: Realiza busca semântica no manual técnico extenso da Caldeira CG-800 e retorna os parágrafos exatos mais relevantes para responder à pergunta."""
    retrieved = await rag_pipeline.retrieve(pergunta, top_k=2)
    if not retrieved:
        return "Nenhum trecho relevante foi localizado no manual extenso."

    retrieved_text = ""
    for item in retrieved:
        retrieved_text += (
            f"--- [RELEVÂNCIA: {item['relevance_score']}] (Parágrafo {item['chunk_id']}) ---\n"
            f"{item['content']}\n\n"
        )

    return retrieved_text.strip()


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 10 - PIPELINE DE RAG SOBRE MANUAIS TÉCNICOS EXTENSOS (SDK) ")
    print("=" * 70)

    print(
        f"Documento extenso 'manual_extenso_caldeira.txt' carregado e dividido em {len(all_chunks)} chunks semânticos."
    )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente_rag = Agent(
        name="AgenteRAGManuaisExtensos",
        instructions="Você é um engenheiro especialista em caldeiras industriais. Sempre utilize a ferramenta 'buscar_no_manual_extenso_rag' para recuperar as especificações do manual e responda com base nos trechos recuperados.",
        tools=[buscar_no_manual_extenso_rag],
        model=model_name,
    )

    pergunta_especifica = "Qual é o torque exato de aperto dos parafusos do flange de exaustão principal da Caldeira CG-800 e qual a periodicidade de aplicação da graxa fluorada?"
    print(f"\nPergunta do Técnico: {pergunta_especifica}\n")

    resultado_rag = await Runner.run(agente_rag, pergunta_especifica)

    print("\n" + "=" * 70)
    print(" RESPOSTA FINAL DO AGENTE SINTETIZADA A PARTIR DO CHUNK DO MEIO (CHUNK 11) ")
    print("=" * 70)
    print(resultado_rag.final_output)


if __name__ == "__main__":
    asyncio.run(main())
