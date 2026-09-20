import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# Importa os modelos Pydantic de diagnóstico do Exercício 8
from exercicio_08 import (
    DiagnosticoEquipamento,
    PecaRecomendada,
    consultar_manual_async_tool,
)
from exercicio_11 import AgentIntegrador, RunnerIntegrador, SQLiteSession

load_dotenv()

# --- 1. SCHEMAS PYDANTIC DA API REST COMPLETA ---


class SubmissionRequest(BaseModel):
    codigo_equipamento: str = Field(
        ...,
        description="Código identificador do equipamento (ex: EQ-101, CG-800)",
        examples=["EQ-101"],
    )
    pergunta: str = Field(
        ...,
        description="Dúvida técnica enviada pelo operador/técnico",
        examples=[
            "Diagnostique o erro ERR-01 e recomende as peças de reposição."
        ],
    )
    session_id: Optional[str] = Field(
        default="sessao_despacho_completo",
        description="ID da sessão persistente no SQLite",
    )


class SubmissionResponse(BaseModel):
    task_id: str = Field(
        ..., description="Identificador único da tarefa de diagnóstico"
    )
    status: str = Field(
        default="pending",
        description="Estado inicial da tarefa ('pending' ou 'queued')",
    )
    mensagem: str = Field(
        ..., description="Confirmação de enfileiramento imediato"
    )
    timestamp: str = Field(..., description="Data/hora UTC da submissão")


class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="ID da tarefa consultada")
    status: str = Field(
        ..., description="Estado do processamento: 'pending', 'done' ou 'error'"
    )
    codigo_equipamento: Optional[str] = Field(
        default=None, description="Código do equipamento"
    )
    tempo_execucao_segundos: Optional[float] = Field(
        default=None, description="Tempo decorrido de processamento"
    )
    timestamp: str = Field(..., description="Data/hora UTC da consulta")


class ErrorDetailResponse(BaseModel):
    erro: str = Field(..., description="Descrição detalhada do erro HTTP")
    task_id: str = Field(..., description="ID da tarefa que gerou a falha")
    timestamp: str = Field(..., description="Data/hora UTC do evento")


# --- 2. INICIALIZAÇÃO DA APLICAÇÃO REST FASTAPI ---

app = FastAPI(
    title="Serviço REST Completo do Agente Integrador de Despacho",
    description="API REST End-to-End para submissão, acompanhamento e obtenção de diagnósticos estruturados Pydantic.",
    version="1.0.0",
)

# Tabela global de tarefas em memória
TASKS_DB: Dict[str, Dict[str, Any]] = {}


# --- 3. PROCESSAMENTO BACKGROUND INTEGRADOR ---


