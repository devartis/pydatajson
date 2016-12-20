#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Módulo principal de pydatajson

Contiene la clase DataJson que reúne los métodos públicos para trabajar con
archivos data.json.
"""

from __future__ import unicode_literals
from __future__ import print_function
from __future__ import with_statement

import sys
import io
import os.path
from urlparse import urljoin, urlparse
import warnings
import json
import jsonschema
import requests
import unicodecsv as csv

ABSOLUTE_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class DataJson(object):
    """Métodos para trabajar con archivos data.json."""

    # Variables por default
    ABSOLUTE_SCHEMA_DIR = os.path.join(ABSOLUTE_PROJECT_DIR, "schemas")
    DEFAULT_CATALOG_SCHEMA_FILENAME = "catalog.json"

    def __init__(self,
                 schema_filename=DEFAULT_CATALOG_SCHEMA_FILENAME,
                 schema_dir=ABSOLUTE_SCHEMA_DIR):
        """Crea un manipulador de `data.json`s.

        Salvo que se indique lo contrario, el validador de esquemas asociado
        es el definido por default en las constantes de clase.

        Args:
            schema_filename (str): Nombre del archivo que contiene el esquema
                validador.
            schema_dir (str): Directorio (absoluto) donde se encuentra el
                esquema validador (y sus referencias, de tenerlas).
        """
        self.validator = self._create_validator(schema_filename, schema_dir)

    @classmethod
    def _create_validator(cls, schema_filename, schema_dir):
        """Crea el validador necesario para inicializar un objeto DataJson.

        Para poder resolver referencias inter-esquemas, un Validador requiere
        que se especifique un RefResolver (Resolvedor de Referencias) con el
        directorio base (absoluto) y el archivo desde el que se referencia el
        directorio.

        Para poder validar formatos, un Validador requiere que se provea
        explícitamente un FormatChecker. Actualmente se usa el default de la
        librería, jsonschema.FormatChecker().

        Args:
            schema_filename (str): Nombre del archivo que contiene el esquema
                validador "maestro".
            schema_dir (str): Directorio (absoluto) donde se encuentra el
                esquema validador maestro y sus referencias, de tenerlas.

        Returns:
            Draft4Validator: Un validador de JSONSchema Draft #4. El validador
                se crea con un RefResolver que resuelve referencias de
                `schema_filename` dentro de `schema_dir`.
        """
        schema_path = os.path.join(schema_dir, schema_filename)
        schema = cls._json_to_dict(schema_path)

        # Según https://github.com/Julian/jsonschema/issues/98
        # Permite resolver referencias locales a otros esquemas.
        resolver = jsonschema.RefResolver(
            base_uri=urljoin('file:', schema_path), referrer=schema)

        format_checker = jsonschema.FormatChecker()

        validator = jsonschema.Draft4Validator(
            schema=schema, resolver=resolver, format_checker=format_checker)

        return validator

    @staticmethod
    def _json_to_dict(dict_or_json_path):
        """Toma el path a un JSON y devuelve el diccionario que representa.

        Si el argumento es un dict, lo deja pasar. Si es un string asume que el
        parámetro es una URL si comienza con 'http' o 'https', o un path local
        de lo contrario.

        Args:
            dict_or_json_path (dict or str): Si es un str, path local o URL
                remota a un archivo de texto plano en formato JSON.

        Returns:
            dict: El diccionario que resulta de deserializar
                dict_or_json_path.

        """
        assert isinstance(dict_or_json_path, (dict, str, unicode))

        if isinstance(dict_or_json_path, dict):
            return dict_or_json_path

        parsed_url = urlparse(dict_or_json_path)

        if parsed_url.scheme in ["http", "https"]:
            req = requests.get(dict_or_json_path)
            json_string = req.content

        else:
            # En caso de que dict_or_json_path parezca ser una URL remota,
            # advertirlo
            path_start = parsed_url.path.split(".")[0]
            if path_start == "www" or path_start.isdigit():
                warnings.warn("""
