# FEN PIURA V2
## Documento maestro de caso, arquitectura, investigación y ejecución colaborativa

**Versión:** 2.0 (prototipo experimental)  
**Fecha:** 24 de octubre de 2026  
**Tipo de proyecto:** optimización logística cuántico-híbrida para contingencias FEN  
**Piloto:** Bajo Piura, Perú  
**Audiencia:** equipo de investigación, desarrollo, asesores y jurado de competencia  
**Estado:** baseline clásico nuevo y subproblema QAOA ideal disponibles; conexión QPU opcional no ejecutada en esta V2.

> **Advertencia de uso:** los puntos de entrega, demandas, condiciones de vías y velocidades de este prototipo son ilustrativos. El sistema no debe usarse para decisiones reales de evacuación ni de reparto sin validación de datos y autoridades competentes.

---

# 1. Resumen ejecutivo

Durante emergencias vinculadas al Fenómeno El Niño, la distribución de ayuda humanitaria puede verse afectada por interrupciones viales, ventanas limitadas de acceso, distintos tipos de vehículos, capacidad disponible y urgencia diferenciada por comunidad. El problema se representa como un *Vehicle Routing Problem with Time Windows* (VRPTW) con flota heterogénea y escenarios de desvío.

**Nuestra propuesta:** construir un entorno reproducible que genere rutas de atención factibles, compare algoritmos clásicos y un componente QAOA en IBM Quantum, visualice los resultados y permita recalcular un plan cuando cambian las condiciones de las vías. La hipótesis no es que la QPU sea más rápida que un algoritmo clásico: buscamos determinar con qué tamaños, circuitos y métricas un componente cuántico ofrece resultados útiles, y dónde no.

**Qué existe ya:** primera versión con 8 puntos ilustrativos, tres vehículos y circuitos QAOA ejecutados en `ibm_kingston`, según los resultados aportados por el equipo. La corrida registrada muestreó cinco subproblemas con 4–9 qubits y registró 12 segundos de uso total de QPU. Es evidencia histórica de V1, no una repetición ejecutada en V2. La selección secuencial de V1 generaba soluciones factibles, pero no garantizaba óptimo global del VRPTW.

**Qué incorpora V2:** un motor global de selección de rutas por programación entera, un generador configurable de instancias 8/10/25/50, un subproblema cuántico de selección de rutas limitado a 10 variables, QAOA ideal reproducible, muestra uniforme comparable, reconstrucción de un plan híbrido y replanificación ilustrativa previa a la salida. Se incluyen código, notebook, pruebas y resultados exportables.

**Qué NO está completado:** red vial real de OpenStreetMap; datos verificados de albergues, demandas e inundaciones; comparación integrada con PyVRP y OR-Tools; replanificación de vehículos ya en tránsito; experimentos de la V2 en una QPU real; interfaz web final. Estos puntos son trabajo planificado, no capacidades entregadas.

# 2. Problema, usuarios y contexto de aplicación

**Decisión a apoyar.** Un coordinador de logística conoce el inventario disponible, los albergues que deben recibir ayuda y los vehículos habilitados. Antes de despachar, necesita decidir qué albergue atiende cada vehículo, en qué orden, a qué hora y qué cambia si una conexión vial se retrasa o deja de estar disponible.

**Usuarios previstos en la PoC:** equipo de operaciones humanitarias, responsables regionales de gestión de riesgos y analistas de optimización. No implica integración institucional ni adopción por una entidad pública.

**Valor buscado:** cobertura oportuna de demanda prioritaria, rutas operativamente válidas, trazabilidad de por qué se escoge cada alternativa y capacidad de comparar tecnologías con evidencia reproducible. No se debe afirmar que los métodos clásicos colapsan ante escenarios dinámicos: existen solvers clásicos muy competitivos.

**Caso geográfico piloto:** Bajo Piura. Las localidades de referencia de V1 incluyen Catacaos, Cura Mori, El Tallán, La Arena, La Unión, Vice, Bernal y Sechura. Los nombres de albergues y sus ubicaciones en el notebook son ficticios; incluso cuando se inspiran en distritos reales, no son establecimientos verificados.

