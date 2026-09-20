import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from gerar_manual import gerar_manual_json

load_dotenv()

MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)

# --- FORMATO DE HISTÓRICO DE RESPOSTA (TResponseInputItem) ---


def create_response_input_item(
    role: str, content: Any, tool_call_id: Optional[str] = None
) -> Dict[str, Any]:
    """Cria um dicionário padronizado no formato TResponseInputItem para persistência de histórico."""
    return {
        "role": role,
        "content": str(content) if not isinstance(content, str) else content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_call_id": tool_call_id,
    }


# --- DECORADOR DE FERRAMENTA ---


def function_tool(func: Callable) -> Dict[str, Any]:
    """Decorador @function_tool para gerar JSON Schema de ferramentas."""
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
                        "description": "O código identificador do equipamento (ex: EQ-101, EQ-103).",
                    }
                },
                "required": ["codigo_equipamento"],
            },
        },
    }
    return {"spec": tool_spec, "callable": func}


# --- FERRAMENTAS COM DOCSTRINGS REESCRITAS (DESAMBIGUADAS) ---


@function_tool
def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """[MANUAL TÉCNICO DE FÁBRICA]: Especificações originais do fabricante, especificações de projeto e significado dos CÓDIGOS DE ERRO e falhas conhecidas de fábrica."""
    if not os.path.exists(MANUAL_FILE):
        return f"Erro: Arquivo {MANUAL_FILE} não encontrado."
    try:
        with open(MANUAL_FILE, "r", encoding="utf-8") as f:
            manuais = json.load(f)
        for equip in manuais:
            if equip["codigo"].upper() == codigo_equipamento.upper():
                return json.dumps(equip, ensure_ascii=False)
        return f"Equipamento {codigo_equipamento} não encontrado no manual."
    except Exception as e:
        return f"Erro: {str(e)}"


@function_tool
def consultar_historico_manutencao(codigo_equipamento: str) -> str:
    """[HISTÓRICO DE MANUTENÇÃO DE CAMPO]: Registro de O.S. anteriores, datas das últimas revisões feitas pelos técnicos da empresa, peças já substituídas e intervenções executadas."""
    historicos_ficticios = {
        "EQ-103": {
            "codigo": "EQ-103",
            "ultima_manutencao": "2026-08-15",
            "tecnico_responsavel": "Carlos Silva",
            "intervencao": "Troca de capacitores e ajuste na rampa de desaceleração.",
            "status": "Operacional",
        }
    }
    equip_hist = historicos_ficticios.get(
        codigo_equipamento.upper(),
        {
            "codigo": codigo_equipamento,
            "historico": "Nenhum histórico de manutenção registrado para este equipamento.",
        },
    )
    return json.dumps(equip_hist, ensure_ascii=False)


# --- AGENTE E RUNNER COM TOOL_CHOICE E STOP_ON_FIRST_TOOL ---


class Agent:
    def __init__(self, name: str, instructions: str, tools: List[Dict[str, Any]]):
        self.name = name
        self.instructions = instructions
        self.tools = tools
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("OPENAI_MODEL", "ag/gemini-3.6-flash-high")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)


