# Texto a 3D multi-proveedor: oMLX con fallback Ollama

Fecha original: 2026-07-18
Revisión arquitectónica: 2026-07-19
Estado: diseño aprobado; integrado al programa Local Asset Compiler

## 0. Correcciones adversariales obligatorias

Este documento especializa Texto→3D. `2026-07-19-local-asset-compiler-program-design.md` gobierna el programa; `2026-07-19-profile-policy-design.md` gobierna perfiles; `2026-07-19-benchmark-arena-model-registry-design.md` gobierna promoción. El diseño padre `2026-07-19-end-to-end-asset-pipeline-design.md` prevalece cuando exista conflicto sobre seguridad, ciclo de vida, assets o concurrencia.

Cambios vinculantes tras revisión independiente:

- El modelo no generará JavaScript ejecutable: producirá CSG IR JSON declarativa, versionada y allowlisted. Parser/compilador confiable aplicará límites de schema, nodos, profundidad y coste.
- IPC será por operación: `start(request) -> operationId` generado por main, eventos de progreso, `cancel(operationId)` y `result(operationId)`. No existirá controlador global compartido.
- Renderer nunca enviará o recibirá rutas arbitrarias ni STL/base64 voluminoso. Usará IDs opacos resueltos por un repositorio main-owned, con confinamiento, cuotas, TTL y escritura atómica.
- oMLX admite solo URL WHATWG `http` de loopback, origen exacto, sin credenciales embebidas, redirects ni proxy. La clave queda ligada al origen y fuera de procesos hijos.
- Un timeout no habilita fallback GPU hasta confirmar terminación del proveedor primario. Si no puede confirmarse, falla como `primary_may_still_be_running`.
- Modelos con capacidad desconocida quedan solo en selección manual. La selección automática usa allowlist de capacidades verificadas y métricas Pareto; no un score escalar ni coincidencias de nombre.
- Selección manual de Ollama no cambia silenciosamente a oMLX. Selección automática/oMLX puede usar un fallback Ollama congelado al iniciar la operación.
- Historial antiguo se migra por tipo: imagen/STL→Ollama, GLB→Hunyuan, desconocido→`unknown`; nunca se inventa procedencia.
- Circuit breaker avanzado queda diferido hasta demostrar lifecycle, cancelación y exclusión GPU correctos.

## 1. Resultado verificable

Texto a 3D debe usar automáticamente el mejor modelo local compatible demostrado por benchmark, servido por oMLX, y recurrir una sola vez a Ollama cuando oMLX falle antes de entregar contenido. La generación conserva cancelación, reparaciones CSG IR, historial y mensajes honestos sobre proveedor/modelo.

Imagen preserva Ollama e Imagen a 3D preserva Hunyuan3D MLX y sus resultados funcionales. Sí se permiten y exigen migraciones transversales de lifecycle, seguridad, assets y readiness definidas por el diseño padre.

Éxito significa:

- STL compilable producido mediante oMLX en una prueba real.
- STL compilable producido mediante Ollama cuando oMLX se simula inaccesible.
- Cancelación efectiva durante descubrimiento, carga, completion, reparación o fallback.
- Credenciales ausentes de renderer, IPC de lectura, logs, historial y errores.
- Selección de modelos basada en capacidad y restricciones, no solo en nombres.
- Benchmark reproducible con métricas separadas de calidad, carga y generación.
- Tests, build y comprobaciones UI con código de salida cero.

## 2. Principios y límites

### Principios

1. **Dominio antes que proveedor:** la UI invoca `text3d`; no debe conocer detalles HTTP de oMLX/Ollama.
2. **Fallback explícito y acotado:** solo fallos de infraestructura antes de recibir contenido; máximo un cambio de proveedor.
3. **Seguridad local por defecto:** oMLX solo en loopback; secretos confinados al proceso Electron principal.
4. **Capacidad observable:** cada modelo tiene proveedor, tipo, límites, estado y razones de elegibilidad.
5. **Calidad medible:** no se promueve un modelo por reputación; se compara con el prompt y compilador reales.
6. **Cambios reversibles:** una variable de recuperación permite volver temporalmente a Ollama sin revertir código.
7. **Compatibilidad progresiva:** historial anterior y API oMLX estándar siguen funcionando cuando faltan extensiones específicas.

