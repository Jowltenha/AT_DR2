import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings, function_tool
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)


def create_response_input_item(
    role: str, content: Any, tool_call_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cria um dicionário padronizado no formato TResponseInputItem para persistência de histórico."""
    return {
        "role": role,
        "content": str(content) if not isinstance(content, str) else content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_call_id": tool_call_id,
    }


@function_tool
def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """[MANUAL TÉCNICO DE FÁBRICA]: Especificações originais do fabricante, especificações de projeto e significado dos CÓDIGOS DE ERRO e falhas conhecidas de fábrica."""
    if not os.path.exists(MANUAL_FILE):
        return f"Erro: Arquivo {MANUAL_FILE} não encontrado."
    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)
    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)
    return f"Equipamento {codigo_equipamento} não encontrado no manual."


@function_tool
def consultar_historico_manutencao(codigo_equipamento: str) -> str:
    """[HISTÓRICO DE MANUTENÇÃO DE CAMPO]: Registro de O.S. anteriores, datas das últimas revisões feitas pelos técnicos da empresa, peças já substituídas e intervenções executadas."""
    historicos_ficticios = {
        "EQ-103": {
            "codigo": "EQ-103",
            "ultima_manutencao": "2026-08-15",
            "tecnico_responsavel": "Carlos Silva",
            "intervencao": "Troca de capacitores e ajuste na rampa de desaceleração.",
            "status": "Operacional",
        }
    }
    equip_hist = historicos_ficticios.get(
        codigo_equipamento.upper(),
        {
            "codigo": codigo_equipamento,
            "historico": "Nenhum histórico de manutenção registrado para este equipamento.",
        },
    )
    return json.dumps(equip_hist, ensure_ascii=False)


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 6 - SELEÇÃO DE TOOLS, STOP_ON_FIRST_TOOL E HISTÓRICO (SDK) ")
    print("=" * 70)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente = Agent(
        name="AgenteManutencaoAvancado",
        instructions="Você é um assistente técnico industrial. Use a ferramenta apropriada para cada tipo de consulta.",
        tools=[consultar_manual_equipamento, consultar_historico_manutencao],
        model=model_name,
    )

    prompt_teste = "Qual o estado de manutenção e histórico das revisões do equipamento EQ-103?"

    # 1. Teste automatizado forçando tool_choice para 'consultar_historico_manutencao'
    print(
        "\n[1. Teste Automatizado: Forçando tool_choice no ModelSettings para 'consultar_historico_manutencao']"
    )
    agente_forced = Agent(
        name="AgenteManutencaoForced",
        instructions="Você é um assistente técnico industrial.",
        tools=[consultar_manual_equipamento, consultar_historico_manutencao],
        model=model_name,
        model_settings=ModelSettings(tool_choice="consultar_historico_manutencao"),
    )
    res_forced = await Runner.run(agente_forced, prompt_teste)
    print(f"Resposta Final: {res_forced.final_output}")

    # 2. Teste de desempenho com tool_use_behavior='stop_on_first_tool'
    print("\n" + "-" * 70)
    print(
        "[2. Teste de Desempenho: Execução com tool_use_behavior='stop_on_first_tool']"
    )
    agente_stopped = Agent(
        name="AgenteManutencaoStopped",
        instructions="Você é um assistente técnico industrial.",
        tools=[consultar_manual_equipamento, consultar_historico_manutencao],
        model=model_name,
        tool_use_behavior="stop_on_first_tool",
    )
    res_stopped = await Runner.run(agente_stopped, prompt_teste)
    print(f"Resposta Retornada (Direta da Tool): {res_stopped.final_output}")

    # 3. Exibição da Lista de Histórico no formato TResponseInputItem
    print("\n" + "=" * 70)
    print(" HISTÓRICO DE EXECUÇÃO REGISTRADO (Estrutura TResponseInputItem) ")
    print("=" * 70)
    history_items = [
        create_response_input_item("user", prompt_teste),
        create_response_input_item(
            "assistant_tool_call",
            {
                "function": "consultar_historico_manutencao",
                "arguments": {"codigo_equipamento": "EQ-103"},
            },
            tool_call_id="call_01",
        ),
        create_response_input_item(
            "tool", res_stopped.final_output, tool_call_id="call_01"
        ),
    ]
    print(json.dumps(history_items, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
