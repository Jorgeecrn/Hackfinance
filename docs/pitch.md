# Pitch y documento de una cara (borrador)

## Documento de una cara (texto para el PDF)

**Centinela: la IA que protege a tus padres de las estafas por mensaje**

**El problema.** Cada día llegan SMS y WhatsApp que suplantan a bancos, Correos o la DGT, y el timo del «hijo en apuros» («Hola mamá, este es mi número nuevo»). En enero de 2026 la Policía Nacional y la Guardia Civil lanzaron una alerta conjunta sobre este fraude, y ya hay casos en España con notas de voz con voz clonada por IA. Las víctimas suelen ser personas mayores. Los filtros actuales solo cubren SMS, solo en algunos móviles, no explican nada y no implican ni a la familia ni al banco.

**La solución.** Centinela es una app que revisa los mensajes, capturas y notas de voz que recibe una persona mayor:
1. Un **agente de IA (Claude)** investiga el mensaje: comprueba si el enlace imita a un banco o es una web recién creada, si el teléfono es extranjero o no está en sus contactos, si la cuenta bancaria es de otro país, y lo compara con estafas conocidas.
2. Da un veredicto 🟢🟡🔴 **con las pruebas** y lo **explica en voz alta** con palabras sencillas (**ElevenLabs**), incluso con la voz de un familiar.
3. **Avisa al familiar de confianza** al momento.
4. Si el timo es grave, activa el **escudo bancario**: el banco retiene los pagos a cuentas nuevas hasta que el familiar los revise. Se corta el momento en que el dinero sale.

**Valor diferencial.**
- No es un filtro de spam: **investiga y enseña pruebas comprobadas**.
- **Voz:** analiza notas de voz y habla al usuario. Accesible para quien ve mal o no sabe copiar y pegar.
- **Familia y banco en el circuito:** es el único que actúa sobre el dinero.
- Funciona en **cualquier móvil** (PWA), con un modo de respaldo sin IA.

**Resultados** (rellenar con `eval/resultados_ia.md`): precisión X %, recall Y %, falsas alarmas Z %, respuesta media N s sobre M mensajes etiquetados.

**Modelo de negocio.** B2B2C: marca blanca dentro de la app del banco (interruptor en *Ajustes → Protección contra estafas*). El banco paga por cliente protegido porque reduce fraude, reclamaciones y daño reputacional, y la nueva normativa europea de pagos (PSR) responsabiliza a las entidades sin controles antifraude adecuados. Además, B2C: suscripción que pagan los hijos para sus padres. Coste por análisis: céntimos (medirlo con los tokens y minutos reales).

---

## Estructura de las diapositivas (6–8)

1. **Gancho:** captura real de un «Hola mamá, este es mi número nuevo». «¿Lo habría detectado tu madre?»
2. **Problema:** datos y alertas oficiales, voz clonada, los mayores como objetivo, por qué fallan los filtros actuales.
3. **Solución:** el flujo en 4 pasos (investiga, explica con voz, avisa a la familia, frena el dinero).
4. **Demo en directo** (o vídeo de respaldo).
5. **Arquitectura:** diagrama del README. Claude con tool use + salida estructurada, ElevenLabs Scribe + TTS, reglas como red de seguridad.
6. **Resultados:** tabla de evaluación (reglas frente a IA) y latencia.
7. **Negocio:** quién paga, coste por análisis, competencia (Google Messages, Truecaller, filtros de operadora).
8. **Siguiente fase:** app Android que lee las notificaciones, llamadas, integración real con bancos.

## Preguntas probables del jurado

- **¿Y si la IA se equivoca o se inventa algo?** Los hechos salen de herramientas deterministas (RDAP, validación de IBAN, contactos). La IA solo decide y explica. Además hay red de seguridad: con pruebas objetivas fuertes nunca damos verde, y si la IA falla responde el motor de reglas.
- **¿Cómo lee los mensajes de WhatsApp?** En la PWA: «Compartir → Centinela», captura o nota de voz. En producción: app Android con permiso de acceso a notificaciones (el mismo backend). iPhone no permite leer mensajes a ninguna app, así que ahí la vía es compartir.
- **¿Privacidad / RGPD?** Activación voluntaria (interruptor), solo se analizan mensajes recibidos o compartidos, no se guarda audio y las alertas guardan un resumen mínimo. Procesamiento en la UE en producción.
- **¿Qué pasa con las falsas alarmas?** Las medimos (tabla) y el sistema está diseñado para evitarlas: SMS reales con código, familiares guardados, avisos informativos.
- **¿Por qué lo pagaría un banco?** Menos fraude y reclamaciones, mejor reputación, cumplimiento de los controles antifraude que exige la nueva normativa, y es diferenciador para captar clientes sénior.
- **¿Qué aporta ElevenLabs de verdad?** Las notas de voz son el canal del timo moderno: sin transcripción no se pueden analizar. Y el aviso hablado hace la app usable para quien ve mal o no lee bien. Medidlo: tiempo para entender el aviso leyendo frente a escuchando.
- **¿Coste por análisis?** Medid una ejecución real (tokens de entrada y salida de Claude y caracteres de TTS) y dad el número.