Invariantes:

- Una operación activa tiene exactamente un `operationId` generado por main, señal raíz, controller hijo por intento y como máximo dos proveedores; nunca comparte estado mutable con otra operación.
- Ningún secreto cruza una frontera IPC de lectura.
- Ninguna entrada de historial se escribe antes de existir STL final renombrado atómicamente.
- Recibir contenido fija proveedor/modelo para todas las reparaciones de esa operación.
- Descubrimiento nunca carga ni descarga modelos.

### Incluye

- Dominio Electron independiente para Texto a 3D.
- Clientes oMLX y Ollama detrás de un contrato común.
- Descubrimiento, filtrado, puntuación y selección automática.
- Credenciales oMLX y Ajustes seguros.
- Orquestación de generación, reparación, cancelación y fallback.
- Telemetría local no sensible e historial compatible.
- Tests unitarios, de contrato, integración opt-in, build y verificación UI.
- Benchmark reproducible sobre modelos ya instalados.

### Excluye

- Reemplazar proveedor/modelo de Imagen o Hunyuan3D.
- Cambiar pesos o parámetros de calidad Hunyuan3D fuera de los contratos transversales de seguridad/lifecycle.
- Descargar o eliminar modelos.
- Aplicar automáticamente el ganador del benchmark.
- Crear proxy Ollama, servicio adicional o dependencia cloud.
- Refactorizar áreas no tocadas por Texto a 3D.

## 3. Arquitectura objetivo

### 3.1 Frontera renderer

Se añadirá `window.text3d` en `electron/preload.js`:

- `status()`
- `start(request) -> operationId`
- `onProgress(operationId, listener)`
- `cancel(operationId)`
- `result(operationId)`
- `getSettingsStatus()`
- `saveSettings(input)`
- `clearStoredKey()`

Preload valida antes de `ipcRenderer.invoke` y main repite antes de construir requests: prompt 32 KiB UTF-8, model/asset/operation ID 256 B, URL 256 B, key 8 KiB, request máximo 16 campos/profundidad 3 y settings 8 campos/profundidad 2. Perfil/mode son enums, seed/temperatura/tokens números finitos acotados y no se aceptan arrays salvo schema explícito. Exceder límites rechaza antes de serializar cuerpos HTTP.

Los IPC legacy `window.ollama`/`window.hunyuan` basados en paths se retiran en Gate -1 para todos los workflows y se sustituyen por asset IDs. Texto a 3D deja de invocar `window.ollama.generateStl`. No se exponen funciones genéricas de filesystem, HTTP, cifrado ni lectura de clave.

### 3.2 Capas Electron

```text
Renderer
  -> IPC text3d
    -> Text3DOrchestrator
       -> ModelRegistry
       -> CredentialStore
       -> OmlxProvider
       -> OllamaProvider
       -> CsgIrCompiler utility process
       -> AssetRepository main-owned
```

Responsabilidades:

- **Text3DOrchestrator:** máquina de estados, intento principal, reparaciones, fallback, cancelación y resultado final.
- **ModelRegistry:** normaliza modelos, aplica restricciones y entrega conjunto Pareto y selección primaria/fallback congelada.
- **CredentialStore:** resuelve, cifra, persiste y redacta credenciales.
- **OmlxProvider:** salud, modelos y `/v1/chat/completions`.
- **OllamaProvider:** adapta `/api/tags` y `/api/generate` al mismo contrato.
- **CsgIrCompiler:** utility process desechable; valida CSG IR sin expresiones/callbacks/módulos, llama primitivas JSCAD confiables y aplica límites CPU/RSS/deadline/output. Reemplaza por completo la evaluación `node:vm`.