# 3. Objetivo general y objetivos específicos

**Objetivo general.** Evaluar la viabilidad de una arquitectura cuántico-híbrida para planificación y replanificación de rutas de ayuda humanitaria en escenarios ilustrativos y progresivamente realistas del FEN, comparando factibilidad, calidad de ruta, tiempo y escalabilidad frente a métodos clásicos.

**OE1 — Instancias.** Publicar tres instancias principales de aproximadamente 10, 25 y 50 puntos, con escenarios de demanda, ventanas horarias, vehículos y vialidad versionados.

**OE2 — Referencia clásica.** Calcular un óptimo verificable en una instancia pequeña, y soluciones de referencia reproducibles en las medianas/grandes mediante MILP, OR-Tools y PyVRP cuando estén integrados.

**OE3 — Hardware cuántico.** Ejecutar QAOA en simulación y, sobre subproblemas adecuados de selección de rutas, en IBM Quantum con registro de backend, job ID, parámetros, profundidad, compuertas de dos qubits y consumo.

**OE4 — Benchmark.** Comparar brecha porcentual, tasa de factibilidad, atención crítica, tiempo de obtención de solución, tiempo real de CPU/QPU/cola y presupuesto computacional.

**OE5 — Cambio de escenario.** Incorporar al menos un evento vial que obligue a recalcular el plan y medir el tiempo hasta disponer de una nueva alternativa válida.

**Criterio de éxito académico:** soluciones factibles en tres instancias de diseño, comparación cuantitativa bajo las mismas reglas, presentación clara de limitaciones y un prototipo reproducible. No se exige demostrar ventaja cuántica.

# 4. Alcance y delimitaciones

| Incluido en el objetivo del proyecto | Excluido o condicionado |
| --- | --- |
| 1–2 depósitos, hasta 50 puntos de demanda, flota heterogénea | Operación de reparto humanitario real |
| Capacidad, horarios, urgencia, vehículos habilitados | Inventario real o validación del COER/INDECI ya obtenida |
| Escenarios de afectación de caminos | Predicción meteorológica estocástica completa |
| Evaluación clásica vs cuántica en rutas candidatas | Resolver 50 puntos completos en una sola QPU |
| Mapa, cronograma, comparación y prototipo de evento | Drones, embarcaciones y transporte multimodal |
| Trazabilidad de códigos y resultados | Garantías de aceleración o ventaja cuántica |

**Alcance implementado en V2:** punto de origen único; hasta tres paradas por viaje; de uno a tres viajes por vehículo asignados a franjas de salida fijas para las instancias ampliadas; ventanas horarias; tiempos estimados mediante Haversine ajustada por factor 1.3 y multiplicadores sintéticos para tramos; selección MILP; QAOA ideal acotado; replanificación antes de despachar.

**Límite operativo esencial:** los viajes múltiples de V2 están restringidos a *slots* predeterminados y no representan un ruteo multi-viaje con horarios flexibles. El sistema impide usar simultáneamente el mismo vehículo dentro de un slot, pero todavía no optimiza de manera continua la hora de inicio del siguiente viaje. Este cambio será prioridad en la transición a datos reales.

# 5. Datos, procedencia y escenarios

## 5.1 Escenario heredado de 8 puntos

- Depósito ficticio `D0`, georreferenciado de manera ilustrativa cerca de Piura.
- Ocho puntos `P1–P8`, ventanas entre 06:30 y 16:00, prioridades del 1 al 3 y demandas derivadas de una regla heurística de población distrital usada en V1.
- Capacidad de la flota: `V1` camión 6 t, 10 paletas, 35 km/h, sin acceso inundado; `V2` camioneta 4x4, 4 paletas, 50 km/h; `V3` camión 4x4, 7 paletas, 40 km/h.
- `P2` y `P3` requieren vehículo todoterreno en el escenario inicial.
- Tiempo de recorrido estimado desde distancia geodésica ×1.3, y factores de desvío en `P5–P6` y `D0–P8`.
- La demanda total del caso V1/V2 de 8 puntos es 19 paletas.

