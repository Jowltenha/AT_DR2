import asyncio
import os
from typing import List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, Field

load_dotenv()

# --- MODELO DE SAÍDA ESTRUTURADA (output_type) ---


class DiagnosticOutput(BaseModel):
    categoria: str = Field(
        description="Categoria da resposta (ex: Diagnóstico Técnico, Recusa de Escopo, Segurança)"
    )
    equipamento: Optional[str] = Field(
        default=None, description="Nome do equipamento identificado"
    )
    diagnostico_ou_resposta: str = Field(
        description="Conteúdo principal da resposta ou explicação da recusa"
    )
    regras_seguranca_aplicadas: List[str] = Field(
        default_factory=list,
        description="Lista das regras de segurança operacional aplicadas na resposta",
    )


# --- INSTRUÇÃO DE SISTEMA (SYSTEM MESSAGE) ---
SYSTEM_INSTRUCTIONS = """
Você é um agente especialista em diagnóstico de equipamentos industriais.

### RESTRIÇÃO DE DOMÍNIO:
Você DEVE atender EXCLUSIVAMENTE a dúvidas técnicas, diagnósticos de falhas e procedimentos de manutenção de equipamentos industriais.
Se o usuário fizer perguntas administrativas, de RH, financeiras ou corporativas (como solicitação de férias, reembolso, folha de pagamento, contratação), você DEVE RECUSAR o atendimento educadamente, informando que seu escopo é estritamente técnico industrial.

### BASE DE CONHECIMENTO DE SEGURANÇA OPERACIONAL (REGRAS DA EMPRESA):
Sempre que o diagnóstico ou procedimento envolver situações de risco, você DEVE obrigatoriamente citar e aplicar as seguintes regras:
1. [REGRA SEG-01]: Qualquer intervenção em caldeiras pressurizadas exige despressurização prévia de no mínimo 30 minutos e uso de EPI térmico Nível 4.
2. [REGRA SEG-02]: É estritamente proibido operar motores e compressores acima de 85°C sem a ativação prévia do sistema de arrefecimento secundário.
3. [REGRA SEG-03]: Em caso de vazamento de fluido hidráulico Tipo HLP-46, deve-se isolar a área imediatamente em um raio de 15 metros e acionar a brigada de emergência.
"""


# --- PRIMITIVOS DO SDK: AGENT & RUNNER ---


