package space.p314b.tallercito

import android.app.KeyguardManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.toMutableStateList
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.time.Instant

enum class Pantalla { PRINCIPAL, EDITOR, VISTA, DESTINO, VINCULAR }

/** Lo que se está editando: vive en memoria hasta «guardar borrador». */
class Edicion(val base: Borrador, val esNuevo: Boolean) {
    var titulo by mutableStateOf(base.titulo)
    val partes = base.partes.map { it.html }.toMutableStateList()
    val titulosPartes = base.partes.map { it.titulo }
    val origenes = base.partes.map { it.origenCapitulo }
    var idx by mutableIntStateOf(0)
    var sucio by mutableStateOf(false)
    var posteoNuevo by mutableStateOf(base.destino.tipo != "existente")
    /** "sitio:<slug>" o "local:<id de borrador>". */
    var elegido by mutableStateOf<String?>(if (base.destino.tipo == "existente") "sitio:" + base.destino.slug else null)
    var vista: EditorTexto? = null

    /** Pasa lo que hay en el editor a la parte actual. */
    fun volcar() {
        vista?.let { partes[idx] = Formato.aHtml(it.text) }
    }

    fun json(): JSONObject = JSONObject().put("base", base.json()).put("nuevo", esNuevo).put("titulo", titulo)
        .put("partes", JSONArray(partes.toList())).put("idx", idx).put("sucio", sucio)
        .put("posteoNuevo", posteoNuevo).put("elegido", elegido ?: JSONObject.NULL)

    companion object {
        fun de(o: JSONObject): Edicion {
            val ps = o.getJSONArray("partes")
            val base = borradorDe(o.getJSONObject("base"))
            val e = Edicion(base.copy(partes = base.partes.mapIndexed { i, p -> p.copy(html = ps.optString(i, p.html)) }), o.optBoolean("nuevo"))
            e.titulo = o.optString("titulo")
            e.idx = o.optInt("idx").coerceIn(0, e.partes.size - 1)
            e.sucio = o.optBoolean("sucio")
            e.posteoNuevo = o.optBoolean("posteoNuevo", true)
            e.elegido = o.optString("elegido").takeIf { it.isNotEmpty() && it != "null" }
            return e
        }
    }
}

class Estado(val almacen: Almacen, private val llaves: Llave) {
    var borradores by mutableStateOf(almacen.borradores())
    var obras by mutableStateOf(almacen.obras())
    var llave by mutableStateOf(llaves.leer())
    var enLinea by mutableStateOf(false)
    val seleccion = mutableStateListOf<String>()
    var pantalla by mutableStateOf(Pantalla.PRINCIPAL)
    var aviso by mutableStateOf<String?>(null)
    var ocupado by mutableStateOf(false)
    var ed by mutableStateOf<Edicion?>(null)
    var pedirDesbloqueo: (titulo: String, accion: () -> Unit) -> Unit = { _, a -> a() }
    /** Se muestra «¿Querés descartar el contenido?». */
    var confirmarVolver by mutableStateOf(false)

    /** Volver a la pantalla principal: si hay cambios sin guardar, pregunta. */
    fun pedirVolver() {
        val e = ed ?: run { pantalla = Pantalla.PRINCIPAL; return }
        if (e.sucio) confirmarVolver = true else cerrarEdicion()
    }

    private fun guardarLista(l: List<Borrador>) {
        borradores = l
        almacen.guardarBorradores(l)
        seleccion.retainAll(l.map { it.id }.toSet())
    }

    fun nuevo() {
        ed = Edicion(Borrador(), esNuevo = true)
        pantalla = Pantalla.EDITOR
    }

    fun abrir(b: Borrador) {
        ed = Edicion(b, esNuevo = false)
        pantalla = Pantalla.EDITOR
    }

    fun cerrarEdicion() {
        ed = null
        almacen.guardarSesion(null)
        pantalla = Pantalla.PRINCIPAL
    }

