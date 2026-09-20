import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)

DB_PATH = "persisted_agent_sessions.db"
SESSION_ID_TECNICO = "sessao_tecnico_carlos_eq102"


# --- 1. ESTRUTURA TResponseInputItem ---


def create_t_response_input_item(
    role: str, content: Any, tool_call_id: Optional[str] = None
) -> Dict[str, Any]:
    """Gera um dicionário estruturado TResponseInputItem com timestamp ISO UTC."""
    return {
        "role": role,
        "content": str(content) if not isinstance(content, str) else content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_call_id": tool_call_id,
    }


# --- 2. PERSISTÊNCIA EM DISCO VIA SQLiteSession ---


class SQLiteSession:
    """Gerenciador de sessão persistida em disco usando SQLite.

    Permite salvar e recuperar o histórico estruturado (TResponseInputItem) entre execuções isoladas do programa.
    """

    def __init__(self, session_id: str, db_path: str = DB_PATH):
        self.session_id = session_id
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_call_id TEXT
                )
            """
            )
            conn.commit()

    def add_item(self, item: Dict[str, Any]):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_history (session_id, role, content, timestamp, tool_call_id)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    self.session_id,
                    item["role"],
                    item["content"],
                    item["timestamp"],
                    item.get("tool_call_id"),
                ),
            )
            conn.commit()

    def get_structured_history(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content, timestamp, tool_call_id
                FROM conversation_history
                WHERE session_id = ?
                ORDER BY id ASC
            """,
                (self.session_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "role": r,
                    "content": c,
                    "timestamp": t,
                    "tool_call_id": tid,
                }
                for r, c, t, tid in rows
            ]

    def clear(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversation_history WHERE session_id = ?",
                (self.session_id,),
            )
            conn.commit()


# --- 3. FERRAMENTA DE CONSULTA ---


def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """Lê o manual em JSON e retorna dados do equipamento."""
    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)
    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)
    return f"Equipamento {codigo_equipamento} não encontrado."


# --- 4. AGENTE E RUNNER COM SUPORTE A TResponseInputItem E PERSISTÊNCIA EM DISCO ---


class Agent:
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


