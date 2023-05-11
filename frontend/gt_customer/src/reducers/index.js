import { combineReducers } from 'redux';
import user from './user';
import requests from './requests';
import requests_on_map from './requests_on_map';
import selected_request_on_map from './selected_request_on_map';
import reports from './reports';
import contacts from './contacts';
import imports from './imports';
import invoices from './invoices';

export default combineReducers({
    user,
    requests,
    requests_on_map,
    selected_request_on_map,
    reports,
    contacts,
    imports,
    invoices,
});
