import FileDownload from 'js-file-download';
import { parse } from 'content-disposition';
import { BACKEND_URL } from '../constants';
import axios from 'axios';
import { getToken, showError } from '../index';

const downloadFile =
    ({ url, filename, params = {}, method = 'get' }) =>
    () => {
        const token = getToken();
        return axios({
            method,
            url: `${BACKEND_URL}${url}`,
            params,
            headers: {
                Authorization: `Bearer ${token}`,
            },
            responseType: 'blob',
        }).then((response) => {
            try {
                const disposition = parse(
                    response.request.getResponseHeader('Content-Disposition')
                );
                filename = disposition.parameters.filename;
            } catch (exception) {
                // nothing to do
            }
            FileDownload(response.data, filename);
        });
    };

export default downloadFile;
