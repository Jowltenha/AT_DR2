import asyncio
import os
from dotenv import load_dotenv
from agents import Agent, Runner

load_dotenv()


def format_agent_response(response_text: str) -> str:
    """Função auxiliar para formatação elegante da resposta do agente antes da impressão."""
    header = "=" * 60
    title = " AGENTE DE EQUIPAMENTOS INDUSTRIAIS - RESPOSTA "
    footer = "=" * 60
    formatted_body = "\n".join(
        f"  │ {line}" for line in response_text.strip().split("\n")
    )

    return f"\n{header}\n{title.center(60)}\n{header}\n{formatted_body}\n{footer}\n"


async def main():
    print("Iniciando o Agente de Equipamentos Industriais com OpenAI Agents SDK...")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    # Instancia o Agent do OpenAI Agents SDK
    agent = Agent(
        name="AgenteEquipamentos",
        instructions="Você é um assistente especialista que responde perguntas gerais sobre equipamentos industriais de forma clara e objetiva.",
        model=model_name,
    )

    prompt_usuario = "Quais são as principais rotinas de manutenção para uma bomba centrífuga?"

    # Execução assíncrona utilizando o Runner oficial do SDK
    result = await Runner.run(agent, prompt_usuario)

    # Formatação da resposta final do agente
    resposta_formatada = format_agent_response(str(result.final_output))

    print(resposta_formatada)


if __name__ == "__main__":
    asyncio.run(main())
