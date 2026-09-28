import asyncio
import os
from dotenv import load_dotenv
from agents import Agent, Runner, SQLiteSession, function_tool
from gerar_manual_extenso import gerar_manual_extenso
from exercicio_10 import buscar_no_manual_extenso_rag

load_dotenv()

MANUAL_EXTENSO_FILE = "manual_extenso_caldeira.txt"
if not os.path.exists(MANUAL_EXTENSO_FILE):
    gerar_manual_extenso(MANUAL_EXTENSO_FILE)

DB_PATH = "integrator_agent_sessions.db"


async def main():
    print("=" * 70)
    print(" EXERCÍCIO 11 - AGENTE INTEGRADOR (MEMÓRIA SQLITE + RAG SDK) ")
    print("=" * 70)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not model_name or "/" in model_name:
        model_name = "gpt-4o-mini"

    agente = Agent(
        name="AgenteIntegradorEspecialista",
        instructions=(
            "Você é um engenheiro sênior de suporte. Sintetize as respostas utilizando o histórico "
            "da conversa acumulado na sessão e consulte a ferramenta RAG 'buscar_no_manual_extenso_rag' para recuperar procedimentos técnicos de manuais extensos."
        ),
        tools=[buscar_no_manual_extenso_rag],
        model=model_name,
    )

    # --- CENÁRIO A: Técnico fazendo 3 perguntas em sequência sobre o mesmo atendimento ---
    print("\n" + "=" * 70)
    print(" 📌 CENÁRIO A: Técnico em Diagnóstico de Acompanhamento (Multi-turno) ")
    print("=" * 70)

    sessao_tecnico_a = SQLiteSession(
        session_id="atendimento_tecnico_carlos", db_path=DB_PATH
    )

    p1 = "Qual é a frequência recomendada para realizar o teste hidrostático na Caldeira CG-800?"
    print(f"\n[Cenário A - Turno 1]: {p1}")
    r1 = await Runner.run(agente, p1, session=sessao_tecnico_a)
    print(f"[Agente Integrador - Turno 1]:\n{r1.final_output}")

    p2 = "E qual é o valor da pressão de teste exigido nesse mesmo procedimento?"
    print(f"\n[Cenário A - Turno 2 (Contextual)]: {p2}")
    r2 = await Runner.run(agente, p2, session=sessao_tecnico_a)
    print(f"[Agente Integrador - Turno 2]:\n{r2.final_output}")

    p3 = "Se houver reparo com solda antes desse prazo de 5 anos, o teste precisa ser antecipado?"
    print(f"\n[Cenário A - Turno 3 (Contextual)]: {p3}")
    r3 = await Runner.run(agente, p3, session=sessao_tecnico_a)
    print(f"[Agente Integrador - Turno 3]:\n{r3.final_output}")

    # --- CENÁRIO B: Técnico fazendo uma única pergunta pontual sobre um procedimento raro ---
    print("\n" + "=" * 70)
    print(" 📌 CENÁRIO B: Técnico fazendo Pergunta Única sobre Procedimento Raro ")
    print("=" * 70)

    sessao_tecnico_b = SQLiteSession(
        session_id="atendimento_tecnico_roberto", db_path=DB_PATH
    )

    p_pontual = "Qual é o ganho de eficiência térmica proporcionado pelo economizador da caldeira e qual a temperatura da água de entrada?"
    print(f"\n[Cenário B - Pergunta Única Pontual]: {p_pontual}")
    r_pontual = await Runner.run(agente, p_pontual, session=sessao_tecnico_b)
    print(f"[Agente Integrador - Resposta Pontual]:\n{r_pontual.final_output}")


if __name__ == "__main__":
    asyncio.run(main())