El escenario V2 respeta estos elementos estructurales de V1, pero cambia la función objetivo y resuelve el problema mediante rutas candidatas globales. Por ello **los valores numéricos de objetivo de V1 y V2 no son comparables directamente**.

## 5.2 Escenarios ampliados

| Escenario | Puntos | Vehículos físicos | Slots por vehículo | Naturaleza |
| --- | ---: | ---: | ---: | --- |
| Control de la PoC | 8 | 3 | 1 | Ficticio, heredado de V1 |
| Pequeño | 10 | 4 | 1 | 8 base + 2 sintéticos |
| Mediano | 25 | 5 | 2 | Sintético, con grupos geográficos aproximados |
| Grande | 50 | 8 | 3 | Sintético, diseñado como prueba de estrés |

Una configuración original de 50 puntos, ocho vehículos y un máximo absoluto de tres visitas por vehículo sería matemáticamente inviable (24 visitas posibles). V2 resuelve esa contradicción usando hasta tres salidas por vehículo, con capacidad y retorno controlados por slot. No debe interpretarse como que la logística real ya soporta esos viajes.

## 5.3 Fuentes a incorporar en el siguiente sprint

| Fuente | Uso | Requisito de calidad |
| --- | --- | --- |
| OpenStreetMap / OSRM u otro enrutador | Tiempos sobre carreteras efectivas | Red direccionable, transitabilidad y restricciones de acceso |
| INDECI / COEN y autoridades locales | Daños, puntos relevantes y escenarios | Fecha, vigencia, fuente y estatus de verificación |
| SENAMHI / ENFEN | Contexto de condiciones y niveles de riesgo | Distinguir pronóstico, alerta y observación |
| INEI / fuentes de demanda | Estimaciones de demanda, no stock | Método y supuestos documentados |
| COER / municipalidades (si colaboran) | Validación operativa | Permiso y trazabilidad; no presuponer disponibilidad |

**Esquema mínimo de parada:** `id`, `lat`, `lon`, `demanda_paletas`, `inicio_ventana`, `fin_ventana`, `prioridad`, `requisitos_de_acceso`, `fuente`, `fecha_de_verificacion`. El origen de cada variable debe registrarse como observado, estimado o sintético.

# 6. Arquitectura V2 y flujo de extremo a extremo

1. **Configuración de escenario** → crear puntos, vehículos, slots y factores de ruta.
2. **Chequeos de calidad de datos** → coordenadas, prioridades, capacidad, ventanas y accesos.
3. **Generación de rutas candidatas** → enumeración exhaustiva cuando el tamaño lo permite; rutas diversificadas, por proximidad y semillas fijas en instancias grandes.
4. **Simulador de factibilidad** → exige carga por viaje dentro de capacidad, retornos antes del final del slot, ventanas respetadas y compatibilidad todoterreno.
5. **Optimización global clásica (MILP/HiGHS)** → selecciona una ruta por slot como máximo y cubre cada parada exactamente una vez.
6. **Selección de vecindario cuántico** → mantiene fijo el resto del plan, toma dos slots con alternativas completas y prepara un QUBO pequeño.
7. **Benchmark QUBO** → enumeración exacta local, uniforme aleatorio y QAOA ideal; opcional QPU real.
8. **Reconstrucción híbrida** → reemplaza exclusivamente rutas de vecindario si la muestra es válida; verifica cobertura global y costo bajo la misma función.
9. **Cambio de condición vial** → actualiza los factores de viaje, reconstruye el pool y resuelve el plan previo al despacho.
10. **Reporte y entrega** → JSON reproducible, CSV de benchmark, mapas exploratorios y futura interfaz.

## 6.1 Contrato matemático del optimizador maestro

