/* Lógica de la página de Voceo: sin dependencias ni CDN. */

const $ = (selector, raiz = document) => raiz.querySelector(selector);
const $$ = (selector, raiz = document) => [...raiz.querySelectorAll(selector)];

const elError = $("#error");
const elCargando = $("#cargando");
let urlAudio = null;

// --- pestañas ------------------------------------------------------------
$$(".pestana").forEach((boton) => {
  boton.addEventListener("click", () => {
    $$(".pestana").forEach((b) => b.classList.toggle("activa", b === boton));
    $$(".panel").forEach((p) =>
      p.classList.toggle("oculto", p.id !== boton.dataset.panel)
    );
    ocultarMensajes();
  });
});

// --- utilidades ----------------------------------------------------------
function ocultarMensajes() {
  elError.classList.add("oculto");
  elCargando.classList.add("oculto");
}

function mostrarError(mensaje) {
  elError.textContent = mensaje;
  elError.classList.remove("oculto");
  elCargando.classList.add("oculto");
}

function ajustesDe(panel) {
  return {
    voz: $(".voz", panel).value,
    velocidad: $(".velocidad", panel).value,
    repetir: $(".repetir", panel).value,
    campanilla: $(".campanilla", panel).checked,
    perfil: $(".perfil", panel).value,
  };
}

/** Lee el error que devuelve el servidor, venga en JSON o en texto plano. */
async function errorDe(respuesta) {
  try {
    const datos = await respuesta.json();
    return datos.error || `Error ${respuesta.status}`;
  } catch {
    return respuesta.status === 401
      ? "Contraseña incorrecta."
      : `Error ${respuesta.status}`;
  }
}

async function conEspera(boton, tarea) {
  ocultarMensajes();
  elCargando.classList.remove("oculto");
  boton.disabled = true;
  try {
    await tarea();
  } catch (fallo) {
    mostrarError(fallo.message || String(fallo));
  } finally {
    boton.disabled = false;
    elCargando.classList.add("oculto");
  }
}

// --- campos de la plantilla ---------------------------------------------
// Los datos de las plantillas los deja la página en `window.VOCEO`.
const plantillas = Object.fromEntries(
  (window.VOCEO.plantillas || []).map((p) => [p.nombre, p])
);

const selectorPlantilla = $("#plantilla");
const zonaCampos = $("#campos-plantilla");
const zonaTexto = $("#zona-texto");

function pintarCampos(nombre) {
  const plantilla = plantillas[nombre];
  zonaCampos.innerHTML = "";
  if (!plantilla) {
    zonaCampos.classList.add("oculto");
    zonaTexto.classList.remove("oculto");
    return;
  }
  zonaTexto.classList.add("oculto");
  zonaCampos.classList.remove("oculto");

  const descripcion = document.createElement("p");
  descripcion.className = "descripcion";
  descripcion.textContent = plantilla.descripcion;
  zonaCampos.append(descripcion);

  if (plantilla.campos.length === 0) {
    const nota = document.createElement("p");
    nota.className = "pista";
    nota.textContent = "Esta plantilla no necesita ningún dato.";
    zonaCampos.append(nota);
    return;
  }

  plantilla.campos.forEach((campo) => {
    const etiqueta = document.createElement("label");
    const obligatorio = plantilla.obligatorios.includes(campo);
    etiqueta.textContent = campo.replace(/_/g, " ");
    if (!obligatorio) {
      const marca = document.createElement("span");
      marca.className = "opcional";
      marca.textContent = " (opcional)";
      etiqueta.append(marca);
    }
    if (plantilla.deletrear.includes(campo)) {
      const marca = document.createElement("span");
      marca.className = "opcional";
      marca.textContent = " · se leerá letra a letra";
      etiqueta.append(marca);
    }

    const entrada = document.createElement("input");
    entrada.type = "text";
    entrada.dataset.campo = campo;
    entrada.placeholder = plantilla.por_defecto[campo] || "";
    zonaCampos.append(etiqueta, entrada);
  });
}

selectorPlantilla.addEventListener("change", () => {
  pintarCampos(selectorPlantilla.value);
  ocultarMensajes();
});