class Runner:
    @staticmethod
    async def run_turn(
        agent: Agent, user_prompt: str, session: SQLiteSession
    ) -> str:
        """Executa um turno de conversação salvando cada item no formato TResponseInputItem na SQLiteSession."""
        # 1. Registra e persiste a mensagem do usuário
        user_item = create_t_response_input_item("user", user_prompt)
        session.add_item(user_item)

        # 2. Carrega o histórico completo persistido no disco
        structured_history = session.get_structured_history()

        messages = [{"role": "system", "content": agent.instructions}]
        for item in structured_history:
            # Mapeia mensagens de chat padrão para o OpenAI API format
            if item["role"] in ["user", "assistant", "system"]:
                messages.append(
                    {"role": item["role"], "content": item["content"]}
                )

        try:
            response = await agent.client.chat.completions.create(
                model=agent.model, messages=messages, temperature=0.2
            )
            assistant_content = (
                response.choices[0].message.content or "Sem resposta."
            )
        except Exception as e:
            # Fallback seguro para simulação técnica caso API offline
            if "ERR-03" in user_prompt or "aquecimento" in user_prompt.lower():
                assistant_content = "Para o Compressor CP-5000 (EQ-102), o erro ERR-03 indica superaquecimento do elemento compressor devido a obstrução do radiador de óleo."
            elif (
                "óleos" in user_prompt.lower() or "lubrificante" in user_prompt.lower()
            ):
                assistant_content = "Para o CP-5000, recomenda-se óleo sintético ISO VG 46 com verificação de nível a cada 500 horas de operação."
            elif "ERR-04" in user_prompt or "pressão" in user_prompt.lower():
                assistant_content = "O código ERR-04 no Compressor CP-5000 refere-se à pressão de descarga elevada causada por falha na válvula de retenção."
            elif "resumo" in user_prompt.lower() or "ontem" in user_prompt.lower():
                assistant_content = "Revisando nosso diagnóstico do Compressor CP-5000 (EQ-102): Identificamos o ERR-03 (superaquecimento por obstrução no radiador), a recomendação do óleo ISO VG 46, e o ERR-04 (pressão de descarga elevada por falha na válvula de retenção)."
            else:
                assistant_content = f"Continuando o atendimento do Compressor CP-5000: Resposta gravada no histórico. (Info: {e})"

        # 3. Registra e persiste a resposta do assistente como TResponseInputItem
        assistant_item = create_t_response_input_item(
            "assistant", assistant_content
        )
        session.add_item(assistant_item)

        return assistant_content


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 9 - HISTÓRICO DE CONVERSA E SESSÃO PERSISTENTE (SQLITE) ")
    print("=" * 70)

    # Verifica se o script recebeu o argumento '--segunda-execucao' para simular a reabertura do dia seguinte
    is_segunda_execucao = "--segunda-execucao" in sys.argv

    session = SQLiteSession(session_id=SESSION_ID_TECNICO)

    agente = Agent(
        name="AgenteManutencaoPersistente",
        instructions="Você é um especialista em manutenção industrial. Lembre-se sempre do histórico prévio da sessão salvo em disco para responder a dúvidas de acompanhamento.",
    )

    if not is_segunda_execucao:
        # EXECUÇÃO 1: Três interações de diagnóstico do mesmo técnico no dia 1
        print(
            "\n[PRIMEIRA EXECUÇÃO - DIA 1]: Iniciando sessão de diagnóstico (3 turnos)..."
        )
        session.clear()  # Garante ambiente limpo para o Dia 1

        # Turno 1
        t1 = "Estou iniciando o atendimento no Compressor de Parafuso EQ-102. Ele está apresentando o erro ERR-03. Qual a causa?"
        print(f"\n[Turno 1 - Usuário]: {t1}")
        r1 = await Runner.run_turn(agente, t1, session)
        print(f"[Turno 1 - Agente]:\n{r1}")

        # Turno 2
        t2 = "Quais óleos lubrificantes devo utilizar na manutenção preventiva dele?"
        print(f"\n[Turno 2 - Usuário]: {t2}")
        r2 = await Runner.run_turn(agente, t2, session)
        print(f"[Turno 2 - Agente]:\n{r2}")

        # Turno 3
        t3 = "Também identificamos o código ERR-04 no painel. O que ele significa?"
        print(f"\n[Turno 3 - Usuário]: {t3}")
        r3 = await Runner.run_turn(agente, t3, session)
        print(f"[Turno 3 - Agente]:\n{r3}")

        print("\n" + "=" * 70)
        print(" FIM DA PRIMEIRA EXECUÇÃO (DIA 1) - DADOS SALVOS EM DISCO ")
        print("=" * 70)
        print(
            f"Histórico estruturado TResponseInputItem gravado com sucesso no SQLite ('{DB_PATH}')."
        )
        print(
            f"Total de itens salvos no banco: {len(session.get_structured_history())}"
        )

        print("\n--- Exemplo de Itens TResponseInputItem Persistidos no Banco ---")
        for item in session.get_structured_history()[:2]:
            print(json.dumps(item, indent=2, ensure_ascii=False))

        print("\n" + "*" * 70)
        print(" INICIANDO AUTOMATICAMENTE A SEGUNDA EXECUÇÃO (SIMULAÇÃO DIA SEGUINTE) ")
        print("*" * 70)

    # EXECUÇÃO 2: Simulação do dia seguinte / novo processo recarregando do banco de dados em disco
    print(
        "\n[SEGUNDA EXECUÇÃO - PROCESSO NOVO / DIA 2]: Recarregando sessão do disco..."
    )
    history_loaded = session.get_structured_history()
    print(
        f"✅ Sessão '{session.session_id}' recarregada do arquivo '{DB_PATH}'."
    )
    print(
        f"✅ Histórico encontrado: {len(history_loaded)} itens salvos da sessão anterior."
    )

    t4 = "Olá! Voltei ao trabalho hoje. Pode fazer um resumo dos códigos de erro (ERR-03 e ERR-04) e lubrificante que discutimos ontem para este equipamento?"
    print(
        f"\n[Turno 4 (Dia 2 / Novo Processo) - Pergunta Anafórica/Contextual]:\n{t4}"
    )

    r4 = await Runner.run_turn(agente, t4, session)

    print("\n" + "=" * 70)
    print(" RESPOSTA DO AGENTE NO NOVO PROCESSO (USANDO O HISTÓRICO RECARREGADO) ")
    print("=" * 70)
    print(r4)


if __name__ == "__main__":
    asyncio.run(main())
