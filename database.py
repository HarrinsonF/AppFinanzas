import sqlite3
import shutil
import os
from datetime import date, timedelta, datetime
import csv

DB_NAME = 'mis_finanzas.db'

def inicializar_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Cuentas (Ahora nos importa mucho el TIPO)
    c.execute('''CREATE TABLE IF NOT EXISTS cuentas (
                    id INTEGER PRIMARY KEY, nombre TEXT, saldo REAL, tipo TEXT UNIQUE)''') # tipo: BOVEDA o OPERATIVO

    # 2. Configuración (NUEVA TABLA)
    c.execute('''CREATE TABLE IF NOT EXISTS config (
                    clave TEXT PRIMARY KEY, valor TEXT)''')

    # 3. Tablas Estándar
    c.execute('''CREATE TABLE IF NOT EXISTS gastos_fijos (
                    id INTEGER PRIMARY KEY, nombre TEXT, monto REAL, 
                    dia_vencimiento INTEGER, pagado INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimientos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, 
                    descripcion TEXT, monto REAL, cuenta_id INTEGER, tipo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas (
                    id INTEGER PRIMARY KEY, nombre TEXT, 
                    costo_total REAL, ahorrado REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS prestamos (
                    id INTEGER PRIMARY KEY, deudor TEXT, 
                    monto_total REAL, abonado REAL DEFAULT 0, 
                    completado INTEGER DEFAULT 0)''')

    # --- DATOS INICIALES (Seed) ---
    c.execute("SELECT count(*) FROM cuentas")
    if c.fetchone()[0] == 0:
        # Nombres por defecto, pero editables
        c.execute("INSERT INTO cuentas (nombre, saldo, tipo) VALUES (?, ?, ?)", ('Mi Bóveda (Scotia)', 0, 'BOVEDA'))
        c.execute("INSERT INTO cuentas (nombre, saldo, tipo) VALUES (?, ?, ?)", ('Caja Chica (BCP)', 0, 'OPERATIVO'))
        
        # Configuración por defecto
        c.execute("INSERT INTO config (clave, valor) VALUES (?, ?)", ('tasa_afp', '11.37'))
        c.execute("INSERT INTO config (clave, valor) VALUES (?, ?)", ('limite_alerta', '10.0'))
        
        c.execute("INSERT INTO metas (nombre, costo_total) VALUES (?, ?)", ('Ahorro Ejemplo', 1000))

    conn.commit()
    conn.close()

# --- GESTIÓN DE CONFIGURACIÓN ---
def obtener_config():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT clave, valor FROM config")
    data = dict(c.fetchall())
    
    # También traemos los nombres de los bancos actuales
    c.execute("SELECT nombre FROM cuentas WHERE tipo='BOVEDA'")
    res_boveda = c.fetchone()
    c.execute("SELECT nombre FROM cuentas WHERE tipo='OPERATIVO'")
    res_operativo = c.fetchone()
    
    conn.close()
    
    # Retornamos todo en un diccionario bonito
    return {
        'tasa_afp': float(data.get('tasa_afp', 11.37)),
        'limite_alerta': float(data.get('limite_alerta', 10.0)),
        'nombre_boveda': res_boveda[0] if res_boveda else "Bóveda",
        'nombre_operativo': res_operativo[0] if res_operativo else "Diario"
    }

def guardar_configuraicon(nuevo_nombre_boveda, nuevo_nombre_operativo, nueva_tasa_afp, nuevo_limite):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Actualizar tabla config
    c.execute("UPDATE config SET valor = ? WHERE clave = 'tasa_afp'", (str(nueva_tasa_afp),))
    c.execute("UPDATE config SET valor = ? WHERE clave = 'limite_alerta'", (str(nuevo_limite),))
    
    # Actualizar nombres de bancos
    c.execute("UPDATE cuentas SET nombre = ? WHERE tipo = 'BOVEDA'", (nuevo_nombre_boveda,))
    c.execute("UPDATE cuentas SET nombre = ? WHERE tipo = 'OPERATIVO'", (nuevo_nombre_operativo,))
    
    conn.commit()
    conn.close()

# --- LECTURA ---
def obtener_saldo_por_tipo(tipo_cuenta):
    # tipo_cuenta debe ser 'BOVEDA' o 'OPERATIVO'
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT saldo FROM cuentas WHERE tipo = ?", (tipo_cuenta,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0.0

def obtener_fijos_pendientes():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT sum(monto) FROM gastos_fijos WHERE pagado = 0")
    total = c.fetchone()[0]
    conn.close()
    return total if total else 0.0

def obtener_todos_fijos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, nombre, monto, pagado FROM gastos_fijos")
    items = c.fetchall()
    conn.close()
    return items

def obtener_metas():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, nombre, costo_total, ahorrado FROM metas")
    items = c.fetchall()
    conn.close()
    return items

def obtener_gastos_semana():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_inicio = date.today() - timedelta(days=6)
    c.execute('''SELECT fecha, sum(monto) FROM movimientos 
                 WHERE tipo='GASTO' AND fecha >= ? 
                 GROUP BY fecha ORDER BY fecha''', (fecha_inicio,))
    data = c.fetchall()
    conn.close()
    return data

