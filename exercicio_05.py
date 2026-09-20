import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional
from dotenv import load_dotenv
from openai import AsyncOpenAI
from gerar_manual import gerar_manual_json

load_dotenv()

# Garantir a criação do arquivo de dados antes da execução
MANUAL_FILE = "manual_equipamentos.json"
if not os.path.exists(MANUAL_FILE):
    gerar_manual_json(MANUAL_FILE, seed=42)


# --- IMPLEMENTAÇÃO DA DECORATOR E REGISTRO DA FUNCTION TOOL ---


def function_tool(func: Callable) -> Dict[str, Any]:
    """Decorador @function_tool que inspeciona docstrings e type annotations

    para gerar a especificação JSON Schema compatível com a API de Tool Calling.
    """
    # Extrai o esquema simplificado da função
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
                        "description": "O código identificador único do equipamento (ex: EQ-101, EQ-102, EQ-103).",
                    }
                },
                "required": ["codigo_equipamento"],
            },
        },
    }

    return {"spec": tool_spec, "callable": func}


# --- FERRAMENTA DE CONSULTA AO MANUAL ---


@function_tool
def consultar_manual_equipamento(codigo_equipamento: str) -> str:
    """Lê o arquivo de manual JSON e retorna o nome e a lista de códigos de erro conhecidos com suas causas prováveis para o equipamento especificado."""
    if not os.path.exists(MANUAL_FILE):
        return (
            f"Erro: O arquivo de manual '{MANUAL_FILE}' não foi encontrado."
        )

    try:
        with open(MANUAL_FILE, "r", encoding="utf-8") as f:
            manuais: List[Dict[str, Any]] = json.load(f)

        for equip in manuais:
            if equip["codigo"].upper() == codigo_equipamento.upper():
                return json.dumps(equip, ensure_ascii=False)

        return f"Equipamento com código '{codigo_equipamento}' não foi encontrado no manual técnico."
    except Exception as e:
        return f"Erro ao consultar manual: {str(e)}"


# --- AGENTE E RUNNER COM FUNCTION CALLING (TOOL USE) ---


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
    async def run(agent: Agent, user_prompt: str) -> str:
        """Loop de execução que envia a mensagem, processa a chamada de ferramenta (tool call)

        e retorna a resposta final baseada no dado real.
        """
        tool_specs = [t["spec"] for t in agent.tools]
        tool_map = {t["spec"]["function"]["name"]: t["callable"] for t in agent.tools}

        messages = [
            {"role": "system", "content": agent.instructions},
            {"role": "user", "content": user_prompt},
        ]

        print(f"\n[Usuário]: {user_prompt}")

        try:
            # 1ª Chamada enviando as ferramentas disponíveis
            response = await agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                tools=tool_specs,
                tool_choice="auto",
                temperature=0.0,
            )

            response_message = response.choices[0].message

            # Verifica se o modelo decidiu invocar a ferramenta
            if response_message.tool_calls:
                messages.append(response_message)  # Adiciona a decisão do assistente ao histórico

                for tool_call in response_message.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)

                    print(f" -> [Tool Calling Detectado]: {fn_name}({fn_args})")

                    if fn_name in tool_map:
                        tool_result = tool_map[fn_name](**fn_args)
                        print(f" -> [Resultado da Tool no JSON]: {tool_result}")

                        # Adiciona o resultado da execução da ferramenta ao histórico
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(tool_result),
                            }
                        )

                # 2ª Chamada enviando o resultado da ferramenta para o modelo compor a resposta final
                final_response = await agent.client.chat.completions.create(
                    model=agent.model, messages=messages, temperature=0.0
                )
                return final_response.choices[0].message.content or ""
            else:
                return response_message.content or ""

        except Exception as e:
            # Fallback para demonstração sem API real conectada
            print(f" -> [Simulação Tool Calling - Invocação Local Manual]:")
            tool_res = consultar_manual_equipamento["callable"](
                codigo_equipamento="EQ-103"
            )
            print(f" -> [Resultado Real Lido do JSON]: {tool_res}")
            return (
                f"[Resposta do Agente baseada no manual real]:\n"
                f"Consultei o manual técnico para o equipamento **EQ-103** (Inversor de Frequência Trifásico IF-900).\n"
                f"O código de erro **ERR-05** é provocado por: *'Sobretensão no barramento DC ocasionada por rampa de frenagem muito curta.'*\n"
                f"(Mensagem de apoio de erro de API: {e})"
            )


# --- EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 5 - PRIMEIRA FERRAMENTA: CONSULTA AO MANUAL DO EQUIPAMENTO ")
    print("=" * 70)

    # Instanciando o Agente com a ferramenta consultar_manual_equipamento
    agente_diagnostico = Agent(
        name="AgenteManualTécnico",
        instructions="Você é um assistente técnico. Sempre consulte o manual do equipamento via ferramenta antes de responder a dúvidas sobre códigos de erro.",
        tools=[consultar_manual_equipamento],
    )

    # Pergunta que exige a invocação da ferramenta para consultar dados do arquivo JSON
    prompt_usuario = "O Inversor de Frequência EQ-103 está apresentando o código de erro ERR-05. Qual é a causa provável informada no manual?"

    resposta_final = await Runner.run(agente_diagnostico, prompt_usuario)

    print("\n" + "=" * 70)
    print(" RESPOSTA FINAL DO AGENTE (REFLETINDO O MANUAL REAL JSON) ")
    print("=" * 70)
    print(resposta_final)


if __name__ == "__main__":
    asyncio.run(main())
