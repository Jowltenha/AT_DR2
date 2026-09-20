import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
    

class Agent:
    """Representa o agente configurado com instruções do sistema e modelo."""

    def __init__(
        self, instructions: str, model: str = None
    ):
        self.instructions = instructions
        self.model = model or os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def run(self, user_prompt: str) -> str:
        """Executa a chamada assíncrona para o modelo da OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.instructions},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            # Fallback para demonstração sem chave ativa
            return (
                f"[Simulação/Demonstração]: Resposta para '{user_prompt}' sobre equipamentos industriais.\n"
                f"Detalhe técnico: Motores de indução trifásicos e bombas centrífugas requerem manutenção preditiva constante.\n"
                f"(Info de erro real de API se aplicável: {e})"
            )


class Runner:
    """Orquestra e executa o Agent de forma assíncrona."""

    def __init__(self, agent: Agent):
        self.agent = agent

    async def execute(self, prompt: str) -> str:
        """Método de execução assíncrona utilizando async/await."""
        return await self.agent.run(prompt)


def format_agent_response(response_text: str) -> str:
    """Função auxiliar para formatação elegante da resposta do agente antes da impressão.

    Gerada/Estruturada com apoio do Tab Completion / Command do Editor.
    """
    header = "=" * 60
    title = " AGENTE DE EQUIPAMENTOS INDUSTRIAIS - RESPOSTA "
    footer = "=" * 60
    formatted_body = "\n".join(
        f"  │ {line}" for line in response_text.strip().split("\n")
    )

    return f"\n{header}\n{title.center(60)}\n{header}\n{formatted_body}\n{footer}\n"


async def main():
    print("Iniciando o Agente de Equipamentos Industriais...")

    # Instancia o Agent com instruções específicas do sistema
    agent = Agent(
        instructions="Você é um assistente especialista que responde perguntas gerais sobre equipamentos industriais de forma clara e objetiva."
    )

    # Instancia e executa através do Runner
    runner = Runner(agent)
    prompt_usuario = "Quais são as principais rotinas de manutenção para uma bomba centrífuga?"

    # Execução assíncrona com await
    resposta_bruta = await runner.execute(prompt_usuario)

    # Formatação com a função auxiliar
    resposta_formatada = format_agent_response(resposta_bruta)

    print(resposta_formatada)


if __name__ == "__main__":
    # Execução do loop de eventos assíncrono
    asyncio.run(main())