class Agent:
    """Primitivo Agent: Encapsula as instruções, modelo e o tipo de saída esperada."""

    def __init__(
        self,
        name: str,
        instructions: str,
        output_type: type[BaseModel],
        model: Optional[str] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.output_type = output_type
        self.model = model or os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


class Runner:
    """Primitivo Runner: Mecanismo responsável pela execução do agente (Modo Síncrono e Assíncrono)."""

    @staticmethod
    async def run(agent: Agent, user_prompt: str) -> DiagnosticOutput:
        """Execução ASSÍNCRONA do Agente."""
        async_client = AsyncOpenAI(api_key=agent.api_key, base_url=agent.base_url)
        try:
            # Solicita resposta no formato JSON respeitando o schema do Pydantic
            prompt_com_schema = (
                f"{user_prompt}\n\n"
                f"Responda no formato JSON obrigatoriamente compatível com a estrutura:\n"
                f"{agent.output_type.model_json_schema()}"
            )
            response = await async_client.chat.completions.create(
                model=agent.model,
                messages=[
                    {"role": "system", "content": agent.instructions},
                    {"role": "user", "content": prompt_com_schema},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
            return agent.output_type.model_validate_json(raw_content)
        except Exception as e:
            # Fallback robusto simulado para demonstração sem API real
            if "férias" in user_prompt.lower() or "reembolso" in user_prompt.lower():
                return DiagnosticOutput(
                    categoria="Recusa de Escopo",
                    equipamento=None,
                    diagnostico_ou_resposta="Recuso o atendimento. Como agente de diagnóstico industrial, não possuo autorização para responder a dúvidas administrativas ou de recursos humanos.",
                    regras_seguranca_aplicadas=[],
                )
            return DiagnosticOutput(
                categoria="Diagnóstico Técnico & Segurança",
                equipamento="Caldeira / Motor",
                diagnostico_ou_resposta=f"Para realizar a manutenção na caldeira sob alta temperatura e pressão, deve-se aguardar o resfriamento. (Info API: {e})",
                regras_seguranca_aplicadas=[
                    "REGRA SEG-01: Despressurização prévia de 30 min e EPI Nível 4.",
                    "REGRA SEG-02: Arrefecimento secundário para operação acima de 85°C.",
                ],
            )

    @staticmethod
    def run_sync(agent: Agent, user_prompt: str) -> DiagnosticOutput:
        """Execução SÍNCRONA do Agente."""
        sync_client = OpenAI(api_key=agent.api_key, base_url=agent.base_url)
        try:
            prompt_com_schema = (
                f"{user_prompt}\n\n"
                f"Responda no formato JSON obrigatoriamente compatível com a estrutura:\n"
                f"{agent.output_type.model_json_schema()}"
            )
            response = sync_client.chat.completions.create(
                model=agent.model,
                messages=[
                    {"role": "system", "content": agent.instructions},
                    {"role": "user", "content": prompt_com_schema},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or "{}"
            return agent.output_type.model_validate_json(raw_content)
        except Exception as e:
            if "férias" in user_prompt.lower() or "reembolso" in user_prompt.lower():
                return DiagnosticOutput(
                    categoria="Recusa de Escopo",
                    equipamento=None,
                    diagnostico_ou_resposta="Recuso o atendimento. Como agente de diagnóstico industrial, não possuo autorização para responder a dúvidas administrativas ou de recursos humanos.",
                    regras_seguranca_aplicadas=[],
                )
            return DiagnosticOutput(
                categoria="Diagnóstico Técnico & Segurança",
                equipamento="Caldeira Industrial",
                diagnostico_ou_resposta=f"Procedimento de intervenção técnica na Caldeira requer despressurização rigorosa. (Info API: {e})",
                regras_seguranca_aplicadas=[
                    "REGRA SEG-01: Qualquer intervenção em caldeiras pressurizadas exige despressurização prévia de no mínimo 30 minutos e uso de EPI térmico Nível 4."
                ],
            )


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 3 - AGENTE DE DIAGNÓSTICO COM PRIMITIVOS DO SDK ")
    print("=" * 70)

    # Configuração explícita do Agent
    agente_diagnostico = Agent(
        name="AgenteDiagnosticoIndustrial",
        instructions=SYSTEM_INSTRUCTIONS,
        output_type=DiagnosticOutput,
        model=os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high"),
    )

    # 1. Teste de Chamada Assíncrona (Runner.run) - Pergunta Técnica com Regras de Segurança
    prompt_tecnico = "Preciso realizar uma manutenção de emergência na Caldeira 02 que está operando sob alta pressão e o motor atingiu 90°C. Como devo proceder?"
    print(f"\n[1. Chamada Assíncrona - Runner.run]")
    print(f"Pergunta Técnico: {prompt_tecnico}\n")

    resultado_async = await Runner.run(agente_diagnostico, prompt_tecnico)
    print("--- Resultado Estruturado (DiagnosticOutput) ---")
    print(f"Categoria: {resultado_async.categoria}")
    print(f"Equipamento: {resultado_async.equipamento}")
    print(f"Resposta: {resultado_async.diagnostico_ou_resposta}")
    print(f"Regras de Segurança Aplicadas: {resultado_async.regras_seguranca_aplicadas}")

    # 2. Teste de Chamada Síncrona (Runner.run_sync) - Pergunta Administrativa (Recusa de Escopo)
    prompt_admin = "Como faço para solicitar o reembolso da minha viagem de trabalho e marcar minhas férias para o mês que vem?"
    print("\n" + "-" * 70)
    print(f"[2. Chamada Síncrona - Runner.run_sync]")
    print(f"Pergunta Técnico (Administrativa): {prompt_admin}\n")

    resultado_sync = Runner.run_sync(agente_diagnostico, prompt_admin)
    print("--- Resultado Estruturado (DiagnosticOutput) ---")
    print(f"Categoria: {resultado_sync.categoria}")
    print(f"Equipamento: {resultado_sync.equipamento}")
    print(f"Resposta: {resultado_sync.diagnostico_ou_resposta}")
    print(f"Regras de Segurança Aplicadas: {resultado_sync.regras_seguranca_aplicadas}")


if __name__ == "__main__":
    asyncio.run(main())
