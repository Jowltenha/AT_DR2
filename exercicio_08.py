import asyncio
import json
import os
from typing import List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool
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


# --- 2. EXCEÇÃO E FERRAMENTA ASSÍNCRONA COM FAILURE_ERROR_FUNCTION ASSÍNCRONO ---


class EquipamentoNaoEncontradoError(Exception):
    """Exceção lançada quando o código de equipamento não é localizado no manual."""

    pass


async def failure_error_function_async(ctx, error: Exception) -> str:
    """Tratador assíncrono de erros para a ferramenta de consulta de manual."""
    if isinstance(error, EquipamentoNaoEncontradoError):
        return f"[ERRO ASSÍNCRONO TRATADO VIA failure_error_function]: {str(error)}. Verifique a solicitação."
    return f"[FALHA INESPERADA NA FERRAMENTA ASSÍNCRONA]: {str(error)}"


@function_tool(failure_error_function=failure_error_function_async)
async def consultar_manual_async_tool(codigo_equipamento: str) -> str:
    """[MANUAL TÉCNICO DE FÁBRICA]: Consulta o manual técnico pelo código do equipamento (ex: 'EQ-101', 'EQ-102'). ATENÇÃO: Passe apenas o código do equipamento (ex: 'EQ-101'). Não passe códigos de erro como 'ERR-01'."""
    await asyncio.sleep(0.01)

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


# --- 3. EXECUÇÃO DEMONSTRATIVA ---


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 8 - MODELOS ANINHADOS E AGENTE DE DIAGNÓSTICO COMPLETO (SDK) ")
    print("=" * 70)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente_completo = Agent(
        name="AgenteDiagnosticoCompleto",
        instructions=(
            "Você é um agente especialista em diagnóstico industrial.\n"
            "1. Consulte a ferramenta 'consultar_manual_async_tool' UMA ÚNICA VEZ para buscar as especificações do equipamento.\n"
            "2. Preencha o relatório no formato DiagnosticoEquipamento. Caso o manual não especifique as peças exatas, infira e liste as peças recomendadas apropriadas (ex: Selo Mecânico, Filtro, Gaxeta).\n"
            "3. IMPORTANTE: Após a primeira consulta da ferramenta (ou em caso de erro da ferramenta), NÃO chame a ferramenta novamente e responda imediatamente gerando o resultado estruturado."
        ),
        output_type=DiagnosticoEquipamento,
        tools=[consultar_manual_async_tool],
        model=model_name,
    )

    # 1. TESTE COM CÓDIGO DE EQUIPAMENTO VÁLIDO (EQ-101)
    print(
        "\n[1. Teste com Equipamento VÁLIDO (EQ-101) - Gerando Lista Aninhada de Peças]"
    )
    prompt_valido = "Diagnostique o problema no equipamento EQ-101 referente ao erro ERR-01 e recomende as peças de reposição."
    result_valido = await Runner.run(agente_completo, prompt_valido)

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
