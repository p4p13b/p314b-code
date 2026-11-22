package space.p314b.tallercito

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import java.time.Instant
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/* ── Modelo ── */

/** Una parte del borrador: una nota, o un capítulo de una copia del taller. */
data class Parte(val titulo: String = "", val html: String = "", val origenCapitulo: String? = null)

/** Adónde va al subir: posteo nuevo, sumar a uno del sitio, o copia que vuelve. */
data class Destino(val tipo: String = "nuevo", val slug: String = "", val titulo: String = "")

data class Borrador(
    val id: String = UUID.randomUUID().toString(),
    val titulo: String = "",
    val partes: List<Parte> = listOf(Parte()),
    val destino: Destino = Destino(),
    val creado: String = Instant.now().toString(),
    val modificado: String = Instant.now().toString(),
) {
    val esCopia get() = destino.tipo == "copia"
}

/** Un posteo del sitio (de corpus.json), para «sumar a un posteo existente». */
data class ObraSitio(val slug: String, val titulo: String, val tipo: String)

fun Parte.json() = JSONObject().put("titulo", titulo).put("html", html)
    .put("origen", origenCapitulo?.let { JSONObject().put("capitulo", it) } ?: JSONObject.NULL)

fun Destino.json() = JSONObject().put("tipo", tipo).put("slug", slug).put("titulo", titulo)

fun Borrador.json() = JSONObject().put("id", id).put("titulo", titulo)
    .put("partes", JSONArray(partes.map { it.json() }))
    .put("destino", destino.json()).put("creado", creado).put("modificado", modificado)

fun parteDe(o: JSONObject) = Parte(
    o.optString("titulo"), o.optString("html"),
    o.optJSONObject("origen")?.optString("capitulo")?.takeIf { it.isNotEmpty() },
)

fun destinoDe(o: JSONObject?) = if (o == null) Destino() else Destino(o.optString("tipo", "nuevo"), o.optString("slug"), o.optString("titulo"))

fun borradorDe(o: JSONObject): Borrador {
    val ps = o.optJSONArray("partes") ?: JSONArray()
    return Borrador(
        id = o.optString("id").ifEmpty { UUID.randomUUID().toString() },
        titulo = o.optString("titulo"),
        partes = (0 until ps.length()).map { parteDe(ps.getJSONObject(it)) }.ifEmpty { listOf(Parte()) },
        destino = destinoDe(o.optJSONObject("destino")),
        creado = o.optString("creado").ifEmpty { Instant.now().toString() },
        modificado = o.optString("modificado").ifEmpty { Instant.now().toString() },
    )
}

/* ── Memoria local: todo queda en el celular hasta que se sube ── */

class Almacen(ctx: Context) {
    private val dir = ctx.filesDir

    private fun leer(nombre: String): String? = File(dir, nombre).takeIf { it.exists() }?.readText()
    private fun escribir(nombre: String, texto: String) {
        val tmp = File(dir, "$nombre.tmp")
        tmp.writeText(texto)
        tmp.renameTo(File(dir, nombre))
    }

    fun borradores(): List<Borrador> = try {
        val a = JSONArray(leer("borradores.json") ?: "[]")
        (0 until a.length()).map { borradorDe(a.getJSONObject(it)) }
    } catch (e: Exception) { emptyList() }

    fun guardarBorradores(l: List<Borrador>) = escribir("borradores.json", JSONArray(l.map { it.json() }).toString())

    fun obras(): List<ObraSitio> = try {
        val a = JSONArray(leer("obras.json") ?: "[]")
        (0 until a.length()).map { a.getJSONObject(it).let { o -> ObraSitio(o.getString("slug"), o.getString("titulo"), o.getString("tipo")) } }
    } catch (e: Exception) { emptyList() }

    fun guardarObras(l: List<ObraSitio>) = escribir("obras.json",
        JSONArray(l.map { JSONObject().put("slug", it.slug).put("titulo", it.titulo).put("tipo", it.tipo) }).toString())

    /** Lo que se estaba editando, por si Android cierra la app en el medio. */
    fun sesion(): JSONObject? = try { leer("sesion.json")?.let { JSONObject(it) } } catch (e: Exception) { null }
    fun guardarSesion(o: JSONObject?) { if (o == null) File(dir, "sesion.json").delete() else escribir("sesion.json", o.toString()) }
}

/* ── La llave del celular, cifrada con el almacén de claves de Android ── */

class Llave(ctx: Context) {
    private val prefs = ctx.getSharedPreferences("llave", Context.MODE_PRIVATE)
    private val alias = "tallercito"

    private fun clave(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        kg.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build()
        )
        return kg.generateKey()
    }

    fun guardar(llave: String?) {
        if (llave == null) { prefs.edit().remove("v").apply(); return }
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, clave())
        val ct = c.doFinal(llave.toByteArray())
        prefs.edit().putString("v", Base64.encodeToString(c.iv, Base64.NO_WRAP) + ":" + Base64.encodeToString(ct, Base64.NO_WRAP)).apply()
    }

    fun leer(): String? = try {
        val v = prefs.getString("v", null) ?: return null
        val (iv, ct) = v.split(":").map { Base64.decode(it, Base64.NO_WRAP) }
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, clave(), GCMParameterSpec(128, iv))
        String(c.doFinal(ct))
    } catch (e: Exception) { null }
}

/* ── Red: el buzón del sitio (worker/tallercito.js) ── */

class ErrorRed(val codigo: Int, mensaje: String) : Exception(mensaje)

object Red {
    const val BASE = "https://www.p314b.space"

    /** Bloqueante: llamar desde Dispatchers.IO. */
    fun pedir(ruta: String, cuerpo: JSONObject? = null, llave: String? = null): JSONObject {
        val con = URL(BASE + ruta).openConnection() as HttpURLConnection
        try {
            con.connectTimeout = 15000
            con.readTimeout = 30000
            con.setRequestProperty("Accept", "application/json")
            con.setRequestProperty("User-Agent", "tallercito-android")
            if (llave != null) con.setRequestProperty("Authorization", "Tallercito $llave")
            if (cuerpo != null) {
                con.requestMethod = "POST"
                con.doOutput = true
                con.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                con.outputStream.use { it.write(cuerpo.toString().toByteArray()) }
            }
            val cod = con.responseCode
            val txt = (if (cod in 200..299) con.inputStream else con.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            val o = try { JSONObject(txt) } catch (e: Exception) { JSONObject() }
            if (cod !in 200..299) throw ErrorRed(cod, o.optString("error").ifEmpty { "el sitio respondió $cod" })
            return o
        } finally { con.disconnect() }
    }

    /** Los posteos de texto y nota publicados (para sumar a uno). */
    fun obrasDelSitio(): List<ObraSitio> {
        val con = URL("$BASE/corpus.json").openConnection() as HttpURLConnection
        try {
            con.connectTimeout = 15000
            con.readTimeout = 30000
            val o = JSONObject(con.inputStream.bufferedReader().use { it.readText() })
            val a = o.optJSONArray("obras") ?: JSONArray()
            return (0 until a.length()).map { a.getJSONObject(it) }
                .filter { it.optString("tipo_nodo") == "post" && it.optString("tipo") != "pdf" }
                .map { ObraSitio(it.getString("id"), it.optString("titulo").trim().ifEmpty { it.getString("id") }, if (it.optString("tipo") == "nota") "nota" else "texto") }
        } finally { con.disconnect() }
    }
}