`electron/main.js` queda como composición e IPC. No contendrá reglas nuevas de ranking, autenticación o fallback.

### 3.3 Contrato de proveedor

Cada proveedor implementará:

```text
health({ signal }) -> ProviderHealth
listModels({ signal }) -> ModelDescriptor[]
complete({ modelId, system, prompt, seed, temperature, maxTokens, signal })
  -> CompletionResult
```

`ModelDescriptor`:

- `key`: identificador opaco y estable para UI.
- `provider`: `omlx` u `ollama`.
- `id`: identificador real del modelo.
- `label`: etiqueta segura para mostrar.
- `kind`: `llm`, `vlm`, `image`, `embedding`, `reranker`, `audio` o `unknown`.
- `loaded`, `loading`, `estimatedBytes`.
- `maxContext`, `maxOutputTokens`.
- `eligibleForText3d` y `ineligibleReason`.
- `benchmarkMetrics` solo en proceso principal/tests; la UI recibe razones de elegibilidad y posición Pareto, nunca un score único engañoso.

`CompletionResult`:

- `text` limpio, sin bloques de razonamiento separados.
- `provider`, `modelId`.
- `latencyMs`, `loadObservedMs` cuando oMLX lo informe.
- `usage` reducido a tokens de entrada/salida si existe.

## 4. Estados y flujo completo

### 4.1 Máquina de estados

```text
idle -> queued -> acquiring -> running -> releasing -> committing -> succeeded|failed
queued --cancel--> cancelled
running --cancel request--> cancelling -> releasing -> cancelled
running/generating --infra failure before content--> releasing
  -> acquiring fallback -> running -> releasing -> succeeded|failed
```

`cancelled` solo se publica tras ack del backend o kill confirmado. `cancelled` domina commit mediante CAS; un resultado tardío se descarta.

Antes de persistir, CAS exclusivo `releasing -> committing`. Si cancel gana primero se descarta temp; si `committing` gana, cancel devuelve `too_late_to_cancel`. `succeeded` requiere manifest fsync+rename completo.

Una operación tiene un `operationId`, señal raíz y controller hijo por intento/deadline. Cancelar raíz domina terminal mediante CAS; timeout aborta solo el intento y permite fallback con controller nuevo tras confirmar terminación. `cancel(operationId)` verifica owner y jamás activa fallback. El lease GPU usa estados queued/acquiring/running/releasing, cola FIFO de una, rechazo de tercera solicitud y release solo tras ack/kill.

### 4.2 Arranque y actualización de estado

1. Consultar oMLX y Ollama en paralelo con timeout corto e independiente.
2. No bloquear render por un proveedor lento; retornar estado parcial conocido.
3. Cachear descubrimiento durante 15 segundos para evitar polling costoso.
4. El refresh manual invalida caché y ejecuta una comprobación nueva.
5. Conservar último estado exitoso marcado como `stale` cuando una actualización falla.
6. No descargar ni cargar modelos durante el simple descubrimiento.

Timeouts iniciales: 2 segundos para salud/descubrimiento por proveedor y 600 segundos para completion. Ambos serán constantes testeables, no números dispersos.

### 4.3 Selección

La UI conserva un único selector de modelo en Texto a 3D. Sus entradas son descriptores unificados (`oMLX - modelo`, `Ollama - modelo`); no se añade selector independiente de proveedor.

Selección inicial automática:

1. Modelo oMLX promovido/pinneado por holdout y aún elegible.
2. Baseline estable previamente aprobado si el promovido no está disponible.
3. Sin evidencia previa, selector manual y acción `Ejecutar benchmark`; la lista provisional nunca se convierte en default runtime.

El fallback Ollama se congela al inicio desde una allowlist aprobada y verificada; si no existe, se reporta degradación en vez de elegir por nombre.

Si el usuario cambia el modelo, se conserva su elección mientras siga disponible durante la sesión. El fallback sigue activo porque fue el comportamiento aprobado, pero la UI informará el cambio de proveedor.

### 4.4 Generación