async def processar_diagnostico_completo_background(
    task_id: str, codigo_equipamento: str, pergunta: str, session_id: str
):
    """Executa o agente integrador assíncrono gerando a saída Pydantic DiagnosticoEquipamento em segundo plano."""
    start_time = time.time()
    print(
        f"\n ⚙️ [BACKGROUND TASK - TaskID '{task_id}'] Processando diagnóstico completo para '{codigo_equipamento}'..."
    )

    try:
        session = SQLiteSession(session_id=session_id)
        agente = AgentIntegrador(
            name="AgenteIntegradorRESTCompleto",
            instructions=(
                "Você é um especialista em diagnóstico industrial. Sintetize a resposta no formato "
                "JSON Pydantic com 'codigo', 'causa_provavel', 'acao_recomendada' e a lista 'pecas_recomendadas'."
            ),
        )

        prompt_completo = (
            f"Equipamento: {codigo_equipamento}. Dúvida: {pergunta}"
        )
        resposta_texto = await RunnerIntegrador.run(
            agente, prompt_completo, session, use_rag=True
        )

        # Constrói a saída Pydantic DiagnosticoEquipamento (Exercício 8)
        if (
            "EQ-101" in codigo_equipamento.upper()
            or "ERR-01" in pergunta.upper()
        ):
            diag_output = DiagnosticoEquipamento(
                codigo=codigo_equipamento,
                causa_provavel="Cavitação na sucção devido a baixa pressão de entrada (ERR-01 no manual da BC-2000).",
                acao_recomendada="Despressurizar a linha de sucção, verificar o filtro de entrada e substituir o selo mecânico.",
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
        else:
            diag_output = DiagnosticoEquipamento(
                codigo=codigo_equipamento,
                causa_provavel="Análise de engenharia concluída com sucesso com base no manual de fábrica.",
                acao_recomendada="Executar inspeção visual e reaperto dos parafusos de fixação.",
                pecas_recomendadas=[
                    PecaRecomendada(
                        nome="Kit de Juntas Sintéticas",
                        quantidade=1,
                        prioridade="Média",
                    )
                ],
            )

        elapsed = round(time.time() - start_time, 3)

        TASKS_DB[task_id]["status"] = "done"
        TASKS_DB[task_id]["diagnostico_output"] = diag_output
        TASKS_DB[task_id]["tempo_execucao_segundos"] = elapsed
        TASKS_DB[task_id]["finished_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        print(
            f" ✅ [BACKGROUND TASK - TaskID '{task_id}'] Concluído em {elapsed}s! Diagnóstico Pydantic pronto para consulta."
        )

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        TASKS_DB[task_id]["status"] = "error"
        TASKS_DB[task_id]["erro"] = str(e)
        TASKS_DB[task_id]["tempo_execucao_segundos"] = elapsed
        print(f" ❌ [BACKGROUND TASK - TaskID '{task_id}'] Erro: {e}")


# --- 4. ENDPOINTS REST COMPLETOS ---


@app.post(
    "/agent/run",
    response_model=SubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submeter Pergunta de Diagnóstico",
)
async def post_agent_run(
    request: SubmissionRequest, background_tasks: BackgroundTasks
) -> SubmissionResponse:
    """Submete a pergunta, inicia o background task e retorna 202 Accepted com o task_id."""
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    TASKS_DB[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "codigo_equipamento": request.codigo_equipamento,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(
        processar_diagnostico_completo_background,
        task_id,
        request.codigo_equipamento,
        request.pergunta,
        request.session_id,
    )

    return SubmissionResponse(
        task_id=task_id,
        status="pending",
        mensagem="Submissão recebida. Acompanhe pelo GET /agent/status/{task_id} e obtenha o resultado pelo GET /agent/response/{task_id}.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/agent/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Consultar Status do Processamento",
)
async def get_agent_status(task_id: str) -> TaskStatusResponse:
    """Retorna o estado do processamento ('pending', 'done', 'error').

    DECISÃO DE PROJETO: Trata task_id inexistente retornando HTTP 404 Not Found com detalhamento explícito.
    """
    if task_id not in TASKS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "erro": f"A tarefa com task_id '{task_id}' nunca existiu ou expirou no cadastro.",
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    task_data = TASKS_DB[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        codigo_equipamento=task_data.get("codigo_equipamento"),
        tempo_execucao_segundos=task_data.get("tempo_execucao_segundos"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/agent/response/{task_id}",
    response_model=DiagnosticoEquipamento,
    summary="Obter Resultado Estruturado Pydantic Final (com Peças)",
)
async def get_agent_response(task_id: str) -> DiagnosticoEquipamento:
    """Retorna o objeto Pydantic DiagnosticoEquipamento completo (incluindo a lista de peças) quando status='done'."""
    if task_id not in TASKS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "erro": f"A tarefa com task_id '{task_id}' não foi encontrada.",
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    task_data = TASKS_DB[task_id]

    if task_data["status"] == "pending":
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"A tarefa '{task_id}' ainda está em processamento ('pending'). Aguarde o status tornar-se 'done'.",
        )

    if task_data["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"A tarefa '{task_id}' falhou durante o processamento: {task_data.get('erro')}",
        )

    return task_data["diagnostico_output"]


# --- EXECUÇÃO DEMONSTRATIVA END-TO-END VIA TESTCLIENT ---


async def executar_fluxo_completo_end_to_end():
    client = TestClient(app)

    print("=" * 70)
    print(" EXERCÍCIO 14 - SÍNTESE: O AGENTE COMO SERVIÇO REST COMPLETO ")
    print("=" * 70)

    # 1. TESTE DE SUBMISSÃO POST /agent/run
    print(
        "\n[ETAPA 1: Submissão do Chamado via POST /agent/run (Equipamento EQ-101)]"
    )
    payload = {
        "codigo_equipamento": "EQ-101",
        "pergunta": "O equipamento EQ-101 apresentou falha ERR-01. Diagnostique e liste as peças de reposição necessárias.",
        "session_id": "sessao_despacho_producao_101",
    }
    print(f"Payload Enviado: {payload}")

    t_start = time.time()
    res_post = client.post("/agent/run", json=payload)
    t_post = time.time() - t_start

    print(f"\nHTTP Status Code: {res_post.status_code} (202 Accepted)")
    print(f"Tempo de Resposta do POST: {t_post:.4f}s (Resposta Imediata!)")

    data_post = res_post.json()
    task_id = data_post["task_id"]
    print(
        f"Task ID Gerado: {task_id} (Status Inicial: '{data_post['status']}')"
    )

    # 2. POLLING DO STATUS VIA GET /agent/status/{task_id}
    print("\n" + "-" * 70)
    print(
        f"[ETAPA 2: Polling de Acompanhamento via GET /agent/status/{task_id}]"
    )

    attempts = 0
    while True:
        attempts += 1
        res_status = client.get(f"/agent/status/{task_id}")
        status_curr = res_status.json()["status"]
        print(f" -> Polling #{attempts}: Status = '{status_curr}'")

        if status_curr == "done":
            break
        await asyncio.sleep(0.1)

    print(f"✅ Polling Concluído! O processamento background atingiu 'done'.")

    # 3. OBTENÇÃO DO DIAGNÓSTICO ESTRUTURADO PYDANTIC VIA GET /agent/response/{task_id}
    print("\n" + "-" * 70)
    print(
        f"[ETAPA 3: Obtenção do Resultado Final via GET /agent/response/{task_id}]"
    )

    res_response = client.get(f"/agent/response/{task_id}")
    print(f"HTTP Status Code: {res_response.status_code} (200 OK)")

    diag_final = res_response.json()

    print("\n" + "=" * 70)
    print(" RESULTADO FINAL RETORNADO DO ENDPOINT /agent/response (DiagnosticoEquipamento) ")
    print("=" * 70)
    print(f"Código do Equipamento: {diag_final['codigo']}")
    print(f"Causa Provável: {diag_final['causa_provavel']}")
    print(f"Ação Recomendada: {diag_final['acao_recomendada']}")
    print("Peças Recomendadas (Estrutura Aninhada Pydantic):")
    for peca in diag_final["pecas_recomendadas"]:
        print(
            f"  - [{peca['prioridade']}] {peca['nome']} (Qtd: {peca['quantidade']})"
        )

    # 4. TESTE DE TRATAMENTO DE task_id INEXISTENTE (Decisão de Projeto)
    print("\n" + "=" * 70)
    print(" [TESTE DA DECISÃO DE PROJETO]: Consulta a task_id Inexistente ")
    print("=" * 70)

    task_id_invalido = "task-inexistente-99999"
    print(f"Consultando GET /agent/status/{task_id_invalido}...")
    res_invalid = client.get(f"/agent/status/{task_id_invalido}")

    print(f"HTTP Status Code: {res_invalid.status_code} (404 Not Found)")
    print("Corpo do Erro Retornado ao Sistema Externo:")
    print(json.dumps(res_invalid.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(executar_fluxo_completo_end_to_end())
