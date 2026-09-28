import asyncio
import json
import time
import uuid
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from agents import Agent, Runner, SQLiteSession
from exercicio_10 import buscar_no_manual_extenso_rag

load_dotenv()


class SubmissionRequest(BaseModel):
    codigo_equipamento: str = Field(
        ..., description="Código único do equipamento", examples=["CG-800"]
    )
    pergunta: str = Field(
        ...,
        description="Pergunta técnica para o agente",
        examples=["Qual a periodicidade de manutenção preventiva da bomba?"],
    )
    session_id: Optional[str] = Field(
        default="sessao_despacho_async",
        description="ID da sessão persistente no SQLite",
    )


class SubmissionResponse(BaseModel):
    task_id: str = Field(
        ..., description="Identificador único da tarefa gerada para polling"
    )
    status: str = Field(
        default="pending",
        description="Status inicial da tarefa ('pending' ou 'queued')",
    )
    mensagem: str = Field(
        ..., description="Instruções para acompanhamento do processamento"
    )
    timestamp: str = Field(
        ..., description="Data/hora UTC da submissão em formato ISO 8601"
    )


class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="ID da tarefa consultada")
    status: str = Field(
        ...,
        description="Estado real do processamento: 'pending', 'done' ou 'error'",
    )
    codigo_equipamento: Optional[str] = Field(
        default=None, description="Código do equipamento consultado"
    )
    resultado: Optional[Any] = Field(
        default=None, description="Resultado do diagnóstico (quando status='done')"
    )
    erro: Optional[str] = Field(
        default=None, description="Mensagem de erro (quando status='error')"
    )
    tempo_execucao_segundos: Optional[float] = Field(
        default=None, description="Tempo total de processamento em segundos"
    )
    timestamp: str = Field(
        ..., description="Data/hora UTC da consulta de status"
    )


app = FastAPI(
    title="Serviço REST Assíncrono de Despacho (Polling Pattern)",
    description="Implementação do padrão de submissão assíncrona POST /agent/run e consulta de status GET /agent/status/{task_id}.",
    version="1.0.0",
)

TASKS_STORE: Dict[str, Dict[str, Any]] = {}


async def executar_diagnostico_background(
    task_id: str, codigo_equipamento: str, pergunta: str, session_id: str
):
    start_time = time.time()
    print(
        f"\n ⚙️ [BACKGROUND PROCESS] Iniciando execução para TaskID '{task_id}' (Status: pending -> processando)..."
    )

    try:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if not model_name or "/" in model_name:
            model_name = "gpt-4o-mini"

        session = SQLiteSession(session_id=session_id)
        agente = Agent(
            name="AgenteAsyncPolling",
            instructions="Você é um assistente técnico em serviço REST assíncrono.",
            tools=[buscar_no_manual_extenso_rag],
            model=model_name,
        )

        prompt_completo = (
            f"Equipamento: {codigo_equipamento}. Pergunta: {pergunta}"
        )

        result = await Runner.run(agente, prompt_completo, session=session)
        elapsed = round(time.time() - start_time, 3)

        TASKS_STORE[task_id]["status"] = "done"
        TASKS_STORE[task_id]["resultado"] = str(result.final_output)
        TASKS_STORE[task_id]["tempo_execucao_segundos"] = elapsed
        TASKS_STORE[task_id]["finished_at"] = datetime.now(
            timezone.utc
        ).isoformat()

        print(
            f" ✅ [BACKGROUND PROCESS] Concluído para TaskID '{task_id}' em {elapsed}s! Status atualizado para 'done'."
        )

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        TASKS_STORE[task_id]["status"] = "error"
        TASKS_STORE[task_id]["erro"] = str(e)
        TASKS_STORE[task_id]["tempo_execucao_segundos"] = elapsed
        print(
            f" ❌ [BACKGROUND PROCESS] Erro para TaskID '{task_id}': {e}. Status atualizado para 'error'."
        )


@app.post(
    "/agent/run",
    response_model=SubmissionResponse,
    status_code=202,
    summary="Submeter Pergunta de Diagnóstico (Assíncrono)",
)
async def post_agent_run(
    request: SubmissionRequest, background_tasks: BackgroundTasks
) -> SubmissionResponse:
    task_id = f"task-{uuid.uuid4().hex[:8]}"

    TASKS_STORE[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "codigo_equipamento": request.codigo_equipamento,
        "pergunta": request.pergunta,
        "resultado": None,
        "erro": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    background_tasks.add_task(
        executar_diagnostico_background,
        task_id,
        request.codigo_equipamento,
        request.pergunta,
        request.session_id,
    )

    return SubmissionResponse(
        task_id=task_id,
        status="pending",
        mensagem="Submissão aceita com sucesso. Consulte o resultado via GET /agent/status/{task_id}.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/agent/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Consultar Estado do Processamento pelo task_id",
)
async def get_agent_status(task_id: str) -> TaskStatusResponse:
    if task_id not in TASKS_STORE:
        raise HTTPException(
            status_code=404,
            detail=f"Tarefa com task_id '{task_id}' não foi encontrada.",
        )

    task_data = TASKS_STORE[task_id]

    return TaskStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        codigo_equipamento=task_data.get("codigo_equipamento"),
        resultado=task_data.get("resultado"),
        erro=task_data.get("erro"),
        tempo_execucao_segundos=task_data.get("tempo_execucao_segundos"),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def demonstrar_fluxo_assincrono():
    client = TestClient(app)

    print("=" * 70)
    print(" EXERCÍCIO 13 - PADRÃO DE SUBMISSÃO E CONSULTA ASSÍNCRONA (POLLING) ")
    print("=" * 70)

    print("\n[ETAPA 1: Submetendo pergunta via POST /agent/run]")
    payload = {
        "codigo_equipamento": "CG-800",
        "pergunta": "Qual a temperatura da água de entrada no economizador?",
        "session_id": "sessao_despacho_async_01",
    }
    print(f"Payload Enviado: {payload}")

    t_start = time.time()
    res_post = client.post("/agent/run", json=payload)
    t_post = time.time() - t_start

    print(f"\nHTTP Status Code: {res_post.status_code} (202 Accepted)")
    print(f"Tempo de Resposta do POST: {t_post:.4f}s (Resposta Imediata!)")

    data_post = res_post.json()
    task_id = data_post["task_id"]
    print("Corpo da Resposta do POST (SubmissionResponse):")
    print(json.dumps(data_post, indent=2, ensure_ascii=False))

    print("\n" + "-" * 70)
    print(
        f"[ETAPA 2: Consulta Imediata via GET /agent/status/{task_id} (Esperado: status='pending')]"
    )
    res_status_1 = client.get(f"/agent/status/{task_id}")
    print(f"HTTP Status Code: {res_status_1.status_code}")
    print("Corpo da Resposta (TaskStatusResponse):")
    print(json.dumps(res_status_1.json(), indent=2, ensure_ascii=False))

    print("\n -> Aguardando conclusão da BackgroundTask em segundo plano...")
    await asyncio.sleep(0.5)

    print("\n" + "-" * 70)
    print(
        f"[ETAPA 3: Consulta Final via GET /agent/status/{task_id} (Esperado: status='done')]"
    )
    res_status_2 = client.get(f"/agent/status/{task_id}")
    print(f"HTTP Status Code: {res_status_2.status_code}")
    print("Corpo da Resposta Final com o Resultado (TaskStatusResponse):")
    print(json.dumps(res_status_2.json(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(demonstrar_fluxo_assincrono())