1. Congelar `operationId`, prompt, perfil, seed y selección; cambios posteriores de UI no afectan la operación activa.
2. Construir una sola vez el prompt optimizado y el schema/system prompt CSG IR.
3. Solicitar completion no streaming al proveedor primario.
4. Extraer únicamente contenido de respuesta; razonamiento separado no se concatena al código.
5. Enviar CSG IR validada al utility process confiable; compilar con primitivas JSCAD bajo límites reales. Ningún proceso evalúa código del modelo.
6. Ante error de compilación, ejecutar reparaciones con el mismo proveedor/modelo y temperatura reducida solo mientras `attempt <= maxRepairAttempts <= 2`; `maxRepairAttempts` y `effectivePlanHash` son main-owned (0/1/2 para Velocidad/Balanceado/Calidad).
7. Guardar STL mediante escritura atómica y devolver procedencia.

### 4.5 Fallback exacto

Fallback permitido si no existe contenido y el error normalizado es:

- `connection`
- `timeout`
- `authentication`
- `model_unavailable`
- `provider_overloaded`
- `empty_completion`

Fallback prohibido para:

- `cancelled`
- CSG IR inválida después de recibir contenido
- error del parser/compilador confiable
- escritura de archivo
- validación de entrada
- segundo fallo después de haber usado fallback

El máximo por operación es un proveedor primario + un proveedor fallback. Antes de arrancar fallback GPU se debe confirmar que el primario terminó y liberó recursos; en caso contrario se devuelve `primary_may_still_be_running`. Si Ollama no dispone de modelo elegible, el resultado explica ambos hechos sin perder la causa original oMLX.

## 5. Resiliencia

### 5.1 Resiliencia inicial

La primera versión usa timeout, errores normalizados, una sola transición de fallback y estado degradado observable. El circuit breaker queda diferido: se incorporará únicamente después de probar cancelación, liberación de recursos y exclusión GPU, para no ocultar carreras con un estado global prematuro.

### 5.2 Compatibilidad API

Descubrimiento oMLX:

1. Preferir `/v1/models/status` para tipo, carga, memoria y límites.
2. Si no existe, usar `/v1/models` y marcar capacidades desconocidas.
3. Nunca cargar todos los modelos para probar compatibilidad.
4. Una incompatibilidad de schema produce error seguro y fallback; no intenta adivinar estructuras arbitrarias.

Completion:

- Usar `/v1/chat/completions` OpenAI-compatible.
- Aceptar `choices[0].message.content` textual.
- Rechazar arrays/objetos no soportados con `invalid_response`.
- Limitar respuesta HTTP aceptada a 2 MiB para evitar consumo de memoria accidental.
- Mantener timeout largo de generación separado del timeout corto de salud.
- Leer respuestas como stream con corte inmediato en el byte N+1; no acumular primero para validar después.

### 5.3 Recuperación operacional

`TEXT3D_PROVIDER_MODE=ollama` fuerza temporalmente el comportamiento anterior. Es un kill switch de recuperación, no una preferencia visible ni una segunda arquitectura.

## 6. Seguridad y privacidad

### 6.1 URL

- Predeterminado: `http://127.0.0.1:8000`.
- Solo se aceptan `localhost`, `127.0.0.1` y `::1`.
- Se exige `http:`, `pathname==='/'`, `search===''`, `hash===''`, userinfo vacío y puerto válido.
- `localhost` se canonicaliza/resuelve solo a IP literal loopback; cualquier A/AAAA no-loopback se rechaza antes de adjuntar autorización.
- Se deshabilitan redirects y proxies; cada request revalida socket remoto, puerto y origen canónico exacto antes de adjuntar autorización.
- No se amplía a servidores remotos en esta entrega.

### 6.2 Credenciales

Precedencia efectiva:

1. `OMLX_API_KEY`.
2. Reemplazo cifrado guardado por Xreality Convert.
3. `auth.api_key` válido de `~/.omlx/settings.json`.

Comportamiento:

- Abrir settings mediante `open(O_NOFOLLOW)`, validar con `fstat` tipo regular/owner/tamaño máximo 1 MiB y leer por descriptor.
- Parsear únicamente el campo requerido.
- Guardar reemplazo cifrado con Electron `safeStorage` dentro de `app.getPath('userData')`.
- Escritura atómica con temp `O_EXCL|0600`, fsync y rename confinado.
- Si `safeStorage.isEncryptionAvailable()` es falso, no persistir y explicarlo; nunca degradar a texto plano.
- `clearStoredKey()` elimina solo el blob de Xreality Convert, nunca modifica settings de oMLX.

### 6.3 Redacción

- Ninguna API IPC devuelve la clave.
- Logs registran `operationId`, proveedor, modelo, categoría de error y tiempos; no prompt, código completo, headers ni cuerpos HTTP.
- Mensajes al renderer se construyen desde catálogo seguro, no desde `err.message` remoto sin sanitizar.
- Tests usan una clave centinela y fallan si aparece en cualquier payload serializado.

## 7. Elegibilidad y selección de modelos

### 7.1 Filtros duros

oMLX es elegible cuando:

- `model_type` es `llm` o `vlm`; si el endpoint no aporta tipo/capacidades, el modelo queda solo para selección manual con advertencia.
- Soporta completion textual.
- `maxOutputTokens` es conocido y al menos 4096 para selección automática general; 2048 queda manual/laboratorio o perfil simple.
- `pinned/non-evictable + target + transientReserve <= effectiveCeiling`; reserva transitoria se mide por backend/configuración. Tamaño, pinned, reserva o ceiling desconocidos impiden selección automática.
- No es helper ni está en carga fallida.

Ollama es elegible solo mediante allowlist positiva de generación textual verificada con `/api/show` y contract test. Capacidad desconocida queda manual; no se infiere por ausencia de palabras de imagen.

### 7.2 Selección inicial y promoción

La allowlist inicial contiene solo modelos inspeccionados con capacidad y límites suficientes. El nombre puede aportar una etiqueta informativa, nunca decidir elegibilidad o calidad. El orden provisional Gemma Coder 4-bit, gpt-oss-20b y Qwen3-8B sirve únicamente para ejecutar benchmark; Qwen3.5-9B (2048) queda laboratorio/perfil simple. Runtime permanece manual o usa baseline estable pinneado hasta aprobar holdout. Después, se elige dentro del frente Pareto por esta prioridad: `schemaValid@1`, compilación al primer intento, validez geométrica, latencia caliente y memoria incremental. Los empates se resuelven por menor memoria y luego `id` ascendente.

No se asumirá que `coder`, VLM, más parámetros o versión más nueva equivale a mejor JSCAD. Modelos `uncensored`/`heretic` no entran en selección automática. La UI muestra capacidad, evidencia y razón de inelegibilidad.

### 7.3 Estado local inicial

Con los modelos observados, el primer benchmark debe incluir como mínimo:

- `gemma-4-12b-coder-fable5-composer2.5-4bit` (Coder, 6.55 GB).
- `gpt-oss-20b-MXFP4-Q8` (LLM, 11.81 GB).
- `qwen3.5-9b-mlx-4bit` (VLM/texto, 5.82 GB).
- `qwen3-8b-4bit` (LLM ligero, 4.51 GB).

`Qwen3.5-9B-Fable-5-v1-oQ4` queda condicionado porque actualmente declara máximo de salida de 1500 tokens. Audio, embeddings y rerankers quedan fuera.

## 8. UI honesta

### 8.1 Indicador de sistema

El header deja de resumir todo como `Ollama - MLX local`. Mostrará estado agregado y detalles accesibles:

- `Listo`: al menos un pipeline utilizable.
- `Degradado`: Texto a 3D funciona por fallback o una dependencia no crítica falla.
- `Requiere configuración`: oMLX exige clave y no hay fallback apto.
- `Sin servicio`: ningún proveedor requerido está disponible.

### 8.2 Ajustes