Sea `R` el conjunto de rutas factibles generadas y `x_r ∈ {0,1}` la decisión de usar cada ruta. Cada ruta `r` tiene costo `c_r`, un conjunto de puntos visitados y un slot de vehículo asignado:

- **Minimizar:** suma de `c_r * x_r` para todas las rutas candidatas.
- **Cobertura:** para cada albergue `i`, suma de `x_r` de rutas que contienen `i` = 1.
- **Exclusividad del slot:** para cada slot `s`, suma de `x_r` de rutas de `s` ≤ 1.
- **Variables:** binarias. Toda ruta candidata ya pasó la validación logística.

**Costo V2 para cada ruta:** minutos de viaje + `0.05 ×` minutos de espera + `1.0 ×` penalidad temporal normalizada por prioridad. La penalidad de prioridad aplica a `(prioridad − 1) × (inicio_atención − 06:00)/60`. Estos pesos son **supuestos de diseño** y deben calibrarse con el equipo antes del benchmark oficial. También pueden sustituirse por una función lexicográfica: primero atender demanda crítica, luego minimizar atraso/riesgo y finalmente distancia.

**Resultado del solver:** `optimal=True` certifica el óptimo respecto al pool modelado si HiGHS termina con estado óptimo. En la instancia de ocho puntos, el pool es exhaustivo respecto a rutas de 1–3 paradas factibles y la flota/slots fijados. En 10/25/50, el pool es una muestra de rutas; el valor óptimo reportado NO es el óptimo demostrado del VRPTW irrestricto.

## 6.2 Formulación del QUBO local

Para una selección de hasta diez rutas candidatas en dos slots, el objetivo cuántico es escoger una combinación que cubra cada punto local exactamente una vez y no asigne dos rutas al mismo slot.

**QUBO:** costo lineal de rutas + `λ × Σ_i(cobertura_i − 1)^2` + `λ × Σ_(r,t mismo slot) x_r x_t`.

- `λ` se calcula a partir del costo de las alternativas y el QUBO se escala numéricamente.
- La referencia exacta es la mejor cadena factible del subproblema QUBO enumerada clásicamente.
- El QAOA variacional se entrena en simulación ideal, con CVaR y profundidad `p` configurable; la QPU real solo se utiliza si el operador lo habilita.
- La métrica de factibilidad cuántica es el porcentaje de *shots* con una cadena que cumple el predicado del subproblema, no la factibilidad del VRPTW completo por sí sola.
- Una muestra cuántica inválida se descarta, sin declarar que fue reparada; la reconstrucción del plan completo solo se efectúa para una combinación local válida.

**Regla de integridad del experimento:** el plan híbrido validado se compara con el mejor plan clásico sobre el mismo pool y la misma función objetivo. Si la referencia MILP ya es óptima, una muestra QAOA no puede superarla; puede igualarla o degradarla.

# 7. Métricas y protocolo de evaluación

| Métrica | Definición operativa | Cuidado metodológico |
| --- | --- | --- |
| Factibilidad global | % de planes que pasan cobertura, carga, ventanas, acceso y slot | Registrar fallos; nunca sustituir silenciosamente por un plan clásico |
| Brecha respecto al óptimo/conocido | `100 × (coste método − referencia) / abs(referencia)` | Diferenciar óptimo certificado de mejor conocido del pool |
| Atención de prioridad alta | Puntos prioritarios atendidos en su ventana / puntos prioritarios definidos | Después, añadir volumen crítico (paletas) |
| Tiempo hasta objetivo | Tiempo hasta generar una ruta con brecha ≤5% | Incluir tiempos del pipeline, no únicamente QPU |
| Tiempo de replanificación | Segundos entre recepción del escenario alterado y plan factible | V2: antes de despacho, no tiempo real en tránsito |
| Costo cuántico | Shots, tiempo QPU facturado, cola, profundidad y puertas 2q | Versionar backend y parámetros |
| Robustez | Medianas, rangos y fallos por semilla/evento | Repetir experimentos aleatorios, evitar corrida única |

