package space.p314b.tallercito

import android.content.Context
import android.graphics.Typeface
import android.text.Editable
import android.text.Html
import android.text.Layout
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.AlignmentSpan
import android.text.style.RelativeSizeSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import android.widget.EditText

/*  El texto del editor se guarda como HTML simple, el mismo que entiende el
    taller (sitio/tallercito-taller.js):
      <p style="text-align:center|right"> … </p>   un párrafo por renglón
      <b> <i>                                       negrita, itálica
      <font face="sans-serif|monospace">            tipografía (serif = la de siempre)
      <big> <small>                                 tamaño grande / chico          */

object Formato {
    const val GRANDE = 1.25f
    const val CHICO = 0.8f

    fun aSpanned(html: String): SpannableStringBuilder {
        val sb = SpannableStringBuilder(Html.fromHtml(html, Html.FROM_HTML_MODE_COMPACT))
        while (sb.isNotEmpty() && sb[sb.length - 1] == '\n') sb.delete(sb.length - 1, sb.length)
        return sb
    }

    fun textoPlano(html: String): String = aSpanned(html).toString()

    fun palabras(html: String): Int = textoPlano(html).split(Regex("\\s+")).count { it.isNotBlank() }

    private data class F(val b: Boolean, val i: Boolean, val cara: String?, val tam: String?)

    private fun formatoEn(t: Spanned, pos: Int): F {
        var b = false; var i = false; var cara: String? = null; var tam: String? = null
        for (s in t.getSpans(pos, pos + 1, Any::class.java)) {
            if (t.getSpanStart(s) > pos || t.getSpanEnd(s) <= pos) continue
            when (s) {
                is StyleSpan -> when (s.style) {
                    Typeface.BOLD -> b = true
                    Typeface.ITALIC -> i = true
                    Typeface.BOLD_ITALIC -> { b = true; i = true }
                }
                is TypefaceSpan -> if (s.family == "sans-serif" || s.family == "monospace") cara = s.family
                is RelativeSizeSpan -> tam = when {
                    s.sizeChange > 1.05f -> "big"
                    s.sizeChange < 0.95f -> "small"
                    else -> tam
                }
            }
        }
        return F(b, i, cara, tam)
    }

