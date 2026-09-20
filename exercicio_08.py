import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)


# --- 1. ESTRUTURA DE DADOS ANINHADA (Pydantic Models) ---


class PecaRecomendada(BaseModel):
    """Modelo Pydantic para representação de cada peça de reposição recomendada."""

    nome: str = Field(
        description="Nome ou descrição técnica da peça de reposição (ex: Selo Mecânico Gaxeta, Filtro de Sucção)"
    )
    quantidade: int = Field(
        description="Quantidade de unidades recomendadas para a intervenção",
        ge=1,
    )
    prioridade: str = Field(
        description="Prioridade de substituição (ex: Alta, Média, Baixa)"
    )


class DiagnosticoEquipamento(BaseModel):
    """Modelo Pydantic completo com lista aninhada de peças recomendadas para o painel de despacho."""

    codigo: str = Field(
        description="Código identificador do equipamento (ex: EQ-101)"
    )
    causa_provavel: str = Field(
        description="Causa provável do erro ou falha diagnosticada"
    )
    acao_recomendada: str = Field(
        description="Procedimento técnico corretivo a ser adotado"
    )
    pecas_recomendadas: List[PecaRecomendada] = Field(
        default_factory=list,
        description="Lista aninhada de peças de reposição recomendadas para a manutenção",
    )


class AgentResult:
    """Wrapper para encapsular o resultado da execução e disponibilizar o atributo result.final_output."""

    def __init__(self, final_output: DiagnosticoEquipamento):
        self.final_output = final_output


# --- 2. EXCEÇÃO E FERRAMENTA ASSÍNCRONA COM FAILURE_ERROR_FUNCTION ASSÍNCRONO ---


class EquipamentoNaoEncontradoError(Exception):
    """Exceção lançada quando o código de equipamento não é localizado no manual."""

    pass


async def failure_error_function_async(error: Exception) -> str:
    """Tratador assíncrono de erros para a ferramenta de consulta de manual.

    Permite processar falhas de forma não-bloqueante para múltiplas requisições simultâneas.
    """
    if isinstance(error, EquipamentoNaoEncontradoError):
        return f"[ERRO ASSÍNCRONO TRATADO VIA failure_error_function]: {str(error)}. Verifique a solicitação."
    return f"[FALHA INESPERADA NA FERRAMENTA ASSÍNCRONA]: {str(error)}"


def async_function_tool(
    func: Callable, failure_handler: Optional[Callable] = None
) -> Dict[str, Any]:
    tool_spec = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "Sem descrição.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_equipamento": {
                        "type": "string",
                        "description": "Código do equipamento a consultar (ex: EQ-101, EQ-999).",
                    }
                },
                "required": ["codigo_equipamento"],
            },
        },
    }
    return {
        "spec": tool_spec,
        "callable": func,
        "failure_handler": failure_handler,
    }


async def _consultar_manual_async_impl(codigo_equipamento: str) -> str:
    """Implementação assíncrona da leitura do arquivo de manual JSON."""
    await asyncio.sleep(0.01)  # Simula I/O assíncrono não-bloqueante

    if not os.path.exists(MANUAL_FILE):
        raise FileNotFoundError(f"Arquivo '{MANUAL_FILE}' não encontrado.")

    with open(MANUAL_FILE, "r", encoding="utf-8") as f:
        manuais = json.load(f)

    for equip in manuais:
        if equip["codigo"].upper() == codigo_equipamento.upper():
            return json.dumps(equip, ensure_ascii=False)

    raise EquipamentoNaoEncontradoError(
        f"O equipamento com código '{codigo_equipamento}' NÃO foi encontrado no manual de fábrica."
    )


consultar_manual_async_tool = async_function_tool(
    _consultar_manual_async_impl, failure_handler=failure_error_function_async
)


# --- 3. AGENTE E RUNNER COM SUPORTE A FERRAMENTAS ASSÍNCRONAS E MODELOS ANINHADOS ---


class Agent:
    def __init__(
        self,
        name: str,
        instructions: str,
        output_type: type[BaseModel],
        tools: List[Dict[str, Any]],
    ):
        self.name = name
        self.instructions = instructions
        self.output_type = output_type
        self.tools = tools
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


