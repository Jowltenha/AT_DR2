import asyncio
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

# --- DATACLASSES E WRAPPERS (SIMULANDO SDK PRIMITIVES: ModelSettings, RunContextWrapper, OpenAIChatCompletionsModel) ---


class ModelSettings:
    """Configurações personalizadas de modelo (temperature, max_tokens, etc.)."""

    def __init__(self, temperature: float = 0.2, max_tokens: int = 500):
        self.temperature = temperature
        self.max_tokens = max_tokens


class RunContextWrapper:
    """Injeta informações de contexto de execução (ex: filial_id) sem expor no prompt do usuário,

    e rastreia métricas de uso de tokens.
    """

    def __init__(self, filial_id: str):
        self.filial_id = filial_id
        self.usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def update_usage(
        self, prompt_tokens: int, completion_tokens: int, total_tokens: int
    ):
        self.usage["prompt_tokens"] += prompt_tokens
        self.usage["completion_tokens"] += completion_tokens
        self.usage["total_tokens"] += total_tokens


class OpenAIChatCompletionsModel:
    """Provedor de modelo customizado/compatível com a API OpenAI (para filiais com provedores alternativos/proxies)."""

    def __init__(self, model_name: str, api_key: str, base_url: str):
        self.model_name = model_name
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)


class Agent:
    """Primitivo Agent com suporte a modelo customizado, configurações de modelo e ferramentas."""

    def __init__(
        self,
        name: str,
        instructions: str,
        model_provider: OpenAIChatCompletionsModel,
        model_settings: Optional[ModelSettings] = None,
    ):
        self.name = name
        self.instructions = instructions
        self.model_provider = model_provider
        self.model_settings = model_settings or ModelSettings()


# --- TOOL DE TESTE QUE USA O CONTEXTO DA FILIAL ---


def consultar_manual_tool(
    context_wrapper: RunContextWrapper, termo: str
) -> str:
    """Tool que recebe o identificador da filial via RunContextWrapper sem depender de menção no prompt."""
    return f"[TOOL consultar_manual] Filial '{context_wrapper.filial_id}': Registro encontrado para '{termo}'. Procedimento autorizado conforme norma local."


# --- RUNNER COM SUPORTE A RUN_STREAMED E MONITORAMENTO ---


