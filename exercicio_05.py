import asyncio
import json
import os
from dotenv import load_dotenv
from agents import Agent, Runner, function_tool
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)


@function_tool
def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """Consulta o manual técnico do equipamento informado e retorna suas especificações e lista de erros em JSON."""
    if not os.path.exists(MANUAL_FILE):
        return f"Erro: Arquivo {MANUAL_FILE} não encontrado."
    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)
    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)
    return f"Equipamento {codigo_equipamento} não encontrado no manual."


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 5 - PRIMEIRA FERRAMENTA: CONSULTA AO MANUAL (@function_tool) ")
    print("=" * 70)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente = Agent(
        name="AgenteConsultaManual",
        instructions="Você é um assistente técnico industrial. Sempre consulte o manual do equipamento usando a ferramenta 'consultar_manual_equipamento' para responder com precisão factual.",
        tools=[consultar_manual_equipamento],
        model=model_name,
    )

    prompt = "O Inversor de Frequência EQ-103 está apresentando o código de erro ERR-05. Qual é a causa provável informada no manual?"
    print(f"\nPergunta do Técnico: {prompt}\n")

    result = await Runner.run(agente, prompt)

    print("--- Resposta do Agente (com base na Tool) ---")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