def obtener_meses_disponibles():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT substr(fecha, 1, 7) FROM movimientos ORDER BY fecha DESC")
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data

def obtener_movimientos_por_mes(mes_str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if mes_str == "Todo":
        c.execute("SELECT id, fecha, descripcion, monto, tipo FROM movimientos ORDER BY fecha DESC LIMIT 50")
    else:
        c.execute("SELECT id, fecha, descripcion, monto, tipo FROM movimientos WHERE fecha LIKE ? ORDER BY fecha DESC", (f"{mes_str}%",))
    data = c.fetchall()
    conn.close()
    return data

# --- ESCRITURA (Ahora usando TIPOS) ---

def actualizar_saldo(tipo_cuenta, monto, es_gasto=True, descripcion="Movimiento"):
    # tipo_cuenta: 'BOVEDA' o 'OPERATIVO'
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    signo = -1 if es_gasto else 1
    
    # 1. Actualizar Saldo
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = ?", (monto * signo, tipo_cuenta))
    
    # 2. Registrar Movimiento (Guardamos el nombre real del banco en la descripción o logs si quisieramos)
    tipo_mov = "GASTO" if es_gasto else "INGRESO"
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), descripcion, monto, tipo_mov))
    conn.commit()
    conn.close()

def alternar_estado_gasto(id_gasto, nuevo_estado):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT monto, nombre FROM gastos_fijos WHERE id = ?", (id_gasto,))
    res = c.fetchone()
    if not res: return
    monto, nombre = res
    
    estado_int = 1 if nuevo_estado else 0
    c.execute("UPDATE gastos_fijos SET pagado = ? WHERE id = ?", (estado_int, id_gasto))
    
    # FIXED: Siempre afecta a la BOVEDA
    signo = -1 if nuevo_estado else 1
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = 'BOVEDA'", (monto * signo,))
    
    tipo_mov = "GASTO" if nuevo_estado else "INGRESO" 
    desc = f"Pago Fijo: {nombre}" if nuevo_estado else f"Reembolso Fijo: {nombre}"
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), desc, monto, tipo_mov))
    conn.commit()
    conn.close()

def abonar_a_meta(id_meta, monto):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE metas SET ahorrado = ahorrado + ? WHERE id = ?", (monto, id_meta))
    # Sale de la BOVEDA
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE tipo = 'BOVEDA'", (monto,))
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), "Abono a Meta", monto, "AHORRO"))
    conn.commit()
    conn.close()

def retirar_de_meta(id_meta, monto):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE metas SET ahorrado = ahorrado - ? WHERE id = ?", (monto, id_meta))
    # Entra a la BOVEDA (disponible)
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = 'BOVEDA'", (monto,))
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), "Retiro Emergencia Meta", monto, "INGRESO"))
    conn.commit()
    conn.close()

def eliminar_movimiento(id_movimiento):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT monto, tipo, descripcion FROM movimientos WHERE id = ?", (id_movimiento,))
    res = c.fetchone()
    if res:
        monto, tipo, desc = res
        signo = 1 if (tipo == 'GASTO' or tipo == 'AHORRO') else -1
        
        # Inteligencia para saber a qué TIPO de cuenta devolver
        # Por defecto Operativo, salvo que sea algo de la bóveda
        tipo_banco = 'OPERATIVO' 
        palabras_boveda = ['Fijo', 'Abono', 'Trf a', 'Sueldo', 'Ingreso', 'Retiro', 'Meta']
        if any(p in desc for p in palabras_boveda):
            tipo_banco = 'BOVEDA'
        
        c.execute(f"UPDATE cuentas SET saldo = saldo + ? WHERE tipo = '{tipo_banco}'", (monto * signo,))
        c.execute("DELETE FROM movimientos WHERE id = ?", (id_movimiento,))
    
    conn.commit()
    conn.close()

def reiniciar_fijos_nuevo_mes():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE gastos_fijos SET pagado = 0")
    conn.commit()
    conn.close()

def agregar_nuevo_fijo(nombre, monto, dia):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO gastos_fijos (nombre, monto, dia_vencimiento) VALUES (?, ?, ?)", (nombre, monto, dia))
    conn.commit()
    conn.close()

def eliminar_gasto_fijo(id_gasto):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM gastos_fijos WHERE id = ?", (id_gasto,))
    conn.commit()
    conn.close()

def crear_meta(nombre, costo):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO metas (nombre, costo_total) VALUES (?, ?)", (nombre, costo))
    conn.commit()
    conn.close()

# --- BACKUP ---
def exportar_base_datos(ruta_destino):
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.close()
        shutil.copy(DB_NAME, ruta_destino)
        return True
    except: return False

def restaurar_base_datos(ruta_origen):
    try:
        if not os.path.exists(ruta_origen): return False
        shutil.copy(DB_NAME, f"backup_pre_restore_{datetime.now().strftime('%H%M%S')}.db")
        shutil.copy(ruta_origen, DB_NAME)
        return True
    except: return False

