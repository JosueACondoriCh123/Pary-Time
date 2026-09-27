"""Tests del journal, portados de Night Council (tests/test_core.py)."""
import pytest

from core.journal import Journal, JournalError


# --- diario ---

def test_journal_chain_verifies(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    for i in range(5):
        j.append("decision", {"decision_id": f"dec_{i}", "reason": "x"}, "sha:man")
    assert j.verify() == 5
    # Reabrir continúa la cadena.
    j2 = Journal(tmp_path / "j.jsonl")
    j2.append("decision", {"n": 6}, "sha:man")
    assert j2.verify() == 6


@pytest.mark.parametrize("tamper", ["edit", "delete", "swap"])
def test_journal_detects_tampering(tmp_path, tamper):
    p = tmp_path / "j.jsonl"
    j = Journal(p)
    for i in range(4):
        j.append("decision", {"size_usd": 100 + i}, "sha:man")
    lines = p.read_text(encoding="utf-8").splitlines()
    if tamper == "edit":
        lines[1] = lines[1].replace('"size_usd":101', '"size_usd":999')
    elif tamper == "delete":
        del lines[2]
    else:
        lines[1], lines[2] = lines[2], lines[1]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(JournalError):
        Journal(p).verify()


def test_journal_rejects_secrets(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    with pytest.raises(JournalError):
        j.append("config", {"nested": {"OC_SECRET_KEY": "x"}}, "v")


# --- A10: el diario se parsea una vez por línea, no una vez por consulta ---

def test_reading_the_journal_many_times_parses_each_line_once(tmp_path):
    """Un ciclo consulta el diario ocho o nueve veces. Antes cada consulta reparseaba el
    archivo entero, así que el costo por ciclo crecía con los días de corrida."""
    j = Journal(tmp_path / "j.jsonl")
    for i in range(50):
        j.append("heartbeat", {"cycle": i}, "v")
    assert j._parses == 0                                  # escribir no parsea
    assert len(list(j.events())) == 50
    once = j._parses
    assert once == 50
    for _ in range(10):
        list(j.events())
    assert j._parses == once                               # releer no vuelve a parsear nada
    j.append("heartbeat", {"cycle": 50}, "v")
    assert len(list(j.events())) == 51 and j._parses == once + 1     # solo la línea nueva
    assert j.verify() == 51


# --- A7: un corte de luz a mitad de una escritura no puede dejar al agente sin arrancar ---

def torn(tmp_path, n=3):
    """Diario con n eventos completos y un cuarto a medio escribir, como tras un corte."""
    p = tmp_path / "j.jsonl"
    j = Journal(p)
    for i in range(n):
        j.append("heartbeat", {"cycle": i}, "v")
    with p.open("a", encoding="utf-8") as f:
        f.write('{"seq":4,"ts":1758,"kind":"decision","payload":{"dec')
        f.flush()
    return p


def test_a_torn_last_line_does_not_brick_the_agent(tmp_path):
    p = torn(tmp_path)
    j = Journal(p)                                   # hoy esto reventaba en el constructor
    assert [e["payload"]["cycle"] for e in j.events()] == [0, 1, 2]
    assert j.verify() == 3
    assert j.torn_tail is not None


def test_appending_after_a_torn_line_heals_it_and_keeps_the_chain(tmp_path):
    p = torn(tmp_path)
    j = Journal(p)
    j.append("heartbeat", {"cycle": 3}, "v")
    assert j.verify() == 4
    assert j.torn_tail is None
    # La línea rota no se borra en silencio: queda al lado, para el auditor.
    [saved] = list(tmp_path.glob("j.jsonl.torn-*"))
    assert saved.read_text(encoding="utf-8").startswith('{"seq":4')
    assert "jsonl.torn" not in p.read_text(encoding="utf-8")
    assert Journal(p).verify() == 4                  # y reabrirlo sigue funcionando


def test_a_torn_line_in_the_middle_is_corruption_and_must_fail(tmp_path):
    p = torn(tmp_path)
    with p.open("a", encoding="utf-8") as f:         # algo escribió después de la línea rota
        f.write('\n{"seq":5,"ts":1759,"kind":"heartbeat","payload":{},"prev":"x","hash":"y"}\n')
    with pytest.raises(JournalError, match="ilegible"):
        Journal(p).verify()