    /** «Guardar borrador»: queda en el celular, con su fecha de modificación. */
    fun guardar(): String? {
        val e = ed ?: return null
        e.volcar()
        val ahora = Instant.now().toString()
        val partes = e.partes.indices.map { Parte(e.titulosPartes.getOrElse(it) { "" }, e.partes[it], e.origenes.getOrNull(it)) }
        val elegido = e.elegido
        if (!e.base.esCopia && !e.posteoNuevo && elegido == null) return "Elegí a qué posteo se suma."
        val lista = borradores.toMutableList()
        val pos = lista.indexOfFirst { it.id == e.base.id }
        if (!e.base.esCopia && !e.posteoNuevo && elegido!!.startsWith("local:")) {
            // Sumar a un borrador del tallercito: se arma un texto por acumulación,
            // siempre al final.
            val destinoId = elegido.removePrefix("local:")
            val i = lista.indexOfFirst { it.id == destinoId }
            if (i < 0) return "Ese borrador ya no está."
            val t = lista[i]
            val suma = partes.map { it.copy(titulo = it.titulo.ifEmpty { e.titulo.trim() }, origenCapitulo = null) }
            lista[i] = t.copy(partes = t.partes + suma, modificado = ahora)
            if (pos >= 0) lista.removeAt(pos)
        } else {
            val destino = when {
                e.base.esCopia -> e.base.destino
                e.posteoNuevo -> Destino()
                else -> elegido!!.removePrefix("sitio:").let { slug -> Destino("existente", slug, obras.find { it.slug == slug }?.titulo ?: slug) }
            }
            val b = e.base.copy(titulo = e.titulo.trim(), partes = partes, destino = destino, modificado = ahora)
            if (pos >= 0) lista[pos] = b else lista.add(0, b)
        }
        guardarLista(lista)
        cerrarEdicion()
        return null
    }

    fun descartarSeleccion() {
        val sel = seleccion.toSet()
        guardarLista(borradores.filter { it.id !in sel })
        aviso = "${sel.size} borrador${if (sel.size == 1) "" else "es"} descartado${if (sel.size == 1) "" else "s"}"
    }

    fun guardarLlave(l: String?) { llaves.guardar(l); llave = l }

    /** Baja las copias del taller y la lista de posteos del sitio. */
    suspend fun sincronizar() {
        if (!enLinea) return
        runCatching { withContext(Dispatchers.IO) { Red.obrasDelSitio() } }.onSuccess { o ->
            if (o.isNotEmpty()) { obras = o; almacen.guardarObras(o) }
        }
        val l = llave ?: return
        try {
            val r = withContext(Dispatchers.IO) { Red.pedir("/api/tallercito/salientes", null, l) }
            val a = r.optJSONArray("copias") ?: JSONArray()
            if (a.length() == 0) return
            val ids = mutableListOf<String>()
            val nuevos = (0 until a.length()).map { a.getJSONObject(it) }.map { o ->
                ids.add(o.getString("id"))
                val ps = o.optJSONArray("partes") ?: JSONArray()
                Borrador(
                    id = "copia-" + o.getString("id"),
                    titulo = o.optString("titulo"),
                    partes = (0 until ps.length()).map { parteDe(ps.getJSONObject(it)) }.ifEmpty { listOf(Parte()) },
                    destino = destinoDe(o.optJSONObject("destino")),
                    creado = o.optString("enviado").ifEmpty { Instant.now().toString() },
                )
            }.filter { n -> borradores.none { it.id == n.id } }
            guardarLista(nuevos + borradores)
            withContext(Dispatchers.IO) { Red.pedir("/api/tallercito/salientes/recibido", JSONObject().put("ids", JSONArray(ids)), l) }
            if (nuevos.isNotEmpty()) aviso = "↓ llegó${if (nuevos.size == 1) " 1 copia" else "ron ${nuevos.size} copias"} desde el taller"
        } catch (e: ErrorRed) {
            if (e.codigo == 401) { guardarLlave(null); aviso = "El taller revocó este celular: vinculalo de nuevo." }
        } catch (e: Exception) { /* sin red estable: se intenta la próxima vez */ }
    }

