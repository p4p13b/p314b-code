package space.p314b.tallercito

import android.graphics.Typeface
import android.text.Editable
import android.text.InputType
import android.text.Layout
import android.text.TextWatcher
import android.util.TypedValue
import android.view.Gravity
import android.widget.TextView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.launch
import java.text.Normalizer
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val FECHA = DateTimeFormatter.ofPattern("dd/MM HH:mm").withZone(ZoneId.systemDefault())
private fun fecha(iso: String) = runCatching { FECHA.format(Instant.parse(iso)) }.getOrDefault("")
private fun sinTildes(s: String) = Normalizer.normalize(s, Normalizer.Form.NFD).replace(Regex("\\p{M}"), "").lowercase()

@Composable
fun App(est: Estado, atras: () -> Unit) {
    Column(Modifier.fillMaxSize().imePadding()) {
        when (est.pantalla) {
            Pantalla.PRINCIPAL -> Principal(est)
            Pantalla.EDITOR -> est.ed?.let { Editor(est, it) } ?: Principal(est)
            Pantalla.VISTA -> est.ed?.let { Vista(est, it) } ?: Principal(est)
            Pantalla.DESTINO -> est.ed?.let { DestinoPantalla(est, it) } ?: Principal(est)
            Pantalla.VINCULAR -> Vincular(est)
        }
    }
    if (est.confirmarVolver) {
        Dialogo(
            "¿Querés descartar el contenido?",
            "Hay cambios sin guardar" + (est.ed?.titulo?.takeIf { it.isNotBlank() }?.let { " en «$it»" } ?: "") + ". Si volvés ahora, se pierden.",
            listOf(
                opcion("guardar y volver", true) { est.confirmarVolver = false; est.aviso = est.guardar() ?: "✓ borrador guardado" },
                opcion("descartar", false) { est.confirmarVolver = false; est.cerrarEdicion() },
                opcion("seguir editando", false) { est.confirmarVolver = false },
            ),
        ) { est.confirmarVolver = false }
    }
}

private fun opcion(t: String, primario: Boolean, f: () -> Unit): Triple<String, Boolean, () -> Unit> = Triple(t, primario, f)

/* ── Barra de arriba ── */

@Composable
private fun Arriba(izq: String, der: String, derColor: Color = c.muted, alIzq: (() -> Unit)? = null, alDer: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        if (alIzq != null) Mono(izq, 14.sp, c.muted, modifier = Modifier.clickable(onClick = alIzq))
        else Row {
            Mono("p314b ", 14.sp, c.ink, peso = androidx.compose.ui.text.font.FontWeight.Medium)
            Mono("· ", 14.sp, c.red)
            Mono("tallercito", 14.sp, c.ink, peso = androidx.compose.ui.text.font.FontWeight.Medium)
        }
        Box(Modifier.weight(1f))
        Mono(der, 10.sp, derColor, mayus = true, modifier = if (alDer != null) Modifier.clickable(onClick = alDer) else Modifier)
    }
    Linea()
}

@Composable
private fun Abajo(contenido: @Composable RowScope.() -> Unit) {
    Linea()
    Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically, content = contenido)
}

/* ── A · Pantalla principal ── */

