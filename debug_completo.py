import requests
from bs4 import BeautifulSoup
from datetime import datetime
import locale

# Establecer español como idioma para la fecha
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')

hoy = datetime.now()
dia = str(hoy.day)
mes = hoy.strftime('%B').lower()
fecha_hoy = f'{dia} de {mes}'

print(f'Fecha que estamos buscando: {fecha_hoy}')

url = 'https://www.futbolred.com/parrilla-de-futbol'
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

print("=== ANÁLISIS COMPLETO DE LA PÁGINA ===")

# Buscar todas las tablas
tablas = soup.find_all('table')
print(f'Tablas encontradas: {len(tablas)}')

for i, tabla in enumerate(tablas):
    print(f'\n--- Tabla {i+1} ---')
    filas = tabla.find_all('tr')
    print(f'Filas en tabla: {len(filas)}')
    
    # Mostrar las primeras filas
    for j, fila in enumerate(filas[:3]):
        celdas = fila.find_all(['td', 'th'])
        if celdas:
            contenido = ' | '.join([celda.get_text(strip=True) for celda in celdas])
            print(f'  Fila {j+1}: {contenido}')

# Buscar divs que puedan contener fechas
print('\n=== BUSCANDO CONTENEDORES DE FECHA ===')
contenedores_fecha = soup.find_all(['div', 'h1', 'h2', 'h3', 'h4', 'span'], 
                                   string=lambda text: text and ('agosto' in text.lower() or 'hoy' in text.lower() or '2025' in text))

for contenedor in contenedores_fecha:
    print(f'Contenedor con fecha: {contenedor.name} - "{contenedor.get_text(strip=True)}"')

# Buscar por clases comunes
print('\n=== BUSCANDO POR CLASES COMUNES ===')
clases_buscar = ['.date', '.fecha', '.day', '.dia', '.schedule', '.horario']
for clase in clases_buscar:
    elementos = soup.select(clase)
    if elementos:
        print(f'Elementos con clase {clase}: {len(elementos)}')
        for elem in elementos[:2]:
            print(f'  - {elem.get_text(strip=True)}')

# Buscar estructura específica de la página
print('\n=== ESTRUCTURA ESPECÍFICA ===')
main_content = soup.find('main') or soup.find('div', class_='main') or soup.find('div', class_='content')
if main_content:
    print('Contenido principal encontrado')
    # Buscar fechas dentro del contenido principal
    fechas_main = main_content.find_all(string=lambda text: text and 'agosto' in text.lower())
    for fecha in fechas_main[:5]:
        print(f'  Fecha en main: {fecha.strip()}')