    /** Sube lo seleccionado a la bandeja: entra como borrador, no se publica. */
    suspend fun subir() {
        val l = llave ?: run { pantalla = Pantalla.VINCULAR; return }
        val sel = borradores.filter { it.id in seleccion }
        if (sel.isEmpty()) return
        ocupado = true
        try {
            val cuerpo = JSONObject().put("borradores", JSONArray(sel.map { it.json().put("idLocal", it.id) }))
            val r = withContext(Dispatchers.IO) { Red.pedir("/api/tallercito/subir", cuerpo, l) }
            val ok = r.optJSONArray("ok") ?: JSONArray()
            val subidos = (0 until ok.length()).map { ok.getJSONObject(it).optString("idLocal") }.toSet()
            guardarLista(borradores.filter { it.id !in subidos })
            aviso = "✓ ${subidos.size} subido${if (subidos.size == 1) "" else "s"} a la bandeja, como borrador"
        } catch (e: ErrorRed) {
            if (e.codigo == 401) { guardarLlave(null); aviso = "El celular no está vinculado: vinculalo de nuevo." }
            else aviso = "No se pudo subir: ${e.message}"
        } catch (e: Exception) {
            aviso = "No se pudo subir (¿sin conexión?). Queda todo guardado en el celular."
        } finally { ocupado = false }
    }

    suspend fun vincular(codigo: String): String? = try {
        val r = withContext(Dispatchers.IO) {
            Red.pedir("/api/tallercito/vincular", JSONObject().put("codigo", codigo).put("nombre", Build.MANUFACTURER + " " + Build.MODEL))
        }
        guardarLlave(r.getString("llave"))
        aviso = "✓ celular vinculado con el taller"
        pantalla = Pantalla.PRINCIPAL
        sincronizar()
        null
    } catch (e: ErrorRed) { e.message } catch (e: Exception) { "Sin conexión con el sitio." }
}

class MainActivity : ComponentActivity() {
    private lateinit var est: Estado
    private var alDesbloquear: (() -> Unit)? = null

    private val confirmar = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        if (r.resultCode == RESULT_OK) alDesbloquear?.invoke()
        alDesbloquear = null
    }

    private val red = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { runOnUiThread { est.enLinea = true; lifecycleScope.launch { est.sincronizar() } } }
        override fun onLost(network: Network) { runOnUiThread { est.enLinea = hayRed() } }
    }

    private fun hayRed(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val cap = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    @Suppress("DEPRECATION")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        est = Estado(Almacen(this), Llave(this))
        est.almacen.sesion()?.let { runCatching { est.ed = Edicion.de(it); est.pantalla = Pantalla.EDITOR } }
        est.enLinea = hayRed()
        // Descartar pide el desbloqueo del celular (PIN, patrón o huella).
        est.pedirDesbloqueo = { titulo, accion ->
            val km = getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
            val intent = if (km.isDeviceSecure) km.createConfirmDeviceCredentialIntent(titulo, "Desbloqueá el celular para confirmar.") else null
            if (intent != null) { alDesbloquear = accion; confirmar.launch(intent) } else accion()
        }
        (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager).registerDefaultNetworkCallback(red)
        setContent {
            Tema {
                BackHandler(enabled = est.pantalla != Pantalla.PRINCIPAL) { atras() }
                App(est, ::atras)
            }
        }
    }

    /** Atrás del celular: un paso hacia la pantalla principal. */
    private fun atras() {
        when (est.pantalla) {
            Pantalla.VISTA -> est.pantalla = Pantalla.EDITOR
            Pantalla.DESTINO -> est.pantalla = Pantalla.VISTA
            Pantalla.VINCULAR -> est.pantalla = Pantalla.PRINCIPAL
            Pantalla.EDITOR -> est.pedirVolver()
            Pantalla.PRINCIPAL -> finish()
        }
    }

    override fun onResume() {
        super.onResume()
        lifecycleScope.launch { est.sincronizar() }
    }

    override fun onStop() {
        super.onStop()
        est.ed?.let { it.volcar(); est.almacen.guardarSesion(it.json()) }
    }

    override fun onDestroy() {
        runCatching { (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager).unregisterNetworkCallback(red) }
        super.onDestroy()
    }
}