@Composable
fun ColumnScope.Principal(est: Estado) {
    val alcance = rememberCoroutineScope()
    var menu by remember { mutableStateOf(false) }
    val estadoRed = when {
        est.llave == null -> "vincular ›"
        est.enLinea -> "● en línea"
        else -> "● sin conexión"
    }
    Arriba("", estadoRed, if (est.llave == null) c.red else if (est.enLinea) c.ok else c.amb, alDer = { est.pantalla = Pantalla.VINCULAR })
    Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
        Hueco(14)
        Row(Modifier.fillMaxWidth().border(1.dp, c.red).clickable { menu = !menu }.padding(14.dp)) {
            Mono("＋ nuevo", 12.sp, c.red, mayus = true)
            Box(Modifier.weight(1f))
            Mono(if (menu) "▴" else "▾", 12.sp, c.red)
        }
        if (menu) {
            Row(Modifier.fillMaxWidth().background(c.bg2).border(1.dp, c.red).clickable { menu = false; est.nuevo() }.padding(14.dp)) {
                Serif("Nuevo borrador · Nota", 17.sp, c.ink, italic = true)
                Box(Modifier.weight(1f))
                Mono("→", 13.sp, c.red)
            }
        }
        est.aviso?.let {
            Hueco(10)
            Row(Modifier.fillMaxWidth().border(1.dp, c.amb).clickable { est.aviso = null }.padding(10.dp)) {
                Mono(it, 12.sp, c.amb, modifier = Modifier.weight(1f))
                Mono("×", 13.sp, c.amb)
            }
        }
        Hueco(16)
        Mono("borradores en el celular · ${est.borradores.size}", 10.sp, mayus = true)
        if (est.borradores.isEmpty()) {
            Hueco(24)
            Serif("Nada por ahora. Todo lo que escribas queda guardado acá hasta que lo subas.", 15.sp, c.muted)
        }
        LazyColumn(Modifier.weight(1f)) {
            items(est.borradores, key = { it.id }) { b ->
                val on = b.id in est.seleccion
                Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f).clickable { est.abrir(b) }) {
                        Serif(b.titulo.ifBlank { "(sin título)" }, 18.sp, c.ink, italic = true)
                        Hueco(4)
                        val pal = b.partes.sumOf { Formato.palabras(it.html) }
                        val dest = when (b.destino.tipo) {
                            "existente" -> "→ suma a «${b.destino.titulo}»"
                            "copia" -> "copia del taller"
                            else -> null
                        }
                        val partes = if (b.partes.size > 1) "${b.partes.size} partes" else null
                        Mono(listOfNotNull(dest, partes, "modificado ${fecha(b.modificado)}", "$pal pal.").joinToString(" · "), 11.sp,
                            if (b.esCopia) c.amb else c.muted)
                    }
                    Ancho(10)
                    Interruptor(on) { if (on) est.seleccion.remove(b.id) else est.seleccion.add(b.id) }
                }
                Linea()
            }
        }
    }
    val n = est.seleccion.size
    Mono(
        if (!est.enLinea) "Sin conexión: se puede subir cuando vuelva." else "Entran a la bandeja como borrador. No se publica nada.",
        11.sp, if (est.enLinea) c.muted else c.amb, modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
    )
    Abajo {
        Boton("descartar${if (n > 0) " $n" else ""}", Modifier, primario = false, habilitado = n > 0, color = c.red) {
            est.pedirDesbloqueo("Descartar $n borrador${if (n == 1) "" else "es"}") { est.descartarSeleccion() }
        }
        Boton(
            when {
                est.ocupado -> "subiendo…"
                est.llave == null -> "vincular para subir"
                else -> "subir${if (n > 0) " $n" else ""} a la bandeja ↑"
            },
            Modifier.weight(1f),
            habilitado = !est.ocupado && (est.llave == null || (n > 0 && est.enLinea)),
        ) {
            if (est.llave == null) est.pantalla = Pantalla.VINCULAR else alcance.launch { est.subir() }
        }
    }
}

/* ── B · Editor ── */