def generar_reporte_csv(ruta_archivo, mes_str="Todo"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # Filtramos los movimientos según el mes seleccionado
        if mes_str == "Todo":
            c.execute("SELECT id, fecha, descripcion, monto, tipo FROM movimientos ORDER BY fecha DESC")
        else:
            c.execute("SELECT id, fecha, descripcion, monto, tipo FROM movimientos WHERE fecha LIKE ? ORDER BY fecha DESC", (f"{mes_str}%",))
            
        datos = c.fetchall()
        
        with open(ruta_archivo, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Cabeceras del Excel
            writer.writerow(["ID", "Fecha", "Descripción", "Monto", "Tipo Movimiento"])
            # Datos
            writer.writerows(datos)
            
        conn.close()
        return True
    except Exception as e:
        print(f"Error CSV: {e}")
        # Aseguramos que la conexión se cierre incluso si hay un error
        if conn:
            conn.close()
        return False

def eliminar_meta(id_meta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Ver cuánta plata tenía esa meta antes de borrarla
    c.execute("SELECT nombre, ahorrado FROM metas WHERE id = ?", (id_meta,))
    res = c.fetchone()
    
    if res:
        nombre, ahorrado = res
        
        # 2. Si tenía ahorros, devolvemos la plata a la Bóveda (Saldo Disponible)
        if ahorrado > 0:
            c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = 'BOVEDA'", (ahorrado,))
            
            # Registramos que nos devolvieron la plata
            c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
                      (date.today(), f"Eliminación Meta: {nombre}", ahorrado, "INGRESO"))
        
        # 3. Borramos la meta definitivamente
        c.execute("DELETE FROM metas WHERE id = ?", (id_meta,))
        
    conn.commit()
    conn.close()


def registrar_prestamo(deudor, monto):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Crear el registro del préstamo
    c.execute("INSERT INTO prestamos (deudor, monto_total) VALUES (?, ?)", (deudor, monto))
    
    # 2. El dinero sale de la BOVEDA
    c.execute("UPDATE cuentas SET saldo = saldo - ? WHERE tipo = 'BOVEDA'", (monto,))
    
    # 3. Registrar el movimiento para el historial
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), f"Préstamo a: {deudor}", monto, "GASTO")) # Figura como salida
    
    conn.commit()
    conn.close()

def abonar_prestamo(id_prestamo, monto_recibido):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Ver cuánto nos debían exactamente
    c.execute("SELECT deudor, monto_total, abonado FROM prestamos WHERE id = ?", (id_prestamo,))
    res = c.fetchone()
    if not res: return
    
    deudor, monto_total, abonado_actual = res
    deuda_restante = monto_total - abonado_actual
    
    # 2. Lógica de "La Yapita" (El extra)
    capital_a_cubrir = 0
    ingreso_extra = 0
    completado = 0
    
    if monto_recibido >= deuda_restante:
        # Nos pagaron todo (y quizás un extra)
        capital_a_cubrir = deuda_restante
        ingreso_extra = monto_recibido - deuda_restante
        completado = 1
    else:
        # Nos pagaron solo una parte
        capital_a_cubrir = monto_recibido
        
    # 3. Actualizar el préstamo
    c.execute("UPDATE prestamos SET abonado = abonado + ?, completado = ? WHERE id = ?", 
              (capital_a_cubrir, completado, id_prestamo))
    
    # 4. El dinero físico entra a la BOVEDA
    c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = 'BOVEDA'", (monto_recibido,))
    
    # 5. Registrar movimientos separados para que tu historial sea claro
    c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
              (date.today(), f"Cobro préstamo: {deudor}", capital_a_cubrir, "INGRESO"))
              
    if ingreso_extra > 0:
        c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
                  (date.today(), f"Extra (Propina/Interés) de: {deudor}", ingreso_extra, "INGRESO"))
    
    conn.commit()
    conn.close()

def obtener_prestamos_activos():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, deudor, monto_total, abonado FROM prestamos WHERE completado = 0")
    data = c.fetchall()
    conn.close()
    return data

def eliminar_prestamo(id_prestamo):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Ver cuánto dinero faltaba cobrar
    c.execute("SELECT monto_total, abonado, deudor FROM prestamos WHERE id = ?", (id_prestamo,))
    res = c.fetchone()
    
    if res:
        monto_total, abonado, deudor = res
        deuda_restante = monto_total - abonado
        
        # 2. Si faltaba cobrar plata, la devolvemos a la Bóveda para cuadrar la contabilidad
        if deuda_restante > 0:
            c.execute("UPDATE cuentas SET saldo = saldo + ? WHERE tipo = 'BOVEDA'", (deuda_restante,))
            c.execute("INSERT INTO movimientos (fecha, descripcion, monto, tipo) VALUES (?, ?, ?, ?)",
                      (date.today(), f"Anulación préstamo: {deudor}", deuda_restante, "INGRESO"))
        
        # 3. Borramos el registro
        c.execute("DELETE FROM prestamos WHERE id = ?", (id_prestamo,))
        
    conn.commit()
    conn.close()