import asyncio
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


class ChatProtocolDemo:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def run_multiturn_conversation(self):
        """1.

        Conversa multi-turno acumulando histórico (system, user, assistant).
        """
        print("\n" + "=" * 60)
        print(" 1. DEMONSTRAÇÃO DE CONVERSA MULTI-TURNO COM HISTÓRICO ")
        print("=" * 60)

        history = [
            {
                "role": "system",
                "content": "Você é um especialista em diagnóstico de falhas industriais.",
            }
        ]

        # Turno 1: Usuário apresenta o equipamento e a falha inicial
        prompt_1 = "Estou analisando o Compressor Parafuso Modelo CP-500. Ele está apresentando superaquecimento após 2 horas de operação."
        history.append({"role": "user", "content": prompt_1})
        print(f"\n[Usuário - Turno 1]: {prompt_1}")

        try:
            resp_1 = await self.client.chat.completions.create(
                model=self.model, messages=history, temperature=0.2
            )
            ans_1 = resp_1.choices[0].message.content or ""
        except Exception as e:
            ans_1 = f"[Simulação]: Entendido. Para o Compressor Parafuso CP-500, o superaquecimento pode ser causado por elemento filtrante obstruído ou nível baixo de óleo refrigerante. (Erro API: {e})"

        history.append({"role": "assistant", "content": ans_1})
        print(f"\n[Agente - Turno 1]:\n{ans_1}")

        # Turno 2: Pergunta anafórica (depende do contexto do equipamento CP-500 citado no Turno 1)
        prompt_2 = "Quais são os óleos lubrificantes específicos recomendados para ele e qual a pressão ideal de trabalho?"
        history.append({"role": "user", "content": prompt_2})
        print(f"\n[Usuário - Turno 2 (Contextual/Anafórico)]: {prompt_2}")

        try:
            resp_2 = await self.client.chat.completions.create(
                model=self.model, messages=history, temperature=0.2
            )
            ans_2 = resp_2.choices[0].message.content or ""
        except Exception as e:
            ans_2 = f"[Simulação]: Para ele (Compressor Parafuso CP-500), recomenda-se óleo sintético ISO VG 46 ou VG 68. A pressão ideal de trabalho varia entre 7.5 e 10 bar. (Erro API: {e})"

        history.append({"role": "assistant", "content": ans_2})
        print(f"\n[Agente - Turno 2]:\n{ans_2}")

    async def run_hyperparameter_tests(self):
        """2.

        Variação de Temperatura/Top-P para Diagnóstico Técnicos e
        Ajuste de Max Tokens/Frequency Penalty para Sugestões Abertas.
        """
        print("\n" + "=" * 60)
        print(" 2. EXPERIMENTAÇÃO COM HIPERPARÂMETROS DA API ")
        print("=" * 60)

        prompt_diag = "Qual é a causa provável do código de erro E-104 em um inversor de frequência trifásico?"

        # Teste 1: Diagnóstico com baixa temperatura e top_p (Determinístico/Preciso)
        print("\n--- Teste A: Diagnóstico Técnico (temp=0.1, top_p=0.1) ---")
        try:
            resp_a = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_diag}],
                temperature=0.1,
                top_p=0.1,
            )
            print(resp_a.choices[0].message.content)
        except Exception as e:
            print(
                f"[Simulação]: Erro E-104 indica sobretensão no barramento DC devido a desaceleração rápida ou tensão de entrada elevada. (Erro: {e})"
            )

        # Teste 2: Diagnóstico com alta temperatura e top_p (Criativo/Estocástico - Não recomendado para diagnóstico)
        print("\n--- Teste B: Diagnóstico Técnico (temp=0.9, top_p=0.95) ---")
        try:
            resp_b = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_diag}],
                temperature=0.9,
                top_p=0.95,
            )
            print(resp_b.choices[0].message.content)
        except Exception as e:
            print(
                f"[Simulação]: O código E-104 pode ser uma falha genérica de comunicação, sobrecarga ou aquecimento. (Erro: {e})"
            )

        # Teste 3: Sugestão de manutenção preventiva (Ajuste de max_tokens e frequency_penalty)
        prompt_sugestao = "Elabore um plano criativo de melhorias e sugestões abertas para manutenção preventiva na planta industrial."
        print(
            "\n--- Teste C: Sugestão Aberta (temp=0.7, max_tokens=250, frequency_penalty=1.2) ---"
        )
        try:
            resp_c = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt_sugestao}],
                temperature=0.7,
                max_tokens=250,
                frequency_penalty=1.2,
            )
            print(resp_c.choices[0].message.content)
        except Exception as e:
            print(
                f"[Simulação]: 1. Implementação de sensores IoT para análise de vibração. 2. Termografia infravermelha semanal. 3. Gamificação da rotina dos operadores. (Erro: {e})"
            )


async def main():
    demo = ChatProtocolDemo()
    await demo.run_multiturn_conversation()
    await demo.run_hyperparameter_tests()


if __name__ == "__main__":
    asyncio.run(main())