@Composable
fun ColumnScope.Editor(est: Estado, ed: Edicion) {
    var tick by remember { mutableIntStateOf(0) }
    val col = c
    Arriba("← principal", if (ed.base.esCopia) "copia · borrador" else if (ed.partes.size > 1) "acumulado · borrador" else "nota · borrador",
        alIzq = { ed.volcar(); est.pedirVolver() })
    Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
        Hueco(12)
        Mono("título", 10.sp, mayus = true)
        BasicTextField(
            ed.titulo, { ed.titulo = it; ed.sucio = true },
            Modifier.fillMaxWidth().padding(vertical = 6.dp),
            textStyle = TextStyle(color = c.ink, fontSize = 22.sp, fontFamily = FontFamily.Serif, fontStyle = FontStyle.Italic),
            singleLine = true, cursorBrush = SolidColor(c.red),
            decorationBox = { inner -> Box { if (ed.titulo.isEmpty()) Serif("Título", 22.sp, c.ghost, italic = true); inner() } },
        )
        Linea()
        Hueco(6)
        Mono("creado ${fecha(ed.base.creado)}" + (if (!ed.esNuevo) " · modificado ${fecha(ed.base.modificado)}" else "") + " · sin categoría", 10.5.sp, c.ghost)
        if (ed.partes.size > 1) {
            Hueco(10)
            Row(Modifier.fillMaxWidth().border(1.dp, c.rule), verticalAlignment = Alignment.CenterVertically) {
                Mono("‹", 20.sp, if (ed.idx > 0) c.red else c.ghost, modifier = Modifier.clickable(enabled = ed.idx > 0) { cambiarParte(ed, ed.idx - 1) }.padding(horizontal = 18.dp, vertical = 8.dp))
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                    Mono("parte ${ed.idx + 1} de ${ed.partes.size}", 12.sp, c.ink, mayus = true)
                    ed.titulosPartes.getOrNull(ed.idx)?.takeIf { it.isNotBlank() }?.let { Mono("«$it»", 11.sp) }
                }
                Mono("›", 20.sp, if (ed.idx < ed.partes.size - 1) c.red else c.ghost, modifier = Modifier.clickable(enabled = ed.idx < ed.partes.size - 1) { cambiarParte(ed, ed.idx + 1) }.padding(horizontal = 18.dp, vertical = 8.dp))
            }
            Row(Modifier.fillMaxWidth().padding(top = 6.dp), horizontalArrangement = Arrangement.Center) {
                repeat(ed.partes.size.coerceAtMost(12)) { i ->
                    Box(Modifier.padding(horizontal = 3.dp).size(7.dp).background(if (i == ed.idx) c.red else c.ghost, CircleShape))
                }
            }
        }
        Hueco(8)
        Linea()
        // Barra: alineación · tipografía · tamaño · B I N
        val v = ed.vista
        val vuelta = tick // se vuelve a calcular la barra cuando se mueve el cursor
        val sel = v?.selectionStart ?: 0
        val al = v?.let { Formato.alineacionEn(it.text, sel) } ?: Layout.Alignment.ALIGN_NORMAL
        val fam = v?.let { Formato.familiaEn(it.text, sel) } ?: "serif"
        val tam = v?.let { Formato.tamanoEn(it.text, sel) }
        val bold = v?.let { Formato.tiene(it.text, it.selectionStart, it.selectionEnd, Typeface.BOLD) } ?: false
        val ital = v?.let { Formato.tiene(it.text, it.selectionStart, it.selectionEnd, Typeface.ITALIC) } ?: false
        fun op(f: (EditorTexto) -> Unit) { ed.vista?.let { f(it); ed.sucio = true; tick++ } }
        Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Tecla("⇤", al == Layout.Alignment.ALIGN_NORMAL) { op { Formato.alinear(it, Layout.Alignment.ALIGN_NORMAL) } }
            Tecla("⇔", al == Layout.Alignment.ALIGN_CENTER) { op { Formato.alinear(it, Layout.Alignment.ALIGN_CENTER) } }
            Tecla("⇥", al == Layout.Alignment.ALIGN_OPPOSITE) { op { Formato.alinear(it, Layout.Alignment.ALIGN_OPPOSITE) } }
            Box(Modifier.weight(1f))
            Tecla("B", bold) { op { Formato.alternar(it, Typeface.BOLD) } }
            Tecla("I", ital, italica = true) { op { Formato.alternar(it, Typeface.ITALIC) } }
            Tecla("N", false) { op { Formato.normal(it) } }
        }
        Row(Modifier.fillMaxWidth().padding(bottom = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            val nombreFam = mapOf("serif" to "serif", "sans-serif" to "sans", "monospace" to "mono")
            Tecla("letra: ${nombreFam[fam]} ▾", fam != "serif", ancho = true) {
                val sig = when (fam) { "serif" -> "sans-serif"; "sans-serif" -> "monospace"; else -> "serif" }
                op { Formato.fuente(it, sig) }
            }
            Tecla("tamaño: ${when (tam) { "big" -> "grande"; "small" -> "chico"; else -> "normal" }} ▾", tam != null, ancho = true) {
                val sig = when (tam) { null -> Formato.GRANDE; "big" -> Formato.CHICO; else -> null }
                op { Formato.tamano(it, sig) }
            }
        }
        Box(Modifier.fillMaxWidth().weight(1f).background(c.bg2).border(1.dp, c.rule)) {
            AndroidView(
                factory = { ctx ->
                    EditorTexto(ctx).apply {
                        background = null
                        setTextColor(col.soft.toArgb())
                        setHintTextColor(col.ghost.toArgb())
                        highlightColor = col.red.copy(alpha = 0.3f).toArgb()
                        hint = "Escribí…"
                        typeface = Typeface.SERIF
                        setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
                        setLineSpacing(0f, 1.35f)
                        gravity = Gravity.TOP or Gravity.START
                        inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES
                        setPadding(36, 30, 36, 30)
                        setText(Formato.aSpanned(ed.partes[ed.idx]))
                        addTextChangedListener(object : TextWatcher {
                            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, d: Int) {}
                            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, d: Int) {}
                            override fun afterTextChanged(s: Editable?) { if (tag != "cargando") ed.sucio = true }
                        })
                        alMoverSeleccion = { tick++ }
                        ed.vista = this
                    }
                },
                modifier = Modifier.fillMaxSize(),
                update = { ed.vista = it },
            )
        }
        Hueco(4)
    }
    Abajo {
        Mono(if (ed.sucio) "sin guardar" else "guardado", 10.sp, if (ed.sucio) c.amb else c.muted, mayus = true, modifier = Modifier.weight(1f))
        Boton("vista previa →") { ed.volcar(); est.pantalla = Pantalla.VISTA }
    }
}