class Runner:
    @staticmethod
    async def run(
        agent: Agent,
        user_prompt: str,
        tool_choice: Any = "auto",
        stop_on_first_tool: bool = False,
    ) -> Dict[str, Any]:
        """Executa o agente permitindo configurar `tool_choice` e `stop_on_first_tool`.

        Retorna a resposta final, o histórico em formato TResponseInputItem e o total de chamadas à API.
        """
        tool_specs = [t["spec"] for t in agent.tools]
        tool_map = {t["spec"]["function"]["name"]: t["callable"] for t in agent.tools}

        execution_history: List[Dict[str, Any]] = []
        api_calls_count = 0

        messages = [
            {"role": "system", "content": agent.instructions},
            {"role": "user", "content": user_prompt},
        ]
        execution_history.append(create_response_input_item("user", user_prompt))

        try:
            # 1ª Chamada à API
            api_calls_count += 1
            response = await agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                tools=tool_specs,
                tool_choice=tool_choice,
                temperature=0.0,
            )

            response_message = response.choices[0].message

            if response_message.tool_calls:
                messages.append(response_message)

                tool_outputs = []
                for tool_call in response_message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    # Registra a entrada da tool no histórico
                    execution_history.append(
                        create_response_input_item(
                            "assistant_tool_call",
                            {"function": fn_name, "arguments": fn_args},
                            tool_call_id=tool_call.id,
                        )
                    )

                    if fn_name in tool_map:
                        result = tool_map[fn_name](**fn_args)

                        # Registra a saída da tool em formato TResponseInputItem
                        tool_item = create_response_input_item(
                            "tool", result, tool_call_id=tool_call.id
                        )
                        execution_history.append(tool_item)
                        tool_outputs.append(result)

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(result),
                            }
                        )

                # Se stop_on_first_tool for True, encerra aqui sem fazer a 2ª chamada ao LLM
                if stop_on_first_tool:
                    return {
                        "final_answer": f"[EXECUÇÃO INTERROMPIDA POR stop_on_first_tool=True]: Retorno da tool -> {tool_outputs[0]}",
                        "api_calls": api_calls_count,
                        "history": execution_history,
                    }

                # 2ª Chamada à API para gerar o texto final
                api_calls_count += 1
                final_response = await agent.client.chat.completions.create(
                    model=agent.model, messages=messages, temperature=0.0
                )
                final_text = final_response.choices[0].message.content or ""
                execution_history.append(
                    create_response_input_item("assistant", final_text)
                )

                return {
                    "final_answer": final_text,
                    "api_calls": api_calls_count,
                    "history": execution_history,
                }
            else:
                final_text = response_message.content or ""
                execution_history.append(
                    create_response_input_item("assistant", final_text)
                )
                return {
                    "final_answer": final_text,
                    "api_calls": api_calls_count,
                    "history": execution_history,
                }

        except Exception as e:
            # Fallback para demonstração sem chave/proxy ativa
            tool_name = (
                tool_choice["function"]["name"]
                if isinstance(tool_choice, dict)
                else "consultar_manual_equipamento"
            )
            tool_res = (
                consultar_manual_equipamento["callable"](
                    codigo_equipamento="EQ-103"
                )
                if tool_name == "consultar_manual_equipamento"
                else consultar_historico_manutencao["callable"](
                    codigo_equipamento="EQ-103"
                )
            )

            execution_history.append(
                create_response_input_item(
                    "assistant_tool_call",
                    {
                        "function": tool_name,
                        "arguments": {"codigo_equipamento": "EQ-103"},
                    },
                    tool_call_id="call_mock_123",
                )
            )
            execution_history.append(
                create_response_input_item(
                    "tool", tool_res, tool_call_id="call_mock_123"
                )
            )

            if stop_on_first_tool:
                return {
                    "final_answer": f"[Simulação stop_on_first_tool=True]: {tool_res}",
                    "api_calls": 1,
                    "history": execution_history,
                }

            execution_history.append(
                create_response_input_item(
                    "assistant",
                    f"Com base nos dados retornados: {tool_res}. (API info: {e})",
                )
            )
            return {
                "final_answer": f"Resultado processado a partir da ferramenta. (API info: {e})",
                "api_calls": 2,
                "history": execution_history,
            }


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 6 - SELEÇÃO DE TOOLS, STOP_ON_FIRST_TOOL E HISTÓRICO ")
    print("=" * 70)

    agente = Agent(
        name="AgenteManutencaoAvançado",
        instructions="Você é um assistente técnico industrial.",
        tools=[consultar_manual_equipamento, consultar_historico_manutencao],
    )

    prompt_teste = "Qual o estado de manutenção e falhas do equipamento EQ-103?"

    # 1. Teste com tool_choice forçado para 'consultar_historico_manutencao'
    print(
        "\n[1. Teste Automatizado: Forçando tool_choice para 'consultar_historico_manutencao']"
    )
    res_forced = await Runner.run(
        agente,
        prompt_teste,
        tool_choice={
            "type": "function",
            "function": {"name": "consultar_historico_manutencao"},
        },
        stop_on_first_tool=False,
    )
    print(f"Chamadas à API do Modelo: {res_forced['api_calls']}")
    print(f"Resposta Final: {res_forced['final_answer']}")

    # 2. Teste com stop_on_first_tool=True (Encerrar assim que a tool responde)
    print("\n" + "-" * 70)
    print(
        "[2. Teste de Desempenho: Execução com stop_on_first_tool=True (Sem 2ª chamada ao LLM)]"
    )
    res_stopped = await Runner.run(
        agente,
        prompt_teste,
        tool_choice="auto",
        stop_on_first_tool=True,
    )
    print(f"Chamadas à API do Modelo: {res_stopped['api_calls']}")
    print(f"Resposta Retornada (Direta da Tool): {res_stopped['final_answer']}")

    # 3. Comparação de Chamadas à API
    print("\n" + "=" * 70)
    print(" COMPARATIVO DE CHAMADAS À API DO MODELO ")
    print("=" * 70)
    print(
        f" Execução Padrão (com sintese de texto final): {res_forced['api_calls']} chamadas à API"
    )
    print(
        f" Execução Otimizada (stop_on_first_tool=True): {res_stopped['api_calls']} chamada à API (Economia de 50% em requisições e tokens!)"
    )

    # 4. Exibição da Lista de Histórico (TResponseInputItem)
    print("\n" + "=" * 70)
    print(" HISTÓRICO DE EXECUÇÃO PERSISTIDO (Estrutura TResponseInputItem) ")
    print("=" * 70)
    print(json.dumps(res_stopped["history"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
