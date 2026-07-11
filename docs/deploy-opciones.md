# Opciones de despliegue - ParrillaFutbolBot

## Resumen

Actualmente el bot funciona con:
- **Render (cron)**: `bot_parrilla.py` via cron job diario a las 8am (gratis)
- **Uso local**: `bot_local.py` bajo demanda para interactuar

Este documento enumera opciones para tener el bot interactivo 24/7 sin pagar (o muy poco).

---

## Opcion 1: Oracle Cloud Free Tier (recomendada)

**Costo: $0**

Oracle Cloud ofrece una VM ARM Ampere A1 siempre gratis:
- 4 OCPU, 24 GB RAM, 200 GB disco
- Solo requiere crear cuenta y configurar SSH

### Pasos basicos

1. Crear cuenta en https://www.oracle.com/cloud/free/
2. Crear una instancia VM.Standard.A1.Flex (Ubuntu 22.04)
3. Conectarse via SSH e instalar:
   ```bash
   sudo apt update && sudo apt install -y python3 python3-pip git
   git clone https://github.com/andresgalvis26/ParrillaFutbolBot.git
   cd ParrillaFutbolBot
   pip install -r src/config/requirements.txt
   ```
4. Configurar `src/config/.env` con BOT_TOKEN, SCRAPER_SOURCE, etc.
5. Ejecutar con `screen` o `tmux`:
   ```bash
   screen -S bot
   cd src && python bot_local.py
   # Ctrl+A, D para despegar
   ```
6. Opcional: crear un servicio systemd para que arranque solo.

### Ventajas
- Recurso generoso, corre 24/7
- Gratis para siempre
- Se puede agregar cron de respaldo

### Desventajas
- Registro puede pedir tarjeta de credito
- La VM se duerme si no se usa (pero para un bot no hay problema)

---

## Opcion 2: Railway

**Costo: ~$0-2/mes**

Railway tiene $5 de credito mensual gratis (sin tarjeta en algunos planes). Un bot en polling consume ~$1-2/mes.

### Pasos basicos

1. Crear cuenta en https://railway.app/
2. Conectar repositorio de GitHub
3. Crear un nuevo proyecto tipo "Worker"
4. Configurar:
   - Start command: `cd src && python bot_local.py`
   - Variables de entorno: BOT_TOKEN, SCRAPER_SOURCE, etc.
5. Hacer deploy

### Ventajas
- Muy sencillo (conecta repo y listo)
- Sin mantener VM

### Desventajas
- Eventualmente hay que pagar si se acaban los creditos
- Menos control que una VM

---

## Opcion 3: Render (mixto - lo que ya tenes)

**Costo: ~$0-7/mes**

Ya tenes el cron gratis en Render. Agregar un servicio interactivo:

### 3a. Background Worker (pago)

Render ofrece Background Workers desde $7/mes. Ahi corre `bot_local.py` 24/7.

### 3b. Solo cron + uso local bajo demanda (sigue siendo gratis)

Usas Render solo para el cron diario. Cuando queres interactuar:
- Ejecutas `python bot_local.py` en tu PC un rato
- Lo cerras cuando terminaste
- El cron sigue mandando el mensaje de las 8am todos los dias

### Ventajas
- Ya tenes la infraestructura
- No mover nada

### Desventajas
- Worker pago ($7/mes)
- Opcion 3b no es 24/7

---

## Opcion 4: Local + tunel (solo si la PC esta siempre encendida)

**Costo: $0**

Corres `bot_local.py` en tu PC y usas un tunel para webhooks en vez de polling.

### Con ngrok
```bash
ngrok http 8080
# Configurar webhook en Telegram apuntando a la URL de ngrok
```

### Con Cloudflare Tunnel (mejor)
- Cliente ligero, sin puertos abiertos
- Gratis y mas estable que ngrok

### Desventaja
- La PC tiene que estar encendida 24/7
- No es ideal si apagas la PC en la noche

---

## Opcion 5: PythonAnywhere

**Costo: ~$5/mes (Hacker plan)**

PythonAnywhere tiene un plan Hacker por $5/mes que permite:
- Un proceso siempre activo (+2 tareas programadas)
- Acceso via web
- Bash consola

### Limitaciones
- No hay `curl_cffi` instalado por defecto (habria que pedirlo o compilarlo)
- Solo funciona `partidos-de-hoy`

---

## Conclusion

| Opcion | Costo | 24/7 | Dificultad |
|--------|-------|------|------------|
| Oracle Cloud Free Tier | $0 | Si | Media |
| Railway | ~$0-2/mes | Si | Baja |
| Render Worker (3a) | $7/mes | Si | Baja |
| Render cron + local (3b) | $0 | No | Nula |
| Local + tunel | $0 | Depende | Media |
| PythonAnywhere | $5/mes | Si | Media |

**Para el futuro**: Oracle Cloud Free Tier es la mejor relacion costo/beneficio. Railway es la mas facil. Seguir con solo el cron + local bajo demanda es lo mas practico por ahora.