La dirección del archivo JSON ingresada parece una URL, pero no comienza
con 'http' o 'https' así que será tratada como una dirección local. ¿Tal vez
quiso decir 'http://{}'?
                """.format(dict_or_json_path).encode("utf8"))

            with open(dict_or_json_path) as json_file:
                json_string = json_file.read()

        json_dict = json.loads(json_string, encoding="utf8")

        return json_dict

    def is_valid_catalog(self, datajson_path):
        """Valida que un archivo `data.json` cumpla con el schema definido.

        Chequea que el data.json tiene todos los campos obligatorios y que
        tanto los campos obligatorios como los opcionales siguen la estructura
        definida en el schema.

        Args:
            datajson_path (str): Path al archivo data.json a ser validado.

        Returns:
            bool: True si el data.json cumple con el schema, sino False.
        """
        datajson = self._json_to_dict(datajson_path)
        res = self.validator.is_valid(datajson)
        return res

    def validate_catalog(self, datajson_path):
        """Analiza un data.json registrando los errores que encuentra.

        Chequea que el data.json tiene todos los campos obligatorios y que
        tanto los campos obligatorios como los opcionales siguen la estructura
        definida en el schema.

        Args:
            datajson_path (str): Path al archivo data.json a ser validado.

        Returns:
            dict: Diccionario resumen de los errores encontrados::

                {
                    "status": "OK",  # resultado de la validación global
                    "error": {
                        "catalog": {
                            "status": "OK",
                            "errors": []
                            "title": "Título Catalog"},
                        "dataset": [
                            {
                                "status": "OK",
                                "errors": [],
                                "title": "Titulo Dataset 1"
                            },
                            {
                                "status": "ERROR",
                                "errors": [error1_info, error2_info, ...],
                                "title": "Titulo Dataset 2"
                            }
                        ]
                    }
                }

            Donde errorN_info es un dict con la información del N-ésimo
            error encontrado, con las siguientes claves: "path", "instance",
            "message", "validator", "validator_value", "error_code".

        """
        datajson = self._json_to_dict(datajson_path)

        # La respuesta por default se devuelve si no hay errores
        default_response = {
            "status": "OK",
            "error": {
                "catalog": {
                    "status": "OK",
                    "title": datajson.get("title"),
                    "errors": []
                },
                # "dataset" contiene lista de rtas default si el catálogo
                # contiene la clave "dataset" y además su valor es una lista.
                # En caso contrario "dataset" es None.
                "dataset": [
                    {
                        "status": "OK",
                        "title": dataset.get("title"),
                        "errors": []
                    } for dataset in datajson["dataset"]
                ] if ("dataset" in datajson and
                      isinstance(datajson["dataset"], list)) else None
            }
        }

        def _update_response(error, response):
            """Actualiza la respuesta por default acorde a un error de
            validación."""
            new_response = response.copy()

            # El status del catálogo entero será ERROR
            new_response["status"] = "ERROR"

            # Adapto la información del ValidationError recibido a los fines
            # del validador de DataJsons
            error_info = {
                # Error Code 1 para "campo obligatorio faltante"
                # Error Code 2 para "error en tipo o formato de campo"
                "error_code": 1 if error.validator == "required" else 2,
                "message": error.message,
                "validator": error.validator,
                "validator_value": error.validator_value,
                "path": list(error.path),
                # La instancia validada es irrelevante si el error es de tipo 1
                "instance": (None if error.validator == "required" else
                             error.instance)
            }

            # Identifico a qué nivel de jerarquía sucedió el error.
            if len(error.path) >= 2 and error.path[0] == "dataset":
                # El error está a nivel de un dataset particular o inferior
                position = new_response["error"]["dataset"][error.path[1]]
            else:
                # El error está a nivel de catálogo
                position = new_response["error"]["catalog"]

            position["status"] = "ERROR"
            position["errors"].append(error_info)

            return new_response

        # Genero la lista de errores en la instancia a validar
        errors_iterator = self.validator.iter_errors(datajson)

        final_response = default_response.copy()
        for error in errors_iterator:
            final_response = _update_response(error, final_response)

        return final_response

    def generate_datasets_report(self, catalogs, report_path):
        """Genera reporte de datasets de catálogos.

        Args:
            catalogs (str o list):
            report_path (str):
        """
        report_fieldnames = [
            'catalog_metadata_url', 'catalog_title', 'catalog_description',
            'dataset_title', 'dataset_accrualPeriodicity',
            'valid_dataset_metadata', 'harvest', 'dataset_description',
            'dataset_publisher_name', 'dataset_superTheme', 'dataset_theme',
            'dataset_landingPage', 'distributions_list'
        ]

        # Si se pasa un único catálogo, convertirlo en lista
        if isinstance(catalogs, (dict, str, unicode)):
            catalogs = [catalogs]

        with io.open(report_path, 'w', encoding='utf-8') as output:
            writer = csv.DictWriter(output, report_fieldnames)
            writer.writeheader()

            for catalog in catalogs:
                assert isinstance(catalog, (dict, str, unicode))

                if isinstance(catalog, (str, unicode)):
                    catalog_metadata_url = catalog
                    catalog = self._json_to_dict(catalog)
                else:
                    catalog_metadata_url = None

                validation = self.validate_catalog(catalog)

                for dataset, index in enumerate(catalog["dataset"]):

                    def _stringify_distribution(distribution):
                        title = distribution.get("title")
                        url = distribution.get("downloadURL")

                        return "\"{}\": {}".format(title, url)

                    distributions_list = "\n".join(
                        [_stringify_distribution(d) for d in
                         dataset["distribution"]])

                    dataset_report = {
                        "catalog_metadata_url": catalog_metadata_url,
                        "catalog_title": catalog.get("title"),
                        "catalog_description": catalog.get("description"),
                        "dataset_title": dataset.get("title"),
                        "dataset_accrualPeriodicity": dataset.get(
                            "accrualPeriodicity"),
                        "valid_dataset_metadata": (validation["error"][
                            "datasest"][index]["status"] == "OK"),
                        "harvest": False,
                        "dataset_description": dataset.get("description"),
                        # Esto explota si publisher no es un dict
                        "dataset_publisher_name": dataset.get("publisher").get(
                            "name"),
                        "dataset_superTheme": dataset.get("superTheme"),
                        "dataset_theme": dataset.get("theme"),
                        "dataset_landingPage": dataset.get("landingPage"),
                        "distributions_list": distributions_list
                    }

                    writer.writerow(dataset_report)

    def generate_harvester_config(self, datasets_report, config_path):
        """Genera archivo de configuración del harvester según el reporte.

        Args:
            datasets_report (str):
            config_path (str):
        """
        pass

    def generate_harvestable_catalogs(self, catalogs, datasets_report,
                                      write_to_file, files_dir):
        """Genera archivo de configuración del harvester según el reporte.

        Args:
            datasets_report (str):
            config_path (str):
            write_to_file (bool):
            files_dir (str):
        """
        pass


def main():
    """Permite ejecutar el módulo por línea de comandos.

    Valida un path o url a un archivo data.json devolviendo True/False si es
    válido y luego el resultado completo.

    Example:
        python pydatajson.py http://181.209.63.71/data.json
        python pydatajson.py ~/github/pydatajson/tests/samples/full_data.json
    """
    datajson_file = sys.argv[1]
    dj_instance = DataJson()
    bool_res = dj_instance.is_valid_catalog(datajson_file)
    full_res = dj_instance.validate_catalog(datajson_file)
    print(bool_res)
    print(json.dumps(full_res, separators=(",", ": "), indent=4))


if __name__ == '__main__':
    main()