**Protocolo reproducible propuesto:** fijar semillas y versiones; construir una instancia congelada; correr el baseline MILP; evaluar uniformemente el mismo sub-QUBO por enumeración, muestreo aleatorio y QAOA ideal; documentar la primera muestra factible, mejor costo y mediana. Para pruebas de hardware, registrar backend, calibración disponible, diseño de circuito, número de shots y job ID. No mezclar resultados de circuitos o funciones objetivo distintas en una sola tabla de desempeño.

**Comparadores pendientes necesarios:** OR-Tools y PyVRP sobre el problema de rutas completo, y recocido simulado/heurística clásica sobre **el mismo sub-QUBO**, con presupuestos comparables. El MILP actualmente integrado resuelve exactamente el problema maestro del pool, no sustituye todas esas referencias.

# 8. Replanificación y alcance de la demostración

**Evento implementado:** aumentar factores de desvío ilustrativos en pares `P7–P8` y `D0–P8`; recalcular rutas y selección **antes de iniciar entregas**. Permite medir la sensibilidad del plan y mostrar cambios de asignación o secuencia.

**Evento comprometido para el concurso:** cerrar una arista de una red vial real obtenida de OpenStreetMap y recalcular los tiempos de viaje usando rutas alternativas sobre el grafo. El modelo debe identificar cuando un albergue queda inalcanzable y reportarlo explícitamente, sin dibujar una ruta ficticia. Además, el sistema debe preservar lo ya entregado y la ubicación de vehículos si el evento ocurre a mitad de jornada; esta última capacidad aún requiere diseño e implementación.

**Regla de seguridad:** la opción de ruta clásica operativa debe estar disponible mientras la QPU está en cola; el resultado cuántico se muestra como evaluación experimental. Esto evita depender del tiempo de espera del hardware para una decisión humanitaria.

# 9. Componentes, estructura de repositorio y dependencias

| Módulo | Archivo actual | Contrato / salida |
| --- | --- | --- |
| Escenarios y validación | `src/fen_v2.py` | `Scenario`, `Stop`, `Vehicle`, `TripSlot` |
| Constructor de rutas | `src/fen_v2.py` | Lista de `Route`, solo si cumplen ventanas y capacidad |
| Maestro clásico | `src/fen_v2.py` | Solución MILP, estado, bound, gap, validación |
| QUBO / QAOA | `src/fen_v2.py` | Subproblema, resultados ideal/aleatorio; ejecución IBM opcional |
| Replanificación | `src/fen_v2.py` y notebook | Escenario alterado, nuevo pool, nuevo MILP |
| Experimentos | `notebooks/FEN_Piura_V2_Proceso_Completo.ipynb` | Tablas, figuras, CSV/JSON |
| QA | `tests/test_pipeline.py` | Siete controles automáticos |
| Gestión y diseño | `docs/Documentacion_Proyecto_FEN_Piura_V2.md` | Alcance, protocolos, trabajo por rol |
| Interfaz interactiva | Pendiente | Editor de escenario, mapa vial, cronograma, benchmark |

**Dependencias del núcleo:** NumPy, SciPy/HiGHS, Pandas y Matplotlib. Para IBM Quantum: Qiskit y `qiskit-ibm-runtime` actualizados. La QPU nunca se utiliza automáticamente; necesita habilitación explícita y entrada segura del token.

**Ejecución rápida:** abrir el notebook en Colab, ejecutar las celdas de instalación, creación del módulo, configuración, baseline, QUBO/QAOA, evento y benchmark. El notebook es autocontenido. El repositorio tiene la misma lógica en el `.py` para control de versiones y pruebas locales.

# 10. Fases de trabajo y criterios para avanzar

## Fase 1. Validación y referencia (semanas 1–2)

**Objetivo:** formular el modelo de manera coherente; reemplazar el sesgo jerárquico de V1; producir pruebas auditables.