// --- carga del catálogo completo de voces --------------------------------
(async () => {
  try {
    const respuesta = await fetch("/voces");
    if (!respuesta.ok) return; // se quedan las voces recomendadas
    const catalogo = await respuesta.json();
    if (!catalogo.length) return;
    $$(".voz").forEach((selector) => {
      const elegida = selector.value;
      selector.innerHTML = "";
      catalogo.forEach((voz) => {
        const opcion = document.createElement("option");
        opcion.value = voz.id;
        opcion.textContent = voz.nombre;
        selector.append(opcion);
      });
      selector.value = catalogo.some((v) => v.id === elegida)
        ? elegida
        : window.VOCEO.vozPorDefecto;
    });
  } catch {
    /* sin conexión al catálogo: se dejan las voces recomendadas */
  }
})();

// --- petición de un aviso ------------------------------------------------
function cuerpoDelAviso() {
  const panel = $("#panel-uno");
  const cuerpo = { ...ajustesDe(panel), archivo: $("#archivo").value };
  const plantilla = selectorPlantilla.value;
  if (plantilla) {
    cuerpo.plantilla = plantilla;
    cuerpo.campos = Object.fromEntries(
      $$("[data-campo]", zonaCampos).map((e) => [e.dataset.campo, e.value])
    );
  } else {
    cuerpo.texto = $("#texto").value;
  }
  return cuerpo;
}

$("#btn-previsualizar").addEventListener("click", (evento) =>
  conEspera(evento.target, async () => {
    const respuesta = await fetch("/previsualizar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpoDelAviso()),
    });
    if (!respuesta.ok) throw new Error(await errorDe(respuesta));
    const datos = await respuesta.json();
    const zona = $("#previsualizacion");
    zona.innerHTML = "";
    const parrafo = document.createElement("p");
    parrafo.className = "texto-final";
    parrafo.textContent = datos.texto;
    zona.append(parrafo);
    zona.classList.remove("oculto");
  })
);

$("#btn-generar").addEventListener("click", (evento) =>
  conEspera(evento.target, async () => {
    const respuesta = await fetch("/generar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpoDelAviso()),
    });
    if (!respuesta.ok) throw new Error(await errorDe(respuesta));

    const audio = await respuesta.blob();
    if (urlAudio) URL.revokeObjectURL(urlAudio);
    urlAudio = URL.createObjectURL(audio);

    const nombre = respuesta.headers.get("X-Voceo-Archivo") || "aviso.mp3";
    const duracion = respuesta.headers.get("X-Voceo-Duracion");
    $("#reproductor").src = urlAudio;
    $("#descargar").href = urlAudio;
    $("#descargar").download = nombre;
    $("#detalle-resultado").textContent = duracion
      ? `${nombre} · ${duracion} s`
      : nombre;
    $("#resultado").classList.remove("oculto");
    $("#reproductor").play().catch(() => {
      /* algunos navegadores no dejan reproducir solos: el botón sigue ahí */
    });
  })
);

// --- petición de un lote -------------------------------------------------
$("#btn-lote").addEventListener("click", (evento) =>
  conEspera(evento.target, async () => {
    const archivo = $("#csv").files[0];
    if (!archivo) throw new Error("Elige primero el archivo CSV.");

    const panel = $("#panel-lote");
    const formulario = new FormData();
    formulario.append("csv", archivo);
    Object.entries(ajustesDe(panel)).forEach(([clave, valor]) =>
      formulario.append(clave, valor)
    );

    const respuesta = await fetch("/lote", { method: "POST", body: formulario });
    if (!respuesta.ok) throw new Error(await errorDe(respuesta));

    const zip = await respuesta.blob();
    const url = URL.createObjectURL(zip);
    const generados = respuesta.headers.get("X-Voceo-Generados") || "?";
    const fallidos = respuesta.headers.get("X-Voceo-Fallidos") || "0";

    const zona = $("#resultado-lote");
    zona.innerHTML = "";
    const resumen = document.createElement("p");
    resumen.textContent =
      fallidos === "0"
        ? `${generados} avisos generados.`
        : `${generados} avisos generados, ${fallidos} con error (ver errores.csv dentro del ZIP).`;
    const enlace = document.createElement("a");
    enlace.className = "principal";
    enlace.href = url;
    enlace.download = "avisos.zip";
    enlace.textContent = "Descargar el ZIP";
    zona.append(resumen, enlace);
    zona.classList.remove("oculto");
  })
);
