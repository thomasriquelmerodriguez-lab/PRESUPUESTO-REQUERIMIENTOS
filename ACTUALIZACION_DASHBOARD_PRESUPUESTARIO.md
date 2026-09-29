# Actualización: Dashboard de gestión presupuestaria

Se incorpora un nuevo módulo **Dashboard presupuestario** orientado a la toma de decisiones.

## Cálculo central

El saldo se calcula como:

**Saldo disponible = Presupuesto vigente - Requerimientos registrados - Obligado CAS**

Los totales generales respetan la regla presupuestaria vigente: se consideran las cuentas desde **215-21** y el presupuesto general no duplica niveles jerárquicos.

## Indicadores

- Presupuesto vigente.
- Obligado CAS.
- Requerimientos registrados.
- Saldo disponible.
- Porcentaje comprometido.
- Cantidad de requerimientos y cuentas utilizadas.

## Visualizaciones

- Estado presupuestario por cuenta de primer orden.
- Drill-down por cuenta matriz y cuenta específica.
- Evolución mensual de requerimientos.
- Semáforo de compromiso presupuestario:
  - Verde: menos de 50%.
  - Amarillo: 50% a 75%.
  - Naranjo: 75% a 90%.
  - Rojo: 90% o más o saldo negativo.
- Cuentas que requieren atención.
- Ranking de cuentas con mayor monto de requerimientos.

## Alertas

El dashboard destaca:

- cuentas con saldo negativo;
- cuentas con más de 90% comprometido;
- cuentas con saldo igual o inferior a $5.000.000;
- requerimientos que quedaron asociados a cuentas que ya no están presentes en el presupuesto vigente.

## Reporte

El botón **Generar reporte** abre una vista imprimible que puede guardarse como PDF desde el navegador.

## Render

No se requieren nuevas variables de entorno ni cambios en PostgreSQL. Reemplace los archivos del repositorio por esta versión y ejecute **Manual Deploy -> Deploy latest commit**.
