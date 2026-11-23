"""Simulação de oito pedidos em uma pizzaria com forno compartilhado."""

import multiprocessing as mp
import os
import platform
import random
import threading
import time
from pathlib import Path


NUM_PEDIDOS = 8
NUM_PIZZAIOLOS = 3
CAPACIDADE_FORNO = 2
TEMPO_FORNO = 3
ARQUIVO_VENDAS = Path("pizzas_prontas.txt")
SABORES = ("Calabresa", "Marguerita", "Frango com Catupiry", "Quatro Queijos")


def exibir(mensagem, trava_saida):
    with trava_saida:
        print(mensagem, flush=True)


def fazer_pedido(numero, fila_pedidos, largada, trava_saida):
    largada.wait()
    sabor = random.choice(SABORES)
    with trava_saida:
        fila_pedidos.put((numero, sabor))
        print(f"[CLIENTE] Pedido #{numero} ({sabor}) realizado.", flush=True)


def assar(numero, forno, ocupacao, trava_saida):
    
    with forno:
        with ocupacao.get_lock():
            ocupacao.value += 1
            exibir(
                f"[FORNO] Pizza #{numero} entrou no forno "
                f"({ocupacao.value}/{CAPACIDADE_FORNO} vagas ocupadas).",
                trava_saida,
            )

        assada = False
        try:
            time.sleep(TEMPO_FORNO)
            assada = True
        finally:
            with ocupacao.get_lock():
                ocupacao.value -= 1
                if assada:
                    exibir(f"[FORNO] Pizza #{numero} assada e retirada.", trava_saida)


def entregar(numero, trava_saida):
    exibir(f"[ENTREGA] Entregador a caminho da entrega #{numero}...", trava_saida)
    time.sleep(random.uniform(1, 3))
    exibir(f"[CONCLUÍDO] Pedido #{numero} entregue ao cliente!", trava_saida)


def trabalhar_na_cozinha(fila_pedidos, forno, ocupacao, trava_vendas, trava_saida):
    pid = os.getpid()
    entregas = []
    while True:
        pedido = fila_pedidos.get()
        if pedido is None:
            break

        numero, sabor = pedido
        exibir(f"[PIZZAIOLO {pid}] Iniciando preparo da pizza #{numero}.", trava_saida)
        time.sleep(random.uniform(2, 4))
        assar(numero, forno, ocupacao, trava_saida)

        with trava_vendas:
            with ARQUIVO_VENDAS.open("a", encoding="utf-8") as arquivo:
                arquivo.write(f"Pedido #{numero} ({sabor})\n")

        entrega = threading.Thread(target=entregar, args=(numero, trava_saida))
        entrega.start()
        entregas.append(entrega)

    for entrega in entregas:
        entrega.join()


def gerenciar_pizzaria():
    print(f"[GERENTE] PID {os.getpid()} | Arquitetura: {platform.machine()}", flush=True)
    if NUM_PIZZAIOLOS < 1 or CAPACIDADE_FORNO < 1:
        raise ValueError("A pizzaria precisa de pelo menos um pizzaiolo e uma vaga no forno.")

    
    contexto = mp.get_context("spawn")
    fila_pedidos = contexto.Queue()
    forno = contexto.BoundedSemaphore(CAPACIDADE_FORNO)
    ocupacao = contexto.Value("i", 0)
    trava_vendas = contexto.Lock()
    trava_saida = contexto.Lock()

    pizzaiolos = [
        contexto.Process(
            target=trabalhar_na_cozinha,
            args=(fila_pedidos, forno, ocupacao, trava_vendas, trava_saida),
            name=f"Pizzaiolo-{numero}",
        )
        for numero in range(1, NUM_PIZZAIOLOS + 1)
    ]
    for pizzaiolo in pizzaiolos:
        pizzaiolo.start()

    largada = threading.Barrier(NUM_PEDIDOS)
    clientes = [
        threading.Thread(
            target=fazer_pedido,
            args=(numero, fila_pedidos, largada, trava_saida),
        )
        for numero in range(1, NUM_PEDIDOS + 1)
    ]
    for cliente in clientes:
        cliente.start()
    for cliente in clientes:
        cliente.join()

    for _ in pizzaiolos:
        fila_pedidos.put(None)
    for pizzaiolo in pizzaiolos:
        pizzaiolo.join()
    fila_pedidos.close()
    fila_pedidos.join_thread()

    falhas = [pizzaiolo.name for pizzaiolo in pizzaiolos if pizzaiolo.exitcode != 0]
    if falhas:
        raise SystemExit(f"[GERENTE] Falha na cozinha: {', '.join(falhas)}.")


if __name__ == "__main__":
    gerenciar_pizzaria()
