"""Pruebas de la línea de órdenes."""

import pytest

from voceo import proveedores
from voceo.cli import main


@pytest.fixture
def con_config(tmp_path, monkeypatch, proveedor_falso):
    """Un voceo.toml de prueba que usa el proveedor falso."""
    ruta = tmp_path / "voceo.toml"
    ruta.write_text(
        f'proveedor = "falso-mp3"\nsalida = "{tmp_path / "audio"}"\n'
        "campanilla = false\nnormalizar_volumen = false\n"
        "silencio_inicial = 0.0\nsilencio_final = 0.0\n\n"
        '[perfiles.emergencia]\nrepetir = 2\nvelocidad = "-15%"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return ruta


def test_sin_orden_muestra_la_ayuda(capsys):
    assert main([]) == 0
    assert "voceo" in capsys.readouterr().out


def test_generar_escribe_el_mp3(con_config, tmp_path, capsys):
    assert main(["generar", "Hola centro comercial", "-o", str(tmp_path / "a.mp3")]) == 0
    assert (tmp_path / "a.mp3").exists()
    assert "✓" in capsys.readouterr().out


def test_generar_usa_la_carpeta_de_salida(con_config, tmp_path):
    assert main(["generar", "Cierre en quince minutos"]) == 0
    assert (tmp_path / "audio" / "cierre-en-quince-minutos.mp3").exists()


def test_simular_no_genera_audio(con_config, tmp_path, capsys):
    assert main(["generar", "El Sr. López", "--simular"]) == 0
    assert capsys.readouterr().out.strip() == "El señor López"
    assert not (tmp_path / "audio").exists()


def test_generar_desde_archivo_txt(con_config, tmp_path, capsys):
    fuente = tmp_path / "aviso.txt"
    fuente.write_text("Texto desde archivo", encoding="utf-8")
    assert main(["generar", str(fuente), "--simular"]) == 0
    assert "Texto desde archivo" in capsys.readouterr().out


def test_generar_desde_la_entrada_estandar(con_config, monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("Texto por tubería"))
    assert main(["generar", "-", "--simular"]) == 0
    assert "Texto por tubería" in capsys.readouterr().out


def test_plantilla_rellena_los_campos(con_config, capsys):
    assert main(["plantilla", "llamado_persona", "--campo", "nombre=Ana", "--simular"]) == 0
    assert "Ana" in capsys.readouterr().out


def test_campo_mal_escrito(con_config, capsys):
    assert main(["plantilla", "llamado_persona", "--campo", "nombre"]) == 1
    assert "campo=valor" in capsys.readouterr().err


def test_plantilla_inexistente(con_config, capsys):
    assert main(["plantilla", "no_existe"]) == 1
    assert "✗" in capsys.readouterr().err


def test_los_ajustes_de_la_plantilla_se_aplican(con_config, espia_config, tmp_path):
    """La plantilla «evacuacion» pide repetir=2; debe llegar así al generador."""
    assert main(["plantilla", "evacuacion", "-o", str(tmp_path / "e.mp3")]) == 0
    assert espia_config["config"].repetir == 2


def test_la_cli_manda_sobre_los_ajustes_de_la_plantilla(con_config, espia_config, tmp_path):
    assert main(
        ["plantilla", "evacuacion", "--repetir", "1", "-o", str(tmp_path / "e.mp3")]
    ) == 0
    assert espia_config["config"].repetir == 1


def test_el_perfil_se_aplica(con_config, espia_config, tmp_path):
    assert main(
        ["generar", "Hola", "--perfil", "emergencia", "-o", str(tmp_path / "a.mp3")]
    ) == 0
    assert espia_config["config"].velocidad == "-15%"


def test_la_cli_manda_sobre_el_perfil(con_config, espia_config, tmp_path):
    assert main(
        ["generar", "Hola", "--perfil", "emergencia", "--velocidad=-2%",
         "-o", str(tmp_path / "a.mp3")]
    ) == 0
    assert espia_config["config"].velocidad == "-2%"


def test_velocidad_negativa_sin_el_simbolo_por_ciento(con_config, espia_config, tmp_path):
    """«--velocidad -2» debe funcionar sin necesidad del «=»."""
    assert main(
        ["generar", "Hola", "--velocidad", "-2", "-o", str(tmp_path / "a.mp3")]
    ) == 0
    assert espia_config["config"].velocidad == "-2%"


def test_listar_plantillas(con_config, capsys):
    assert main(["plantillas"]) == 0
    salida = capsys.readouterr().out
    assert "llamado_persona" in salida
    assert "plantillas en" in salida


def test_detalle_de_una_plantilla(con_config, capsys):
    assert main(["plantillas", "vehiculo"]) == 0
    salida = capsys.readouterr().out
    assert "--campo placas=" in salida
    assert "se deletrea" in salida


def test_lote_genera_los_avisos(con_config, tmp_path, capsys):
    csv = tmp_path / "avisos.csv"
    csv.write_text("archivo,texto\nuno.mp3,Hola\ndos.mp3,Adiós\n", encoding="utf-8")
    assert main(["lote", str(csv), "-d", str(tmp_path / "lote")]) == 0
    assert (tmp_path / "lote" / "uno.mp3").exists()
    assert "2 generados" in capsys.readouterr().out


def test_lote_con_error_devuelve_codigo_1(con_config, tmp_path, capsys):
    csv = tmp_path / "avisos.csv"
    csv.write_text("archivo,plantilla\nuno.mp3,inventada\n", encoding="utf-8")
    assert main(["lote", str(csv), "-d", str(tmp_path / "lote")]) == 1


def test_lote_simular(con_config, tmp_path, capsys):
    csv = tmp_path / "avisos.csv"
    csv.write_text("texto\nHola a todos\n", encoding="utf-8")
    assert main(["lote", str(csv), "--simular"]) == 0
    assert "Hola a todos" in capsys.readouterr().out


def test_voces(con_config, capsys):
    assert main(["voces"]) == 0
    assert "falsa-1" in capsys.readouterr().out


def test_voces_con_filtro_sin_resultados(con_config, capsys):
    assert main(["voces", "--buscar", "zzz"]) == 0
    assert "No se encontraron voces" in capsys.readouterr().out


def test_campanilla(tmp_path, capsys):
    destino = tmp_path / "camp.wav"
    assert main(["campanilla", "-o", str(destino)]) == 0
    assert destino.exists()


def test_doctor(con_config, capsys):
    assert main(["doctor"]) == 0
    salida = capsys.readouterr().out
    assert "ffmpeg" in salida
    assert "Proveedores de voz" in salida


def test_proveedor_desconocido_en_la_cli(con_config, capsys):
    with pytest.raises(SystemExit):
        main(["generar", "Hola", "--proveedor", "inventado"])
