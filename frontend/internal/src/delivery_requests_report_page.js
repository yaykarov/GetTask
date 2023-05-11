import React from 'react';
import ReactDOM from 'react-dom';
import { RequestsReport } from './pages/DeliveryRequestsReportPage.jsx';

ReactDOM.render(<RequestsReport {...window.getPageProps()}/>, document.getElementById('root'));
