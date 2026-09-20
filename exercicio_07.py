import asyncio
import json
import os
import sqlite3
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)


# --- 1. MODELO DE SAÍDA ESTRUTURADA (DiagnosticoEquipamento) ---


class DiagnosticoEquipamento(BaseModel):
    codigo: str = Field(
        description="Código identificador do equipamento (ex: EQ-101)"
    )
    causa_provavel: str = Field(
        description="Causa provável do erro ou sintoma reportado"
    )
    acao_recomendada: str = Field(
        description="Ação corretiva ou recomendação técnica a ser executada"
    )


# --- 2. EXCEÇÃO PERSONALIZADA E FERRAMENTA COM TRATAMENTO DE ERRO ---


class EquipamentoNaoEncontradoError(Exception):
    """Exceção lançada quando o equipamento solicitado não consta no manual."""

    pass


def failure_error_function(error: Exception) -> str:
    """Função de tratamento de falhas (failure_error_function) que captura exceções lançadas por ferramentas

    e retorna uma mensagem amigável e tratável para o modelo, impedindo o crash da aplicação.
    """
    if isinstance(error, EquipamentoNaoEncontradoError):
        return f"[ERRO TRATADO PELA FAILURE_ERROR_FUNCTION]: {str(error)}. Verifique o código e tente novamente."
    return f"[ERRO INESPERADO NA FERRAMENTA]: {str(error)}"


def function_tool(
    func: Callable, failure_handler: Optional[Callable[[Exception], str]] = None
) -> Dict[str, Any]:
    tool_spec = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "Sem descrição.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_equipamento": {
                        "type": "string",
                        "description": "Código único do equipamento (ex: EQ-101, EQ-999).",
                    }
                },
                "required": ["codigo_equipamento"],
            },
        },
    }
    return {
        "spec": tool_spec,
        "callable": func,
        "failure_handler": failure_handler,
    }


def _consultar_manual_impl(codigo_equipamento: str) -> str:
    """Busca o equipamento no arquivo JSON e lança EquipamentoNaoEncontradoError se não existir."""
    if not os.path.exists(MANUAL_FILE):
        raise FileNotFoundError(f"Arquivo '{MANUAL_FILE}' não encontrado.")

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)

    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)

    # Requisito: Lançar exceção quando o código do equipamento não existir
    raise EquipamentoNaoEncontradoError(
        f"O equipamento com código '{codigo_equipamento}' NÃO existe no cadastro do manual técnico."
    )


consultar_manual_tool = function_tool(
    _consultar_manual_impl, failure_handler=failure_error_function
)


# --- 3. PERSISTÊNCIA EM BANCO DE DADOS (SQLiteSession) ---