Botón independiente junto al indicador abre diálogo con:

- URL oMLX local.
- Estado y origen de credencial: entorno, clave cifrada, settings o ausente; nunca valor.
- Estado de proveedor, última comprobación y errores normalizados.
- Modelos Texto a 3D elegibles e inelegibles con razón breve.
- Campo password para reemplazo.
- Guardar, eliminar reemplazo y volver a comprobar.

Guardar una clave transmite el valor solo al proceso Electron principal. Al resolver, el campo se vacía inmediatamente.

### 8.3 Generación

- Antes de ejecutar: selector etiqueta proveedor/modelo.
- Durante: estado `Generando con ...`, `Reparando intento 2/3` o `Cambiando a Ollama`.
- Después: resultado e historial muestran proveedor final, modelo, intentos y duración.
- Fallback muestra aviso persistente en esa operación, no toast efímero engañoso.
- Cancelación no muestra error rojo.

## 9. Persistencia y compatibilidad

Resultado nuevo:

```text
provider
model
duration
attempts
fallbackUsed
fallbackReason
operationId
```

El historial persiste solo procedencia segura y métricas. No persiste prompt adicional, claves, cuerpo HTTP ni código de reparación intermedio.

Entradas previas sin `provider` se clasifican por artefacto: imagen/STL→`Ollama (histórico)`, GLB→`Hunyuan (histórico)`, otro→`Proveedor desconocido`. No hay migración destructiva. Campos desconocidos se ignoran.

El STL se escribe primero a archivo temporal confinado al repositorio y luego se renombra. Renderer recibe un ID opaco, nunca una ruta. Una cancelación o fallo no deja entrada de historial ni archivo parcial; persistencia de artefacto e historial tiene una única transacción/linearización documentada.

## 10. Benchmark reproducible

### 10.1 Propósito

Comparar modelos para esta tarea concreta, no medir inteligencia general. El benchmark usa exactamente el system prompt, optimización de perfiles, extractor y compilador de producción.

### 10.2 Corpus mínimo

24 prompts versionados: cuatro categorías (paramétrico, booleanos/ensamble, objeto reconocible y XR restringido), seis prompts por categoría. Se separan desarrollo y holdout. Prompts, seed, perfil y límites quedan versionados; ninguno contiene datos privados.

### 10.3 Ejecución

- Modelos secuenciales para respetar 24 GB de memoria unificada.
- Cold se mide en sesión separada tras unload/restart autorizado. Para hot, un warmup separado y no puntuado precede ejecuciones.
- Tres seeds por prompt, orden balanceado entre modelos.
- Temperatura 0 como comparación principal; 0.2 solo como experimento separado.
- `maxTokens=min(4096, cap)` y misma política de reparación, parser y compilador CSG IR de producción; caps menores se etiquetan y truncación se reporta.
- Separar carga fría, primer token/completion cuando esté disponible y tiempo total.
- Registrar versión oMLX, modelo exacto, tamaño, estado de carga y commit de la app.
- Registrar `git rev-parse HEAD` y flag de árbol dirty; no asumir que existe commit de la entrega.
- Descargar modelos queda prohibido durante benchmark.

### 10.4 Métricas

- Compila al primer intento.
- Compila dentro de tres intentos.
- CSG IR válida al primer intento y rechazos por schema/rango/coste.
- Número de reparaciones.
- Triángulos y presencia de geometría no vacía.
- Respeto aproximado del límite de caras.
- Dimensiones finitas y no degeneradas.
- Duración fría y caliente.
- Tokens de salida, cuando el proveedor los informe.
- Pico/margen de memoria reportado por oMLX.

Se presentan métricas crudas, intervalos bootstrap 95%, frente Pareto y recomendación explicada. `pass@1` y recuperación dentro de tres intentos permanecen separados. Dimensiones, agujeros, paredes finas, topología y fidelidad funcional se revisan con reglas y evaluación humana ciega. No existe score compuesto único ni promoción automática sin aprobación del usuario.