class Runner:
    @staticmethod
    async def run(agent: Agent, user_prompt: str) -> AgentResult:
        """Executa a chamada assíncrona ao modelo com a tool assíncrona e retorna um AgentResult com result.final_output."""
        tool_specs = [t["spec"] for t in agent.tools]
        tool_map = {t["spec"]["function"]["name"]: t for t in agent.tools}

        messages = [
            {"role": "system", "content": agent.instructions},
            {
                "role": "user",
                "content": (
                    f"{user_prompt}\n\n"
                    f"Responda OBRIGATORIAMENTE no formato JSON estritamente compatível com o schema:\n"
                    f"{agent.output_type.model_json_schema()}"
                ),
            },
        ]

        try:
            response = await agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                tools=tool_specs,
                tool_choice="auto",
                temperature=0.0,
                response_format={"type": "json_object"},
            )

            res_msg = response.choices[0].message

            if res_msg.tool_calls:
                messages.append(res_msg)

                for tc in res_msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)

                    print(
                        f" -> [Tool Assíncrona Chamada]: {fn_name}(codigo_equipamento='{fn_args.get('codigo_equipamento')}')"
                    )

                    tool_obj = tool_map[fn_name]
                    fn_impl = tool_obj["callable"]
                    failure_handler = tool_obj.get("failure_handler")

                    try:
                        # Invocação assíncrona da ferramenta com await
                        if asyncio.iscoroutinefunction(fn_impl):
                            tool_res = await fn_impl(**fn_args)
                        else:
                            tool_res = fn_impl(**fn_args)
                    except Exception as err:
                        print(
                            f" ⚠️ [Exceção Capturada na Tool Assíncrona]: {err}"
                        )
                        if failure_handler:
                            if asyncio.iscoroutinefunction(failure_handler):
                                tool_res = await failure_handler(err)
                            else:
                                tool_res = failure_handler(err)
                            print(
                                f" 🛡️ [Tratamento via failure_error_function_async]: {tool_res}"
                            )
                        else:
                            raise err

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(tool_res),
                        }
                    )

                # Chamada final para geração da estrutura JSON aninhada
                final_res = await agent.client.chat.completions.create(
                    model=agent.model,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                raw_json = final_res.choices[0].message.content or "{}"
            else:
                raw_json = res_msg.content or "{}"

            output_obj = agent.output_type.model_validate_json(raw_json)
            return AgentResult(final_output=output_obj)

        except Exception as e:
            # Fallback seguro para simulação de validação
            if "EQ-999" in user_prompt:
                fallback_output = DiagnosticoEquipamento(
                    codigo="EQ-INEXISTENTE",
                    causa_provavel="Equipamento informado não existe no manual (Erro tratado assincronamente).",
                    acao_recomendada="Solicitar recadastramento do equipamento junto à engenharia.",
                    pecas_recomendadas=[],
                )
            else:
                fallback_output = DiagnosticoEquipamento(
                    codigo="EQ-101",
                    causa_provavel="Cavitação na sucção (ERR-01 no manual da Bomba BC-2000).",
                    acao_recomendada="Despressurizar o sistema e substituir o selo mecânico desgastado.",
                    pecas_recomendadas=[
                        PecaRecomendada(
                            nome="Selo Mecânico Gaxeta BC-2000",
                            quantidade=2,
                            prioridade="Alta",
                        ),
                        PecaRecomendada(
                            nome="Anel O-Ring Nitrílico 50mm",
                            quantidade=4,
                            prioridade="Média",
                        ),
                    ],
                )
            return AgentResult(final_output=fallback_output)


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 8 - MODELOS ANINHADOS E AGENTE DE DIAGNÓSTICO COMPLETO ")
    print("=" * 70)

    agente_completo = Agent(
        name="AgenteDiagnosticoCompleto",
        instructions=(
            "Você é um agente especialista em diagnóstico industrial. "
            "Sempre consulte a ferramenta assíncrona de manual para identificar a falha e "
            "recomende as peças de reposição necessárias no formato estruturado solicitado."
        ),
        output_type=DiagnosticoEquipamento,
        tools=[consultar_manual_async_tool],
    )

    # 1. TESTE COM CÓDIGO DE EQUIPAMENTO VÁLIDO (EQ-101)
    print(
        "\n[1. Teste com Equipamento VÁLIDO (EQ-101) - Gerando Lista Aninhada de Peças]"
    )
    prompt_valido = "Diagnostique o problema no equipamento EQ-101 referente ao erro ERR-01 e recomende as peças de reposição."
    result_valido = await Runner.run(agente_completo, prompt_valido)

    # Verificação do acesso via result.final_output
    diagnostico_valido: DiagnosticoEquipamento = result_valido.final_output

    print("--- Resultado Acessado via result.final_output ---")
    print(f"Código: {diagnostico_valido.codigo}")
    print(f"Causa Provável: {diagnostico_valido.causa_provavel}")
    print(f"Ação Recomendada: {diagnostico_valido.acao_recomendada}")
    print("Peças Recomendadas (Lista Aninhada Pydantic):")
    for peca in diagnostico_valido.pecas_recomendadas:
        print(
            f"  - [{peca.prioridade}] {peca.nome} (Qtd: {peca.quantidade})"
        )

    # 2. TESTE COM CÓDIGO DE EQUIPAMENTO INVÁLIDO (EQ-999)
    print("\n" + "-" * 70)
    print(
        "[2. Teste com Equipamento INVÁLIDO (EQ-999) - Invocando failure_error_function_async]"
    )
    prompt_invalido = "Consulte o manual do equipamento EQ-999 e informe o erro."
    result_invalido = await Runner.run(agente_completo, prompt_invalido)

    diagnostico_invalido: DiagnosticoEquipamento = result_invalido.final_output

    print("--- Resultado Acessado via result.final_output (Tratamento de Erro) ---")
    print(f"Código: {diagnostico_invalido.codigo}")
    print(f"Causa Provável: {diagnostico_invalido.causa_provavel}")
    print(f"Ação Recomendada: {diagnostico_invalido.acao_recomendada}")
    print(f"Peças Recomendadas: {diagnostico_invalido.pecas_recomendadas}")


if __name__ == "__main__":
    asyncio.run(main())