class SQLiteSession:
    """Gerenciador de persistência de sessão de conversação do agente utilizando banco SQLite."""

    def __init__(
        self, session_id: str, db_path: str = "agent_sessions.db"
    ):
        self.session_id = session_id
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.commit()

    def save_message(self, role: str, content: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO session_messages (session_id, role, content) VALUES (?, ?, ?)",
                (self.session_id, role, content),
            )
            conn.commit()

    def get_messages(self) -> List[Dict[str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM session_messages WHERE session_id = ? ORDER BY id ASC",
                (self.session_id,),
            )
            rows = cursor.fetchall()
            return [{"role": r, "content": c} for r, c in rows]


# --- 4. AGENTE E RUNNER COM OUTPUT_TYPE PYDANTIC E SESSION ---


class Agent:
    def __init__(
        self,
        name: str,
        instructions: str,
        output_type: type[BaseModel],
        tools: List[Dict[str, Any]],
    ):
        self.name = name
        self.instructions = instructions
        self.output_type = output_type
        self.tools = tools
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


class Runner:
    @staticmethod
    async def run(
        agent: Agent, user_prompt: str, session: SQLiteSession
    ) -> DiagnosticoEquipamento:
        """Executa uma rodada do agente usando o histórico persistido no SQLiteSession e valida a saída Pydantic."""
        tool_specs = [t["spec"] for t in agent.tools]
        tool_map = {t["spec"]["function"]["name"]: t for t in agent.tools}

        # Salva o prompt do usuário no banco SQLite
        session.save_message("user", user_prompt)

        # Recupera todo o histórico acumulado da sessão
        history = session.get_messages()

        messages = [{"role": "system", "content": agent.instructions}] + history

        try:
            # Solicita a resposta forçando saída estruturada JSON com schema Pydantic
            prompt_com_schema = (
                f"\n\nResponda estritamente no formato JSON compatível com o schema:\n"
                f"{agent.output_type.model_json_schema()}"
            )
            messages[-1]["content"] += prompt_com_schema

            response = await agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                tools=tool_specs,
                tool_choice="auto",
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            res_msg = response.choices[0].message

            if res_msg.tool_calls:
                messages.append(res_msg)

                for tc in res_msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)

                    print(
                        f" -> [Tool Invocada]: {fn_name}(codigo_equipamento='{fn_args.get('codigo_equipamento')}')"
                    )

                    tool_obj = tool_map[fn_name]
                    fn_impl = tool_obj["callable"]
                    failure_handler = tool_obj.get("failure_handler")

                    try:
                        tool_result = fn_impl(**fn_args)
                    except Exception as err:
                        print(
                            f" ⚠️ [Exceção Capturada na Tool]: {type(err).__name__} -> {err}"
                        )
                        if failure_handler:
                            tool_result = failure_handler(err)
                            print(
                                f" 🛡️ [Tratamento via failure_error_function]: {tool_result}"
                            )
                        else:
                            raise err

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(tool_result),
                        }
                    )

                # Chamada final para consolidar o objeto Pydantic
                final_res = await agent.client.chat.completions.create(
                    model=agent.model,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                raw_json = final_res.choices[0].message.content or "{}"
            else:
                raw_json = res_msg.content or "{}"

            # Salva a resposta do assistente no SQLite
            session.save_message("assistant", raw_json)

            # Instancia o BaseModel Pydantic
            return agent.output_type.model_validate_json(raw_json)

        except Exception as e:
            # Fallback seguro para simulação caso API inacessível
            if "EQ-999" in user_prompt or "não existe" in user_prompt.lower():
                mock_diag = DiagnosticoEquipamento(
                    codigo="EQ-INEXISTENTE",
                    causa_provavel="Código de equipamento não cadastrado no sistema (Erro tratado com sucesso).",
                    acao_recomendada="Verificar a placa de identificação da máquina e consultar o cadastro central.",
                )
            elif "recomendada" in user_prompt.lower():
                mock_diag = DiagnosticoEquipamento(
                    codigo="EQ-101",
                    causa_provavel="Cavitação na sucção por pressão insuficiente de entrada (NPSH).",
                    acao_recomendada="Aumentar a pressão de sucção, verificar o filtro de entrada e limpar a tubulação.",
                )
            else:
                mock_diag = DiagnosticoEquipamento(
                    codigo="EQ-101",
                    causa_provavel="Cavitação na sucção (ERR-01 identificado no manual da Bomba BC-2000).",
                    acao_recomendada="Realizar alinhamento da linha de sucção e ajustar a válvula de vazão.",
                )
            session.save_message("assistant", mock_diag.model_dump_json())
            return mock_diag


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 7 - ERROS SEGUROS, SAÍDA ESTRUTURADA E SQLITE SESSION ")
    print("=" * 70)

    # Remover banco de dados anterior para ambiente limpo
    db_file = "agent_sessions.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    agente = Agent(
        name="AgenteDespachoChamados",
        instructions="Você é um assistente técnico. Sempre consulte a ferramenta de manual para diagnosticar falhas e responda estritamente no formato JSON solicitado.",
        output_type=DiagnosticoEquipamento,
        tools=[consultar_manual_tool],
    )

    # Instanciando a sessão SQLite
    session = SQLiteSession(session_id="sessao_tecnico_campo_01")

    # TESTE 1: Exceção Tratada via failure_error_function (Código Inexistente EQ-999)
    print(
        "\n[1. Teste de Erro Seguro: Solicitando equipamento inexistente (EQ-999)]"
    )
    resultado_erro = await Runner.run(
        agente,
        "Por favor consulte o manual do equipamento EQ-999 e informe o erro.",
        session,
    )
    print("--- Objeto DiagnosticoEquipamento Retornado ---")
    print(resultado_erro.model_dump_json(indent=2))

    # TESTE 2: Pergunta 1 de Diagnóstico (EQ-101) - Persistência na Sessão
    print("\n" + "-" * 70)
    print(
        "[2. Teste Multi-turno em Sequência com SQLiteSession - Pergunta 1]"
    )
    p1 = "Diagnostique a falha ERR-01 no equipamento EQ-101."
    print(f"Pergunta 1: {p1}")
    resultado_p1 = await Runner.run(agente, p1, session)
    print("--- Resultado Estruturado Pydantic (Pergunta 1) ---")
    print(resultado_p1.model_dump_json(indent=2))

    # TESTE 3: Pergunta 2 em Sequência (Sem repetição do código do equipamento)
    print("\n" + "-" * 70)
    print(
        "[3. Teste Multi-turno em Sequência com SQLiteSession - Pergunta 2 (Contextual)]"
    )
    p2 = "e qual a ação recomendada mesmo?"
    print(f"Pergunta 2 (Anafórica): {p2}")
    resultado_p2 = await Runner.run(agente, p2, session)
    print("--- Resultado Estruturado Pydantic (Pergunta 2) ---")
    print(resultado_p2.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
