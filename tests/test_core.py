# -*- coding: utf-8 -*-

"""Tests del modulo pydatajson."""

from __future__ import print_function, unicode_literals, with_statement

import json
import os.path
import re
from collections import OrderedDict
from pprint import pprint

import nose
import vcr
from nose.tools import assert_true, assert_false, assert_equal, assert_list_equal, assert_raises, \
    assert_dict_equal, assert_regexp_matches
from six import iteritems, text_type

from tests.support.factories.core_files import TEST_FILE_RESPONSES
from .support.constants import BAD_DATAJSON_URL, BAD_DATAJSON_URL2
from .support.utils import jsonschema_str

try:
    import mock
except ImportError:
    from unittest import mock
import filecmp
import io
from .context import pydatajson
from .support.decorators import load_expected_result, RESULTS_DIR

my_vcr = vcr.VCR(path_transformer=vcr.VCR.ensure_suffix('.yaml'),
                 cassette_library_dir=os.path.join("tests", "cassetes"),
                 record_mode='once')


class TestDataJsonTestCase(object):
    SAMPLES_DIR = os.path.join("tests", "samples")
    RESULTS_DIR = RESULTS_DIR
    TEMP_DIR = os.path.join("tests", "temp")

    @classmethod
    def get_sample(cls, sample_filename):
        return os.path.join(cls.SAMPLES_DIR, sample_filename)

    @classmethod
    def setUp(cls):
        cls.dj = pydatajson.DataJson(cls.get_sample("full_data.json"))
        cls.catalog = pydatajson.readers.read_catalog(
            cls.get_sample("full_data.json"))
        cls.maxDiff = None
        cls.longMessage = True

    @classmethod
    def tearDown(cls):
        del (cls.dj)

    def run_case(self, case_filename, expected_dict=None):

        sample_path = os.path.join(self.SAMPLES_DIR, case_filename + ".json")
        result_path = os.path.join(self.RESULTS_DIR, case_filename + ".json")

        if expected_dict is None:
            with io.open(result_path, encoding='utf8') as result_file:
                expected_dict = json.load(result_file)

        response_bool = self.dj.is_valid_catalog(sample_path)
        response_dict = self.dj.validate_catalog(sample_path)

        print(text_type(json.dumps(
            response_dict, indent=4, separators=(",", ": "),
            ensure_ascii=False
        )))

        if expected_dict["status"] == "OK":
            assert_true(response_bool)
        elif expected_dict["status"] == "ERROR":
            assert_false(response_bool)
        else:
            raise Exception("LA RESPUESTA {} TIENE UN status INVALIDO".format(
                case_filename))

        assert_dict_equal.__self__.maxDiff = None
        assert_dict_equal(expected_dict, response_dict)

    # Tests de CAMPOS REQUERIDOS

    # Tests de inputs válidos
    def test_validity(self):
        for filename, value_or_none in iteritems(TEST_FILE_RESPONSES):
            yield self.run_case, filename, value_or_none

    def test_validity_of_invalid_dataset_type(self):
        """
        Validación ante un campo 'dataset' inválido en un catalogo
        :return:
        """
        case_filename = "invalid_dataset_type"
        expected_valid = False
        path = ['error', 'catalog', 'errors', 0, 'message']
        regex = '\{.*\} is not of type %s' % jsonschema_str('array')

        self.validate_message_with_file(case_filename, expected_valid, path, regex)

    def test_invalid_dataset_theme_type(self):
        case_filename = "invalid_dataset_theme_type"
        expected_valid = False
        path = ['error', 'dataset', 0, 'errors', 0, 'message']
        regex = "%s is not valid under any of the given schemas" % jsonschema_str('contrataciones')
        self.validate_message_with_file(case_filename, expected_valid, path, regex)

    def test_several_assorted_errors(self):
        case_filename = "several_assorted_errors"
        expected_errors = [
            (
                ['error', 'catalog', 'errors', ],
                "%s is a required property" % jsonschema_str('title')
            ),
            (
                ['error', 'catalog', 'errors', ],
                "%s is not valid under any of the given schemas" % jsonschema_str('')
            ),
            (
                ['error', 'catalog', 'errors', ], "%s is not a %s" % (
                    jsonschema_str('datosmodernizacion.gob.ar'), jsonschema_str('email'))
            ),
            (
                ['error', 'catalog', 'errors', ],
                "%s is not valid under any of the given schemas" % jsonschema_str('datos.gob.ar')
            ),
            (
                ['error', 'dataset', 0, 'errors', ],
                "123 is not valid under any of the given schemas"),
            (
                ['error', 'dataset', 0, 'errors', ],
                "\[.*\] is not of type %s" % jsonschema_str('object')
            ),
            (
                ['error', 'dataset', 0, 'errors', ],
                "\[%s\] is not valid under any of the given schemas" % jsonschema_str('string')
            ),
        ]

        for path, regex in expected_errors:
            self.validate_contains_message_with_file(case_filename, path, regex)

    def validate_message_with_file(self, case_filename, expected_valid, path, regex):
        sample_path = os.path.join(self.SAMPLES_DIR, case_filename + ".json")

        self.validate_string_in(sample_path, path, regex)
        self.validate_valid(sample_path, expected_valid)

    def validate_string_in(self, datajson, path, regex):
        response_dict = self.dj.validate_catalog(datajson)
        p = re.compile(regex)
        response = response_dict.copy()
        for key in path:
            response = response[key]
        assert_regexp_matches(response, p)

    def validate_valid(self, datajson, expected_valid):
        response_bool = self.dj.is_valid_catalog(datajson)
        if expected_valid:
            assert_true(response_bool)
        else:
            assert_false(response_bool)

    def validate_contains_message_with_file(self, case_filename, path, regex):
        sample_path = os.path.join(self.SAMPLES_DIR, case_filename + ".json")
        self.validate_contains_message(sample_path, path, regex)

    def validate_contains_message(self, datajson, path, regex):
        response_bool = self.dj.is_valid_catalog(datajson)
        response_dict = self.dj.validate_catalog(datajson)

        assert_false(response_bool)

        response = response_dict.copy()
        for key in path:
            response = response[key]

        p = re.compile(regex)
        matches = [p.match(error['message']) for error in response]
        assert_true(any(matches))

    @my_vcr.use_cassette('test_validate_bad_remote_datajson')
    def test_validate_invalid_remote_datajson_is_invalid(self):
        """ Testea `is_valid_catalog` contra un data.json remoto invalido."""

        res = self.dj.is_valid_catalog(BAD_DATAJSON_URL)
        assert_false(res)

    def test_validate_invalid_remote_datajson_has_errors(self):
        """ Testea `validate_catalog` contra un data.json remoto invalido."""

        errors = [
            (
                ['error', 'catalog', 'errors', ],
                "%s is too short" % jsonschema_str('')
            ),
            (
                ['error', 'catalog', 'errors', ],
                "%s is not a %s" % (jsonschema_str(''), jsonschema_str('email'))
            ),
        ]
        for path, regex in errors:
            with my_vcr.use_cassette('test_validate_bad_remote_datajson'):
                yield self.validate_contains_message, BAD_DATAJSON_URL, path, regex
        # assert_equal(exp, res)

    # Tests contra una URL REMOTA
    @my_vcr.use_cassette('test_validate_bad_remote_datajson2')
    def test_validate_invalid_remote_datajson_is_invalid2(self):
        """ Testea `is_valid_catalog` contra un data.json remoto invalido."""

        res = self.dj.is_valid_catalog(BAD_DATAJSON_URL2)
        assert_false(res)

    def test_validate_invalid_remote_datajson_has_errors2(self):
        """ Testea `validate_catalog` contra un data.json remoto invalido."""
        errors = [
            (
                ['error', 'catalog', 'errors', ],
                "%s is not a %s" % (jsonschema_str(''), jsonschema_str('email'))
            ),
            (
                ['error', 'catalog', 'errors', ],
                "%s is too short" % jsonschema_str('')
            ),
        ]
        for path, regex in errors:
            with my_vcr.use_cassette('test_validate_bad_remote_datajson2'):
                yield self.validate_contains_message, BAD_DATAJSON_URL2, path, regex

    def test_correctness_of_accrualPeriodicity_regex(self):
        """Prueba que la regex de validación de
        dataset["accrualPeriodicity"] sea correcta."""

        datajson_path = "tests/samples/full_data.json"
        datajson = json.load(open(datajson_path))

        valid_values = ['R/P10Y', 'R/P4Y', 'R/P3Y', 'R/P2Y', 'R/P1Y',
                        'R/P6M', 'R/P4M', 'R/P3M', 'R/P2M', 'R/P1M',
                        'R/P0.5M', 'R/P0.33M', 'R/P1W', 'R/P0.5W',
                        'R/P0.33W', 'R/P1D', 'R/PT1H', 'R/PT1S',
                        'eventual']

        for value in valid_values:
            datajson["dataset"][0]["accrualPeriodicity"] = value
            res = self.dj.is_valid_catalog(datajson)
            assert_true(res, msg=value)

        invalid_values = ['RP10Y', 'R/PY', 'R/P3', 'RR/P2Y', 'R/PnY',
                          'R/P6MT', 'R/PT', 'R/T1M', 'R/P0.M', '/P0.33M',
                          'R/P1Week', 'R/P.5W', 'R/P', 'R/T', 'R/PT1H3M',
                          'eventual ', '']

        for value in invalid_values:
            datajson["dataset"][0]["accrualPeriodicity"] = value
            res = self.dj.is_valid_catalog(datajson)
            assert_false(res, msg=value)

    # TESTS DE catalog_report
    # Reporte esperado para "full_data.json", con harvest = 0
    LOCAL_URL = os.path.join(SAMPLES_DIR, "full_data.json")
    EXPECTED_REPORT = [
        OrderedDict([(u'catalog_metadata_url', u'tests/samples/full_data.json'),
                     (u'catalog_federation_id', u'modernizacion'),
                     (u'catalog_federation_org', None),
                     (u'catalog_title', u'Datos Argentina'),
                     (u'catalog_description',
                      u'Portal de Datos Abiertos del Gobierno de la Rep\xfablica Argentina'),
                     (u'valid_catalog_metadata', 1),
                     (u'valid_dataset_metadata', 1),
                     (u'dataset_index', 0),
                     (u'harvest', 1),
                     (u'dataset_identifier',
                      u'99db6631-d1c9-470b-a73e-c62daa32c777'),
                     (u'dataset_title',
                      u'Sistema de contrataciones electr\xf3nicas'),
                     (u'dataset_accrualPeriodicity', u'R/P1Y'),
                     (u'dataset_description',
                      u'Datos correspondientes al Sistema de Contrataciones Electr\xf3nicas (Argentina Compra)'),
                     (u'dataset_publisher_name',
                      u'Ministerio de Modernizaci\xf3n. Secretar\xeda de Modernizaci\xf3n Administrativa. Oficina Nacional de Contrataciones'),
                     (u'dataset_superTheme', u'econ'),
                     (u'dataset_theme',
                      u'contrataciones, compras, convocatorias'),
                     (u'dataset_landingPage',
                      u'http://datos.gob.ar/dataset/sistema-de-contrataciones-electronicas-argentina-compra'),
                     (u'dataset_landingPage_generated',
                      u'dataset/99db6631-d1c9-470b-a73e-c62daa32c777'),
                     (u'dataset_issued',
                      u'2016-04-14T19:48:05.433640-03:00'),
                     (u'dataset_modified',
                      u'2016-04-19T19:48:05.433640-03:00'),
                     (u'distributions_formats', '{"CSV": 1}'),
                     (u'distributions_list',
                      u'"Convocatorias abiertas durante el a\xf1o 2015": http://186.33.211.253/dataset/99db6631-d1c9-470b-a73e-c62daa32c420/resource/4b7447cb-31ff-4352-96c3-589d212e1cc9/download/convocatorias-abiertas-anio-2015.csv'),
                     (u'dataset_license',
                      u'Open Data Commons Open Database License 1.0'),
                     (u'dataset_language', u'spa'),
                     (u'dataset_spatial', u'ARG'),
                     (u'dataset_temporal', u'2015-01-01/2015-12-31'),
                     (u'notas', u'')]),
        OrderedDict([(u'catalog_metadata_url', u'tests/samples/full_data.json'),
                     (u'catalog_federation_id',
                      u'modernizacion'),
                     (u'catalog_federation_org', None),
                     (u'catalog_title',
                      u'Datos Argentina'),
                     (u'catalog_description',
                      u'Portal de Datos Abiertos del Gobierno de la Rep\xfablica Argentina'),
                     (u'valid_catalog_metadata', 1),
                     (u'valid_dataset_metadata', 1),
                     (u'dataset_index', 1),
                     (u'harvest', 1),
                     (u'dataset_identifier',
                      u'99db6631-d1c9-470b-a73e-c62daa32c420'),
                     (u'dataset_title',
                      u'Sistema de contrataciones electr\xf3nicas (sin datos)'),
                     (u'dataset_accrualPeriodicity',
                      u'R/P1Y'),
                     (u'dataset_description',
                      u'Datos correspondientes al Sistema de Contrataciones Electr\xf3nicas (Argentina Compra) (sin datos)'),
                     (u'dataset_publisher_name',
                      u'Ministerio de Modernizaci\xf3n. Secretar\xeda de Modernizaci\xf3n Administrativa. Oficina Nacional de Contrataciones'),
                     (u'dataset_superTheme',
                      u'ECON'),
                     (u'dataset_theme',
                      u'contrataciones, compras, convocatorias'),
                     (u'dataset_landingPage',
                      u'http://datos.gob.ar/dataset/sistema-de-contrataciones-electronicas-argentina-compra'),
                     (u'dataset_landingPage_generated',
                      u'dataset/99db6631-d1c9-470b-a73e-c62daa32c420'),
                     (u'dataset_issued',
                      u'2016-04-14T19:48:05.433640-03:00'),
                     (u'dataset_modified',
                      u'2016-04-19T19:48:05.433640-03:00'),
                     (u'distributions_formats',
                      '{"PDF": 1}'),
                     (u'distributions_list',
                      u'"Convocatorias abiertas durante el a\xf1o 2015": http://186.33.211.253/dataset/99db6631-d1c9-470b-a73e-c62daa32c420/resource/4b7447cb-31ff-4352-96c3-589d212e1cc9/download/convocatorias-abiertas-anio-2015.pdf'),
                     (u'dataset_license',
                      u'Open Data Commons Open Database License 1.0'),
                     (u'dataset_language',
                      u'spa'),
                     (u'dataset_spatial',
                      u'ARG'),
                     (u'dataset_temporal',
                      u'2015-01-01/2015-12-31'),
                     (u'notas', u'No tiene distribuciones con datos.')])]

    def test_catalog_report_harvest_good(self):
        """catalog_report() marcará para cosecha los datasets con metadata
        válida si harvest='valid'."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        actual = self.dj.catalog_report(
            catalog, harvest='good', catalog_id="modernizacion")

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 1
        expected[1]["harvest"] = 0

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        assert_equal(actual[1]["harvest"], expected[1]["harvest"])
        # Compruebo que toda la lista sea la esperada
        assert_list_equal(actual, expected)

    def test_catalog_report_harvest_valid(self):
        """catalog_report() marcará para cosecha los datasets con metadata
        válida si harvest='valid'."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        actual = self.dj.catalog_report(
            catalog, harvest='valid', catalog_id="modernizacion")

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 1
        expected[1]["harvest"] = 1

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        # Compruebo que toda la lista sea la esperada
        print(actual)
        assert_list_equal(actual, expected)

    def test_catalog_report_harvest_none(self):
        """catalog_report() no marcará ningún dataset para cosecha si
        harvest='none'."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        actual = self.dj.catalog_report(
            catalog, harvest='none', catalog_id="modernizacion")

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 0
        expected[1]["harvest"] = 0

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        # Compruebo que toda la lista sea la esperada
        assert_list_equal(actual, expected)

    def test_catalog_report_harvest_all(self):
        """catalog_report() marcará todo dataset para cosecha si
        harvest='all'."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        actual = self.dj.catalog_report(
            catalog, harvest='all', catalog_id="modernizacion")

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 1
        expected[1]["harvest"] = 1

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        # Compruebo que toda la lista sea la esperada
        assert_list_equal(actual, expected)

    def test_catalog_report_harvest_report(self):
        """catalog_report() marcará para cosecha los datasets presentes en
        `report` si harvest='report'."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        # Compruebo que no se harvestee nada si el reporte no incluye el
        # dataset del catálogo
        report = [("data.json", "Un dataset que no es")]
        actual = self.dj.catalog_report(
            catalog, harvest='report', report=report,
            catalog_id="modernizacion"
        )

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 0
        expected[1]["harvest"] = 0

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        # Compruebo que toda la lista sea la esperada
        assert_list_equal(actual, expected)

        # Compruebo que sí se harvestee si el reporte incluye el dataset del
        # catálogo
        report = [(os.path.join(self.SAMPLES_DIR, "full_data.json"),
                   "Sistema de contrataciones electrónicas")]
        actual = self.dj.catalog_report(
            catalog, harvest='report',
            report=report, catalog_id="modernizacion")

        expected = list(self.EXPECTED_REPORT)
        expected[0]["harvest"] = 1

        # Compruebo explícitamente que el valor de 'harvest' sea el esperado
        assert_equal(actual[0]["harvest"], expected[0]["harvest"])
        # Compruebo que toda la lista sea la esperada
        assert_list_equal(actual, expected)

    @nose.tools.raises(ValueError)
    def test_catalog_report_harvest_report_without_report_file(self):
        """Si harvest='report' y report='None', se levanta un ValueError."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")
        self.dj.catalog_report(catalog, harvest='report')

    @nose.tools.raises(ValueError)
    def test_catalog_report_invalid_harvest_value(self):
        """Si harvest not in ["all", "none", "valid", "report"] se levanta un
        ValueError."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")
        self.dj.catalog_report(catalog, harvest='harvest')

    def test_catalog_report_missing_datasets(self):
        """Si la clave "dataset" de un catalogo no esta presente, el reporte es
        una tabla vacía."""
        catalog = os.path.join(self.SAMPLES_DIR, "missing_dataset.json")
        assert_list_equal(self.dj.catalog_report(catalog), [])

    def test_generate_datasets_report(self):
        """generate_datasets_report() debe unir correctamente los resultados de
        catalog_report()"""

        return_value = [{"ckan": "in a box", "portal": "andino", "capo": "si"}]
        self.dj.catalog_report = mock.MagicMock(return_value=return_value)

        catalogs = ["catalogo A", "catalogo B", "catalogo C"]
        actual = self.dj.generate_datasets_report(catalogs)

        expected = []
        for catalog in catalogs:
            expected.extend(return_value)

        assert_equal(actual, expected)

    def test_generate_datasets_report_single_catalog(self):
        """Invocar generate_datasets_report con una str que sea la ruta a un
        catálogo, o con una lista que sólo contenga esa misma string dan el
        mismo resultado."""
        catalog_str = os.path.join(self.SAMPLES_DIR, "full_data.json")
        catalog_list = [catalog_str]

        report_str = self.dj.generate_datasets_report(catalog_str)
        report_list = self.dj.generate_datasets_report(catalog_list)

        assert_list_equal(report_str, report_list)

    @mock.patch('pydatajson.writers.write_table')
    def test_export_generate_datasets_report(self, write_table_mock):
        """Si se pasa una ruta en `export_path`, generate_datasets_report llama
        a writers.write_table."""
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        self.dj.generate_datasets_report(catalog, export_path="una ruta")

        pydatajson.writers.write_table.assert_called_once()

    def test_generate_harvester_config_freq_none(self):
        """generate_harvester_config() debe filtrar el resultado de
        generate_datasets_report() a únicamente los 3 campos requeridos, y
        conservar el accrualPeriodicity original."""

        datasets_report = [
            {
                "catalog_metadata_url": 1,
                "dataset_title": 1,
                "dataset_accrualPeriodicity": 1,
                "otra key": 1,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",
                "harvest": 0
            },
            {
                "catalog_metadata_url": 2,
                "dataset_title": 2,
                "dataset_accrualPeriodicity": 2,
                "otra key": 2,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",

                "harvest": 1
            },
            {
                "catalog_metadata_url": 3,
                "dataset_title": 3,
                "dataset_accrualPeriodicity": 3,
                "otra key": 3,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",

                "harvest": 1
            }
        ]

        expected_config = [
            {
                "catalog_metadata_url": 2,
                "dataset_title": 2,
                "dataset_accrualPeriodicity": 2,
                "dataset_owner_org": "organizacion-en-ckan",
                "job_name": "organismo",
            },
            {
                "catalog_metadata_url": 3,
                "dataset_title": 3,
                "dataset_accrualPeriodicity": 3,
                "dataset_owner_org": "organizacion-en-ckan",
                "job_name": "organismo",
            }
        ]

        self.dj.generate_datasets_report = mock.MagicMock(
            return_value=datasets_report)

        actual_config = self.dj.generate_harvester_config(
            catalogs="un catalogo", harvest='valid', frequency=None)

        assert_list_equal(actual_config, expected_config)

    def test_generate_harvester_config_no_freq(self):
        """generate_harvester_config() debe filtrar el resultado de
        generate_datasets_report() a únicamente los 3 campos requeridos, y
        usar "R/P1D" como accrualPeriodicity"""

        datasets_report = [
            {
                "catalog_metadata_url": 1,
                "dataset_title": 1,
                "dataset_accrualPeriodicity": 1,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",
                "otra key": 1,
                "harvest": 0
            },
            {
                "catalog_metadata_url": 2,
                "dataset_title": 2,
                "dataset_accrualPeriodicity": 2,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",
                "otra key": 2,
                "harvest": 1
            },
            {
                "catalog_metadata_url": 3,
                "dataset_title": 3,
                "dataset_accrualPeriodicity": 3,
                "catalog_federation_org": "organizacion-en-ckan",
                "catalog_federation_id": "organismo",
                "otra key": 3,
                "harvest": 1
            }
        ]

        expected_config = [
            {
                "catalog_metadata_url": 2,
                "dataset_title": 2,
                "dataset_accrualPeriodicity": "R/P1D",
                "dataset_owner_org": "organizacion-en-ckan",
                "job_name": "organismo",
            },
            {
                "catalog_metadata_url": 3,
                "dataset_title": 3,
                "dataset_accrualPeriodicity": "R/P1D",
                "dataset_owner_org": "organizacion-en-ckan",
                "job_name": "organismo",
            }
        ]

        self.dj.generate_datasets_report = mock.MagicMock(
            return_value=datasets_report)

        actual_config = self.dj.generate_harvester_config(
            catalogs="un catalogo", harvest='valid')

        assert_list_equal(actual_config, expected_config)

    # TESTS DE GENERATE_HARVESTABLE_CATALOGS

    CATALOG = {
        "title": "Micro Catalogo",
        "dataset": [
            {
                "title": "Dataset Valido",
                "description": "Descripción valida",
                "distribution": []
            },
            {
                "title": "Dataset Invalido"
            }
        ]
    }

    @mock.patch('pydatajson.readers.read_catalog',
                return_value=CATALOG.copy())
    def test_generate_harvestable_catalogs_all(self, patched_read_catalog):

        catalogs = ["URL Catalogo A", "URL Catalogo B"]

        expected = [pydatajson.readers.read_catalog(c) for c in catalogs]
        actual = self.dj.generate_harvestable_catalogs(catalogs, harvest='all')

        assert_equal(actual, expected)

    @mock.patch('pydatajson.readers.read_catalog',
                return_value=CATALOG.copy())
    def test_generate_harvestable_catalogs_none(self, patched_read_catalog):

        catalogs = ["URL Catalogo A", "URL Catalogo B"]

        harvest_none = self.dj.generate_harvestable_catalogs(
            catalogs, harvest='none')

        for catalog in harvest_none:
            # Una lista vacía es "falsa"
            assert_false(catalog["dataset"])

    REPORT = [
        {
            "catalog_metadata_url": "URL Catalogo A",
            "dataset_title": "Dataset Valido",
            "dataset_accrualPeriodicity": "eventual",
            "harvest": 1
        },
        {
            "catalog_metadata_url": "URL Catalogo A",
            "dataset_title": "Dataset Invalido",
            "dataset_accrualPeriodicity": "eventual",
            "harvest": 0
        },
        {
            "catalog_metadata_url": "URL Catalogo B",
            "dataset_title": "Dataset Valido",
            "dataset_accrualPeriodicity": "eventual",
            "harvest": 1
        },
        {
            "catalog_metadata_url": "URL Catalogo B",
            "dataset_title": "Dataset Invalido",
            "dataset_accrualPeriodicity": "eventual",
            "harvest": 0
        }
    ]

    @mock.patch('pydatajson.DataJson.generate_datasets_report',
                return_value=REPORT)
    @mock.patch('pydatajson.readers.read_catalog',
                return_value=CATALOG.copy())
    def test_generate_harvestable_catalogs_valid(self, mock_read_catalog,
                                                 mock_gen_dsets_report):

        catalogs = ["URL Catalogo A", "URL Catalogo B"]

        expected_catalog = {
            "title": "Micro Catalogo",
            "dataset": [
                {
                    "title": "Dataset Valido",
                    "description": "Descripción valida",
                    "distribution": []
                }
            ]
        }
        expected = [expected_catalog, expected_catalog]

        actual = self.dj.generate_harvestable_catalogs(
            catalogs, harvest='valid')

        assert_list_equal(actual, expected)

    @mock.patch('pydatajson.DataJson.generate_datasets_report',
                return_value=REPORT)
    @mock.patch('pydatajson.readers.read_catalog',
                return_value=CATALOG.copy())
    def test_generate_harvestable_catalogs_report(self, mock_read_catalog,
                                                  mock_gen_dsets_report):

        catalogs = ["URL Catalogo A", "URL Catalogo B"]

        expected_catalog = {
            "title": "Micro Catalogo",
            "dataset": [
                {
                    "title": "Dataset Valido",
                    "description": "Descripción valida",
                    "distribution": []
                }
            ]
        }
        expected = [expected_catalog, expected_catalog]

        datasets_to_harvest = [
            ("URL Catalogo A", "Dataset Valido"),
            ("URL Catalogo B", "Dataset Valido")
        ]

        actual = self.dj.generate_harvestable_catalogs(
            catalogs, harvest='report', report=datasets_to_harvest)

        # `expected` es igual que en la prueba anterior.
        assert_list_equal(actual, expected)

    def test_generate_datasets_summary(self):
        """Genera informe conciso sobre datasets correctamente."""
        catalog = os.path.join(self.SAMPLES_DIR,
                               "several_datasets_for_harvest.json")
        actual = self.dj.generate_datasets_summary(catalog)
        expected = [
            OrderedDict([('indice', 0),
                         ('titulo', 'Sistema de contrataciones electrónicas UNO'),
                         ('identificador', None),
                         ('estado_metadatos', 'ERROR'),
                         ('cant_errores', 4),
                         ('cant_distribuciones', 4)]),
            OrderedDict([('indice', 1),
                         ('titulo', 'Sistema de contrataciones electrónicas DOS'),
                         ('identificador', None),
                         ('estado_metadatos', 'OK'),
                         ('cant_errores', 0),
                         ('cant_distribuciones', 1)]),
            OrderedDict([('indice', 2),
                         ('titulo', 'Sistema de contrataciones electrónicas TRES'),
                         ('identificador', None),
                         ('estado_metadatos', 'OK'),
                         ('cant_errores', 0),
                         ('cant_distribuciones', 1)])]

        assert_list_equal(actual, expected)

    @my_vcr.use_cassette()
    def test_generate_catalog_readme(self):
        """Genera README para presentar un catálogo."""
        catalog = os.path.join(self.SAMPLES_DIR,
                               "several_datasets_for_harvest.json")
        actual_filename = os.path.join(self.TEMP_DIR, "catalog_readme.md")

        expected_filename = os.path.join(self.RESULTS_DIR, "catalog_readme.md")

        self.dj.generate_catalog_readme(catalog, export_path=actual_filename)

        comparison = filecmp.cmp(actual_filename, expected_filename)
        if comparison:
            os.remove(actual_filename)
        else:
            """
{} se escribió correctamente, pero no es idéntico al esperado. Por favor,
revíselo manualmente""".format(actual_filename)

        assert_true(comparison)

    @my_vcr.use_cassette()
    def test_generate_catalog_indicators(self):
        catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        # Resultados esperados haciendo cuentas manuales sobre el catálogo
        expected = {
            'datasets_cant': 3,
            'distribuciones_cant': 6,
            'datasets_meta_ok_cant': 2,
            'datasets_meta_error_cant': 1,
            'datasets_meta_ok_pct': round(100 * float(2) / 3, 2),
        }

        for k, v in expected.items():
            assert_true(indicators[k], v)

    @my_vcr.use_cassette()
    def test_date_indicators(self):
        from datetime import datetime
        catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]
        dias_diff = (datetime.now() - datetime(2016, 4, 14)).days

        expected = {
            'catalogo_ultima_actualizacion_dias': dias_diff,
            'datasets_actualizados_cant': 1,
            'datasets_desactualizados_cant': 2,
            'datasets_actualizados_pct': 100 * round(float(1) / 3, 2),
            'datasets_frecuencia_cant': {
                'R/P1W': 1,
                'R/P1M': 1,
                'eventual': 1
            },
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    @my_vcr.use_cassette()
    def test_format_indicators(self):
        catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        expected = {
            'distribuciones_formatos_cant': {
                'CSV': 1,
                'XLSX': 1,
                'PDF': 1
            }
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    def test_field_indicators_on_min_catalog(self):
        catalog = os.path.join(self.SAMPLES_DIR, "minimum_data.json")

        # Se espera un único catálogo como resultado, índice 0
        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        expected = {
            'campos_recomendados_pct': 0.0,
            'campos_optativos_pct': 0.0,
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    def test_field_indicators_on_full_catalog(self):
        catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        # Se espera un único catálogo como resultado, índice 0
        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        expected = {
            'campos_recomendados_pct': 95.45,
            'campos_optativos_pct': 100
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    def test_federation_indicators_same_catalog(self):
        catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")

        indicators = self.dj.generate_catalogs_indicators(catalog, catalog)[1]

        # Esperado: todos los datasets están federados
        expected = {
            'datasets_federados_cant': 3,
            'datasets_no_federados_cant': 0,
            'datasets_no_federados': [],
            'datasets_federados_pct': 100
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    def test_federation_indicators_no_datasets(self):
        catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")
        central = os.path.join(self.SAMPLES_DIR, "catalogo_justicia.json")
        indicators = self.dj.generate_catalogs_indicators(catalog, central)[1]

        # Esperado: ningún dataset está federado
        expected = {
            'datasets_federados_cant': 0,
            'datasets_no_federados_cant': 3,
            'datasets_no_federados': [
                ('Sistema de contrataciones electrónicas UNO', None),
                ('Sistema de contrataciones electrónicas DOS', None),
                ('Sistema de contrataciones electrónicas TRES', None)],
            'datasets_federados_pct': 0
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    def test_federation_indicators_removed_datasets(self):

        # CASO 1
        # se buscan los datasets federados en el central que fueron eliminados
        # en el específico pero no se encuentran porque el publisher.name no
        # tiene publicado ningún otro dataset en el catálogo específico
        catalog = os.path.join(
            self.SAMPLES_DIR, "catalogo_justicia_removed.json"
        )
        central = os.path.join(self.SAMPLES_DIR, "catalogo_justicia.json")
        indicators = self.dj.generate_catalogs_indicators(catalog, central)[1]

        # Esperado: no se encuentra el dataset removido, porque el
        # publisher.name no existe en ningún otro dataset
        expected = {
            "datasets_federados_eliminados_cant": 0,
            "datasets_federados_eliminados": []
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

        # CASO 2
        # se buscan los datasets federados en el central que fueron eliminados
        # en el específico y se encuentran porque el publisher.name tiene
        # publicado otro dataset en el catálogo específico
        catalog = os.path.join(
            self.SAMPLES_DIR, "catalogo_justicia_removed_publisher.json"
        )
        indicators = self.dj.generate_catalogs_indicators(catalog, central)[1]
        # Esperado: no se encuentra el dataset removido, porque el
        # publisher.name no existe en ningún otro dataset
        expected = {
            "datasets_federados_eliminados_cant": 1,
            "datasets_federados_eliminados": [(
                'Base de datos legislativos Infoleg',
                "http://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg"
            )]
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v)

    @my_vcr.use_cassette()
    def test_network_indicators(self):
        one_catalog = os.path.join(self.SAMPLES_DIR, "several_datasets.json")
        other_catalog = os.path.join(self.SAMPLES_DIR, "full_data.json")

        indicators, network_indicators = self.dj.generate_catalogs_indicators([
            one_catalog,
            other_catalog
        ])

        # Esperado: suma de los indicadores individuales
        # No se testean los indicadores de actualización porque las fechas no
        # se mantienen actualizadas
        expected = {
            'catalogos_cant': 2,
            'datasets_cant': 5,
            'distribuciones_cant': 8,
            'datasets_meta_ok_cant': 4,
            'datasets_meta_error_cant': 1,
            'datasets_meta_ok_pct': 100 * float(4) / 5,
            'distribuciones_formatos_cant': {
                'CSV': 2,
                'XLSX': 1,
                'PDF': 2
            },
            'campos_optativos_pct': 33.33,
            'campos_recomendados_pct': 50.72,
        }

        for k, v in expected.items():
            assert_equal(network_indicators[k], v)

    @my_vcr.use_cassette()
    def test_indicators_invalid_periodicity(self):
        catalog = os.path.join(self.SAMPLES_DIR,
                               "malformed_accrualperiodicity.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        # Periodicidad inválida se considera automáticamente como
        # catálogo desactualizado
        expected = {
            'datasets_actualizados_cant': 0,
            'datasets_desactualizados_cant': 1,
            'datasets_actualizados_pct': 0
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v, k)

    @my_vcr.use_cassette()
    def test_indicators_missing_periodicity(self):
        catalog = os.path.join(self.SAMPLES_DIR, "missing_periodicity.json")

        # Dataset con periodicidad faltante no aporta valores para indicadores
        # de tipo 'datasets_(des)actualizados'
        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]
        expected = {
            'datasets_actualizados_cant': 0,
            'datasets_desactualizados_cant': 0,
            'datasets_actualizados_pct': 0
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v, k)

    @my_vcr.use_cassette()
    def test_indicators_missing_dataset(self):
        catalog = os.path.join(self.SAMPLES_DIR, "missing_dataset.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]

        # Catálogo sin datasets no aporta indicadores significativos
        expected = {
            'datasets_cant': 0,
            'datasets_meta_ok_cant': 0,
            'datasets_meta_error_cant': 0,
            'datasets_actualizados_cant': 0,
            'datasets_desactualizados_cant': 0,
            'datasets_actualizados_pct': 0,
            'distribuciones_formatos_cant': {},
            'datasets_frecuencia_cant': {}
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v, k)

    @my_vcr.use_cassette()
    def test_last_updated_indicator_missing_issued_field(self):
        from datetime import datetime
        catalog = os.path.join(self.SAMPLES_DIR, "minimum_data.json")

        indicators = self.dj.generate_catalogs_indicators(catalog)[0][0]
        dias_diff = (datetime.now() - datetime(2016, 4, 14)).days

        # Catálogo no tiene 'issued', pero su dataset sí -> uso el del dataset
        expected = {
            'catalogo_ultima_actualizacion_dias': dias_diff
        }

        for k, v in expected.items():
            assert_equal(indicators[k], v, k)

    def test_dataset_is_updated(self):
        catalog = os.path.join(self.SAMPLES_DIR, "catalogo_justicia.json")

        # Datasset con periodicity mensual vencida
        dataset = "Base de datos legislativos Infoleg"
        assert_false(self.dj.dataset_is_updated(catalog, dataset))

        # Dataset con periodicity eventual, siempre True
        dataset = "Declaración Jurada Patrimonial Integral de carácter público"
        assert_true(self.dj.dataset_is_updated(catalog, dataset))

    def test_date_network_indicators_empty_catalog(self):
        catalog = os.path.join(self.SAMPLES_DIR, "invalid_catalog_empty.json")
        indics, network_indics = self.dj.generate_catalogs_indicators(
            [catalog,
             catalog]
        )

        for k, v in network_indics.items():
            assert_true(v is not None)

    def test_DataJson_constructor(self):
        for key, value in iteritems(self.catalog):
            assert_equal(self.dj[key], value)

    def test_datasets_property(self):
        """La propiedad datasets equivale a clave 'dataset' de un catalog."""
        assert_equal(self.dj.datasets, self.catalog["dataset"])
        assert_equal(self.dj.datasets, self.dj["dataset"])

    @load_expected_result()
    def test_datasets(self, expected_result):
        datasets = self.dj.get_datasets()
        pprint(datasets)
        assert_equal(expected_result, datasets)

        datasets = self.dj.datasets
        pprint(datasets)
        assert_equal(expected_result, datasets)

    def test_datasets_without_catalog(self):
        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            datasets = dj.get_datasets()

        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            datasets = dj.datasets

    def test_distributions_property(self):
        """La propiedad distributions equivale a clave 'distribution' de un catalog."""
        distributions = []
        for dataset in self.catalog["dataset"]:
            for distribution in dataset["distribution"]:
                distribution["dataset_identifier"] = dataset["identifier"]
                distributions.append(distribution)
        assert_equal(self.dj.distributions, distributions)

        distributions = []
        for dataset in self.dj["dataset"]:
            for distribution in dataset["distribution"]:
                distribution["dataset_identifier"] = dataset["identifier"]
                distributions.append(distribution)
        assert_equal(self.dj.distributions, distributions)

    @load_expected_result()
    def test_distributions(self, expected_result):
        distributions = self.dj.get_distributions()
        pprint(distributions)
        assert_equal(expected_result, distributions)

        distributions = self.dj.distributions
        pprint(distributions)
        assert_equal(expected_result, distributions)

    def test_distributions_without_catalog(self):
        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            distributions = dj.get_distributions()

        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            distributions = dj.distributions

    def test_fields_property(self):
        """La propiedad fields equivale a clave 'field' de un catalog."""
        fields = []
        for dataset in self.catalog["dataset"]:
            for distribution in dataset["distribution"]:
                if "field" in distribution:
                    for field in distribution["field"]:
                        field["dataset_identifier"] = dataset["identifier"]
                        field["distribution_identifier"] = distribution[
                            "identifier"]
                        fields.append(field)
        assert_equal(self.dj.fields, fields)

        fields = []
        for dataset in self.dj["dataset"]:
            for distribution in dataset["distribution"]:
                if "field" in distribution:
                    for field in distribution["field"]:
                        field["dataset_identifier"] = dataset["identifier"]
                        field["distribution_identifier"] = distribution[
                            "identifier"]
                        fields.append(field)
        assert_equal(self.dj.fields, fields)

    @load_expected_result()
    def test_fields(self, expected_result):
        fields = self.dj.get_fields()
        pprint(fields)
        assert_equal(expected_result, fields)

        fields = self.dj.fields
        pprint(fields)
        assert_equal(expected_result, fields)

    def test_fields_without_catalog(self):
        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            fields = dj.get_fields()

        with assert_raises(KeyError):
            dj = pydatajson.DataJson()
            fields = dj.fields


if __name__ == '__main__':
    nose.run(defaultTest=__name__)
