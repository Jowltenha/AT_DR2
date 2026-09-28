import asyncio
import json
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool, SQLiteSession
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


# --- 2. EXCEÇÃO PERSONALIZADA E FAILURE_ERROR_FUNCTION ---


class EquipamentoNaoEncontradoError(Exception):
    """Exceção lançada quando o equipamento solicitado não consta no manual."""

    pass


def failure_error_function(ctx, error: Exception) -> str:
    """Função de tratamento de falhas (failure_error_function) que captura exceções lançadas por ferramentas

    e retorna uma mensagem amigável para o modelo, impedindo o crash da aplicação.
    """
    if isinstance(error, EquipamentoNaoEncontradoError):
        return f"[ERRO TRATADO PELA FAILURE_ERROR_FUNCTION]: {str(error)}. Verifique o código e tente novamente."
    return f"[ERRO INESPERADO NA FERRAMENTA]: {str(error)}"


@function_tool(failure_error_function=failure_error_function)
def consultar_manual_tool(codigo_equipamento: str) -> str:
    """[MANUAL TÉCNICO DE FÁBRICA]: Consulta o manual técnico pelo código do equipamento (ex: 'EQ-101', 'EQ-102'). Passe apenas o código do equipamento."""
    if not os.path.exists(MANUAL_FILE):
        raise FileNotFoundError(f"Arquivo '{MANUAL_FILE}' não encontrado.")

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)

    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)

    raise EquipamentoNaoEncontradoError(
        f"O equipamento com código '{codigo_equipamento}' NÃO existe no cadastro do manual técnico."
    )


# --- 3. EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 7 - ERROS SEGUROS, SAÍDA ESTRUTURADA E SQLITE SESSION (SDK) ")
    print("=" * 70)

    db_file = "agent_sessions.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    session = SQLiteSession(session_id="sessao_tecnico_campo_01", db_path=db_file)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente = Agent(
        name="AgenteDespachoChamados",
        instructions=(
            "Você é um assistente técnico industrial. "
            "Consulte a ferramenta de manual 'consultar_manual_tool' para diagnosticar a falha. "
            "Após consultar a ferramenta (ou caso ocorra erro), responda imediatamente no formato de diagnóstico estruturado."
        ),
        output_type=DiagnosticoEquipamento,
        tools=[consultar_manual_tool],
        model=model_name,
    )

    # TESTE 1: Exceção Tratada via failure_error_function (Código Inexistente EQ-999)
    print(
        "\n[1. Teste de Erro Seguro: Solicitando equipamento inexistente (EQ-999)]"
    )
    resultado_erro = await Runner.run(
        agente,
        "Por favor consulte o manual do equipamento EQ-999 e informe o erro.",
        session=session,
    )
    output_erro: DiagnosticoEquipamento = resultado_erro.final_output
    print("--- Objeto DiagnosticoEquipamento Retornado ---")
    print(output_erro.model_dump_json(indent=2))

    # TESTE 2: Pergunta 1 de Diagnóstico (EQ-101) - Persistência na Sessão
    print("\n" + "-" * 70)
    print(
        "[2. Teste Multi-turno em Sequência com SQLiteSession - Pergunta 1]"
    )
    p1 = "Diagnostique a falha ERR-01 no equipamento EQ-101."
    print(f"Pergunta 1: {p1}")
    resultado_p1 = await Runner.run(agente, p1, session=session)
    output_p1: DiagnosticoEquipamento = resultado_p1.final_output
    print("--- Resultado Estruturado Pydantic (Pergunta 1) ---")
    print(output_p1.model_dump_json(indent=2))

    # TESTE 3: Pergunta 2 em Sequência (Contextual/Anafórica)
    print("\n" + "-" * 70)
    print(
        "[3. Teste Multi-turno em Sequência com SQLiteSession - Pergunta 2 (Contextual)]"
    )
    p2 = "e qual a ação recomendada mesmo?"
    print(f"Pergunta 2 (Anafórica): {p2}")
    resultado_p2 = await Runner.run(agente, p2, session=session)
    output_p2: DiagnosticoEquipamento = resultado_p2.final_output
    print("--- Resultado Estruturado Pydantic (Pergunta 2) ---")
    print(output_p2.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
