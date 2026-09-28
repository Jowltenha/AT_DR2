import asyncio
import os
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from agents import Agent, Runner

load_dotenv()


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


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 3 - AGENTE DE DIAGNÓSTICO COM PRIMITIVOS DO OPENAI AGENTS SDK ")
    print("=" * 70)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente_diagnostico = Agent(
        name="AgenteDiagnosticoIndustrial",
        instructions=SYSTEM_INSTRUCTIONS,
        output_type=DiagnosticOutput,
        model=model_name,
    )

    prompt_tecnico = "Preciso realizar uma manutenção de emergência na Caldeira 02 que está operando sob alta pressão e o motor atingiu 90°C. Como devo proceder?"
    print(f"\n[1. Chamada Assíncrona - Runner.run (Diagnóstico Técnico)]")
    print(f"Pergunta Técnico: {prompt_tecnico}\n")

    resultado_async = await Runner.run(agente_diagnostico, prompt_tecnico)
    out_async: DiagnosticOutput = resultado_async.final_output

    print("--- Resultado Estruturado (DiagnosticOutput) ---")
    print(f"Categoria: {out_async.categoria}")
    print(f"Equipamento: {out_async.equipamento}")
    print(f"Resposta: {out_async.diagnostico_ou_resposta}")
    print(f"Regras de Segurança Aplicadas: {out_async.regras_seguranca_aplicadas}")

    prompt_admin = "Como faço para solicitar o reembolso da minha viagem de trabalho e marcar minhas férias para o mês que vem?"
    print("\n" + "-" * 70)
    print(f"[2. Chamada de Validação de Escopo - Runner.run (Pergunta Administrativa)]")
    print(f"Pergunta Técnico (Administrativa): {prompt_admin}\n")

    resultado_admin = await Runner.run(agente_diagnostico, prompt_admin)
    out_admin: DiagnosticOutput = resultado_admin.final_output

    print("--- Resultado Estruturado (DiagnosticOutput) ---")
    print(f"Categoria: {out_admin.categoria}")
    print(f"Equipamento: {out_admin.equipamento}")
    print(f"Resposta: {out_admin.diagnostico_ou_resposta}")
    print(f"Regras de Segurança Aplicadas: {out_admin.regras_seguranca_aplicadas}")


if __name__ == "__main__":
    asyncio.run(main())
