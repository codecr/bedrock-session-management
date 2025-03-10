#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Demostración de Amazon Bedrock Session Management APIs
Caso de uso: Asistente de Diagnóstico para Infraestructura Cloud

Este programa demuestra el uso completo de las Session Management APIs 
para mantener el contexto de diagnóstico de problemas de infraestructura.
"""

import boto3
import uuid
import json
import time
import os
import sys
import argparse
from datetime import datetime
from botocore.exceptions import ClientError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

# Inicializar rich console para mejor visualización
console = Console()

# Inicializar el cliente de Bedrock (asume credenciales configuradas)
client = None
try:
    client = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
except Exception as e:
    console.print(f"[bold red]Error al inicializar el cliente de Bedrock: {e}[/]")
    sys.exit(1)

# Funciones principales para la gestión de sesiones

def create_troubleshooting_session(incident_id, system_affected, severity="high"):
    """
    Crea una nueva sesión para un incidente de infraestructura.
    
    Args:
        incident_id (str): ID del incidente en el sistema de tickets
        system_affected (str): Sistema afectado (ej: "payment-microservice")
        severity (str): Severidad del incidente (alta/media/baja)
        
    Returns:
        str: ID de la sesión creada o None si hay error
    """
    try:
        # Validar entradas
        if not incident_id or not system_affected:
            console.print("[bold red]Error: ID de incidente y sistema afectado son obligatorios[/]")
            return None
            
        # Crear una sesión con metadatos relevantes para diagnóstico
        response = client.create_session(
            sessionMetadata={
                "incidentId": incident_id,
                "systemAffected": system_affected,
                "severity": severity,
                "startedAt": datetime.now().isoformat()
            },
            tags={
                'Environment': 'Development',
                'IncidentType': 'PerformanceDegradation',
                'Demo': 'True'
            }
        )
        
        session_id = response["sessionId"]
        console.print(f"[bold green]✅ Sesión de diagnóstico creada. ID: {session_id}[/]")
        return session_id
    
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ValidationException':
            console.print("[bold red]Error de validación: Verifique los parámetros ingresados[/]")
        elif error_code == 'ThrottlingException':
            console.print("[bold red]Límite de velocidad excedido. Intente nuevamente más tarde[/]")
        else:
            console.print(f"[bold red]Error al crear la sesión: {str(e)}[/]")
        return None

def store_diagnostic_step(session_identifier, engineer_id, diagnostics_data, screenshots=None):
    """
    Almacena un paso en el proceso de diagnóstico.
    
    Args:
        session_identifier (str): ID o ARN de la sesión
        engineer_id (str): ID del ingeniero ejecutando este paso
        diagnostics_data (dict): Datos del diagnóstico
        screenshots (list, optional): Capturas de pantalla en bytes
        
    Returns:
        tuple: (success, invocation_id, step_id) indicando éxito y los IDs generados
    """
    console.print("[bold blue]Registrando paso de diagnóstico...[/]")
    
    try:
        # 1. Validar que la sesión existe (evita errores posteriores)
        try:
            session = client.get_session(sessionIdentifier=session_identifier)
            console.print("[green]✓ Sesión validada[/]")
        except Exception as e:
            console.print(f"[bold red]Error: La sesión {session_identifier} no existe o no es accesible: {str(e)}[/]")
            return False, None, None
        
        # 2. Crear una invocación con reintento
        invocation_id = None
        max_retries = 3
        for retry in range(max_retries):
            try:
                response = client.create_invocation(
                    sessionIdentifier=session_identifier,
                    description=f"Diagnóstico en {diagnostics_data.get('component', 'sistema desconocido')} por {engineer_id}"
                )
                invocation_id = response.get("invocationId")
                if not invocation_id:
                    console.print("[yellow]⚠ Respuesta de create_invocation no contiene invocationId[/]")
                    console.print(f"[dim]Respuesta completa: {json.dumps(response, default=str)}[/]")
                    continue
                    
                console.print(f"[green]✓ Invocación creada: {invocation_id}[/]")
                break
            except Exception as e:
                if retry < max_retries - 1:
                    console.print(f"[yellow]⚠ Intento {retry+1} fallido: {str(e)}. Reintentando...[/]")
                    time.sleep(1)
                else:
                    console.print(f"[bold red]Error al crear invocación después de {max_retries} intentos: {str(e)}[/]")
                    return False, None, None
        
        if not invocation_id:
            console.print("[bold red]No se pudo obtener un ID de invocación válido[/]")
            return False, None, None
            
        # 3. Estructurar los datos de diagnóstico con formato más claro
        formatted_data = (
            f"## Paso de diagnóstico\n\n"
            f"**Ingeniero:** {engineer_id}\n"
            f"**Componente:** {diagnostics_data.get('component', 'No especificado')}\n"
            f"**Acción ejecutada:** {diagnostics_data.get('action', 'No especificada')}\n\n"
            f"**Resultado observado:**\n{diagnostics_data.get('result', 'No documentado')}\n\n"
            f"**Siguiente acción recomendada:**\n{diagnostics_data.get('next_steps', 'No definida')}"
        )
        
        # 4. Preparar los bloques de contenido
        content_blocks = [
            {
                'text': formatted_data
            }
        ]
        
        # 5. Procesar imágenes si están disponibles
        if screenshots and isinstance(screenshots, list):
            for i, screenshot_path in enumerate(screenshots):
                try:
                    if os.path.exists(screenshot_path):
                        with open(screenshot_path, 'rb') as img_file:
                            img_data = img_file.read()
                            img_format = screenshot_path.split('.')[-1].lower()
                            if img_format not in ['png', 'jpeg', 'jpg', 'gif', 'webp']:
                                img_format = 'png'  # Default
                                
                            content_blocks.append({
                                'image': {
                                    'format': img_format,
                                    'source': {'bytes': img_data}
                                }
                            })
                            console.print(f"[green]✓ Imagen {i+1} cargada: {screenshot_path}[/]")
                    else:
                        console.print(f"[yellow]⚠️ Imagen no encontrada: {screenshot_path}[/]")
                except Exception as img_error:
                    console.print(f"[yellow]⚠️ Error procesando imagen {screenshot_path}: {img_error}[/]")
        
        # 6. Almacenar el paso de diagnóstico
        step_id = str(uuid.uuid4())
        try:
            step_response = client.put_invocation_step(
                sessionIdentifier=session_identifier,
                invocationIdentifier=invocation_id,
                invocationStepId=step_id,
                invocationStepTime=datetime.now().isoformat(),
                payload={
                    'contentBlocks': content_blocks
                }
            )
            console.print(f"[bold green]✅ Paso de diagnóstico registrado con éxito[/]")
            console.print(f"[dim]- Sesión: {session_identifier}[/]")
            console.print(f"[dim]- Invocación: {invocation_id}[/]")
            console.print(f"[dim]- Paso: {step_id}[/]")
            
            # 7. Verificar que el paso se creó correctamente
            try:
                verification = client.get_invocation_step(
                    sessionIdentifier=session_identifier,
                    invocationIdentifier=invocation_id,
                    invocationStepId=step_id
                )
                console.print(f"[green]✓ Verificación exitosa del paso creado[/]")
            except Exception as e:
                console.print(f"[yellow]⚠ No se pudo verificar el paso creado: {str(e)}[/]")
            
            return True, invocation_id, step_id
        except Exception as e:
            console.print(f"[bold red]Error al almacenar el paso de diagnóstico: {str(e)}[/]")
            return False, invocation_id, None
        
    except Exception as e:
        console.print(f"[bold red]Error inesperado: {str(e)}[/]")
        return False, None, None

def retrieve_diagnostic_context(session_identifier):
    """
    Recupera el contexto completo de un diagnóstico de infraestructura.
    
    Args:
        session_identifier (str): ID o ARN de la sesión
        
    Returns:
        dict: Contexto completo del diagnóstico con datos estructurados
    """
    try:
        console.print("[bold blue]Recuperando contexto de diagnóstico...[/]")
        
        # Obtener detalles de la sesión
        session_response = client.get_session(
            sessionIdentifier=session_identifier
        )
        
        # Manejar diferentes posibles estructuras de respuesta
        if "session" in session_response:
            session = session_response["session"]
        else:
            session = session_response
        
        # Verificar que tenemos acceso a los metadatos
        session_metadata_key = "sessionMetadata"
        if session_metadata_key not in session:
            session_metadata_key = "metadata"  # Alternativa posible
            if session_metadata_key not in session:
                incident_metadata = {}
                console.print("[yellow]⚠️ No se pudieron recuperar metadatos de la sesión[/]")
            else:
                incident_metadata = session[session_metadata_key]
        else:
            incident_metadata = session[session_metadata_key]
        
        # Listar todas las invocaciones (pasos de diagnóstico)
        invocations_response = client.list_invocations(
            sessionIdentifier=session_identifier
        )
        
        # Usar invocationSummaries en lugar de invocations
        invocations = invocations_response.get("invocationSummaries", [])
        #console.print(f"[dim]Invocaciones recuperadas: {len(invocations)}[/]")
        
        # Construir el contexto estructurado del diagnóstico
        diagnostic_context = {
            "incidentInfo": {
                "incidentId": incident_metadata.get("incidentId", "Unknown"),
                "systemAffected": incident_metadata.get("systemAffected", "Unknown"),
                "severity": incident_metadata.get("severity", "Unknown"),
                "startedAt": session.get("creationDateTime", datetime.now().isoformat()),
                "status": "Active" if not session.get("endDateTime") else "Closed"
            },
            "diagnosticTimeline": [],
            "hypotheses": [],
            "componentsTested": set(),
            "screenshots": []
        }
        
        # Recuperar y organizar los pasos de diagnóstico
        for inv in sorted(invocations, key=lambda x: x.get("createdAt", "")):
            try:
                # Extraer información disponible directamente de la invocación
                invocation_id = inv["invocationId"]
                
                # Convierte createdAt a string ISO si es un objeto datetime
                creation_time = inv.get("createdAt")
                if isinstance(creation_time, datetime):
                    creation_time = creation_time.isoformat()
                
                # La descripción puede que no esté disponible, usamos un valor predeterminado
                description = inv.get("description", f"Invocación {invocation_id}")
                
                # Listar pasos de la invocación
                invocation_steps_response = client.list_invocation_steps(
                    sessionIdentifier=session_identifier,
                    invocationIdentifier=invocation_id
                )
                            
                invocation_steps = invocation_steps_response.get("invocationStepSummaries", [])
                #console.print(f"[dim]Pasos encontrados para invocación {invocation_id}: {len(invocation_steps)}[/]")
                
                diagnostic_steps = []
                
                for step in sorted(invocation_steps, key=lambda x: x.get("invocationStepTime", "")):
                    try:
                        step_id = step.get("invocationStepId")
                        
                        # Obtener detalles del paso
                        step_response = client.get_invocation_step(
                            sessionIdentifier=session_identifier,
                            invocationIdentifier=invocation_id,
                            invocationStepId=step_id
                        )
                        
                        # Manejar posibles estructuras diferentes
                        if "invocationStep" in step_response:
                            step_details = step_response["invocationStep"]
                        else:
                            step_details = step_response
                        
                        # Asegurarse de que payload y contentBlocks existen
                        if "payload" not in step_details or "contentBlocks" not in step_details["payload"]:
                            console.print(f"[yellow]⚠️ Estructura de paso inesperada para {step_id}[/]")
                            continue
                        
                        # Procesar los bloques de contenido
                        content_blocks = step_details["payload"]["contentBlocks"]
                        text_content = ""
                        images = []
                        
                        for block in content_blocks:
                            if 'text' in block:
                                text_content = block['text']
                                
                                # Extraer componentes probados del texto (lógica más flexible)
                                if "componente:" in text_content.lower() or "Componente:" in text_content:
                                    component = ""
                                    if "Componente:" in text_content:
                                        parts = text_content.split("Componente:")[1].split("\n")
                                        component = parts[0].strip()
                                    elif "componente:" in text_content.lower():
                                        parts = text_content.lower().split("componente:")[1].split("\n")
                                        component = parts[0].strip()
                                    
                                    if component:
                                        console.print(f"[dim]Componente detectado: {component}[/]")
                                        diagnostic_context["componentsTested"].add(component)
                                
                                # Extraer hipótesis del texto
                                if "hipótesis" in text_content.lower():
                                    hypothesis_text = text_content
                                    engineer = "Unknown"
                                    if "Ingeniero:" in text_content:
                                        engineer = text_content.split("Ingeniero:")[1].split("\n")[0].strip()
                                    
                                    diagnostic_context["hypotheses"].append({
                                        "text": hypothesis_text,
                                        "timestamp": step_details.get("invocationStepTime", ""),
                                        "engineer": engineer
                                    })
                            
                            if 'image' in block:
                                # Referencia a la imagen
                                images.append({
                                    "stepId": step_id,
                                    "format": block['image'].get('format', 'unknown')
                                })
                                diagnostic_context["screenshots"].append({
                                    "stepId": step_id,
                                    "invocationId": invocation_id,
                                    "timestamp": step_details.get("invocationStepTime", ""),
                                    "associatedText": text_content[:100] + "..." if len(text_content) > 100 else text_content
                                })
                        
                        # Crear entrada para este paso
                        diagnostic_steps.append({
                            "timestamp": step_details.get("invocationStepTime", ""),
                            "textContent": text_content,
                            "hasImages": len(images) > 0,
                            "imageRefs": images
                        })
                    except Exception as step_error:
                        console.print(f"[yellow]⚠️ Error procesando paso {step.get('invocationStepId', 'unknown')}: {str(step_error)}[/]")
                        continue
                
                # Extraer ingeniero del descriptor de la invocación (si existe)
                engineer = "Unknown"
                if description and isinstance(description, str) and "por " in description:
                    engineer = description.split("por ")[1]
                
                # Añadir esta invocación al timeline
                diagnostic_context["diagnosticTimeline"].append({
                    "timestamp": creation_time,
                    "description": description,
                    "engineer": engineer,
                    "steps": diagnostic_steps
                })
            except Exception as inv_error:
                console.print(f"[yellow]⚠️ Error procesando invocación {inv.get('invocationId', 'unknown')}: {str(inv_error)}[/]")
                continue
        
        # Convertir el conjunto de componentes a lista para serialización JSON
        diagnostic_context["componentsTested"] = list(diagnostic_context["componentsTested"])
        
        # Ordenar cronológicamente
        diagnostic_context["diagnosticTimeline"].sort(key=lambda x: x["timestamp"])
        diagnostic_context["hypotheses"].sort(key=lambda x: x["timestamp"])
        diagnostic_context["screenshots"].sort(key=lambda x: x["timestamp"])
        
        # Depuración - Mostrar un resumen del contexto
        console.print(f"[dim]Resumen del contexto recuperado:[/]")
        console.print(f"[dim]- Timeline events: {len(diagnostic_context['diagnosticTimeline'])}[/]")
        console.print(f"[dim]- Componentes: {len(diagnostic_context['componentsTested'])}[/]")
        console.print(f"[dim]- Hipótesis: {len(diagnostic_context['hypotheses'])}[/]")
        console.print(f"[dim]- Capturas: {len(diagnostic_context['screenshots'])}[/]")
        
        console.print("[bold green]✅ Contexto de diagnóstico recuperado correctamente[/]")
        return diagnostic_context
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            console.print(f"[bold red]Error: La sesión {session_identifier} no existe[/]")
        else:
            console.print(f"[bold red]Error al recuperar el contexto del diagnóstico: {str(e)}[/]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error inesperado: {str(e)}[/]")
        import traceback
        traceback.print_exc()  # Para obtener el stack trace completo
        return None
     
def end_diagnostic_session(session_identifier, resolution_summary, resolution_type):
    """
    Finaliza una sesión de diagnóstico de infraestructura con información 
    de resolución.
    
    Args:
        session_identifier (str): ID o ARN de la sesión
        resolution_summary (str): Resumen de cómo se resolvió el incidente
        resolution_type (str): Categoría de resolución (fix, workaround, escalation)
        
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario
    """
    try:
        # Primero, añadimos un paso final con el resumen de resolución
        invocation_id = client.create_invocation(
            sessionIdentifier=session_identifier,
            description="Resolución del incidente"
        )["invocationId"]
        
        # Estructurar el resumen de resolución
        resolution_data = (
            f"## Resolución del Incidente\n\n"
            f"**Tipo de resolución:** {resolution_type}\n\n"
            f"**Resumen:**\n{resolution_summary}\n\n"
            f"**Fecha de resolución:** {datetime.now().isoformat()}\n\n"
            f"**Lecciones aprendidas:**\n- [Por completar en la revisión post-incidente]"
        )
        
        # Almacenar el resumen de resolución -
        client.put_invocation_step(
            sessionIdentifier=session_identifier,
            invocationIdentifier=invocation_id,
            invocationStepId=str(uuid.uuid4()),
            invocationStepTime=datetime.now().isoformat(), 
            payload={
                'contentBlocks': [{
                    'text': resolution_data
                }]
            }
        )
        
        # Ahora finalizamos formalmente la sesión
        client.end_session(
            sessionIdentifier=session_identifier
        )
        
        console.print(f"[bold green]✅ Sesión de diagnóstico {session_identifier} finalizada con éxito[/]")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            console.print(f"[bold red]Error: La sesión {session_identifier} no existe[/]")
        elif e.response['Error']['Code'] == 'ConflictException':
            console.print(f"[bold red]Error: La sesión {session_identifier} ya está finalizada[/]")
        else:
            console.print(f"[bold red]Error al finalizar la sesión de diagnóstico: {str(e)}[/]")
        return False

def delete_diagnostic_session(session_identifier, reason, approver_id):
    """
    Elimina permanentemente una sesión de diagnóstico y todos sus datos asociados.
    
    Args:
        session_identifier (str): ID o ARN de la sesión
        reason (str): Justificación para la eliminación
        approver_id (str): ID del responsable que aprueba la eliminación
        
    Returns:
        bool: True si la operación fue exitosa, False en caso contrario
    """
    try:
        # Registrar la solicitud de eliminación (simulado)
        audit_log = {
            "action": "session_deletion",
            "session_id": session_identifier,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "approver": approver_id
        }
        
        console.print(f"[bold yellow]Registrando eliminación en logs de auditoría: {json.dumps(audit_log)}[/]")
        
        # Confirmación final
        if not Confirm.ask("[bold red]¿Está seguro de eliminar permanentemente esta sesión? Esta acción no se puede deshacer"):
            console.print("[yellow]Operación de eliminación cancelada por el usuario[/]")
            return False
        
        # Eliminar la sesión
        client.delete_session(
            sessionIdentifier=session_identifier
        )
        
        console.print(f"[bold green]✅ Sesión de diagnóstico {session_identifier} eliminada permanentemente[/]")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            console.print(f"[bold red]Error: La sesión {session_identifier} no existe[/]")
        else:
            console.print(f"[bold red]Error al eliminar la sesión de diagnóstico: {str(e)}[/]")
        return False

def display_diagnostic_context(context):
    """
    Muestra el contexto de diagnóstico de forma legible
    
    Args:
        context (dict): Contexto de diagnóstico recuperado
    """
    if not context:
        return
    
    console.print("\n[bold cyan]📊 RESUMEN DE DIAGNÓSTICO[/]")
    
    # Información del incidente
    incident_info = context["incidentInfo"]
    console.print(Panel.fit(
        f"ID: [bold]{incident_info['incidentId']}[/]\n"
        f"Sistema: [bold]{incident_info['systemAffected']}[/]\n"
        f"Severidad: [bold]{incident_info['severity']}[/]\n"
        f"Inicio: [bold]{incident_info['startedAt']}[/]\n"
        f"Estado: [bold]{incident_info['status']}[/]",
        title="📝 Información del Incidente",
        border_style="blue"
    ))
    
    # Componentes probados
    console.print(Panel.fit(
        ", ".join(context["componentsTested"]) if context["componentsTested"] else "Ninguno",
        title="🔍 Componentes Analizados",
        border_style="green"
    ))
    
    # Hipótesis
    if context["hypotheses"]:
        hypothesis_table = Table(show_header=True, header_style="bold magenta")
        hypothesis_table.add_column("Fecha")
        hypothesis_table.add_column("Ingeniero")
        hypothesis_table.add_column("Hipótesis")
        
        for hyp in context["hypotheses"]:
            # Asegurar que timestamp sea un string
            timestamp_str = str(hyp["timestamp"]) if hyp["timestamp"] else "Unknown"
            if isinstance(hyp["timestamp"], datetime):
                timestamp_str = hyp["timestamp"].isoformat()
                
            hypothesis_table.add_row(
                timestamp_str,
                hyp["engineer"],
                hyp["text"][:50] + "..." if len(hyp["text"]) > 50 else hyp["text"]
            )
        
        console.print(Panel(hypothesis_table, title="🧠 Hipótesis", border_style="yellow"))
    
    # Línea de tiempo
    console.print("[bold cyan]📅 LÍNEA DE TIEMPO DEL DIAGNÓSTICO[/]")
    
    if not context["diagnosticTimeline"]:
        console.print("[yellow]  No hay eventos en la línea de tiempo[/]")
    else:
        # Depuración - Mostrar cuántos eventos hay en la línea de tiempo
        console.print(f"[dim]  Total de eventos en línea de tiempo: {len(context['diagnosticTimeline'])}[/]")
        
        for i, event in enumerate(context["diagnosticTimeline"]):
            # Asegurar que timestamp sea un string
            event_timestamp = event["timestamp"]
            if isinstance(event_timestamp, datetime):
                timestamp_str = event_timestamp.isoformat().replace('T', ' ')[:19]
            else:
                # Convertir otros formatos de timestamp a string seguro
                timestamp_str = str(event_timestamp)
                # Intentar formatear si tiene formato ISO
                if isinstance(timestamp_str, str) and 'T' in timestamp_str:
                    timestamp_str = timestamp_str.replace('T', ' ')[:19]
            
            # Mostrar información del evento
            console.print(f"[bold]{i+1}. {timestamp_str}[/] - {event['description']} (Ingeniero: {event['engineer']})")
            
            # Contar los pasos
            step_count = len(event["steps"])
            if step_count == 0:
                console.print("   └─ [dim]No hay pasos detallados para este evento[/]")
            else:
                console.print(f"   └─ [dim]{step_count} paso(s) registrado(s)[/]")
                
                # Mostrar cada paso individual
                for j, step in enumerate(event["steps"]):
                    # Asegurar que el timestamp del paso sea un string
                    step_timestamp = step["timestamp"]
                    if isinstance(step_timestamp, datetime):
                        step_time = step_timestamp.isoformat().replace('T', ' ')[11:19]
                    else:
                        # Manejar diferentes formatos de timestamp
                        step_time = str(step_timestamp)
                        # Si parece ser un formato ISO
                        if isinstance(step_time, str):
                            if 'T' in step_time:
                                step_time = step_time.split('T')[1][:8]
                            elif ' ' in step_time:
                                step_time = step_time.split(' ')[1][:8]
                            else:
                                step_time = step_time[:8]  # Tomar los primeros 8 caracteres como fallback
                    
                    icon = "🖼️ " if step["hasImages"] else "📝 "
                    
                    # Extraer texto para mostrar (recortado si es muy largo)
                    text_preview = step["textContent"]
                    if len(text_preview) > 50:
                        text_preview = text_preview[:50] + "..."
                    
                    console.print(f"      {j+1}. {icon}[dim]{step_time}[/] - {text_preview}")
    
    # Capturas de pantalla
    if context["screenshots"]:
        console.print(f"\n[bold cyan]🖼️ {len(context['screenshots'])} CAPTURAS DE PANTALLA DISPONIBLES[/]")
        for i, ss in enumerate(context["screenshots"]):
            # Asegurar que el timestamp sea un string
            ss_timestamp = ss["timestamp"]
            if isinstance(ss_timestamp, datetime):
                ss_time = ss_timestamp.isoformat().replace('T', ' ')
            else:
                ss_time = str(ss_timestamp)
                if 'T' in ss_time:
                    ss_time = ss_time.replace('T', ' ')
            
            console.print(f"   {i+1}. [dim]{ss_time}[/] - {ss['associatedText']}")
    else:
        console.print("[dim]No hay capturas de pantalla registradas[/]")

def run_diagnostic_cli():
    """
    Ejecuta la interfaz de línea de comandos para el diagnóstico
    """
    console.print(Panel.fit(
        "[bold cyan]Amazon Bedrock Session Management APIs[/]\n"
        "[bold cyan]Demostración: Asistente de Diagnóstico para Infraestructura Cloud[/]",
        border_style="cyan"
    ))
    
    current_session_id = None
    
    while True:
        console.print("\n[bold cyan]MENÚ PRINCIPAL[/]")
        if current_session_id:
            console.print(f"[green]Sesión activa: {current_session_id}[/]")
        
        options = [
            "1. Crear nueva sesión de diagnóstico",
            "2. Registrar paso de diagnóstico",
            "3. Ver contexto completo de diagnóstico",
            "4. Finalizar sesión de diagnóstico",
            "5. Eliminar sesión",
            "6. Cambiar sesión activa",
            "7. Diagnosticar sesión (debug)",  
            "8. Salir"
        ]
        
        for option in options:
            console.print(option)
        
        choice = Prompt.ask("\nSeleccione una opción", choices=["1", "2", "3", "4", "5", "6", "7", "8"])
        
        if choice == "1":
            # Crear nueva sesión
            incident_id = Prompt.ask("ID del incidente")
            system_affected = Prompt.ask("Sistema afectado")
            severity = Prompt.ask("Severidad", choices=["high", "medium", "low"], default="high")
            
            session_id = create_troubleshooting_session(incident_id, system_affected, severity)
            if session_id:
                current_session_id = session_id
        
        elif choice == "2":
            # Registrar paso de diagnóstico
            if not current_session_id:
                console.print("[bold red]Error: No hay una sesión activa[/]")
                continue
                
            engineer_id = Prompt.ask("ID del ingeniero")
            component = Prompt.ask("Componente analizado")
            action = Prompt.ask("Acción ejecutada")
            result = Prompt.ask("Resultado observado (puede ser multilinea, finalice con ENTER vacío)")
            next_steps = Prompt.ask("Siguientes pasos recomendados")
            
            has_screenshots = Confirm.ask("¿Desea incluir capturas de pantalla?")
            screenshots = []
            
            if has_screenshots:
                while True:
                    screenshot_path = Prompt.ask("Ruta a la imagen (deje vacío para terminar)")
                    if not screenshot_path:
                        break
                    screenshots.append(screenshot_path)
            
            diagnostics_data = {
                "component": component,
                "action": action,
                "result": result,
                "next_steps": next_steps
            }
            
            store_diagnostic_step(current_session_id, engineer_id, diagnostics_data, screenshots)
        
        elif choice == "3":
            # Ver contexto completo
            if not current_session_id:
                session_id = Prompt.ask("ID de la sesión a consultar")
            else:
                session_id = current_session_id
                
            context = retrieve_diagnostic_context(session_id)
            if context:
                display_diagnostic_context(context)                               
        
        elif choice == "4":
            # Finalizar sesión
            if not current_session_id:
                session_id = Prompt.ask("ID de la sesión a finalizar")
            else:
                session_id = current_session_id
                
            resolution_type = Prompt.ask("Tipo de resolución", choices=["fix", "workaround", "escalation"])
            resolution_summary = Prompt.ask("Resumen de la resolución (puede ser multilinea, finalice con ENTER vacío)")
            
            success = end_diagnostic_session(session_id, resolution_summary, resolution_type)
            if success and session_id == current_session_id:
                if Confirm.ask("¿Desea iniciar una nueva sesión?"):
                    current_session_id = None
                    console.print("[yellow]Sesión finalizada. Seleccione 'Crear nueva sesión' para comenzar otra.[/]")
        
        elif choice == "5":
            # Eliminar sesión
            if not current_session_id:
                session_id = Prompt.ask("ID de la sesión a eliminar")
            else:
                session_id = current_session_id
                
            reason = Prompt.ask("Razón para eliminar la sesión")
            approver_id = Prompt.ask("ID del aprobador")
            
            success = delete_diagnostic_session(session_id, reason, approver_id)
            if success and session_id == current_session_id:
                current_session_id = None
                console.print("[yellow]Sesión eliminada. Ya no hay sesión activa.[/]")
        
        elif choice == "6":
            # Cambiar sesión activa
            session_id = Prompt.ask("ID de la nueva sesión activa")
            
            # Verificar que la sesión existe
            try:
                client.get_session(sessionIdentifier=session_id)
                current_session_id = session_id
                console.print(f"[green]Sesión activa cambiada a: {current_session_id}[/]")
            except ClientError as e:
                console.print(f"[bold red]Error: La sesión {session_id} no existe o no es accesible[/]")
        
        elif choice == "7":
            # Nueva opción de diagnóstico
            if not current_session_id:
                session_id = Prompt.ask("ID de la sesión a diagnosticar")
            else:
                session_id = current_session_id
                
            diagnose_session_management(session_id)
        
        elif choice == "8":
            # Salir (antes era la opción 7)
            if Confirm.ask("[yellow]¿Está seguro que desea salir?[/]"):
                console.print("[bold cyan]¡Gracias por utilizar la demostración de Session Management APIs![/]")
                break

def diagnose_session_management(session_id):
    """
    Realiza un diagnóstico completo de una sesión para identificar problemas.
    
    Args:
        session_id (str): ID de la sesión a diagnosticar
    """
    console.print(Panel.fit(f"[bold cyan]Diagnóstico de sesión: {session_id}[/]", border_style="cyan"))
    
    try:
        # 1. Verificar que la sesión existe
        console.print("[bold]1. Verificando existencia de sesión...[/]")
        try:
            session_response = client.get_session(sessionIdentifier=session_id)
            console.print("[green]✓ Sesión encontrada[/]")
            console.print(f"[dim]Metadatos: {json.dumps(session_response, default=str)[:200]}...[/]")
        except Exception as e:
            console.print(f"[bold red]✗ Error al recuperar sesión: {str(e)}[/]")
            return
        
        # 2. Probar creación de invocación
        console.print("\n[bold]2. Probando creación de invocación...[/]")
        try:
            invocation_response = client.create_invocation(
                sessionIdentifier=session_id,
                description="Invocación de diagnóstico"
            )
            invocation_id = invocation_response.get("invocationId")
            if invocation_id:
                console.print(f"[green]✓ Invocación creada exitosamente: {invocation_id}[/]")
            else:
                console.print(f"[yellow]⚠ Invocación creada pero sin ID: {invocation_response}[/]")
                return
        except Exception as e:
            console.print(f"[bold red]✗ Error al crear invocación: {str(e)}[/]")
            return
        
        # 3. Probar creación de paso de invocación
        console.print("\n[bold]3. Probando creación de paso de invocación...[/]")
        step_id = str(uuid.uuid4())
        try:
            step_response = client.put_invocation_step(
                sessionIdentifier=session_id,
                invocationIdentifier=invocation_id,
                invocationStepId=step_id,
                invocationStepTime=datetime.now().isoformat(),
                payload={
                    'contentBlocks': [{
                        'text': "Este es un paso de diagnóstico para verificar la funcionalidad de las APIs."
                    }]
                }
            )
            console.print(f"[green]✓ Paso de invocación creado exitosamente: {step_id}[/]")
            console.print(f"[dim]Respuesta: {json.dumps(step_response, default=str)[:200]}...[/]")
        except Exception as e:
            console.print(f"[bold red]✗ Error al crear paso de invocación: {str(e)}[/]")
            return
        
        # 4. Verificar listado de invocaciones
        console.print("\n[bold]4. Verificando listado de invocaciones...[/]")
        try:
            invocations_response = client.list_invocations(sessionIdentifier=session_id)
            invocations = invocations_response.get("invocations", [])
            console.print(f"[green]✓ {len(invocations)} invocaciones encontradas[/]")
            for i, inv in enumerate(invocations):
                console.print(f"  {i+1}. ID: {inv.get('invocationId')} - {inv.get('description')}")
        except Exception as e:
            console.print(f"[bold red]✗ Error al listar invocaciones: {str(e)}[/]")
            return
        
        # 5. Verificar pasos de la invocación de diagnóstico
        console.print(f"\n[bold]5. Verificando pasos de invocación {invocation_id}...[/]")
        try:
            steps_response = client.list_invocation_steps(
                sessionIdentifier=session_id,
                invocationIdentifier=invocation_id
            )
            steps = steps_response.get("invocationSteps", [])
            console.print(f"[green]✓ {len(steps)} pasos encontrados[/]")
            for i, step in enumerate(steps):
                console.print(f"  {i+1}. ID: {step.get('invocationStepId')}")
                
                # Intentar recuperar el contenido del paso
                try:
                    step_content = client.get_invocation_step(
                        sessionIdentifier=session_id,
                        invocationIdentifier=invocation_id,
                        invocationStepId=step.get('invocationStepId')
                    )
                    console.print(f"     [green]✓ Contenido recuperado correctamente[/]")
                except Exception as e:
                    console.print(f"     [red]✗ Error al recuperar contenido: {str(e)}[/]")
        except Exception as e:
            console.print(f"[bold red]✗ Error al listar pasos: {str(e)}[/]")
        
        console.print("\n[bold green]✅ Diagnóstico completado[/]")
        console.print("""
[bold cyan]Análisis y siguientes pasos:[/]
1. Si no se encontraron invocaciones en el paso 4, el problema está en la creación de invocaciones
2. Si se encontraron invocaciones pero no pasos, el problema está en la creación de pasos
3. Si todo funciona correctamente en esta prueba pero no en tu flujo principal, 
   revisa cómo estás manejando los IDs de sesión e invocación
        """)
        
    except Exception as e:
        console.print(f"[bold red]Error durante el diagnóstico: {str(e)}[/]")

if __name__ == "__main__":
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Demostración de Amazon Bedrock Session Management APIs')
    parser.add_argument('--region', type=str, default='us-east-1', help='Región de AWS (default: us-east-1)')
    
    args = parser.parse_args()
    
    try:
        # Inicializar cliente con la región especificada
        client = boto3.client('bedrock-agent-runtime', region_name=args.region)
        run_diagnostic_cli()
    except Exception as e:
        console.print(f"[bold red]Error fatal: {str(e)}[/]")
        sys.exit(1)