**Tareas:** revisar datos ficticios V1; congelar la función objetivo; ejecutar MILP exacto para 8 puntos; añadir pruebas negativas de ventanas/capacidad; comparar ideal/QUBO/uniforme; introducir OR-Tools como referencia independiente.

**Salida:** una carpeta por experimento con escenario JSON, código versionado, resultado clásico, resultado ideal y reporte de validación.

**Gate A:** 8/8 puntos cubiertos, cero violaciones de restricciones, óptimo global certificado para la formulación V2 de ocho puntos y pruebas automáticas verdes.

## Fase 2. Datos viales y escalabilidad (semanas 3–4)

**Objetivo:** completar las instancias de 10/25/50 y hacer operativa la arquitectura de rutas candidatas.

**Tareas:** OSM y matriz vial; definición transparente de demanda; generador de instancias versionado; rutas candidatas por agrupación geográfica; itinerarios multiviaje con horarios compatibles; incorporación de PyVRP.

**Salida:** tres instancias oficiales del proyecto (no confundir con escenarios sintéticos actuales), diagnóstico de factibilidad y benchmark clásico.

**Gate B:** los tres escenarios están documentados, el validador distingue rutas factibles/inviables y existe una base clásica reproducible en cada tamaño. Si alguno no tiene plan factible, corregir los supuestos o informar claramente el motivo.

## Fase 3. Cuántica, perturbaciones y experimento (semanas 5–6)

**Objetivo:** evaluar el componente QAOA bajo presupuestos controlados y medir escenarios de replanificación.

**Tareas:** ejecutar varias semillas, profundidades p=1/2 y tamaños de QUBO; comparar con recocido simulado sobre el mismo QUBO; seleccionar las corridas de QPU real; registrar duración y cola; diseñar evento de puente cerrado sobre el grafo real.

**Salida:** matriz de experimentos con evidencia reproducible IBM, gráficos por ruido/profundidad y resultados de replanificación.

**Gate C:** al menos una corrida IBM verificada de la formulación V2, tasas de factibilidad trazables, comparación justa con solución clásica y escenario vial replanificado de forma validada. Si QPU no está disponible, registrar el bloqueo y conservar el experimento ideal como tal.

## Fase 4. Producto, validación y pitch (semanas 7–8)

**Objetivo:** entregar un sistema demostrable y defendible técnicamente ante jurado.

**Tareas:** dashboard, mapa real, cronograma por vehículo, selector de escenarios, comparación CPU/QPU y reproductor de resultados guardados; pruebas de interfaz y ensayo de pitch; documentación final.

**Salida:** notebook, repositorio, demo, datos de pruebas, informe final y presentación con roles de exposición definidos.

**Gate D:** demo reproducible sin Internet/QPU en vivo mediante resultados históricos etiquetados; ninguna afirmación de ventaja cuántica no demostrada; métricas y escenarios trazables; presentación completa en el tiempo permitido.

# 11. Propuesta de trabajo para cuatro integrantes

Se proponen roles funcionales, no asignaciones de personas. Nombrar un responsable principal por cada frente y un coordinador de integración.

| Frente | Dueño propuesto | Entregables | Depende de |
| --- | --- | --- | --- |
| A. Datos, GIS y escenarios | Integrante 1 | Datos versionados, red vial, cierres, documentación de fuente | Validación con operación |
| B. Investigación de operaciones | Integrante 2 | MILP, OR-Tools, PyVRP, métricas y validador | Escenarios A |
| C. Optimización cuántica | Integrante 3 | QUBO, QAOA ideal/IBM, job logs y benchmark | Rutas candidatas B |
| D. Plataforma y comunicación | Integrante 4 | Dashboard, reproducción de corridas, presentación | A/B/C |

**Coordinación:** una reunión técnica semanal de 30–45 min; una revisión de integración semanal; cada tarea cierra con PR revisada por otro integrante. No modificar la función objetivo sin aprobación de B+C y un nuevo identificador de versión de escenario. Integrante 4 mantiene el registro de decisiones y riesgos, sujeto a que el equipo acuerde esa designación.