## 11. Observabilidad

Cada operación mantiene una traza local acotada:

```text
operationId, state, provider, model, attempt, elapsedMs, errorKind
```

La traza sirve para UI/diagnóstico durante la sesión. No contiene prompt ni código generado y no se envía fuera del Mac. Los logs rotan según mecanismo existente o se mantienen solo en memoria si no existe uno seguro.

## 12. Estrategia de pruebas

### 12.1 Runner

Usar `node:test` para módulos CommonJS puros y añadir un script `npm test` explícito. Esto evita una dependencia de test innecesaria. El renderer se valida con build y navegador; solo se añadirá un runner DOM si una interacción no puede cubrirse de forma estable mediante separación de lógica.

### 12.2 Unitarias

- Normalización de modelos y claves opacas.
- Filtros duros, allowlist y selección Pareto explicable.
- Precedencia de credenciales y redacción centinela.
- Validación estricta de URL loopback.
- Traducción de respuestas oMLX/Ollama.
- Clasificación segura de errores.
- Transiciones válidas de máquina de estados.
- Política de fallback y máximo un cambio.
- Timeout sin terminación confirmada bloquea fallback GPU.
- CSG IR rechaza expresiones, `constructor`, callbacks, módulos, profundidad/nodos/coste excedidos y números no finitos.
- IPC: sender no autorizado, `operationId` ajeno, doble cancelación y resultado tardío.
- Paths: traversal, symlink y asset ID inexistente.
- Compatibilidad de historial.
- Escritura atómica mediante filesystem temporal.

### 12.3 Contrato

Servidor HTTP local efímero para comprobar requests reales:

- Authorization correcto sin imprimir secreto.
- `/v1/models/status` y degradación `/v1/models`.
- Completion válida, vacía, schema inválido, `401`, `404`, `429`, `500`, timeout y abort.
- Redirect, proxy configurado, URL ambigua, body N+1 y servidor loopback impostor.
- Ollama tags/generate adaptados al mismo contrato.

### 12.4 Integración opt-in

- oMLX local real con clave descubierta.
- Modelo pequeño ya instalado para smoke test.
- Modelo Coder elegido para validación final.
- Ollama real como fallback.

Estas pruebas no forman parte del suite rápido si requieren modelos cargados; se ejecutan explícitamente y reportan modelo/tiempo.

### 12.5 UI

- Diálogo abre/cierra y conserva foco.
- Clave nunca reaparece después de guardar.
- Estado agregado coincide con proveedores.
- Selector muestra proveedor/modelo sin duplicados.
- Aviso de fallback y cancelación son honestos.
- Sin errores de consola.

## 13. Etapas de implementación y gates

### Etapa -2: baseline read-only

- Capturar build, comportamiento y artefactos actuales antes de cualquier mutación.
- Añadir caracterización y PoC rojo controlado; registrar versiones y árbol dirty.

Gate: evidencia original reproducible; ningún cambio de producción.

### Etapa -1: contención

- Sustituir ejecución `node:vm` por CSG IR declarativa y cerrar IPC/path/server impersonation.
- Introducir `WorkflowCoordinator` y `AssetRepository` mínimos definidos por el diseño padre.

Gate: PoC de escape y pruebas adversariales P0/P1 quedan bloqueadas antes de habilitar nuevas rutas.

### Etapa 0: baseline seguro

- Repetir build y caracterización tras contención.
- Comparar contra evidencia Gate -2 y documentar cambios esperados por migración CSG IR.
- Capturar generación Ollama o documentar bloqueo externo.

Gate: contención sin regresiones no justificadas.

### Etapa 1: núcleo puro

- Contratos, errores, registry, selección Pareto y state machine por operación.
- Tests primero; sin Electron ni red real.

Gate: unitarias verdes y API del dominio revisada.

### Etapa 2: clientes y credenciales

- oMLX, adaptador Ollama, URL local, safeStorage y persistencia atómica.
- Tests de contrato con servidor efímero.

