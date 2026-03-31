# Documentación Técnica Exhaustiva del Proyecto SBR

Este documento detalla la estructura, configuración, arquitectura de software, bases de datos y la lógica de negocio (Business Logic) subyacente de la aplicación web SBR, desarrollada en el framework Django (versión 6.0.1).

---

## 1. Visión General y Arquitectura

SBR es un sistema transaccional de gestión de bienes raíces especializado en la venta, financiamiento y administración de lotes de terreno. El objetivo primordial es ofrecer a los vendedores una interfaz unificada para emitir contratos, generar tablas de amortización y procesar pagos, mientras que a la gerencia le provee métricas financieras y cálculo de mora en tiempo real.

### 1.1 Stack Científico-Técnico
*   **Backend:** Python 3.x con Django 6.0.1.
*   **Base de Datos Relacional:** SQLite3 (`db.sqlite3` y `sbr_db.sqlite3` encontrados en entorno de desarrollo). Se utiliza el ORM nativo de Django para consultas complejas (anotaciones, agregaciones y uniones de tablas o `prefetch_related`).
*   **Motor PDF Genérico:** `WeasyPrint` con soporte de `GTK3` para Windows para transformar vistas HTML (Jinja2 Templates) a archivos de contrato o recibos en formato portable.
*   **Capa de Presentación:** Vanilla CSS combinado con las plantillas HTML de Django.
*   **Seguridad:** 
    *   `django-axes` interviene como *middleware* protegiendo endpoints de autenticación contra ataques de fuerza bruta (bloqueo automático tras 5 intentos fallidos `AXES_FAILURE_LIMIT = 5`).
    *   Integración con el API de recargas `django_recaptcha`.
    *   Aislado frente a vulnerabilidades de tipo XSS mediante la adopción de `bleach` en las interfaces de guardado modelo (`save()` method) limpiando scripts maliciosos.

### 1.2 Arquitectura Modular

El monorepo está compuesto por un core central y módulos satélites:
*   `sbr_dos/`: Core de configuración (`settings.py`, variables de entorno vía `python-dotenv`, root `urls.py` y configuración de Middlewares).
*   `Aplicaciones/sbr_app_dos/`: Módulo principal (Core de Ventas). Gestiona usuarios, lotes, clientes, ventas, amortizaciones y PDFs.
*   `Aplicaciones/sbr_gestor/`: Módulo financiero (Core de Caja). Registra y analiza todos los egresos/ingresos, graficando consolidados y procesando los rendimientos derivados de `sbr_app_dos`.

---

## 2. Bases de Datos y Modelado (Entidad-Relación)

La base de datos sigue un esquema altamente normalizado, implementado y manejado mediante migraciones en `sbr_app_dos/models.py`.

### 2.1 Modelos del Core de Ventas (`sbr_app_dos`)
*   **Lote (`Lote`):** Identifica geográficamente un área. Sus restricciones incluyen el tamaño, precio al contado y un `estado` estricto de máquina de estados (`DISPONIBLE`, `RESERVADO`, `VENDIDO`). Soporta imágenes (`plano`, `foto_lista`).
*   **Cliente (`Cliente`):** Entidad humana amarrada al Agente Vendedor (`ForeignKey(User)`). El input del usuario en atributos sensibles como la dirección es sanitizado con `bleach`.
*   **Contrato (`Contrato`):** Es el pilar del modelo (Agregador Root). Vincula a *un* Cliente con *múltiples* Lotes (relación *many-to-many*). Contiene la información matemática vital: `valor_entrada`, `precio_venta_final`, y transfiere las variables a deudas con `saldo_a_financiar`.
*   **Cuota (`Cuota`):** Fragmento temporal de amortización atado al contrato. Tiene características económicas de deuda, tales como `valor_capital`, `valor_mora` y control granular de lo recabado `valor_pagado`. Ademas, los administradores pueden dictaminar una excepción usando la flag boolean `mora_exenta`.
*   **Pago (`Pago`) y DetallePago (`DetallePago`):** Al generarse un abono del cliente, un único comprobante de pago (`Pago`) se subdivide proporcionalmente según un orden secuencial (FIFO o intencional) a múltiples cuotas creando vínculos por trazabilidad en `DetallePago`.

### 2.2 Modelos del Core Financiero (`sbr_gestor`)
*   **Transaccion (`Transaccion`):** Clasificado en `INGRESO` o `GASTO`, con control documental de `foto_recibo`. 
*   **CategoriaTransaccion (`CategoriaTransaccion`):** Identifica semánticamente las transacciones ("Servicios Básicos", "Nómina", etc.).

---

## 3. Lógica de Negocio (Business Logic) y Servicios Acoplados

El componente más intrincado radica en `sbr_app_dos/services.py`, encargado de abstraer la lógica financiera lejos de las funciones del controlador (Views).

