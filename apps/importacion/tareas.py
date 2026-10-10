"""Tareas de Django-Q2; las ejecuta el contenedor worker (`manage.py qcluster`)."""

from apps.importacion import servicios


def procesar(documento_id):
    servicios.procesar_documento(documento_id)