class Runner:
    @staticmethod
    async def run(
        agent: Agent,
        user_prompt: str,
        context_wrapper: Optional[RunContextWrapper] = None,
    ) -> str:
        """Execução padrão do agente."""
        messages = [
            {"role": "system", "content": agent.instructions},
            {"role": "user", "content": user_prompt},
        ]
        try:
            resp = await agent.model_provider.client.chat.completions.create(
                model=agent.model_provider.model_name,
                messages=messages,
                temperature=agent.model_settings.temperature,
                max_tokens=agent.model_settings.max_tokens,
            )
            content = resp.choices[0].message.content or ""
            if resp.usage and context_wrapper:
                context_wrapper.update_usage(
                    resp.usage.prompt_tokens,
                    resp.usage.completion_tokens,
                    resp.usage.total_tokens,
                )
            return content
        except Exception as e:
            # Fallback para demonstração técnica caso API offline
            if context_wrapper:
                context_wrapper.update_usage(35, 65, 100)
            return f"[Simulação {agent.name}]: Análise efetuada com sucesso. (API info: {e})"

    @staticmethod
    async def run_streamed(
        agent: Agent,
        user_prompt: str,
        context_wrapper: Optional[RunContextWrapper] = None,
    ) -> AsyncGenerator[str, None]:
        """Execução em modo Streaming (token a token)."""
        messages = [
            {"role": "system", "content": agent.instructions},
            {"role": "user", "content": user_prompt},
        ]
        try:
            stream = await agent.model_provider.client.chat.completions.create(
                model=agent.model_provider.model_name,
                messages=messages,
                temperature=agent.model_settings.temperature,
                max_tokens=agent.model_settings.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        yield delta
                if chunk.usage and context_wrapper:
                    context_wrapper.update_usage(
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                        chunk.usage.total_tokens,
                    )
        except Exception as e:
            # Emulação de streaming para demonstração sem API ativa
            simulated_tokens = [
                "[Simulação Streaming]: ",
                "Iniciando ",
                "diagnóstico ",
                "complexo ",
                "para ",
                "o ",
                "equipamento. ",
                "Análise ",
                "concluída ",
                "com ",
                "sucesso. ",
                f"(Info: {e})",
            ]
            for tok in simulated_tokens:
                await asyncio.sleep(0.05)
                yield tok
            if context_wrapper and context_wrapper.usage["total_tokens"] == 0:
                context_wrapper.update_usage(45, 75, 120)


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 4 - SELEÇÃO DE MODELO, STREAMING E MONITORAMENTO ")
    print("=" * 70)

    api_key = os.getenv("OPENAI_API_KEY", "mock-key")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")

    # Provedor do Modelo (OpenAIChatCompletionsModel) para compatibilidade
    provider_padrao = OpenAIChatCompletionsModel(
        model_name=model_name, api_key=api_key, base_url=base_url
    )
    provider_alternativo_filial = OpenAIChatCompletionsModel(
        model_name="gpt-4o-mini", api_key=api_key, base_url=base_url
    )

    # 1. Configuração dos Agentes
    # Agente de Triagem (Leve/Barato)
    agente_triagem = Agent(
        name="AgenteTriagem",
        instructions="Classifique o chamado em uma frase: Baixa, Média ou Alta prioridade.",
        model_provider=provider_alternativo_filial,
        model_settings=ModelSettings(temperature=0.0, max_tokens=60),
    )

    # Agente de Diagnóstico Complexo (Mais robusto, ModelSettings customizados)
    agente_diagnostico_complexo = Agent(
        name="AgenteDiagnosticoComplexo",
        instructions="Você é um especialista em diagnóstico avançado de manuais industriais.",
        model_provider=provider_padrao,
        model_settings=ModelSettings(temperature=0.1, max_tokens=300),
    )

    # 2. Teste da Tool com RunContextWrapper (Injeção de Filial)
    contexto_filial_07 = RunContextWrapper(filial_id="FILIAL-SP-07")
    print(
        f"\n[1. Injeção de Contexto sem expor no prompt - Filial: {contexto_filial_07.filial_id}]"
    )
    resultado_tool = consultar_manual_tool(contexto_filial_07, "Bomba Válvula X")
    print(resultado_tool)

    # 3. Execução em Streaming (Runner.run_streamed) com Medição de Tempo e Tokens
    prompt_diagnostico = "O gerador principal apresentou vibração excessiva a 3000 RPM após a substituição do mancal. Analise os procedimentos."
    print(
        f"\n[2. Execução com Streaming (Runner.run_streamed) & ModelSettings(temp=0.1, max_tokens=300)]"
    )
    print(f"Pergunta: {prompt_diagnostico}")
    print("Resposta recebida token a token: ", end="", flush=True)

    start_time = time.time()
    full_response = ""

    # Consumo do streaming via async for
    async for chunk in Runner.run_streamed(
        agente_diagnostico_complexo,
        prompt_diagnostico,
        context_wrapper=contexto_filial_07,
    ):
        print(chunk, end="", flush=True)
        full_response += chunk

    execution_time = round(time.time() - start_time, 3)
    print("\n")

    # 4. Estruturação do Dicionário de Métricas para GET /agent/status/{task_id}
    status_metrics: Dict[str, Any] = {
        "task_id": "task-diag-88492-sf",
        "status": "done",
        "filial_id": contexto_filial_07.filial_id,
        "modelo_utilizado": agente_diagnostico_complexo.model_provider.model_name,
        "tempo_resposta_segundos": execution_time,
        "tokens_consumidos": contexto_filial_07.usage,
        "model_settings_aplicados": {
            "temperature": agente_diagnostico_complexo.model_settings.temperature,
            "max_tokens": agente_diagnostico_complexo.model_settings.max_tokens,
        },
    }

    print("=" * 70)
    print(" DICIONÁRIO DE MÉTRICAS REGISTRADO (Futuro Endpoint REST GET /agent/status/{task_id}) ")
    print("=" * 70)
    print(json.dumps(status_metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
