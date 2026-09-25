# Actualización para Render: SECRET_KEY simple

Esta versión elimina la validación que exigía que `SECRET_KEY` fuera aleatoria y tuviera al menos 32 caracteres en producción.

Ahora `SECRET_KEY` acepta cualquier valor de **4 o más caracteres**, por ejemplo:

```env
SECRET_KEY=2026
```

Se mantienen las validaciones de producción para `SECURE_COOKIES=true` y `APP_ORIGIN` con HTTPS.

> Seguridad: una clave corta o predecible es menos resistente frente a ataques. Para un sitio público se recomienda usar una clave larga aunque la aplicación ya no la exija.
