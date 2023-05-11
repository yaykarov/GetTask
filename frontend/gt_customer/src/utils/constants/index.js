import { getEnvValue } from '..';

export const DADATA_API_KEY = '864c4422fa0e7f050a37d04c1dc17ef57bb4f879';
export const BACKEND_URL = getEnvValue(
    'REACT_APP_GT_BO_BASE_URL_SERVER',
    'http://dulemaga.ru:8002/'
);
export const ITEMS_ON_PAGE = 50;
export const REQUESTS_PREFIX = 'requests';
export const REQUESTS_ON_MAP_PREFIX = 'requests_on_map';
export const IMPORTS_PREFIX = 'imports';
export const REPORTS_PREFIX = 'reports';
export const BALANCE_PREFIX = 'balance';
