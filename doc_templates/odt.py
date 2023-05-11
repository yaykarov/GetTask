# -*- coding: utf-8 -*-

import io
import os
import subprocess
import xml
import zipfile

from tempfile import NamedTemporaryFile

from django.http import HttpResponse


_CONTENT_FNAME = 'content.xml'


def _cells(tree, cell_ids):
    for cell_id in cell_ids:
        parents = tree.findall('.//*[@id="{}"]/..'.format(cell_id))
        if parents:
            parent = parents[0]
            children = list(parent)
            found = False
            for child in children:
                if not found:
                    if cell_id == child.get('id'):
                        found = True
                if found:
                    subchildren = list(child)
                    if subchildren:
                        yield subchildren[0]


def _write_sequence(tree, cell_ids, text):
    i = 0
    for cell in _cells(tree, cell_ids):
        if i < len(text):
            cell.text = text.upper()[i]
        else:
            break
        i += 1


def _write(tree, cell_id, text):
    cells = tree.findall('.//*[@id="{}"]'.format(cell_id))
    if cells:
        cell = cells[0]
        cell.text = text


def _content_str(root_dir, intervals, plain_cells, values):
    tree = xml.etree.ElementTree.parse(os.path.join(root_dir, _CONTENT_FNAME))
    root = tree.getroot()

    for k, v in intervals.items():
        val = values.get(k)
        if val:
            if not isinstance(v, list):
                v = [v]
            _write_sequence(tree, v, val)

    for k, v in plain_cells.items():
        val = values.get(k)
        if val:
            _write(tree, v, val)

    return xml.etree.ElementTree.tostring(root, encoding='utf8', method='xml')


def fill_template(root_dir, intervals, plain_cells, values):
    proxy_file = io.BytesIO()
    with zipfile.ZipFile(proxy_file, "w", compression=zipfile.ZIP_DEFLATED) as myzip:
        for root, subdirs, files in os.walk(root_dir):
            for f in files:
                if f[-4:] in ['.swp', 'xml~']:
                    continue
                if f == _CONTENT_FNAME:
                    continue
                fname = os.path.join(root, f)
                myzip.write(fname, arcname=fname[len(root_dir):])

        myzip.writestr(
            _CONTENT_FNAME,
            _content_str(
                root_dir,
                intervals,
                plain_cells,
                values
            )
        )

    return proxy_file.getvalue()


def make_response(document, filename):
    response = HttpResponse(
        content_type='application/vnd.oasis.opendocument.text'
    )
    response[
        'Content-Disposition'
    ] = 'attachment; filename={}'.format(filename)
    response.write(document)
    return response


UNOCONV_COMMANDS = ['unoconv']

try:
    from .unoconv_local import *
except ImportError:
    pass


def convert_to_pdf(document, suffix='.odt'):
    src = NamedTemporaryFile(suffix=suffix, delete=False)
    src.write(document)
    src.flush()

    command = UNOCONV_COMMANDS + [
        '-f',
        'pdf',
        src.name
    ]
    subprocess.run(command)

    dst = open(src.name[:-3]+'pdf', 'rb')
    return dst.read()


def make_response_pdf(document, filename):
    response = HttpResponse(content_type='application/pdf')
    response[
        'Content-Disposition'
    ] = 'attachment; filename={}'.format(filename)
    response.write(convert_to_pdf(document))

    return response