### 3.1 Motor de Creación de Contratos y Amortización (`generar_tabla_amortizacion`)
1.  **Asistente Wizard en la Vista:** La ruta de ventas intercepta el POST recuperando el id del `Cliente`, o creándolo al vuelo. Enlaza los ids de los `Lote`s seleccionados y crea la entidad lógica de `Contrato` incluyendo el "Pago Principal" (La Entrada).
2.  **Distribución del Dinero:** Una vez validado el lote a estado "VENDIDO", invoca `generar_tabla_amortizacion(contrato_id)`.
3.  **Algoritmo Lineal:** Se disgrega el valor del `saldo_a_financiar` equitativamente sobre el `numero_cuotas`. No aplica interés compuesto para el abono a capital; las fechas del *due date* saltan en ciclos estandarizados cronometrados de un mes `relativedelta(months=1)`. Las disparidades debidas a divisiones fraccionales centesimales recaen usualmente sobre la carga de la última cuota garantizando un cuadre contable exacto.

### 3.2 Motor de Morosidad Analítica (`actualizar_moras_contrato`)
*   **Detección:** Iterar periódocamente sobre las cuotas de estados "PENDIENTES" o "PARCIALES". Si `cuota.fecha_vencimiento < hoy`:
*   **Castigo Lineal:** Se determina el valor del porcentaje seteado por el administrador (`ConfiguracionSistema.mora_porcentaje`). Si el cliente carece de perdonazo manual (`mora_exenta = False`), el algoritmo recalcula la condena multiplicando porcentualmente contra el capital inicial.
*   **Aseguramiento de Eficiencia:** La función ha sido optimizada para cargas en ráfagas con `actualizar_moras_masivo`, la cual procesa volumétricamente decenas de contratos de un vendedor eludiendo los ciclos recursivos (N+1 Queries del ORM de Django).

### 3.3 Procesador Asincrónico de Pagos (`registrar_pago_cliente`)
Representa el corazón transaccional de pagos concurrentes y validación de deudas en SQLite.
1.  **Atomización (ACID):** Opera bajo `@transaction.atomic` (si las líneas fallan o un crash sucede, todos los abonos son descartables por *rollback* evitando corrupciones económicas).
2.  **Cascada Secuencial (Waterfall Disbursement):** El cliente aporta $X, se busca la cuota más antigua o la `cuota_origen` señalada. Se rellena la cuota hasta calzar su deuda (capital + mora del momento), si sobra dinero se salta al siguiente eslabón temporal, rellenando de igual manera hasta agotar el saldo.
3.  **Registro Granular:** Todo aporte crea paralelamente registros auditables `DetallePago` cruzando al objeto padre de Transacción con la `Cuota` impactada.

### 3.4 Motor de Auditoría y Viaje en el Tiempo (`recalcular_deuda_contrato`)
*   Dado el requisito de que los administradores editen un `Pago` originado hace meses: Resulta inviable aplicar simplemente un "delta", debido a la interdependencia con la morosidad y otras cuotas.
*   **El Algoritmo:** Limpia íntegramente (a $0.00 de pagos aplicados) todos los registros dependientes. Iterando desde el pago primigenio por estampa de la fecha `pago_set.order_by('fecha_pago')` para recrear las transacciones simulando "un viaje en el tiempo", reimponiendo moras según su contexto original, y restaurando deudas y balances como si acabaran de ejecutarse iterativamente.

---

## 4. Reportería y Procesamiento de Documentos PFD

*   **Exportación Legal Dinámica:** En `sbr_app_dos/services.py`, las funciones orientadas como `generar_pdf_contrato(contrato_id)` compilan el DOM Virtual (El Template Django `reportes/plantilla_contrato.html`). 
*   **Pisa (XHTML2PDF) y WeasyPrint:** Se renderiza el ecosistema web transformándolo a un objeto Byte (Buffer).
*   Se acudió a utilidades propias para normalizar rutas estáticas y multimedia, como la función callback `link_callback` interceptando los Asset Paths según el OS host en el que opera Django (Win vs Linux).
*   Una vez exportado el PDF final, se adhiere mediante modelo físico de fichero al campo de Django `archivo_contrato_pdf`, de gran persistencia y listo para descarga HTTP Response binaria (`FileResponse`).

---

## 5. Controladores de Gestión Directiva (`sbr_gestor/views.py`)
Encargado del BI (Business Intelligence).
La función analítica vital se halla en `calcular_ganancias_lotes()`, que extrae un sumatorio transaccional bruto sobrecruzando las tablas del modulo principal. Acopla el `saldo_actual` sumando las ganancias del modulo Ventas más los manuales de "Ingresos Operacionales" restándoles "Gastos" de la caja chica, entregando en un objeto JSON (`chart_ingresos`) una métrica cruda para renderización de "Dashboards" apoyados en librerías en UI como Charts.js.

---
*Fin del documento técnico.*
