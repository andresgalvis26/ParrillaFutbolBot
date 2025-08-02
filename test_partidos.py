import requests
from bs4 import BeautifulSoup
from datetime import datetime
import locale

# Establecer español como idioma para la fecha
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8') # Linux / Mac
except:
    locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252') # Windows

def obtener_partidos():
    hoy = datetime.now()
    dia = str(hoy.day)
    mes = hoy.strftime('%B').lower()
    fecha_hoy = f"{dia} de {mes}"
    
    url = 'https://www.futbolred.com/parrilla-de-futbol'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    mensaje = f"📺 *Partidos de hoy ({fecha_hoy}):*\n\n"
    
    print(f"Buscando partidos para el {fecha_hoy}...")
    
    # Buscar todas las tablas en la página
    tablas = soup.find_all('table')
    partidos_encontrados = False
    
    for tabla in tablas:
        filas = tabla.find_all('tr')
        if not filas:
            continue
            
        # La primera fila contiene la fecha
        primera_fila = filas[0]
        fecha_texto = primera_fila.get_text(strip=True).lower()
        
        print(f"Analizando fecha: {fecha_texto}")
        
        # Verificar si la fecha coincide con hoy
        if f"{dia} de agosto" in fecha_texto or fecha_hoy in fecha_texto:
            print(f"✅ Fecha encontrada: {fecha_texto}")
            
            # Procesar las filas de partidos (saltar la primera que es la fecha)
            for fila in filas[1:]:
                columnas = fila.find_all('td')
                if len(columnas) >= 4:
                    partido = columnas[0].get_text(strip=True)
                    liga = columnas[1].get_text(strip=True)
                    hora = columnas[2].get_text(strip=True)
                    canal = columnas[3].get_text(strip=True)
                    
                    if partido and liga and hora and canal:
                        mensaje += f"• {partido} ({liga}) - {hora} por {canal}\n"
                        partidos_encontrados = True
                        print(f"  📺 {partido} ({liga}) - {hora} por {canal}")
    
    if not partidos_encontrados:
        mensaje += "No se encontraron partidos para hoy."
        print("❌ No se encontraron partidos para hoy.")
    
    return mensaje

if __name__ == '__main__':
    resultado = obtener_partidos()
    print("\n" + "="*50)
    print("RESULTADO FINAL:")
    print("="*50)
    print(resultado)
