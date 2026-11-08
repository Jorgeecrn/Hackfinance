# Plan de trabajo: 3 días

La base ya funciona de principio a fin (reglas, agente, PWA, familia, banco, tests y evaluación). Los 3 días son para **conectar las claves reales, medir, pulir y preparar la presentación**. Si sois menos personas, juntad roles (A+B y C+D).

| Rol | Se encarga de |
|---|---|
| **A · IA** | Agente con Claude: prompt, herramientas, evaluación |
| **B · Voz** | ElevenLabs: notas de voz, voz de los avisos, grabación |
| **C · Frontend** | PWA: UX para mayores, accesibilidad, instalación en el móvil |
| **D · Negocio y pitch** | Datos del problema, modelo de negocio, PDF, diapositivas, guion de la demo |

## Día 1: todo funcionando con claves reales

- **Todos:** clonar, `pip install -r requirements.txt`, `cp .env.example .env`, arrancar y recorrer la demo en modo básico.
- **A:** poner `ANTHROPIC_API_KEY`, probar los 10 ejemplos de `demo.html` y ajustar `SYSTEM_PROMPT` en `backend/app/agent.py` si algún veredicto suena raro. Ejecutar `python eval/run_eval.py --modo ia` y guardar los resultados.
- **B:** poner `ELEVENLABS_API_KEY`, elegir una voz española cálida y lenta (`ELEVENLABS_VOICE_ID`), grabar 3–4 notas de voz de prueba («hola mamá, se me ha roto el móvil…») y comprobar la transcripción.
- **C:** probar la PWA en un móvil real a través de un túnel HTTPS: instalar, «Compartir → Centinela», micrófono y sonido.
- **D:** escribir el documento de una cara (borrador en `docs/pitch.md`) y el esqueleto de las diapositivas.

## Día 2: diferenciación y medición

- **A:** ampliar `eval/dataset.jsonl` con **mensajes reales** (pedid a familiares y amigos capturas de timos que les hayan llegado; quitad los datos personales). Objetivo: más de 120 mensajes. Comparar reglas frente a IA y sacar la tabla para el pitch.
- **B:** voz de un familiar con su consentimiento (clonación de voz en ElevenLabs) para el aviso «Mamá, soy Lucía, ese mensaje no es mío». Opcional: agente conversacional de ElevenLabs para preguntar «¿esto es un timo?» hablando.
- **C:** pulir textos, tamaños y contraste; probar con alguien mayor de verdad (5 minutos, sin ayuda) y apuntar dónde se atasca.
- **D:** modelo de negocio con números: coste por análisis (tokens de Claude y minutos de ElevenLabs medidos), precio B2B por cliente protegido y B2C para familias.
- **Opcional:** avisos reales por Telegram (`TELEGRAM_BOT_TOKEN`), Google Safe Browsing.

## Día 3: congelar, ensayar y entregar

- **Mañana:** congelar funcionalidades. Solo arreglos. `python -m pytest -q` en verde.
- Ensayar la demo 3 veces con el guion del README y cronómetro. Grabar un **vídeo de respaldo** por si falla la red.
- Preparar las respuestas a las preguntas del jurado (en `docs/pitch.md`).
- **Entrega:** repositorio público, `README.md` revisado, **Download ZIP** desde GitHub, PDF de una cara y PowerPoint.

## Comprobación antes de entregar

- [ ] `README.md` con instalación, configuración, ejecución y pruebas (ya está; revisad la URL del repo)
- [ ] `.env` **no** está en el repositorio (está en `.gitignore`)
- [ ] Tests en verde
- [ ] `eval/resultados_ia.md` generado con la versión final
- [ ] PDF de una cara
- [ ] Presentación (PowerPoint)
- [ ] ZIP descargado de GitHub con la última versión
- [ ] La demo que se enseña es la versión entregada (lo exige la organización)