private fun cambiarParte(ed: Edicion, n: Int) {
    ed.volcar()
    ed.idx = n
    ed.vista?.let {
        it.tag = "cargando"
        it.setText(Formato.aSpanned(ed.partes[n]))
        it.tag = null
    }
}

@Composable
private fun Tecla(t: String, on: Boolean, italica: Boolean = false, ancho: Boolean = false, onClick: () -> Unit) {
    Box(
        Modifier.heightIn(min = 36.dp).then(if (ancho) Modifier else Modifier.width(40.dp))
            .border(1.dp, if (on) c.red else c.rule)
            .clickable(onClick = onClick).padding(horizontal = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        if (italica) Serif(t, 16.sp, if (on) c.red else c.soft, italic = true)
        else Mono(t, 13.sp, if (on) c.red else c.soft, peso = if (t == "B") androidx.compose.ui.text.font.FontWeight.Bold else androidx.compose.ui.text.font.FontWeight.Normal)
    }
}

/* ── B · Vista previa ── */

@Composable
fun ColumnScope.Vista(est: Estado, ed: Edicion) {
    val col = c
    Arriba("← editor", "vista previa", alIzq = { est.pantalla = Pantalla.EDITOR })
    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 22.dp, vertical = 24.dp)) {
        Mono(if (ed.partes.size > 1) "texto" else "nota", 10.sp, c.red, mayus = true)
        Hueco(8)
        Serif(ed.titulo.ifBlank { "(sin título)" }, 30.sp, c.ink, italic = true)
        Hueco(6)
        Mono("${fecha(Instant.now().toString()).take(5)} · ${ed.partes.sumOf { Formato.palabras(it) }} palabras", 11.sp)
        Hueco(20)
        ed.partes.forEachIndexed { i, html ->
            if (ed.partes.size > 1) {
                Hueco(14)
                Mono("— ${ed.titulosPartes.getOrNull(i)?.ifBlank { null } ?: "${i + 1}"}", 11.sp, c.red, mayus = true)
                Hueco(6)
            }
            AndroidView(factory = { ctx ->
                TextView(ctx).apply {
                    setTextColor(col.soft.toArgb())
                    typeface = Typeface.SERIF
                    setTextSize(TypedValue.COMPLEX_UNIT_SP, 18f)
                    setLineSpacing(0f, 1.45f)
                }
            }, update = { it.text = Formato.aSpanned(html) }, modifier = Modifier.fillMaxWidth())
        }
    }
    Abajo {
        Boton("← regresar", Modifier.weight(1f), primario = false) { est.pantalla = Pantalla.EDITOR }
        Boton("siguiente →", Modifier.weight(1f)) { est.pantalla = Pantalla.DESTINO }
    }
}