Gate: secreto centinela ausente de todos los payloads/logs de prueba.

### Etapa 3: orquestación Texto a 3D

- Completion, compilación, reparación, cancelación y fallback.
- Mantener kill switch Ollama.

Gate: matrices de estado/fallo verdes; máximo un fallback demostrado.

### Etapa 4: IPC y renderer

- `window.text3d`, modelos normalizados, estados, Ajustes e historial.
- No tocar branches Imagen/Hunyuan salvo separar referencias compartidas imprescindibles.

Gate: build verde, consola limpia y flujos no objetivo sin regresión visible.

### Etapa 5: integración real

- oMLX activo produce STL.
- Fallo oMLX controlado activa Ollama.
- Cancelación durante request real.

Gate: evidencia de proveedor/modelo, archivo válido y ausencia de secreto.

### Etapa 6: benchmark

- Ejecutar corpus sobre candidatos instalados.
- Producir reporte con métricas crudas y recomendación.

Gate: runs completos, condiciones registradas, sin cambio automático de preferencia.

### Etapa 7: revisión final

- Diff boundary.
- Tests rápidos + integración seleccionada + build + navegador.
- Revisar mensajes, historial, archivos parciales y logs.

Gate: todos los criterios de aceptación con evidencia fresca o riesgo residual explícito.

## 14. Criterios de aceptación medibles

1. oMLX elegible se selecciona automáticamente sin iniciar configuración manual.
2. Descubrimiento responde en máximo 2 segundos por proveedor o retorna estado stale/degradado.
3. Falla de conexión/auth/modelo antes de contenido produce exactamente un fallback Ollama solo tras confirmar terminación del primario.
4. Cancelación evita fallback, historial y archivo parcial.
5. Tres fallos CSG IR consumen como máximo tres completions totales, no seis.
6. Historial identifica proveedor/modelo final y renderiza entradas antiguas.
7. Clave centinela no aparece en objetos IPC serializados, logs ni mensajes UI.
8. URL no-loopback es rechazada antes de cualquier request.
9. Imagen continúa llamando exclusivamente a Ollama.
10. Imagen a 3D continúa cargando `dgrauet/hunyuan3d-2.1-mlx` sin cambios.
11. Tests unitarios/contrato/adversariales y build terminan con exit code 0.
12. Navegador muestra Ajustes, estados, selección y fallback sin errores de consola.
13. Smoke real oMLX genera STL no vacío con triángulos mayores que cero.
14. Smoke fallback genera STL o reporta de forma verificable que Ollama carece de modelo apto.
15. Benchmark registra condiciones, métricas crudas y no cambia preferencias.

## 15. Riesgos y mitigaciones

- **Modelo cargado excede memoria:** filtro con ceiling/margen; benchmark secuencial.
- **Endpoint oMLX cambia:** estándar `/v1/models` como degradación y errores de schema explícitos.
- **Clave settings cambia de formato:** campo específico, límite de tamaño y UI de reemplazo.
- **safeStorage no disponible:** bloquear persistencia, nunca texto plano.
- **Fallback oculta problemas:** aviso persistente, procedencia e historial.
- **Polling martilla servidor:** caché, timeout corto y refresh explícito; breaker diferido.
- **Cancelación pierde carrera:** `operationId` y única señal; ignorar resultados tardíos.
- **Nombre favorece modelo engañoso:** allowlist de capacidad + frente Pareto + benchmark real.
- **Benchmark confunde carga con inferencia:** métricas fría/caliente separadas.
- **Refactor rompe Imagen/Hunyuan:** boundary, tests de caracterización y verificación visual separada.

## 16. Decisiones posteriores, no bloqueantes

Después del benchmark, el usuario podrá aprobar una de estas acciones en otra entrega:

- Cambiar preferencia predeterminada al modelo ganador.
- Descargar un Coder MLX oficial adicional.
- Eliminar modelos redundantes para liberar disco.
- Ampliar oMLX a análisis visual, solo con diseño independiente.

Ninguna se anticipa en esta implementación.
