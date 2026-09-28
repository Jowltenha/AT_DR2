import asyncio
import json
import os
import time
from typing import Any, Dict
from dotenv import load_dotenv
from agents import Agent, Runner, ModelSettings

load_dotenv()


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 4 - SELEÇÃO DE MODELO, STREAMING E MONITORAMENTO (SDK) ")
    print("=" * 70)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    # 1. Configuração dos Agentes com Primitivos do SDK
    agente_triagem = Agent(
        name="AgenteTriagem",
        instructions="Classifique o chamado em uma frase: Baixa, Média ou Alta prioridade.",
        model="gpt-4o-mini",
        model_settings=ModelSettings(temperature=0.0, max_tokens=150),
    )

    agente_diagnostico_complexo = Agent(
        name="AgenteDiagnosticoComplexo",
        instructions="Você é um especialista em diagnóstico avançado de manuais industriais. Seja direto e objetivo.",
        model=model_name,
        model_settings=ModelSettings(temperature=0.1, max_tokens=600),
    )

    # 2. Rastreamento de Filial sem expor no prompt do usuário
    filial_id = "FILIAL-SP-07"
    print(f"\n[1. Rastreamento de Contexto - Filial: {filial_id}]")

    # 3. Execução com Streaming (Runner.run_streamed)
    prompt_diagnostico = "O gerador principal apresentou vibração excessiva a 3000 RPM após a substituição do mancal. Analise os procedimentos."
    print(
        f"\n[2. Execução com Streaming (Runner.run_streamed) & ModelSettings(temp=0.1, max_tokens=600)]"
    )
    print(f"Pergunta: {prompt_diagnostico}")
    print("Resposta recebida token a token: ", end="", flush=True)

    start_time = time.time()
    full_response = ""

    # Consumo do streaming do SDK via result_stream.stream_events()
    result_stream = Runner.run_streamed(
        agente_diagnostico_complexo,
        prompt_diagnostico,
    )

    async for event in result_stream.stream_events():
        if event.type == "raw_response_event":
            if hasattr(event.data, "delta") and event.data.delta:
                print(event.data.delta, end="", flush=True)
                full_response += event.data.delta

    execution_time = round(time.time() - start_time, 3)
    print("\n")

    # 4. Estruturação do Dicionário de Métricas para Monitoramento
    status_metrics: Dict[str, Any] = {
        "task_id": "task-diag-88492-sf",
        "status": "done",
        "filial_id": filial_id,
        "modelo_utilizado": model_name,
        "tempo_resposta_segundos": execution_time,
        "model_settings_aplicados": {
            "temperature": 0.1,
            "max_tokens": 600,
        },
    }

    print("=" * 70)
    print(" DICIONÁRIO DE MÉTRICAS REGISTRADO (Futuro Endpoint REST GET /agent/status/{task_id}) ")
    print("=" * 70)
    print(json.dumps(status_metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