/* ── C · Destino ── */

@Composable
fun ColumnScope.DestinoPantalla(est: Estado, ed: Edicion) {
    var buscar by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    Arriba("← vista previa", "destino", alIzq = { est.pantalla = Pantalla.VISTA })
    Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
        Hueco(14)
        Serif(ed.titulo.ifBlank { "(sin título)" }, 20.sp, c.ink, italic = true)
        if (ed.base.esCopia) {
            Hueco(20)
            Box(Modifier.fillMaxWidth().border(1.dp, c.amb).padding(12.dp)) {
                Serif("Es una copia de «${ed.base.destino.titulo}». Al subirla, el taller compara los cambios y los incorpora en ese mismo posteo, sin duplicarlo (las acciones se conservan).", 15.sp, c.soft)
            }
        } else {
            Hueco(20)
            Mono("¿posteo nuevo?", 10.sp, mayus = true)
            Hueco(8)
            Row(Modifier.fillMaxWidth().border(1.dp, c.rule)) {
                listOf(true to "sí", false to "no").forEach { (v, t) ->
                    Box(Modifier.weight(1f).background(if (ed.posteoNuevo == v) c.red else Color.Transparent)
                        .clickable { if (ed.posteoNuevo != v) { ed.posteoNuevo = v; ed.sucio = true } }.padding(12.dp), contentAlignment = Alignment.Center) {
                        Mono(t, 12.sp, if (ed.posteoNuevo == v) Color.White else c.muted, mayus = true)
                    }
                }
            }
            if (ed.posteoNuevo) {
                Hueco(14)
                Serif("Entra a la bandeja como posteo nuevo, en borrador. Su fecha de creación será la de la subida a la bandeja.", 15.sp, c.muted)
            } else {
                Hueco(16)
                Mono("sumar a un posteo existente", 10.sp, mayus = true)
                Hueco(8)
                val q = sinTildes(buscar.trim())
                val ok = { t: String -> q.isEmpty() || sinTildes(t).contains(q) }
                val notas = est.obras.filter { it.tipo == "nota" && ok(it.titulo) }
                val textos = est.obras.filter { it.tipo != "nota" && ok(it.titulo) }
                val locales = est.borradores.filter { it.id != ed.base.id && !it.esCopia && ok(it.titulo) }
                Column(Modifier.fillMaxWidth().weight(1f).background(c.bg2).border(1.dp, c.rule)) {
                    Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                        Mono("⌕ ", 14.sp, c.ghost)
                        BasicTextField(buscar, { buscar = it }, Modifier.weight(1f), singleLine = true,
                            textStyle = TextStyle(color = c.soft, fontSize = 16.sp, fontFamily = FontFamily.Serif), cursorBrush = SolidColor(c.red),
                            decorationBox = { inner -> Box { if (buscar.isEmpty()) Serif("buscar", 16.sp, c.ghost); inner() } })
                    }
                    Linea()
                    LazyColumn(Modifier.weight(1f)) {
                        fun grupo(t: String) = item { Mono(t, 10.sp, mayus = true, modifier = Modifier.padding(start = 12.dp, top = 10.dp, bottom = 4.dp)) }
                        fun opcion(clave: String, titulo: String, tipo: String) = item {
                            val sel = ed.elegido == clave
                            Row(Modifier.fillMaxWidth().background(if (sel) c.red.copy(alpha = 0.12f) else Color.Transparent)
                                .clickable { ed.elegido = clave; ed.sucio = true }.padding(horizontal = 12.dp, vertical = 9.dp)) {
                                Serif(titulo, 16.sp, if (sel) c.red else c.ink, italic = true, modifier = Modifier.weight(1f))
                                Mono(tipo, 11.sp, c.ghost)
                            }
                        }
                        if (notas.isNotEmpty()) { grupo("notas del sitio"); notas.forEach { opcion("sitio:" + it.slug, it.titulo, "nota") } }
                        if (textos.isNotEmpty()) { grupo("textos del sitio"); textos.forEach { opcion("sitio:" + it.slug, it.titulo, "texto") } }
                        if (locales.isNotEmpty()) { grupo("borradores del tallercito"); locales.forEach { opcion("local:" + it.id, it.titulo.ifBlank { "(sin título)" }, if (it.partes.size > 1) "${it.partes.size} partes" else "borrador") } }
                        if (est.obras.isEmpty()) item { Mono("La lista de posteos se baja con conexión.", 11.sp, c.amb, modifier = Modifier.padding(12.dp)) }
                    }
                }
                val elegido = ed.elegido
                val nombre = when {
                    elegido == null -> null
                    elegido.startsWith("sitio:") -> est.obras.find { it.slug == elegido.removePrefix("sitio:") }?.titulo ?: elegido.removePrefix("sitio:")
                    else -> est.borradores.find { it.id == elegido.removePrefix("local:") }?.titulo?.ifBlank { "(sin título)" }
                }
                Hueco(8)
                Mono(nombre?.let { "se agrega al final (último lugar) de «$it»" } ?: "elegí a cuál", 11.sp, c.red)
            }
        }
        error?.let { Hueco(8); Mono(it, 12.sp, c.red) }
        Hueco(8)
    }
    Linea()
    Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Boton("guardar borrador", Modifier.fillMaxWidth()) {
            val e = est.guardar()
            if (e != null) error = e else est.aviso = "✓ borrador guardado en el celular"
        }
        Boton("retornar a la pantalla principal", Modifier.fillMaxWidth(), primario = false) { est.pedirVolver() }
    }
}

