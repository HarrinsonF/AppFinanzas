import flet as ft
import database as db
from datetime import date, datetime
import calendar

def main(page: ft.Page):
    page.title = "Finanzas Master 3.0"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 420
    page.window_height = 850
    page.padding = 15

    db.inicializar_db()

    # --- VARIABLES GLOBALES DE ESTADO ---
    config_actual = {} # Aquí cargaremos tus preferencias
    
    # --- UI Elements (Placeholders) ---
    txt_presupuesto = ft.Text(value="...", size=40, weight=ft.FontWeight.BOLD)
    txt_estado = ft.Text(value="...", size=14, color=ft.Colors.GREY_400)
    banner_alerta = ft.Container(visible=False, bgcolor=ft.Colors.RED_900, padding=10, border_radius=5)
    
    columna_gastos_fijos = ft.Column()
    columna_metas = ft.Column()
    columna_historial = ft.Column()
    chart_container = ft.Column()
    
    dd_meses = ft.Dropdown(width=150, label="Filtrar Mes", on_change=lambda e: cargar_historial())
    id_meta_seleccionada = [None] 
    es_retiro_meta = [False]

    # --- CARGA DE CONFIGURACIÓN ---
    def cargar_configuracion():
        nonlocal config_actual
        config_actual = db.obtener_config()
        # config_actual tiene: {'tasa_afp', 'limite_alerta', 'nombre_boveda', 'nombre_operativo'}
        
        # Actualizar textos de botones y labels que usan nombres de bancos
        lbl_boveda.value = f"Ingresos {config_actual['nombre_boveda']}"
        btn_ingreso_boveda.text = f"Ingreso a {config_actual['nombre_boveda']}"
        lbl_transferencia.value = f"Mover a {config_actual['nombre_operativo']}"
        btn_transfer.text = f"Transferir a {config_actual['nombre_operativo']}"
        chk_afp.label = f"Descontar AFP ({config_actual['tasa_afp']}%)"
        
        # Pre-llenar inputs de configuración
        set_input_boveda.value = config_actual['nombre_boveda']
        set_input_operativo.value = config_actual['nombre_operativo']
        set_input_afp.value = str(config_actual['tasa_afp'])
        set_input_alerta.value = str(config_actual['limite_alerta'])

    def guardar_csv(e: ft.FilePickerResultEvent):
            if e.path:
                if db.generar_reporte_csv(e.path):
                    mostrar_snack("✅ Reporte Excel generado exitosamente.")
                else:
                    mostrar_snack("❌ Error al generar reporte.")

    fp_csv = ft.FilePicker(on_result=guardar_csv)
    page.overlay.append(fp_csv)

    # --- CÁLCULOS PRINCIPALES ---
    def calcular_datos():
        saldo_operativo = db.obtener_saldo_por_tipo('OPERATIVO')
        hoy = date.today()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        dias_restantes = (ultimo_dia - hoy.day) + 1
        diario = saldo_operativo / dias_restantes if dias_restantes > 0 else 0
        return diario, saldo_operativo

    def actualizar_interfaz():
        cargar_configuracion() # Refrescar nombres y tasas
        diario, saldo_operativo = calcular_datos()
        
        txt_presupuesto.value = f"S/ {diario:.2f}"
        
        # USAMOS EL LÍMITE PERSONALIZADO
        limite = config_actual['limite_alerta']
        
        if diario < 0:
            txt_presupuesto.color = ft.Colors.RED
            txt_estado.value = "¡EN ROJO! Déficit crítico."
            banner_alerta.content = ft.Text(f"⚠️ ALERTA: Saldo negativo en {config_actual['nombre_operativo']}", color="white")
            banner_alerta.visible = True
        elif diario < limite:
            txt_presupuesto.color = ft.Colors.ORANGE
            txt_estado.value = f"¡Ojo! Menos de S/{limite} diarios."
            banner_alerta.visible = False
        else:
            txt_presupuesto.color = ft.Colors.GREEN
            txt_estado.value = "Vas excelente. Disfruta."
            banner_alerta.visible = False

        saldo_boveda = db.obtener_saldo_por_tipo('BOVEDA')
        fijos_pendientes = db.obtener_fijos_pendientes()
        boveda_libre = saldo_boveda - fijos_pendientes

        txt_info_bancos.value = (f"{config_actual['nombre_operativo']}: S/ {saldo_operativo:.2f}\n\n"
                                 f"{config_actual['nombre_boveda']}: S/ {saldo_boveda:.2f}\n"
                                 f"- Reservado Fijos: S/ {fijos_pendientes:.2f}\n"
                                 f"= Disponible Real: S/ {boveda_libre:.2f}")
        
        cargar_lista_fijos()
        cargar_wishlist()
        
        if not dd_meses.value:
            hoy_str = date.today().strftime("%Y-%m")
            meses = db.obtener_meses_disponibles()
            dd_meses.options = [ft.dropdown.Option(m) for m in meses]
            if hoy_str not in meses and meses: dd_meses.value = meses[0]
            else: dd_meses.value = hoy_str
            
        cargar_historial()
        construir_grafico()
        page.update()

    # --- BUILDERS ---
    def construir_grafico():
        data = db.obtener_gastos_semana()
        if not data:
            chart_container.controls = [ft.Text("Sin gastos recientes", color="grey")]
            return
        bar_groups = []
        max_y = 0
        for i, (fecha, monto) in enumerate(data):
            if monto > max_y: max_y = monto
            bar_groups.append(ft.BarChartGroup(x=i, bar_rods=[ft.BarChartRod(from_y=0, to_y=monto, width=15, color=ft.Colors.AMBER, border_radius=5)]))
        chart = ft.BarChart(
            bar_groups=bar_groups,
            border=ft.border.all(1, ft.Colors.GREY_800),
            left_axis=ft.ChartAxis(labels_size=30),
            bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=i, label=ft.Text(d[0].split("-")[2])) for i, d in enumerate(data)]),
            height=200, max_y=max_y * 1.2
        )
        chart_container.controls = [ft.Text("Gastos Semanales", weight="bold"), chart]

    def cargar_lista_fijos():
        columna_gastos_fijos.controls.clear()
        columna_gastos_fijos.controls.append(
            ft.Row([ft.Text("Pagos Mensuales", weight="bold"),
                    ft.ElevatedButton("Nuevo Mes 📅", bgcolor=ft.Colors.BLUE_GREY_900, color="white", scale=0.8, on_click=lambda e: page.open(dlg_confirmar_reinicio))],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        datos = db.obtener_todos_fijos()
        for id_g, nom, mon, pag in datos:
            chk = ft.Checkbox(label=f"{nom} (S/ {mon})", value=(pag==1), data=id_g, 
                            on_change=lambda e: [db.alternar_estado_gasto(e.control.data, e.control.value), actualizar_interfaz()])
            btn_del = ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", tooltip="Borrar",
                                    on_click=lambda e, x=id_g: [db.eliminar_gasto_fijo(x), actualizar_interfaz()])
            columna_gastos_fijos.controls.append(ft.Row([chk, btn_del], alignment="spaceBetween"))
        columna_gastos_fijos.controls.append(ft.TextButton("Agregar Nuevo Fijo +", on_click=lambda e: page.open(dlg_nuevo_fijo)))

    def cargar_wishlist():
        columna_metas.controls.clear()
        datos = db.obtener_metas()
        for id_m, nom, costo, ahorrado in datos:
            progreso = ahorrado / costo if costo > 0 else 0
            btn_abonar = ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color="green", tooltip="Abonar",
                on_click=lambda e, id_ref=id_m: abrir_dialogo_meta(id_ref, es_retiro=False))
            btn_retirar = ft.IconButton(ft.Icons.REMOVE_CIRCLE, icon_color="red", tooltip="Retirar",
                on_click=lambda e, id_ref=id_m: abrir_dialogo_meta(id_ref, es_retiro=True))
            
            columna_metas.controls.append(ft.Container(
                content=ft.Column([
                    ft.Row([ft.Text(nom, weight="bold", expand=True), ft.Text(f"S/ {ahorrado} / {costo}")]),
                    ft.ProgressBar(value=progreso, color=ft.Colors.PURPLE_400, bgcolor=ft.Colors.GREY_800),
                    ft.Row([btn_retirar, ft.Text("Gestión"), btn_abonar], alignment=ft.MainAxisAlignment.END)
                ]), padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=10, margin=5))
        columna_metas.controls.append(ft.ElevatedButton("Crear Meta", on_click=lambda e: page.open(dlg_nueva_meta), width=200))

    def cargar_historial():
        columna_historial.controls.clear()
        mes = dd_meses.value if dd_meses.value else "Todo"
        movs = db.obtener_movimientos_por_mes(mes)
        total = sum(m[3] for m in movs if m[4] == 'GASTO')
        columna_historial.controls.append(ft.Text(f"Gasto Total {mes}: S/ {total:.2f}", weight="bold", color="amber"))
        
        for id_mov, fecha, desc, monto, tipo in movs:
            icono = ft.Icons.ARROW_DOWNWARD if tipo == 'GASTO' else ft.Icons.ARROW_UPWARD
            color = ft.Colors.RED if tipo == 'GASTO' else ft.Colors.GREEN
            columna_historial.controls.append(ft.ListTile(
                leading=ft.Icon(icono, color=color), title=ft.Text(desc, size=14), subtitle=ft.Text(f"{fecha}", size=12),
                trailing=ft.Row([ft.Text(f"S/ {monto:.2f}", weight="bold"),
                                 ft.IconButton(ft.Icons.DELETE, icon_color="grey", on_click=lambda e, x=id_mov: [db.eliminar_movimiento(x), actualizar_interfaz()])
                                ], alignment="end", width=140)))

    # --- ACCIONES ---
    def registrar_gasto(e):
        if input_gasto_monto.value and input_gasto_desc.value:
            try:
                db.actualizar_saldo('OPERATIVO', float(input_gasto_monto.value), es_gasto=True, descripcion=input_gasto_desc.value)
                input_gasto_monto.value = ""
                input_gasto_desc.value = ""
                actualizar_interfaz()
                mostrar_snack("Gasto registrado 💸")
            except: pass

    def registrar_ingreso_click(e):
        if dlg_ingreso_monto.value:
            try:
                monto = float(dlg_ingreso_monto.value)
                desc = dlg_ingreso_desc.value if dlg_ingreso_desc.value else "Ingreso"
                if chk_afp.value:
                    tasa = config_actual['tasa_afp']
                    descuento = monto * (tasa / 100)
                    monto_neto = monto - descuento
                    desc += f" (Desc AFP {tasa}%)"
                else: monto_neto = monto
                
                db.actualizar_saldo('BOVEDA', monto_neto, es_gasto=False, descripcion=desc)
                dlg_ingreso.open = False
                dlg_ingreso_monto.value = ""
                chk_afp.value = False
                actualizar_interfaz()
                mostrar_snack("Ingreso registrado 🤑")
            except: pass

    def transferir(e):
        if input_transfer.value:
            try:
                monto = float(input_transfer.value)
                db.actualizar_saldo('BOVEDA', monto, es_gasto=True, descripcion=f"Trf a {config_actual['nombre_operativo']}")
                db.actualizar_saldo('OPERATIVO', monto, es_gasto=False, descripcion=f"Recarga desde {config_actual['nombre_boveda']}")
                input_transfer.value = ""
                actualizar_interfaz()
                mostrar_snack("Transferencia OK 🔄")
            except: pass

    def guardar_ajustes(e):
        try:
            db.guardar_configuraicon(
                set_input_boveda.value, set_input_operativo.value,
                float(set_input_afp.value), float(set_input_alerta.value)
            )
            dlg_settings.open = False
            actualizar_interfaz()
            mostrar_snack("Configuración actualizada ⚙️")
        except: mostrar_snack("Error en valores numéricos")

    def mostrar_snack(t):
        page.snack_bar = ft.SnackBar(ft.Text(t))
        page.snack_bar.open = True
        page.update()

    # --- BACKUP ---
    def save_bkp(e: ft.FilePickerResultEvent):
        if e.path: db.exportar_base_datos(e.path)
    def load_bkp(e: ft.FilePickerResultEvent):
        if e.files and db.restaurar_base_datos(e.files[0].path): actualizar_interfaz()
            
    fp_save = ft.FilePicker(on_result=save_bkp)
    fp_load = ft.FilePicker(on_result=load_bkp)
    page.overlay.extend([fp_save, fp_load])

    # --- ELEMENTOS UI ---
    # Dialog Settings
    set_input_boveda = ft.TextField(label="Nombre Bóveda (Banco Principal)")
    set_input_operativo = ft.TextField(label="Nombre Caja Chica (Diario)")
    set_input_afp = ft.TextField(label="Tasa AFP (%)", keyboard_type="number")
    set_input_alerta = ft.TextField(label="Alerta Gasto Diario (S/)", keyboard_type="number")
    dlg_settings = ft.AlertDialog(title=ft.Text("Ajustes"), content=ft.Column([set_input_boveda, set_input_operativo, set_input_afp, set_input_alerta], height=250),
                                  actions=[ft.TextButton("Guardar", on_click=guardar_ajustes)])

    # Inputs Normales
    input_gasto_desc = ft.TextField(label="¿Qué compraste?", expand=True)
    input_gasto_monto = ft.TextField(label="S/", width=80, keyboard_type="number")
    btn_gasto = ft.IconButton(icon=ft.Icons.ADD_CIRCLE, icon_color="red", icon_size=40, on_click=registrar_gasto)
    txt_info_bancos = ft.Text(size=12, text_align="center")

    # Ingreso
    dlg_ingreso_monto = ft.TextField(label="Monto Bruto", keyboard_type="number")
    dlg_ingreso_desc = ft.TextField(label="Desc.")
    chk_afp = ft.Checkbox(label="AFP", value=False)
    dlg_ingreso = ft.AlertDialog(title=ft.Text("Ingreso"), content=ft.Column([dlg_ingreso_desc, dlg_ingreso_monto, chk_afp], height=180),
                                 actions=[ft.TextButton("Ingresar", on_click=registrar_ingreso_click)])
    
    # Nuevo Fijo / Meta / Dialogos
    dlg_fijo_nombre = ft.TextField(label="Nombre")
    dlg_fijo_monto = ft.TextField(label="Monto", keyboard_type="number")
    dlg_nuevo_fijo = ft.AlertDialog(title=ft.Text("Nuevo Fijo"), content=ft.Column([dlg_fijo_nombre, dlg_fijo_monto], height=150),
        actions=[ft.TextButton("Guardar", on_click=lambda e: [db.agregar_nuevo_fijo(dlg_fijo_nombre.value, float(dlg_fijo_monto.value), 1), setattr(dlg_nuevo_fijo, 'open', False), actualizar_interfaz()])])

    dlg_meta_nombre = ft.TextField(label="Meta")
    dlg_meta_costo = ft.TextField(label="Costo", keyboard_type="number")
    dlg_nueva_meta = ft.AlertDialog(title=ft.Text("Nueva Meta"), content=ft.Column([dlg_meta_nombre, dlg_meta_costo], height=150),
        actions=[ft.TextButton("Crear", on_click=lambda e: [db.crear_meta(dlg_meta_nombre.value, float(dlg_meta_costo.value)), setattr(dlg_nueva_meta, 'open', False), actualizar_interfaz()])])
    def abrir_dialogo_meta(id_meta, es_retiro):
        id_meta_seleccionada[0] = id_meta
        es_retiro_meta[0] = es_retiro
        
        titulo = "RETIRAR de Ahorro (Emergencia)" if es_retiro else "ABONAR a Ahorro"
        dlg_meta_gestion.title = ft.Text(titulo, color="red" if es_retiro else "green")
        dlg_gestion_monto.label = "Monto a Retirar" if es_retiro else "Monto a Abonar"
        page.open(dlg_meta_gestion)
    
    dlg_gestion_monto = ft.TextField(label="Monto", keyboard_type="number")
    dlg_meta_gestion = ft.AlertDialog(title=ft.Text("Gestión"), content=dlg_gestion_monto,
        actions=[ft.TextButton("Confirmar", on_click=lambda e: [
            db.retirar_de_meta(id_meta_seleccionada[0], float(dlg_gestion_monto.value)) if es_retiro_meta[0] else db.abonar_a_meta(id_meta_seleccionada[0], float(dlg_gestion_monto.value)),
            setattr(dlg_meta_gestion, 'open', False), setattr(dlg_gestion_monto, 'value', ""), actualizar_interfaz(), mostrar_snack("Actualizado")])])

    dlg_confirmar_reinicio = ft.AlertDialog(title=ft.Text("¿Nuevo Mes?"), content=ft.Text("Se desmarcarán los fijos."),
        actions=[ft.TextButton("Sí", on_click=lambda e: [db.reiniciar_fijos_nuevo_mes(), setattr(dlg_confirmar_reinicio, 'open', False), actualizar_interfaz()])])

    # Elementos dinámicos (Labels que cambiarán de nombre)
    lbl_boveda = ft.Text("Ingresos Bóveda", weight="bold", color="white")
    btn_ingreso_boveda = ft.ElevatedButton("Ingreso", icon=ft.Icons.ATTACH_MONEY, bgcolor="white", color="green", on_click=lambda e: page.open(dlg_ingreso))
    lbl_transferencia = ft.Text("Mover", weight="bold")
    btn_transfer = ft.ElevatedButton("Transferir", on_click=transferir)
    input_transfer = ft.TextField(label="Monto", width=150, keyboard_type="number")

    # --- APP BAR (Aquí va el engranaje) ---
    page.appbar = ft.AppBar(
        title=ft.Text("Mis Finanzas"),
        center_title=False,
        bgcolor=ft.Colors.BLUE_GREY_900, # <--- CAMBIAMOS ESTA LÍNEA (Antes decía SURFACE_VARIANT)
        actions=[
            ft.IconButton(ft.Icons.SETTINGS, on_click=lambda e: page.open(dlg_settings))
        ]
    )

    # --- TABS ---
    tab_dashboard = ft.Container(padding=20, content=ft.Column([
        banner_alerta, ft.Text("Disponible Hoy:", size=16), txt_presupuesto, txt_estado, ft.Divider(),
        ft.Row([input_gasto_desc, input_gasto_monto, btn_gasto]), ft.Divider(), chart_container, ft.Divider(), txt_info_bancos
    ], horizontal_alignment="center", scroll="auto"))

    tab_fijos = ft.Container(padding=20, content=ft.Column([columna_gastos_fijos], scroll="auto"))

    tab_wishlist = ft.Container(padding=20, content=ft.Column([
        ft.Container(padding=10, bgcolor=ft.Colors.GREEN_900, border_radius=10, content=ft.Column([
            lbl_boveda, 
            btn_ingreso_boveda
        ], horizontal_alignment="center")),
        ft.Divider(),
        ft.Text("Metas", size=20, weight="bold"), 
        columna_metas,
        ft.Divider(),
        lbl_transferencia, 
        ft.Row([input_transfer, btn_transfer], alignment="center"),
        ft.Divider(),
        ft.Container(
            padding=15, 
            border=ft.border.all(1, ft.Colors.GREY_800), 
            border_radius=10, 
            content=ft.Column([
                ft.Text("Backup / Seguridad", weight="bold", color="amber"),
                ft.Row([
                    ft.ElevatedButton(
                        "Exportar Data 💾", 
                        on_click=lambda e: fp_save.save_file(file_name=f"Backup_{date.today()}.db"), 
                        bgcolor=ft.Colors.BLUE_GREY_800, 
                        color="white"
                    ),
                    ft.ElevatedButton(
                        "Restaurar Data 📂", 
                        on_click=lambda e: fp_load.pick_files(), 
                        bgcolor=ft.Colors.GREY_900, 
                        color="white"
                    )
                ], alignment=ft.MainAxisAlignment.CENTER)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    ], scroll=ft.ScrollMode.AUTO))

    tab_historial = ft.Container(padding=20, content=ft.Column([
            ft.Row([
                ft.Text("Historial", size=20, weight="bold"), 
                dd_meses
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # Botón Nuevo para Exportar
            ft.ElevatedButton("Descargar en Excel 📊", 
                            icon=ft.Icons.DOWNLOAD, 
                            bgcolor=ft.Colors.GREEN_700, 
                            color="white",
                            on_click=lambda e: fp_csv.save_file(file_name=f"Reporte_Finanzas_{date.today()}.csv")),
            
            ft.Divider(),
            columna_historial
        ], scroll=ft.ScrollMode.AUTO))
    
    page.add(ft.Tabs(tabs=[
        ft.Tab(text="Diario", content=tab_dashboard), ft.Tab(text="Fijos", content=tab_fijos),
        ft.Tab(text="Bóveda", content=tab_wishlist), ft.Tab(text="Historial", content=tab_historial)
    ], expand=True))

    actualizar_interfaz() # Carga inicial

if __name__ == "__main__":

    ft.app(target=main, assets_dir="assets")