**Definición de terminado:** código en rama principal, prueba automática o registro de experimento, ejemplo de entrada/salida, supuestos explícitos y evidencia en carpeta de resultados. Capturas aisladas o métricas sin semilla no cierran una tarea.

# 12. Backlog priorizado

| ID | Prioridad | Historia / tarea | Criterio de aceptación |
| --- | --- | --- | --- |
| P0-01 | P0 | Congelar modelo global de costo y cobertura | Función objetivo común y verificable |
| P0-02 | P0 | Validar ocho puntos vs referencia exacta | Checks automáticos y MILP óptimo |
| P0-03 | P0 | Probar cierres y casos inviables | El sistema detecta/no oculta inviabilidad |
| P1-01 | P1 | Sustituir Haversine por matriz OSM | Red real versionada y tiempos justificables |
| P1-02 | P1 | Agregar OR-Tools y PyVRP | Tablas para idénticas restricciones |
| P1-03 | P1 | Optimizar viajes múltiples sin slots rígidos | Consistencia temporal del mismo vehículo |
| P1-04 | P1 | Comparar QAOA/azar/recocido con mismo QUBO | Métricas y semillas compartidas |
| P1-05 | P1 | Replanificar en una red vial alterada | Nuevo plan con coberturas verificadas |
| P2-01 | P2 | Ejecutar QPU real V2 | Job IDs y métricas publicables |
| P2-02 | P2 | Dashboard y reproductor de experimento | Demo completamente reproducible |
| P2-03 | P2 | Pruebas 25/50 y análisis de frontera | Informe de tiempo, calidad y límites |
| P2-04 | P2 | Validación de supuestos con expertos | Registro de entrevista y acuerdos |

# 13. Riesgos y mitigación

| Riesgo | Probabilidad / impacto | Plan de control |
| --- | --- | --- |
| Datos ficticios parecen reales | Alto / alto | Etiquetado visible, ficha de procedencia, no usar términos operativos definitivos |
| Penalidades QUBO producen pocas muestras factibles | Alto / medio | Vecindarios pequeños, validación exacta y ajuste de formulación |
| Profundidad/ruteo de QPU degrada resultados | Alto / medio | Mostrar puertas 2q, usar p bajo, comparar dos backends si es viable |
| Espera de IBM supera necesidades de emergencia | Alto / alto | Solver clásico disponible; QPU solo como experimento |
| No existe ruta factible para una instancia | Medio / alto | Test previo de cobertura/capacidad/ventanas y declaración explícita de inviabilidad |
| MILP agota tiempo con 50 puntos | Medio / medio | Pool diversificado, límites de tiempo y reportar incumbente/gap |
| Demasiado alcance para la competencia | Alto / alto | Mantener gates A–D; producto mínimo prioriza benchmark y demo de vía interrumpida |
| Dependencias y versiones cambian | Medio / medio | Semillas, environment, versiones, pruebas, corrida de respaldo |
| API keys expuestas | Medio / alto | Ingreso seguro, no escribir en JSON, no subir credenciales al repositorio |

# 14. Diseño de la demo para un jurado

**Secuencia recomendada de 4–5 minutos (ajustable a reglas reales):**

1. **Situación realista (30 s):** mapa de Piura, comunidades y demanda prioritaria; aclarar origen/supuestos de datos.
2. **Plan inicial (60 s):** vehículo, capacidad, ventanas y rutas; mostrar todas las validaciones.
3. **Evento (60 s):** se cierra un tramo vial; recalcular la alternativa clásica y mostrar cómo cambian rutas, tiempos y cobertura. Especificar si es cierre real en grafo o simulación de multiplicadores.
4. **Elemento cuántico (60 s):** mostrar el subproblema de selección, circuito, job ID de IBM y comparación frente a solución exacta y baseline aleatorio; distinguir corrida reproducida de ejecución en vivo.
5. **Impacto y honestidad científica (60 s):** qué funciona, dónde aún no escala, cómo se ampliaría y cuál es el valor de un sistema que incorpora decisiones verificables y análisis de límites tecnológicos.

