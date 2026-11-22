package space.p314b.tallercito

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog

/* Colores del sitio: oscuro (negro, tinta clara, rojo) y claro (blanco y rojo). */
data class Colores(
    val bg: Color, val bg2: Color, val ink: Color, val soft: Color, val muted: Color,
    val ghost: Color, val rule: Color, val red: Color, val amb: Color, val ok: Color,
)

val OSCURO = Colores(
    Color(0xFF000000), Color(0xFF0B0B0B), Color(0xFFF5F5F5), Color(0xFFCFCFCF), Color(0xFF8D8D8D),
    Color(0xFF5A5A5A), Color(0x21FFFFFF), Color(0xFFE0393A), Color(0xFFD9A441), Color(0xFF6FAE6A),
)
val CLARO = Colores(
    Color(0xFFFAFAFA), Color(0xFFF0F0F0), Color(0xFF111111), Color(0xFF333333), Color(0xFF5E5E5E),
    Color(0xFF8A8A8A), Color(0x24111111), Color(0xFFC62A2A), Color(0xFF9A6B12), Color(0xFF3F6B3A),
)

val LocalColores = staticCompositionLocalOf { OSCURO }
val c: Colores @Composable get() = LocalColores.current

@Composable
fun Tema(contenido: @Composable () -> Unit) {
    val col = if (isSystemInDarkTheme()) OSCURO else CLARO
    CompositionLocalProvider(LocalColores provides col) {
        Box(Modifier.background(col.bg)) { contenido() }
    }
}

/** Texto serif (el del sitio). */
@Composable
fun Serif(t: String, size: TextUnit = 17.sp, color: Color = c.soft, italic: Boolean = false, modifier: Modifier = Modifier, align: TextAlign? = null) =
    BasicText(t, modifier, TextStyle(color = color, fontSize = size, fontFamily = FontFamily.Serif,
        fontStyle = if (italic) FontStyle.Italic else FontStyle.Normal, lineHeight = size * 1.4, textAlign = align ?: TextAlign.Start))

/** Texto mono (etiquetas, datos). */
@Composable
fun Mono(t: String, size: TextUnit = 11.sp, color: Color = c.muted, mayus: Boolean = false, modifier: Modifier = Modifier, align: TextAlign? = null, peso: FontWeight = FontWeight.Normal) =
    BasicText(if (mayus) t.uppercase() else t, modifier, TextStyle(color = color, fontSize = size, fontFamily = FontFamily.Monospace,
        letterSpacing = if (mayus) 0.12.em else 0.em, fontWeight = peso, textAlign = align ?: TextAlign.Start))

@Composable
fun Boton(texto: String, modifier: Modifier = Modifier, primario: Boolean = true, habilitado: Boolean = true, color: Color? = null, onClick: () -> Unit) {
    val rojo = color ?: c.red
    Box(
        modifier
            .alpha(if (habilitado) 1f else 0.4f)
            .then(if (primario) Modifier.background(rojo, RoundedCornerShape(2.dp)) else Modifier.border(1.dp, if (color != null) rojo else c.rule, RoundedCornerShape(2.dp)))
            .clickable(enabled = habilitado, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        contentAlignment = Alignment.Center,
    ) {
        Mono(texto, 12.sp, if (primario) Color.White else (color ?: c.soft), mayus = true, align = TextAlign.Center, peso = FontWeight.Medium)
    }
}

@Composable
fun Interruptor(on: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp, 24.dp)
            .border(1.dp, if (on) c.red else c.rule, RoundedCornerShape(12.dp))
            .background(if (on) c.red.copy(alpha = 0.15f) else Color.Transparent, RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
    ) {
        Box(
            Modifier.offset(x = if (on) 23.dp else 3.dp, y = 4.dp).size(16.dp)
                .background(if (on) c.red else c.ghost, CircleShape)
        )
    }
}

@Composable
fun Linea() = Box(Modifier.fillMaxWidth().height(1.dp).background(c.rule))

/** Diálogo con título, texto y botones (de arriba hacia abajo). */
@Composable
fun Dialogo(titulo: String, texto: String, botones: List<Triple<String, Boolean, () -> Unit>>, alCerrar: () -> Unit) {
    Dialog(onDismissRequest = alCerrar) {
        Column(
            Modifier.fillMaxWidth().background(c.bg2).border(1.dp, c.red).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Serif(titulo, 22.sp, c.ink, italic = true)
            Serif(texto, 15.sp, c.muted)
            Spacer(Modifier.height(8.dp))
            botones.forEach { (t, prim, f) -> Boton(t, Modifier.fillMaxWidth(), primario = prim, onClick = f) }
        }
    }
}

@Composable
fun Hueco(alto: Int) = Spacer(Modifier.height(alto.dp))

@Composable
fun Ancho(ancho: Int) = Spacer(Modifier.width(ancho.dp))