/* ── Vincular con el taller ── */

@Composable
fun ColumnScope.Vincular(est: Estado) {
    val alcance = rememberCoroutineScope()
    var codigo by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var yendo by remember { mutableStateOf(false) }
    Arriba("← principal", if (est.llave != null) "vinculado" else "sin vincular", alIzq = { est.pantalla = Pantalla.PRINCIPAL })
    Column(Modifier.weight(1f).padding(horizontal = 24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Hueco(50)
        Mono("vincular con el taller", 10.sp, mayus = true)
        Hueco(14)
        Serif("En el taller de la computadora abrí «bandeja de cambios» → «vincular celular» y escribí acá el código que aparece.", 16.sp, c.soft, align = TextAlign.Center)
        Hueco(24)
        BasicTextField(
            codigo, { codigo = it.filter(Char::isDigit).take(6); error = null },
            Modifier.width(220.dp).border(1.dp, if (codigo.length == 6) c.red else c.rule).padding(12.dp),
            textStyle = TextStyle(color = c.ink, fontSize = 28.sp, fontFamily = FontFamily.Monospace, textAlign = TextAlign.Center, letterSpacing = 8.sp),
            singleLine = true, cursorBrush = SolidColor(c.red),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
        )
        error?.let { Hueco(10); Mono(it, 12.sp, c.red, align = TextAlign.Center) }
        Hueco(30)
        Serif("Se hace una sola vez. El celular guarda una llave propia, cifrada, que solo sirve para dejar borradores en la bandeja y bajar copias del taller. Se puede revocar desde el taller.", 14.sp, c.muted, align = TextAlign.Center)
        if (est.llave != null) {
            Hueco(24)
            Mono("este celular ya está vinculado", 11.sp, c.ok)
            Hueco(10)
            Boton("desvincular", primario = false) { est.guardarLlave(null) }
        }
    }
    Abajo {
        Boton(if (yendo) "vinculando…" else "vincular", Modifier.weight(1f), habilitado = codigo.length == 6 && !yendo && est.enLinea) {
            yendo = true
            alcance.launch { error = est.vincular(codigo); yendo = false }
        }
    }
    if (!est.enLinea) Mono("Hace falta conexión para vincular.", 11.sp, c.amb, modifier = Modifier.padding(start = 16.dp, bottom = 12.dp))
}