**Mensaje principal del pitch:** “Ante cortes de vías durante El Niño, proponemos un gemelo experimental de la logística humanitaria: compara optimización clásica y cuántica bajo las mismas reglas y ayuda a justificar rutas replanificadas para proteger la atención prioritaria”.

**Evitar frases que puedan invalidar la propuesta:** “lo cuántico siempre es más rápido”, “50 albergues se resolvieron enteros en IBM”, “las carreteras mostradas son navegables”, “el modelo está listo para operar” o “demostramos ventaja cuántica”.

# 15. Evidencia, archivos, comunicación y versionado

**Estructura de carpeta final de cada corrida:** `experiments/YYYYMMDD_ID/` con `scenario.json`, `run_config.json`, `classical_result.json`, `qubo_definition.json`, `qaoa_ideal.json`, `qpu_job.json` si existe, `validation.json`, `metrics.csv`, gráficos y `README` de interpretación.

**Reglas:** semilla fija por serie; identificador de escenario inmutable; propietario de cada pipeline; PR de revisión cruzada; issues por incumplimiento de criterios; nunca añadir token personal a notebooks o capturas; etiquetar cada figura con “simulado”, “hardware IBM” o “datos ilustrativos”.

**Artefactos incluidos con esta entrega:** notebook autocontenido, motor `.py`, pruebas, CSV y JSON de ejemplo, documento maestro Markdown/DOCX/PDF y guía de instalación. El paquete no incluye servicio web ni mapa vial real.

# 16. Primer sprint sugerido tras compartir con el equipo

**Primero (día 1–2):** cada integrante ejecuta el notebook, verifica controles, registra entorno, abre el repositorio y asigna propietarios a los módulos.

**Segundo (día 3–4):** responsable de operaciones valida el óptimo del caso ocho; responsable GIS propone red vial; responsable cuántico revisa el QUBO y las tasas de factibilidad; responsable producto maqueta el dashboard sin conectar backend aún.

**Tercero (día 5–7):** integrar primera matriz vial o, si aún no se logra, un set reproducible de tiempos de viaje; ejecutar benchmark con una segunda librería clásica; presentar un demo temprano de corte de ruta. La decisión para iniciar Fase 2 depende del cumplimiento de Gate A.

# 17. Fuentes técnicas y trazabilidad de afirmaciones

**Documentos base proporcionados por el equipo:**

- `Propuesta PoC VRPTW cuántico-híbrido para respuesta al FEN (Perú).md`, 23–24/oct/2026. De ella se recuperan los objetivos, tres instancias y cuatro fases del plan.
- `poc_analisis.md`, 24/oct/2026. Contiene métricas reportadas de la primera corrida y proyecciones aproximadas de ruido/escalado; estas proyecciones no sustituyen validación de hardware.
- `VRPTW_FEN_Piura_QAOA.ipynb` y variante con selector QPU. Definen el caso ilustrativo heredado, la flota, los ocho puntos y la estructura QAOA V1.

**Referencias públicas para el siguiente sprint:**

- IBM Quantum Sampler: https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-sampler
- IBM Runtime release notes: https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/release-notes
- Google OR-Tools VRPTW: https://developers.google.com/optimization/routing/vrptw
- PyVRP: https://pyvrp.org/
- OpenStreetMap: https://www.openstreetmap.org/
- INDECI: https://www.gob.pe/indeci
- SENAMHI: https://www.senamhi.gob.pe/

**Nota sobre concurso:** la rúbrica, fecha de entrega y reglas formales no fueron aportadas; los gates, roles y cronograma son una propuesta de planificación que deberá ajustarse al documento oficial del reto.

---

**Decisión para el equipo:** aprobar la V2 como infraestructura experimental de partida, no como versión final competitiva. La inversión prioritaria debe ir a datos viales, comparadores clásicos y replanificación verificable, mientras el componente IBM se desarrolla con experimentación controlada.
