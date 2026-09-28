import asyncio
import os
from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings

load_dotenv()


def get_valid_model_name() -> str:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        return "gpt-4o-mini"
    return model_name


async def run_multiturn_conversation():
    """1. Conversa multi-turno utilizando o OpenAI Agents SDK."""
    print("\n" + "=" * 60)
    print(" 1. DEMONSTRAÇÃO DE CONVERSA MULTI-TURNO COM HISTÓRICO VIA SDK ")
    print("=" * 60)

    model_name = get_valid_model_name()

    agent = Agent(
        name="EspecialistaFalhas",
        instructions="Você é um especialista em diagnóstico de falhas industriais.",
        model=model_name,
    )

    prompt_1 = "Estou analisando o Compressor Parafuso Modelo CP-500. Ele está apresentando superaquecimento após 2 horas de operação."
    print(f"\n[Usuário - Turno 1]: {prompt_1}")

    result_1 = await Runner.run(agent, prompt_1)
    ans_1 = str(result_1.final_output)
    print(f"\n[Agente - Turno 1]:\n{ans_1}")

    prompt_2 = f"Sobre o mesmo Compressor Parafuso CP-500 citado anteriormente: quais são os óleos lubrificantes específicos recomendados para ele e qual a pressão ideal de trabalho?"
    print(f"\n[Usuário - Turno 2 (Contextual)]: {prompt_2}")

    result_2 = await Runner.run(agent, prompt_2)
    ans_2 = str(result_2.final_output)
    print(f"\n[Agente - Turno 2]:\n{ans_2}")


async def run_hyperparameter_tests():
    """2. Variação de Temperatura/Top-P e Max Tokens/Frequency Penalty usando ModelSettings."""
    print("\n" + "=" * 60)
    print(" 2. EXPERIMENTAÇÃO COM HIPERPARÂMETROS DA API VIA SDK ")
    print("=" * 60)

    model_name = get_valid_model_name()
    prompt_diag = "Qual é a causa provável do código de erro E-104 em um inversor de frequência trifásico?"

    print("\n--- Teste A: Diagnóstico Técnico (temp=0.1, top_p=0.1) ---")
    agent_a = Agent(
        name="DiagDeterministico",
        instructions="Você é um especialista em diagnóstico técnico.",
        model=model_name,
        model_settings=ModelSettings(temperature=0.1, top_p=0.1),
    )
    res_a = await Runner.run(agent_a, prompt_diag)
    print(res_a.final_output)

    print("\n--- Teste B: Diagnóstico Técnico (temp=0.9, top_p=0.95) ---")
    agent_b = Agent(
        name="DiagEstocastico",
        instructions="Você é um especialista em diagnóstico técnico.",
        model=model_name,
        model_settings=ModelSettings(temperature=0.9, top_p=0.95),
    )
    res_b = await Runner.run(agent_b, prompt_diag)
    print(res_b.final_output)

    prompt_sugestao = "Elabore um plano sucinto com 3 melhorias objetivas para manutenção preventiva na planta industrial."
    print("\n--- Teste C: Sugestão Aberta (temp=0.7, max_tokens=600, frequency_penalty=1.2) ---")
    agent_c = Agent(
        name="SugestaoManutencao",
        instructions="Você é um consultor de manutenção industrial. Responda de forma sucinta e direta.",
        model=model_name,
        model_settings=ModelSettings(
            temperature=0.7, max_tokens=600, frequency_penalty=1.2
        ),
    )
    res_c = await Runner.run(agent_c, prompt_sugestao)
    print(res_c.final_output)


async def main():
    await run_multiturn_conversation()
    await run_hyperparameter_tests()


if __name__ == "__main__":
    asyncio.run(main())