    private fun escapar(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("  ", " &#160;")

    fun aHtml(t: Spanned): String {
        val texto = t.toString()
        if (texto.isBlank()) return ""
        val sb = StringBuilder()
        var ini = 0
        while (true) {
            var fin = texto.indexOf('\n', ini)
            if (fin < 0) fin = texto.length
            var al: Layout.Alignment? = null
            for (a in t.getSpans(ini, fin, AlignmentSpan::class.java)) {
                if (t.getSpanStart(a) <= ini && t.getSpanEnd(a) >= fin) al = a.alignment
            }
            when (al) {
                Layout.Alignment.ALIGN_CENTER -> sb.append("<p style=\"text-align:center\">")
                Layout.Alignment.ALIGN_OPPOSITE -> sb.append("<p style=\"text-align:right\">")
                else -> sb.append("<p>")
            }
            var i = ini
            while (i < fin) {
                val f = formatoEn(t, i)
                var j = i + 1
                while (j < fin && formatoEn(t, j) == f) j++
                if (f.cara != null) sb.append("<font face=\"${f.cara}\">")
                if (f.tam != null) sb.append("<${f.tam}>")
                if (f.b) sb.append("<b>")
                if (f.i) sb.append("<i>")
                sb.append(escapar(texto.substring(i, j)))
                if (f.i) sb.append("</i>")
                if (f.b) sb.append("</b>")
                if (f.tam != null) sb.append("</${f.tam}>")
                if (f.cara != null) sb.append("</font>")
                i = j
            }
            sb.append("</p>\n")
            if (fin >= texto.length) break
            ini = fin + 1
        }
        return sb.toString().trimEnd()
    }

    /* ── Operaciones sobre la selección ── */

    private fun copia(s: Any): Any = when (s) {
        is StyleSpan -> StyleSpan(s.style)
        is TypefaceSpan -> TypefaceSpan(s.family ?: "serif")
        is RelativeSizeSpan -> RelativeSizeSpan(s.sizeChange)
        is AlignmentSpan.Standard -> AlignmentSpan.Standard(s.alignment)
        else -> s
    }

    /** Saca de [ini, fin) los spans que cumplen [que], cortándolos si sobresalen. */
    private fun quitar(e: Editable, ini: Int, fin: Int, parrafo: Boolean = false, que: (Any) -> Boolean) {
        for (s in e.getSpans(ini, fin, Any::class.java)) {
            if (!que(s)) continue
            val a = e.getSpanStart(s); val b = e.getSpanEnd(s)
            if (ini != fin && (b <= ini || a >= fin)) continue
            e.removeSpan(s)
            val flag = if (parrafo) Spanned.SPAN_PARAGRAPH else Spanned.SPAN_EXCLUSIVE_INCLUSIVE
            // un span de párrafo mal cortado tira excepción: se pierde ese tramo, no la app
            if (a < ini) runCatching { e.setSpan(copia(s), a, ini, if (parrafo) Spanned.SPAN_PARAGRAPH else Spanned.SPAN_EXCLUSIVE_EXCLUSIVE) }
            if (b > fin) runCatching { e.setSpan(copia(s), fin, b, flag) }
        }
    }

    private fun marcar(e: Editable, ini: Int, fin: Int, span: Any) =
        e.setSpan(span, ini, fin, if (ini == fin) Spanned.SPAN_INCLUSIVE_INCLUSIVE else Spanned.SPAN_EXCLUSIVE_INCLUSIVE)

    fun tiene(e: Spanned, ini: Int, fin: Int, estilo: Int): Boolean {
        if (ini == fin) return ini > 0 && formatoEn(e, ini - 1).let { if (estilo == Typeface.BOLD) it.b else it.i }
        return (ini until fin).all { formatoEn(e, it).let { f -> if (estilo == Typeface.BOLD) f.b else f.i } }
    }

    fun alternar(ed: EditText, estilo: Int) {
        val e = ed.text; val ini = ed.selectionStart; val fin = ed.selectionEnd
        val ya = tiene(e, ini, fin, estilo)
        quitar(e, ini, fin) { it is StyleSpan && (it.style == estilo) }
        if (!ya) marcar(e, ini, fin, StyleSpan(estilo))
    }

    fun normal(ed: EditText) {
        val e = ed.text; val ini = ed.selectionStart; val fin = ed.selectionEnd
        quitar(e, ini, fin) { it is StyleSpan || it is TypefaceSpan || it is RelativeSizeSpan }
    }

    /** "serif" (la de siempre), "sans-serif" o "monospace". */
    fun fuente(ed: EditText, familia: String) {
        val e = ed.text; val ini = ed.selectionStart; val fin = ed.selectionEnd
        quitar(e, ini, fin) { it is TypefaceSpan }
        if (familia != "serif") marcar(e, ini, fin, TypefaceSpan(familia))
    }

    /** null = normal. */
    fun tamano(ed: EditText, factor: Float?) {
        val e = ed.text; val ini = ed.selectionStart; val fin = ed.selectionEnd
        quitar(e, ini, fin) { it is RelativeSizeSpan }
        if (factor != null) marcar(e, ini, fin, RelativeSizeSpan(factor))
    }

    fun alinear(ed: EditText, al: Layout.Alignment) {
        val e = ed.text; val t = e.toString()
        val ini = t.lastIndexOf('\n', (ed.selectionStart - 1).coerceAtLeast(0)).let { if (ed.selectionStart == 0) 0 else it + 1 }
        val n = t.indexOf('\n', ed.selectionEnd)
        val fin = if (n < 0) t.length else n + 1
        quitar(e, ini, fin, parrafo = true) { it is AlignmentSpan }
        if (al != Layout.Alignment.ALIGN_NORMAL && fin > ini) runCatching { e.setSpan(AlignmentSpan.Standard(al), ini, fin, Spanned.SPAN_PARAGRAPH) }
    }

    fun alineacionEn(e: Spanned, pos: Int): Layout.Alignment {
        val t = e.toString()
        val ini = if (pos == 0) 0 else t.lastIndexOf('\n', pos - 1) + 1
        var al = Layout.Alignment.ALIGN_NORMAL
        for (a in e.getSpans(ini, ini, AlignmentSpan::class.java)) al = a.alignment
        return al
    }

    fun familiaEn(e: Spanned, pos: Int): String = if (pos <= 0) "serif" else formatoEn(e, pos - 1).cara ?: "serif"
    fun tamanoEn(e: Spanned, pos: Int): String? = if (pos <= 0) null else formatoEn(e, pos - 1).tam
}

/** EditText que avisa cuando se mueve la selección (para la barra). */
class EditorTexto(ctx: Context) : EditText(ctx) {
    var alMoverSeleccion: (() -> Unit)? = null
    override fun onSelectionChanged(selStart: Int, selEnd: Int) {
        super.onSelectionChanged(selStart, selEnd)
        alMoverSeleccion?.invoke()
    }
}
