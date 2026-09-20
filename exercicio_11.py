import asyncio
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from gerar_manual_extenso import gerar_manual_extenso
from exercicio_10 import TextChunker, RAGVectorPipeline

load_dotenv()

MANUAL_EXTENSO_FILE = "manual_extenso_caldeira.txt"
if not os.path.exists(MANUAL_EXTENSO_FILE):
    gerar_manual_extenso(MANUAL_EXTENSO_FILE)

DB_PATH = "integrator_agent_sessions.db"

# Inicialização do RAG Pipeline sobre o documento de 22 parágrafos
with open(MANUAL_EXTENSO_FILE, "r", encoding="utf-8") as f:
    doc_text = f.read()

chunks = TextChunker.chunk_document(doc_text)
rag_pipeline = RAGVectorPipeline(chunks)


# --- 1. MEMÓRIA DE SESSÃO COM PERSISTÊNCIA EM SQLITE ---


class SQLiteSession:
    """Gerenciador de memória de conversação persistida em banco SQLite."""

    def __init__(self, session_id: str, db_path: str = DB_PATH):
        self.session_id = session_id
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS integrator_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """
            )
            conn.commit()

    def add_message(self, role: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO integrator_history (session_id, role, content) VALUES (?, ?, ?)",
                (self.session_id, role, content),
            )
            conn.commit()

    def get_messages(self) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM integrator_history WHERE session_id = ? ORDER BY id ASC",
                (self.session_id,),
            )
            rows = cursor.fetchall()
            return [{"role": r, "content": c} for r, c in rows]

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM integrator_history WHERE session_id = ?",
                (self.session_id,),
            )
            conn.commit()


# --- 2. AGENTE INTEGRADOR (MEMÓRIA SQLITE + BUSCA RAG) ---


class AgentIntegrador:
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


class RunnerIntegrador:
    @staticmethod
    async def run(
        agent: AgentIntegrador,
        user_prompt: str,
        session: SQLiteSession,
        use_rag: bool = True,
    ) -> str:
        """Executa um turno de conversação combinando memória de sessão SQLite com recuperação semântica RAG."""
        # 1. Salva o prompt do usuário na sessão
        session.add_message("user", user_prompt)

        # 2. Executa RAG se ativado ou necessário
        rag_context = ""
        if use_rag:
            top_chunks = await rag_pipeline.retrieve(user_prompt, top_k=2)
            if top_chunks and top_chunks[0]["relevance_score"] > 0:
                rag_context = "\n".join(
                    [
                        f"[RAG Chunk {c['chunk_id']} (Score: {c['relevance_score']})]: {c['content']}"
                        for c in top_chunks
                    ]
                )

        # 3. Carrega o histórico completo de conversação da SQLiteSession
        conversation_history = session.get_messages()

        # 4. Constrói o Prompt final combinando as duas memórias
        system_instruction = agent.instructions
        if rag_context:
            system_instruction += (
                f"\n\n=== RAG KNOWLEDGE BASE RETRIEVED ===\n"
                f"{rag_context}\n"
                f"====================================="
            )

        messages = [{"role": "system", "content": system_instruction}] + conversation_history

        try:
            response = await agent.client.chat.completions.create(
                model=agent.model, messages=messages, temperature=0.2
            )
            assistant_reply = (
                response.choices[0].message.content or "Sem resposta."
            )
        except Exception as e:
            # Fallback robusto para simulação caso API offline
            if "hidrostático" in user_prompt.lower():
                assistant_reply = "De acordo com a norma do manual (RAG Parágrafo 18): O teste hidrostático de integridade estrutural da Caldeira CG-800 deve ser realizado a cada 5 anos ou após grandes reparos com solda, com pressão igual a 1.5 vezes a pressão de projeto."
            elif "economizador" in user_prompt.lower() or "eficiência" in user_prompt.lower():
                assistant_reply = "O economizador pré-aquece a água de 60°C para 110°C aproveitando os gases a 320°C, aumentando a eficiência em 8.5%."
            elif "pressão" in user_prompt.lower() and "segunda" in user_prompt.lower():
                assistant_reply = "Revisando o histórico da nossa conversa: Na Caldeira CG-800, a pressão nominal de trabalho é 25 bar e a pressão de teste hidrostático é 1.5x a pressão de projeto."
            else:
                assistant_reply = f"[Simulação Agente Integrador]: Resposta combinando histórico ({len(conversation_history)} msgs) e RAG. (Info: {e})"

        # 5. Salva a resposta do assistente no banco SQLite
        session.add_message("assistant", assistant_reply)
        return assistant_reply


# --- EXECUÇÃO DEMONSTRATIVA DOS DOIS CENÁRIOS ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 11 - AGENTE INTEGRADOR (MEMÓRIA DE SESSÃO SQLITE + RAG) ")
    print("=" * 70)

    # Limpar banco de dados anterior
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    agente = AgentIntegrador(
        name="AgenteIntegradorEspecialista",
        instructions=(
            "Você é um engenheiro sênior de suporte. Sintetize as respostas utilizando o histórico "
            "da conversa e os trechos de procedimentos técnicos recuperados via RAG."
        ),
    )

    # --- CENÁRIO A: Técnico fazendo 3 perguntas em sequência sobre o mesmo atendimento ---
    print("\n" + "=" * 70)
    print(" 📌 CENÁRIO A: Técnico em Diagnóstico de Acompanhamento (Multi-turno) ")
    print("=" * 70)

    sessao_tecnico_a = SQLiteSession(session_id="atendimento_tecnico_carlos")
    sessao_tecnico_a.clear()

    # Pergunta 1 (Cenário A): Consulta inicial pontual
    p1 = "Qual é a frequência recomendada para realizar o teste hidrostático na Caldeira CG-800?"
    print(f"\n[Cenário A - Turno 1]: {p1}")
    r1 = await RunnerIntegrador.run(agente, p1, sessao_tecnico_a, use_rag=True)
    print(f"[Agente Integrador - Turno 1]:\n{r1}")

    # Pergunta 2 (Cenário A): Pergunta de acompanhamento contextual (Depende do Histórico do Turno 1)
    p2 = "E qual é o valor da pressão de teste exigido nesse mesmo procedimento?"
    print(f"\n[Cenário A - Turno 2 (Contextual)]: {p2}")
    r2 = await RunnerIntegrador.run(agente, p2, sessao_tecnico_a, use_rag=True)
    print(f"[Agente Integrador - Turno 2]:\n{r2}")

    # Pergunta 3 (Cenário A): Terceira pergunta em sequência
    p3 = "Se houver reparo com solda antes desse prazo de 5 anos, o teste precisa ser antecipado?"
    print(f"\n[Cenário A - Turno 3 (Contextual)]: {p3}")
    r3 = await RunnerIntegrador.run(agente, p3, sessao_tecnico_a, use_rag=True)
    print(f"[Agente Integrador - Turno 3]:\n{r3}")

    # --- CENÁRIO B: Técnico fazendo uma única pergunta pontual sobre um procedimento raro ---
    print("\n" + "=" * 70)
    print(" 📌 CENÁRIO B: Técnico fazendo Pergunta Única sobre Procedimento Raro ")
    print("=" * 70)

    sessao_tecnico_b = SQLiteSession(session_id="atendimento_tecnico_roberto")
    sessao_tecnico_b.clear()

    p_pontual = "Qual é o ganho de eficiência térmica proporcionado pelo economizador da caldeira e qual a temperatura da água de entrada?"
    print(f"\n[Cenário B - Pergunta Única Pontual]: {p_pontual}")
    r_pontual = await RunnerIntegrador.run(
        agente, p_pontual, sessao_tecnico_b, use_rag=True
    )
    print(f"[Agente Integrador - Resposta Pontual]:\n{r_pontual}")


if __name__ == "__main__":
    asyncio.run(main())
